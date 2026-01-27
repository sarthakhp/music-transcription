import json
import logging
from pathlib import Path

from .models import PitchFrame

logger = logging.getLogger(__name__)


def export_processed_frames(
    processed_frames: list[PitchFrame],
    output_path: str | Path,
    original_song_path: str | Path | None = None,
    vocal_file_path: str | Path | None = None,
    instrumental_file_path: str | Path | None = None,
    bpm: float | None = None,
    **additional_metadata
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    metadata = {}
    
    if original_song_path:
        metadata["original_song_path"] = str(Path(original_song_path).resolve())
    
    if vocal_file_path:
        metadata["vocal_file_path"] = str(Path(vocal_file_path).resolve())
    
    if instrumental_file_path:
        metadata["instrumental_file_path"] = str(Path(instrumental_file_path).resolve())
    
    if bpm is not None:
        metadata["bpm"] = bpm
    
    metadata.update(additional_metadata)
    
    frames_data = [
        {
            "time": frame.time,
            "frequency": frame.frequency,
            "confidence": frame.confidence,
            "midi_pitch": frame.midi_pitch,
            "is_voiced": frame.is_voiced,
        }
        for frame in processed_frames
    ]
    
    data = {
        "metadata": metadata,
        "processed_frames": frames_data,
        "frame_count": len(processed_frames),
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Exported {len(processed_frames)} processed frames to {output_path}")
    return output_path

