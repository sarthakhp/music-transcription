#!/usr/bin/env python3
import sys
import logging
from pathlib import Path

import torchaudio

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
        output_path = output_dir / f"{audio_path.stem}_{stem_name}.wav"
        audio_tensor = torchaudio.functional.resample(
            __import__('torch').tensor(audio_data), 
            config.sample_rate, 
            config.sample_rate
        )
        torchaudio.save(str(output_path), audio_tensor, config.sample_rate)
        print(f"  - {stem_name}: {output_path}")


if __name__ == "__main__":
    main()

