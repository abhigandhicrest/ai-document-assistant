<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreDocumentRequest;
use App\Models\Document;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Illuminate\View\View;
use Symfony\Component\HttpFoundation\StreamedResponse;

class DocumentController extends Controller
{
    public function index(): View
    {
        $documents = $this->userDocuments();

        return view('documents.index', [
            'documents' => $documents,
        ]);
    }

    public function store(StoreDocumentRequest $request): RedirectResponse
    {
        $file = $request->file('file');
        $storedPath = $file->storeAs(
            'documents/'.$request->user()->id,
            (string) Str::uuid().'.pdf',
            'local',
        );

        $document = $request->user()->documents()->create([
            'original_name' => basename($file->getClientOriginalName()),
            'path' => $storedPath,
            'mime_type' => $file->getMimeType() ?: 'application/pdf',
            'size' => $file->getSize(),
            'status' => 'ready',
        ]);

        return redirect()->route('documents.show', $document);
    }

    public function show(Document $document): View
    {
        Gate::authorize('view', $document);

        $document->load(['questions' => fn ($query) => $query->oldest()]);

        return view('documents.show', [
            'document' => $document,
        ]);
    }

    public function download(Document $document): StreamedResponse
    {
        Gate::authorize('download', $document);

        return Storage::disk('local')->download($document->path, $document->original_name);
    }

    public function destroy(Document $document): RedirectResponse
    {
        Gate::authorize('delete', $document);

        Storage::disk('local')->delete($document->path);
        $document->delete();

        return redirect()->route('documents.index');
    }

    /**
     * @return Collection<int, Document>
     */
    private function userDocuments()
    {
        return request()->user()->documents()->latest()->get();
    }
}
