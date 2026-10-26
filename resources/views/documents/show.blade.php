<x-layouts::app :title="$document->original_name">
    <div class="flex h-full w-full flex-1 flex-col gap-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div class="flex flex-col gap-1">
                <flux:heading size="xl">{{ $document->original_name }}</flux:heading>
                <flux:subheading>
                    {{ \Illuminate\Support\Number::fileSize($document->size) }}
                    · {{ __('Uploaded') }} {{ $document->created_at?->timezone(config('app.timezone'))->format('M j, Y g:i A') }}
                </flux:subheading>
            </div>

            <div class="flex items-center gap-2">
                <flux:button :href="route('documents.download', $document)" size="sm">{{ __('Download') }}</flux:button>
                <form method="POST" action="{{ route('documents.destroy', $document) }}" onsubmit="return confirm('Delete this document?')">
                    @csrf
                    @method('DELETE')
                    <flux:button type="submit" variant="danger" size="sm">{{ __('Delete') }}</flux:button>
                </form>
            </div>
        </div>

        <div class="flex flex-col gap-4">
            <flux:heading size="lg">{{ __('Questions') }}</flux:heading>

            <div id="question-list" class="flex flex-col gap-4">
                @forelse ($document->questions as $question)
                    <div class="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
                        <p class="font-medium">{{ $question->body }}</p>
                        <p @class([
                            'mt-2 text-sm',
                            'text-red-600 dark:text-red-400' => $question->status === \App\Models\Question::STATUS_FAILED,
                        ])>{{ $question->answer }}</p>
                    </div>
                @empty
                    <flux:text id="questions-empty">{{ __('No questions yet.') }}</flux:text>
                @endforelse
            </div>
        </div>

        <form id="ask-form" method="POST" action="{{ route('questions.store', $document) }}" class="flex max-w-2xl flex-col gap-4">
            @csrf

            <flux:textarea
                name="body"
                :label="__('Ask a question')"
                :placeholder="__('What does this document say about...')"
                rows="4"
                required
            >{{ old('body') }}</flux:textarea>

            <p id="ask-error" class="hidden text-sm text-red-600 dark:text-red-400"></p>

            <div>
                <flux:button type="submit" variant="primary" data-ask-label="{{ __('Ask') }}" data-asking-label="{{ __('Asking...') }}">{{ __('Ask') }}</flux:button>
            </div>
        </form>
    </div>

    <script>
        document.getElementById('ask-form')?.addEventListener('submit', async (event) => {
            event.preventDefault();

            const form = event.currentTarget;
            const button = form.querySelector('button[type="submit"]');
            const error = document.getElementById('ask-error');
            const field = form.querySelector('[name="body"]');
            const token = form.querySelector('input[name="_token"]')?.value ?? '';

            error.textContent = '';
            error.classList.add('hidden');
            button.disabled = true;
            button.textContent = button.dataset.askingLabel;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-CSRF-TOKEN': token,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({ body: field.value }),
                });

                const payload = await response.json().catch(() => ({}));

                if (response.status === 422) {
                    error.textContent = payload.errors?.body?.[0] ?? payload.message ?? @json(__('The question could not be sent.'));
                    error.classList.remove('hidden');
                    return;
                }

                if (!response.ok || !payload.question) {
                    error.textContent = payload.message ?? @json(__('The question could not be sent.'));
                    error.classList.remove('hidden');
                    return;
                }

                document.getElementById('questions-empty')?.remove();

                const item = document.createElement('div');
                item.className = 'rounded-xl border border-zinc-200 p-4 dark:border-zinc-700';

                const body = document.createElement('p');
                body.className = 'font-medium';
                body.textContent = payload.question.body;

                const answer = document.createElement('p');
                answer.className = payload.question.status === 'failed'
                    ? 'mt-2 text-sm text-red-600 dark:text-red-400'
                    : 'mt-2 text-sm';
                answer.textContent = payload.question.answer ?? '';

                item.append(body, answer);
                document.getElementById('question-list').append(item);
                field.value = '';
                item.scrollIntoView({ block: 'nearest' });
            } catch {
                error.textContent = @json(__('The question could not be sent.'));
                error.classList.remove('hidden');
            } finally {
                button.disabled = false;
                button.textContent = button.dataset.askLabel;
            }
        });
    </script>
</x-layouts::app>
