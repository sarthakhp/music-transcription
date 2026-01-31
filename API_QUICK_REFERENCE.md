# Music Transcription API - Quick Reference

**Base URL:** `http://localhost:8000`

---

## Endpoints Summary

| Method | Endpoint | Purpose | Returns |
|--------|----------|---------|---------|
| **POST** | `/api/v1/transcribe` | Upload audio file | `job_id` |
| **GET** | `/api/v1/jobs/{id}/status` | Poll progress | Status & progress % |
| **GET** | `/api/v1/jobs/{id}/results` | Get summary | All results info |
| **GET** | `/api/v1/jobs/{id}/stems` | List stems | Available stems |
| **GET** | `/api/v1/jobs/{id}/stems/{name}` | Download stem | MP3 file |
| **GET** | `/api/v1/jobs/{id}/frames` | Get pitch data | Frames JSON |
| **GET** | `/api/v1/jobs/{id}/chords` | Get chords | Chords JSON |
| **DELETE** | `/api/v1/jobs/{id}` | Delete job | Confirmation |
| **GET** | `/health` | Health check | System status |

---

## Job Status Flow

```
queued → processing → completed
                   ↘ failed
```

**Progress Stages:**
- `separation` (0-33%)
- `transcription` (33-66%)
- `chords` (66-100%)

---

## Example: Upload & Poll

**1. Upload**
```http
POST /api/v1/transcribe
Content-Type: multipart/form-data

file: song.mp3
```

**Response:**
```json
{
  "job_id": "abc-123",
  "status": "queued"
}
```

**2. Poll Status**
```http
GET /api/v1/jobs/abc-123/status
```

**Response:**
```json
{
  "status": "processing",
  "stage": "transcription",
  "progress": 45
}
```

---

## Example: Get Results

**When status = "completed":**

```http
GET /api/v1/jobs/abc-123/results
```

**Response:**
```json
{
  "status": "completed",
  "progress": 100,
  "stems": ["vocals", "bass", "drums", "other", "original"],
  "frames_available": true,
  "chords_available": true,
  "duration": 240.5,
  "tempo_bpm": 120.0
}
```

---

## Example: Download Stems

```http
GET /api/v1/jobs/abc-123/stems/vocals
GET /api/v1/jobs/abc-123/stems/original
```

**Returns:** MP3 file (audio/mpeg)

**Available stems:** `vocals`, `bass`, `drums`, `other`, `original`

---

## Example: Get Frames

```http
GET /api/v1/jobs/abc-123/frames
```

**Response:**
```json
{
  "processed_frames": [
    {
      "time": 0.0,
      "frequency": 440.0,
      "confidence": 0.95,
      "midi_pitch": 69.0,
      "is_voiced": true
    }
  ],
  "frame_count": 24050
}
```

---

## Example: Get Chords

```http
GET /api/v1/jobs/abc-123/chords
```

**Response:**
```json
{
  "chords": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "chord": "C:maj",
      "confidence": 0.89
    }
  ],
  "num_chords": 48
}
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| `400` | Invalid file type or request |
| `404` | Job not found |
| `413` | File too large (>100MB) |
| `429` | Queue full (max 3 jobs) |
| `500` | Server error |

---

## File Formats

**Supported:** MP3, WAV, FLAC, M4A, OGG  
**Max Size:** 100MB  
**Output Stems:** MP3 (320kbps)

---

## Timing

**4-minute song:** ~2-3 minutes processing  
**Poll Interval:** Every 2-5 seconds  
**Concurrent Jobs:** Max 3

---

## Testing

**Interactive Docs:** http://localhost:8000/docs

Try the API directly in your browser!

