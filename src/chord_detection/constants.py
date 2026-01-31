DEFAULT_SAMPLE_RATE = 22050
DEFAULT_HOP_LENGTH = 4410
DEFAULT_TEMPO_BPM = 120.0

CHORD_VOCABULARY_MAJMIN = [
    "C", "C:min", "C#", "C#:min", "D", "D:min", "D#", "D#:min",
    "E", "E:min", "F", "F:min", "F#", "F#:min", "G", "G:min",
    "G#", "G#:min", "A", "A:min", "A#", "A#:min", "B", "B:min", "N"
]

ROOT_LIST = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
QUALITY_LIST = ["min", "maj", "dim", "aug", "min6", "maj6", "min7", "minmaj7", "maj7", "7", "dim7", "hdim7", "sus2", "sus4"]

def _build_extended_vocabulary():
    vocab = {}
    for i in range(168):
        root = i // 14
        root = ROOT_LIST[root]
        quality = i % 14
        quality = QUALITY_LIST[quality]
        if i % 14 != 1:
            chord = root + ":" + quality
        else:
            chord = root
        vocab[i] = chord
    vocab[168] = "X"
    vocab[169] = "N"
    return [vocab[i] for i in range(170)]

CHORD_VOCABULARY_EXTENDED = _build_extended_vocabulary()

