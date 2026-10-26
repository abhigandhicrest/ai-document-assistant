<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;

class StoreDocumentRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /**
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $maxKilobytes = max(1, (int) config('ai.max_upload_kb', 20480));

        return [
            'file' => ['required', 'file', 'mimes:pdf', 'extensions:pdf', 'max:'.$maxKilobytes],
        ];
    }
}
