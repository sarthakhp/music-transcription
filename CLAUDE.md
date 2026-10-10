# Music Transcription — Backend

## Code Navigation
- **Always use Serena MCP tools** for code reading, symbol lookup, and navigation. Never use default Read/Grep/Glob or Explore agents for code analysis.
- Activate the project via Serena at session start.

## Architecture
- **FastAPI** backend at `api/` — routes, services, workers, database
- **SQLite** database via SQLAlchemy at `api.db`; schema migrations in `api/database/session.py` using additive `ALTER TABLE ADD COLUMN` (no Alembic)
- **Job pipeline**: upload → separate stems → transcribe vocal pitch → instrument notes → chord detection → store results. Per-job `audio_type` (`mixed` default | `vocals` | `instrumental`, `AudioType` in `api/database/models.py`) decides which stages run; it flows route → `JobManager.create_job` → `task_queue` kwargs → `job_runner --audio-type` → `PipelineWorker`, and retry reuses `job.audio_type`. `vocals`/`instrumental` skip separation (original is the only stem) and the model download. Skipped stages still write **empty-but-valid** frames/instruments/chords JSON, because the viewer errors on a missing frames or chords file.
- **Storage**: audio files in `files/`, processed outputs in `storage/`, models in `models/`
- **Packaging**: `packaging/` builds the macOS `.app` via pywebview; the Flutter web frontend is bundled inside

## Key Files
| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI app, CORS middleware (`allow_origin_regex` for localhost dev) |
| `api/config.py` | Settings via pydantic (`cors_allow_localhost`, origins, etc.) |
| `api/routes/jobs.py` | Job CRUD, rename (`PATCH /{id}/rename`), results endpoints |
| `api/database/session.py` | DB init + `_migrate_db()` for additive schema migrations |
| `api/database/models.py` | SQLAlchemy Job model (`display_name` column added) |
| `api/models/schemas.py` | Pydantic response schemas (`JobResponse`, `RenameJobRequest`, etc.) |
| `api/workers/` | Background processing workers (`pipeline_worker.py` = stage logic, `task_queue.py` = subprocess spawn, `job_runner.py` = CLI entry) |
| `api/services/storage_publisher.py` | Publishes completed jobs to Firebase Storage; `sync_job_metadata` pushes display name / audio type to an already-published job |
| `api/services/cloud_library.py` + `api/routes/cloud.py` | List the cloud index and **import** a cloud-only job into local storage (same id, same on-disk layout, so every existing endpoint serves it) |
| `api/services/settings_sync.py` | Per-song viewer settings at `settings/<job_id>.json` in the bucket (`GET/PUT /api/v1/cloud/jobs/{id}/settings`) |
| `packaging/launcher.py` | pywebview launcher — `private_mode=False` required for preferences |

## Dev Workflow
- Start backend: `python run_api.py` (port 47821)
- Frontend dev server talks to backend at `http://localhost:47821`
- CORS: `cors_allow_localhost=true` in config allows all `http://localhost:*` origins
- To deploy frontend to the installed DMG: run `../music-transcription-viewer/scripts/deploy_launchpad.sh`

## Schema Migrations
Never use Alembic — use additive `ALTER TABLE ADD COLUMN` in `_migrate_db()`:
```python
if "column_name" not in columns:
    conn.execute(text("ALTER TABLE jobs ADD COLUMN column_name TYPE"))
    conn.commit()
```

## Cloud storage (Firebase)
Layout: `index.json` (summaries), `jobs/<id>/{manifest,frames,chords,instruments}.json` + `*.mp3`, `settings/<id>.json`. Reads are public via download-token URLs; **anonymous writes are denied** (only the backend's service account writes), so the hosted viewer/phone are read-only.
- **Never overwrite a bucket object without keeping its `firebaseStorageDownloadTokens` metadata.** The hosted viewer's `FIREBASE_INDEX_URL` (a CI variable, also baked into the deployed `main.dart.js`) includes `index.json`'s token; losing it breaks the hosted site. Use `bucket.get_blob()` (loads metadata; `blob()` + `exists()` does not) or `blob.patch()`.
- Settings objects use a deterministic token (`uuid5(NAMESPACE_URL, "music-transcription-settings:<id>")`) so clients build the URL from the job id alone; the Dart side mirrors it (`settingsToken`).
- Manifest/index carry `display_name` and `audio_type`; `PATCH /rename` syncs them in a background task.

## Testing the backend safely
- Run a scratch server with `MT_DATA_DIR=<tmp> CHORD_MODEL_PATH=<repo model> uvicorn api.main:app --port <other>`; `MT_WEB_DIR=<flutter build/web>` serves the frontend from it.
- **The repo `.env` enables Firebase publishing.** A scratch server that completes a job publishes to the REAL bucket. Blank `FIREBASE_CREDENTIALS_PATH`/`FIREBASE_STORAGE_BUCKET` unless the test is deliberately read-only cloud access, and delete any test objects afterwards.

## CORS Setup
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"http://localhost:\d+" if settings.cors_allow_localhost else None,
    ...
)
```

## Gotchas
- `pywebview private_mode=False` — required or SharedPreferences (Flutter) won't persist
- Backend files inside the installed `.app` are at `Contents/Resources/backend/api/`. `deploy_launchpad.sh` (viewer repo) rsyncs `api/` there; `src/`, `requirements`, bundled Python/ffmpeg changes still need `packaging/macos/build.sh`. The app must be restarted, and the user's DB is migrated on next start
- Job `display_name` overrides `video_title` and `input_filename` for display

## DMG Debugging

**Live logs** — tail this while the app is running:
```bash
tail -f ~/Library/Application\ Support/MusicTranscriber/logs/launcher.log
```
All `dlog(...)` calls in `launcher.py` write here with timestamps.

**Hot-patching `launcher.py`** — no rebuild needed, just copy and restart the app:
```bash
cp packaging/launcher.py /Applications/MusicTranscriber.app/Contents/Resources/launcher.py
```

**What requires a full rebuild** (`bash packaging/macos/build.sh`):
- `setup_deps.py` or `requirements-launcher.txt` changes (venv packages)
- Flutter web build changes (or use `deploy_launchpad.sh` for just the frontend)
- Bundled Python/ffmpeg changes

## pywebview `create_file_dialog` file_types format

pywebview validates filter strings with a strict regex — the format must be `"Description(*.ext1;*.ext2)"` with **no space before `(`** and **no slashes in the description**:

```python
# Correct
file_types = ("Audio Video(*.mp3;*.wav;*.flac)", "JSON(*.json)", "All(*.*)")

# Wrong — slash in description, space before paren
file_types = ("Audio/Video Files (*.mp3;*.wav)", "All Files (*.*)")
```

The HTTP picker bridge (`_PickerHandler` on port 47823) is what the Flutter app uses to trigger the native dialog — it bypasses WKWebView's gesture-context restriction on pywebview's JS API.
