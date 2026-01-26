import logging
from pathlib import Path

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from .config import TranscriptionConfig
from .constants import DEFAULT_TEMPO_BPM
from .models import NoteEvent, TranscriptionResult

logger = logging.getLogger(__name__)


class MidiGenerator:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()
        self.ticks_per_beat = 480

    def generate(self, result: TranscriptionResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        mid = MidiFile(ticks_per_beat=self.ticks_per_beat)

        meta_track = MidiTrack()
        mid.tracks.append(meta_track)
        tempo = mido.bpm2tempo(result.tempo_bpm or DEFAULT_TEMPO_BPM)
        meta_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
        meta_track.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))

        if result.key_info:
            key_signature = self._get_key_signature(result.key_info.tonic_name, result.key_info.scale_type)
            meta_track.append(MetaMessage('key_signature', key=key_signature, time=0))

        meta_track.append(MetaMessage('track_name', name='Vocals', time=0))

        vocal_track = MidiTrack()
        mid.tracks.append(vocal_track)

        events = self._create_events(result.notes, tempo)
        events.sort(key=lambda e: e[0])

        current_tick = 0
        for tick, msg in events:
            delta = tick - current_tick
            msg.time = max(0, delta)
            vocal_track.append(msg)
            current_tick = tick

        vocal_track.append(MetaMessage('end_of_track', time=0))

        mid.save(str(output_path))
        logger.info(f"Saved MIDI to {output_path} ({len(result.notes)} notes)")
        return output_path

    def _create_events(
        self,
        notes: list[NoteEvent],
        tempo: int
    ) -> list[tuple[int, Message]]:
        events = []

        for note in notes:
            start_tick = self._seconds_to_ticks(note.start_time, tempo)
            end_tick = self._seconds_to_ticks(note.end_time, tempo)

            midi_note = max(0, min(127, note.anchor_midi))
            velocity = max(1, min(127, note.velocity))

            events.append((start_tick, Message('note_on', note=midi_note, velocity=velocity, channel=0)))
            events.append((end_tick, Message('note_off', note=midi_note, velocity=0, channel=0)))

        return events

    def _seconds_to_ticks(self, seconds: float, tempo: int) -> int:
        beats = seconds * (1_000_000 / tempo)
        return int(beats * self.ticks_per_beat)

    def _ticks_to_seconds(self, ticks: int, tempo: int) -> float:
        beats = ticks / self.ticks_per_beat
        return beats * (tempo / 1_000_000)

    def _get_key_signature(self, tonic_name: str, scale_type: str) -> str:
        major_keys = {
            "C": "C", "G": "G", "D": "D", "A": "A", "E": "E", "B": "B",
            "F#": "F#", "C#": "C#", "F": "F", "Bb": "Bb", "Eb": "Eb",
            "Ab": "Ab", "Db": "Db", "Gb": "Gb"
        }

        minor_keys = {
            "A": "Am", "E": "Em", "B": "Bm", "F#": "F#m", "C#": "C#m",
            "G#": "G#m", "D#": "D#m", "A#": "A#m", "D": "Dm", "G": "Gm",
            "C": "Cm", "F": "Fm", "Bb": "Bbm", "Eb": "Ebm"
        }

        if "minor" in scale_type.lower() or scale_type.lower() in ["kafi", "asavari", "bhairavi"]:
            return minor_keys.get(tonic_name, "C")
        else:
            return major_keys.get(tonic_name, "C")

