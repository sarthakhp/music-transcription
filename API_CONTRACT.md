# Music Transcription API - Contract Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000` (development)  
**Date:** 2026-01-31

---

## Overview

This API accepts audio files and processes them through a 3-stage pipeline:
1. **Source Separation** (0-33%) - Separates audio into vocals, bass, drums, other
2. **Vocal Transcription** (33-66%) - Extracts pitch data at 10ms intervals
3. **Chord Detection** (66-100%) - Detects chord progression

Processing is asynchronous. Upload returns immediately with a `job_id`, then poll for status updates.

---

## Authentication

**None required** for MVP. All endpoints are publicly accessible.

---

## Endpoints

### 1. Upload Audio File

**POST** `/api/v1/transcribe`

Upload an audio file to start processing.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (audio file)

**Supported Formats:** MP3, WAV, FLAC, M4A, OGG  
**Max File Size:** 100MB (configurable)

**Response:** `202 Accepted`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job created successfully. Processing started."
}
```

**Errors:**
- `400` - Invalid file type
- `413` - File too large
- `429` - Too many concurrent jobs (max 3)

---

### 2. Get Job Status

**GET** `/api/v1/jobs/{job_id}/status`

Quick status check for polling.

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "stage": "transcription",
  "progress": 45,
  "error_message": null
}
```

**Status Values:** `queued`, `processing`, `completed`, `failed`  
**Stage Values:** `separation`, `transcription`, `chords`  
**Progress:** 0-100 (integer percentage)

---

### 3. Get Job Results Summary

**GET** `/api/v1/jobs/{job_id}/results`

Get aggregated results and availability flags.

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "input_filename": "song.mp3",
  "duration": 240.5,
  "tempo_bpm": 120.0,
  "stems": ["vocals", "bass", "drums", "other", "instrumental", "original"],
  "frames_available": true,
  "chords_available": true,
  "num_frames": 24050,
  "num_chords": 48,
  "processing_time": 145.2
}
```

---

### 4. List Available Stems

**GET** `/api/v1/jobs/{job_id}/stems`

Get list of separated audio stems.

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "stems": [
    {
      "name": "vocals",
      "filename": "song_vocals.mp3",
      "size_bytes": 5242880,
      "download_url": "/api/v1/jobs/{job_id}/stems/vocals"
    },
    {
      "name": "bass",
      "filename": "song_bass.mp3",
      "size_bytes": 4194304,
      "download_url": "/api/v1/jobs/{job_id}/stems/bass"
    },
    {
      "name": "instrumental",
      "filename": "song_instrumental.mp3",
      "size_bytes": 6291456,
      "download_url": "/api/v1/jobs/{job_id}/stems/instrumental"
    },
    {
      "name": "original",
      "filename": "song_original.mp3",
      "size_bytes": 8388608,
      "download_url": "/api/v1/jobs/{job_id}/stems/original"
    }
  ]
}
```

---

### 5. Download Stem

**GET** `/api/v1/jobs/{job_id}/stems/{stem_name}`

Download a specific separated stem or the original audio.

**Stem Names:** `vocals`, `bass`, `drums`, `other`, `instrumental`, `original`

**Note:** The `instrumental` stem contains all non-vocal audio (bass + drums + other combined).

**Response:** `200 OK`
- Content-Type: `audio/mpeg`
- Body: MP3 file (320kbps)

---

### 6. Get Processed Frames

**GET** `/api/v1/jobs/{job_id}/frames`

Get pitch detection data (10ms intervals).

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "bpm": 120.0,
    "original_song_path": "/path/to/song.mp3"
  },
  "processed_frames": [
    {
      "time": 0.0,
      "frequency": 440.0,
      "confidence": 0.95,
      "midi_pitch": 69.0,
      "is_voiced": true
    },
    {
      "time": 0.01,
      "frequency": 442.5,
      "confidence": 0.93,
      "midi_pitch": 69.1,
      "is_voiced": true
    }
  ],
  "frame_count": 24050
}
```

**Frame Fields:**
- `time` - Timestamp in seconds
- `frequency` - Frequency in Hz
- `confidence` - Detection confidence (0.0-1.0)
- `midi_pitch` - MIDI note number (nullable)
- `is_voiced` - Whether frame contains voice

---

### 7. Get Chords

**GET** `/api/v1/jobs/{job_id}/chords`

Get detected chord progression.

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "chords": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "duration": 2.5,
      "chord_label": "C",
      "confidence": 0.89,
      "root": "",
      "quality": "",
      "bass": ""
    },
    {
      "start_time": 2.5,
      "end_time": 5.0,
      "duration": 2.5,
      "chord_label": "G:maj",
      "confidence": 0.92,
      "root": "",
      "quality": "",
      "bass": ""
    }
  ],
  "duration": 240.5,
  "sample_rate": 44100,
  "tempo_bpm": 120.0,
  "key_info": {},
  "num_chords": 48
}
```

**Chord Fields:**
- `start_time` - Start time in seconds
- `end_time` - End time in seconds
- `duration` - Duration of the chord in seconds
- `chord_label` - Chord name (e.g., "C", "G:maj", "A:min", "N" for no chord)
- `confidence` - Detection confidence (0.0-1.0)
- `root` - Root note (currently empty string)
- `quality` - Chord quality (currently empty string)
- `bass` - Bass note (currently empty string)

---

### 8. Delete Job

**DELETE** `/api/v1/jobs/{job_id}`

Delete job and all associated files.

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job and associated files deleted successfully",
  "deleted": true
}
```

---

### 9. Health Check

**GET** `/health`

Check API health and queue status.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "connected",
  "storage": "/path/to/storage",
  "active_jobs": 2,
  "max_concurrent_jobs": 3
}
```

---

## Typical Usage Flow

```
1. Upload File
   POST /api/v1/transcribe
   → Get job_id

2. Poll Status (every 2-5 seconds)
   GET /api/v1/jobs/{job_id}/status
   → Check progress (0-100%)
   → Check status (queued → processing → completed)

3. When status = "completed":
   
   a) Get Results Summary
      GET /api/v1/jobs/{job_id}/results
   
   b) Download Stems
      GET /api/v1/jobs/{job_id}/stems/vocals
      GET /api/v1/jobs/{job_id}/stems/bass
      (etc.)
   
   c) Get Frames Data
      GET /api/v1/jobs/{job_id}/frames
   
   d) Get Chords Data
      GET /api/v1/jobs/{job_id}/chords

4. Cleanup (optional)
   DELETE /api/v1/jobs/{job_id}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here",
  "error_code": "OPTIONAL_CODE",
  "timestamp": "2026-01-31T12:00:00Z"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `202` - Accepted (async operation started)
- `400` - Bad Request (invalid input)
- `404` - Not Found (job doesn't exist)
- `413` - Payload Too Large (file too big)
- `429` - Too Many Requests (queue full)
- `500` - Internal Server Error

---

## Processing Times

**Typical for 4-minute song:**
- Total: 2-3 minutes
- Separation: 45-60 seconds
- Transcription: 45-60 seconds
- Chords: 30-45 seconds

**Concurrent Jobs:** Maximum 3 jobs can process simultaneously.

---

## CORS

All origins are allowed in development. Production will restrict to specific domains.

---

## Interactive Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Use these for testing and exploring the API interactively.

