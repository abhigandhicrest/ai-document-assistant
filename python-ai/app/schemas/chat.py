"""Question and answer shapes for the chat API and the Laravel /ask call."""

from pydantic import BaseModel, Field, field_validator


class Source(BaseModel):
    document_id: str
    page_numbers: list[int]
    excerpt: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    document_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("A question is required.")
        return stripped

    @field_validator("document_id")
    @classmethod
    def document_id_is_safe(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("The document id is not valid.")
        return value


class ChatResponse(BaseModel):
    status: str = "success"
    answer: str
    retrieved_chunk_count: int
    sources: list[Source]


class LaravelAskRequest(BaseModel):
    document_id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    filename: str = Field(min_length=1, max_length=255)
    storage_path: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=5000)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("A question is required.")
        return stripped


class LaravelAskResponse(BaseModel):
    answer: str
    meta: dict[str, object]
