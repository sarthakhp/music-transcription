import logging
import shutil
from pathlib import Path
from typing import Literal

import numpy as np
import torch
import torchaudio
from pydub import AudioSegment

logger = logging.getLogger(__name__)


def save_stem_as_mp3(
    stem_name: str,
    audio_data: np.ndarray,
    output_dir: Path,
    base_filename: str,
    sample_rate: int = 44100,
    bitrate: str = "320k",
) -> Path:
    mp3_path = output_dir / f"{base_filename}_{stem_name}.mp3"
    temp_wav_path = output_dir / f"_temp_{base_filename}_{stem_name}.wav"

    try:
        audio_tensor = torch.tensor(audio_data)
        torchaudio.save(str(temp_wav_path), audio_tensor, sample_rate)

        audio_segment = AudioSegment.from_wav(str(temp_wav_path))
        audio_segment.export(str(mp3_path), format="mp3", bitrate=bitrate)

        logger.info(f"Saved {stem_name} stem to {mp3_path}")
        return mp3_path

    finally:
        if temp_wav_path.exists():
            temp_wav_path.unlink()


def save_stems_as_mp3(
    stems: dict[str, np.ndarray],
    output_dir: Path,
    base_filename: str,
    sample_rate: int = 44100,
    bitrate: str = "320k",
    verbose: bool = True,
) -> dict[str, Path]:
    stem_paths = {}

    for stem_name, audio_data in stems.items():
        mp3_path = save_stem_as_mp3(
            stem_name=stem_name,
            audio_data=audio_data,
            output_dir=output_dir,
            base_filename=base_filename,
            sample_rate=sample_rate,
            bitrate=bitrate,
        )

        if verbose:
            print(f"  - {stem_name} (MP3): {mp3_path}")

        stem_paths[stem_name] = mp3_path

    return stem_paths


def copy_original_audio(
    input_audio_path: Path,
    output_dir: Path,
    output_format: Literal["mp3", "wav", "flac"] = "mp3",
    bitrate: str = "320k",
    verbose: bool = True,
) -> Path | None:
    output_path = output_dir / f"{input_audio_path.stem}_original.{output_format}"

    try:
        if input_audio_path.suffix.lower() == f".{output_format}":
            shutil.copy2(input_audio_path, output_path)
            if verbose:
                print(f"  - Original ({output_format.upper()}): {output_path}")
        else:
            audio_segment = AudioSegment.from_file(str(input_audio_path))

            if output_format == "mp3":
                audio_segment.export(str(output_path), format="mp3", bitrate=bitrate)
            elif output_format == "wav":
                audio_segment.export(str(output_path), format="wav")
            elif output_format == "flac":
                audio_segment.export(str(output_path), format="flac")

            if verbose:
                print(f"  - Original ({output_format.upper()}): {output_path}")

        logger.info(f"Saved original audio to {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"Failed to copy/convert original audio: {e}")
        if verbose:
            print(f"  - Warning: Could not copy original audio file")
        return None

