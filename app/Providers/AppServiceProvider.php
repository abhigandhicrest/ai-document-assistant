<?php

namespace App\Providers;

use App\Services\Ai\DocumentAnswerer;
use App\Services\Ai\PlaceholderDocumentAnswerer;
use App\Services\Ai\PythonDocumentAnswerer;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\ServiceProvider;
use Illuminate\Validation\Rules\Password;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        $this->app->bind(DocumentAnswerer::class, function ($app): DocumentAnswerer {
            return match ($app['config']->get('ai.driver')) {
                'python' => $app->make(PythonDocumentAnswerer::class),
                default => $app->make(PlaceholderDocumentAnswerer::class),
            };
        });
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        $this->configureDefaults();
    }

    /**
     * Configure default behaviors for production-ready applications.
     */
    protected function configureDefaults(): void
    {
        Date::use(CarbonImmutable::class);

        DB::prohibitDestructiveCommands(
            app()->isProduction(),
        );

        Password::defaults(fn (): ?Password => app()->isProduction()
            ? Password::min(12)
                ->mixedCase()
                ->letters()
                ->numbers()
                ->symbols()
                ->uncompromised()
            : null,
        );
    }
}
