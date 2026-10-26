"""Shapes returned by the HTTP API and shown in the API docs."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["success"])
    message: str = Field(examples=["Python AI service is running"])


class ErrorResponse(BaseModel):
    status: str = Field(examples=["error"])
    message: str = Field(examples=["Only PDF files are accepted."])
