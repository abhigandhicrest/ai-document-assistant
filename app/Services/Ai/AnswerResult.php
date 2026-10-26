<?php

namespace App\Services\Ai;

final readonly class AnswerResult
{
    /**
     * @param  array<string, mixed>  $meta
     */
    public function __construct(
        public string $answer,
        public string $status,
        public array $meta = [],
    ) {}
}
