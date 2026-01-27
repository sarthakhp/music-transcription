# Vocal Pitch Visualization Webapp - Project Handoff Document

## Project Overview

Build an interactive web application to visualize vocal pitch analysis data from audio transcription. The webapp will display pitch contour data as an interactive graph synchronized with audio playback.

---

## Core Requirements

### 1. Audio Playback
- **Play/Pause button** for the original song or vocal track
- Audio controls (play, pause, seek, volume)
- Display current playback time and total duration

### 2. Interactive Pitch Graph
- **X-Axis**: Time (seconds)
- **Y-Axis**: Frequency (Hz) OR Piano Notes (C4, D4, E4, etc.) - user selectable
- **Data Points**: Plot dots from `processed_frames` array
  - Each dot represents a pitch frame at a specific time
  - Color-code dots based on:
    - `is_voiced`: true (colored) vs false (gray/hidden)
    - `confidence`: opacity/intensity (higher confidence = more opaque)

### 3. Synchronized Playhead
- **Red vertical bar** that moves left-to-right as audio plays
- Bar position syncs with `audio.currentTime`
- Updates smoothly using `requestAnimationFrame`
- Clicking on graph should seek audio to that time

### 4. Zoom & Pan Controls
- **Pinch zoom** (touch devices) - changes X-axis time range
- **Mouse wheel zoom** (desktop)
- **Drag to pan** horizontally
- **Zoom controls** (+ / - buttons)
- Auto-scroll option to keep playhead centered during playback

---

## Data Format

### Input JSON Structure

```json
{
  "metadata": {
    "original_song_path": "/path/to/song.mp3",
    "vocal_file_path": "/path/to/vocals.wav",
    "bpm": 144.23
  },
  "processed_frames": [
    {
      "time": 0.0,
      "frequency": 0.0,
      "confidence": 0.005,
      "midi_pitch": 0.0,
      "is_voiced": false
    },
    {
      "time": 7.2,
      "frequency": 119.58,
      "confidence": 0.68,
      "midi_pitch": 46.44,
      "is_voiced": true
    }
  ],
  "frame_count": 12000
}
```

### Data Specifications
- **Time interval**: 0.01 seconds (10ms) between frames
- **Frequency range**: 0 Hz (unvoiced) to ~2000 Hz (typical vocal range)
- **MIDI pitch range**: 0 (unvoiced) to ~90 (typical: 40-80 for vocals)
- **Confidence**: 0.0 to 1.0 (threshold typically 0.6 for voiced detection)
- **Frame count**: ~6000 frames per minute of audio

### Sample Data
A sample JSON file is provided: `mitti-ke-bete-120_sec_vocals_processed_frames.json`
- Duration: 120 seconds
- ~12,000 frames
- BPM: 144.23

---

## Recommended Tech Stack

### Core Framework
- **React 18+ with TypeScript**
- **Vite** for build tooling (fast dev server)

### Audio Playback
- **Howler.js** - Simple, reliable audio playback library
  - `npm install howler @types/howler`
  - Cross-browser compatible
  - Easy time synchronization

### Visualization
- **D3.js** - For custom interactive graphs
  - `npm install d3 @types/d3`
  - Built-in zoom/pan behaviors (`d3.zoom()`)
  - Precise control over SVG rendering
  - Time-based scales for X-axis

**Alternative**: Plotly.js (`react-plotly.js`) - Easier but less customizable

### Styling
- **Tailwind CSS** - Fast, utility-first styling
- **shadcn/ui** (optional) - Beautiful pre-built components

---

## Key Features to Implement

### Phase 1: Core Functionality
1. ✅ Load JSON file (drag-drop or file picker)
2. ✅ Load audio file (user provides original song or vocal track)
3. ✅ Parse and validate JSON data
4. ✅ Render basic pitch graph with D3.js
5. ✅ Audio playback controls (play/pause)
6. ✅ Synchronized red playhead bar

### Phase 2: Interactivity
7. ✅ Zoom in/out on X-axis (time)
8. ✅ Pan left/right
9. ✅ Click graph to seek audio
10. ✅ Toggle Y-axis: Frequency (Hz) vs Piano Notes

### Phase 3: Visual Enhancements
11. ✅ Color-code dots by confidence (opacity)
12. ✅ Hide/show unvoiced frames (toggle)
13. ✅ Piano keyboard overlay on Y-axis (optional)
14. ✅ Display metadata (BPM, file paths)
15. ✅ Responsive design (mobile + desktop)

---

## Technical Implementation Guide

