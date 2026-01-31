import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import librosa

from .config import ChordDetectionConfig
from .constants import DEFAULT_SAMPLE_RATE, CHORD_VOCABULARY_MAJMIN, CHORD_VOCABULARY_EXTENDED
from .btc_utils.transformer_modules import (
    MultiHeadAttention,
    PositionwiseFeedForward,
    LayerNorm,
    SoftmaxOutputLayer,
    _gen_timing_signal,
    _gen_bias_mask,
)

logger = logging.getLogger(__name__)


class SelfAttentionBlock(nn.Module):
    def __init__(
        self,
        hidden_size,
        total_key_depth,
        total_value_depth,
        filter_size,
        num_heads,
        bias_mask=None,
        layer_dropout=0.0,
        attention_dropout=0.0,
        relu_dropout=0.0,
    ):
        super(SelfAttentionBlock, self).__init__()

        self.multi_head_attention = MultiHeadAttention(
            hidden_size,
            total_key_depth,
            total_value_depth,
            hidden_size,
            num_heads,
            bias_mask,
            attention_dropout,
        )
        self.positionwise_convolution = PositionwiseFeedForward(
            hidden_size,
            filter_size,
            hidden_size,
            layer_config="cc",
            padding="both",
            dropout=relu_dropout,
        )
        self.dropout = nn.Dropout(layer_dropout)
        self.layer_norm_mha = LayerNorm(hidden_size)
        self.layer_norm_ffn = LayerNorm(hidden_size)

    def forward(self, inputs):
        x = inputs
        x_norm = self.layer_norm_mha(x)
        y = self.multi_head_attention(x_norm, x_norm, x_norm)
        x = self.dropout(x + y)
        x_norm = self.layer_norm_ffn(x)
        y = self.positionwise_convolution(x_norm)
        y = self.dropout(x + y)
        return y


class BiDirectionalSelfAttention(nn.Module):
    def __init__(
        self,
        hidden_size,
        total_key_depth,
        total_value_depth,
        filter_size,
        num_heads,
        max_length,
        layer_dropout=0.0,
        attention_dropout=0.0,
        relu_dropout=0.0,
    ):
        super(BiDirectionalSelfAttention, self).__init__()

        params = (
            hidden_size,
            total_key_depth or hidden_size,
            total_value_depth or hidden_size,
            filter_size,
            num_heads,
            _gen_bias_mask(max_length),
            layer_dropout,
            attention_dropout,
            relu_dropout,
        )
        self.attn_block = SelfAttentionBlock(*params)

        params = (
            hidden_size,
            total_key_depth or hidden_size,
            total_value_depth or hidden_size,
            filter_size,
            num_heads,
            torch.transpose(_gen_bias_mask(max_length), dim0=2, dim1=3),
            layer_dropout,
            attention_dropout,
            relu_dropout,
        )
        self.backward_attn_block = SelfAttentionBlock(*params)
        self.linear = nn.Linear(hidden_size * 2, hidden_size)

    def forward(self, inputs):
        x, _ = inputs
        encoder_outputs = self.attn_block(x)
        reverse_outputs = self.backward_attn_block(x)
        outputs = torch.cat((encoder_outputs, reverse_outputs), dim=2)
        y = self.linear(outputs)
        return y, []


class BiDirectionalSelfAttentionLayers(nn.Module):
    def __init__(
        self,
        embedding_size,
        hidden_size,
        num_layers,
        num_heads,
        total_key_depth,
        total_value_depth,
        filter_size,
        max_length=100,
        input_dropout=0.0,
        layer_dropout=0.0,
        attention_dropout=0.0,
        relu_dropout=0.0,
    ):
        super(BiDirectionalSelfAttentionLayers, self).__init__()

        self.timing_signal = _gen_timing_signal(max_length, hidden_size)
        params = (
            hidden_size,
            total_key_depth or hidden_size,
            total_value_depth or hidden_size,
            filter_size,
            num_heads,
            max_length,
            layer_dropout,
            attention_dropout,
            relu_dropout,
        )
        self.embedding_proj = nn.Linear(embedding_size, hidden_size, bias=False)
        self.self_attn_layers = nn.Sequential(
            *[BiDirectionalSelfAttention(*params) for _ in range(num_layers)]
        )
        self.layer_norm = LayerNorm(hidden_size)
        self.input_dropout = nn.Dropout(input_dropout)

    def forward(self, inputs):
        x = self.input_dropout(inputs)
        x = self.embedding_proj(x)
        x += self.timing_signal[:, : inputs.shape[1], :].type_as(inputs.data)
        y, _ = self.self_attn_layers((x, []))
        y = self.layer_norm(y)
        return y, []


