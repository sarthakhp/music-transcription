import logging
from pathlib import Path

import torch
import torchaudio
import numpy as np

from .config import SeparationConfig
from .constants import KNOWN_STEMS

logger = logging.getLogger(__name__)


def extract_stem_name(filename: str) -> str:
    filename_lower = filename.lower()
    for stem in KNOWN_STEMS:
        if stem in filename_lower:
            return stem
    return "other"


def process_chunk(
    chunk: torch.Tensor,
    sr: int,
    separator,
    config: SeparationConfig,
) -> dict[str, np.ndarray]:
    temp_path = config.output_dir / "_temp_chunk.wav"
    torchaudio.save(str(temp_path), chunk, sr)
    input_samples = chunk.shape[1]

    try:
        output_files = separator.separate(str(temp_path))

        stems = {}
        for output_file in output_files:
            output_path = config.output_dir / Path(output_file).name
            stem_name = extract_stem_name(output_path.stem)
            if stem_name in config.stems:
                audio, output_sr = torchaudio.load(str(output_path))
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

