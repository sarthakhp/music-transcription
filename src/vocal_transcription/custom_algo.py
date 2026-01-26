import logging

from .models import PitchFrame

logger = logging.getLogger(__name__)


class FrequencySmoothing:
    def __init__(self, threshold_hz: float = 2.0):
        self.threshold_hz = threshold_hz
    
    def smooth_frequencies(self, frames: list[PitchFrame]) -> list[PitchFrame]:
        if not frames:
            return frames
        
        smoothed_frames = []
        i = 0
        
        while i < len(frames):
            current_frame = frames[i]
            
            if current_frame.frequency <= 0:
                smoothed_frames.append(current_frame)
                i += 1
                continue
            
            group = [current_frame]
            j = i + 1
            
            while j < len(frames):
                next_frame = frames[j]
                
                if next_frame.frequency <= 0:
                    break
                
                if abs(next_frame.frequency - current_frame.frequency) < self.threshold_hz:
                    group.append(next_frame)
                    j += 1
                else:
                    break
            
            avg_frequency = sum(f.frequency for f in group) / len(group)
            
            for frame in group:
                smoothed_frame = PitchFrame(
                    time=frame.time,
                    frequency=avg_frequency,
                    confidence=frame.confidence,
                    midi_pitch=self._frequency_to_midi(avg_frequency),
                )
                smoothed_frames.append(smoothed_frame)
            
            i = j
        
        smoothed_count = sum(1 for orig, smooth in zip(frames, smoothed_frames) 
                            if abs(orig.frequency - smooth.frequency) > 0.01)
        logger.info(f"Frequency smoothing: {smoothed_count} frames adjusted (threshold={self.threshold_hz}Hz)")
        
        return smoothed_frames
    
    def _frequency_to_midi(self, frequency: float) -> float:
        if frequency <= 0:
            return 0.0
        import numpy as np
        return 69 + 12 * np.log2(frequency / 440.0)

