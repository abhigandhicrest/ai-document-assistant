<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreQuestionRequest;
use App\Models\Document;
use App\Services\Ai\DocumentAnswerer;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;

class QuestionController extends Controller
{
    public function store(StoreQuestionRequest $request, Document $document, DocumentAnswerer $answerer): JsonResponse|RedirectResponse
    {
        $result = $answerer->answer($document, $request->string('body')->toString());

        $question = $document->questions()->create([
            'user_id' => $request->user()->id,
            'body' => $request->validated('body'),
            'answer' => $result->answer,
            'status' => $result->status,
            'meta' => $result->meta,
        ]);

        if ($request->expectsJson()) {
            return response()->json([
                'question' => [
                    'body' => $question->body,
                    'answer' => $question->answer,
                    'status' => $question->status,
                ],
            ]);
        }

        return redirect()->route('documents.show', $document);
    }
}
