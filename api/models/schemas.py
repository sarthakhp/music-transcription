from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

from api.database.models import JobStatus, ProcessingStage


def utc_now():
    return datetime.now(timezone.utc)


class JobCreate(BaseModel):
    pass


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    stage: Optional[ProcessingStage] = None
    progress: int

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    error_message: Optional[str] = None
    message: Optional[str] = None
    
    input_filename: str
    file_size: int
    separation_model: Optional[str] = None

    source_type: Optional[str] = None
    source_url: Optional[str] = None
    video_title: Optional[str] = None

    duration: Optional[float] = None
    tempo_bpm: Optional[float] = None
    num_frames: Optional[int] = None
    num_chords: Optional[int] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class JobStatusResponse(BaseModel):
    id: str
    status: JobStatus
    stage: Optional[ProcessingStage] = None
    progress: int
    stage_progress: int = 0
    error_message: Optional[str] = None
    message: Optional[str] = None

    class Config:
        from_attributes = True


class TranscribeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = "Job created successfully"


class JobResultsResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    
    input_filename: str
    duration: Optional[float] = None
    tempo_bpm: Optional[float] = None
    
    stems: Optional[List[str]] = None
    frames_available: bool = False
    instruments_available: bool = False
    chords_available: bool = False
    
    num_frames: Optional[int] = None
    num_chords: Optional[int] = None
    
    processing_time: Optional[float] = None
    
    class Config:
        from_attributes = True


class StemInfo(BaseModel):
    name: str
    filename: str
    size_bytes: int
    download_url: str


class StemsListResponse(BaseModel):
    job_id: str
    stems: List[StemInfo]


class HealthResponse(BaseModel):
    status: str
    database: str
    storage: str
    active_jobs: int
    max_concurrent_jobs: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class ProcessedFrame(BaseModel):
    time: float
    frequency: float
    confidence: float
    midi_pitch: Optional[float] = None
    is_voiced: bool


class FramesResponse(BaseModel):
    job_id: str
    metadata: dict
    processed_frames: List[ProcessedFrame]
    frame_count: int


class Chord(BaseModel):
    start_time: float
    end_time: float
    duration: float
    chord_label: str
    confidence: Optional[float] = None
    root: str = ""
    quality: str = ""
    bass: str = ""


class ChordsResponse(BaseModel):
    job_id: str
    chords: List[Chord]
    duration: float
    sample_rate: Optional[int] = None
    tempo_bpm: Optional[float] = None
    key_info: Optional[dict] = None
    num_chords: int


class URLMetadataResponse(BaseModel):
    title: str
    duration: float          # total duration in seconds
    uploader: str
    thumbnail: Optional[str] = None
    url: str
    max_duration_seconds: int  # so the UI knows the limit


class InstrumentNote(BaseModel):
    onset: float
    offset: float
    duration: float
    pitch: int
    velocity: int
    confidence: float = 0.0
    pitch_bends: List[float] = []


class InstrumentTrackResponse(BaseModel):
    instrument: str
    num_notes: int
    duration: float
    notes: List[InstrumentNote]


class InstrumentsResponse(BaseModel):
    job_id: str
    tracks: dict[str, InstrumentTrackResponse]
    duration: float
    total_notes: int
    tempo_bpm: Optional[float] = None


class CancelJobResponse(BaseModel):
    job_id: str
    message: str = "Job cancelled successfully"
    cancelled: bool = True


class DeleteJobResponse(BaseModel):
    job_id: str
    message: str = "Job deleted successfully"
    deleted: bool = True


class QueueStatusResponse(BaseModel):
    active_jobs: int
    max_concurrent_jobs: int
    can_accept_jobs: bool
    active_job_ids: List[str]


class SeparationModelResponse(BaseModel):
    key: str
    display_name: str
    stems: List[str]
    description: str


class SeparationModelsListResponse(BaseModel):
    models: List[SeparationModelResponse]
    default_model: str

