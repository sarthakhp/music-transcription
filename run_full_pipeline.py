#!/usr/bin/env python3
"""
Full Music Transcription Pipeline
Orchestrates source separation and vocal transcription in a single automated workflow.
"""
import logging
from pathlib import Path

from src.source_separation import (
    SeparationConfig,
    AppleSiliconSeparator,
    save_stems_as_mp3,
    copy_original_audio,
)
from src.vocal_transcription import VocalTranscriber, TranscriptionConfig
from src.chord_detection import ChordDetector, ChordDetectionConfig

# Configuration
INPUT_AUDIO_PATH = "/Users/psarthak/personal/projects/music-transcription/files/mitti-ke-bete-120_sec.mp3"  # Change this to your audio file

# Output directories
SEPARATION_OUTPUT_DIR = Path("output/separated")
TRANSCRIPTION_OUTPUT_DIR = Path("output/transcription")
CHORD_OUTPUT_DIR = Path("output/chords")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_separation(audio_path: Path, output_dir: Path) -> dict[str, Path]:
    """
    Run source separation on the input audio file.
    
    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save separated stems
        
    Returns:
        Dictionary mapping stem names to their output file paths
        
    Raises:
        Exception: If separation fails
    """
    print(f"\n{'='*60}")
    print(f"STEP 1: SOURCE SEPARATION")
    print(f"{'='*60}")
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
    stem_paths = save_stems_as_mp3(
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
    
    print(f"\n{'='*60}")
    print(f"STEP 1 COMPLETE: Source separation finished successfully")
    print(f"{'='*60}\n")
    
    return stem_paths


def run_transcription(vocals_path: Path, original_audio_path: Path, output_dir: Path) -> None:
    """
    Run vocal transcription on the separated vocals stem.
    
    Args:
        vocals_path: Path to vocals MP3 file
        original_audio_path: Path to original audio for tempo detection
        output_dir: Directory to save transcription outputs
        
    Raises:
        Exception: If transcription fails
    """
    print(f"\n{'='*60}")
    print(f"STEP 2: VOCAL TRANSCRIPTION")
    print(f"{'='*60}")
    print(f"Vocals file: {vocals_path}")
    print(f"Original audio: {original_audio_path}")
    print(f"Output directory: {output_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    config = TranscriptionConfig(
        hop_size_ms=10,
        crepe_model="full",
        confidence_threshold=0.6,
        device="auto",
    )
    
    logger.info(f"Configuration: model={config.crepe_model}, hop={config.hop_size_ms}ms, device={config.get_device()}")
    
    transcriber = VocalTranscriber(config)
    
    print("\nStarting vocal transcription...")
    logger.info(f"Transcribing: {vocals_path}")
    result = transcriber.transcribe(
        vocals_path,
        original_audio_path=original_audio_path,
        output_dir=output_dir,
    )

    stem = vocals_path.stem

    # Save MIDI file
    midi_path = output_dir / f"{stem}.mid"
    transcriber.save_midi(result, midi_path)
    logger.info(f"MIDI saved: {midi_path}")
    print(f"\nOutput files:")
    print(f"  - MIDI: {midi_path}")

    # Export JSON
    json_path = output_dir / f"{stem}.json"
    transcriber.export_json(result, json_path)
    logger.info(f"JSON saved: {json_path}")
    print(f"  - JSON: {json_path}")

    # Export CSV
    csv_path = output_dir / f"{stem}_pitch.csv"
    transcriber.export_pitch_csv(result, csv_path)
    logger.info(f"CSV saved: {csv_path}")
    print(f"  - CSV: {csv_path}")

    print(f"\n{'='*60}")
    print(f"Transcription Complete!")
    print(f"{'='*60}")
    print(f"Duration: {result.duration:.2f} seconds")
    print(f"Notes detected: {len(result.notes)}")
    print(f"Tempo: {result.tempo_bpm:.1f} BPM")
    if result.key_info:
        print(f"Key: {result.key_info.tonic_name} {result.key_info.scale_type} (confidence: {result.key_info.confidence:.2f})")
    print(f"Output: {midi_path}")
    print(f"{'='*60}\n")


def find_available_stems(output_dir: Path, base_filename: str) -> dict:
    """
    Find available stems for chord detection.

    Args:
        output_dir: Directory containing separated stems
        base_filename: Base filename without extension

    Returns:
        Dictionary with available stem paths (bass, other, instrumental)
    """
    stems = {}

    bass_wav = output_dir / f"{base_filename}_bass.wav"
    if bass_wav.exists():
        stems["bass"] = bass_wav
        logger.info(f"Found bass stem: {bass_wav}")

    other_wav = output_dir / f"{base_filename}_other.wav"
    if other_wav.exists():
        stems["other"] = other_wav
        logger.info(f"Found other stem: {other_wav}")

    instrumental_wav = output_dir / f"{base_filename}_instrumental.wav"
    if instrumental_wav.exists():
        stems["instrumental"] = instrumental_wav
        logger.info(f"Found instrumental stem: {instrumental_wav}")

    return stems


def run_chord_detection(
    available_stems: dict,
    base_filename: str,
    output_dir: Path,
    tempo_bpm: float = 120.0,
) -> None:
    """
    Run chord detection on available stems.

    Args:
        available_stems: Dictionary with available stem paths
        base_filename: Base filename for output files
        output_dir: Directory to save chord detection outputs
        tempo_bpm: Tempo in BPM (default: 120.0)

    Raises:
        Exception: If chord detection fails
    """
    print(f"\n{'='*60}")
    print(f"STEP 3: CHORD DETECTION")
    print(f"{'='*60}")
    print(f"Available stems: {list(available_stems.keys())}")
    print(f"Output directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    config = ChordDetectionConfig(
        model_path="models/chord_detection/btc_model.pt",
        use_voca=False,
        device="auto",
        min_chord_duration_ms=200,
        smooth_chords=True,
        filter_low_confidence=0.3,
    )

    logger.info(f"Configuration: device={config.get_device()}, min_duration={config.min_chord_duration_ms}ms")

    detector = ChordDetector(config)

    print("\nLoading BTC model...")
    detector.load_model()

    print("\nRunning chord detection...")
    logger.info(f"Detecting chords from available stems")

    progression = detector.detect_from_stems(
        bass_path=available_stems.get("bass"),
        other_path=available_stems.get("other"),
        instrumental_path=available_stems.get("instrumental"),
        tempo_bpm=tempo_bpm,
    )

    json_path = output_dir / f"{base_filename}_chords.json"
    lab_path = output_dir / f"{base_filename}_chords.lab"
    csv_path = output_dir / f"{base_filename}_chords.csv"

    detector.save_json(progression, json_path)
    detector.save_lab(progression, lab_path)
    detector.save_csv(progression, csv_path)

    print(f"\n{'='*60}")
    print(f"Chord Detection Complete!")
    print(f"{'='*60}")
    print(f"Duration: {progression.duration:.2f} seconds")
    print(f"Chords detected: {len(progression.chords)}")
    print(f"Average chord duration: {progression.duration / len(progression.chords):.2f}s")
    print(f"\nOutput files:")
    print(f"  - JSON: {json_path}")
    print(f"  - LAB:  {lab_path}")
    print(f"  - CSV:  {csv_path}")
    print(f"{'='*60}\n")


def main():
    """
    Main pipeline orchestration function.
    """
    audio_path = Path(INPUT_AUDIO_PATH)

    # Validate input file
    if not audio_path.exists():
        print(f"Error: File not found: {audio_path}")
        print(f"Please update INPUT_AUDIO_PATH in the script to point to your audio file.")
        return 1

    print(f"\n{'#'*60}")
    print(f"# FULL MUSIC TRANSCRIPTION PIPELINE")
    print(f"{'#'*60}")
    print(f"Input: {audio_path}")
    print(f"Separation output: {SEPARATION_OUTPUT_DIR}")
    print(f"Transcription output: {TRANSCRIPTION_OUTPUT_DIR}")
    print(f"Chord detection output: {CHORD_OUTPUT_DIR}")
    print(f"{'#'*60}\n")

    try:
        # Step 1: Source Separation
        stem_paths = run_separation(audio_path, SEPARATION_OUTPUT_DIR)

        # Check if vocals stem was created
        if "vocals" not in stem_paths:
            print(f"Error: Vocals stem not found in separation output")
            return 1

        vocals_path = stem_paths["vocals"]

    except Exception as e:
        logger.error(f"Source separation failed: {e}", exc_info=True)
        print(f"\n{'='*60}")
        print(f"ERROR: Source separation failed")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"Pipeline aborted. Transcription will not be attempted.")
        print(f"{'='*60}\n")
        return 1

    try:
        # Step 2: Vocal Transcription
        run_transcription(vocals_path, audio_path, TRANSCRIPTION_OUTPUT_DIR)

    except Exception as e:
        logger.error(f"Vocal transcription failed: {e}", exc_info=True)
        print(f"\n{'='*60}")
        print(f"ERROR: Vocal transcription failed")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"Separation completed successfully, but transcription failed.")
        print(f"Separated stems are available in: {SEPARATION_OUTPUT_DIR}")
        print(f"{'='*60}\n")
        return 1

    try:
        # Step 3: Chord Detection
        available_stems = find_available_stems(SEPARATION_OUTPUT_DIR, audio_path.stem)

        if not available_stems:
            logger.warning("No stems available for chord detection (bass, other, or instrumental)")
            print(f"\n{'='*60}")
            print(f"WARNING: Skipping chord detection - no suitable stems found")
            print(f"{'='*60}\n")
        else:
            run_chord_detection(
                available_stems=available_stems,
                base_filename=audio_path.stem,
                output_dir=CHORD_OUTPUT_DIR,
                tempo_bpm=120.0,
            )

    except Exception as e:
        logger.error(f"Chord detection failed: {e}", exc_info=True)
        print(f"\n{'='*60}")
        print(f"ERROR: Chord detection failed")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"Previous steps completed successfully, but chord detection failed.")
        print(f"Separated stems: {SEPARATION_OUTPUT_DIR}")
        print(f"Transcription: {TRANSCRIPTION_OUTPUT_DIR}")
        print(f"{'='*60}\n")

    # Success!
    print(f"\n{'#'*60}")
    print(f"# PIPELINE COMPLETE!")
    print(f"{'#'*60}")
    print(f"All steps completed successfully!")
    print(f"\nOutputs:")
    print(f"  Separated stems: {SEPARATION_OUTPUT_DIR}")
    print(f"  Transcription:   {TRANSCRIPTION_OUTPUT_DIR}")
    print(f"  Chord detection: {CHORD_OUTPUT_DIR}")
    print(f"{'#'*60}\n")

    return 0


if __name__ == "__main__":
    exit(main())