class BTCModelCore(nn.Module):
    def __init__(
        self,
        feature_size=144,
        hidden_size=128,
        num_layers=8,
        num_heads=4,
        total_key_depth=128,
        total_value_depth=128,
        filter_size=128,
        timestep=108,
        num_chords=25,
        input_dropout=0.2,
        layer_dropout=0.2,
        attention_dropout=0.2,
        relu_dropout=0.2,
    ):
        super(BTCModelCore, self).__init__()

        self.timestep = timestep

        params = (
            feature_size,
            hidden_size,
            num_layers,
            num_heads,
            total_key_depth,
            total_value_depth,
            filter_size,
            timestep,
            input_dropout,
            layer_dropout,
            attention_dropout,
            relu_dropout,
        )

        self.self_attn_layers = BiDirectionalSelfAttentionLayers(*params)
        self.output_layer = SoftmaxOutputLayer(
            hidden_size=hidden_size, output_size=num_chords, probs_out=True
        )

    def forward(self, x):
        self_attn_output, _ = self.self_attn_layers(x)
        logits = self.output_layer(self_attn_output)
        return logits


class BTCModel:
    def __init__(self, config: ChordDetectionConfig | None = None):
        self.config = config or ChordDetectionConfig()
        self.device = self.config.get_device()
        self.model = None
        self.mean = None
        self.std = None
        self.vocabulary = (
            CHORD_VOCABULARY_EXTENDED if self.config.use_voca else CHORD_VOCABULARY_MAJMIN
        )

        logger.info(f"BTCModel initialized on device: {self.device}")
        logger.info(
            f"Vocabulary size: {len(self.vocabulary)} ({'extended' if self.config.use_voca else 'maj/min'})"
        )

    def load_model(self, model_path: str | Path | None = None):
        model_path = model_path or self.config.model_path

        if model_path is None:
            raise ValueError("Model path must be provided either in config or as argument")

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(f"Loading BTC model from: {model_path}")

        try:
            checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)

            self.mean = checkpoint.get("mean", 0.0)
            self.std = checkpoint.get("std", 1.0)

            num_chords = 170 if self.config.use_voca else 25
            feature_size = 144

            self.model = BTCModelCore(
                feature_size=feature_size,
                hidden_size=128,
                num_layers=8,
                num_heads=4,
                total_key_depth=128,
                total_value_depth=128,
                filter_size=128,
                timestep=108,
                num_chords=num_chords,
                input_dropout=0.2,
                layer_dropout=0.2,
                attention_dropout=0.2,
                relu_dropout=0.2,
            )

            self.model.load_state_dict(checkpoint["model"])
            self.model.to(self.device)
            self.model.eval()

            logger.info(f"Model loaded successfully with {num_chords} chord classes")
            logger.info(f"Normalization: mean={self.mean}, std={self.std}")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def extract_features(self, audio: np.ndarray, sr: int) -> np.ndarray:
        if sr != self.config.sample_rate:
            logger.info(f"Resampling from {sr}Hz to {self.config.sample_rate}Hz")
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.config.sample_rate)
            sr = self.config.sample_rate

        logger.info(f"Extracting CQT features...")

        n_bins = 144
        bins_per_octave = 24
        hop_length = 2048

        cqt = librosa.cqt(
            audio,
            sr=sr,
            hop_length=hop_length,
            n_bins=n_bins,
            bins_per_octave=bins_per_octave,
        )

        cqt_mag = np.abs(cqt)
        cqt_log = np.log(cqt_mag + 1e-6)

        logger.info(f"CQT shape: {cqt_log.shape} (bins x frames)")
        return cqt_log

    def predict(self, audio: np.ndarray, sr: int) -> list[tuple[float, str, float]]:
        features = self.extract_features(audio, sr)

        if self.model is None:
            logger.warning("Model not loaded. Returning placeholder predictions.")
            num_frames = features.shape[1]
            hop_seconds = 2048 / self.config.sample_rate

            predictions = []
            for i in range(num_frames):
                time = i * hop_seconds
                predictions.append((time, "N", 0.5))

            return predictions

        logger.info("Running BTC inference...")

        features = features.T
        features = (features - self.mean) / self.std

        n_timestep = 108
        feature_per_second = 10.0 / n_timestep

        num_pad = n_timestep - (features.shape[0] % n_timestep)
        features = np.pad(
            features, ((0, num_pad), (0, 0)), mode="constant", constant_values=0
        )
        num_instance = features.shape[0] // n_timestep

        predictions = []
        prev_chord = None
        start_time = 0.0

        with torch.no_grad():
            features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)

            for t in range(num_instance):
                batch_features = features_tensor[:, n_timestep * t : n_timestep * (t + 1), :]
                logits = self.model(batch_features)
                probs = torch.softmax(logits, dim=-1)
                prediction = torch.argmax(probs, dim=-1).squeeze()
                confidence = torch.max(probs, dim=-1).values.squeeze()

                for i in range(n_timestep):
                    if t == num_instance - 1 and i >= n_timestep - num_pad:
                        break

                    current_time = feature_per_second * (n_timestep * t + i)
                    chord_idx = prediction[i].item()
                    conf = confidence[i].item()
                    chord_label = self.vocabulary[chord_idx]

                    predictions.append((current_time, chord_label, conf))

        logger.info(f"Generated {len(predictions)} chord predictions")
        return predictions

    def get_vocabulary(self) -> list[str]:
        return self.vocabulary

