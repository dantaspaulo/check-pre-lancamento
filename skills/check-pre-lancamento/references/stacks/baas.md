<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# BaaS e auth gerenciada · onde olhar e como corrigir

Referência para o agente que audita apps em Supabase, Firebase, Convex, PocketBase, Appwrite e auth gerenciada (Clerk, Auth0, Auth.js, Better Auth): onde a proteção mora em cada plataforma, o que o `scan.py` sinaliza e a correção certa. O critério de FALHA/ATENÇÃO/OK/N/A continua no `checks.md`, que já cobre o básico de RLS e de regras do Firebase; aqui fica o que vai além.

**Stacks:** [Supabase](#supabase) · [Firebase](#firebase) · [Convex](#convex) · [PocketBase](#pocketbase) · [Appwrite](#appwrite) · [Clerk, Auth0, Auth.js e Better Auth](#clerk-auth0-authjs-e-better-auth)

**C04 em BaaS.** No placar, C04 "Ativar RLS" cobre a camada que decide quem lê e escreve cada registro quando o cliente fala direto com o backend: RLS no Supabase, Security Rules no Firebase (Firestore, Realtime Database e Storage), API rules no PocketBase e permissões no Appwrite. O Convex não tem regra declarativa: a checagem fica dentro de cada função pública (C06/C07), e C04 é N/A com essa justificativa.

## Supabase

**Onde olhar primeiro**
- `supabase/migrations/*.sql`: `enable row level security`, `create policy`, `grant`/`revoke`, funções `security definer`, views, `insert into storage.buckets` e policies em `storage.objects`.
- `supabase/config.toml`: `[auth]`, `[auth.email]`, `[auth.rate_limit]`, `[auth.captcha]`, `[auth.email.smtp]`, `[functions.<nome>] verify_jwt`, `[api] schemas` e `max_rows`. Ele descreve o ambiente local; produção só bate com ele se o projeto usa `supabase config push` (ou branching). Confirme no painel.
- `supabase/functions/*/index.ts` (como cada Edge Function identifica quem chama) e `supabase/tests/*.sql` (testes pgTAP).
- Clientes: `lib/supabase*` e todo `createClient(...)`, vendo qual chave usa e em que lado roda (C03).
- Painel: Security Advisor; Authentication (provedores, rate limits, SMTP, senhas, CAPTCHA); Storage (policies e buckets); configurações da API (schemas expostos, Data API); API keys; Database (SSL e restrição de rede).

**Sinais do scanner**
- `tabela_sem_rls`, `rls_desativado`, `policy_permissiva`, `security_definer`, `view_sem_security_invoker`, `grant_para_anon` → C04 · `policy_usa_user_metadata`, `user_metadata_para_papel` → C07
- `service_role_jwt`, `supabase_secret_key`, `public_env_service_role`, `service_role_in_client` → C03 · `supabase_secret`, `supabase_pat` → C01
- `edge_function_sem_jwt`, `getSession_no_servidor` → C06 · `senha_minima_curta` → C10 · `postgrest_filtro_string` → C13 · `bucket_publico`, `bucket_publico_sql` → C16
- `select_estrela`, `select_estrela_sem_limite` → C17 · `supabase_smtp_padrao` → P06 · sinais `C04.rls_nao_verificavel_pelo_repo`, `C06.supabase_confirmacao_email_desligada`, `C12.supabase_captcha_config`
- Limites: sem migrations no repo, o estado real só aparece no banco (queries do `checks.md`), no Security Advisor ou via MCP. `edge_function_sem_jwt` só vê `verify_jwt = false`, mas função com `verify_jwt = true` também pode estar aberta (ver C06). Tabela que segue com os grants padrão de `anon` e policy sem `to` não são sinalizadas.

**Correções por checagem**
- **C03 Usar apenas Public Key no DB** — cliente só com `sb_publishable_` (ou o `anon` legado); `sb_secret_` e `service_role` só no servidor. As chaves legadas (`anon`/`service_role`, que são JWT) estão sendo descontinuadas até o fim de 2026: migre para as novas e desative as legadas no painel.
- **C04 Ativar RLS** — o RLS filtra linhas, mas é o grant que decide se a operação roda. Em projeto antigo, tabela nova no `public` nasce com todos os privilégios para `anon` e `authenticated`, e policy não retira grant. Padrão por tabela:
  ```sql
  alter table public.docs enable row level security;
  revoke all on table public.docs from anon, authenticated;
  grant select, insert, update, delete on table public.docs to authenticated;
  create policy docs_select on public.docs for select to authenticated
    using ((select auth.uid()) = owner_id);
  create index on public.docs (owner_id);
  ```
  - Uma policy por operação (nada de `for all`), sempre com `to authenticated` ou `to anon`; sem `to`, vale para `public`, que inclui o visitante. Use `(select auth.uid())` e índice na coluna da policy.
  - Login anônimo usa o papel `authenticated`. Com `enable_anonymous_sign_ins` ligado, barre com policy restritiva: `create policy so_conta_real on public.docs as restrictive for insert to authenticated with check ((select (auth.jwt()->>'is_anonymous')::boolean) is false);`
  - Multi-tenant e papéis: a checagem de membro vai numa função `security definer` em schema não exposto (`private`). Policy que lê a tabela protegida pela outra cai em `infinite recursion detected in policy` (42P17).
  - `security definer`: `set search_path = ''`, nomes qualificados (`public.tabela`) e nunca em schema exposto, onde vira RPC com o poder do dono. Revogue o execute padrão (`revoke execute on function private.f() from public, anon, authenticated;`) e dê só a quem usa.
  - Views: `create view ... with (security_invoker = true)` (Postgres 15+); sem isso, a view entrega as linhas que a policy esconderia. Materialized view não tem RLS: tire do schema exposto.
  - Coluna: RLS é por linha. Para esconder coluna, revogue o `select` dela ou mova para outra tabela; para travar edição, veja C08.
  - Realtime: Postgres Changes respeita o RLS; Broadcast e Presence em canal privado dependem de policy em `realtime.messages`.
  - Prova: testes pgTAP em `supabase/tests/`, rodados com `supabase test db`, com allow e deny por operação para `anon` e `authenticated`.
  - Security Advisor (painel, `supabase db advisors` ou `get_advisors` com `type: "security"` no MCP). Pesam: 0013 `rls_disabled_in_public`, 0007 `policy_exists_rls_disabled`, 0024 `permissive_rls_policy`, 0015 `rls_references_user_metadata`, 0010 `security_definer_view`, 0011 `function_search_path_mutable`, 0028/0029 `anon_`/`authenticated_security_definer_function_executable`, 0002 `auth_users_exposed`, 0023 `sensitive_columns_exposed`, 0025 `public_bucket_allows_listing`, 0012 `auth_allow_anonymous_sign_ins`.
  - Schemas expostos: só `public` (e `graphql_public` se usa GraphQL); sem uso da Data API, desligue-a.
- **C06 Auth server-side** — `verify_jwt = true` (padrão) só barra quem não manda credencial: por compatibilidade, aceita também as chaves publishable e secret, e a publishable está no seu site. Dentro da função, identifique o usuário:
  ```ts
  import { withSupabase } from "npm:@supabase/server@1";
  export default {
    fetch: withSupabase({ auth: "user" }, async (_req, ctx) => {
      const { data } = await ctx.supabase.from("docs").select("id,title"); // com o RLS do usuário
      return Response.json(data);
    }),
  };
  ```
  Sem o pacote: `supabase.auth.getClaims(token)` ou `getUser(token)`, e 401 se falhar. `verify_jwt = false` só para webhook com assinatura (`stripe.webhooks.constructEventAsync`), cron ou serviço com `sb_secret_` no header `apikey` (`auth: "secret"`) e rota pública de verdade. `ctx.supabaseAdmin` ignora o RLS: filtre pelo id do usuário. No servidor (SSR), `getClaims()` ou `getUser()`, nunca `getSession()`.
  - Auth: `enable_confirmations = true` (no `config.toml` local vem `false`; confira o painel), `secure_password_change = true`, `enable_signup = false` se o cadastro é só por convite, `additional_redirect_urls` com URLs exatas (curinga largo vira open redirect), `jwt_expiry` de 3600 ou menos e MFA para conta admin.
- **C07 Restringir acessos** — papel em `app_metadata` (só o servidor altera), lido no SQL com `auth.jwt() -> 'app_metadata' ->> 'role'`; `user_metadata` e `raw_user_meta_data` o próprio usuário muda com `updateUser({ data })`. Papel que muda com frequência: tabela `user_roles` + Custom Access Token Hook.
- **C08 Bloquear Mass Assignment** — o RLS não impede trocar coluna: `revoke update on public.profiles from authenticated; grant update (name, bio, avatar_url) on public.profiles to authenticated;` ou trigger `before update` que recusa mudança em `role`, `plan` e `credits`.
- **C10 Hash nas senhas** — o Auth faz o hash; falta a política: `minimum_password_length` ≥ 8 (padrão 6) e `password_requirements = "lower_upper_letters_digits"` ou mais forte. A checagem de senha vazada (HaveIBeenPwned) só existe do plano Pro para cima: no Free, ATENÇÃO.
- **C11 Rate limit** — o Auth já limita os próprios endpoints (`[auth.rate_limit]`: `email_sent`, `sms_sent`, `sign_in_sign_ups`, `token_verifications`, `token_refresh`, `anonymous_users`; no painel, Rate Limits). Edge Function e RPC não têm limite: Upstash/Redis dentro da função ou WAF na frente.
- **C12 Bot protection** — `[auth.captcha]` com `enabled = true`, `provider = "turnstile"` (ou `"hcaptcha"`) e `secret = "env(TURNSTILE_SECRET)"`, mais `options: { captchaToken }` no `signUp`, `signInWithPassword`, `signInWithOtp` e `resetPasswordForEmail`.
- **C13 Queries parametrizadas** — `.or()` e `.filter()` com string montada deixam o usuário injetar filtro: use `.eq`/`.ilike` encadeados, ou valide e escape antes. Em função SQL, `execute format('select ... where id = $1') using id` (identificador com `%I`), nunca `||` com input.
- **C16 Restringir uploads** — policy em `storage.objects`: upload pede `insert`, e `upsert` pede também `select` e `update`:
  ```sql
  create policy "upload na própria pasta" on storage.objects for insert to authenticated
    with check (bucket_id = 'docs' and (storage.foldername(name))[1] = (select auth.uid()::text));
  ```
  Bucket público: qualquer um baixa pela URL e policy de leitura não protege; arquivo privado vai em bucket privado com `createSignedUrl` de expiração curta. Configure `file_size_limit` e `allowed_mime_types` no bucket.
- **C17 Limitar respostas de API** — `select("id,title")` com `.range()`; `[api] max_rows` (padrão 1000) é o teto da Data API: baixe se a tela não precisa de tanto.
- **C19 Forçar HTTPS** — conexão direta ao Postgres com SSL obrigatório e restrição de rede, as duas no painel (Database).
- **P06 E-mail e domínio** — o SMTP padrão só entrega para e-mails do time do projeto, manda 2 mensagens por hora (número que pode mudar sem aviso) e não tem SLA. Com SMTP próprio, o limite começa em 30 por hora e sobe em Rate Limits.

## Firebase

**Onde olhar primeiro**
- `firestore.rules`, `storage.rules`, `database.rules.json` e `firebase.json` (quais regras o deploy usa, `headers` do Hosting). O console pode ter regra publicada diferente da do repo: confira lá.
- `functions/src/**`: `onCall`, `onRequest`, triggers, uso do Admin SDK e `setGlobalOptions`.
- Cliente: `initializeApp`, `initializeAppCheck` e leituras e escritas diretas no Firestore e no Storage.
- Console: App Check (enforcement por produto), Authentication (cadastro, política de senha, proteção contra enumeração de e-mail) e, no Google Cloud, as restrições da chave de API.

**Sinais do scanner**
- `firebase_if_true`, `firebase_sem_condicao`, `firebase_modo_teste`, `rtdb_publico` → C04 · `firebase_admin_in_client` → C03 · `gcp_service_account`, `fcm_server_key` → C01
- `google_api_key` → C01 (chave em config do Firebase sai com confiança baixa: é pública, mas peça a restrição) · sinais `C12.protecao_framework_em` (App Check) e `C12.verificacao_servidor_em` (`enforceAppCheck`, `consumeAppCheckToken`)
- Limites: `if request.auth != null` sozinho vira `firebase_qualquer_logado` (C04, média), porque qualquer pessoa cria conta. `match /{document=**}` com outra condição fraca passa calado. `onCall` e `onRequest` entram como rota e podem cair em `rota_sem_auth_aparente`.

**Correções por checagem**
- **C01 Esconder API Keys** — a chave web (`AIza...`) identifica o projeto e não é segredo, mas restrinja no Google Cloud: restrição de aplicativo (referrer HTTP, bundle ID, pacote Android) e de API (só as que o app usa). Se a mesma chave libera Gemini ou Firebase AI Logic, ela gasta o seu dinheiro: restrinja e exija App Check.
- **C03 Usar apenas Public Key no DB** — o Admin SDK ignora as regras: só em Cloud Functions ou servidor. JSON de service account vazado: crie outra chave e apague a antiga na conta de serviço, no IAM do Google Cloud.
- **C04 Ativar RLS** — no Firebase, C04 são as Security Rules. Regra por dono com campo travado (dentro de `match /databases/{db}/documents`):
  ```
  match /users/{uid} {
    allow read: if request.auth != null && request.auth.uid == uid;
    allow update: if request.auth != null && request.auth.uid == uid
      && !request.resource.data.diff(resource.data).affectedKeys().hasAny(['role', 'plan', 'credits']);
  }
  ```
  - Regras somam (OR): um `match /{document=**} { allow read, write: if request.auth != null; }` abre tudo para qualquer conta, mesmo com regra fina embaixo.
  - `request.auth != null` = qualquer pessoa que se cadastre (o cadastro é aberto pela API com a chave web). Amarre a `uid`, a custom claim definida pelo Admin SDK (`request.auth.token.admin == true`) ou a `request.auth.token.email_verified`.
  - Regra não é filtro: a query do cliente precisa pedir só o que a regra deixa. Valide o formato com `request.resource.data.keys().hasOnly([...])`, `is string` e `.size() <= 80`.
  - Realtime Database: `.read` e `.write` cascateiam (o que o pai libera, o filho não tira); valide com `.validate`.
  - Teste no Emulator com `@firebase/rules-unit-testing` e publique com `firebase deploy --only firestore:rules,storage`.
- **C06 Auth server-side** — `onCall` entrega `request.auth`: `if (!request.auth) throw new HttpsError("unauthenticated", "login necessário")`. `onRequest` é HTTP público: exija `Authorization: Bearer <idToken>` e valide com `getAuth().verifyIdToken(token)` (`firebase-admin/auth`).
- **C10 Hash nas senhas** — o Firebase Auth faz o hash (OK). Ative a política de senha (tamanho mínimo acima do padrão de 6) e confira a proteção contra enumeração de e-mail.
- **C11 Rate limit** — nem regras nem funções limitam por usuário: o App Check reduz automação, `maxInstances` (`setGlobalOptions`) segura o custo e endpoint caro (IA, e-mail) precisa de contador próprio por `uid` (Firestore ou Redis). Ligue alerta de orçamento no Google Cloud.
- **C12 Bot protection** — App Check (reCAPTCHA Enterprise no web, Play Integrity e App Attest no mobile) com enforcement ligado em Firestore, Storage e Functions. Em função: `onCall({ enforceAppCheck: true }, ...)`; endpoint sensível: `consumeAppCheckToken: true` + token de uso limitado no cliente. App Check não substitui auth nem regras.
- **C16 Restringir uploads** — `storage.rules` por dono, tamanho e tipo (dentro de `match /b/{bucket}/o`):
  ```
  match /users/{uid}/{arquivo} {
    allow read: if request.auth != null && request.auth.uid == uid;
    allow write: if request.auth != null && request.auth.uid == uid
      && request.resource.size < 5 * 1024 * 1024
      && request.resource.contentType.matches('image/(png|jpeg|webp)');
  }
  ```
  O `contentType` é o que o cliente declarou: para PDF e arquivo crítico, valide de novo numa função.
- **C18 Security headers** — Hosting: bloco `headers` no `firebase.json` com `"source": "**"`.

## Convex

**Onde olhar primeiro**
- `convex/**/*.ts`: cada `export const x = query/mutation/action/httpAction(...)` é endpoint público; `internalQuery`, `internalMutation` e `internalAction` não são.
- `convex/http.ts` (rotas HTTP públicas no domínio `.convex.site`), `convex/auth.config.ts`, `convex/schema.ts`, `convex/crons.ts` e `convex/convex.config.ts` (componentes).
- Wrappers como `customQuery`/`customMutation` (`convex-helpers`), onde a auth costuma morar.
- Variáveis do deployment (`npx convex env list`) e `CONVEX_DEPLOY_KEY` (segredo de CI).

**Sinais do scanner**
- `convex_funcao_publica_sem_auth` → C06 · `convex_sem_validador` → C14 · `@convex-dev/rate-limiter` conta como rate limit em C11.
- Limites: só são lidas as funções declaradas direto com `query(`, `mutation(` ou `action(`, procurando `ctx.auth`, `getUserIdentity`, `getAuthUserId` ou `requireUser` no corpo. Função feita com wrapper (`authedQuery`, `customMutation`) e `httpAction` não são analisadas: leia o wrapper e cada uso. `query` sem `args` não é sinalizada.

**Correções por checagem**
- **C01 Esconder API Keys** — segredo em variável do deployment (`npx convex env set NOME valor`), lido com `process.env` dentro das funções; `CONVEX_DEPLOY_KEY` fora do repo e do front.
- **C06 Auth server-side** — função pública pode ser chamada por qualquer um: checagem no início de toda `query`, `mutation` e `action` pública, e o que só o backend usa vira `internal*` (scheduler, crons e `ctx.run*` só com funções internas):
  ```ts
  export const remover = mutation({
    args: { id: v.id("docs") },
    handler: async (ctx, { id }) => {
      const identity = await ctx.auth.getUserIdentity();
      if (!identity) throw new Error("não autenticado");
      const doc = await ctx.db.get(id);
      if (doc?.ownerId !== identity.tokenIdentifier) throw new Error("não encontrado");
      await ctx.db.delete(id);
    },
  });
  ```
  Com Convex Auth, `getAuthUserId(ctx)` (`@convex-dev/auth/server`). `httpAction` é público: webhook verifica a assinatura.
- **C07 Restringir acessos** — `v.id("docs")` garante formato e tabela, não dono: carregue e compare, como acima. Nunca aceite `userId` em `args` como identidade.
- **C11 Rate limit** — componente `@convex-dev/rate-limiter`, instalado com `app.use(rateLimiter)` em `convex/convex.config.ts`:
  ```ts
  const rateLimiter = new RateLimiter(components.rateLimiter, {
    enviarMensagem: { kind: "token bucket", rate: 10, period: MINUTE, capacity: 3 },
  });
  // no handler:
  await rateLimiter.limit(ctx, "enviarMensagem", { key: userId, throws: true });
  ```
- **C14 Validação dos inputs** — `args` com validador em toda função pública (sem `args`, ela aceita qualquer valor) e `returns` para fixar o formato da saída.
- **C17 Limitar respostas de API** — `.collect()` só para poucos resultados; índice + `.take(n)` ou `.paginate(opts)`, devolvendo só os campos que a tela usa (retornar `doc` entrega o documento inteiro).

## PocketBase

**Onde olhar primeiro**
- `pb_migrations/*.js` e `pb_schema.json`: `listRule`, `viewRule`, `createRule`, `updateRule`, `deleteRule` e, em coleção de auth, `manageRule`.
- `pb_hooks/*.pb.js`: rotas próprias (`routerAdd`) e hooks.
- Painel `/_/`: API Rules de cada coleção, Settings → Application (rate limiting e IP real atrás de proxy), Settings → Backups, MFA e OTP do `_superusers`.
- `pb_data/` (banco SQLite e uploads): nunca no repo.

**Sinais do scanner**
- `pocketbase_regra_publica` → C04 (regra `""` em migration ou schema) · `arquivo_sensivel_rastreado` (`*.db` versionado) → C02
- Limites: regra feita só no painel não aparece no repo; sem migrations exportadas, C04 fica ATENÇÃO até conferir o painel. Regra que só exige estar logado (`@request.auth.id != ""` sem dono) vira `pocketbase_qualquer_logado` (C04, média); `manageRule` não é lida.

**Correções por checagem**
- **C04 Ativar RLS** — no PocketBase, C04 são as API rules: `null` (travada, o padrão) = só superusuário; `""` (vazia) = qualquer pessoa, inclusive visitante; expressão = só quem satisfaz. Superusuário ignora as regras.
  - Dono: `list`, `view`, `update` e `delete` com `@request.auth.id != "" && owner = @request.auth.id`; `create` com `@request.auth.id != "" && @request.body.owner = @request.auth.id`.
  - Campo que o usuário não pode mudar: acrescente `&& @request.body.role:isset = false` (nem enviar) ou `@request.body.role:changed = false`.
- **C05 Criptografia de dados** — `--encryptionEnv=PB_ENCRYPTION_KEY` (chave de 32 caracteres) cifra as configurações salvas, como SMTP e S3.
- **C06 Auth server-side** — rota de `pb_hooks` sem middleware é pública: `routerAdd("POST", "/api/app/x", handler, $apis.requireAuth())` (ou `$apis.requireSuperuserAuth()`).
- **C10 Hash nas senhas** — o PocketBase faz o hash; proteja o superusuário com MFA e OTP (opções da coleção `_superusers`).
- **C11 Rate limit** — limitador nativo (v0.23+) em Settings → Application; atrás de proxy, configure os "User IP proxy headers", senão todo mundo tem o IP do proxy.
- **C16 Restringir uploads** — no campo `file`: tamanho máximo (padrão ~5 MB), tipos MIME permitidos e "Protected" para arquivo privado (acesso com o token curto de `pb.files.getToken()` e a View rule).
- **C17 Limitar respostas de API** — campo com a opção "Hidden" sai da API; e-mail das contas só com `emailVisibility` quando precisar.

## Appwrite

**Onde olhar primeiro**
- `appwrite.config.json` ou `appwrite.json`: tabelas (antes coleções), buckets e functions (`execute`).
- Código com `Permission.*` e `Role.*`; onde roda o Server SDK (`node-appwrite` com `setKey`).
- Console: permissões e Row security de cada tabela; buckets (permissões, tamanho, extensões, File security); Auth → Security; Platforms (hostnames permitidos); API keys e scopes.

**Sinais do scanner**
- `appwrite_permissao_any` → C04 (escrita com `Role.any()`).
- Limites: leitura com `Role.any()` e escrita com `Role.users()` (qualquer conta) viram `appwrite_leitura_publica_ou_qualquer_conta` (C04, média); permissão definida só no painel não aparece no repo.

**Correções por checagem**
- **C03 Usar apenas Public Key no DB** — API key do Server SDK ignora permissões: só no servidor ou numa Function, com os scopes mínimos.
- **C04 Ativar RLS** — no Appwrite, C04 são as permissões, hoje em tabelas e linhas (TablesDB; antes, coleções e documentos). Permissão da tabela vale para todas as linhas e soma com a da linha. Para dono por linha, ligue Row security, dê na tabela só `create` para `Role.users()` e grave a linha com `Permission.read(Role.user(uid))`, `Permission.update(Role.user(uid))` e `Permission.delete(Role.user(uid))`.
  - `Role.any()` = qualquer visitante; `Role.users()` = qualquer conta (cadastro aberto); `Role.guests()` = só quem não está logado; papel com `Role.team(teamId, "admin")` ou `Role.label("admin")` (label só o servidor define).
- **C06 Auth server-side** — Function com `execute: ["any"]` é pública: restrinja e confira o usuário dentro; webhook com assinatura.
- **C10 Hash nas senhas** — o Appwrite faz o hash; em Auth → Security, ligue histórico de senha, dicionário de senhas comuns e bloqueio de dado pessoal na senha.
- **C11 Rate limit** — os endpoints de Auth já têm limite de abuso; Function cara precisa do próprio.
- **C16 Restringir uploads** — bucket com `maximumFileSize` e `allowedFileExtensions` (só olha a extensão: tipo crítico se valida numa Function), File security e nada de `read` para `Role.any()` em arquivo privado.

## Clerk, Auth0, Auth.js e Better Auth

**Onde olhar primeiro**
- `middleware.ts` ou `proxy.ts` (o Next 16 renomeou o arquivo; o código do `clerkMiddleware` e do `auth` não muda).
- Route handlers, Server Actions e APIs: `auth()`, `currentUser()`, `auth0.getSession()`, `auth.api.getSession()`.
- Onde o papel é lido: `publicMetadata`/`unsafeMetadata` (Clerk), `app_metadata`/`user_metadata` (Auth0), callbacks `jwt`/`session` (Auth.js), `additionalFields` (Better Auth).
- Webhooks (`/api/webhooks/*`) e segredos no `.env`: `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SIGNING_SECRET`, `AUTH_SECRET`, `AUTH0_SECRET`, `BETTER_AUTH_SECRET`.

**Sinais do scanner**
- `user_metadata_para_papel` → C07 · `jwt_decode_sem_verificar`, `auth_so_no_middleware`, `rota_sem_auth_aparente` → C06 · sinal `C10.auth_gerenciada`
- `stripe_live`/`stripe_test` (`sk_live_`/`sk_test_` também são da Clerk), `stripe_webhook` (`whsec_`, também da Svix), `public_env_secret` → C01
- Limites: `auth_so_no_middleware` lê `middleware.ts` e `proxy.ts` (Next 16). Papel em `unsafeMetadata` (Clerk) vira `clerk_unsafe_metadata_papel` (C07). Com Supabase, Firebase, Clerk, Better Auth ou Auth0, `sem_rate_limit` cai para baixa (o login já é limitado), mas rota de IA, e-mail e SMS continua precisando de limite próprio.

**Correções por checagem**
- **C06 Auth server-side** — a checagem fica em cada handler; middleware/proxy só redireciona página:
  - Clerk: `const { userId } = await auth(); if (!userId) return new Response(null, { status: 401 });` ou `await auth.protect()`. `clerkMiddleware()` sozinho não protege rota: use `createRouteMatcher` + `auth.protect()` e repita a checagem nas APIs.
  - Auth0 (`@auth0/nextjs-auth0` v4): `await auth0.getSession()` no servidor. API própria valida o access token (assinatura, `aud`, `iss`) com `express-oauth2-jwt-bearer` ou JWKS, nunca o ID token.
  - Auth.js v5: `const session = await auth()` em cada route handler e Server Action. Desde set/2025 o projeto é mantido pelo time do Better Auth, que recomenda Better Auth para projeto novo.
  - Better Auth: `await auth.api.getSession({ headers: await headers() })`. O `getSessionCookie()` no middleware só vê se o cookie existe, não valida.
  - Webhook (Svix: Clerk, Resend e outros): rota pública, mas verificada antes de tocar no banco:
    ```ts
    import { verifyWebhook } from "@clerk/nextjs/webhooks";
    export async function POST(req: NextRequest) {
      const evt = await verifyWebhook(req); // usa CLERK_WEBHOOK_SIGNING_SECRET; lança se a assinatura não bate
      // ...
    }
    ```
    Fora da Clerk: `new Webhook(secret).verify(corpoCru, cabecalhos)` do pacote `svix`, com `svix-id`, `svix-timestamp` e `svix-signature`.
- **C07 Restringir acessos** — papel onde o usuário não escreve:
  - Clerk: `publicMetadata` (só backend e painel alteram), exposto via `sessionClaims` customizado, ou `has({ role: "org:admin" })` com Organizations. O `unsafeMetadata` o usuário edita.
  - Auth0: `app_metadata`, emitido como claim com namespace numa Action pós-login. O `user_metadata` o usuário edita (escopo `update:current_user_metadata`).
  - Auth.js: papel lido do banco no callback `jwt`/`session`, nunca do `profile` do provedor.
  - Better Auth: campo extra com `input: false` (`additionalFields: { role: { type: "string", input: false } }`) ou o plugin admin.
- **C08 Bloquear Mass Assignment** — Better Auth sem `input: false` aceita `role` no cadastro. `unsafeMetadata` (Clerk) e `user_metadata` (Auth0) nunca decidem acesso, plano ou crédito.
- **C09 Proteger cookies** — Auth.js, Better Auth e o SDK do Auth0 guardam a sessão em cookie HttpOnly; a Clerk usa token de sessão de vida curta, renovado sozinho. Nos quatro, OK citando a lib. Better Auth: `trustedOrigins` com a lista real e nunca `disableCSRFCheck: true`. `AUTH_SECRET`/`BETTER_AUTH_SECRET` fortes e só no servidor.
- **C10 Hash nas senhas** — Clerk e Auth0 gerenciam; o Better Auth usa scrypt (OK). No Auth.js com Credentials, o hash e o limite de tentativas são seus.
- **C11 Rate limit** — Better Auth: limitador ligado só em produção, padrão de 100 requisições a cada 10 s, em memória (em serverless, `storage: "database"` ou secondary storage), com `customRules` para o login; chamada `auth.api` feita no servidor não passa por ele. Auth0: ligue Brute-force protection, Suspicious IP throttling e Breached password detection (Attack Protection). Clerk e Auth0 limitam o próprio login; suas rotas de IA continuam por sua conta.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
