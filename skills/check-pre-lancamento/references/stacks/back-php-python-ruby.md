<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Back-end PHP, Python e Ruby · onde olhar e como corrigir

Referência por stack para o agente que audita: onde o problema costuma estar, o que o `scan.py` sinaliza e a correção certa em cada framework. O critério de FALHA/ATENÇÃO/OK/N/A continua no `checks.md`.

**Stacks:** [Laravel](#laravel) · [Symfony](#symfony) · [Django e DRF](#django-e-drf) · [Flask](#flask) · [FastAPI](#fastapi) · [Rails](#rails)

Sinais genéricos, válidos em todas as stacks e não repetidos abaixo: `generic_assignment`, `db_url_password` (C01) · `arquivo_sensivel_rastreado`, `segredo_no_historico` (C02) · `rota_sem_auth_aparente` (C06) · `admin_sem_checagem_de_papel`, `identidade_do_cliente`, `cors_aberto` (C07) · `sem_rate_limit`, `ia_sem_rate_limit` (C11) · `rota_sem_validacao_aparente` (C14) · `sem_security_headers`, `headers_faltando` (C18) · `url_http` (C19) · `auditoria_nao_executada` (C20).

Versões de referência (out/2026): Laravel 12 e 13 · Django 5.2 LTS e 6.x · Rails 8.x. Versão sem correção de segurança entra em C20.

## Laravel

Vale para Laravel 11, 12 e 13 (esqueleto enxuto, com `bootstrap/app.php` no lugar do `Kernel.php`). App que veio do 10 pode ainda ter `app/Http/Kernel.php` e `RouteServiceProvider`: leia os dois.

**Onde olhar primeiro**
- `routes/web.php`, `routes/api.php` e arquivos incluídos: grupos `Route::middleware(['auth:sanctum'])->group(...)`, `->middleware('auth')`, `throttle:*`, `->can(...)`. Se der para rodar, `php artisan route:list -v` mostra o middleware de cada rota.
- `bootstrap/app.php`: `withRouting(... health: '/up')` e, em `withMiddleware`, `statefulApi()`, `throttleApi()`, `trustProxies(at: ...)`, exclusões de CSRF (`validateCsrfTokens(except: ...)`; no 13, `preventRequestForgery(except: ...)`) e `encryptCookies(except: ...)`.
- `app/Http/Controllers/**`: `$request->all()`/`input()` indo para o model, `Model::find($id)` sem dono, `return Model::all()`, `getClientOriginalName()`.
- `app/Http/Requests/**`: `authorize()` que só faz `return true`; `rules()` com campo sensível.
- `app/Models/**`: `$fillable`/`$guarded` (no 13, `#[Fillable]`/`#[Hidden]`), `$hidden`, `casts()` (`'password' => 'hashed'`, `encrypted`).
- `app/Policies/**`, `Gate::define`/`Gate::before` no `AppServiceProvider` e providers de painel (Telescope, Horizon, Pulse, Nova, Filament).
- `resources/views/**/*.blade.php` (`{!! !!}`) e `resources/js/**` se for Inertia/Livewire.
- `config/session.php`, `config/cors.php` (só existe se publicado; senão vale o padrão do framework), `config/sanctum.php` (`expiration`, `stateful`), `config/filesystems.php`, `config/services.php`, `config/logging.php`.
- `.env` de produção (peça os valores, não o arquivo): `APP_ENV`, `APP_DEBUG`, `APP_URL`, `SESSION_SECURE_COOKIE`, `SESSION_SAME_SITE`, `SESSION_DOMAIN`, `MAIL_MAILER`, `LOG_LEVEL`. `VITE_*` e `MIX_*` vão para o bundle.
- `composer.json` (`require` × `require-dev`: Telescope, Debugbar, Horizon, Pulse, Filament, Nova) e `composer.lock` versionado.
- Servidor web: document root em `public/` (raiz do projeto exposta = `.env` público) e bloqueio de dotfiles.

**Sinais do scanner**
- `laravel_rota_sem_auth` → C06 · `laravel_admin_sem_auth` → C07 · `laravel_request_all`, `laravel_unguard`, `laravel_guarded_vazio` → C08
- `laravel_cookie_inseguro`, `laravel_secure_default_false`, `csrf_desligado` → C09 · `laravel_bcrypt_rounds_baixo`, `md5_php_sql` → C10
- `laravel_raw_interpolado`, `php_query_superglobal` → C13 · `blade_sem_escape`, `desserializacao_insegura` (`unserialize($_...)`) → C14
- `laravel_debug_producao`, `debugbar_em_producao`, `php_debug_leftover`, `directory_listing`, `painel_de_banco`, `arquivo_sensivel_publico` → C15
- `nome_original_framework` → C16 · `laravel_user_sem_hidden`, `laravel_all_sem_paginacao` → C17 · `tls_verificacao_desligada` (cURL) → C19
- `public_env_secret` (`VITE_`/`MIX_` com segredo) → C01 · `vulnerabilidades_altas` (`composer audit`) → C20 · `laravel_mail_log` → P06
- Limites:
  - O parser de rotas acompanha as chaves dos grupos. Ele reconhece:
    - `->middleware('auth…')` na linha da rota;
    - grupo `middleware([...])->group(` e `Route::group(['middleware' => 'auth'], …)`;
    - middleware encadeado até 3 linhas acima do `->group(`.

    `HasMiddleware` no controller, `#[Middleware('auth')]` (13) e middleware anexado ao grupo `api` no `bootstrap/app.php` ainda geram falso positivo. Confirme com `route:list -v`.
  - Só cobra rota de escrita (`post`, `put`, `patch`, `delete`, `any`, `resource`). `Route::get` fora de grupo com auth que devolve dado privado passa calado.
  - `laravel_user_sem_hidden` aceita `$hidden` e `#[Hidden([...])]`. `debugbar_em_producao` conhece `barryvdh/laravel-debugbar` e `fruitcake/laravel-debugbar`.
  - `csrf_desligado` pega `$except = ['*']` (10) e `validateCsrfTokens(except: ['*'])` / `preventRequestForgery(except: ['*'])` (11+). Exclusão de rotas específicas não dispara: leia o `bootstrap/app.php`.
  - `SESSION_SAME_SITE=none` ou `SESSION_SECURE_COOKIE=false` no `.env` não passam pelas regras de C09.

**Correções por checagem**
- **C01 Esconder API Keys** — segredo no `.env` (fora do Git), lido em `config/services.php` com `env()` e usado no código como `config('services.openai.key')`; com `config:cache`, `env()` fora de `config/` devolve `null`. Nunca segredo como valor padrão de `env('X', '...')` nem com prefixo `VITE_`/`MIX_`.
- **C02 Limpar secrets do Git** — `.env` vazado leva junto o `APP_KEY`: gere outro (`php artisan key:generate`) e troque banco, mail e APIs. Com dado em cast `encrypted`, re-cifre antes de descartar a chave velha e não deixe a chave vazada em `APP_PREVIOUS_KEYS` além da migração: ela segue aceita para decifrar cookie forjado.
- **C05 Criptografia de dados** — cast `encrypted` (AES-256 com o `APP_KEY`) em coluna `text`; para buscar por CPF, guarde também um HMAC:
  ```php
  protected function casts(): array
  {
      return ['cpf' => 'encrypted', 'documento' => 'encrypted'];
  }
  // busca: coluna cpf_hash = hash_hmac('sha256', $cpf, config('app.hmac_key'))
  ```
- **C06 Auth server-side** — rota privada sempre dentro de grupo com `auth` (sessão) ou `auth:sanctum` (SPA/token):
  ```php
  Route::middleware(['auth:sanctum', 'throttle:api'])->group(function () {
      Route::apiResource('documentos', DocumentoController::class);
  });
  ```
  Token do Sanctum não expira por padrão (`expiration => null`): defina `expiration`, agende `sanctum:prune-expired` e revogue no logout (`currentAccessToken()->delete()`). SPA no mesmo domínio usa o modo cookie (`statefulApi()` + `SANCTUM_STATEFUL_DOMAINS`), não token guardado no navegador. Webhook (Stripe, Asaas, Mercado Pago, Efí) fica fora do grupo `web` e verifica a assinatura.
- **C07 Restringir acessos** — busque pelo dono (`$request->user()->documentos()->findOrFail($id)`) ou autorize com Policy: `Gate::authorize('update', $documento)`, `->can('update', 'documento')` na rota ou `#[Authorize]` no método (13). No 11+ o `Controller` base vem vazio: `$this->authorize()` só existe com o trait `AuthorizesRequests`. Rotas aninhadas: `->scopeBindings()`. `FormRequest::authorize()` com `return true` não autoriza nada.
  - Painéis: o Filament exige `FilamentUser::canAccessPanel()` fora do ambiente local; Nova, Horizon, Telescope e Pulse liberam pelos gates `viewNova`, `viewHorizon`, `viewTelescope`, `viewPulse`. Confira quem passa em cada um.
  - CORS: o padrão é `allowed_origins => ['*']` em `api/*`, com `supports_credentials => false`. Com cookie (Sanctum SPA), publique (`php artisan config:publish cors`) e troque por lista: `'allowed_origins' => [env('FRONTEND_URL')]`, `'supports_credentials' => true`.
- **C08 Bloquear Mass Assignment** — o model recebe só o que passou na validação, e só campo editável tem regra:
  ```php
  public function update(UpdatePerfilRequest $request)
  {
      $request->user()->update($request->validated()); // ou $request->safe()->only(['name', 'bio'])
  }
  ```
  `$fillable` (ou `#[Fillable]`) explícito, sem `role`, `is_admin`, `plan`, `credits`, `user_id`; nunca `$guarded = []` nem `Model::unguard()`; `forceFill` só com dado do servidor. Em dev, `Model::preventSilentlyDiscardingAttributes(! $this->app->isProduction())` no `AppServiceProvider` mostra campo descartado. Livewire 3: propriedade pública vem do navegador; trave id e papel com `#[Locked]`.
- **C09 Proteger cookies** — em `config/session.php`, `'secure' => env('SESSION_SECURE_COOKIE')` vem `null`: ponha `SESSION_SECURE_COOKIE=true` em produção. Mantenha `http_only` `true` e `same_site` `lax` (`none` só com motivo e CSRF ativo); o helper `cookie()` herda `secure` e `same_site` da sessão. `SESSION_DOMAIN=.dominio` expõe o cookie a todo subdomínio: só para Sanctum SPA em subdomínio. CSRF: não exclua rota de formulário; no 13 o middleware é `PreventRequestForgery` (confere `Sec-Fetch-Site` e cai no token).
- **C10 Hash nas senhas** — `Hash::make()` ou cast `'password' => 'hashed'` (bcrypt com `BCRYPT_ROUNDS` padrão 12; Argon2id com `'driver' => 'argon2id'` no `config/hashing.php`, publicado com `php artisan config:publish hashing`). `BCRYPT_ROUNDS=4` no `phpunit.xml` é só teste. Política: `Password::defaults(fn () => Password::min(8)->uncompromised())` no `AppServiceProvider` e `Password::defaults()` nas regras de cadastro.
- **C11 Rate limit** — no 11+ o grupo `api` vem sem `throttle`: chame `$middleware->throttleApi()` e defina os limitadores no `AppServiceProvider::boot()`:
  ```php
  RateLimiter::for('api', fn (Request $r) => Limit::perMinute(60)->by($r->user()?->id ?: $r->ip()));
  RateLimiter::for('ia', fn (Request $r) => Limit::perMinute(10)->by($r->user()?->id ?: $r->ip()));
  // rotas de IA, e-mail, SMS e reset de senha: ->middleware('throttle:ia')
  ```
  Breeze e Fortify limitam o login; controller de login próprio não. Atrás de proxy/Cloudflare, `trustProxies(at: ...)`, senão `$request->ip()` é o IP do proxy. Várias instâncias: cache compartilhado (`throttleWithRedis()` ou `'limiter' => 'redis'` no `config/cache.php`).
- **C12 Bot protection** — Turnstile ou reCAPTCHA no cadastro, login, reset e contato, com o token validado no servidor (regra de validação que chama o `siteverify` via `Http::asForm()->post(...)`). Widget sem essa regra é enfeite.
- **C13 Queries parametrizadas** — bindings sempre; coluna e ordenação vêm de allowlist (o PDO não parametriza nome de coluna):
  ```php
  DB::select('select id, name from users where email = ?', [$email]);
  $q->whereRaw('total > ?', [$min]);
  $sort = in_array($request->sort, ['created_at', 'name'], true) ? $request->sort : 'created_at';
  $q->orderBy($sort);
  ```
  `DB::raw("... $x")`, `whereRaw("... {$x}")` e `DB::statement` concatenado são FALHA.
- **C14 Validação dos inputs** — toda escrita passa por FormRequest ou `$request->validate()` com tipo e tamanho (`'title' => ['required', 'string', 'max:120']`) e arrays com chaves fixas (`'meta' => 'array:cor,tamanho'`). Blade: `{{ }}` escapa, `{!! !!}` não; use só com HTML sanitizado (`symfony/html-sanitizer` ou HTMLPurifier). `{!! Str::markdown($texto) !!}` deixa HTML cru passar: `Str::markdown($texto, ['html_input' => 'strip', 'allow_unsafe_links' => false])`. `unserialize()` de input vira `json_decode()`.
- **C15 Evitar vazamento de conteúdo** — produção com `APP_ENV=production` e `APP_DEBUG=false` (com debug, a página de erro mostra stack, queries e configuração); `php artisan about` confirma. Telescope: `composer require laravel/telescope --dev` e registro só em `local` (seção "Local Only Installation" da doc) ou gate `viewTelescope` fechado. Debugbar só em `require-dev`. Tire `dd()`, `dump()` e `phpinfo()`. Nginx com `root .../public` e `location ~ /\.(?!well-known).* { deny all; }`. App antigo com Ignition < 2.5.2 e debug ligado tem RCE (CVE-2021-3129).
- **C16 Restringir uploads** — tipo lido do conteúdo, tamanho e nome gerado pelo servidor:
  ```php
  $request->validate(['doc' => ['required', File::types(['pdf', 'jpg', 'png'])->max('5mb')]]);
  $path = $request->file('doc')->store('docs/'.$request->user()->id, 'local'); // nome aleatório
  ```
  `File::types` e `mimes` leem o conteúdo. A regra `image` recusa SVG no 12+; no 11 aceita, então use `mimes`. Disco `public` + `storage:link` = qualquer um com a URL baixa: documento privado fica no disco `local` (raiz `storage/app/private` no 11+) e sai por rota com auth + Policy (`Storage::download`) ou por `Storage::temporaryUrl()` (S3; no `local`, com `'serve' => true`). `getClientOriginalName()` nunca entra no caminho. Limite também em `upload_max_filesize`, `post_max_size` e `client_max_body_size`.
- **C17 Limitar respostas de API** — `$hidden` (ou `#[Hidden]`) com `password`, `remember_token`, `two_factor_secret`, `two_factor_recovery_codes` e ids de gateway; melhor ainda, API Resource com os campos escolhidos. Listagem com `paginate()`/`cursorPaginate()` e teto (`min($request->integer('per_page', 20), 100)`). Inertia: o que vai em `HandleInertiaRequests::share()` e nas props sai no HTML da página.
- **C18 Security headers** — o Laravel não manda CSP, `X-Frame-Options` nem nosniff. No `handle()` de um middleware global (`$middleware->append(SecurityHeaders::class)`):
  ```php
  $response = $next($request);
  $response->headers->add([
      'X-Frame-Options' => 'DENY',
      'X-Content-Type-Options' => 'nosniff',
      'Referrer-Policy' => 'strict-origin-when-cross-origin',
      'Content-Security-Policy' => "default-src 'self'; frame-ancestors 'none'",
  ]);
  return $response;
  ```
  CSP com nonce: `spatie/laravel-csp` + `Vite::useCspNonce()`. `expose_php = Off` no `php.ini` tira o `X-Powered-By`.
- **C19 Forçar HTTPS** — redirect e HSTS no nginx ou na Cloudflare. No app: `URL::forceHttps(app()->isProduction())` (11.x em diante; antes, `URL::forceScheme('https')`), `APP_URL` com `https://` e `trustProxies(at: ...)` para o Laravel enxergar o `X-Forwarded-Proto`. Fora: `Http::withoutVerifying()`, `'verify' => false` no Guzzle e `CURLOPT_SSL_VERIFYPEER => false`.
- **C20 Scan de dependências** — `composer audit --locked --no-dev` com `composer.lock` versionado; Dependabot `package-ecosystem: "composer"`; front no mesmo repo, `npm audit` também. O Laravel 11 está sem correção de segurança desde 12/03/2026 e o 12 recebe só segurança até 24/02/2027: versão ≤ 11 em produção é ATENÇÃO ALTO (FALHA se o audit acusar).
- **P05 e P06 (prontidão)** — o `/up` só prova que o app subiu; para checar banco e fila, trate o evento `DiagnosingHealth`. `MAIL_MAILER=log` em produção não manda e-mail nenhum.

## Symfony

**Onde olhar primeiro**
- `config/packages/security.yaml` (`firewalls`, `access_control`, `password_hashers`, `login_throttling`) e `src/Security/Voter/**`.
- Controllers com `#[Route]` e `#[IsGranted]`; DTOs com `#[MapRequestPayload]`; Forms.
- `config/packages/framework.yaml` (sessão, CSRF, rate limiter), `nelmio_cors.yaml`, `nelmio_security.yaml`.
- `.env`, `.env.local`, `.env.prod.local` (`APP_ENV`, `APP_DEBUG`, `APP_SECRET`, `DATABASE_URL`), `config/secrets/` e `config/bundles.php` (WebProfilerBundle só em `dev`/`test`).
- Templates Twig: `|raw`.

**Sinais do scanner**
- Não há regra própria e as rotas `#[Route]` não entram na lista: C06 e C07 saem só da leitura. Valem `php_query_superglobal` (C13), `desserializacao_insegura` (C14), `directory_listing` (C15), `tls_verificacao_desligada` (C19) e `vulnerabilidades_altas` via `composer audit` (C20).
- Limites: a validação conta como embutida (`sem_lib_de_validacao` não dispara). `login_throttling` e o RateLimiter do Symfony não contam em C11 (`sem_rate_limit` pode ser falso).

**Correções por checagem**
- **C06 Auth server-side** — negar por padrão no `access_control` (o primeiro match vence, então a ordem importa) e `#[IsGranted('ROLE_USER')]` no controller:
  ```yaml
  access_control:
      - { path: ^/login, roles: PUBLIC_ACCESS }
      - { path: ^/admin, roles: ROLE_ADMIN }
      - { path: ^/, roles: ROLE_USER }
  ```
- **C07 Restringir acessos** — acesso a objeto por Voter: `$this->denyAccessUnlessGranted('EDIT', $documento)` ou `#[IsGranted('EDIT', 'documento')]`; consulta de repositório sempre com o dono.
- **C08 Bloquear Mass Assignment** — Form com campos explícitos (`allow_extra_fields` é `false` por padrão) ou DTO com `#[MapRequestPayload]` (6.3+) copiado campo a campo para a entidade; nunca desserializar o JSON direto na entidade.
- **C09 Proteger cookies** — `framework.session` com `cookie_secure: auto`, `cookie_httponly: true` e `cookie_samesite: lax`; CSRF ligado nos forms e no login (`enable_csrf: true` no `form_login`).
- **C10 Hash nas senhas** — `password_hashers` com `'auto'` para `PasswordAuthenticatedUserInterface` e `UserPasswordHasherInterface::hashPassword()`.
- **C11 Rate limit** — `login_throttling: { max_attempts: 5 }` no firewall (precisa de `symfony/rate-limiter`); demais rotas sensíveis com limitadores do `framework.rate_limiter`.
- **C13 Queries parametrizadas** — DQL `->where('u.email = :e')->setParameter('e', $email)`, DBAL `executeQuery('select ... where id = ?', [$id])`; concatenar em `createQuery` ou `where()` é FALHA.
- **C14 Validação dos inputs** — constraints no DTO (`#[Assert\NotBlank]`, `#[Assert\Length(max: 120)]`); Twig escapa, e `|raw` só depois de `|sanitize_html` (componente `symfony/html-sanitizer`).
- **C15 Evitar vazamento de conteúdo** — `APP_ENV=prod` e `APP_DEBUG=0`; WebProfilerBundle só em `dev` (o `/_profiler` mostra requisições, variáveis e queries); `APP_SECRET` no cofre (`php bin/console secrets:set`) ou em variável de ambiente.
- **C18 Security headers** — `nelmio/security-bundle` (CSP, nosniff, clickjacking, Referrer-Policy) ou listener de resposta; CORS com `nelmio/cors-bundle` e lista de origens.
- **C20 Scan de dependências** — `composer audit` ou `symfony check:security`.

## Django e DRF

**Onde olhar primeiro**
- `settings.py` ou `settings/*.py` (o de produção): `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_*`, `SESSION_*`, `CSRF_*`, `MIDDLEWARE`, `REST_FRAMEWORK`, `PASSWORD_HASHERS`, `CORS_*`, `STORAGES`, `LOGGING`.
- `urls.py` (`admin.site.urls` em `/admin/`, `router.register`), `views.py` e viewsets (`get_queryset`, `permission_classes`, `@csrf_exempt`, `request.data` direto no model).
- `serializers.py` (`fields`, `read_only_fields`), `forms.py`, `models.py` (`FileField`, campos sensíveis).
- Templates: `|safe`, `mark_safe`, `{% autoescape off %}`. Dependências: `requirements*.txt`, `pyproject.toml`, `uv.lock`/`poetry.lock`.
- `python manage.py check --deploy` com o settings de produção aponta boa parte dos ajustes de C09, C15, C18 e C19.

**Sinais do scanner**
- `django_secret` → C01 · `drf_sem_permissao_padrao`, `drf_allow_any`, `jwt_decode_sem_verificar` → C06 · `django_fields_all`, `python_kwargs_do_request` → C08
- `django_cookie_inseguro`, `csrf_desligado` (`@csrf_exempt`) → C09 · `hash_rapido_py`, `coluna_senha_sem_hash` → C10 · `py_execute_fstring`, `py_execute_format`, `orm_raw_fstring` → C13
- `django_autoescape_off`, `jinja_safe` (`mark_safe`, `|safe`), `ssrf_url_do_usuario`, `path_traversal`, `open_redirect`, `desserializacao_insegura`, `py_shell`, `shell_true` → C14
- `django_debug`, `django_allowed_hosts_aberto`, `traceback_na_resposta`, `log_sensivel_py` → C15 · `django_ssl_redirect_off`, `py_verify_false` → C19 · `vulnerabilidades_python` (pip-audit) → C20
- Limites:
  - `LoginRequiredMiddleware` (5.1+) não conta como auth: com ele, view sem decorator aparece como `rota_sem_auth_aparente`. E `request.user` no arquivo já conta como auth, mesmo sem checar `is_authenticated`.
  - `X-Frame-Options: DENY` (`XFrameOptionsMiddleware`) e `Referrer-Policy: same-origin` (`SecurityMiddleware`) vêm por padrão: `headers_faltando` pode listá-los à toa. Confira o `MIDDLEWARE`.
  - `django-axes` não conta em C11. PyJWT `jwt.decode(token, key, algorithms=[...])` verifica a assinatura: `jwt_decode_sem_verificar` só é FALHA com `options={"verify_signature": False}`.

**Correções por checagem**
- **C01 Esconder API Keys** — `SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]` (quebra no boot se faltar); chave `django-insecure-` em produção é FALHA. Na rotação, a antiga vai em `SECRET_KEY_FALLBACKS` (4.1+) só durante a transição; se vazou, sem fallback, porque ela assina sessão e link de reset.
- **C06 Auth server-side** — no DRF o padrão é `AllowAny`, então toda view nova nasce pública. Defina o padrão e libere a exceção com `permission_classes = [AllowAny]` explícito:
  ```python
  REST_FRAMEWORK = {
      "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
      "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle",
                                   "rest_framework.throttling.UserRateThrottle"],
      "DEFAULT_THROTTLE_RATES": {"anon": "30/min", "user": "120/min"},
      "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
      "PAGE_SIZE": 20,
  }
  ```
  Views do Django: no 5.1+, `django.contrib.auth.middleware.LoginRequiredMiddleware` e `@login_not_required` nas públicas; antes, `@login_required`/`LoginRequiredMixin` em cada uma. `@csrf_exempt` só em webhook com assinatura verificada.
- **C07 Restringir acessos** — filtre pelo dono em `get_queryset()`; `has_object_permission` não roda na listagem:
  ```python
  class DocumentoViewSet(viewsets.ModelViewSet):
      serializer_class = DocumentoSerializer
      def get_queryset(self):
          return Documento.objects.filter(owner=self.request.user)
      def perform_create(self, serializer):
          serializer.save(owner=self.request.user)
  ```
  Admin: só `is_staff` entra; mude o caminho `/admin/`, use 2FA e dê `is_superuser` só a quem precisa. CORS (`django-cors-headers`): `CORS_ALLOWED_ORIGINS = ["https://meuapp.com.br"]`; `CORS_ALLOW_ALL_ORIGINS = True` com `CORS_ALLOW_CREDENTIALS = True` é FALHA.
- **C08 Bloquear Mass Assignment** — `fields = ["name", "bio"]` e `read_only_fields = ["owner", "role", "plan"]` no serializer e no ModelForm; `Model.objects.create(**request.data)` é FALHA; o dono vem de `perform_create`, nunca do body.
- **C09 Proteger cookies** — `SESSION_COOKIE_SECURE = True` e `CSRF_COOKIE_SECURE = True` (o padrão é `False`); `SESSION_COOKIE_HTTPONLY` e `SESSION_COOKIE_SAMESITE = "Lax"` já são padrão. `CSRF_TRUSTED_ORIGINS` com esquema (`"https://meuapp.com.br"`). DRF com `SessionAuthentication` mantém o CSRF; com JWT (simplejwt), access token curto.
- **C10 Hash nas senhas** — o padrão (PBKDF2) é OK; Argon2: `pip install "django[argon2]"` e `"django.contrib.auth.hashers.Argon2PasswordHasher"` primeiro em `PASSWORD_HASHERS`. Senha só por `create_user`, `set_password` ou `make_password`. `AUTH_PASSWORD_VALIDATORS` ligados (o `MinimumLengthValidator` padrão pede 8).
- **C11 Rate limit** — o throttling do DRF (acima) usa o cache: com vários workers, cache compartilhado (Redis), não `LocMemCache`. Views comuns: `django-ratelimit` (`@ratelimit(key="ip", rate="5/m", block=True)`); login: `django-axes`. Atrás de proxy, o `REMOTE_ADDR` é o do proxy: ajuste a chave de IP.
- **C13 Queries parametrizadas** — o ORM é parametrizado. SQL cru com parâmetro, sem aspas em volta do `%s`:
  ```python
  User.objects.raw("SELECT id, email FROM app_user WHERE email = %s", [email])
  cursor.execute("UPDATE app_doc SET title = %s WHERE id = %s", [title, pk])
  ```
  `.raw(f"...")`, `.extra()`/`RawSQL` com f-string e `order_by(request.GET["sort"])` sem allowlist são FALHA.
- **C14 Validação dos inputs** — forms e serializers com `max_length`, tipos e validators. Templates escapam: `mark_safe`/`|safe` só com HTML limpo (`nh3.clean(html)`; o `bleach` foi descontinuado) e `format_html()` para montar HTML. `pickle.loads`/`yaml.load` de input viram JSON ou `yaml.safe_load`.
- **C15 Evitar vazamento de conteúdo** — `DEBUG = os.environ.get("DJANGO_DEBUG") == "1"`; `ALLOWED_HOSTS` explícito; DRF em produção só com `JSONRenderer` (a API navegável expõe tudo); Swagger (`drf-spectacular`) atrás de auth; log sem senha, token e CPF.
- **C16 Restringir uploads** — tamanho, tipo real e nome definidos no servidor:
  ```python
  def validar_arquivo(f):
      if f.size > 5 * 1024 * 1024:
          raise ValidationError("Arquivo grande demais")
      if magic.from_buffer(f.read(2048), mime=True) not in {"application/pdf", "image/png", "image/jpeg"}:
          raise ValidationError("Tipo não permitido")
      f.seek(0)
  ```
  `FILE_UPLOAD_MAX_MEMORY_SIZE` não é limite (só decide memória × disco) e `DATA_UPLOAD_MAX_MEMORY_SIZE` não conta arquivo. `upload_to` com `uuid4()`. `MEDIA_URL` servido pelo nginx é público: arquivo privado sai por view com permissão (`FileResponse` ou `X-Accel-Redirect`) ou de S3 privado com URL assinada (django-storages).
- **C17 Limitar respostas de API** — serializer de saída com campos explícitos; paginação global (acima) e `max_page_size` na classe de paginação se ela aceitar `page_size_query_param`.
- **C18 Security headers** — `SecurityMiddleware` e `XFrameOptionsMiddleware` já mandam nosniff, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` e COOP. CSP nativa no Django 6.0+ (antes, `django-csp`):
  ```python
  from django.utils.csp import CSP
  MIDDLEWARE += ["django.middleware.csp.ContentSecurityPolicyMiddleware"]
  SECURE_CSP = {"default-src": [CSP.SELF], "script-src": [CSP.SELF, CSP.NONCE], "frame-ancestors": [CSP.NONE]}
  # nonce: context processor django.template.context_processors.csp e nonce="{{ csp_nonce }}" no <script>
  ```
  Com script de terceiro, comece por `SECURE_CSP_REPORT_ONLY`.
- **C19 Forçar HTTPS** — `SECURE_SSL_REDIRECT = True` (ou redirect no proxy), `SECURE_HSTS_SECONDS = 31536000` e `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`. Atrás de proxy, `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` só se o proxy sempre sobrescreve esse header. Postgres: `"OPTIONS": {"sslmode": "require"}`.
- **C20 Scan de dependências** — `pip-audit -r requirements.txt` (com uv ou poetry, exporte o lock antes); Dependabot `pip`. O 4.2 e o 5.1 estão sem correção de segurança: use 5.2 LTS (até abr/2028) ou 6.x.

## Flask

**Onde olhar primeiro**
- `app.py` ou `create_app()`: `app.run(debug=...)`, `SECRET_KEY`, `app.config.from_*` e extensões (`flask_login`, `flask_wtf`, `flask_limiter`, `flask_talisman`, `flask_cors`).
- Blueprints e `@app.route`: `@login_required`, `request.args/form/json/files`, `render_template_string`, `send_file`.
- Comando de produção (Procfile, Dockerfile): gunicorn ou uwsgi, nunca o servidor de desenvolvimento.

**Sinais do scanner**
- `flask_debug` → C15 (CRÍTICO) · `render_template_string`, `jinja_safe` (`Markup(`), `jinja_sem_autoescape`, `path_traversal` (`send_file`), `ssrf_url_do_usuario`, `open_redirect`, `py_shell`, `shell_true` → C14
- `python_kwargs_do_request` → C08 · `py_execute_fstring`, `py_execute_format`, `orm_raw_fstring` → C13 · `erro_inteiro_na_resposta`, `mensagem_interna`, `traceback_na_resposta` → C15
- `objeto_usuario_inteiro` (`jsonify(user)`), `limit_sem_teto` → C17 · `hash_rapido_py` → C10 · `py_verify_false` → C19

**Correções por checagem**
- **C06 Auth server-side** — `@login_required` (Flask-Login) em toda view privada, ou `@bp.before_request` que devolve 401 sem `current_user.is_authenticated`. Token: `jwt.decode(token, key, algorithms=["HS256"])` (PyJWT).
- **C09 Proteger cookies** — a sessão do Flask é cookie assinado, não cifrado: o usuário lê o conteúdo, então nada sensível em `session`. `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE="Lax"` (o padrão não define) e `REMEMBER_COOKIE_SECURE=True`. CSRF: `CSRFProtect(app)` (Flask-WTF).
- **C11 Rate limit** — Flask-Limiter com storage compartilhado e `ProxyFix` para o IP real atrás de proxy:
  ```python
  app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
  limiter = Limiter(get_remote_address, app=app, default_limits=["200/hour"], storage_uri="redis://redis:6379")

  @app.post("/login")
  @limiter.limit("5/minute")
  def login(): ...
  ```
- **C13 Queries parametrizadas** — SQLAlchemy: `session.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})`; f-string dentro de `text()` é FALHA.
- **C14 Validação dos inputs** — `render_template_string` com input é SSTI (executa código): use `render_template` com arquivo. `Markup()`/`|safe` só com HTML sanitizado (`nh3`). Valide a entrada com pydantic, marshmallow ou Flask-WTF.
- **C15 Evitar vazamento de conteúdo** — nunca `debug=True` ou `FLASK_DEBUG=1` fora da máquina local: o debugger do Werkzeug executa código. Rode com gunicorn e use `@app.errorhandler(500)` com mensagem neutra e detalhe só no log.
- **C16 Restringir uploads** — `MAX_CONTENT_LENGTH = 5 * 1024 * 1024`. `secure_filename()` não basta: nome `uuid4().hex` + extensão da allowlist, tipo pelo conteúdo (`python-magic`) e download por `send_from_directory`, nunca `send_file` com caminho do usuário.
- **C18 Security headers** — `flask-talisman` manda CSP, `X-Frame-Options`, nosniff e Referrer-Policy: `Talisman(app, content_security_policy={"default-src": "'self'"})`.
- **C19 Forçar HTTPS** — o Talisman também força HTTPS e manda HSTS (`force_https=True` é o padrão); atrás de proxy, `ProxyFix` com `x_proto=1` para ele enxergar o `https`.

## FastAPI

**Onde olhar primeiro**
- `main.py`: `FastAPI(docs_url=..., redoc_url=..., openapi_url=...)`, `CORSMiddleware`, `TrustedHostMiddleware`, `HTTPSRedirectMiddleware`, `include_router(..., dependencies=...)`.
- `routers/**` (`APIRouter(dependencies=[...])`, handlers com `Depends(get_current_user)`) e `deps.py`/`security.py` (JWT e hash de senha).
- Schemas Pydantic de entrada e saída, `response_model`, parâmetros `limit`/`offset`, `UploadFile`.
- Comando do uvicorn ou gunicorn (`--proxy-headers`, `--forwarded-allow-ips`).

**Sinais do scanner**
- `fastapi_docs_publico` → C15 · `limit_sem_teto_fastapi` → C17 · `jwt_decode_sem_verificar` → C06 · `cors_aberto` (`allow_origins=["*"]`) → C07
- `python_kwargs_do_request` → C08 · `py_execute_fstring`, `py_execute_format`, `orm_raw_fstring` → C13 · `hash_rapido_py` → C10 · `py_verify_false` → C19
- Limites: o scanner trata rota FastAPI como validada pelos type hints, mas body `dict`, `Any` ou `await request.json()` passa sem validação de fato. Dependência de auth no `APIRouter` ou no `include_router` de outro arquivo gera `rota_sem_auth_aparente` falso.

**Correções por checagem**
- **C06 Auth server-side** — dependência no router inteiro e, quando o handler precisa do usuário, também no parâmetro:
  ```python
  router = APIRouter(prefix="/documentos", dependencies=[Depends(get_current_user)])

  @router.get("/{doc_id}")
  def ler(doc_id: int, user: Annotated[User, Depends(get_current_user)]): ...
  ```
  JWT com PyJWT, como na doc oficial: `jwt.decode(token, SECRET, algorithms=["HS256"])`, validando `exp` e, se usar, `aud` e `iss`.
- **C07 Restringir acessos** — dono no WHERE (`select(Doc).where(Doc.id == doc_id, Doc.owner_id == user.id)`) e 404 se não achar. CORS com credencial só com lista: `CORSMiddleware(app, allow_origins=["https://meuapp.com.br"], allow_credentials=True)`.
- **C08 Bloquear Mass Assignment** — schema de entrada separado do modelo do banco, sem `owner_id`/`role` e com `model_config = ConfigDict(extra="forbid")`; aplique só `data.model_dump(exclude_unset=True)` desse schema.
- **C09 Proteger cookies** — `response.set_cookie("session", token, httponly=True, secure=True, samesite="lax")`.
- **C10 Hash nas senhas** — `pwdlib` com Argon2 (`PasswordHash.recommended()`), como na doc oficial atual, que trocou o passlib.
- **C11 Rate limit** — `slowapi` (`@limiter.limit("10/minute")`, que exige `request: Request` no handler) ou `fastapi-limiter` (Redis). Atrás de proxy, uvicorn com `--proxy-headers --forwarded-allow-ips=<ip do proxy>`.
- **C14 Validação dos inputs** — campo com limite: `Annotated[str, Field(max_length=120)]`, `EmailStr`, `Field(ge=1, le=100)`; nunca `dict` ou `Any` em body de escrita.
- **C15 Evitar vazamento de conteúdo** — `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` em produção (ou docs atrás de auth), sem `debug=True`, e handler de exceção genérico.
- **C16 Restringir uploads** — `UploadFile` não tem limite: limite no proxy (`client_max_body_size`) e leitura em blocos que para no máximo; tipo pelos bytes (`python-magic` ou `filetype`); nome com `uuid4()`.
- **C17 Limitar respostas de API** — `response_model=DocOut` filtra a saída (schema sem campo interno); `limit: Annotated[int, Query(le=100)] = 20`.
- **C18 Security headers** — nada vem por padrão: `@app.middleware("http")` que grava os headers na resposta, ou no proxy.
- **C19 Forçar HTTPS** — redirect no proxy; `HTTPSRedirectMiddleware` só se o TLS termina no próprio app; `TrustedHostMiddleware(allowed_hosts=["meuapp.com.br"])`.

## Rails

**Onde olhar primeiro**
- `config/routes.rb` e `app/controllers/application_controller.rb`: `before_action :authenticate_user!` (Devise) ou `include Authentication` (gerador do Rails 8).
- Controllers: `skip_before_action`, `allow_unauthenticated_access`, strong params, `Model.find(params[:id])`, `render json:`.
- Models (`has_secure_password`, `has_one_attached`, validações) e views (`html_safe`, `raw`, `<%==`).
- `config/environments/production.rb` (`force_ssl`, `assume_ssl`, `consider_all_requests_local`, `hosts`) e `config/initializers/` (`content_security_policy.rb`, `filter_parameter_logging.rb`, `cors.rb`, `rack_attack.rb`).
- `config/credentials*.yml.enc` com `config/master.key` fora do Git, `config/storage.yml`, `Gemfile.lock`.

**Sinais do scanner**
- `rails_skip_auth` → C06 · `rails_params_direto`, `rails_permit_all` → C08 · `csrf_desligado` (`skip_before_action :verify_authenticity_token`) → C09
- `rails_sql_interpolado`, `rails_order_params` → C13 · `rails_html_safe`, `desserializacao_insegura` (`Marshal.load`) → C14 · `rails_erros_detalhados` → C15
- `rails_render_model` → C17 · `rails_force_ssl_off` → C19 · `vulnerabilidades_bundle_audit` → C20 · `arquivo_sensivel_rastreado` (`config/master.key`) → C02
- Limites:
  - A herança de auth só é vista com `before_action :authenticate…` no `ApplicationController`. Com o gerador do Rails 8 (`include Authentication`), controller sem a palavra `authenticate` aparece como `rota_sem_auth_aparente`, e o que tem `allow_unauthenticated_access` passa como protegido. Leia as exceções.
  - `rate_limit` (Rails 7.2+) não conta em C11 (`sem_rate_limit` pode ser falso). O `/up` do Rails (`get "up" => "rails/health#show"`) não conta em P05.

**Correções por checagem**
- **C02 Limpar secrets do Git** — `config/master.key` e `config/credentials/*.key` ficam fora do Git (padrão do `.gitignore`). Vazou: gere credenciais novas, troque cada segredo de dentro e passe a chave só por `RAILS_MASTER_KEY`.
- **C06 Auth server-side** — auth no `ApplicationController` e exceção explícita: `skip_before_action :authenticate_user!, only: %i[index show]` (Devise) ou `allow_unauthenticated_access only: %i[new create]` (Rails 8).
- **C07 Restringir acessos** — escopo pelo usuário: `current_user.documents.find(params[:id])` (no gerador do Rails 8, `Current.user.documents.find(...)`), nunca `Document.find(params[:id])` solto. Papéis com Pundit (`after_action :verify_authorized`) ou CanCanCan.
- **C08 Bloquear Mass Assignment** — `params.expect(user: [:name, :email])` (8.0+) ou `params.require(:user).permit(:name, :email)`; nunca `permit!` nem `:role`/`:admin` na lista.
- **C09 Proteger cookies** — sessão em cookie cifrado (padrão) e `force_ssl` marca o cookie como Secure. `protect_from_forgery` vem ligado; pular CSRF só em API com token no header, nunca com sessão por cookie.
- **C10 Hash nas senhas** — `has_secure_password` (bcrypt) ou Devise (bcrypt); senha nunca em coluna sem hash.
- **C11 Rate limit** — `rate_limit to: 10, within: 3.minutes, only: :create` (7.2+; o gerador do Rails 8 já põe no login) em login, reset e IA. O contador fica no cache: com várias instâncias, cache compartilhado (Solid Cache ou Redis). Alternativa: `rack-attack`.
- **C13 Queries parametrizadas** — `where(email: email)`, `where("email = ?", email)`, `find_by_sql(["... WHERE id = ?", id])`, `sanitize_sql_like(termo)`; `order(params[:sort])` só com allowlist (`%w[name created_at].include?(params[:sort])`). `#{}` em `where`, `order`, `pluck` ou `select` é FALHA.
- **C14 Validação dos inputs** — validações no model + strong params. Views escapam: `raw`, `html_safe` e `<%==` só depois de `sanitize(html)`. `Marshal.load`/`YAML.load` de input viram JSON ou `YAML.safe_load`.
- **C15 Evitar vazamento de conteúdo** — `consider_all_requests_local = false` em produção (padrão do template). `config.filter_parameters` já cobre senha, token e segredo: inclua `:cpf` e afins.
- **C16 Restringir uploads** — os controllers do Active Storage são públicos: a URL é permanente e não pede login. Arquivo privado sai por controller próprio com auth. Tipo e tamanho não vêm validados: `active_storage_validations` ou validação no model (`blob.content_type`, `blob.byte_size`).
- **C17 Limitar respostas de API** — `render json: @user` serializa tudo, inclusive `password_digest`: `as_json(only: %i[id name])`, serializer ou Jbuilder; paginação com `pagy`.
- **C18 Security headers** — o Rails já manda `X-Frame-Options: SAMEORIGIN`, nosniff e `Referrer-Policy: strict-origin-when-cross-origin`. A CSP vem comentada: ative em `config/initializers/content_security_policy.rb` (`policy.default_src :self`, `policy.frame_ancestors :none`) com nonce.
- **C19 Forçar HTTPS** — `config.force_ssl = true` (o template atual já vem assim; liga redirect, HSTS e cookie Secure). Atrás de proxy que termina TLS, `config.assume_ssl = true`; se o health check vier por HTTP, exclua o `/up` do redirect em `ssl_options`.
- **C20 Scan de dependências** — `bundle-audit check --update` e `brakeman` (análise estática; app novo já traz no Gemfile); Dependabot `bundler`.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
