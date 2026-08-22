import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional

import torch
import torchaudio
import numpy as np

from src.audio_io import load_audio
from .config import SeparationConfig
from .constants import KNOWN_STEMS

logger = logging.getLogger(__name__)


@contextmanager
def _timed(label: str):
    t0 = time.monotonic()
    try:
        yield
    finally:
        logger.debug(f"[timing] {label}: {time.monotonic() - t0:.2f}s")


def extract_stem_name(filename: str) -> str:
    filename_lower = filename.lower()
    for stem in KNOWN_STEMS:
        if stem in filename_lower:
            return stem
    return "other"


def _make_progress_tqdm(
    base_tqdm,
    start_pct: int,
    end_pct: int,
    progress_callback: Callable[[int, str], None],
):
    """Return a tqdm subclass that drives progress_callback from real model steps.

    Each tqdm.update() maps the current step count linearly from start_pct to
    end_pct and calls progress_callback(pct, message). This replaces the
    time-based estimator with accurate, model-derived progress.

    We patch the specific architecture modules (MDX / MDXC) because tqdm is
    imported there at the top level. If audio-separator moves the loop to a
    different file, the patch silently falls back to the original tqdm — so
    update _TQDM_MODULES in process_chunk if progress stops working after an
    upstream upgrade.
    """
    class _ProgressTqdm(base_tqdm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._step_start = time.monotonic()

        def update(self, n=1):
            result = super().update(n)
            elapsed = time.monotonic() - self._step_start
            self._step_start = time.monotonic()
            logger.debug(f"[tqdm] step {self.n}/{self.total}: {elapsed:.2f}s")
            if self.total:
                pct = int(start_pct + (end_pct - start_pct) * self.n / self.total)
                try:
                    progress_callback(pct, f"Separating audio (step {self.n}/{self.total})")
                except Exception as exc:
                    logger.warning(f"Progress callback failed in tqdm step: {exc}")
            return result

    return _ProgressTqdm


# Architecture modules that contain the tqdm inference loop.
# Both MDX and MDXC are patched since the model is picked at runtime.
_TQDM_MODULES = [
    "audio_separator.separator.architectures.mdx_separator",
    "audio_separator.separator.architectures.mdxc_separator",
]


def process_chunk(
    chunk: torch.Tensor,
    sr: int,
    separator,
    config: SeparationConfig,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    progress_start_pct: int = 20,
    progress_end_pct: int = 95,
) -> dict[str, np.ndarray]:
    with _timed("write temp wav"):
        temp_fd, temp_path_str = tempfile.mkstemp(
            suffix=".wav", prefix="chunk_", dir=str(config.output_dir)
        )
        os.close(temp_fd)
        temp_path = Path(temp_path_str)
        torchaudio.save(str(temp_path), chunk, sr)

    input_samples = chunk.shape[1]

    # Patch each architecture module's tqdm with a progress-reporting subclass.
    # Restored unconditionally in the finally block.
    import importlib
    patched: list[tuple] = []
    if progress_callback:
        for mod_name in _TQDM_MODULES:
            try:
                mod = importlib.import_module(mod_name)
                base = mod.tqdm
                mod.tqdm = _make_progress_tqdm(base, progress_start_pct, progress_end_pct, progress_callback)
                patched.append((mod, base))
            except Exception as exc:
                logger.warning(f"Could not patch tqdm in {mod_name}: {exc}")

    try:
        with _timed("separator.separate"):
            output_files = separator.separate(str(temp_path))

        stems = {}
        for output_file in output_files:
            output_path = config.output_dir / Path(output_file).name
            if not output_path.exists():
                logger.error(
                    f"Expected separated stem not found at {output_path}. "
                    f"separator.separate() returned {output_files!r}, "
                    f"config.output_dir={config.output_dir}"
                )
                raise FileNotFoundError(
                    f"Separated stem not found: {output_path}. "
                    f"audio_separator may have written to a different directory."
                )
            stem_name = extract_stem_name(output_path.stem)
            if stem_name in config.stems:
                audio, output_sr = load_audio(output_path)
                output_samples = audio.shape[1]

                logger.debug(
                    f"Chunk {stem_name}: input={input_samples} samples ({input_samples/sr:.2f}s @ {sr}Hz), "
                    f"output={output_samples} samples ({output_samples/output_sr:.2f}s @ {output_sr}Hz), "
                    f"diff={output_samples - input_samples} samples ({(output_samples - input_samples)/sr*1000:.1f}ms)"
                )

                if output_sr != sr:
                    logger.warning(f"Unexpected sample rate mismatch: input {sr}Hz, output {output_sr}Hz")

                if output_samples != input_samples:
                    diff_ms = (output_samples - input_samples) / sr * 1000
                    if abs(diff_ms) > 10:
                        logger.warning(
                            f"Length mismatch for {stem_name}: input {input_samples}, output {output_samples} "
                            f"(diff: {output_samples - input_samples} samples = {diff_ms:.1f}ms)"
                        )
                    if output_samples > input_samples:
                        audio = audio[:, :input_samples]
                    else:
                        padding = torch.zeros((audio.shape[0], input_samples - output_samples))
                        audio = torch.cat([audio, padding], dim=1)

                stems[stem_name] = audio.numpy()
                output_path.unlink(missing_ok=True)

        return stems
    finally:
        temp_path.unlink(missing_ok=True)
        for mod, base in patched:
            mod.tqdm = base
