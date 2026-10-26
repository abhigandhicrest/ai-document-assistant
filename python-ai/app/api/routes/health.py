"""Health route.

This route only reports that the process is running. It must not load an
embedding model or contact a language model.
"""

from fastapi import APIRouter

from app.schemas.responses import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check that the API is running",
)
def health() -> HealthResponse:
    """Use this first when a later call fails.

    A 200 response means the Python process is up. This call does not read a
    PDF, load an embedding model, or contact a language model.
    """
    return HealthResponse(
        status="success",
        message="Python AI service is running",
    )
