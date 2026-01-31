import json
import logging
from pathlib import Path

from .models import ChordProgression, ChordEvent

logger = logging.getLogger(__name__)


class ChordExporter:
    @staticmethod
    def export_json(progression: ChordProgression, output_path: str | Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "duration": progression.duration,
            "sample_rate": progression.sample_rate,
            "tempo_bpm": progression.tempo_bpm,
            "key_info": progression.key_info,
            "num_chords": len(progression.chords),
            "chords": [
                {
                    "start_time": chord.start_time,
                    "end_time": chord.end_time,
                    "duration": chord.duration,
                    "chord_label": chord.chord_label,
                    "confidence": chord.confidence,
                    "root": chord.root,
                    "quality": chord.quality,
                    "bass": chord.bass,
                }
                for chord in progression.chords
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(progression.chords)} chords to JSON: {output_path}")

    @staticmethod
    def export_lab(progression: ChordProgression, output_path: str | Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            for chord in progression.chords:
                f.write(f"{chord.start_time:.6f}\t{chord.end_time:.6f}\t{chord.chord_label}\n")

        logger.info(f"Exported {len(progression.chords)} chords to LAB: {output_path}")

    @staticmethod
    def export_csv(progression: ChordProgression, output_path: str | Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("start_time,end_time,duration,chord_label,confidence,root,quality,bass\n")
            for chord in progression.chords:
                f.write(
                    f"{chord.start_time:.6f},{chord.end_time:.6f},{chord.duration:.6f},"
                    f"{chord.chord_label},{chord.confidence:.4f},"
                    f"{chord.root},{chord.quality},{chord.bass}\n"
                )

        logger.info(f"Exported {len(progression.chords)} chords to CSV: {output_path}")

