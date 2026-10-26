# Python AI service

This folder is the Python half of the AI Document Assistant. The Laravel application in the parent directory is the website. This service reads PDFs, stores searchable passages, and asks a language model to answer from those passages.

Laravel and Python stay separate. Laravel handles pages, login, and the PDF the user uploaded in the browser. Python handles text extraction, embeddings, search, and the language model. The website already posts each question to `POST /ask` on this service.

## How an answer is produced

1. The PDF text is split into overlapping chunks. Short passages are easier to search than a whole file, and the overlap keeps a sentence that falls on a cut.
2. Each chunk is turned into a vector by the Sentence Transformers model `sentence-transformers/all-MiniLM-L6-v2`. That model is small enough for a laptop. The first use downloads it, about 90 MB. Change `EMBEDDING_MODEL` only if you also delete `storage/chroma`, because old and new vectors are not comparable.
3. The vectors are stored in a local ChromaDB database under `storage/chroma`.
4. A question is embedded with the same model. Chroma returns the closest passages for that document.
5. Those passages and the question are sent to the configured language model. The prompt tells the model to use only that text and to treat the PDF as data, not as new instructions.

If search finds no passages, the API says so and does not call the model. A scanned PDF with no text layer cannot be read. This service does not perform OCR.

Processing is synchronous. A large PDF, or the first load of the embedding model, can take longer than a minute. Laravel waits up to `AI_PYTHON_TIMEOUT` seconds (180 in `.env.example`) and then stores a generic failure if Python has not answered yet.

## Project layout

| Path | Purpose |
| --- | --- |
| `app/main.py` | Creates the FastAPI app and registers routes. |
| `app/config.py` | Reads host, port, chunking, embedding, Chroma, and language-model settings. |
| `app/api/routes/health.py` | The health endpoint. |
| `app/api/routes/documents.py` | Upload, list, inspect, process, and delete documents. |
| `app/api/routes/chat.py` | `POST /api/chat/ask` for a document that is already indexed. |
| `app/api/routes/ask.py` | `POST /ask`, the route the Laravel site calls. |
| `app/services/document_processor.py` | Reads PDF text and splits it into chunks. |
| `app/services/embedding_service.py` | Loads the embedding model when it is first needed. |
| `app/services/vector_store.py` | Saves and searches chunk vectors in ChromaDB. |
| `app/services/llm_service.py` | Calls the configured language model. |
| `app/services/rag_pipeline.py` | Retrieves passages, builds the prompt, and requests an answer. |
| `app/services/metadata_store.py` | Saves upload records in SQLite. |
| `app/utils/exceptions.py` | Errors that can be shown safely to a caller. |
| `storage/uploads/` | Saved PDFs. The filename is a generated id, not the browser filename. |
| `storage/metadata/` | The SQLite file that records uploads. |
| `tests/` | Automated checks that do not need a running server. |

## Requirements

- Python 3.10.6 or another Python 3.10+ release. This machine uses Laragon's Python at `D:\laragon\bin\python\python-3.10\python.exe`.
- No LLM API key is required to start the service or call the health endpoint. A key, or a local Ollama server, is required before a question can be answered.

## Setup

From this `python-ai` directory:

