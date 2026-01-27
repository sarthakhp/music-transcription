# Quick Start Guide for AI Agent

## What You're Building

An interactive web app to visualize vocal pitch data synchronized with audio playback.

## Files Provided

1. **VISUALIZATION_WEBAPP_HANDOFF.md** - Complete project specification
2. **SAMPLE_DATA.json** - Sample data structure for testing
3. **Full data file** - `mitti-ke-bete-120_sec_vocals_processed_frames.json` (120 seconds, ~12,000 frames)

## Quick Setup Commands

```bash
# 1. Create React + TypeScript project with Vite
npm create vite@latest vocal-pitch-viewer -- --template react-ts
cd vocal-pitch-viewer

# 2. Install dependencies
npm install
npm install d3 @types/d3
npm install howler @types/howler
npm install -D tailwindcss postcss autoprefixer

# 3. Initialize Tailwind
npx tailwindcss init -p

# 4. Start dev server
npm run dev
```

## Core Requirements (Priority Order)

### Must Have (MVP)
1. Load JSON file (drag-drop or file picker)
2. Load audio file (user uploads)
3. Display pitch graph with D3.js (dots for each frame)
4. Play/pause audio with Howler.js
5. Red vertical playhead bar synced with audio
6. Basic zoom in/out on X-axis

### Should Have
7. Pan left/right
8. Click graph to seek audio
9. Toggle Y-axis: Frequency vs Piano Notes
10. Color dots by confidence (opacity)

### Nice to Have
11. Hide/show unvoiced frames
12. Display metadata (BPM, duration)
13. Zoom controls (+ / - buttons)
14. Mobile responsive

## Key Technical Points

### Data Structure
```typescript
interface PitchFrame {
  time: number;        // seconds (0.01 interval)
  frequency: number;   // Hz (0 = unvoiced)
  confidence: number;  // 0.0 to 1.0
  midi_pitch: number;  // fractional MIDI note
  is_voiced: boolean;  // true if frequency > 0
}
```

### Audio Sync Pattern
```typescript
// Use requestAnimationFrame to update playhead
useEffect(() => {
  if (!isPlaying) return;
  
  const update = () => {
    const time = audio.seek();
    setCurrentTime(time);
    requestAnimationFrame(update);
  };
  
  requestAnimationFrame(update);
}, [isPlaying]);
```

### D3 Graph Basics
```typescript
// X-axis: Time
const xScale = d3.scaleLinear()
  .domain([0, maxTime])
  .range([0, width]);

// Y-axis: Frequency
const yScale = d3.scaleLinear()
  .domain([0, 2000])  // 0-2000 Hz
  .range([height, 0]);

// Plot dots
svg.selectAll('circle')
  .data(frames.filter(f => f.is_voiced))
  .join('circle')
  .attr('cx', d => xScale(d.time))
  .attr('cy', d => yScale(d.frequency))
  .attr('r', 2)
  .attr('opacity', d => d.confidence);
```

### MIDI to Note Name
```typescript
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function midiToNote(midi: number): string {
  const octave = Math.floor(midi / 12) - 1;
  const note = NOTE_NAMES[Math.round(midi) % 12];
  return `${note}${octave}`;
}

// Example: 69 → A4, 60 → C4
```

## Suggested Implementation Order

### Step 1: Basic Setup (30 min)
- Create Vite project
- Install dependencies
- Set up Tailwind CSS
- Create basic component structure

### Step 2: Data Loading (30 min)
- File upload component
- Parse JSON
- Display metadata
- TypeScript interfaces

### Step 3: D3 Graph (1-2 hours)
- Create SVG container
- Set up scales (X: time, Y: frequency)
- Plot dots for voiced frames
- Add axes and labels

### Step 4: Audio Player (1 hour)
- Integrate Howler.js
- Play/pause controls
- Display current time / duration
- Volume control

### Step 5: Playhead Sync (30 min)
- Red vertical line
- Update position with requestAnimationFrame
- Sync with audio.currentTime

### Step 6: Zoom & Pan (1-2 hours)
- D3 zoom behavior
- Mouse wheel zoom
- Drag to pan
- Zoom controls (buttons)

### Step 7: Polish (1 hour)
- Styling with Tailwind
- Responsive design
- Error handling
- Loading states

## Testing with Sample Data

1. Use `SAMPLE_DATA.json` for initial testing (16 frames)
2. Test with full file `mitti-ke-bete-120_sec_vocals_processed_frames.json` (12,000 frames)
3. User will provide their own audio file for playback

## Common Pitfalls to Avoid

❌ Don't use SVG for > 50,000 points (use Canvas instead)
❌ Don't update playhead on every frame without requestAnimationFrame
❌ Don't forget to filter out unvoiced frames (frequency = 0)
❌ Don't hardcode dimensions (make responsive)
❌ Don't forget to handle audio load errors

✅ Do use React.memo for expensive components
✅ Do debounce zoom/pan events
✅ Do filter visible frames before rendering
✅ Do use TypeScript for type safety
✅ Do test on mobile devices

## Expected Output

A single-page webapp where:
1. User uploads JSON + audio files
2. Graph displays pitch contour as dots
3. Red line moves as audio plays
4. User can zoom/pan to explore data
5. Clicking graph seeks audio to that time

## Questions?

Refer to **VISUALIZATION_WEBAPP_HANDOFF.md** for:
- Complete technical specifications
- Detailed component structure
- Code examples
- UI/UX mockups
- Performance optimization tips
- Deployment instructions

Good luck! 🚀

