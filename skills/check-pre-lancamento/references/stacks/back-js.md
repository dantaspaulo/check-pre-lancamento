<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Back-end JavaScript e serverless · onde olhar e como corrigir

Referência por stack para o agente que audita back-end em JavaScript/TypeScript e funções serverless: o que chega ao cliente pela resposta, onde olhar, o que o `scan.py` sinaliza e a correção certa em cada stack. O critério de FALHA/ATENÇÃO/OK/N/A continua no `checks.md`.

**Stacks:** [Express](#express) · [Fastify](#fastify) · [NestJS](#nestjs) · [Hono](#hono) · [Koa](#koa) · [Elysia e Bun](#elysia-e-bun) · [AdonisJS](#adonisjs) · [tRPC](#trpc) · [GraphQL (Apollo, Yoga, Mercurius)](#graphql-apollo-yoga-mercurius) · [Vercel e Netlify Functions](#vercel-e-netlify-functions) · [Cloudflare Workers](#cloudflare-workers) · [AWS Lambda](#aws-lambda)

Sinais genéricos, válidos em todas as stacks e não repetidos abaixo: `generic_assignment`, `config_com_segredo`, `db_url_password` (C01) · `arquivo_sensivel_rastreado`, `segredo_no_historico` (C02) · `rota_sem_auth_aparente`, `jwt_decode_sem_verificar`, `jwt_alg_none` (C06) · `identidade_do_cliente`, `busca_por_id_do_request`, `admin_sem_checagem_de_papel`, `cors_aberto`, `cors_sem_opcoes` (C07) · `data_do_request`, `create_update_com_body`, `spread_do_body`, `object_assign_body`, `merge_profundo_com_body` (C08) · `hash_rapido`, `bcrypt_custo_baixo`, `senha_gravada_direto` (C10) · `sem_rate_limit`, `ia_sem_rate_limit` (C11) · `sql_template_interpolado`, `sql_concatenado`, `raw_unsafe`, `nosql_body_direto`, `nosql_where` (C13) · `rota_sem_validacao_aparente`, `sem_lib_de_validacao`, `ssrf_url_do_usuario`, `path_traversal`, `open_redirect`, `shell_interpolado`, `desserializacao_insegura` (C14) · `stack_na_resposta`, `erro_inteiro_na_resposta`, `mensagem_interna`, `log_sensivel` (C15) · `upload_sem_limite`, `upload_sem_validacao_tipo`, `nome_original_no_caminho`, `svg_permitido` (C16) · `objeto_usuario_inteiro`, `limit_sem_teto`, `findmany_sem_take`, `select_estrela_sem_limite`, `sql_select_estrela_sem_limit` (C17) · `sem_security_headers`, `headers_faltando` (C18) · `tls_verificacao_desligada`, `db_sem_tls`, `pg_sem_ssl`, `url_http` (C19) · `auditoria_nao_executada`, `vulnerabilidades_altas` (C20) · `sem_health_check` (P05).

Como o scanner acha rota e auth: `app.`, `router.`, `server.` ou `api.` seguido de `.get('/...')` (ou `new Hono|Elysia|Koa(` com `.get('/...')`) vira `http-router`; `@Controller` com `@Get`, `export default { fetch }`, `exports.handler` com `event.body`, `netlify/functions/**` e `api/*.ts` também entram. Conta como auth, procurado só no arquivo da rota: `req.user`, `jwt.verify`, `jwtVerify`, `passport.authenticate`, `requireAuth`, `authenticate`, `ctx.user`/`ctx.auth`/`ctx.state.user`, `@UseGuards(`, `jwt({`, `bearerAuth(`, `protectedProcedure`, header `authorization` e verificação de assinatura de webhook.

Versões de referência (out/2026): Express 5.3 (4.x ainda suportado) · Fastify 5.12 · NestJS 12 · Hono 4.13 · Koa 3 · Elysia 1.4 · AdonisJS 7 · tRPC 11 · Apollo Server 5 (4 sem suporte desde 26/01/2026) · GraphQL Yoga 6 · Mercurius 16. Versão sem correção de segurança entra em C20.

## Express

**O que vai para o cliente**
- Nenhum código do servidor. Vaza o que a resposta leva: objeto inteiro no `res.json`, erro (sem `NODE_ENV=production`, o handler padrão devolve `err.stack`), `X-Powered-By: Express` e tudo o que `express.static` servir.
- Se o Express também serve o build do front, vale o `front-e-mobile.md` para esse build.

**Onde olhar primeiro**
- Bootstrap (`app.ts`, `server.ts`, `index.ts`): ordem dos `app.use` (helmet, cors, parsers, rate limit, auth, rotas e error handler por último), `app.set("trust proxy", ...)`, `express.static`.
- `routes/**`, `controllers/**`, `middlewares/auth*`, config de `express-session`/`cookie-parser`, multer e consultas (`pool.query`, `knex.raw`, `$queryRawUnsafe`, `Model.find(req.query)`).

**Sinais do scanner**
- `cookie_sem_flags`, `httponly_false`, `secure_false`, `samesite_none` → C09 · `static_na_raiz` → C15 · `x_powered_by` (sem helmet nem `app.disable("x-powered-by")`) → C18
- Limites: com helmet no `package.json`, `headers_faltando` aponta só `Permissions-Policy`, que o helmet não manda.

**Correções por checagem**
- **C06 Auth server-side** — middleware de auth no router privado (modelo no `checks.md`). JWT: `jwt.verify(token, segredo, { algorithms: ["HS256"], issuer, audience })` ou `jwtVerify` do `jose` com `createRemoteJWKSet` para IdP. O Express 4 não repassa erro de handler `async` ao error handler: use wrapper ou suba para o 5.
- **C07 Restringir acessos** — `cors()` sem opções libera `*`: use allowlist. `origin: true` com `credentials: true` reflete qualquer origem.
- **C08 Bloquear Mass Assignment** — o banco recebe o resultado do schema, nunca `req.body`. Mongoose: `Model.create(req.body)` grava `role` se o campo existir no schema.
- **C09 Proteger cookies** — `express-session` com `cookie: { httpOnly: true, secure: true, sameSite: "lax" }`, `resave: false`, `saveUninitialized: false` e store Redis (`connect-redis`): o `MemoryStore` padrão não é para produção. `secure` atrás de proxy exige `trust proxy`. O `csurf` foi descontinuado: SameSite + checagem de `Origin`, ou `csrf-csrf`/`csrf-sync`.
- **C11 Rate limit** — a lib vem com `limit: 5` por minuto e store em memória; com mais de uma instância, `store` do `rate-limit-redis`:
  ```ts
  import { rateLimit } from "express-rate-limit";
  app.set("trust proxy", 1); // nº de proxies na frente; `true` aceita IP forjado
  app.use("/api/auth", rateLimit({ windowMs: 15 * 60_000, limit: 20,
    standardHeaders: "draft-8", legacyHeaders: false }));
  ```
- **C13 Queries parametrizadas** — Mongo: valide o tipo antes do filtro e ligue `mongoose.set("sanitizeFilter", true)` (embrulha `$ne`/`$gt` vindos do request em `$eq`).
- **C14 Validação dos inputs** — middleware `validate(schema)` com zod por rota. `express.json()` mantém o limite padrão de 100 kB; aumente só na rota que precisa. No Express 5, `req.body` é `undefined` sem parser.
- **C15 Evitar vazamento de conteúdo** — `NODE_ENV=production` no deploy e error handler próprio por último. `express.static` só na pasta do build (`dist/`, `public/`), nunca `__dirname` ou `process.cwd()`.
  ```ts
  app.use((err, req, res, _next) => { // 4 argumentos, depois das rotas
    console.error(err);               // ou pino/Sentry
    res.status(500).json({ error: "Erro interno. Tente novamente." });
  });
  ```
- **C16 Restringir uploads** — multer 2.0.2+ (antes, multipart malformado derruba o processo: CVE-2025-7338), `limits: { fileSize, files: 1 }`, `memoryStorage()` e `fileTypeFromBuffer`: o `fileFilter` só vê o MIME declarado pelo cliente.
- **C18 Security headers** — `app.use(helmet())` antes das rotas: CSP, HSTS (365 dias), `X-Frame-Options: SAMEORIGIN`, nosniff, `Referrer-Policy: no-referrer` e sem `X-Powered-By`. `Permissions-Policy` à mão: `res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()")`.
- **C19 Forçar HTTPS** — redirect no proxy, ou `trust proxy` + `req.secure` (modelo no `checks.md`).
- **C20 Scan de dependências** — 4.x e 5.x seguem suportados, mas só a última versão de cada linha recebe correção: fique no último patch.

## Fastify

**O que vai para o cliente**
- Sem código. O handler de erro padrão devolve o `message` do erro original até em 500 (texto do banco, nome de coluna). Sem schema de resposta, sai o objeto inteiro.

**Onde olhar primeiro**
- `Fastify({ trustProxy, bodyLimit, logger })`, plugins registrados (helmet, cors, rate-limit, jwt, cookie, multipart) e se usam `fastify-plugin`, `addHook("onRequest" | "preHandler")`, `schema` de cada rota (`body`, `querystring`, `params`, `response`) e `setErrorHandler`.

**Sinais do scanner**
- `@fastify/helmet` conta como helmet, então `headers_faltando` (C18) só aponta `Permissions-Policy` · `@fastify/rate-limit` conta como rate limit (C11) · `@fastify/multipart` aciona as regras de upload (C16).
- Limites:
  - Rota declarada como `fastify.get(...)`, `instance.post(...)` ou `fastify.route({...})` não entra na lista de rotas: só instâncias chamadas `app`, `server`, `router` ou `api`.
  - `reply.send(user)` e `return user` não disparam `objeto_usuario_inteiro`. O Ajv embutido não conta como lib: `sem_lib_de_validacao` pode ser falso positivo.

**Correções por checagem**
- **C06 Auth server-side** — hook de auth no contexto das rotas privadas: hook registrado dentro de um plugin vale só para as rotas daquele plugin (encapsulamento), e `fastify-plugin` o leva para o pai. Com `@fastify/jwt`: `app.addHook("onRequest", (req) => req.jwtVerify())`.
- **C08 Bloquear Mass Assignment** — com `additionalProperties: false`, o Ajv padrão do Fastify (`removeAdditional: true`) remove campo extra; sem schema de body, `request.body` aceita qualquer coisa.
- **C09 Proteger cookies** — `@fastify/cookie` com `reply.setCookie(nome, valor, { httpOnly: true, secure: true, sameSite: "lax", path: "/" })`; sessão por cookie com formulário: `@fastify/csrf-protection`.
- **C11 Rate limit** — `await app.register(rateLimit, { max: 100, timeWindow: "1 minute", redis })` e, por rota, `config: { rateLimit: { max: 5, timeWindow: "1 minute" } }`; sem `redis`, o contador é por instância. `trustProxy` com IP/CIDR do proxy (a contagem numérica de saltos foi desativada nas versões recentes do 5.x; confira na doc da versão).
- **C14 Validação dos inputs** — schema em toda rota que lê input:
  ```ts
  app.post("/posts", {
    onRequest: [app.authenticate],  // decorator criado com @fastify/jwt
    schema: {
      body: { type: "object", additionalProperties: false, required: ["title"],
              properties: { title: { type: "string", maxLength: 120 } } },
      response: { 201: { type: "object", properties: { id: { type: "string" } } } },
    },
  }, criarPost);
  ```
- **C15 Evitar vazamento de conteúdo** — `setErrorHandler` que loga tudo e devolve texto genérico em 5xx:
  ```ts
  app.setErrorHandler((err, req, reply) => {
    if (err.validation) return reply.code(400).send({ error: "Dados inválidos" });
    req.log.error(err);
    const status = err.statusCode && err.statusCode < 500 ? err.statusCode : 500;
    reply.code(status).send({ error: status < 500 ? err.message : "Erro interno" });
  });
  ```
- **C16 Restringir uploads** — `@fastify/multipart`: `fileSize` padrão = `bodyLimit` (1 MiB) e `parts` = 1000; defina `limits: { fileSize, files: 1 }`, trate `RequestFileTooLargeError` e confira os bytes.
- **C17 Limitar respostas de API** — o schema de `response` serializa só os campos declarados (fast-json-stringify): use em toda rota que devolve usuário.
- **C18 Security headers** — `await app.register(helmet)` (o `@fastify/helmet` usa o helmet: mesmos headers, sem `Permissions-Policy`).
- **C20 Scan de dependências** — Fastify abaixo de 5.3.2 (ou 4.29.1) deixava contornar a validação do body com `Content-Type` malformado (CVE-2025-32442).

## NestJS

**O que vai para o cliente**
- Exceção desconhecida vira `{ "statusCode": 500, "message": "Internal server error" }` (seguro); a mensagem de `HttpException` e as do class-validator saem como estão. `SwaggerModule.setup` publica o mapa da API.

**Onde olhar primeiro**
- `main.ts` (`useGlobalPipes`, helmet, `enableCors`, Swagger, `trust proxy`), `app.module.ts` (`APP_GUARD`, `ThrottlerModule`, `GraphQLModule`), `*.controller.ts` (`@UseGuards`, `@Public()`, `@Body()`), `*.dto.ts`, `*.entity.ts` (`@Exclude()`), guards e strategies (`jwt.strategy.ts`).

**Sinais do scanner**
- `nest_validationpipe_sem_whitelist` (`new ValidationPipe()` sem opções) → C08 · `swagger_publico` → C15 · `rota_sem_auth_aparente` em controller (`@Controller` com `@Get`/`@Post`) → C06 · `graphql_sem_limite` com `@nestjs/graphql` → C17 · `@nestjs/throttler` e `ThrottlerGuard` contam como rate limit (C11).
- Limites: `@UseGuards(...)`/`AuthGuard(...)` contam como auth no arquivo, e com guard global (`provide: APP_GUARD`) as controllers contam como protegidas (`checks.C06.sinais.auth_global`). Confira quais métodos têm `@Public()` e o que o guard aceita. `app.enableCors()` sem opções (= `*`) dispara `cors_sem_opcoes`.

**Correções por checagem**
- **C06 Auth server-side** — guard global para rota nova nascer privada: `{ provide: APP_GUARD, useClass: JwtAuthGuard }` e `@Public()` (lido pelo `Reflector`) só nas públicas.
- **C07 Restringir acessos** — guard de papel lendo o papel do token ou do banco, nunca do body; filtro por dono no service (`where: { id, ownerId: user.id }`). CORS com `app.enableCors({ origin: ["https://meuapp.com.br"], credentials: true })`.
- **C08 Bloquear Mass Assignment** — `app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }))`; DTO aninhado precisa de `@ValidateNested()` + `@Type(() => X)`. O Nest 12 também aceita Standard Schema (zod, valibot) nos decorators de rota (confira a sintaxe na doc da versão).
- **C11 Rate limit** — `ttl` em milissegundos (v5+). Storage padrão em memória: com várias instâncias, use um storage Redis da comunidade (ex.: `@nest-lab/throttler-storage-redis`; confira se já suporta o Nest 12). Atrás de proxy: `app.set("trust proxy", ...)` (Express) ou `trustProxy` no `FastifyAdapter`.
  ```ts
  @Module({
    imports: [ThrottlerModule.forRoot([{ ttl: 60_000, limit: 100 }])],
    providers: [{ provide: APP_GUARD, useClass: ThrottlerGuard }],
  })
  export class AppModule {}
  // login e IA: @Throttle({ default: { limit: 5, ttl: 60_000 } }) no método
  ```
- **C15 Evitar vazamento de conteúdo** — Swagger só fora de produção ou atrás de auth; nunca `throw new HttpException(err.message, 500)` com erro do banco.
- **C17 Limitar respostas de API** — `ClassSerializerInterceptor` global + `@Exclude()` em `passwordHash` e tokens, ou DTO de resposta.
- **C18 Security headers** — `app.use(helmet())` (Express) ou `await app.register(helmet)` com `@fastify/helmet`, antes das rotas: registrado depois, não vale para elas.

## Hono

**O que vai para o cliente**
- Sem código; `c.json(obj)` devolve o objeto inteiro. Roda em Workers, Bun, Node, Deno e Vercel: segredo vem de `c.env` (Workers) ou de `process.env`/`Bun.env`.

**Onde olhar primeiro**
- `src/index.ts` (`new Hono()`, ordem dos `app.use`), `app.route("/x", sub)`, middlewares (`jwt`, `bearerAuth`, `cors`, `csrf`, `secureHeaders`, `bodyLimit`), validadores (`zValidator`) e `app.onError`.

**Sinais do scanner**
- `cors_sem_opcoes` (`cors()` libera `*`) → C07 · `objeto_usuario_inteiro` (`c.json(user)`) → C17 · `headers_pelo_framework` (`secureHeaders(` sem header escrito no código) → C18 · `hono-rate-limiter` conta como rate limit (C11) e `zValidator` como validação (C14).
- Limites: `jwt()`, `bearerAuth()`, `basicAuth()` e `jwtPayload` contam como auth no arquivo. Auth aplicada num `app.use` de outro arquivo ainda gera `rota_sem_auth_aparente`: confira o caminho que o middleware cobre.

**Correções por checagem**
- **C06 Auth server-side** — `alg` é obrigatório no `jwt()`, e `iss` só é conferido se você passar a opção. Hono abaixo de 4.11.4 aceitava o `alg` vindo do token no JWT/JWK (CVE-2026-22817 e CVE-2026-22818).
  ```ts
  import { jwt } from "hono/jwt";
  app.use("/api/*", (c, next) => jwt({ secret: c.env.JWT_SECRET, alg: "HS256" })(c, next)); // Workers: env só na requisição
  app.get("/api/me", (c) => c.json({ id: c.get("jwtPayload").sub }));
  ```
- **C07 Restringir acessos** — `cors({ origin: ["https://meuapp.com.br"], credentials: true })`: o padrão é `origin: "*"`.
- **C09 Proteger cookies** — `setCookie(c, "session", token, { httpOnly: true, secure: true, sameSite: "Lax", path: "/" })` (`hono/cookie`); sessão em cookie com formulário: `csrf()` confere `Origin` e `Sec-Fetch-Site`.
- **C11 Rate limit** — `hono-rate-limiter` (comunidade, storage via unstorage) ou, no Workers, o binding de Rate Limiting (ver [Cloudflare Workers](#cloudflare-workers)).
- **C14 Validação dos inputs** — `zValidator("json", z.strictObject({...}))` e `c.req.valid("json")`; `bodyLimit({ maxSize: 1024 * 1024 })`. No Bun, o `Bun.serve` aceita até 128 MiB por padrão: ajuste `maxRequestBodySize`.
- **C15 Evitar vazamento de conteúdo** — `app.onError((err, c) => { console.error(err); return c.json({ error: "Erro interno" }, 500); })`: não devolva `err.message`.
- **C18 Security headers** — `secureHeaders()` não manda CSP nem `Permissions-Policy`:
  ```ts
  app.use("*", secureHeaders({ contentSecurityPolicy: { defaultSrc: ["'self'"], frameAncestors: ["'none'"] } }));
  app.use("*", async (c, next) => { await next(); c.header("Permissions-Policy", "camera=(), microphone=(), geolocation=()"); });
  ```

## Koa

**O que vai para o cliente**
- Sem código. Erro 5xx sem `expose` sai como "Internal Server Error"; middleware de erro próprio que devolve `err.message` vaza.

**Onde olhar primeiro**
- `app.ts`: `app.proxy`, `app.maxIpsCount`, ordem dos middlewares (erro primeiro; depois helmet, cors, bodyparser, rate limit, auth e router), rotas do `@koa/router`, `ctx.request.body` e `ctx.state.user`.

**Sinais do scanner**
- Rotas `router.get('/...')` entram como `http-router`; `ctx.request.body` conta como input; `koa-ratelimit` conta como rate limit (C11).
- Limites: `ctx.state.user` (koa-jwt, passport) conta como auth no arquivo; middleware em outro arquivo ainda gera falso positivo. `koa-helmet` conta como helmet.

**Correções por checagem**
- **C06 Auth server-side** — `koa-jwt` ou middleware próprio com `jwtVerify` do `jose` (algoritmos fixos) antes do router privado; `.unless({ path: [...] })` só para as rotas públicas listadas.
- **C07 Restringir acessos** — `@koa/cors` 5: o padrão é `*`, e com `credentials: true` sem `origin` ele devolve a origem de quem pediu. Passe uma função de allowlist.
- **C11 Rate limit** — `koa-ratelimit` com `driver: "redis"` em produção. Atrás de proxy, `app.proxy = true` e `app.maxIpsCount` igual ao número de proxies (sem isso, o IP do `X-Forwarded-For` é forjável).
- **C14 Validação dos inputs** — zod no `ctx.request.body` e limite de tamanho no parser (`jsonLimit`; no `koa-body`, também `formidable.maxFileSize`).
- **C15 Evitar vazamento de conteúdo** — middleware de erro primeiro:
  ```ts
  app.use(async (ctx, next) => {
    try { await next(); }
    catch (err) {
      ctx.status = err.status ?? 500;
      ctx.body = { error: err.expose ? err.message : "Erro interno" };
      ctx.app.emit("error", err, ctx); // log
    }
  });
  ```
- **C18 Security headers** — `koa-helmet` (com `helmet` instalado) e `Permissions-Policy` à mão.

## Elysia e Bun

**O que vai para o cliente**
- Sem código; o objeto devolvido pelo handler sai inteiro. Trate erro no `onError` e devolva texto genérico em 5xx.

**Onde olhar primeiro**
- `new Elysia()` e a ordem de `.use()`, `.derive()`/`.resolve()` e hooks (`onBeforeHandle`, `.guard()`): hook só vale para as rotas registradas depois dele, exceto `onRequest`, que é global. Schemas `t.*` por rota, limite de corpo do `Bun.serve`, `bun:sqlite` e `Bun.sql`.

**Sinais do scanner**
- Rotas `new Elysia().get("/...")` entram como `http-router`; `jwt.verify` (de `@elysiajs/jwt`) conta como auth e `t.Object` como validação. `sql_template_interpolado` (C13) pega ``sql.unsafe(`... ${x}`)`` e ``db.query(`... ${x}`)``.
- Limites: o scanner não vê a ordem dos hooks (rota declarada antes do hook de auth fica pública). Com `elysia` no `package.json`, a validação embutida (TypeBox) conta como lib de validação.

**Correções por checagem**
- **C06 Auth server-side** — rota pública antes do hook, privada depois:
  ```ts
  new Elysia()
    .use(jwt({ name: "jwt", secret: Bun.env.JWT_SECRET! }))
    .get("/health", () => "ok")                                   // pública
    .derive(async ({ jwt, headers }) => ({ user: await jwt.verify(headers.authorization?.slice(7)) }))
    .onBeforeHandle(({ user, status }) => { if (!user) return status(401); })
    .get("/me", ({ user }) => ({ id: user.sub }));                // privada: depois do hook
  ```
- **C08 Bloquear Mass Assignment** — `body: t.Object({...})` em toda rota que escreve; com `normalize` no padrão, o Elysia tira campo fora do schema, e com `normalize: false` passa a recusar (confira na doc da versão).
- **C10 Hash nas senhas** — `Bun.password.hash(senha)` (Argon2 por padrão) e `Bun.password.verify(senha, hash)`.
- **C11 Rate limit** — `elysia-rate-limit` (comunidade; confira a versão compatível com o seu Elysia) ou limite no edge.
- **C13 Queries parametrizadas** — `Bun.sql` só como template tag (``sql`select id, nome from users where id = ${id}` ``) e `bun:sqlite` com `?` (`db.query("select ... where id = ?").get(id)`); nunca `sql.unsafe` com input.
- **C16 Restringir uploads** — o `Bun.serve` aceita até 128 MiB por padrão: reduza `maxRequestBodySize` (no Elysia, pela opção `serve`; confira na doc da versão). `t.File` com `type` e `maxSize`, e confira os bytes.
- **C18 Security headers** — `onRequest` vale para todas as rotas: `.onRequest(({ set }) => { set.headers["x-content-type-options"] = "nosniff"; set.headers["x-frame-options"] = "DENY"; })`, mais CSP e `Permissions-Policy`.

## AdonisJS

**O que vai para o cliente**
- Sem código; o model Lucid serializado sai inteiro em `return user`, menos as colunas com `serializeAs: null`.

**Onde olhar primeiro**
- `start/routes.ts` (`.use(middleware.auth())` por rota ou grupo), `start/kernel.ts`, `config/shield.ts`, `config/cors.ts`, `config/session.ts`, `start/limiter.ts`, `app/controllers/**` (`request.all()`, `validateUsing`), `app/validators/**` (VineJS), `app/models/**` e `app/policies/**` (Bouncer).

**Sinais do scanner**
- Rotas `router.get('/...')` do `start/routes.ts` entram como `http-router` e `middleware.auth()` conta como auth. O Adonis tem validação nativa: `sem_lib_de_validacao` não dispara.
- Limites: `Model.create(request.all())` vira `adonis_request_all` (C08); `@adonisjs/limiter` e `@adonisjs/validator` contam; controllers não entram na lista de rotas.

**Correções por checagem**
- **C06 Auth server-side** — grupo privado com `.use(middleware.auth())` no `start/routes.ts`; rota fora do grupo é pública.
- **C07 Restringir acessos** — Bouncer (`@adonisjs/bouncer`): `await bouncer.authorize("editarPost", post)` ou policy; consulta filtrada por `auth.user!.id`.
- **C08 Bloquear Mass Assignment** — `const data = await request.validateUsing(criarPostValidator)` e o model recebe `data`, nunca `request.all()` (no máximo `request.only([...])`).
- **C09 Proteger cookies** — o `config/session.ts` do starter já vem com `httpOnly: true`, `secure: app.inProduction` e `sameSite: "lax"`: confira se ninguém mudou. CSRF do Shield ligado para sessão por cookie.
- **C10 Hash nas senhas** — o padrão é scrypt (`config/hash.ts`); argon2 e bcrypt pedem pacote próprio. Coluna da senha com `@column({ serializeAs: null })`.
- **C11 Rate limit** — `@adonisjs/limiter` com store `redis` em produção (`LIMITER_STORE`):
  ```ts
  // start/limiter.ts
  export const throttle = limiter.define("login", () => limiter.allowRequests(5).every("1 minute"));
  // start/routes.ts
  router.post("/login", [SessionController, "store"]).use(throttle);
  ```
- **C16 Restringir uploads** — `request.file("avatar", { size: "2mb", extnames: ["jpg", "png", "webp"] })` (ou `vine.file`) e nome gerado no servidor; extensão não prova conteúdo, confira os bytes.
- **C17 Limitar respostas de API** — `serializeAs: null` em senha e tokens; devolva DTO explícito em vez do model.
- **C18 Security headers** — guarda que não está no `config/shield.ts` fica desligada, e a CSP vem desligada: ligue `csp`, `hsts`, `xFrame` e `contentTypeSniffing`.

## tRPC

**O que vai para o cliente**
- O retorno de cada procedure, sem filtro. Erro que não é `TRPCError` vira `INTERNAL_SERVER_ERROR` com a mensagem original; o `stack` só sai em desenvolvimento.

**Onde olhar primeiro**
- `initTRPC` (`errorFormatter`), `createContext` (de onde vem `ctx.user`), definição de `publicProcedure`/`protectedProcedure`, routers (`*.router.ts`) e o adapter (`app/api/trpc/[trpc]/route.ts`, `pages/api/trpc/[trpc].ts`, `createExpressMiddleware`, `fetchRequestHandler`).

**Sinais do scanner**
- `trpc_mutation_publica` (mutation em `publicProcedure`) → C06; `protectedProcedure` e `authedProcedure` contam como auth.
- Limites: só o arquivo do adapter vira rota; cada procedure pede revisão manual de C06, C07, C14 e C17.

**Correções por checagem**
- **C06 Auth server-side** — `createContext` valida o token (`jwtVerify`, `getUser()`), não só decodifica; procedure privada parte de:
  ```ts
  export const protectedProcedure = t.procedure.use(({ ctx, next }) => {
    if (!ctx.user) throw new TRPCError({ code: "UNAUTHORIZED" });
    return next({ ctx: { user: ctx.user } });
  });
  ```
- **C07 Restringir acessos** — o `input` traz o id do recurso, o dono vem de `ctx.user.id`; mutation administrativa com middleware de papel.
- **C08 Bloquear Mass Assignment** — `z.object` no `.input()` descarta campo extra, mas `z.any()`, `z.record()` e `z.looseObject()` repassam tudo.
- **C11 Rate limit** — no middleware da procedure (chave `ctx.user.id`): uma requisição HTTP em batch carrega várias chamadas. Limite o batch no handler (`maxBatchSize`, v11; confira na doc da versão).
- **C14 Validação dos inputs** — `.input(schema)` em toda procedure, inclusive query.
- **C15 Evitar vazamento de conteúdo** — `errorFormatter` troca a mensagem de `INTERNAL_SERVER_ERROR` por texto genérico e tira o `stack`; o log completo fica no `onError`.
- **C17 Limitar respostas de API** — `.output(schema)` ou DTO no retorno.

## GraphQL (Apollo, Yoga, Mercurius)

**O que vai para o cliente**
- O schema inteiro, via introspection: o Apollo liga quando `NODE_ENV` não é `production`; o Yoga liga por padrão. Erros: o Apollo põe stacktrace fora de `production`/`test`; o Yoga mascara erro inesperado ("Unexpected error."). GraphiQL: no Yoga, só em desenvolvimento; no Mercurius, só com `graphiql: true`.

**Onde olhar primeiro**
- Criação do servidor (`new ApolloServer`, `createYoga`, `app.register(mercurius)`, `GraphQLModule.forRoot`), função `context` (token verificado?), resolvers de `Query`, `Mutation` e de campo, DataLoaders e `typeDefs` (tipo `User` com `email`, `passwordHash`).

**Sinais do scanner**
- `graphql_sem_limite` (nenhuma lib de profundidade ou custo no `package.json`), `graphql_introspection` (`introspection: true`) → C17.
- Limites: resolvers não entram na lista de rotas (C06, C07 e C14 são manuais); introspection ligada por padrão (Yoga, ou Apollo sem `NODE_ENV`) não é acusada; `queryDepth`/`depthLimit` no código contam como limite.

**Correções por checagem**
- **C06 Auth server-side** — `context` monta o usuário a partir do token verificado; cada resolver de dado privado checa `ctx.user`. Apollo: mantenha `csrfPrevention` (padrão ligado).
- **C07 Restringir acessos** — autorização no resolver ou no campo, não só no gateway; `node(id)` e `byId` filtram por dono. DataLoader criado por requisição, dentro do `context`: cache global mistura dados de usuários.
- **C08 Bloquear Mass Assignment** — não espalhe `args.input` no ORM se o input type tem `role` ou `ownerId`.
- **C11 Rate limit** — aliases e batching multiplicam operações num POST só (força bruta de `login` com 100 aliases): limite aliases e custo, e faça rate limit por operação e usuário. No Apollo, `allowBatchedHttpRequests` fica `false`.
- **C15 Evitar vazamento de conteúdo** — Apollo com `NODE_ENV=production` (ou `introspection: false` e `includeStacktraceInErrorResponses: false` explícitos) e `formatError` para mascarar. Yoga: mantenha `maskedErrors`; erro destinado ao cliente é `GraphQLError`.
- **C17 Limitar respostas de API** — profundidade, custo e aliases com GraphQL Armor. Yoga: `plugins: [EnvelopArmorPlugin(), useDisableIntrospection()]` (`@graphql-yoga/plugin-disable-introspection`). Mercurius: `queryDepth: 10`, `graphiql: false` e `validationRules: [NoSchemaIntrospectionCustomRule]` (do pacote `graphql`). Campo de lista com `first`/`limit` máximo.
  ```ts
  import { ApolloArmor } from "@escape.tech/graphql-armor";
  const protecao = new ApolloArmor().protect(); // profundidade, aliases, custo, tokens
  const server = new ApolloServer({ typeDefs, resolvers,
    plugins: [...protecao.plugins], validationRules: [...protecao.validationRules],
    introspection: process.env.NODE_ENV !== "production" });
  ```
- **C20 Scan de dependências** — Apollo Server 4 está sem suporte desde 26/01/2026: Apollo 5 com `@as-integrations/express5` (ou `express4`); o import `@apollo/server/express4` saiu no 5.

## Vercel e Netlify Functions

**O que vai para o cliente**
- A função não vai para o navegador, mas mora no mesmo projeto do front: variável com `NEXT_PUBLIC_`/`VITE_` continua pública. O preview roda com as variáveis do ambiente Preview; se forem as de produção, o preview mexe em produção.

**Onde olhar primeiro**
- Vercel: `api/**` (fora do Next), `vercel.json` (`headers`, `crons`, `functions`), variáveis por ambiente (Production, Preview, Development), Deployment Protection dos previews e o `.env.local` criado por `vercel env pull`.
- Netlify: `netlify/functions/**` (`export const config` com `path` e `rateLimit`), `netlify/edge-functions/**`, `netlify.toml` (`[[headers]]`) e variáveis marcadas como secretas.

**Sinais do scanner**
- `netlify/functions/**` e qualquer arquivo JS/TS em `api/` (inclusive aninhado, como `api/users/[id].ts`, e `.mts`) viram rota `serverless-function` · `cron_a_cada_minuto` (`vercel.json`) → P10 · `vercel.json`, `netlify.toml` e `_headers` contam como headers no código (C18).
- Limites: contador de rate limit em memória dentro da função não é acusado (e não vale entre instâncias).

**Correções por checagem**
- **C01 Esconder API Keys** — segredo só como variável sem prefixo público, no ambiente certo; na Vercel, marque como Sensitive.
- **C02 Limpar secrets do Git** — o `.env.local` do `vercel env pull` fica no `.gitignore`.
- **C06 Auth server-side** — cada função valida sessão ou token no início; webhook confere a assinatura com o corpo cru. Preview protegido pela Deployment Protection (Standard Protection cobre tudo menos o domínio de produção).
- **C11 Rate limit** — Vercel: `checkRateLimit("id-da-regra", { request, rateLimitKey: user.id })` do `@vercel/firewall`, com a regra criada no Firewall (contador por região), ou Upstash. Netlify, no arquivo da function (janela de até 180 s; não dá para declarar no `netlify.toml`):
  ```ts
  export const config: Config = {
    path: "/api/chat",
    rateLimit: { windowLimit: 20, windowSize: 60, aggregateBy: ["ip", "domain"] },
  };
  ```
- **C15 Evitar vazamento de conteúdo** — Vercel: Protected Source Maps se precisar publicar `.map`. Netlify: variável marcada como secreta faz o build falhar se o valor aparecer no código ou na saída (Secrets Controller); não desligue o scan para o build passar.
- **C18 Security headers** — `headers` no `vercel.json` (modelo em `front-e-mobile.md`) ou `[[headers]]` no `netlify.toml`/`_headers`; a própria função também pode mandá-los na resposta.
- **C19 Forçar HTTPS** — HTTPS e HSTS vêm prontos nas duas plataformas; confira o certificado do domínio próprio.

## Cloudflare Workers

**O que vai para o cliente**
- Sem código. Mas `vars` do `wrangler.toml`/`wrangler.jsonc` ficam em texto no repositório e no painel: segredo é `wrangler secret put`.

**Onde olhar primeiro**
- `wrangler.toml`/`wrangler.jsonc` (`vars`, bindings `d1_databases`, `kv_namespaces`, `r2_buckets`, `ratelimits`, `routes`), `.dev.vars`/`.env` locais, `src/index.ts` (`export default { fetch }` ou Hono) e os static assets com `_headers`.

**Sinais do scanner**
- `export default { fetch }` vira rota `worker` · segredo em `vars` aparece pelos padrões de chave e por `generic_assignment` (C01) · `.dev.vars` versionado cai em `arquivo_sensivel_rastreado` (C02) · `sql_template_interpolado` pega ``env.DB.prepare(`... ${x}`)`` (C13).
- Limites: app Hono exportado como `export default app` não vira `worker` (entra como `http-router` se tiver `app.get('/...')`); o binding de Rate Limiting (`ratelimits` no wrangler) conta como rate limit.

**Correções por checagem**
- **C01 Esconder API Keys** — `npx wrangler secret put OPENAI_API_KEY`; `vars` só para config pública.
- **C02 Limpar secrets do Git** — `.dev.vars*` e `.env*` no `.gitignore`.
- **C07 Restringir acessos** — cada Worker com o mínimo de bindings (só o D1, KV ou R2 que ele usa); bucket R2 público só para arquivo público.
- **C11 Rate limit** — binding de Rate Limiting (Wrangler 4.36+); o limite é aproximado e por local da Cloudflare (para limite exato, Durable Object). Chave por usuário ou rota, não só IP.
  ```jsonc
  "ratelimits": [{ "name": "LIMITE_IA", "namespace_id": "1001", "simple": { "limit": 20, "period": 60 } }]
  ```
  ```ts
  const { success } = await env.LIMITE_IA.limit({ key: userId }); // period: 10 ou 60 s
  if (!success) return new Response("Muitas requisições", { status: 429 });
  ```
- **C12 Bot protection** — Turnstile com `siteverify` no Worker (modelo no `checks.md`).
- **C13 Queries parametrizadas** — D1: `env.DB.prepare("select ... where id = ?").bind(id)`.
- **C18 Security headers** — o Worker não manda header de segurança sozinho: monte na `Response` (ou `secureHeaders` do Hono); static assets aceitam arquivo `_headers`.

## AWS Lambda

**O que vai para o cliente**
- Sem código. A variável de ambiente da função aparece em texto para quem tem `lambda:GetFunctionConfiguration` (console, CLI): não é cofre.

**Onde olhar primeiro**
- `serverless.yml`, `template.yaml` (SAM), CDK ou Terraform: `environment`, role IAM, Function URL (`AuthType`), authorizers e throttling do API Gateway; handlers (`exports.handler`, `export const handler`) e o uso de `event.body`.

**Sinais do scanner**
- Handler que lê `event.body`, `queryStringParameters` ou `pathParameters` vira rota `lambda` · `config_com_segredo` e os padrões de chave pegam segredo em `serverless.yml`/`template.yaml` (C01).
- Limites: authorizer, throttling, Function URL e IAM ficam na infra; confira no template ou no console (só leitura).

**Correções por checagem**
- **C01 Esconder API Keys** — segredo no Secrets Manager ou em SSM `SecureString`, lido em runtime: `getSecret("nome")` de `@aws-lambda-powertools/parameters/secrets` (cache de 5 s por padrão) ou a extensão Parameters and Secrets. A variável guarda só o nome ou o ARN.
- **C06 Auth server-side** — authorizer no API Gateway (JWT, Cognito ou Lambda) e checagem no handler. Function URL com `AuthType: NONE` é pública e não passa pelo authorizer nem pelo throttling do API Gateway.
- **C07 Restringir acessos** — role da função com ações e recursos específicos, sem `"*"`; `secretsmanager:GetSecretValue` só no ARN do segredo.
- **C11 Rate limit** — throttling por stage e rota no API Gateway e usage plan; WAF só em REST API, ALB ou CloudFront (HTTP API não aceita WAF).
- **C14 Validação dos inputs** — `event.body` chega como string (base64 se `isBase64Encoded`): `JSON.parse` e schema (`@aws-lambda-powertools/parser` usa zod).
- **C15 Evitar vazamento de conteúdo** — log no CloudWatch sem token nem CPF; resposta de erro genérica no `body`.
- **C18 Security headers** — headers no objeto de resposta, ou Response Headers Policy no CloudFront (há política gerenciada de security headers).

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
