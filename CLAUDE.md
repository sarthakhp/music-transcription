# Music Transcription — Backend

## Code Navigation
- **Always use Serena MCP tools** for code reading, symbol lookup, and navigation. Never use default Read/Grep/Glob or Explore agents for code analysis.
- Activate the project via Serena at session start.

## Architecture
- **FastAPI** backend at `api/` — routes, services, workers, database
- **SQLite** database via SQLAlchemy at `api.db`; schema migrations in `api/database/session.py` using additive `ALTER TABLE ADD COLUMN` (no Alembic)
- **Job pipeline**: upload → separate stems (Demucs) → transcribe pitch (CREPE) → chord detection → store results
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
| `api/workers/` | Background processing workers |
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
- Backend files inside the installed `.app` are at `Contents/Resources/backend/api/` — changes to the source repo don't auto-deploy there; use the deploy script
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
