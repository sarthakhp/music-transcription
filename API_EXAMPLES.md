# Music Transcription API - Usage Examples

Language-agnostic HTTP examples for common workflows.

---

## Example 1: Complete Workflow

### Step 1: Upload Audio File

```http
POST /api/v1/transcribe HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="song.mp3"
Content-Type: audio/mpeg

[binary data]
------WebKitFormBoundary--
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job created successfully. Processing started."
}
```

### Step 2: Poll for Status

```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/status HTTP/1.1
Host: localhost:8000
```

**Response (Processing):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "stage": "separation",
  "progress": 15,
  "error_message": null
}
```

**Response (Completed):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "stage": "chords",
  "progress": 100,
  "error_message": null
}
```

### Step 3: Get Results Summary

```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/results HTTP/1.1
Host: localhost:8000
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "input_filename": "song.mp3",
  "duration": 240.5,
  "tempo_bpm": 120.0,
  "stems": ["vocals", "bass", "drums", "other", "original"],
  "frames_available": true,
  "chords_available": true,
  "num_frames": 24050,
  "num_chords": 48,
  "processing_time": 145.2
}
```

### Step 4: Download Vocals Stem

```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/stems/vocals HTTP/1.1
Host: localhost:8000
```

**Response:**
```
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Disposition: attachment; filename="song_vocals.mp3"

[MP3 binary data]
```

### Step 5: Get Pitch Data

```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/frames HTTP/1.1
Host: localhost:8000
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "bpm": 120.0,
    "original_song_path": "/storage/jobs/.../input/song.mp3"
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

### Step 6: Get Chord Progression

```http
GET /api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/chords HTTP/1.1
Host: localhost:8000
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "chords": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "chord": "C:maj",
      "confidence": 0.89
    },
    {
      "start_time": 2.5,
      "end_time": 5.0,
      "chord": "G:maj",
      "confidence": 0.92
    },
    {
      "start_time": 5.0,
      "end_time": 7.5,
      "chord": "Am:min",
      "confidence": 0.87
    }
  ],
  "duration": 240.5,
  "tempo_bpm": 120.0,
  "num_chords": 48
}
```

---

## Example 2: Error Handling

### File Too Large

```http
POST /api/v1/transcribe HTTP/1.1
[file > 100MB]
```

**Response:**
```json
HTTP/1.1 413 Payload Too Large

{
  "detail": "File size exceeds maximum allowed size of 100MB"
}
```

### Invalid File Type

```http
POST /api/v1/transcribe HTTP/1.1
[file: document.pdf]
```

**Response:**
```json
HTTP/1.1 400 Bad Request

{
  "detail": "Invalid file type. Allowed types: .mp3, .wav, .flac, .m4a, .ogg"
}
```

### Job Not Found

```http
GET /api/v1/jobs/invalid-job-id/status HTTP/1.1
```

**Response:**
```json
HTTP/1.1 404 Not Found

{
  "detail": "Job invalid-job-id not found"
}
```

### Queue Full

```http
POST /api/v1/transcribe HTTP/1.1
[when 3 jobs already processing]
```

**Response:**
```json
HTTP/1.1 429 Too Many Requests

{
  "detail": "Maximum concurrent jobs (3) reached. Please try again later."
}
```

---

## Example 3: Polling Pattern

**Recommended polling logic:**

1. Upload file → get `job_id`
2. Poll every 2-5 seconds
3. Stop polling when `status` is `completed` or `failed`
4. Fetch results

**Pseudo-code:**
```
job_id = upload_file()

while true:
  status = get_status(job_id)
  
  if status == "completed":
    results = get_results(job_id)
    break
  
  if status == "failed":
    error = get_error(job_id)
    break
  
  wait(3 seconds)
```

---

## Example 4: Health Check

```http
GET /health HTTP/1.1
Host: localhost:8000
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "storage": "/Users/user/projects/music-transcription/storage",
  "active_jobs": 2,
  "max_concurrent_jobs": 3
}
```

Use this to check if API is ready before uploading files.

