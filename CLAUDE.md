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
