<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Back-end Java, .NET e Go · onde olhar e como corrigir

Referência por stack para o agente que audita Spring Boot, ASP.NET Core e Go: onde o problema costuma estar, o que o `scan.py` sinaliza e a correção certa em cada framework. O critério de FALHA/ATENÇÃO/OK/N/A continua no `checks.md`.

**Stacks:** [Spring Boot](#spring-boot) · [ASP.NET Core](#aspnet-core) · [Go](#go)

Sinais genéricos, válidos em todas as stacks e não repetidos abaixo: `generic_assignment`, `config_com_segredo`, `db_url_password` (C01) · `arquivo_sensivel_rastreado`, `segredo_no_historico` (C02) · `rota_sem_auth_aparente` (C06) · `admin_sem_checagem_de_papel`, `cors_aberto` (C07) · `sem_rate_limit`, `ia_sem_rate_limit` (C11) · `rota_sem_validacao_aparente` (C14) · `sem_security_headers`, `headers_faltando` (C18) · `url_http` (C19) · `auditoria_nao_executada` (C20).

Versões de referência (out/2026): Spring Boot 4.0/4.1 com Spring Security 7 (Boot 3.5 e Security 6.5 sem suporte OSS desde 30/06/2026) · .NET 10 LTS (.NET 8 e 9 sem suporte a partir de 10/11/2026) · Go: só as duas versões mais recentes recebem correção.

## Spring Boot

Os exemplos valem para Spring Security 6.x e 7.x: DSL com lambda (o 6.1 depreciou `.and()` e o estilo encadeado, que saem no 7).

**Onde olhar primeiro**
- Classe `@Configuration` com `SecurityFilterChain` (`authorizeHttpRequests`, `csrf`, `cors`, `headers`, `sessionManagement`, `oauth2ResourceServer`, `formLogin`) e `@EnableMethodSecurity`.
- `application.properties`/`application.yml` e perfis de produção: `spring.datasource.*`, `management.*`, `server.error.*`, `spring.h2.console.*`, `springdoc.*`, `server.servlet.session.cookie.*`, `spring.servlet.multipart.*`, `server.forward-headers-strategy`, `spring.data.web.pageable.*`.
- `@RestController`: `@RequestBody` com `@Entity`, `@PathVariable Long id` + `findById`, entidade no retorno, `@CrossOrigin`.
- Repositórios e SQL: `@Query(nativeQuery = true)`, `EntityManager.createQuery`/`createNativeQuery`, `JdbcTemplate`, `Sort` e filtros vindos do request.
- Templates Thymeleaf (`th:utext`), uploads (`MultipartFile`), `pom.xml` ou `build.gradle(.kts)`.

**Sinais do scanner**
- `spring_permit_all_geral` → C06 · `spring_entity_no_requestbody` → C08 · `spring_retorna_entity` → C17 · `spring_noop_encoder`, `hash_rapido_jvm_cs_go` → C10
- `jvm_sql_concatenado`, `jvm_string_format_sql` → C13 · `thymeleaf_utext`, `exec_shell_go_jvm`, `desserializacao_insegura` (`ObjectInputStream`), `ssrf_url_do_usuario`, `path_traversal` → C14
- `spring_actuator_aberto`, `spring_stacktrace`, `h2_console`, `swagger_publico` → C15 · `httponly_false_generico`, `csrf_desligado` → C09
- `nome_original_framework` (`getOriginalFilename()`) → C16 · `jdbc_password` → C01 · `cripto_fraca` → C05
- Limites:
  - A auth fica no `SecurityFilterChain`, não no controller. Com `anyRequest().authenticated()` (ou `hasRole`/`access`) na cadeia, o scanner considera os controllers protegidos (`checks.C06.sinais.auth_global`); sem isso, quase todo controller aparece como `rota_sem_auth_aparente`. Decida pela cadeia, pelos `requestMatchers(...).permitAll()` e pelos `@PreAuthorize`.
  - `Cipher.getInstance("AES")` (que no Java é ECB) entra em `cripto_fraca` (C05) e `th:utext` em `thymeleaf_utext` (C14).
  - Não há auditoria de Maven/Gradle no scanner (só o `osv-scanner`, se instalado). Com o starter do Actuator, o `/actuator/health` conta como health check em P05.

**Correções por checagem**
- **C01 Esconder API Keys** — valor real fora dos arquivos versionados: `spring.datasource.password=${DB_PASSWORD}`, `app.openai.key=${OPENAI_API_KEY}`; cofre (Vault, Secrets Manager) via Spring Cloud se houver.
- **C05 Criptografia de dados** — `AttributeConverter` do JPA com `Cipher.getInstance("AES/GCM/NoPadding")`, IV aleatório por valor e chave fora do código. `"AES"` sozinho usa ECB.
- **C06 Auth server-side** — negar por padrão e liberar só a exceção:
  ```java
  @Bean
  SecurityFilterChain api(HttpSecurity http) throws Exception {
      http.authorizeHttpRequests(a -> a
              .requestMatchers("/actuator/health", "/api/public/**").permitAll()
              .requestMatchers("/api/admin/**").hasRole("ADMIN")
              .anyRequest().authenticated())
          .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()));
      return http.build();
  }
  ```
  JWT: `spring.security.oauth2.resourceserver.jwt.issuer-uri` valida assinatura, `iss` e `exp`; confira também o `aud`. `permitAll()` em `/**` ou em `anyRequest()` é FALHA. `antMatchers` e `authorizeRequests` denunciam Spring Security antigo (C20).
- **C07 Restringir acessos** — `@EnableMethodSecurity` + `@PreAuthorize("hasRole('ADMIN')")`; recurso sempre pelo dono: `repo.findByIdAndOwnerId(id, jwt.getSubject())` com `@AuthenticationPrincipal Jwt jwt`, nunca `findById(id)` solto. CORS: `CorsConfigurationSource` com `setAllowedOrigins(List.of("https://meuapp.com.br"))`; `allowedOriginPatterns("*")` com `allowCredentials(true)` é FALHA, e `@CrossOrigin("*")` em API privada é ATENÇÃO.
- **C08 Bloquear Mass Assignment** — DTO (record) só com o editável, validado:
  ```java
  public record AtualizaPerfil(@NotBlank @Size(max = 80) String nome, @Size(max = 500) String bio) {}

  @PutMapping("/me")
  PerfilView atualiza(@Valid @RequestBody AtualizaPerfil in, @AuthenticationPrincipal Jwt jwt) {
      return service.atualiza(jwt.getSubject(), in);
  }
  ```
  Formulário com `@ModelAttribute`: `@InitBinder` com `setAllowedFields(...)`. Bean Validation precisa do `spring-boot-starter-validation`.
- **C09 Proteger cookies** — `server.servlet.session.cookie.secure=true`, `http-only=true` (padrão) e `same-site=lax`. CSRF desligado (`csrf(AbstractHttpConfigurer::disable)`) só em API stateless com token no header; com sessão por cookie, mantenha.
- **C10 Hash nas senhas** — `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (bcrypt) ou `new BCryptPasswordEncoder(12)`; Argon2: `Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8()` (pede BouncyCastle). `NoOpPasswordEncoder` e `{noop}` são FALHA.
- **C11 Rate limit** — não há limite nativo: Bucket4j (com Redis se houver mais de uma instância), filtro próprio ou limite no gateway/WAF; login com bloqueio progressivo por conta e por IP.
- **C13 Queries parametrizadas** — JPQL com parâmetro (`@Query("select u from User u where u.email = :email")` + `@Param("email")`), `createQuery(...).setParameter(...)`, `jdbcTemplate.query("select ... where email = ?", mapper, email)`, `NamedParameterJdbcTemplate`. `Sort` e `ORDER BY` dinâmicos só de allowlist.
- **C14 Validação dos inputs** — `@Valid` em todo `@RequestBody`; `@Validated` na classe para valer constraint em `@RequestParam`/`@PathVariable`. Thymeleaf: `th:text` escapa, `th:utext` não (só com HTML limpo: `Jsoup.clean(html, Safelist.basic())` ou OWASP Java HTML Sanitizer). Nada de `ObjectInputStream` ou default typing do Jackson com dado externo.
- **C15 Evitar vazamento de conteúdo** — `server.error.include-stacktrace` e `include-message` em `never` (é o padrão; `always` ou `on_param` vaza). Actuator: na web só `health` vem exposto; nunca `management.endpoints.web.exposure.include=*` público (`env`, `heapdump`, `configprops`). Se precisar de mais, `management.server.port` interno + Spring Security. `spring.h2.console.enabled=false` fora de dev; `springdoc.api-docs.enabled=false` e `springdoc.swagger-ui.enabled=false` em produção.
- **C16 Restringir uploads** — `spring.servlet.multipart.max-file-size` (padrão 1MB) e `max-request-size` (padrão 10MB) com o tamanho real que o app aceita; tipo pelos bytes (Apache Tika: `new Tika().detect(in)`); nome `UUID.randomUUID()`, gravado fora da pasta estática.
- **C17 Limitar respostas de API** — devolva DTO ou projeção, nunca a `@Entity` (o Jackson serializa hash e relações); `@JsonProperty(access = JsonProperty.Access.WRITE_ONLY)` no `password` como cinto extra. `Pageable` com teto: `spring.data.web.pageable.max-page-size=100` (o padrão é 2000).
- **C18 Security headers** — o Spring Security já manda nosniff, `X-Frame-Options: DENY`, `Cache-Control` sem cache, `X-XSS-Protection: 0` e HSTS (só em resposta HTTPS). Faltam CSP e Referrer-Policy:
  ```java
  http.headers(h -> h
      .contentSecurityPolicy(c -> c.policyDirectives("default-src 'self'; frame-ancestors 'none'"))
      .referrerPolicy(r -> r.policy(ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)));
  ```
  Sem o `spring-boot-starter-security` não sai header nenhum: adicione o starter ou um filtro.
- **C19 Forçar HTTPS** — redirect no proxy ou load balancer e `server.forward-headers-strategy=native` (ou `framework`) para o app enxergar o `https`. JDBC com TLS (`sslmode=require` no Postgres). `TrustManager` que aceita tudo ou `HostnameVerifier` que sempre retorna `true` é FALHA.
- **C20 Scan de dependências** — `mvn org.owasp:dependency-check-maven:check` (ou o plugin do Gradle) ou `osv-scanner scan source -r .`; Dependabot `maven`/`gradle`. Boot 3.x em produção é ATENÇÃO ALTO até migrar para 4.x (sem correção OSS desde 30/06/2026).

## ASP.NET Core

**Onde olhar primeiro**
- `Program.cs`: autenticação e autorização, `AddRateLimiter`, `AddCors`, `AddDataProtection` e a ordem do pipeline (`UseExceptionHandler`, `UseHsts`, `UseHttpsRedirection`, `UseCors`, `UseAuthentication`, `UseAuthorization`, `UseRateLimiter`, `Map*`).
- `appsettings*.json` (connection strings, `Jwt:Key`, `AllowedHosts`), `Properties/launchSettings.json` e o `ASPNETCORE_ENVIRONMENT` de produção.
- Controllers (`[ApiController]`, `[Authorize]`, `[AllowAnonymous]`, `[FromBody] Entidade`), minimal APIs (`MapGroup(...).RequireAuthorization()`), Razor (`@Html.Raw`), Blazor (`MarkupString`).
- EF Core e ADO.NET (`FromSqlRaw`, `ExecuteSqlRaw`, `SqlQueryRaw`, `SqlCommand`), Identity (`IdentityOptions`, páginas scaffolded) e `*.csproj` (`TargetFramework`, pacotes).

**Sinais do scanner**
- `aspnet_allow_anonymous` → C06 · `dotnet_sql_raw_interpolado` → C13 · `aspnet_developer_exception`, `swagger_publico` → C15 · `aspnet_https_metadata_off` → C19
- `httponly_false_generico` (`CookieSecurePolicy.None`, `HttpOnly = false`) → C09 · `hash_rapido_jvm_cs_go` (`MD5.Create()`, `SHA256.Create()`) → C10 · `adonet_password` → C01
- `desserializacao_insegura` (`BinaryFormatter`), `ssrf_url_do_usuario`, `path_traversal`, `open_redirect` → C14 · `nome_original_framework` (`IFormFile.FileName`) → C16
- `aspnet_cors_qualquer_origem` → C07 · `vulnerabilidades_altas`, `vulnerabilidades_moderadas` (`dotnet list package --vulnerable`) → C20
- Limites: com `FallbackPolicy` exigindo usuário autenticado (ou `MapControllers().RequireAuthorization()`), o scanner considera os endpoints protegidos, menos os que têm `[AllowAnonymous]`; sem isso, controller sem `[Authorize]` aparece como `rota_sem_auth_aparente`. `SetIsOriginAllowed(_ => true)` entra em `aspnet_cors_qualquer_origem` (C07). `dotnet list package --vulnerable` roda se o `dotnet` estiver instalado.

**Correções por checagem**
- **C01 Esconder API Keys** — em dev, `dotnet user-secrets set "OpenAI:ApiKey" "<valor>"` (fica fora do repo); em produção, variável de ambiente (`OpenAI__ApiKey`) ou Key Vault (`builder.Configuration.AddAzureKeyVault(...)`). Nada real em `appsettings*.json` versionado.
- **C05 Criptografia de dados** — Data Protection (`IDataProtector.Protect`) ou `AesGcm` com chave fora do código. As chaves do Data Protection, que também cifram cookies e tokens, ficam num diretório local por padrão: em container somem a cada deploy (todo mundo deslogado) e cada réplica gera as suas. Persista em volume durável ou serviço compartilhado: `AddDataProtection().PersistKeysToFileSystem(new DirectoryInfo("/keys")).SetApplicationName("meuapp")`, protegendo as chaves com Key Vault ou certificado.
- **C06 Auth server-side** — autenticado por padrão, exceção explícita:
  ```csharp
  builder.Services.AddAuthorizationBuilder()
      .SetFallbackPolicy(new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build());
  var api = app.MapGroup("/api").RequireAuthorization();
  app.MapGet("/health", () => Results.Ok()).AllowAnonymous();
  ```
  JWT: `AddJwtBearer` com `Authority` e `Audience`, `RequireHttpsMetadata = true` e `TokenValidationParameters` validando issuer, audience, lifetime e chave de assinatura.
- **C07 Restringir acessos** — policies (`AddPolicy("Admin", p => p.RequireRole("admin"))`) e autorização por recurso (`IAuthorizationService.AuthorizeAsync(User, doc, "PodeEditar")`); consulta com dono: `db.Docs.SingleOrDefaultAsync(d => d.Id == id && d.OwnerId == userId)`. CORS: `WithOrigins("https://meuapp.com.br")`. `AllowAnyOrigin()` + `AllowCredentials()` o framework recusa, mas `SetIsOriginAllowed(_ => true)` + `AllowCredentials()` reflete qualquer origem e é FALHA.
- **C08 Bloquear Mass Assignment** — record ou DTO no `[FromBody]`, nunca a entidade (`IsAdmin`, `Role`, `OwnerId` viriam junto). MVC com formulário: `TryUpdateModelAsync(doc, "", d => d.Titulo, d => d.Corpo)`.
- **C09 Proteger cookies** — `ConfigureApplicationCookie(o => { o.Cookie.HttpOnly = true; o.Cookie.SecurePolicy = CookieSecurePolicy.Always; o.Cookie.SameSite = SameSiteMode.Lax; })`; o padrão de `SecurePolicy` é `SameAsRequest`. Antiforgery: filtro global `AutoValidateAntiforgeryTokenAttribute` no MVC; minimal API com formulário (.NET 8+), `app.UseAntiforgery()`.
- **C10 Hash nas senhas** — o Identity usa PBKDF2 (formato V3, 100 mil iterações por padrão): OK, não troque por hash próprio. `IdentityOptions.Password.RequiredLength` padrão é 6: suba para 8 ou mais. Sem Identity, `PasswordHasher<TUser>` ou Argon2id.
- **C11 Rate limit** — limitador nativo (.NET 7+):
  ```csharp
  builder.Services.AddRateLimiter(o => {
      o.RejectionStatusCode = StatusCodes.Status429TooManyRequests; // o padrão é 503
      o.AddFixedWindowLimiter("login", l => { l.PermitLimit = 5; l.Window = TimeSpan.FromMinutes(1); });
  });
  app.UseRateLimiter();
  app.MapPost("/login", Login).RequireRateLimiting("login");
  ```
  Por usuário ou IP: `o.AddPolicy("ia", ctx => RateLimitPartition.GetFixedWindowLimiter(ctx.User.Identity?.Name ?? ctx.Connection.RemoteIpAddress?.ToString() ?? "anon", _ => new() { PermitLimit = 10, Window = TimeSpan.FromMinutes(1) }))`. O contador vive na memória de cada réplica. Identity: `PasswordSignInAsync(..., lockoutOnFailure: true)` (as páginas scaffolded vêm com `false`).
- **C13 Queries parametrizadas** — `FromSql($"... {x}")`/`FromSqlInterpolated`, `SqlQuery<T>($"...")` e `ExecuteSql($"...")` parametrizam; `FromSqlRaw`, `ExecuteSqlRaw` e `SqlQueryRaw` com `$"..."` ou `+` são FALHA (com placeholder `{0}` e argumento, ok). Dapper: `QueryAsync<User>("... where Email = @Email", new { Email = email })`; ADO.NET: `cmd.Parameters.AddWithValue("@email", email)`.
- **C14 Validação dos inputs** — `[ApiController]` valida DataAnnotations e devolve 400; minimal API: `builder.Services.AddValidation()` (.NET 10; antes, filtro ou FluentValidation). `@Html.Raw` e `MarkupString` só com HTML sanitizado (pacote `HtmlSanitizer`). `BinaryFormatter` (removido no .NET 9) e `TypeNameHandling.All` do Newtonsoft com input são FALHA.
- **C15 Evitar vazamento de conteúdo** — `ASPNETCORE_ENVIRONMENT=Production`: no .NET 6+ a página de exceção do desenvolvedor liga sozinha em `Development`. Use `AddProblemDetails()` + `app.UseExceptionHandler()`; `UseDeveloperExceptionPage`, Swagger e `MapOpenApi()` só dentro de `if (app.Environment.IsDevelopment())`; `builder.WebHost.ConfigureKestrel(o => o.AddServerHeader = false)`.
- **C16 Restringir uploads** — `[RequestSizeLimit(5_000_000)]` no endpoint (o Kestrel aceita ~28,6 MB por padrão e `FormOptions.MultipartBodyLengthLimit` vai a 128 MB); tipo pelos bytes; nome `Path.GetRandomFileName()`; nunca `IFormFile.FileName` no caminho nem gravação em `wwwroot`.
- **C17 Limitar respostas de API** — projeção para DTO (`Select(d => new DocDto(d.Id, d.Titulo))`), nunca a entidade do EF; `Take(Math.Min(tamanho, 100))`.
- **C18 Security headers** — nada vem por padrão: middleware no início do pipeline ou o pacote `NetEscapades.AspNetCore.SecurityHeaders`:
  ```csharp
  app.Use(async (ctx, next) => {
      var h = ctx.Response.Headers;
      h["X-Content-Type-Options"] = "nosniff";
      h["X-Frame-Options"] = "DENY";
      h["Referrer-Policy"] = "strict-origin-when-cross-origin";
      h["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'";
      await next();
  });
  ```
- **C19 Forçar HTTPS** — `app.UseHttpsRedirection()` e `app.UseHsts()` fora de Development (o HSTS padrão é de 30 dias: `AddHsts(o => o.MaxAge = TimeSpan.FromDays(365))`). Atrás de proxy, `UseForwardedHeaders` com `XForwardedProto` antes deles. `RequireHttpsMetadata = false` só em dev.
- **C20 Scan de dependências** — `dotnet list package --vulnerable --include-transitive`. O NuGet Audit roda no `restore`, mas só audita transitivos por padrão em projeto .NET 10 (no 8 e no 9, `<NuGetAuditMode>all</NuGetAuditMode>`); Dependabot `nuget`. .NET 8 e 9 perdem suporte em 10/11/2026: migre para o .NET 10.

## Go

Vale para `net/http` e para Gin, Echo, Fiber e chi.

**Onde olhar primeiro**
- `main.go` ou `cmd/*/main.go`: router, middlewares (`r.Use`, `Group`), `http.Server{...}` (timeouts), `ListenAndServe`/TLS e `import _ "net/http/pprof"`.
- Middleware de auth (`func RequireAuth(next http.Handler) http.Handler`), onde ele é aplicado e os handlers (`internal/**/handler*.go`).
- Banco: `database/sql`, pgx, sqlx, GORM, sqlc (`query.sql`). Templates: `html/template` × `text/template`.
- `go.mod`/`go.sum` (diretivas `go` e `toolchain`) e Dockerfile.

**Sinais do scanner**
- `go_bind_e_salva` → C08 · `go_sql_sprintf` → C13 · `go_template_html`, `exec_shell_go_jvm`, `ssrf_url_do_usuario` (`http.Get`), `path_traversal` (`os.Open`) → C14 · `gin_debug`, `go_pprof_exposto` → C15
- `hash_rapido_jvm_cs_go` (`md5.Sum`, `sha256.Sum256` perto de senha) → C10 · `tls_verificacao_desligada` (`InsecureSkipVerify: true`) → C19
- `nome_original_framework` (`header.Filename`) → C16 · `jwt_alg_none` → C06 · `vulnerabilidades_govulncheck` → C20
- Limites: auth aplicada no router de outro arquivo faz o handler aparecer como `rota_sem_auth_aparente`. O go-playground/validator conta como lib de validação, o `limiter` do Fiber conta em C11 e `net/http/pprof` importado vira `go_pprof_exposto` (C15). `sem_lockfile` não cobra `go.sum` e `ReadHeaderTimeout` ausente não é sinalizado.

**Correções por checagem**
- **C06 Auth server-side** — middleware no grupo de rotas, não checagem repetida (e esquecida) handler a handler:
  ```go
  r := chi.NewRouter()
  r.Group(func(r chi.Router) {
      r.Use(RequireAuth) // valida token ou sessão e põe o usuário no context
      r.Get("/api/docs/{id}", getDoc)
  })
  ```
  Gin: `api := r.Group("/api", AuthRequired())`; Echo: `e.Group("/api", echojwt.JWT([]byte(secret)))`; `net/http` 1.22+: `mux.Handle("GET /api/docs/{id}", RequireAuth(http.HandlerFunc(getDoc)))`. JWT (`golang-jwt/jwt/v5`): `jwt.Parse(tok, keyFunc, jwt.WithValidMethods([]string{"HS256"}), jwt.WithIssuer(iss), jwt.WithAudience(aud), jwt.WithExpirationRequired())`.
- **C07 Restringir acessos** — dono no WHERE (`... WHERE id = $1 AND owner_id = $2`), com o usuário tirado do `context`, nunca do body ou da query string.
- **C08 Bloquear Mass Assignment** — struct de entrada só com o editável e `dec.DisallowUnknownFields()` no `json.Decoder`. GORM: `db.Save(&u)` grava todas as colunas, inclusive `Role` vindo do JSON; use `db.Model(&u).Select("Name", "Bio").Updates(in)`. `Updates(map)` montado do request é FALHA.
- **C09 Proteger cookies** — `http.SetCookie(w, &http.Cookie{Name: "session", Value: v, Path: "/", HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode})`; no Gin, `c.SetSameSite(http.SameSiteLaxMode)` antes de `c.SetCookie(...)` com `secure` e `httpOnly` `true`. CSRF com sessão por cookie: Go 1.25+ `http.NewCrossOriginProtection().Handler(mux)` (confere `Sec-Fetch-Site` e `Origin`) ou token.
- **C10 Hash nas senhas** — `bcrypt.GenerateFromPassword([]byte(senha), 12)` (`golang.org/x/crypto/bcrypt`; o `DefaultCost` é 10) ou Argon2id (`github.com/alexedwards/argon2id`). `sha256.Sum256` em senha é FALHA.
- **C11 Rate limit** — `golang.org/x/time/rate` (um limiter por IP ou usuário, num map com mutex e limpeza) ou `github.com/go-chi/httprate` (`httprate.LimitByIP(100, time.Minute)`); várias instâncias: Redis (`github.com/go-redis/redis_rate`). O Gin confia em qualquer proxy por padrão: chame `r.SetTrustedProxies([]string{"10.0.0.0/8"})`, senão `c.ClientIP()` aceita `X-Forwarded-For` forjado. `http.Server{ReadHeaderTimeout: 5 * time.Second}` contra Slowloris.
- **C13 Queries parametrizadas** — placeholder do driver (`$1` no Postgres e no pgx, `?` no MySQL e no SQLite):
  ```go
  row := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE email = $1", email)
  db.Where("name = ?", name).First(&u) // GORM: o valor vai sempre como argumento
  ```
  `fmt.Sprintf` ou `+` em SQL é FALHA. O GORM não escapa string passada a `Select`, `Order`, `Group`, `Having`, `Joins`, `Table`, `Raw`, `Exec` nem a condição inline: `db.First(&u, idDoRequest)` com string injeta SQL (converta com `strconv.Atoi`). O sqlc gera código parametrizado.
- **C14 Validação dos inputs** — `go-playground/validator` (`validate:"required,max=120"`; no Gin, tag `binding`). `html/template` escapa e `text/template` não; `template.HTML(x)` só com HTML limpo (`bluemonday.UGCPolicy().Sanitize(x)`). Comando externo com argumentos separados (`exec.Command("convert", entrada, saida)`), nunca `sh -c` com input. Arquivo: Go 1.24+ `os.OpenRoot(dir)` prende o acesso ao diretório.
- **C15 Evitar vazamento de conteúdo** — `GIN_MODE=release` (ou `gin.SetMode(gin.ReleaseMode)`). `import _ "net/http/pprof"` registra `/debug/pprof/` no `http.DefaultServeMux`: se o app serve esse mux em público, vaza heap e goroutines; use mux próprio e pprof só em porta interna. Erro para o cliente sem `err.Error()`.
- **C16 Restringir uploads** — `r.Body = http.MaxBytesReader(w, r.Body, 5<<20)` antes do parse; o argumento de `ParseMultipartForm` e o `MaxMultipartMemory` do Gin só decidem memória × disco, não limitam. Tipo com `http.DetectContentType` nos primeiros 512 bytes; nome com UUID. Echo: `middleware.BodyLimit("5M")`; Fiber: `fiber.Config{BodyLimit: ...}` (padrão 4 MB).
- **C17 Limitar respostas de API** — struct de resposta própria, `json:"-"` em `PasswordHash` e tokens, `LIMIT` com teto.
- **C18 Security headers** — nada vem por padrão: middleware que grava os headers, `github.com/unrolled/secure`, `middleware.SecureWithConfig(...)` do Echo ou o `helmet` do Fiber.
- **C19 Forçar HTTPS** — `tls.Config{MinVersion: tls.VersionTLS12}`; nunca `InsecureSkipVerify: true` (CA própria vai em `RootCAs`). Sem proxy na frente: `golang.org/x/crypto/acme/autocert` e redirect da porta 80. Postgres: `sslmode=verify-full` (ou `require`).
- **C20 Scan de dependências** — `govulncheck ./...` (aponta só a vulnerabilidade que o código alcança), `go.sum` versionado, Dependabot `gomod`. A stdlib também tem CVE: mantenha `go`/`toolchain` do `go.mod` numa versão suportada. `gosec ./...` como extra.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