```powershell
D:\laragon\bin\python\python-3.10\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

`.env` is ignored by git. Change `API_PORT` there if port 8001 is already in use.

## Start the API

The host and port in `.env` are used when you start the app as a module:

```powershell
.\.venv\Scripts\python.exe -m app.main
```

You can also pass the same values to Uvicorn directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open the API docs and send a test call from the browser:

- Swagger UI: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc
- OpenAPI file: http://127.0.0.1:8001/openapi.json

In Swagger, open an operation and choose **Try it out**. Health needs no input. Upload needs a PDF in the `file` field.

| Method | Path | What a successful call returns |
| --- | --- | --- |
| GET | `/api/health` | `status` `success` and a short message |
| POST | `/api/documents/upload` | `document_id`, `original_filename`, `status` `uploaded`, and a message |
| POST | `/api/documents/{document_id}/process` | Extracts text, creates embeddings, and stores them. Status becomes `processed`. |
| GET | `/api/documents` | Lists document id, filename, time, status, page count, and chunk count. |
| GET | `/api/documents/{document_id}` | One document record. `404` when it is missing. |
| DELETE | `/api/documents/{document_id}` | Deletes the index, the metadata, and a PDF stored by this API. |
| POST | `/api/chat/ask` | Answers from indexed documents. Body: `question`, optional `document_id`, optional `top_k` from 1 to 10. |
| POST | `/ask` | Laravel's question call. Body: `document_id`, `user_id`, `filename`, `storage_path`, `question`. |

Upload errors use `status` `error` plus `message`. A non-PDF is `400`. A file over `MAX_UPLOAD_SIZE_MB` is `413`.

`POST /api/chat/ask` returns:

```json
{
  "status": "success",
  "answer": "The total is 42.",
  "retrieved_chunk_count": 1,
  "sources": [
    {"document_id": "document-id", "page_numbers": [1], "excerpt": "The contract total is 42."}
  ]
}
```

`POST /ask` returns `{ "answer": "...", "meta": { "sources": [], "retrieved_chunk_count": 1 } }`. That is the shape Laravel already expects.

## Language model

This project is set to the local Ollama model `llama3.2`. Ollama must be running on this PC. No API key is required.

```text
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_KEY=
LLM_BASE_URL=http://127.0.0.1:11434/v1
```

Install Ollama, then download the model:

```powershell
winget install --id Ollama.Ollama -e
ollama pull llama3.2
```

To use OpenAI instead:

```text
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.openai.com/v1
```

Restart the Python process after changing `.env`. The key is read from the environment only. It is not written into source code. Health and PDF extraction still work when these values are empty. A question then returns an error saying the model is not configured, and Laravel shows its generic failure sentence.

`API_TOKEN` is optional. When it is set, every route except health requires `Authorization: Bearer <token>`. Use the same value as Laravel's `AI_PYTHON_TOKEN`.

## Laravel

The website setup, login, and the upload-then-question flow are documented in the root [README](../README.md). Laravel posts each question to `POST /ask`. That call indexes the private PDF on the first question. `POST /api/documents/upload` is a separate API path: it only stores the file until `POST /api/documents/{document_id}/process`.

This API has no user accounts. Laravel checks that the logged-in user owns the document before it calls Python. Do not expose port 8001 beyond this machine unless `API_TOKEN` is set. The service does not return stack traces or file paths.

A healthy response is:

```json
{
  "status": "success",
  "message": "Python AI service is running"
}
```

Upload a PDF directly to this API with:

```powershell
curl.exe -F "file=@C:\path\to\notes.pdf" http://127.0.0.1:8001/api/documents/upload
```

A successful upload returns the document id, the original filename, status `uploaded`, and a short message. It does not return the folder where the file was saved. Call `POST /api/documents/{document_id}/process` before `POST /api/chat/ask`. `MAX_UPLOAD_SIZE_MB` limits this API upload. The default is 10 MB. The website upload limit is Laravel's `AI_MAX_UPLOAD_KB`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests call the API inside the process. They build small PDFs in memory, use temporary folders, and do not download models or call an external AI API.

## Storage

`storage/uploads` receives PDFs from the Python upload route. `storage/metadata` holds the SQLite status file. `storage/chroma` holds the vector index. Do not put these folders under Laravel's `public/` directory. Real files written there stay out of git; only the empty `.gitkeep` files are tracked.

To clear local search data, stop the API and delete the files inside `storage/chroma` and `storage/metadata`. Leave the `.gitkeep` files. Leave Laravel's `storage/app/private` in place if those uploaded PDFs should remain.
