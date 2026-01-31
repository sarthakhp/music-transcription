from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class JobStatus(str, PyEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(str, PyEnum):
    SEPARATION = "separation"
    TRANSCRIPTION = "transcription"
    CHORDS = "chords"


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String(36), primary_key=True, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True)
    stage = Column(Enum(ProcessingStage), nullable=True)
    progress = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    error_message = Column(Text, nullable=True)
    
    input_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)

    duration = Column(Float, nullable=True)
    tempo_bpm = Column(Float, nullable=True)
    num_frames = Column(Integer, nullable=True)
    num_chords = Column(Integer, nullable=True)

    input_file_path = Column(Text, nullable=True)
    original_mp3_path = Column(Text, nullable=True)
    stem_paths = Column(JSON, nullable=True)
    frames_json_path = Column(Text, nullable=True)
    chords_json_path = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, stage={self.stage}, progress={self.progress}%)>"
    
    @property
    def is_complete(self) -> bool:
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED]
    
    @property
    def is_processing(self) -> bool:
        return self.status == JobStatus.PROCESSING
    
    @property
    def processing_time(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

