# AI Document Assistant

A local document assistant. You sign in, upload a text PDF, and ask questions about that file. The Laravel site stores the PDF and the questions. A Python service reads the PDF, finds the relevant passages, and asks a local Llama model to answer from those passages.

The two programs stay separate:

| Part | Address | Responsibility |
| --- | --- | --- |
| Laravel website | http://127.0.0.1:8000 | Login, PDF storage, question history |
| Python API | http://127.0.0.1:8001 | Text extraction, search, language model |
| Ollama | http://127.0.0.1:11434 | Local Llama 3.2 answers |

Service-level API details are in [python-ai/README.md](python-ai/README.md). Interactive API docs are at http://127.0.0.1:8001/docs once the Python process is running.

## What happens when you upload and ask

Uploading stores the file. The PDF is read and indexed the first time you ask a question. Later questions on the same file reuse that index.

1. **Upload.** Laravel checks that the file is a PDF, then saves it on the private disk at `storage/app/private/documents/{user id}/{uuid}.pdf`. A MySQL row records the original name, path, size, and status `ready`. Python is not called during upload.
2. **Ask.** The question form sends the text to Laravel with AJAX. The page stays in place. Laravel checks that you own the document, then posts JSON to `POST /ask`:

```json
{
  "document_id": 2,
  "user_id": 1,
  "filename": "sample-contract.pdf",
  "storage_path": "documents/1/uuid.pdf",
  "question": "What is the total?"
}
```

3. **First question.** Python opens that file inside Laravel's private storage. It refuses paths that leave that folder. It then:
   - reads the embedded text and page numbers
   - splits the text into overlapping passages (`CHUNK_SIZE` 800, `CHUNK_OVERLAP` 120)
   - turns each passage into a vector with `sentence-transformers/all-MiniLM-L6-v2`
   - stores the vectors in a local Chroma database and marks the document `processed`
4. **Answer.** Python searches that document for the closest passages (4 by default) and sends those passages plus the question to Llama 3.2. The prompt tells the model to use only that text. If no passage is found, the model is not called.
5. **Save.** Python returns `{ "answer": "...", "meta": { "sources": [] } }`. Laravel stores the question and answer. The page adds the new card. A failed call is stored as “The AI backend could not answer this question.” Older failed rows stay as they were.

The embedding model is only for search. Llama 3.2 writes the answer. A scanned PDF with no text layer cannot be read, and encrypted PDFs are rejected. A PDF that is missing its xref table is repaired when the objects are still present.

The first question on a file is the slow one, because the embedding model loads and the passages are indexed. Laravel waits up to `AI_PYTHON_TIMEOUT` seconds.

## Requirements

