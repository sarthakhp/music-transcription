A4_freq = 437  # Hz
A4_midi = 69
B2_midi = 47

B2_freq = A4_freq * (2 ** ((B2_midi - A4_midi) / 12))
print(f"B2 frequency when A4 = {A4_freq} Hz: {B2_freq:.2f} Hz")

