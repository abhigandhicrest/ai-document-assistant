<?php

use App\Models\Document;
use App\Models\Question;
use App\Models\User;
use App\Services\Ai\PlaceholderDocumentAnswerer;
use App\Services\Ai\PythonDocumentAnswerer;
use Illuminate\Support\Facades\Http;

test('guests are redirected when asking a question', function () {
    $document = Document::factory()->create();

    $this->post(route('questions.store', $document), [
        'body' => 'What is this?',
    ])->assertRedirect(route('login'));
});

test('asking a question stores the question and the placeholder answer', function () {
    config(['ai.driver' => 'placeholder']);

    $user = User::factory()->create();
    $document = Document::factory()->for($user)->create();

    $this->actingAs($user)
        ->post(route('questions.store', $document), [
            'body' => 'What is the total?',
        ])
        ->assertRedirect(route('documents.show', $document));

    $question = $document->questions()->first();

    expect($question)->not->toBeNull()
        ->and($question->user_id)->toBe($user->id)
        ->and($question->body)->toBe('What is the total?')
        ->and($question->status)->toBe(Question::STATUS_ANSWERED)
        ->and($question->answer)->toBe(PlaceholderDocumentAnswerer::MESSAGE);

    $this->actingAs($user)
        ->get(route('documents.show', $document))
        ->assertOk()
        ->assertSee('What is the total?')
        ->assertSee(PlaceholderDocumentAnswerer::MESSAGE);
});

test('asking a question with ajax returns the stored answer', function () {
    config(['ai.driver' => 'placeholder']);

    $user = User::factory()->create();
    $document = Document::factory()->for($user)->create();

    $this->actingAs($user)
        ->postJson(route('questions.store', $document), [
            'body' => 'What is the total?',
        ])
        ->assertOk()
        ->assertJsonPath('question.body', 'What is the total?')
        ->assertJsonPath('question.answer', PlaceholderDocumentAnswerer::MESSAGE)
        ->assertJsonPath('question.status', Question::STATUS_ANSWERED);

    expect($document->questions()->count())->toBe(1);
});

test('the python driver stores an answer from the remote service', function () {
    config([
        'ai.driver' => 'python',
        'ai.python.url' => 'http://127.0.0.1:8001/ask',
        'ai.python.token' => 'secret-token',
    ]);

    Http::fake([
        'http://127.0.0.1:8001/ask' => Http::response([
            'answer' => 'The total is 42.',
            'meta' => ['page' => 2],
        ]),
    ]);

    $user = User::factory()->create();
    $document = Document::factory()->for($user)->create([
        'original_name' => 'contract.pdf',
        'path' => 'documents/'.$user->id.'/contract.pdf',
    ]);

    $this->actingAs($user)->post(route('questions.store', $document), [
        'body' => 'What is the total?',
    ])->assertRedirect(route('documents.show', $document));

    $question = $document->questions()->first();

    expect($question->status)->toBe(Question::STATUS_ANSWERED)
        ->and($question->answer)->toBe('The total is 42.')
        ->and($question->meta)->toBe(['page' => 2]);

    Http::assertSent(function ($request) use ($document, $user) {
        return $request->url() === 'http://127.0.0.1:8001/ask'
            && $request->hasHeader('Authorization', 'Bearer secret-token')
            && $request['document_id'] === $document->id
            && $request['user_id'] === $user->id
            && $request['filename'] === 'contract.pdf'
            && $request['storage_path'] === $document->path
            && $request['question'] === 'What is the total?';
    });
});

test('the python driver stores a failure without the remote error body', function () {
    config([
        'ai.driver' => 'python',
        'ai.python.url' => 'http://127.0.0.1:8001/ask',
    ]);

    Http::fake([
        'http://127.0.0.1:8001/ask' => Http::response('secret upstream failure', 500),
    ]);

    $user = User::factory()->create();
    $document = Document::factory()->for($user)->create();

    $this->actingAs($user)->post(route('questions.store', $document), [
        'body' => 'What is the total?',
    ]);

    $question = $document->questions()->first();

    expect($question->status)->toBe(Question::STATUS_FAILED)
        ->and($question->answer)->toBe(PythonDocumentAnswerer::FAILURE_MESSAGE)
        ->and($question->answer)->not->toContain('secret upstream failure');
});