- PHP 8.3 or newer. On this Laragon install, use PHP 8.4. The default `php` command may be 8.1, which cannot run this Laravel app. The PHP `intl`, `pdo_mysql`, `pdo_sqlite`, and `sqlite3` extensions must be enabled.
- Composer 2. MySQL 8, with a database named `ai_document_assistant`.
- Node.js 22 only when you change frontend assets. The built files in `public/build` are already present.
- Python 3.10 or newer. This machine uses `D:\laragon\bin\python\python-3.10\python.exe`.
- [Ollama](https://ollama.com) with the `llama3.2` model pulled.

Use http://127.0.0.1:8000. Do not open the site through a Laragon virtual host that is still on PHP 8.1.

## Run the project

Start MySQL from Laragon, then use three processes.

**1. Website**

```powershell
cd D:\laragon\www\ai-document-assistant
& "D:\laragon\bin\php\php-8.4.27-Win32-vs17-x64\php.exe" artisan serve --host=127.0.0.1 --port=8000
```

**2. Python API**

```powershell
cd D:\laragon\www\ai-document-assistant\python-ai
.\.venv\Scripts\python.exe -m app.main
```

**3. Local model**

Ollama usually keeps running after it is installed. If `http://127.0.0.1:11434/api/tags` does not list `llama3.2`, pull it:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull llama3.2
```

Check the Python service:

```powershell
curl.exe http://127.0.0.1:8001/api/health
```

A healthy response is `{"status":"success","message":"Python AI service is running"}`.

Open http://127.0.0.1:8000 and sign in. Upload a text PDF, open it, and ask a question. The first answer can take about half a minute.

Frontend assets are already built. Run this only after changing Blade, CSS, or JavaScript, and use Node 22:

```powershell
$env:Path = "D:\laragon\bin\nodejs\node-v22.23.4-win-x64;" + $env:Path
npm run dev
```

## Sign in

Registration is open at http://127.0.0.1:8000/register. Email verification is off. After login, Fortify sends you to `/documents`.

This database already has two local accounts. Both use the password `password`.

| Email | What this account can do |
| --- | --- |
| `alex.owner@example.com` | Upload documents and ask questions about them |
| `blair.reader@example.com` | Sign in, but cannot open another user's document |

A fresh `php artisan db:seed` creates `test@example.com` with the same password. It does not create the two accounts above.

Questions are limited to 10 per minute per user.

## First-time setup

The commands below are for a new checkout. Skip them when `vendor`, `python-ai\.venv`, and the MySQL database already exist.

```powershell
cd D:\laragon\www\ai-document-assistant
copy .env.example .env
& "D:\laragon\bin\php\php-8.4.27-Win32-vs17-x64\php.exe" artisan key:generate
& "D:\laragon\bin\php\php-8.4.27-Win32-vs17-x64\php.exe" artisan migrate
npm install
npm run build
```

Create the MySQL database `ai_document_assistant` first. The example `.env` uses user `root` and an empty password.

Then create the Python environment:

```powershell
cd D:\laragon\www\ai-document-assistant\python-ai
D:\laragon\bin\python\python-3.10\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Set Laravel's driver before asking questions:

```text
AI_DRIVER=python
AI_PYTHON_URL=http://127.0.0.1:8001/ask
AI_PYTHON_TIMEOUT=180
```

`AI_DRIVER` belongs in the Laravel root `.env`. A value in `python-ai/.env` is ignored. Restart `php artisan serve` after changing the Laravel `.env`.

`AI_DRIVER=placeholder` stores the sentence “The Python AI backend is not connected yet” and does not call Python. Existing question rows are not rewritten when you change the driver.

## Configuration

Laravel, in the root `.env`:

| Variable | Purpose |
| --- | --- |
| `AI_DRIVER` | `python` calls the API. `placeholder` stores a fixed sentence. |
| `AI_PYTHON_URL` | Question endpoint. Default `http://127.0.0.1:8001/ask`. |
| `AI_PYTHON_TOKEN` | Optional bearer token. Leave empty on this machine. |
| `AI_PYTHON_TIMEOUT` | Seconds Laravel waits for an answer. Default in the example file is 180. |
| `AI_MAX_UPLOAD_KB` | Website upload limit. Default 20480 KB (20 MB). |

Python, in `python-ai/.env`:

| Variable | Purpose |
| --- | --- |
| `API_HOST`, `API_PORT` | Bind address. Default `127.0.0.1:8001`. |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | Passage size. Overlap must be smaller than the chunk size. |
| `EMBEDDING_MODEL` | Search model. After changing it, delete `python-ai/storage/chroma` so old vectors are not mixed with new ones. |
| `LARAVEL_STORAGE_DIR` | Laravel private disk. Default `../storage/app/private`. |
| `TOP_K` | Passages sent to the language model. Default 4. The API also accepts 1 to 10 on `POST /api/chat/ask`. |
| `LLM_PROVIDER` | `ollama` for the local model. `openai` for a hosted model. |
| `LLM_MODEL` | `llama3.2` for the local setup. |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` for Ollama. |
| `LLM_API_KEY` | Empty for Ollama. Required for `LLM_PROVIDER=openai`. |
| `API_TOKEN` | When set, every route except health requires `Authorization: Bearer <token>`. Use the same value as `AI_PYTHON_TOKEN`. |

Restart the Python process after changing `python-ai/.env`.

To use OpenAI instead of Ollama, set `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, a real `LLM_API_KEY`, and `LLM_BASE_URL=https://api.openai.com/v1`.

## Project layout

| Path | Purpose |
| --- | --- |
| `app/Http/Controllers/DocumentController.php` | List, upload, show, download, and delete PDFs. |
| `app/Http/Controllers/QuestionController.php` | Save a question and return JSON for the AJAX form. |
| `app/Services/Ai/PythonDocumentAnswerer.php` | Posts the question contract to Python. |
| `resources/views/documents/show.blade.php` | Document page and the question form. |
| `config/ai.php` | Driver, URL, token, timeout, and upload limit. |
| `python-ai/app/api/routes/ask.py` | `POST /ask`, the route Laravel calls. |
| `python-ai/app/services/document_indexer.py` | Extract, chunk, embed, and store one PDF. |
| `python-ai/app/services/rag_pipeline.py` | Search passages and request an answer. |
| `storage/app/private` | Uploaded PDFs. This folder is not public. |
| `python-ai/storage/chroma` | Vector index. |
| `python-ai/storage/metadata` | SQLite status for indexed documents. |

Deleting a document in the website removes the private PDF and the MySQL row. It does not remove the Python vector index. To clear search data, stop the Python API and delete the files inside `python-ai/storage/chroma` and `python-ai/storage/metadata`. Leave the `.gitkeep` files.

## API

With the Python process running:

- Swagger UI: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc
- OpenAPI file: http://127.0.0.1:8001/openapi.json

| Method | Path | Used by |
| --- | --- | --- |
| GET | `/api/health` | Health check. Does not load the embedding model. |
| POST | `/ask` | The website. Indexes the Laravel PDF if needed, then answers. |
| POST | `/api/documents/upload` | Direct API upload. Status stays `uploaded` until process is called. |
| POST | `/api/documents/{document_id}/process` | Index a file uploaded through the Python API. |
| POST | `/api/chat/ask` | Ask about a document that is already `processed`. |
| GET | `/api/documents` | List indexed documents. |
| GET | `/api/documents/{document_id}` | One document record. |
| DELETE | `/api/documents/{document_id}` | Remove that API document, its vectors, and a PDF this API stored. |

## Tests

Laravel, using the PHP 8.4 binary:

```powershell
& "D:\laragon\bin\php\php-8.4.27-Win32-vs17-x64\php.exe" artisan test
```

Pest uses SQLite in memory, so `pdo_sqlite` and `sqlite3` must be enabled in that PHP build.

Python:

```powershell
cd python-ai
.\.venv\Scripts\python.exe -m pytest
```

The Python tests build small PDFs in temporary folders. They do not download the embedding model and they do not call Ollama.

## Limits

- Answers come from extracted text. Image-only scans are rejected.
- Encrypted PDFs are rejected.
- The website upload limit is 20 MB. The direct Python upload limit is 10 MB.
- A question that exceeds `AI_PYTHON_TIMEOUT` is saved as a failure even if Python finishes later. Ask again after the first index has completed.
- The red failure sentence is Laravel's generic message. The Python log or `storage/logs/laravel.log` has the status code.
- Port 8001 has no user accounts. Keep it on localhost, or set `API_TOKEN` before exposing it.
