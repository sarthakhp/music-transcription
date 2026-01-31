from fastapi import HTTPException, status


class JobNotFoundException(HTTPException):
    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )


class InvalidAudioFileException(HTTPException):
    def __init__(self, message: str = "Invalid audio file"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )


class FileTooLargeException(HTTPException):
    def __init__(self, max_size_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )


class ProcessingFailedException(HTTPException):
    def __init__(self, message: str = "Processing failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )


class StorageLimitExceededException(HTTPException):
    def __init__(self, message: str = "Storage limit exceeded"):
        super().__init__(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=message
        )


class TooManyJobsException(HTTPException):
    def __init__(self, max_jobs: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum concurrent jobs ({max_jobs}) reached. Please try again later."
        )

