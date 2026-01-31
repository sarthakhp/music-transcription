#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from src.chord_detection import ChordDetector, ChordDetectionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Detect chords from audio stems")
    parser.add_argument("--bass-path", type=str, help="Path to bass stem audio file")
    parser.add_argument("--other-path", type=str, help="Path to other stem audio file")
    parser.add_argument("--instrumental-path", type=str, help="Path to instrumental audio file")
    parser.add_argument("--output-dir", type=str, default="output/chords", help="Output directory")
    parser.add_argument("--model-path", type=str, default="models/chord_detection/btc_model.pt", help="Path to BTC model")
    parser.add_argument("--use-voca", action="store_true", help="Use extended vocabulary (170 chords) instead of maj/min (25 chords)")
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--min-duration", type=int, default=200, help="Minimum chord duration in milliseconds")
    parser.add_argument("--confidence", type=float, default=0.3, help="Confidence threshold for filtering")
    parser.add_argument("--no-smooth", action="store_true", help="Disable chord smoothing")
    parser.add_argument("--tempo", type=float, default=120.0, help="Tempo in BPM")
    parser.add_argument("--output-name", type=str, help="Base name for output files (default: derived from input)")

    args = parser.parse_args()

    if not args.bass_path and not args.other_path and not args.instrumental_path:
        logger.error("At least one of --bass-path, --other-path, or --instrumental-path must be provided")
        parser.print_help()
        return

    bass_path = Path(args.bass_path) if args.bass_path else None
    other_path = Path(args.other_path) if args.other_path else None
    instrumental_path = Path(args.instrumental_path) if args.instrumental_path else None

    if bass_path and not bass_path.exists():
        logger.error(f"Bass file not found: {bass_path}")
        return

    if other_path and not other_path.exists():
        logger.error(f"Other file not found: {other_path}")
        return

    if instrumental_path and not instrumental_path.exists():
        logger.error(f"Instrumental file not found: {instrumental_path}")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = ChordDetectionConfig(
        model_path=args.model_path,
        use_voca=args.use_voca,
        device=args.device,
        min_chord_duration_ms=args.min_duration,
        smooth_chords=not args.no_smooth,
        filter_low_confidence=args.confidence,
    )

    logger.info(f"Configuration: model={config.model_path}, device={config.get_device()}, min_duration={config.min_chord_duration_ms}ms")
    logger.info(f"Vocabulary: {'Extended (170 chords)' if config.use_voca else 'Maj/Min (25 chords)'}")

    detector = ChordDetector(config)

    logger.info("Loading BTC model...")
    detector.load_model()

    logger.info("Running chord detection...")
    progression = detector.detect_from_stems(
        bass_path=bass_path,
        other_path=other_path,
        instrumental_path=instrumental_path,
        tempo_bpm=args.tempo,
    )

    if args.output_name:
        base_name = args.output_name
    else:
        if instrumental_path:
            base_name = instrumental_path.stem
        elif bass_path:
            base_name = bass_path.stem.replace("_bass", "")
        elif other_path:
            base_name = other_path.stem.replace("_other", "")

    json_path = output_dir / f"{base_name}_chords.json"
    lab_path = output_dir / f"{base_name}_chords.lab"
    csv_path = output_dir / f"{base_name}_chords.csv"

    detector.save_json(progression, json_path)
    logger.info(f"JSON saved: {json_path}")

    detector.save_lab(progression, lab_path)
    logger.info(f"LAB saved: {lab_path}")

    detector.save_csv(progression, csv_path)
    logger.info(f"CSV saved: {csv_path}")

    print(f"\n{'='*60}")
    print(f"Chord Detection Complete!")
    print(f"{'='*60}")
    print(f"Duration: {progression.duration:.2f} seconds")
    print(f"Chords detected: {len(progression.chords)}")
    print(f"Average chord duration: {progression.duration / len(progression.chords):.2f}s")
    print(f"\nOutput files:")
    print(f"  JSON: {json_path}")
    print(f"  LAB:  {lab_path}")
    print(f"  CSV:  {csv_path}")
    print(f"{'='*60}")

    from collections import Counter
    chord_counts = Counter(chord.chord_label for chord in progression.chords)
    
    print(f"\nChord Statistics:")
    print(f"  Unique chords: {len(chord_counts)}")
    print(f"\n  Most common chords:")
    for chord_label, count in chord_counts.most_common(10):
        percentage = (count / len(progression.chords)) * 100
        print(f"    {chord_label:<10} {count:>3} times ({percentage:>5.1f}%)")


if __name__ == "__main__":
    main()

