<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Answer driver
    |--------------------------------------------------------------------------
    |
    | "placeholder" stores a reply that the Python service is not connected.
    | "python" POSTs JSON to the URL below:
    |
    | {
    |     "document_id": 1,
    |     "user_id": 1,
    |     "filename": "contract.pdf",
    |     "storage_path": "documents/1/uuid.pdf",
    |     "question": "What is the total?"
    | }
    |
    | The Python service should respond with:
    |
    | { "answer": "...", "meta": {} }
    |
    */

    'driver' => env('AI_DRIVER', 'placeholder'),

    'max_upload_kb' => (int) env('AI_MAX_UPLOAD_KB', 20480),

    'python' => [
        'url' => env('AI_PYTHON_URL', 'http://127.0.0.1:8001/ask'),
        'token' => env('AI_PYTHON_TOKEN'),
        'timeout' => (int) env('AI_PYTHON_TIMEOUT', 60),
    ],

];
