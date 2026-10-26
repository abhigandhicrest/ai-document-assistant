<?php

namespace Database\Factories;

use App\Models\Document;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Document>
 */
class DocumentFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'user_id' => User::factory(),
            'original_name' => 'contract.pdf',
            'path' => 'documents/1/example.pdf',
            'mime_type' => 'application/pdf',
            'size' => 1024,
            'status' => 'ready',
        ];
    }
}
