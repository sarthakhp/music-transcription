#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from src.vocal_transcription import VocalTranscriber, TranscriptionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Transcribe vocals to MIDI")
    parser.add_argument("audio_path", type=str, help="Path to vocals audio file")
    parser.add_argument("--output-dir", type=str, default="output/transcription", help="Output directory")
    parser.add_argument("--hop-size", type=int, default=10, help="Hop size in milliseconds")
    parser.add_argument("--model", type=str, default="full", choices=["tiny", "small", "medium", "large", "full"])
    parser.add_argument("--confidence", type=float, default=0.6, help="Confidence threshold")
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--export-csv", action="store_true", help="Export pitch contour as CSV")
    parser.add_argument("--export-json", action="store_true", help="Export transcription as JSON")
    parser.add_argument("--original-audio", type=str, help="Path to original audio for tempo detection (uses BeatNet)")

    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = TranscriptionConfig(
        hop_size_ms=args.hop_size,
        crepe_model=args.model,
        confidence_threshold=args.confidence,
        device=args.device,
    )

    logger.info(f"Configuration: model={config.crepe_model}, hop={config.hop_size_ms}ms, device={config.get_device()}")

    transcriber = VocalTranscriber(config)

    logger.info(f"Transcribing: {audio_path}")
    result = transcriber.transcribe(audio_path, original_audio_path=args.original_audio)

    stem = audio_path.stem

    midi_path = output_dir / f"{stem}.mid"
    transcriber.save_midi(result, midi_path)
    logger.info(f"MIDI saved: {midi_path}")

    if args.export_json:
        json_path = output_dir / f"{stem}.json"
        transcriber.export_json(result, json_path)
        logger.info(f"JSON saved: {json_path}")

    if args.export_csv:
        csv_path = output_dir / f"{stem}_pitch.csv"
        transcriber.export_pitch_csv(result, csv_path)
        logger.info(f"CSV saved: {csv_path}")

    print(f"\n{'='*60}")
    print(f"Transcription Complete!")
    print(f"{'='*60}")
    print(f"Duration: {result.duration:.2f} seconds")
    print(f"Notes detected: {len(result.notes)}")
    print(f"Tempo: {result.tempo_bpm:.1f} BPM")
    if result.key_info:
        print(f"Key: {result.key_info.tonic_name} {result.key_info.scale_type} (confidence: {result.key_info.confidence:.2f})")
    print(f"Output: {midi_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

