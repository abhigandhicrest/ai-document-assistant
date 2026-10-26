<?php

namespace App\Services\Ai;

use App\Models\Document;

interface DocumentAnswerer
{
    public function answer(Document $document, string $question): AnswerResult;
}
