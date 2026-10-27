<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Front-end, mobile e desktop · onde olhar e como corrigir

Referência por stack para o agente que audita código que roda no navegador, no celular ou na máquina do usuário: o que vai para o cliente, onde olhar, o que o `scan.py` sinaliza e a correção certa em cada stack. O critério de FALHA/ATENÇÃO/OK/N/A continua no `checks.md`.

**Stacks:** [React SPA (Vite e CRA)](#react-spa-vite-e-cra) · [Next.js](#nextjs) · [Remix e React Router](#remix-e-react-router) · [Vue e Nuxt](#vue-e-nuxt) · [Svelte e SvelteKit](#svelte-e-sveltekit) · [Angular](#angular) · [Astro](#astro) · [React Native e Expo](#react-native-e-expo) · [Flutter](#flutter) · [Electron e Tauri](#electron-e-tauri) · [Extensões de navegador](#extensões-de-navegador)

Sinais genéricos, válidos em todas as stacks e não repetidos abaixo: `generic_assignment`, `public_env_secret` e os ids de padrão de chave (`openai_key`, `stripe_live`…) (C01) · `arquivo_sensivel_rastreado`, `segredo_no_historico` (C02) · `token_em_localstorage`, `token_em_sessionstorage` (C09) · `sem_bot_protection`, `captcha_sem_verificacao` (C12) · `inner_html`, `eval`, `document_write` (C14) · `url_http` (C19) · `auditoria_nao_executada`, `vulnerabilidades_altas` (C20) · `localhost_no_cliente` (P01).

Classificação interna do scanner: em arquivo que ele considera cliente, a maioria dos padrões de chave sobe para confiança alta (a nota diz "arquivo vai pro navegador/app") e só ali rodam `llm_api_from_client`, `service_role_in_client`, `firebase_admin_in_client` e `db_driver_in_client`. Arquivo que ele não classifica conta como servidor.

Versões de referência (out/2026): Next.js 16.4 (15.5 ainda recebe patch) · React Router 8 (Remix v2 sem suporte) · Nuxt 4.6 · SvelteKit 3.1 · Angular 22 · Astro 7 · Vite 8 · Expo SDK 58 · Electron 45 · Tauri 2.

## React SPA (Vite e CRA)

**O que vai para o cliente**
- Tudo em `src/` e tudo o que ele importa. SPA não tem lado servidor: o que roda no navegador é público.
- Variáveis embutidas no build: Vite expõe `import.meta.env.VITE_*` e qualquer prefixo extra de `envPrefix`; CRA expõe `process.env.REACT_APP_*`, `NODE_ENV` e `PUBLIC_URL`.
- Também vão: o que `define` ou `DefinePlugin` injeta, a pasta `public/` inteira e os `.map`, se gerados.
- Só servidor: o que fica fora do bundle (`api/` na Vercel, `netlify/functions/`, `supabase/functions/`, Worker). Ver `back-js.md`.

**Onde olhar primeiro**
- `vite.config.*`: `envPrefix`, `define`, `build.sourcemap` e `loadEnv(mode, cwd, '')` repassado para `define`.
- `.env*`, `src/lib/`, `src/services/`, `src/api/` (clientes de API, Supabase, Firebase, SDK de IA) e guardas de rota (`ProtectedRoute`, `RequireAuth`).
- Hospedagem: `vercel.json`, `netlify.toml`, `public/_headers`, `nginx.conf`. CRA: script de build no `package.json` e `craco.config.*`.

**Sinais do scanner**
- `vite_envprefix_vazio`, `bundle_recebe_todo_env`, `define_segredo_no_bundle`, `dangerously_allow_browser`, `llm_api_from_client` → C01 · `service_role_in_client`, `public_env_service_role`, `firebase_admin_in_client`, `db_driver_in_client` → C03
- `document_cookie_token` → C09 · `dangerously_set_inner_html`, `rehype_raw` → C14 · `vite_sourcemap`, `webpack_sourcemap` → C15 · `sem_security_headers`, `headers_faltando`, `csp_unsafe` → C18
- Limites:
  - Com back-end no mesmo repositório (Express, Hono… em algum `package.json`), o SPA deixa de ser cliente inteiro: só `components/`, `hooks/`, `pages/`, `store/` e afins são marcados. Revise `src/lib` e `src/services` à mão para C01.
  - CRA gera source map por padrão: `cra_sourcemap_padrao` (C15) acusa quando não acha `GENERATE_SOURCEMAP=false`.

**Correções por checagem**
- **C01 Esconder API Keys** — chamada com chave secreta sai do SPA para uma função serverless (`api/chat.ts`, Netlify Function, Edge Function) e o front chama `/api/chat`. Tire o prefixo `VITE_`/`REACT_APP_` e rotacione. O Vite atual recusa `envPrefix: ''`; prefixo extra (`['VITE_', 'APP_']`) também é público.
- **C03 Usar apenas Public Key no DB** — no SPA só entra chave pública (`anon`/`sb_publishable_`, web config do Firebase). Quem protege é RLS ou rules (C04) e, no Firebase, App Check.
- **C06 Auth server-side** — guarda de rota é UX. Cada endpoint que o SPA chama valida o token; no Supabase, a policy usa `auth.uid()`.
- **C09 Proteger cookies** — com back próprio no mesmo site, sessão em cookie `HttpOnly; Secure; SameSite=Lax` emitido pelo back, não JWT em `localStorage`. Supabase JS no SPA usa `localStorage` por padrão: ATENÇÃO de severidade baixa (`checks.md`). Auth0 SPA SDK: mantenha `cacheLocation` no padrão (`memory`).
- **C14 Validação dos inputs** — `dangerouslySetInnerHTML` só com `DOMPurify.sanitize`. Markdown de usuário ou de LLM: `react-markdown` sem `rehype-raw`, ou com `rehype-sanitize` depois dele. URL do usuário em `href` só com `https:` ou `mailto:`.
- **C15 Evitar vazamento de conteúdo** — Vite: `build.sourcemap: false` ou `'hidden'` (gera para o Sentry sem publicar). CRA: `GENERATE_SOURCEMAP=false` no script de build.
- **C18 Security headers** — SPA estático não manda header: configure no host. Na Vercel (que já manda HSTS), `vercel.json` abaixo; na Netlify, as mesmas linhas em `public/_headers`; no nginx, `add_header ... always;` no bloco 443.
  ```json
  { "headers": [{ "source": "/(.*)", "headers": [
    { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; connect-src 'self' https://api.meuapp.com.br; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" },
    { "key": "X-Content-Type-Options", "value": "nosniff" },
    { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
    { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
  ] }] }
  ```
- **C19 Forçar HTTPS** — URL da API (`VITE_API_URL`) sempre `https://`; nada de `http://` no bundle.
- **C20 Scan de dependências** — CRA foi descontinuado em 2025 e arrasta dependências antigas: migre para Vite. Nunca sirva produção com `vite` ou `vite preview`: o dev server exposto com `--host` teve CVEs de leitura de arquivo (CVE-2025-30208, CVE-2025-31125, e mais correções de `server.fs` no Vite 8).

## Next.js

**O que vai para o cliente**
- Arquivo com `"use client"` e tudo o que ele importa, inclusive `lib/` compartilhada. Sem a diretiva (e sem ser importado por Client Component), o componente do App Router é Server Component e não entra no bundle.
- Mesmo sem `"use client"`, chegam ao navegador: props que um Server Component passa a um Client Component, o retorno de Server Action e as variáveis capturadas por action inline (cifradas, mas vão e voltam). Pages Router: o retorno de `getServerSideProps`/`getStaticProps` sai inteiro no `__NEXT_DATA__`.
- Env: só `NEXT_PUBLIC_*` (inlinado no build) e tudo o que estiver em `env` no `next.config`, com ou sem prefixo.
- Só servidor: Server Components, `route.ts`, `pages/api/**`, arquivos `"use server"`, `proxy.ts` (Next 16+, antigo `middleware.ts`) e módulos com `import "server-only"`.

**Onde olhar primeiro**
- `next.config.*`: `env`, `headers()`, `images` (`remotePatterns`, `dangerouslyAllowSVG`), `productionBrowserSourceMaps`, `poweredByHeader`, `experimental.serverActions`.
- `proxy.ts` ou `middleware.ts` e o `matcher`; `app/**/route.ts`; `pages/api/**`; arquivos `"use server"` e actions inline em `<form action>`.
- Camada de dados (`lib/`, `data/`, `server/`) com clientes de banco, Supabase admin e SDK de IA; componentes `"use client"` com props largas (`user` inteiro); pastas `[param]`, que são input do usuário.

**Sinais do scanner**
- `next_config_env_secreto`, `dangerously_allow_browser`, `llm_api_from_client` → C01 · `service_role_in_client`, `db_driver_in_client`, `firebase_admin_in_client`, `public_env_service_role` → C03
- `rota_sem_auth_aparente` (route handler, `pages/api`, arquivo `"use server"`), `getSession_no_servidor`, `auth_so_no_middleware`, `next_middleware_bypass`, `jwt_decode_sem_verificar`, `trpc_mutation_publica` → C06
- `identidade_do_cliente`, `busca_por_id_do_request`, `admin_sem_checagem_de_papel`, `user_metadata_para_papel` → C07 · `data_do_request`, `create_update_com_body`, `spread_do_body`, `object_assign_body` → C08
- `ia_sem_rate_limit`, `sem_rate_limit`, `next_image_wildcard` → C11 · `rota_sem_validacao_aparente`, `dangerously_set_inner_html`, `rehype_raw`, `ssrf_url_do_usuario`, `open_redirect` → C14
- `source_maps_producao`, `stack_na_resposta`, `mensagem_interna` → C15 · `findmany_sem_take`, `select_estrela_sem_limite`, `objeto_usuario_inteiro`, `limit_sem_teto` → C17 · `x_powered_by`, `headers_faltando`, `csp_unsafe` → C18 · `next_cve_2025_29927`, `next_react2shell` → C20
- Limites:
  - `auth_so_no_middleware` lê `middleware.ts` e `proxy.ts` (Next 16+). Action inline não entra na lista de rotas. `cookies().set()` não passa por `cookie_sem_flags`.
  - Server Component dentro de `components/` é marcado como cliente: `db_driver_in_client` pode ser falso positivo. Confira se há `"use client"` nele ou em quem o importa.
  - As regras de versão só cobrem CVE-2025-29927 e React2Shell; os avisos de 2026 estão em C20 abaixo.

**Correções por checagem**
- **C01 Esconder API Keys** — chave sem `NEXT_PUBLIC_` e fora do `env` do `next.config`. O módulo que lê a chave começa com `import "server-only"`: o build quebra se um Client Component o importar. Só a camada de dados lê `process.env`.
- **C03 Usar apenas Public Key no DB** — modelo do `checks.md`: `createBrowserClient` com chave pública e cliente admin em arquivo `server-only`.
- **C06 Auth server-side** — cada route handler e cada Server Action checa a sessão dentro dela; auth na página não cobre a action declarada nela. `proxy.ts`/`middleware.ts` serve para redirecionar página, e um `matcher` que exclui um caminho também pula as Server Actions daquele caminho. Supabase: `getUser()` ou `getClaims()`, nunca `getSession()`. Abaixo de 12.3.5, 13.5.9, 14.2.25 ou 15.2.3, atualize (CVE-2025-29927) e descarte `x-middleware-subrequest` no proxy da frente.
- **C07 Restringir acessos** — camada de dados `server-only` recebe o usuário da sessão, filtra pelo dono e devolve DTO. `params` de `[id]` e `searchParams` são input.
- **C08 Bloquear Mass Assignment** — FormData nunca vai inteiro ao banco:
  ```ts
  "use server";
  import { z } from "zod";
  const Perfil = z.strictObject({ nome: z.string().trim().min(1).max(80) });
  export async function salvarPerfil(formData: FormData) {
    const user = await requireUser();                          // C06: lança se não logado
    const data = Perfil.parse({ nome: formData.get("nome") }); // campo a campo
    await db.user.update({ where: { id: user.id }, data });
    return { ok: true };                                       // C17: o registro não volta
  }
  ```
- **C09 Proteger cookies** — `(await cookies()).set(...)` com as flags do `checks.md`; Auth.js, Clerk e `@supabase/ssr` já fazem. Server Action compara `Origin` com o host; atrás de proxy que troca o host, liste a origem pública em `experimental.serverActions.allowedOrigins`, sem curinga amplo.
- **C11 Rate limit** — action ou route handler que chama IA ou manda e-mail: Upstash (modelo do `checks.md`) ou `checkRateLimit("id-da-regra", { request })` do `@vercel/firewall`, com a regra criada no Firewall da Vercel (contador por região). `images.remotePatterns` com hostname explícito, nunca `'**'`.
- **C14 Validação dos inputs** — zod no route handler e na action. `redirect()` com destino vindo da URL só se for caminho relativo (`/x`; recuse `//x` e `https://`).
- **C15 Evitar vazamento de conteúdo** — `productionBrowserSourceMaps` fica `false` (padrão) e `poweredByHeader: false`. Erro genérico para o cliente.
- **C16 Restringir uploads** — Server Action aceita até 1 MB de corpo (`experimental.serverActions.bodySizeLimit`); arquivo grande vai direto ao storage por URL assinada. `images.dangerouslyAllowSVG` só com `contentDispositionType: 'attachment'` e `contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;"`.
- **C17 Limitar respostas de API** — não passe registro do banco para Client Component nem o devolva em action: monte DTO. `experimental.taint` é camada extra, não substitui o DTO.
- **C18 Security headers** — headers fixos no `next.config` (bloco do `checks.md`). CSP com nonce: gere no `proxy.ts` e ponha `Content-Security-Policy` na request e na response; isso obriga render dinâmico (sem ISR nem PPR). Página estática sem nonce: `experimental.sri` (App Router, experimental).
- **C20 Scan de dependências** — depois do React2Shell vieram CVE-2025-55183/55184 (dez/2025), 13 avisos em maio/2026 (entre eles bypass de `middleware`/`proxy` usado como auth; corrigidos em 15.5.18 e 16.2.6, sem correção para 13.x e 14.x) duas RCE críticas em agosto/2026 (uma no otimizador de imagem com AVIF; corrigidas em 15.5.24 e 16.3.3), SSRF e cache poisoning em setembro (15.5.27 / 16.3.8) e mais duas RCE críticas em 14/out/2026 (`use cache` com typed arrays e otimização de imagem com SVG; corrigidas em 15.5.28 e 16.4.1). Abaixo de 15.5.28 ou 16.4.1, e em qualquer 13.x ou 14.x, é FALHA (`next_boletins_2026`, `next_linha_sem_suporte`): suba para o último patch de 15.5 ou 16.4. Fonte: nextjs.org/blog/nextjs-security-update-october-14-2026.

## Remix e React Router

**O que vai para o cliente**
- Do módulo de rota, só o componente, os exports de cliente (`clientLoader`, `clientAction`, `clientMiddleware`) e o que eles importam. `loader`, `action`, `headers` e `middleware` saem do bundle do navegador.
- O retorno de todo `loader` e `action` é serializado para o navegador, no HTML e nas requisições `.data`. No Remix v2 clássico, o que o `loader` do `root` devolve em `ENV` vira `window.ENV`.
- Env no cliente: `import.meta.env.VITE_*` (React Router 7/8 e Remix com Vite).
- Só servidor: `*.server.ts` e pastas `.server/` (o build falha se entrarem no grafo do cliente), `entry.server.tsx` e o código de sessão.

**Onde olhar primeiro**
- `app/routes/**`: cada `loader` e cada `action`. `app/root.tsx` (loader com `ENV`), `app/sessions.server.ts` (`createCookieSessionStorage`), `entry.server.tsx` (headers e nonce), `react-router.config.ts`, `vite.config.ts`.

**Sinais do scanner**
- `rota_sem_auth_aparente` em `app/routes/` com `loader`/`action` sem `requireUserId(`, `getUser(` ou `requireUser` → C06 · `rota_sem_validacao_aparente`, `dangerously_set_inner_html`, `open_redirect` → C14
- Limites:
  - O módulo de rota fica `unknown` (conta como servidor): as regras só de cliente não rodam no componente da rota.
  - O scanner não lê o `middleware` do React Router nem a proteção de CSRF das actions.

**Correções por checagem**
- **C01 Esconder API Keys** — chave só em `*.server.ts`, lido por `loader`/`action`. O `ENV` do root leva só valor público.
- **C06 Auth server-side** — cada `loader` e cada `action` checa a sessão: loaders rodam em paralelo e a requisição `.data` pode pedir só o da rota filha, então o redirect do pai não protege o filho. React Router 8 (ou 7 com `future.v8_middleware`; confira na doc da versão): `middleware` no layout roda antes dos loaders filhos e serve de barreira. Server Function faz a própria checagem.
- **C07 Restringir acessos** — busca por `params.id` sempre junto do `userId` da sessão.
- **C08 Bloquear Mass Assignment** — monte o objeto campo a campo (`{ titulo: form.get("titulo") }`) e valide com `z.strictObject` antes do banco; nunca `Object.fromEntries(form)` direto no ORM.
- **C09 Proteger cookies** — sessão com flags explícitas:
  ```ts
  export const sessions = createCookieSessionStorage({
    cookie: { name: "__session", httpOnly: true, secure: true, sameSite: "lax",
              path: "/", secrets: [process.env.SESSION_SECRET!] },
  });
  ```
- **C14 Validação dos inputs** — `redirect(to)` com `to` vindo da query só se for caminho relativo.
- **C17 Limitar respostas de API** — loader devolve só o que a tela usa: tudo o que ele retorna fica legível no `.data`.
- **C18 Security headers** — export `headers` na rota ou headers no `entry.server.tsx`; CSP com nonce passado ao `ServerRouter` e aos `<Scripts>` (confira na doc da versão).
- **C20 Scan de dependências** — CSRF em action do Framework Mode: CVE-2026-22030 (corrigida em react-router 7.12.0 e @remix-run/server-runtime 2.17.3) e CVE-2026-53663 (baixa, desvio por PUT/PATCH/DELETE, corrigida em 7.15.1). O Remix v2 saiu de suporte: migre para React Router 7 ou 8.

## Vue e Nuxt

**O que vai para o cliente**
- Vue SPA com Vite: igual ao React SPA (`VITE_*`; Vue CLI: `VUE_APP_*`).
- Nuxt: o código do app (`app/` no Nuxt 4; `pages/`, `components/`, `composables/`, `plugins/`, `middleware/`, `stores/` na raiz no Nuxt 3), `runtimeConfig.public`, o `app.config.ts` inteiro e o payload do SSR: o resultado de `useFetch`, `useAsyncData` e `useState` vai serializado no HTML.
- Env: `NUXT_PUBLIC_*` sobrescreve chave declarada em `runtimeConfig.public`.
- Só servidor: `server/` (Nitro: `server/api`, `server/routes`, `server/middleware`, `server/utils`), chaves de `runtimeConfig` fora de `public` (`NUXT_*`) e arquivos `*.server.ts`.

**Onde olhar primeiro**
- `nuxt.config.ts` (`runtimeConfig`, `security` do nuxt-security, `routeRules`, `sourcemap`), `app.config.ts`, `server/api/**`, `server/middleware/**`, route middleware em `middleware/`, composables com `$fetch` e componentes com `v-html`.

**Sinais do scanner**
- `nuxt_runtime_public_segredo` (nome de segredo dentro de `runtimeConfig.public`) → C01 · `rota_sem_auth_aparente` em `server/api` e `server/routes` com `defineEventHandler` (reconhece `requireUserSession(`, `getUserSession(`, `serverSupabaseUser(`, `event.context.user`) → C06 · `v_html`, `rota_sem_validacao_aparente` → C14
- `headers_pelo_framework` (baixa) → C18 no lugar de `sem_security_headers` quando os headers vêm do nuxt-security: confirme com o `check_url.py` o que sai de fato. O módulo também aparece em `sinais` de C11 (`rate_limit_framework_em`).
- Limites: o `app.config.ts` (também público) não é lido; a pasta `shared/` do Nuxt 4 fica `unknown`.

**Correções por checagem**
- **C01 Esconder API Keys** — segredo fica na raiz do `runtimeConfig` e é lido no `server/` com `useRuntimeConfig(event)`. Nada secreto em `public`, em `app.config.ts` nem em `useState`.
  ```ts
  export default defineNuxtConfig({
    runtimeConfig: {
      openaiKey: "",               // NUXT_OPENAI_KEY: só servidor
      public: { apiBase: "/api" }, // NUXT_PUBLIC_API_BASE: vai para o navegador
    },
  });
  ```
- **C06 Auth server-side** — cada handler de `server/api` checa a sessão: `const { user } = await requireUserSession(event)` (nuxt-auth-utils) ou `serverSupabaseUser(event)` (@nuxtjs/supabase). Route middleware (`defineNuxtRouteMiddleware`) é UX, não barreira.
- **C08 Bloquear Mass Assignment** — `readValidatedBody(event, Schema.parse)` com `z.strictObject` e grave só o resultado.
- **C09 Proteger cookies** — nuxt-auth-utils: `NUXT_SESSION_PASSWORD` com 32+ caracteres. Cookie próprio: `setCookie(event, "sessao", token, { httpOnly: true, secure: true, sameSite: "lax", path: "/" })`. O CSRF do nuxt-security vem desligado (liga com `nuxt-csurf`).
- **C11 Rate limit** — o nuxt-security limita 150 requisições a cada 5 min por IP, em memória (LRU): com várias instâncias ou serverless, troque o `rateLimiter.driver` por um storage do unstorage (Redis) ou limite no edge, e aperte em rota de IA e login.
- **C14 Validação dos inputs** — `getValidatedQuery` e `readValidatedBody` com schema. `v-html` só com DOMPurify. Vue não sanitiza `:href`: aceite só `https:` em URL do usuário. Nunca use conteúdo do usuário como template.
- **C15 Evitar vazamento de conteúdo** — `sourcemap.client` fica `false` (padrão). `createError({ statusCode, statusMessage })` com texto genérico.
- **C16 Restringir uploads** — `requestSizeLimiter` do nuxt-security (cerca de 2 MB, 8 MB em upload); `readMultipartFormData` e checagem dos bytes.
- **C17 Limitar respostas de API** — o endpoint devolve DTO. `useFetch(..., { pick })` só enxuga o payload; a rota continua respondendo tudo.
- **C18 Security headers** — o nuxt-security manda CSP com nonce e SRI, HSTS, `X-Frame-Options`, nosniff e `Permissions-Policy`. Confirme que ele está em `modules` e ajuste a CSP aos domínios usados.
- **C20 Scan de dependências** — Nuxt 4.5.1+ (ou 3.21.10+): os patches de maio e julho/2026 corrigiram bypass de route middleware por island, bypass de `routeRules` com chave em maiúscula, RCE por props de server island e vazamento de payload em cache entre usuários.

## Svelte e SvelteKit

**O que vai para o cliente**
- Componentes `.svelte`, `+page.ts`/`+layout.ts` (load universal, roda também no navegador), `$lib` fora de `$lib/server` e `hooks.client.ts`.
- O que o `load` de `+page.server.ts`/`+layout.server.ts` devolve é serializado na página.
- Env: no SvelteKit 2, `$env/static/public` e `$env/dynamic/public` (prefixo `PUBLIC_`). No SvelteKit 3, as variáveis são declaradas em `src/env.ts` com `defineEnvVars` e só as marcadas `public: true` vão para `$app/env/public`; os módulos `$env/*` ficaram obsoletos.
- Só servidor: `+page.server.ts`, `+layout.server.ts`, `+server.ts`, `hooks.server.ts`, `$lib/server/**`, `*.server.ts`, `$env/*/private` e `$app/env/private` (importar no cliente quebra o build).

**Onde olhar primeiro**
- Config: `svelte.config.js` (SvelteKit 2) ou opções do plugin `sveltekit()` no `vite.config.*` (SvelteKit 3): `csp`, `csrf` e adapter.
- `src/hooks.server.ts` (`handle` com a sessão em `event.locals`), `src/routes/**/+server.ts`, `+page.server.ts` (`load` e `actions`), `*.remote.ts` (remote functions, experimental), `src/lib/server/`, `.env` e `src/env.ts`.

**Sinais do scanner**
- `rota_sem_auth_aparente` em `+server.ts`/`+page.server.ts` (reconhece `locals.user`, `locals.session`) → C06 · `svelte_html`, `rota_sem_validacao_aparente` → C14
- `sveltekit-rate-limiter` e `kit.csp` aparecem em `sinais` de C11 e C18.
- Limites: remote functions não entram na lista de rotas; `public: true` no `src/env.ts` não é checado. `kit.csp` só é lido do `svelte.config.*` (no SvelteKit 3 a config mora no `vite.config`: confira à mão); sem header escrito no código, ele vira `headers_pelo_framework` (C18), e com outros headers a CSP aparece como faltando em `headers_faltando`.

**Correções por checagem**
- **C01 Esconder API Keys** — segredo só em `$env/static/private`/`$env/dynamic/private` (2.x) ou em variável sem `public: true` (3.x, lida de `$app/env/private`), e só em arquivo de servidor.
- **C06 Auth server-side** — sessão validada no `handle`; cada `+server.ts`, form action e remote function checa `locals.user`. Guarda em `+layout.server.ts` não protege `+server.ts` nem actions.
  ```ts
  // src/hooks.server.ts
  export const handle: Handle = async ({ event, resolve }) => {
    event.locals.user = await validarSessao(event.cookies.get("session")); // confere no servidor
    if (event.url.pathname.startsWith("/api/") && !event.locals.user)
      return new Response("unauthorized", { status: 401 });
    return resolve(event);
  };
  ```
- **C09 Proteger cookies** — `event.cookies.set` já vem `httpOnly` e `secure` (fora de dev): não desligue. CSRF de formulário: mantenha a checagem de origem; para liberar outra origem use `csrf.trustedOrigins` (o `checkOrigin` está obsoleto), nunca `['*']`.
- **C11 Rate limit** — `sveltekit-rate-limiter` ou Upstash na action e no endpoint. Atrás de proxy (adapter-node), configure `ADDRESS_HEADER` e `XFF_DEPTH` para `getClientAddress()` não devolver o IP do proxy nem um IP forjado.
- **C14 Validação dos inputs** — `{@html}` só com DOMPurify. Form action e endpoint validam com schema; remote function recebe um Standard Schema (zod, valibot) no primeiro argumento.
- **C16 Restringir uploads** — o adapter-node aceita até 512 kB de corpo (`BODY_SIZE_LIMIT`); `Infinity` só com checagem própria no `handle`.
- **C17 Limitar respostas de API** — `load` de servidor devolve DTO: tudo o que ele retorna vai para o navegador.
- **C18 Security headers** — `csp: { mode: "auto", directives: { "script-src": ["self"] } }` (hash na página pré-renderizada, nonce na dinâmica); os demais headers no `handle`, com `response.headers.set(...)` depois do `resolve`.
- **C20 Scan de dependências** — adapter-node sem origem definida permitia SSRF (CVE-2025-67647; kit 2.49.5 e adapter-node 5.5.1): defina a origem (`ORIGIN` no 2.x, `paths.origin` no 3.x). Remote functions tiveram DoS e prototype pollution em 2026 (corrigidos até 2.69.1).

## Angular

**O que vai para o cliente**
- Tudo em `src/app`, os `environment*.ts` (trocados por `fileReplacements`) e os valores de `define` do `angular.json`. Não há prefixo público nativo: valor que entra no build é público. `NG_APP_*` só existe com `@ngx-env/builder` (terceiro).
- SSR (`@angular/ssr`): `server.ts` roda no servidor, mas as respostas guardadas pelo transfer cache do `HttpClient` vão no HTML.

**Onde olhar primeiro**
- `angular.json` (`fileReplacements`, `sourceMap`, `define`, `security.autoCsp`, `allowedHosts`), `src/environments/`, interceptors (`*.interceptor.ts`), guards (`*.guard.ts`), usos de `bypassSecurityTrust*` e de `nativeElement.innerHTML`, `src/server.ts`.

**Sinais do scanner**
- `angular_bypass_sanitizer` → C14 · `angular_sourcemap_prod` → C15 (confiança baixa: costuma ser a config de desenvolvimento) · chaves em `environment*.ts` → C01 (cliente, confiança alta)
- Limites: `[innerHTML]` não é acusado porque o Angular sanitiza; o risco está no `bypassSecurityTrust*`. Guards e interceptors não contam como auth.

**Correções por checagem**
- **C01 Esconder API Keys** — `environment.prod.ts` e `define` são públicos: chave secreta vai para o back-end.
- **C06 Auth server-side** — `canActivate`/`canMatch` é UX; a API valida o token. No interceptor, anexe o token só a requisições para o seu domínio.
- **C09 Proteger cookies** — XSRF do `HttpClient`: o back emite o cookie `XSRF-TOKEN` e confere o header `X-XSRF-TOKEN`; o Angular só envia o header em escrita para URL relativa ou da mesma origem. Nomes próprios: `provideHttpClient(withXsrfConfiguration({ cookieName, headerName }))`.
- **C14 Validação dos inputs** — `bypassSecurityTrust*` só com valor constante ou já sanitizado; ao mexer no DOM direto, `DomSanitizer.sanitize(SecurityContext.HTML, valor)`. Template nunca é montado com input (AOT em produção).
- **C15 Evitar vazamento de conteúdo** — `sourceMap: false` na configuração `production`; `true` só na de desenvolvimento.
- **C18 Security headers** — CSP com nonce: atributo `ngCspNonce` no elemento raiz ou token `CSP_NONCE`, com nonce novo por resposta (cuidado com cache de CDN). Sem SSR: `security.autoCsp: true` gera hash dos scripts inline (não cobre `style-src`). Trusted Types: `trusted-types angular; require-trusted-types-for 'script'`. Os demais headers no `server.ts` (helmet) ou no host.
- **C20 Scan de dependências** — `@angular/ssr` teve SSRF por `Host`/`X-Forwarded-*` (CVE-2026-27739, corrigida em 19.2.21, 20.3.17 e 21.1.5): atualize com `ng update`, configure `allowedHosts` (`angular.json`, `AngularNodeAppEngine` ou `NG_ALLOWED_HOSTS`) e só ligue `trustProxyHeaders` atrás de proxy que reescreve esses headers.

## Astro

**O que vai para o cliente**
- `<script>` dos `.astro`, componentes de framework com `client:*` e as props deles (serializadas no HTML da ilha), `import.meta.env.PUBLIC_*` e `astro:env/client`.
- Só servidor: frontmatter dos `.astro` (no build em `output: 'static'`, por requisição em SSR), endpoints em `src/pages/**/*.ts`, Actions (`src/actions/`), `src/middleware.ts` e `astro:env/server`; segredo com `access: "secret"` não entra em bundle nenhum.

**Onde olhar primeiro**
- `astro.config.*`: `output`, `adapter`, `security` (`checkOrigin`, `csp`, `allowedDomains`) e `env.schema`. `src/middleware.ts`, `src/pages/api/**`, `src/actions/index.ts`, frontmatter que lê sessão ou cookie, `set:html`.

**Sinais do scanner**
- `rota_sem_auth_aparente` em endpoint que exporta `GET`/`POST`, `auth_so_no_middleware` (lê `src/middleware.ts`) → C06 · `rota_sem_validacao_aparente`, `dangerously_set_inner_html`, `v_html`, `svelte_html` (ilhas) → C14
- Limites: `.astro` fica `unknown` (frontmatter é servidor, `<script>` é cliente); Actions não entram na lista de rotas; `set:html` não é acusado; `security.csp` não é reconhecido como CSP (sem outro header escrito no código, sai `sem_security_headers`).

**Correções por checagem**
- **C01 Esconder API Keys** — `env.schema` com `envField.string({ context: "server", access: "secret" })` e leitura por `astro:env/server`. Nada secreto com `PUBLIC_`.
- **C06 Auth server-side** — Action é endpoint público em `/_actions/<nome>`: cada handler checa `context.locals.user` e lança `ActionError({ code: "UNAUTHORIZED" })`. `getActionContext` no middleware é camada extra. Endpoint e página SSR validam a sessão de novo: middleware sozinho já foi contornado.
- **C09 Proteger cookies** — `Astro.cookies.set("session", token, { httpOnly: true, secure: true, sameSite: "lax", path: "/" })`. Mantenha `security.checkOrigin` (padrão `true`).
- **C14 Validação dos inputs** — `input: z.object({...})` em toda Action (`accept: "form"` para formulário). `set:html` só com HTML sanitizado. SSR atrás de proxy: `security.allowedDomains` para não confiar em qualquer `Host`.
- **C17 Limitar respostas de API** — props de ilha (`client:*`) vão no HTML: passe só os campos usados.
- **C18 Security headers** — `security.csp: true` (Astro 6+) gera hash de scripts e estilos; os demais headers no middleware (`const res = await next(); res.headers.set(...)`) ou no host.
- **C20 Scan de dependências** — o middleware de auth foi contornado por caminho codificado ou por prefixo do `base` (corrigido em 5.15.8, 6.4.8 e 7.2.4): fique no último patch da sua linha.

## React Native e Expo

**O que vai para o cliente**
- O app inteiro fica no aparelho: o bundle JS (o bytecode do Hermes também se extrai), `EXPO_PUBLIC_*` (inlinado só na forma `process.env.EXPO_PUBLIC_X`), o `extra` do `app.json`/`app.config.*` (vai no manifesto, lido por `expo-constants`) e os arquivos nativos (`google-services.json`, `GoogleService-Info.plist`).
- Só servidor: API routes do Expo Router (`*+api.ts`, com `web.output: "server"` e `expo/metro-config`), que leem qualquer variável, e o seu back-end. Variável secreta do EAS não protege nada se o app lê o valor.

**Onde olhar primeiro**
- `app.json`/`app.config.ts` (`extra`, `ios.infoPlist`, `android`, plugin `expo-build-properties`), `eas.json` (env por perfil, às vezes com valor real), `.env*`.
- Cliente Supabase/Firebase (opção `storage`), usos de `AsyncStorage` e `SecureStore`, `react-native-webview`, tratamento de deep link, `android/app/src/main/AndroidManifest.xml`, `res/xml/network_security_config.xml`, `ios/*/Info.plist`.

**Sinais do scanner**
- `expo_extra_segredo` → C01 · `token_em_asyncstorage`, `supabase_sessao_asyncstorage` (cliente Supabase com `storage: AsyncStorage`, baixa) → C09 · `webview_origem_aberta` → C14 · `android_debuggable` → C15 · `android_cleartext`, `ios_arbitrary_loads` → C19
- Limites: projeto CNG sem `android/` e `ios/` tem a config nativa só no `app.json`, e as regras de manifest e plist não rodam. `+api.ts` (rota de API do Expo Router) é tratado como servidor.

**Correções por checagem**
- **C01 Esconder API Keys** — nenhuma chave secreta no app nem no `extra`; chamada com segredo passa pelo back-end ou por `+api.ts`. Rotacione o que já foi publicado: binário na loja não se recolhe.
- **C06 Auth server-side** — OAuth com Authorization Code + PKCE (o `expo-auth-session` usa PKCE S256 por padrão), sem client secret no app. Prefira App Links/Universal Links no retorno: esquema próprio (`meuapp://`) pode ser registrado por outro app.
- **C07 Restringir acessos** — o app não esconde rota de ninguém: todo endpoint que ele chama aceita `curl` com o mesmo token. O filtro por dono fica no back.
- **C09 Proteger cookies** — token em `expo-secure-store` (Keychain/Keystore), não em `AsyncStorage`. Sessão grande (Supabase): cifre o valor com chave guardada no SecureStore, como no guia do Supabase (iOS antigo rejeitava valor acima de ~2 KB).
  ```ts
  import * as SecureStore from "expo-secure-store";
  await SecureStore.setItemAsync("refresh_token", token, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  ```
- **C12 Bot protection** — cadastro e login do app com App Check (Firebase) ou Play Integrity e App Attest, verificados no back.
- **C14 Validação dos inputs** — WebView: `originWhitelist` só com seus domínios, `onShouldStartLoadWithRequest` bloqueando o resto e `onMessage` validado com schema; nada de token via `injectedJavaScript`. Parâmetro de deep link é input.
- **C15 Evitar vazamento de conteúdo** — build de release sem `android:debuggable`; tire `console.log` de token (aparece no `adb logcat`).
- **C19 Forçar HTTPS** — o Android 9+ já bloqueia HTTP: não ligue `usesCleartextTraffic` (manifest ou `expo-build-properties`) no release; no iOS, nada de `NSAllowsArbitraryLoads`. Com pasta `android/`, aponte `android:networkSecurityConfig="@xml/network_security_config"` no `<application>`:
  ```xml
  <!-- android/app/src/main/res/xml/network_security_config.xml -->
  <network-security-config>
    <base-config cleartextTrafficPermitted="false" />
  </network-security-config>
  ```
- **C20 Scan de dependências** — `npx expo install --check` alinha as versões ao SDK; rode `npm audit` também.

## Flutter

**O que vai para o cliente**
- O binário inteiro: strings do Dart compilado são recuperáveis. `--dart-define` e `--dart-define-from-file` (`String.fromEnvironment`) ficam dentro do app. O `.env` do `flutter_dotenv` vira asset em texto puro no APK/IPA. `firebase_options.dart` é config pública.
- `--obfuscate --split-debug-info` esconde nomes de símbolo, não strings. Flutter web: vale o [React SPA](#react-spa-vite-e-cra).

**Onde olhar primeiro**
- `pubspec.yaml` (`assets:` com `.env`, `shared_preferences`, `flutter_secure_storage`, `webview_flutter`), `lib/main.dart` (`Supabase.initialize`, `Firebase.initializeApp`), `lib/**/config*.dart`, `HttpOverrides` e `badCertificateCallback`, `android/app/src/main/AndroidManifest.xml`, `ios/Runner/Info.plist`.

**Sinais do scanner**
- `dart_define_segredo` e chaves em `.dart` (sempre cliente) → C01 · `token_em_sharedpreferences` → C09 · `android_debuggable` → C15 · `flutter_certificado_aceito`, `android_cleartext`, `ios_arbitrary_loads` → C19
- Limites: `.env` declarado em `assets` não vira C01 (só C02, se estiver no git); a sessão do `supabase_flutter` em SharedPreferences (padrão) não é acusada; `JavaScriptMode.unrestricted` não é checado.

**Correções por checagem**
- **C01 Esconder API Keys** — chave secreta sai do app para o back-end ou para uma Edge Function; tire o `.env` de `assets` e rotacione o que estava nele.
- **C09 Proteger cookies** — token em `flutter_secure_storage`. No `supabase_flutter`, passe um `LocalStorage` próprio, baseado no secure storage, em `FlutterAuthClientOptions(localStorage: ...)`.
- **C14 Validação dos inputs** — WebView com `JavaScriptMode.unrestricted` só para domínio seu; `NavigationDelegate(onNavigationRequest: ...)` bloqueia o resto; mensagem de `JavaScriptChannel` é input.
- **C15 Evitar vazamento de conteúdo** — release com `--obfuscate --split-debug-info=<pasta>` (símbolos fora do repositório); log de token só sob `kDebugMode`.
- **C19 Forçar HTTPS** — remova `badCertificateCallback = (...) => true` (no máximo atrás de `kDebugMode`); cleartext e ATS como em [React Native e Expo](#react-native-e-expo).
- **C20 Scan de dependências** — `flutter pub outdated`; o `osv-scanner` lê o `pubspec.lock`.

## Electron e Tauri

**O que vai para o cliente**
- Electron: tudo (main, preload, renderer) vai para a máquina do usuário; o `app.asar` abre com `npx @electron/asar extract`. O processo main não é servidor: segredo ali é público.
- Tauri: o front empacotado e o binário Rust (strings extraíveis), mais o `tauri.conf.json`.

**Onde olhar primeiro**
- Electron: cada `new BrowserWindow` (`webPreferences`), `preload.*` (`contextBridge.exposeInMainWorld`), `ipcMain.handle`/`on`, `shell.openExternal`, `setWindowOpenHandler`, `will-navigate`, `protocol.handle`, auto-update e fuses (`forge.config.*`, `electron-builder.yml`).
- Tauri: `src-tauri/tauri.conf.json` (`app.security.csp`, `app.security.pattern`, `assetProtocol.scope`), `src-tauri/capabilities/*.json`, `#[tauri::command]` em `src-tauri/src/**` e escopos dos plugins (fs, shell, http).

**Sinais do scanner**
- Todo JS, TS e Rust é cliente: chaves → C01 (confiança alta) · `shell_interpolado` → C14 · `tls_verificacao_desligada` → C19
- Limites: não checa `webPreferences`, IPC, fuses nem CSP e capabilities do Tauri; as regras de servidor (C08, C13, `ssrf_url_do_usuario`, `path_traversal`) não rodam no main. Revise cada handler de IPC como rota de API.

**Correções por checagem**
- **C01 Esconder API Keys** — nenhuma chave no main nem no Rust: o app chama o seu back-end com o token do usuário.
- **C07 Restringir acessos** — handler de IPC é API: confira quem chamou e valide os argumentos; o preload expõe funções estreitas, nunca o `ipcRenderer`. Tauri: capability por janela com o mínimo de permissão; por padrão todo comando registrado fica liberado para todas as janelas (restrinja com `AppManifest::commands` no `build.rs`).
  ```js
  new BrowserWindow({ webPreferences: { preload: path.join(__dirname, "preload.js"),
    contextIsolation: true, nodeIntegration: false, sandbox: true } }); // padrões atuais: não desligue
  ipcMain.handle("salvar-nota", (event, nota) => {
    if (new URL(event.senderFrame?.url ?? "about:blank").origin !== ORIGEM_DO_APP) throw new Error("origem");
    return salvar(NotaSchema.parse(nota));
  });
  ```
- **C09 Proteger cookies** — token cifrado com `safeStorage.encryptString` (chaveiro do sistema), não em `localStorage`. Tauri: chaveiro do sistema pelo lado Rust (crate `keyring`), não `tauri-plugin-store` (JSON em texto puro).
- **C14 Validação dos inputs** — `shell.openExternal` só com URL `https:` validada; `setWindowOpenHandler(() => ({ action: "deny" }))`; bloqueie `will-navigate` para outra origem. Tauri: argumento de comando tipado e validado no Rust; escopo de `fs`, `shell` e `http` restrito.
- **C18 Security headers** — Electron: CSP por `<meta http-equiv>` ou `session.defaultSession.webRequest.onHeadersReceived`, com `script-src 'self'`. Tauri: sem `app.security.csp` não há CSP; com ela, o Tauri injeta hash e nonce sozinho (`'wasm-unsafe-eval'` se usar WASM).
- **C19 Forçar HTTPS** — carregue só `https://` ou protocolo próprio (`protocol.handle`) em vez de `file://`; nunca `webSecurity: false` nem `allowRunningInsecureContent`.
- **C20 Scan de dependências** — o Electron só corrige as três últimas versões estáveis (Chromium): fique nelas. Fuses com `@electron/fuses`: desligue `RunAsNode`, `EnableNodeOptionsEnvironmentVariable` e `EnableNodeCliInspectArguments`; ligue `EnableEmbeddedAsarIntegrityValidation` e `OnlyLoadAppFromAsar`. Auto-update só por HTTPS e com build assinado.

## Extensões de navegador

**O que vai para o cliente**
- O pacote inteiro (CRX e XPI abrem como zip), com qualquer variável que o bundler injetar: `PLASMO_PUBLIC_*` (Plasmo), `WXT_*` e `VITE_*` (WXT). `chrome.storage.local` fica sem cifra no disco do usuário.
- Content script roda dentro de página que você não controla: o que ele recebe pode ter sido forjado pela página.

**Onde olhar primeiro**
- `manifest.json` (ou `wxt.config.ts`; no Plasmo, `manifest` do `package.json`): `permissions`, `host_permissions`, `content_scripts.matches`, `externally_connectable`, `web_accessible_resources`, `content_security_policy`.
- Service worker (`background.*`), `chrome.runtime.onMessage` e `onMessageExternal`, `window.addEventListener("message")` nos content scripts, `innerHTML` em content script e popup, `chrome.storage.*` com token.

**Sinais do scanner**
- Tudo é cliente: chaves e `public_env_secret` com `PLASMO_PUBLIC_`, `WXT_`, `VITE_` → C01 · os genéricos de C09, C14 e C19 valem aqui.
- Limites: permissões do manifest, `externally_connectable`, validação de mensagens e token em `chrome.storage` são revisão manual.

**Correções por checagem**
- **C01 Esconder API Keys** — nenhuma chave na extensão; ela chama o seu back-end, que autentica o usuário.
- **C07 Restringir acessos** — mínimo de permissão: `host_permissions` específicos em vez de `<all_urls>`, `activeTab` ou `optional_host_permissions` quando der; `web_accessible_resources` com `matches` restrito; `externally_connectable` só com origens suas.
- **C09 Proteger cookies** — token em `chrome.storage.session` (memória; content script não lê por padrão), renovado pelo back. Nunca no `localStorage` da página.
- **C14 Validação dos inputs** — mensagem vinda de content script ou de `onMessageExternal` é dado de atacante: confira `sender.id`/`sender.origin` e valide com schema. `postMessage` da página: `event.source === window` e formato esperado. Nada de `innerHTML` com dado da página ou da API: `textContent` ou DOMPurify.
- **C18 Security headers** — o MV3 não deixa a CSP de `extension_pages` passar de `script-src 'self' 'wasm-unsafe-eval'; object-src 'self'` e não roda código remoto: não tente contornar com `eval` ou script de CDN.
- **C19 Forçar HTTPS** — toda chamada em `https://`.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
