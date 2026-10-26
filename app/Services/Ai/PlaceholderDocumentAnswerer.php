<?php

namespace App\Services\Ai;

use App\Models\Document;
use App\Models\Question;

class PlaceholderDocumentAnswerer implements DocumentAnswerer
{
    public const MESSAGE = 'The Python AI backend is not connected yet. Set AI_DRIVER=python when the service is available.';

    public function answer(Document $document, string $question): AnswerResult
    {
        return new AnswerResult(
            answer: self::MESSAGE,
            status: Question::STATUS_ANSWERED,
        );
    }
}
