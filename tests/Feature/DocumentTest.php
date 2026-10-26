<?php

use App\Models\Document;
use App\Models\User;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;

test('guests are redirected from document pages', function () {
    $this->get(route('documents.index'))->assertRedirect(route('login'));
    $this->post(route('documents.store'))->assertRedirect(route('login'));
});

test('a user can upload a pdf', function () {
    Storage::fake('local');

    $user = User::factory()->create();
    $file = UploadedFile::fake()->create('contract.pdf', 100, 'application/pdf');

    $response = $this->actingAs($user)->post(route('documents.store'), [
        'file' => $file,
    ]);

    $document = Document::query()->first();

    expect($document)->not->toBeNull();

    $response->assertRedirect(route('documents.show', $document));

    Storage::disk('local')->assertExists($document->path);

    expect($document->user_id)->toBe($user->id)
        ->and($document->original_name)->toBe('contract.pdf')
        ->and($document->status)->toBe('ready');

    $this->actingAs($user)
        ->get(route('documents.index'))
        ->assertOk()
        ->assertSee('contract.pdf');
});

test('a non pdf is rejected', function () {
    Storage::fake('local');

    $user = User::factory()->create();
    $file = UploadedFile::fake()->create('notes.txt', 10, 'text/plain');

    $this->actingAs($user)
        ->post(route('documents.store'), [
            'file' => $file,
        ])
        ->assertSessionHasErrors('file');

    expect(Document::query()->count())->toBe(0);
});

test('a user cannot view or download another users document', function () {
    Storage::fake('local');

    $owner = User::factory()->create();
    $other = User::factory()->create();
    $path = 'documents/'.$owner->id.'/secret.pdf';

    Storage::disk('local')->put($path, '%PDF-1.4');

    $document = Document::factory()->for($owner)->create([
        'path' => $path,
        'original_name' => 'secret.pdf',
    ]);

    $this->actingAs($other)->get(route('documents.show', $document))->assertForbidden();
    $this->actingAs($other)->get(route('documents.download', $document))->assertForbidden();

    $this->actingAs($owner)
        ->get(route('documents.download', $document))
        ->assertOk();
});
