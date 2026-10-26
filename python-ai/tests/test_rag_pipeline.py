"""RAG tests. The language model and the vector search are both fakes."""

import json

import httpx
import pytest

from app.services.llm_service import LlmService
from app.services.rag_pipeline import NO_CONTEXT_ANSWER, SYSTEM_PROMPT, RagPipeline, build_user_prompt
from app.services.vector_store import RetrievedChunk
from app.utils.exceptions import AppError
from tests.fakes import FakeLlm, ScriptedStore


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        document_id="doc-1",
        chunk_index=0,
        text="The contract total is 42.",
        page_numbers=[1],
    )


def test_prompt_includes_the_passage_and_refuses_invented_facts() -> None:
    prompt = build_user_prompt("What is the total?", [_chunk()])

    assert "The contract total is 42." in prompt
    assert "What is the total?" in prompt
    assert "pages 1" in prompt
    assert "untrusted data" in SYSTEM_PROMPT
    assert "does not contain the answer" in SYSTEM_PROMPT
    assert "even when the sentence is short" in SYSTEM_PROMPT


def test_answer_uses_retrieved_context_and_returns_sources() -> None:
    llm = FakeLlm("The total is 42.")
    pipeline = RagPipeline(ScriptedStore([_chunk()]), llm)

    result = pipeline.answer("What is the total?", document_id="doc-1", top_k=3)

    assert result.answer == "The total is 42."
    assert result.retrieved_chunk_count == 1
    assert result.sources[0].document_id == "doc-1"
    assert result.sources[0].page_numbers == [1]
    assert result.sources[0].excerpt == "The contract total is 42."
    assert "The contract total is 42." in llm.prompts[0][1]


def test_no_context_does_not_call_the_language_model() -> None:
    llm = FakeLlm()
    pipeline = RagPipeline(ScriptedStore([]), llm)

    result = pipeline.answer("What is the total?", document_id="doc-1", top_k=3)

    assert result.answer == NO_CONTEXT_ANSWER
    assert result.retrieved_chunk_count == 0
    assert result.sources == []
    assert llm.prompts == []


def test_language_model_errors_are_returned() -> None:
    llm = FakeLlm()
    llm.error = AppError("The language model could not be reached.", status_code=503)
    pipeline = RagPipeline(ScriptedStore([_chunk()]), llm)

    with pytest.raises(AppError, match="could not be reached"):
        pipeline.answer("What is the total?", document_id="doc-1", top_k=3)


def test_missing_provider_is_rejected_before_a_network_call() -> None:
    service = LlmService("", "", "", "", 5)

    with pytest.raises(AppError, match="not configured"):
        service.generate("system", "user")


def test_openai_requires_an_api_key() -> None:
    service = LlmService("openai", "gpt-4o-mini", "", "https://api.openai.com/v1", 5)

    with pytest.raises(AppError, match="API key"):
        service.generate("system", "user")


def test_openai_request_uses_the_configured_model() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "The total is 42."}}]})

    service = LlmService(
        "openai",
        "gpt-4o-mini",
        "secret-key",
        "https://api.openai.com/v1",
        5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert service.generate("Be careful", "What is the total?") == "The total is 42."
    assert seen["body"]["model"] == "gpt-4o-mini"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["messages"][0]["content"] == "Be careful"
