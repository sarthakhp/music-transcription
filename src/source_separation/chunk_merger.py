import numpy as np


def merge_chunks(
    chunks: list[dict[str, np.ndarray]], overlap_samples: int
) -> dict[str, np.ndarray]:
    if not chunks:
        return {}

    merged = {}
    for stem in chunks[0].keys():
        stem_chunks = [c[stem] for c in chunks if stem in c]
        if not stem_chunks:
            continue

        if len(stem_chunks) == 1:
            merged[stem] = stem_chunks[0]
            continue

        total_length = stem_chunks[0].shape[1]
        for i in range(1, len(stem_chunks)):
            actual_overlap = min(overlap_samples, stem_chunks[i].shape[1])
            total_length += stem_chunks[i].shape[1] - actual_overlap

        result = np.zeros((stem_chunks[0].shape[0], total_length), dtype=np.float32)

        result[:, :stem_chunks[0].shape[1]] = stem_chunks[0]
        pos = stem_chunks[0].shape[1] - overlap_samples

        for i in range(1, len(stem_chunks)):
            chunk = stem_chunks[i]
            chunk_len = chunk.shape[1]
            actual_overlap = min(overlap_samples, chunk_len)

            t = np.linspace(0, np.pi, actual_overlap)
            fade_in = (1 - np.cos(t)) / 2
            fade_out = (1 + np.cos(t)) / 2

            result[:, pos:pos + actual_overlap] *= fade_out
            result[:, pos:pos + actual_overlap] += chunk[:, :actual_overlap] * fade_in

            remaining = chunk_len - actual_overlap
            if remaining > 0:
                result[:, pos + actual_overlap:pos + actual_overlap + remaining] = chunk[:, actual_overlap:]

            pos += chunk_len - actual_overlap

        merged[stem] = result

    return merged

