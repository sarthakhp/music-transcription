#!/usr/bin/env python3

import logging
from pathlib import Path
import soundfile as sf

from src.chord_detection import ChordDetector, ChordDetectionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_chord_detection_on_instrumental():
    logger.info("=" * 80)
    logger.info("CHORD DETECTION TEST ON REAL AUDIO")
    logger.info("=" * 80)
    
    # Audio file path
    audio_path = "output/separated/mitti-ke-bete-120_sec_instrumental.wav"
    output_dir = Path("output/chords")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"\nInput file: {audio_path}")
    
    # Load audio info
    info = sf.info(audio_path)
    logger.info(f"Audio info: {info.duration:.2f}s, {info.samplerate}Hz, {info.channels} channels")
    
    # Create detector with BTC model
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Initialize Chord Detector")
    logger.info("=" * 80)
    
    config = ChordDetectionConfig(
        model_path="models/chord_detection/btc_model.pt",
        use_voca=False,  # Use maj/min vocabulary (25 chords)
        device="auto",
        min_chord_duration_ms=200,  # Filter chords shorter than 200ms
        smooth_chords=True,
        filter_low_confidence=0.3,
    )
    
    detector = ChordDetector(config)
    
    # Load BTC model
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Load BTC Model")
    logger.info("=" * 80)
    
    detector.load_model()
    
    # For testing, we'll use the instrumental file directly
    # In production, you'd use bass + other stems
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Run Chord Detection")
    logger.info("=" * 80)
    logger.info("NOTE: Using instrumental file directly (ideally use bass + other stems)")
    
    # Load audio
    audio, sr = sf.read(audio_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # Convert to mono
    
    # Run prediction directly on instrumental
    logger.info(f"Running BTC inference on {len(audio)/sr:.2f}s of audio...")
    raw_predictions = detector.btc_model.predict(audio, sr)
    
    # Post-process
    logger.info("Post-processing predictions...")
    chords = detector.post_processor.process(raw_predictions)
    
    # Create progression
    from src.chord_detection.models import ChordProgression
    progression = ChordProgression(
        chords=chords,
        duration=len(audio) / sr,
        sample_rate=sr,
        tempo_bpm=120.0,
        key_info={},
    )
    
    # Export results
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Export Results")
    logger.info("=" * 80)
    
    base_name = "mitti-ke-bete-120_sec"
    
    json_path = output_dir / f"{base_name}_chords.json"
    lab_path = output_dir / f"{base_name}_chords.lab"
    csv_path = output_dir / f"{base_name}_chords.csv"
    
    detector.save_json(progression, json_path)
    detector.save_lab(progression, lab_path)
    detector.save_csv(progression, csv_path)
    
    # Display results
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 80)
    
    logger.info(f"Total duration: {progression.duration:.2f}s")
    logger.info(f"Total chords detected: {len(progression.chords)}")
    logger.info(f"Average chord duration: {progression.duration / len(progression.chords):.2f}s")
    
    # Show first 10 chords
    logger.info("\nFirst 10 chords:")
    logger.info("-" * 80)
    logger.info(f"{'Time':<15} {'Chord':<10} {'Duration':<12} {'Confidence':<12}")
    logger.info("-" * 80)
    
    for i, chord in enumerate(progression.chords[:10]):
        time_str = f"{chord.start_time:.2f}-{chord.end_time:.2f}s"
        duration_str = f"{chord.duration:.2f}s"
        conf_str = f"{chord.confidence:.3f}"
        logger.info(f"{time_str:<15} {chord.chord_label:<10} {duration_str:<12} {conf_str:<12}")
    
    if len(progression.chords) > 10:
        logger.info(f"... and {len(progression.chords) - 10} more chords")
    
    # Chord statistics
    logger.info("\n" + "=" * 80)
    logger.info("CHORD STATISTICS")
    logger.info("=" * 80)
    
    from collections import Counter
    chord_counts = Counter(chord.chord_label for chord in progression.chords)
    
    logger.info(f"Unique chords: {len(chord_counts)}")
    logger.info("\nMost common chords:")
    for chord_label, count in chord_counts.most_common(10):
        percentage = (count / len(progression.chords)) * 100
        logger.info(f"  {chord_label:<10} {count:>3} times ({percentage:>5.1f}%)")
    
    logger.info("\n" + "=" * 80)
    logger.info("✓ CHORD DETECTION COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"\nOutput files:")
    logger.info(f"  JSON: {json_path}")
    logger.info(f"  LAB:  {lab_path}")
    logger.info(f"  CSV:  {csv_path}")


if __name__ == "__main__":
    test_chord_detection_on_instrumental()

