import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .models import PitchFrame, TranscriptionResult

logger = logging.getLogger(__name__)


class PitchVisualizer:
    def __init__(self):
        plt.style.use('seaborn-v0_8-darkgrid')
    
    def plot_processed_frames(self, frames: list[PitchFrame], output_path: str | Path | None = None, show: bool = True):
        if not frames:
            logger.warning("No frames to visualize")
            return
        
        times = [f.time for f in frames]
        frequencies = [f.frequency for f in frames]
        midi_pitches = [f.midi_pitch for f in frames]
        confidences = [f.confidence for f in frames]
        voiced = [f.is_voiced for f in frames]
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        fig.suptitle('Pitch Processing Analysis', fontsize=16, fontweight='bold')
        
        # Plot 1: Frequency over time
        ax1 = axes[0]
        voiced_times = [t for t, v in zip(times, voiced) if v]
        voiced_freqs = [f for f, v in zip(frequencies, voiced) if v]
        unvoiced_times = [t for t, v in zip(times, voiced) if not v]
        unvoiced_freqs = [f for f, v in zip(frequencies, voiced) if not v]
        
        ax1.scatter(voiced_times, voiced_freqs, c='blue', s=10, alpha=0.6, label='Voiced')
        if unvoiced_times:
            ax1.scatter(unvoiced_times, unvoiced_freqs, c='red', s=5, alpha=0.3, label='Unvoiced')
        ax1.set_ylabel('Frequency (Hz)', fontsize=12)
        ax1.set_title('Pitch Frequency Contour', fontsize=13)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: MIDI pitch over time
        ax2 = axes[1]
        voiced_midi = [m for m, v in zip(midi_pitches, voiced) if v]
        
        ax2.scatter(voiced_times, voiced_midi, c='green', s=10, alpha=0.6)
        ax2.set_ylabel('MIDI Pitch', fontsize=12)
        ax2.set_title('MIDI Pitch Contour', fontsize=13)
        ax2.grid(True, alpha=0.3)
        
        # Add MIDI note names on y-axis
        if voiced_midi:
            min_midi = int(min(voiced_midi))
            max_midi = int(max(voiced_midi)) + 1
            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            midi_ticks = range(min_midi, max_midi + 1)
            ax2.set_yticks(midi_ticks)
            ax2.set_yticklabels([f"{note_names[m % 12]}{m // 12 - 1}" for m in midi_ticks], fontsize=8)
        
        # Plot 3: Confidence over time
        ax3 = axes[2]
        ax3.plot(times, confidences, c='purple', linewidth=1, alpha=0.7)
        ax3.fill_between(times, confidences, alpha=0.3, color='purple')
        ax3.set_xlabel('Time (seconds)', fontsize=12)
        ax3.set_ylabel('Confidence', fontsize=12)
        ax3.set_title('Pitch Detection Confidence', fontsize=13)
        ax3.set_ylim([0, 1])
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
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
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved visualization to {output_path}")
        
        if show:
            plt.show()
        else:
            plt.close()

