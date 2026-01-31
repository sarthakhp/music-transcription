#!/usr/bin/env python3
"""
Test chord detection integration with flexible stem availability.
"""
import logging
from pathlib import Path

from src.chord_detection import ChordDetector, ChordDetectionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_with_instrumental():
    """Test chord detection using only instrumental stem."""
    logger.info("=" * 80)
    logger.info("TEST: Chord Detection with Instrumental Only")
    logger.info("=" * 80)
    
    instrumental_path = "output/separated/mitti-ke-bete-120_sec_instrumental.wav"
    
    if not Path(instrumental_path).exists():
        logger.error(f"Instrumental file not found: {instrumental_path}")
        return
    
    config = ChordDetectionConfig(
        model_path="models/chord_detection/btc_model.pt",
        use_voca=False,
        device="auto",
        min_chord_duration_ms=200,
        smooth_chords=True,
        filter_low_confidence=0.3,
    )
    
    detector = ChordDetector(config)
    detector.load_model()
    
    logger.info("\nDetecting chords from instrumental stem only...")
    progression = detector.detect_from_stems(
        instrumental_path=instrumental_path,
        tempo_bpm=120.0,
    )
    
    logger.info(f"\n✓ Success!")
    logger.info(f"  Duration: {progression.duration:.2f}s")
    logger.info(f"  Chords detected: {len(progression.chords)}")
    logger.info(f"  Average chord duration: {progression.duration / len(progression.chords):.2f}s")
    
    output_dir = Path("output/test_integration")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    detector.save_json(progression, output_dir / "test_instrumental_chords.json")
    detector.save_lab(progression, output_dir / "test_instrumental_chords.lab")
    detector.save_csv(progression, output_dir / "test_instrumental_chords.csv")
    
    logger.info(f"\n✓ Output files saved to: {output_dir}")


def test_find_available_stems():
    """Test the find_available_stems function."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Find Available Stems")
    logger.info("=" * 80)
    
    output_dir = Path("output/separated")
    base_filename = "mitti-ke-bete-120_sec"
    
    stems = {}
    
    bass_wav = output_dir / f"{base_filename}_bass.wav"
    if bass_wav.exists():
        stems["bass"] = bass_wav
        logger.info(f"✓ Found bass stem: {bass_wav}")
    else:
        logger.info(f"✗ Bass stem not found: {bass_wav}")
    
    other_wav = output_dir / f"{base_filename}_other.wav"
    if other_wav.exists():
        stems["other"] = other_wav
        logger.info(f"✓ Found other stem: {other_wav}")
    else:
        logger.info(f"✗ Other stem not found: {other_wav}")
    
    instrumental_wav = output_dir / f"{base_filename}_instrumental.wav"
    if instrumental_wav.exists():
        stems["instrumental"] = instrumental_wav
        logger.info(f"✓ Found instrumental stem: {instrumental_wav}")
    else:
        logger.info(f"✗ Instrumental stem not found: {instrumental_wav}")
    
    logger.info(f"\nAvailable stems: {list(stems.keys())}")
    
    if stems:
        logger.info("\n✓ At least one stem is available for chord detection")
    else:
        logger.warning("\n✗ No stems available for chord detection")


if __name__ == "__main__":
    test_find_available_stems()
    print()
    test_with_instrumental()
    
    print("\n" + "=" * 80)
    print("✓ ALL TESTS COMPLETE")
    print("=" * 80)

