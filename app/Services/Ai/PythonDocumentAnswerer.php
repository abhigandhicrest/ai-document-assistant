<?php

namespace App\Services\Ai;

use App\Models\Document;
use App\Models\Question;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

class PythonDocumentAnswerer implements DocumentAnswerer
{
    public const FAILURE_MESSAGE = 'The AI backend could not answer this question.';

    public function answer(Document $document, string $question): AnswerResult
    {
        try {
            $request = Http::acceptJson()
                ->asJson()
                ->timeout($this->timeout());

            $token = config('ai.python.token');

            if (is_string($token) && $token !== '') {
                $request = $request->withToken($token);
            }

            $response = $request->post((string) config('ai.python.url'), [
                'document_id' => $document->id,
                'user_id' => $document->user_id,
                'filename' => $document->original_name,
                'storage_path' => $document->path,
                'question' => $question,
            ]);
        } catch (ConnectionException $exception) {
            report($exception);

            return $this->failure();
        } catch (Throwable $exception) {
            report($exception);

            return $this->failure();
        }

        $answer = $response->json('answer');
        $meta = $response->json('meta');

        if ($response->failed() || ! is_string($answer) || $answer === '') {
            Log::warning('Python AI request failed.', [
                'status' => $response->status(),
                'document_id' => $document->id,
            ]);

            return $this->failure();
        }

        return new AnswerResult(
            answer: $answer,
            status: Question::STATUS_ANSWERED,
            meta: is_array($meta) ? $meta : [],
        );
    }

    private function timeout(): int
    {
        return max(1, (int) config('ai.python.timeout', 60));
    }

    private function failure(): AnswerResult
    {
        return new AnswerResult(
            answer: self::FAILURE_MESSAGE,
            status: Question::STATUS_FAILED,
        );
    }
}
