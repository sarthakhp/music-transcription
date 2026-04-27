"""Shared Basic Pitch inference wrapper.

Handles calling basic_pitch.inference.predict() with the correct parameters
and returns raw note events. Used by both BassTranscriber and MelodicTranscriber.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_basic_pitch(
    audio_path: Path,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 0.058,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
    multiple_pitch_bends: bool = True,
    melodia_trick: bool = True,
) -> list[tuple]:
    """Run Basic Pitch inference on an audio file.

    Returns:
        List of note event tuples: (onset_sec, offset_sec, pitch_midi, amplitude, pitch_bends)
    """
    from basic_pitch.inference import predict

    kwargs = {
        "audio_path": str(audio_path),
        "onset_threshold": onset_threshold,
        "frame_threshold": frame_threshold,
        "minimum_note_length": minimum_note_length,
        "multiple_pitch_bends": multiple_pitch_bends,
        "melodia_trick": melodia_trick,
    }

    if minimum_frequency is not None:
        kwargs["minimum_frequency"] = minimum_frequency
    if maximum_frequency is not None:
        kwargs["maximum_frequency"] = maximum_frequency

    logger.info(
        f"Running Basic Pitch: freq={minimum_frequency}-{maximum_frequency}Hz, "
        f"onset_thresh={onset_threshold}, frame_thresh={frame_threshold}"
    )

    model_output, midi_data, note_events = predict(**kwargs)

    logger.info(f"Basic Pitch detected {len(note_events)} note events")
    return note_events