### 1. Project Setup
```bash
npm create vite@latest vocal-pitch-viewer -- --template react-ts
cd vocal-pitch-viewer
npm install
npm install d3 @types/d3 howler @types/howler
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### 2. Component Structure
```
src/
├── components/
│   ├── AudioPlayer.tsx       # Play/pause, seek, volume controls
│   ├── PitchGraph.tsx        # Main D3 visualization
│   ├── Playhead.tsx          # Red vertical bar overlay
│   ├── FileUploader.tsx      # JSON + audio file upload
│   ├── Controls.tsx          # Zoom, pan, settings
│   └── MetadataDisplay.tsx   # Show BPM, file info
├── hooks/
│   ├── useAudioSync.ts       # Sync audio time with graph
│   ├── useFrameData.ts       # Load and parse JSON
│   └── useZoom.ts            # Handle zoom/pan state
├── utils/
│   ├── audioUtils.ts         # Howler.js wrapper
│   ├── scaleUtils.ts         # Frequency ↔ Piano note conversion
│   └── midiToNote.ts         # MIDI number to note name (60 → C4)
├── types/
│   └── data.ts               # TypeScript interfaces
└── App.tsx
```

### 3. TypeScript Interfaces

```typescript
// src/types/data.ts
export interface PitchFrame {
  time: number;
  frequency: number;
  confidence: number;
  midi_pitch: number;
  is_voiced: boolean;
}

export interface Metadata {
  original_song_path?: string;
  vocal_file_path?: string;
  bpm?: number;
  [key: string]: any; // Allow additional fields
}

export interface ProcessedFramesData {
  metadata: Metadata;
  processed_frames: PitchFrame[];
  frame_count: number;
}
```

### 4. Audio Synchronization Pattern

```typescript
// src/hooks/useAudioSync.ts
import { useEffect, useState } from 'react';
import { Howl } from 'howler';

export const useAudioSync = (audio: Howl | null) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (!audio || !isPlaying) return;

    const updateTime = () => {
      setCurrentTime(audio.seek() as number);
      requestAnimationFrame(updateTime);
    };

    const animationId = requestAnimationFrame(updateTime);
    return () => cancelAnimationFrame(animationId);
  }, [audio, isPlaying]);

  return { currentTime, isPlaying, setIsPlaying };
};
```

### 5. D3 Graph Implementation Tips

```typescript
// Key D3 concepts for the pitch graph

// 1. Scales
const xScale = d3.scaleLinear()
  .domain([0, maxTime])  // Data range
  .range([0, width]);    // Pixel range

const yScale = d3.scaleLinear()
  .domain([minFreq, maxFreq])
  .range([height, 0]);   // Inverted (SVG coords)

// 2. Zoom behavior
const zoom = d3.zoom()
  .scaleExtent([1, 50])  // Min/max zoom
  .on('zoom', (event) => {
    const newXScale = event.transform.rescaleX(xScale);
    // Re-render with newXScale
  });

// 3. Render dots
svg.selectAll('circle')
  .data(frames.filter(f => f.is_voiced))
  .join('circle')
  .attr('cx', d => xScale(d.time))
  .attr('cy', d => yScale(d.frequency))
  .attr('r', 2)
  .attr('opacity', d => d.confidence);

// 4. Playhead line
svg.append('line')
  .attr('x1', xScale(currentTime))
  .attr('x2', xScale(currentTime))
  .attr('y1', 0)
  .attr('y2', height)
  .attr('stroke', 'red')
  .attr('stroke-width', 2);
```

### 6. MIDI to Piano Note Conversion

```typescript
// src/utils/midiToNote.ts
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

export function midiToNoteName(midi: number): string {
  if (midi <= 0) return '-';
  const octave = Math.floor(midi / 12) - 1;
  const noteIndex = Math.round(midi) % 12;
  return `${NOTE_NAMES[noteIndex]}${octave}`;
}

// Example: 60 → C4, 69 → A4, 46.44 → A#2
```

### 7. Frequency to MIDI Conversion (for Y-axis)

```typescript
// src/utils/scaleUtils.ts
export function frequencyToMidi(frequency: number): number {
  if (frequency <= 0) return 0;
  return 69 + 12 * Math.log2(frequency / 440);
}

