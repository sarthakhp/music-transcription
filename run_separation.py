#!/usr/bin/env python3
import sys
import logging
from pathlib import Path

import torch
import torchaudio
from pydub import AudioSegment

from src.source_separation import SeparationConfig, AppleSiliconSeparator

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
    for stem_name, audio_data in stems.items():
        wav_path = output_dir / f"{audio_path.stem}_{stem_name}.wav"
        mp3_path = output_dir / f"{audio_path.stem}_{stem_name}.mp3"

        audio_tensor = torch.tensor(audio_data)

        torchaudio.save(str(wav_path), audio_tensor, config.sample_rate)
        print(f"  - {stem_name} (WAV): {wav_path}")

        audio_segment = AudioSegment.from_wav(str(wav_path))
        audio_segment.export(str(mp3_path), format="mp3", bitrate="320k")
        print(f"  - {stem_name} (MP3): {mp3_path}")


if __name__ == "__main__":
    main()

