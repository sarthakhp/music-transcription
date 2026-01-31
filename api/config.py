from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")
    api_workers: int = Field(default=4, description="Number of worker processes")
    
    storage_path: Path = Field(default=Path("./storage"), description="Base storage directory")
    max_file_size_mb: int = Field(default=100, description="Maximum upload file size in MB")
    job_retention_days: int = Field(default=7, description="Days to keep completed jobs")
    
    max_concurrent_jobs: int = Field(default=3, description="Maximum concurrent processing jobs")
    enable_gpu: bool = Field(default=True, description="Enable GPU/MPS acceleration")
    
    database_url: str = Field(
        default="sqlite:///./api.db",
        description="Database connection URL"
    )
    
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins"
    )
    
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Path = Field(default=Path("./logs/api.log"), description="Log file path")
    
    separation_model_path: Path = Field(
        default=Path("models/separation"),
        description="Path to source separation models"
    )
    chord_model_path: Path = Field(
        default=Path("models/chord_detection/btc_model.pt"),
        description="Path to chord detection model"
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024
    
    def get_job_storage_path(self, job_id: str) -> Path:
        return self.storage_path / "jobs" / job_id
    
    def ensure_directories(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "jobs").mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

