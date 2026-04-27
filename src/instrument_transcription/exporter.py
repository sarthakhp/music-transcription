"""Export instrument transcription results to JSON."""

import json
import logging
from pathlib import Path

from .models import InstrumentTranscriptionResult

logger = logging.getLogger(__name__)


def export_instrument_transcription(
    result: InstrumentTranscriptionResult,
    output_path: str | Path,
    tempo_bpm: float | None = None,
) -> Path:
    """Export instrument transcription to a JSON file.

    Args:
        result: The transcription result containing all instrument tracks.
        output_path: Path to write the JSON file.
        tempo_bpm: Optional tempo from the vocal transcription stage.

    Returns:
        The output path.
    """
    output_path = Path(output_path)

    data = {
        "metadata": {
            "duration": result.duration,
            "total_notes": result.total_notes,
            "instruments": list(result.tracks.keys()),
            "tempo_bpm": tempo_bpm,
        },
        "tracks": {},
    }

    for instrument, track in result.tracks.items():
        data["tracks"][instrument] = {
            "num_notes": track.num_notes,
            "duration": track.duration,
            "notes": [
                {
                    "onset": round(float(note.onset), 4),
                    "offset": round(float(note.offset), 4),
                    "duration": round(float(note.duration), 4),
                    "pitch": int(note.pitch),
                    "velocity": int(note.velocity),
                    "confidence": round(float(note.confidence), 4),
                    "pitch_bends": [round(float(b), 4) for b in note.pitch_bends] if note.pitch_bends else [],
                }
                for note in track.notes
            ],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Exported instrument transcription to {output_path} ({result.total_notes} notes)")
    return output_path
