#!/usr/bin/env python3
import sys
import logging
from pathlib import Path

from src.source_separation import (
    SeparationConfig,
    AppleSiliconSeparator,
    save_stems_as_mp3,
    copy_original_audio,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_separation.py <audio_file> [output_dir]")
        print("Example: python run_separation.py song.mp3 output/separated")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/separated")

    if not audio_path.exists():
        print(f"Error: File not found: {audio_path}")
        sys.exit(1)

    print(f"Input file: {audio_path}")
    print(f"Output directory: {output_dir}")

    config = SeparationConfig(
        output_dir=output_dir,
        output_format="wav",
    )

    separator = AppleSiliconSeparator(config)

    print("\nStarting source separation...")
    stems = separator.separate(audio_path)

    print(f"\nSeparation complete! Found {len(stems)} stems:")

    # Save all stems as MP3 files
    save_stems_as_mp3(
        stems=stems,
        output_dir=output_dir,
        base_filename=audio_path.stem,
        sample_rate=config.sample_rate,
        bitrate="320k",
        verbose=True,
    )

    # Copy/convert original audio to output directory
    print("\nCopying original audio to output directory...")
    copy_original_audio(
        input_audio_path=audio_path,
        output_dir=output_dir,
        output_format="mp3",
        bitrate="320k",
        verbose=True,
    )


if __name__ == "__main__":
    main()

