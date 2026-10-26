"""Call a configured language model.

The RAG pipeline asks this service for an answer. Provider HTTP details stay
here. Tests can pass their own HTTP client so no real model is contacted.
"""

import httpx

from app.utils.exceptions import AppError


class LlmService:
    """OpenAI-compatible chat API used for OpenAI and for a local Ollama server."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
        client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.model = model.strip()
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout_seconds = max(1, timeout_seconds)
        self._client = client

    def ensure_configured(self) -> None:
        """Fail before a long indexing step when the model settings are incomplete."""
        self._require_configuration()

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self._require_configuration()
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        owned_client = self._client is None
        client = self._client or httpx.Client()
        try:
            try:
                response = client.post(
                    f"{self._resolved_base_url()}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise AppError(
                    "The language model could not be reached.",
                    status_code=503,
                ) from exc
        finally:
            if owned_client:
                client.close()

        if response.status_code in {401, 403}:
            raise AppError("The language model rejected the API key.", status_code=502)
        if response.status_code >= 400:
            raise AppError("The language model could not generate an answer.", status_code=502)

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AppError(
                "The language model returned an unexpected response.",
                status_code=502,
            ) from exc
        if not isinstance(content, str) or content.strip() == "":
            raise AppError("The language model returned an empty answer.", status_code=502)
        return content.strip()

    def _require_configuration(self) -> None:
        if self.provider not in {"openai", "ollama"}:
            raise AppError(
                "The language model is not configured. Set LLM_PROVIDER to openai or ollama.",
                status_code=503,
            )
        if self.model == "":
            raise AppError("The language model name is missing. Set LLM_MODEL.", status_code=503)
        if self.provider == "openai" and self.api_key == "":
            raise AppError(
                "The language model API key is missing. Set LLM_API_KEY.",
                status_code=503,
            )

    def _resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url
        if self.provider == "ollama":
            return "http://127.0.0.1:11434/v1"
        return "https://api.openai.com/v1"
