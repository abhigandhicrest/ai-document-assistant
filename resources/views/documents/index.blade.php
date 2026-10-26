<x-layouts::app :title="__('Documents')">
    <div class="flex h-full w-full flex-1 flex-col gap-6">
        <div class="flex flex-col gap-1">
            <flux:heading size="xl">{{ __('Documents') }}</flux:heading>
            <flux:subheading>{{ __('Upload a PDF, then ask questions about it.') }}</flux:subheading>
        </div>

        <form method="POST" action="{{ route('documents.store') }}" enctype="multipart/form-data" class="flex max-w-xl flex-col gap-4">
            @csrf

            <flux:input
                type="file"
                name="file"
                :label="__('PDF document')"
                accept="application/pdf,.pdf"
            />

            <div>
                <flux:button type="submit" variant="primary">{{ __('Upload PDF') }}</flux:button>
            </div>
        </form>

        <div class="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table class="min-w-full text-sm">
                <thead class="border-b border-zinc-200 text-left dark:border-zinc-700">
                    <tr>
                        <th class="px-4 py-3 font-medium">{{ __('Name') }}</th>
                        <th class="px-4 py-3 font-medium">{{ __('Size') }}</th>
                        <th class="px-4 py-3 font-medium">{{ __('Uploaded') }}</th>
                        <th class="px-4 py-3"></th>
                    </tr>
                </thead>
                <tbody>
                    @forelse ($documents as $document)
                        <tr class="border-b border-zinc-200 last:border-0 dark:border-zinc-700">
                            <td class="px-4 py-3">
                                <a href="{{ route('documents.show', $document) }}" class="font-medium underline" wire:navigate>
                                    {{ $document->original_name }}
                                </a>
                            </td>
                            <td class="px-4 py-3">{{ \Illuminate\Support\Number::fileSize($document->size) }}</td>
                            <td class="px-4 py-3">{{ $document->created_at?->timezone(config('app.timezone'))->format('M j, Y g:i A') }}</td>
                            <td class="px-4 py-3 text-end">
                                <a href="{{ route('documents.download', $document) }}" class="underline">{{ __('Download') }}</a>
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="4" class="px-4 py-8 text-center text-zinc-500">{{ __('No documents yet.') }}</td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
</x-layouts::app>