export function midiToFrequency(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}
```

---

## UI/UX Specifications

### Layout
```
┌─────────────────────────────────────────────────────┐
│  Vocal Pitch Visualizer                             │
├─────────────────────────────────────────────────────┤
│  [Upload JSON] [Upload Audio]                       │
│  BPM: 144.23  |  Duration: 120s  |  Frames: 12000   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │                                             │    │
│  │         Pitch Graph (D3.js)                │    │
│  │                                             │    │
│  │  [Red playhead bar moves here]             │    │
│  │                                             │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  [◄] [▶] [⏸]  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  2:00  │
│                                                      │
│  Y-Axis: [Frequency] [Piano Notes]                  │
│  Show Unvoiced: [✓]  |  Zoom: [+] [-] [Reset]      │
└─────────────────────────────────────────────────────┘
```

### Color Scheme Suggestions
- **Background**: Dark theme (#1a1a1a) or light (#ffffff)
- **Voiced frames**: Blue (#3b82f6) with opacity based on confidence
- **Unvoiced frames**: Gray (#6b7280) at 20% opacity
- **Playhead**: Red (#ef4444)
- **Grid lines**: Light gray (#e5e7eb)

### Responsive Breakpoints
- **Mobile**: < 768px - Stack controls vertically
- **Tablet**: 768px - 1024px - Compact layout
- **Desktop**: > 1024px - Full layout with sidebar

---

## Performance Considerations

### Large Dataset Handling
- **12,000 frames** = manageable, but optimize rendering
- Use **canvas** instead of SVG if > 50,000 frames
- Implement **virtualization**: Only render visible time range
- **Debounce** zoom/pan events (100ms)

### Optimization Tips
```typescript
// 1. Filter data before rendering
const visibleFrames = frames.filter(f =>
  f.time >= visibleTimeStart && f.time <= visibleTimeEnd
);

// 2. Memoize expensive calculations
const processedData = useMemo(() =>
  frames.filter(f => f.is_voiced),
  [frames]
);

// 3. Use React.memo for components
export const PitchGraph = React.memo(({ frames, currentTime }) => {
  // ...
});
```

---

## Testing Checklist

### Functionality
- [ ] JSON file loads correctly
- [ ] Audio file plays/pauses
- [ ] Playhead syncs with audio
- [ ] Zoom in/out works smoothly
- [ ] Pan left/right works
- [ ] Click to seek works
- [ ] Y-axis toggle (Frequency ↔ Piano Notes)
- [ ] Unvoiced frames toggle

### Edge Cases
- [ ] Handle empty/invalid JSON
- [ ] Handle audio load errors
- [ ] Handle very short audio (< 5 seconds)
- [ ] Handle very long audio (> 10 minutes)
- [ ] Handle missing metadata fields
- [ ] Mobile touch gestures work

### Browser Compatibility
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

---

## Deployment

### Build for Production
```bash
npm run build
```

### Hosting Options
1. **Vercel** - `vercel deploy` (recommended)
2. **Netlify** - Drag-drop `dist/` folder
3. **GitHub Pages** - Static hosting
4. **Cloudflare Pages** - Fast CDN

### Environment Setup
- No backend required - pure client-side app
- All processing happens in browser
- Audio files loaded from user's device

---

## Future Enhancements (Optional)

### Phase 4: Advanced Features
- [ ] Waveform background visualization
- [ ] Multiple file comparison (overlay 2+ pitch contours)
- [ ] Export graph as PNG/SVG
- [ ] Keyboard shortcuts (Space = play/pause, Arrow keys = seek)
- [ ] Loop region selection
- [ ] Pitch correction suggestions
- [ ] MIDI export from selected region
- [ ] Share visualization via URL (encode data in URL params)

### Phase 5: Analysis Tools
- [ ] Vibrato detection and highlighting
- [ ] Pitch stability metrics
- [ ] Note duration histogram
- [ ] Pitch range visualization (min/max/average)
- [ ] Comparison with reference pitch

---

## Resources & References

### Documentation
- **D3.js**: https://d3js.org/
- **Howler.js**: https://howlerjs.com/
- **React**: https://react.dev/
- **TypeScript**: https://www.typescriptlang.org/

---

## Questions for Clarification

If you need clarification on any requirements, consider:

1. **Y-Axis Display**: Should piano notes show chromatic (all 12 notes) or only scale degrees?
2. **Dot Size**: Should dot size vary with confidence, or just opacity?
3. **Color Coding**: Any preference for color scheme (blue, green, rainbow)?
4. **Mobile Priority**: Is mobile support critical or desktop-first?
5. **File Size Limits**: Max JSON file size to support (current: ~5MB for 120s)?

---

## Success Criteria

The webapp is complete when:
1. ✅ User can load JSON + audio files
2. ✅ Graph displays all voiced pitch frames
3. ✅ Playhead syncs perfectly with audio
4. ✅ Zoom/pan works smoothly on desktop and mobile
5. ✅ UI is intuitive and visually appealing
6. ✅ Performance is smooth (60fps) for 120s audio
7. ✅ Works on Chrome, Firefox, Safari
