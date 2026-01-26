import gc

import torch


def clear_memory(device: str) -> None:
    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()
    gc.collect()

