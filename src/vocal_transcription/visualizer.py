import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .models import PitchFrame, TranscriptionResult

logger = logging.getLogger(__name__)


class PitchVisualizer:
    def __init__(self):
        plt.style.use('seaborn-v0_8-darkgrid')
    
    def plot_processed_frames(self, frames: list[PitchFrame], notes: list = None, output_path: str | Path | None = None, show: bool = True):
        if not frames:
            logger.warning("No frames to visualize")
            return

        times = [f.time for f in frames]
        frequencies = [f.frequency for f in frames]
        midi_pitches = [f.midi_pitch for f in frames]
        confidences = [f.confidence for f in frames]
        voiced = [f.is_voiced for f in frames]

        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
        title = 'Pitch Processing Analysis'
        if notes:
            title += f' - {len(notes)} Notes Detected'
        fig.suptitle(title, fontsize=16, fontweight='bold')

        max_time = max(times) if times else 1.0
        time_step = max(1.0, max_time / 10)
        time_ticks = np.arange(0, max_time + time_step, time_step)
        
        # Plot 1: Frequency over time
        ax1 = axes[0]
        voiced_times = [t for t, f, v in zip(times, frequencies, voiced) if v and f > 20]
        voiced_freqs = [f for f, v in zip(frequencies, voiced) if v and f > 20]
        unvoiced_times = [t for t, f, v in zip(times, frequencies, voiced) if not v and f > 20]
        unvoiced_freqs = [f for f, v in zip(frequencies, voiced) if not v and f > 20]

        ax1.scatter(voiced_times, voiced_freqs, c='blue', s=10, alpha=0.6, label='Voiced')
        if unvoiced_times:
            ax1.scatter(unvoiced_times, unvoiced_freqs, c='red', s=5, alpha=0.3, label='Unvoiced')
        ax1.set_xlabel('Time (seconds)', fontsize=12)
        ax1.set_ylabel('Frequency (Hz)', fontsize=12)
        ax1.set_title('Pitch Frequency Contour', fontsize=13)
        ax1.set_xticks(time_ticks)
        ax1.set_xticklabels([f'{t:.1f}' for t in time_ticks])
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: MIDI pitch over time
        ax2 = axes[1]
        voiced_midi = [m for m, v in zip(midi_pitches, voiced) if v]

        ax2.scatter(voiced_times, voiced_midi, c='lightgreen', s=10, alpha=0.4, label='Pitch Contour')

        if notes:
            for note in notes:
                ax2.barh(note.anchor_midi, note.duration, left=note.start_time,
                        height=0.8, alpha=0.7, color='darkgreen', edgecolor='black', linewidth=0.5)
            ax2.legend(['Pitch Contour', 'Segmented Notes'])

        ax2.set_xlabel('Time (seconds)', fontsize=12)
        ax2.set_ylabel('MIDI Pitch', fontsize=12)
        ax2.set_title('MIDI Pitch Contour with Note Segmentation', fontsize=13)
        ax2.set_xticks(time_ticks)
        ax2.set_xticklabels([f'{t:.1f}' for t in time_ticks])
        ax2.grid(True, alpha=0.3)
        
        # Add MIDI note names on y-axis
        if voiced_midi:
            min_midi = int(min(voiced_midi))
            max_midi = int(max(voiced_midi)) + 1
            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            midi_ticks = range(min_midi, max_midi + 1)
            ax2.set_yticks(midi_ticks)
            ax2.set_yticklabels([f"{note_names[m % 12]}{m // 12 - 1}" for m in midi_ticks], fontsize=8)
        
        # Plot 3: Confidence over time (disabled)
        # ax3 = axes[2]
        # ax3.plot(times, confidences, c='purple', linewidth=1, alpha=0.7)
        # ax3.fill_between(times, confidences, alpha=0.3, color='purple')
        # ax3.set_xlabel('Time (seconds)', fontsize=12)
        # ax3.set_ylabel('Confidence', fontsize=12)
        # ax3.set_title('Pitch Detection Confidence', fontsize=13)
        # ax3.set_xticks(time_ticks)
        # ax3.set_xticklabels([f'{t:.1f}' for t in time_ticks])
        # ax3.set_ylim([0, 1])
        # ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                logger.info(f"Overriding existing file: {output_path}")
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved visualization to {output_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_transcription_result(self, result: TranscriptionResult, output_path: str | Path | None = None, show: bool = True):
        if not result.pitch_contour:
            logger.warning("No pitch contour to visualize")
            return
        
        times = [f.time for f in result.pitch_contour]
        midi_pitches = [f.midi_pitch for f in result.pitch_contour]
        voiced = [f.is_voiced for f in result.pitch_contour]
        
        fig, ax = plt.subplots(figsize=(14, 6))
        fig.suptitle(f'Transcription Result - {len(result.notes)} Notes @ {result.tempo_bpm:.1f} BPM', 
                     fontsize=16, fontweight='bold')
        
        # Plot pitch contour
        voiced_times = [t for t, v in zip(times, voiced) if v]
        voiced_midi = [m for m, v in zip(midi_pitches, voiced) if v]
        
        ax.scatter(voiced_times, voiced_midi, c='lightblue', s=5, alpha=0.4, label='Pitch Contour')
        
        # Plot notes as horizontal bars
        for note in result.notes:
            ax.barh(note.anchor_midi, note.duration, left=note.start_time, 
                   height=0.8, alpha=0.7, color='darkblue', edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('MIDI Pitch', fontsize=12)
        ax.set_title('Notes and Pitch Contour', fontsize=13)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add MIDI note names
        if voiced_midi:
            min_midi = int(min(min(voiced_midi), min(n.anchor_midi for n in result.notes)))
            max_midi = int(max(max(voiced_midi), max(n.anchor_midi for n in result.notes))) + 1
            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            midi_ticks = range(min_midi, max_midi + 1)
            ax.set_yticks(midi_ticks)
            ax.set_yticklabels([f"{note_names[m % 12]}{m // 12 - 1}" for m in midi_ticks], fontsize=8)
        
        plt.tight_layout()
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                logger.info(f"Overriding existing file: {output_path}")
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved visualization to {output_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_key_analysis(self, frames: list[PitchFrame], key_info, output_path: str | Path | None = None, show: bool = True):
        if not frames or not key_info:
            logger.warning("No frames or key info to visualize")
            return

        voiced_frames = [f for f in frames if f.is_voiced]
        if not voiced_frames:
            return

        pitch_classes = [(int(round(f.midi_pitch)) % 12) for f in voiced_frames]
        pitch_class_counts = np.zeros(12)
        for pc in pitch_classes:
            pitch_class_counts[pc] += 1

        if pitch_class_counts.sum() > 0:
            pitch_class_counts = pitch_class_counts / pitch_class_counts.sum()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f'Key Analysis: {key_info.tonic_name} {key_info.scale_type} (Confidence: {key_info.confidence:.2f})',
                     fontsize=16, fontweight='bold')

        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        colors = ['green' if i in key_info.detected_notes else 'lightgray' for i in range(12)]

        tonic_class = key_info.tonic_midi % 12
        colors[tonic_class] = 'red'

        ax1.bar(range(12), pitch_class_counts, color=colors, edgecolor='black', linewidth=1)
        ax1.set_xticks(range(12))
        ax1.set_xticklabels(note_names, fontsize=10)
        ax1.set_xlabel('Pitch Class', fontsize=12)
        ax1.set_ylabel('Relative Frequency', fontsize=12)
        ax1.set_title('Pitch Class Distribution', fontsize=13)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.axvline(tonic_class, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Tonic ({key_info.tonic_name})')
        ax1.legend()

        swara_names = list(key_info.swara_usage.keys())
        swara_values = list(key_info.swara_usage.values())

        colors_swara = ['green' if v > 0.05 else 'lightgray' for v in swara_values]
        colors_swara[0] = 'red'

        ax2.bar(range(len(swara_names)), swara_values, color=colors_swara, edgecolor='black', linewidth=1)
        ax2.set_xticks(range(len(swara_names)))
        ax2.set_xticklabels(swara_names, fontsize=9, rotation=45, ha='right')
        ax2.set_xlabel('Swara (relative to Sa)', fontsize=12)
        ax2.set_ylabel('Usage Frequency', fontsize=12)
        ax2.set_title('Swara Usage Distribution', fontsize=13)
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved key analysis visualization to {output_path}")

        if show:
            plt.show()
        else:
            plt.close()

