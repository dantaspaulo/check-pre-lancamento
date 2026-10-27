<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# As 20 checagens · critério de avaliação e correção

Este arquivo é o critério oficial da skill. Para cada checagem: o que olhar, quando é FALHA / ATENÇÃO / OK / N/A, e como corrigir por stack. O scanner (`scripts/scan.py`) só faz triagem — a decisão final sai daqui, depois de ler o código.

Os exemplos de correção abaixo são os mais comuns (Next.js, Node, Supabase, Python). Para outras stacks, a correção equivalente está em `references/stacks/` (front e mobile, back-end JS, PHP/Python/Ruby, Java/.NET/Go, BaaS); para apps de plataforma, em `references/plataformas.md`; os 10 itens de prontidão (P01–P10), em `references/prontidao.md`.

## Índice

| ID | Checagem | Severidade base | Bloco |
|---|---|---|---|
| C01 | Esconder API Keys | CRÍTICO | Segredos |
| C02 | Limpar secrets do Git | CRÍTICO | Segredos |
| C03 | Usar apenas Public Key no DB | CRÍTICO | Segredos |
| C04 | Ativar RLS | CRÍTICO | Dados |
| C05 | Criptografia de dados | ALTO | Dados |
| C06 | Auth server-side | CRÍTICO | Identidade |
| C07 | Restringir acessos | CRÍTICO | Identidade |
| C08 | Bloquear Mass Assignment | ALTO | Identidade |
| C09 | Proteger cookies | ALTO | Identidade |
| C10 | Hash nas senhas | CRÍTICO | Identidade |
| C11 | Rate limit | ALTO | Abuso |
| C12 | Bot protection | MÉDIO | Abuso |
| C13 | Queries parametrizadas | CRÍTICO | Entrada |
| C14 | Validação dos inputs | ALTO | Entrada |
| C15 | Evitar vazamento de conteúdo | MÉDIO | Saída |
| C16 | Restringir uploads | ALTO | Entrada |
| C17 | Limitar respostas de API | MÉDIO | Saída |
| C18 | Security headers | MÉDIO | Infra |
| C19 | Forçar HTTPS | ALTO | Infra |
| C20 | Scan de dependências | ALTO | Infra |

## Regras gerais de status

- **FALHA** — você viu o problema no código/config (arquivo:linha) ou na resposta do site. Não precisa de prova de exploração.
- **ATENÇÃO** — indício forte mas não confirmado, correção parcial, ou não dá pra verificar sem acesso externo (painel do Supabase, Cloudflare, variáveis da Vercel). Sempre diga o que falta validar e como.
- **OK** — você verificou e está certo. Cite a evidência (ex.: "helmet() em server.ts:12", "Supabase Auth gerencia hash"). "O scanner não achou nada" não é evidência para checagens semânticas (C06, C07, C08, C14, C17): para essas, OK só depois de revisar as rotas.
- **N/A** — a superfície não existe (sem upload → C16 N/A; sem senha própria → C10 N/A; sem Supabase/Firebase/PostgREST → C04 N/A). Diga por quê.

**Precedência:** se qualquer critério de FALHA de uma checagem está confirmado, o status é FALHA — mesmo que outras partes dela não sejam verificáveis daqui. As partes não verificadas entram no `resumo`/`acao_manual`. Ex.: C19 com `ssl: false` no código é FALHA, ainda que o redirect HTTPS não possa ser testado sem URL; C20 com Next vulnerável é FALHA, ainda que o `npm audit` não tenha rodado.

**Status que depende de decisão pendente** (onde vai rodar, qual banco, se o cadastro é aberto): use ATENÇÃO com a severidade do pior cenário plausível, registre a pergunta em `decisoes_pendentes` e diga no `resumo` o que muda em cada resposta. Não marque OK nem N/A apostando no cenário bom.

**Risco real sem checagem própria** (painel admin exposto, `/docs` público, senha enviada por e-mail, sessão longa sem revogação, credencial padrão aceita): encaixe na checagem mais próxima — sessão/token/autenticação → C06; acesso/painéis/papéis → C07; exposição/debug/documentação/logs → C15 — e deixe claro no `resumo`. Não invente checagem nova: o placar tem sempre 20.

**Código que hoje não é usado** (componente não importado, rota órfã): avalie como se estivesse em uso — basta alguém importar amanhã. Diga no `resumo` que hoje está morto e ofereça "apagar" como correção válida. Segredo é FALHA em qualquer arquivo, usado ou não (está no repo e no histórico).

**Severidade efetiva:** comece pela base e ajuste pelo contexto, sempre justificando no `risco`. A nota usa a severidade efetiva como peso, então o ajuste importa. Referências:

| Situação | Severidade efetiva |
|---|---|
| Chave live/de produção exposta, service role no cliente, tabela com dado pessoal sem RLS | CRÍTICO |
| Chave de teste/sandbox exposta | ALTO |
| Cartão/CVV armazenado, dado de saúde em texto puro | CRÍTICO |
| CPF/telefone em texto puro com RLS correto | MÉDIO |
| Endpoint de IA, e-mail ou SMS sem rate limit | ALTO |
| Login/cadastro sem rate limit em auth gerenciada (Supabase/Clerk já limitam) | MÉDIO |
| Flask `debug=True` / Werkzeug debugger em produção | CRÍTICO |
| Upload sem auth gravando no disco do servidor ou com nome do cliente | CRÍTICO |
| Upload autenticado sem validação de tipo para bucket privado | MÉDIO |
| Next.js na faixa do React2Shell | CRÍTICO |
| Source maps públicos sem segredo no código | BAIXO |
| App interno atrás de SSO/VPN (superfície pública pequena) | reduza um nível nas checagens de abuso (C11, C12) |

**C18 e C19 sem URL:** avalie pelo código e config. Plataformas como Vercel e Netlify adicionam HSTS e HTTPS sozinhas, mas não CSP, anti-clickjacking nem nosniff — se nada disso está no código/config, C18 é FALHA. Deixe a confirmação com `check_url.py` como ação manual.

---

## C01 · Esconder API Keys

**Severidade base:** CRÍTICO

**O que é:** nenhuma chave secreta (OpenAI, Anthropic, Stripe secret, Mercado Pago, Asaas, AWS, SendGrid, service role do banco…) pode estar no código que vai pro navegador/app nem hardcoded em lugar nenhum. Chave no front é chave pública: qualquer um abre o DevTools e copia.

**Como detectar:**
- Scanner: padrões de chaves conhecidas, atribuições `apiKey = "..."`, variáveis com prefixo público carregando segredo (`NEXT_PUBLIC_OPENAI_API_KEY`, `VITE_OPENAI_API_KEY`, `REACT_APP_STRIPE_SECRET`, `EXPO_PUBLIC_...`), `dangerouslyAllowBrowser: true` (SDKs da OpenAI/Anthropic no navegador), chamadas diretas a `api.openai.com`/`api.anthropic.com` em arquivo de cliente.
- Manual: confirme se o arquivo roda no cliente. No Next.js App Router, componente com `"use client"` e tudo que ele importa vai pro bundle. Em SPA (Vite/CRA), tudo dentro de `src/` vai pro bundle. Apps mobile (Expo/React Native/Flutter) = cliente: a chave sai no binário.
- Se houver URL publicada, `check_url.py` baixa os bundles JS e procura chaves — é a prova definitiva.

**FALHA:** qualquer segredo real hardcoded (cliente ou servidor), ou segredo exposto via variável com prefixo público, ou SDK de LLM com `dangerouslyAllowBrowser: true`.
**ATENÇÃO:** Google `AIza…` no front (pública se for config do Firebase/Maps com restrição de domínio; secreta se for Gemini). Chave Stripe de **teste** no front (ALTO).
**OK:** segredos só em variáveis de ambiente sem prefixo público, lidos apenas no servidor.
**Nunca é falha:** Supabase `anon`/`sb_publishable_`, Stripe `pk_live_`/`pk_test_`, Firebase web config, Sentry DSN, IDs do Google Analytics — são públicos por design (a segurança vem de RLS/regras, ver C03/C04).

**Como corrigir:**
1. Mover a chamada que usa a chave para o servidor (rota de API, Server Action, Edge Function, Cloud Function) e o front chama essa rota.
2. Renomear a variável tirando o prefixo público e ler só no servidor.
3. **Rotacionar a chave** no painel do provedor — removida do código, ela continua vazada (bundle já publicado, cache, histórico do Git). Ação manual.

Next.js (App Router):
```ts
// app/api/chat/route.ts  — roda só no servidor
import OpenAI from "openai";
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY }); // sem NEXT_PUBLIC_

export async function POST(req: Request) {
  // + auth (C06), validação (C14) e rate limit (C11)
  const { message } = await req.json();
  const r = await openai.responses.create({ model: "gpt-4.1-mini", input: message });
  return Response.json({ text: r.output_text });
}
```
Para garantir que um módulo nunca vá pro cliente: `import "server-only";` no topo de `lib/openai.ts`.

Vite/React SPA: não existe "servidor" — crie uma função serverless (Vercel `api/`, Netlify Functions, Supabase Edge Function) e chame ela. `VITE_*` sempre vai pro bundle.

Supabase Edge Function: `Deno.env.get("OPENAI_API_KEY")` + `supabase secrets set OPENAI_API_KEY=...`.

Mobile (Expo/RN/Flutter): nenhuma chave secreta no app; sempre via backend.

---

## C02 · Limpar secrets do Git

**Severidade base:** CRÍTICO

**O que é:** `.env`, chaves `.pem`, `service-account.json`, `credentials.json` não podem estar versionados — nem hoje, nem no histórico. Repo público com chave no histórico é varrido por bots em minutos.

**Como detectar:**
- Scanner: arquivos sensíveis rastreados (`git ls-files`), `.gitignore` sem `.env`, arquivos `.env*` que já foram adicionados em algum commit, segredos de alta confiança em linhas adicionadas no histórico.
- Se `gitleaks` ou `trufflehog` estiverem instalados, rode: `gitleaks detect --redact --no-banner -v` (mais completo que o scanner).
- Pergunte (ou verifique via `git remote -v` + GitHub) se o repo é público. Repo público agrava: severidade continua CRÍTICO e a rotação vira urgente.

**FALHA:** `.env` (ou equivalente com valores reais) rastreado; segredo real em qualquer commit; chave privada versionada.
**ATENÇÃO:** `.gitignore` não cobre `.env*` mas nenhum foi commitado ainda; `.env.example` com algo que parece valor real.
**OK:** `.gitignore` cobre `.env*`, nada sensível rastreado, histórico limpo.
**N/A:** projeto não é repositório git (registre isso e recomende versionar com `.gitignore` correto).

**Como corrigir (ordem importa):**
1. **Rotacionar todas as chaves que já foram commitadas** (manual, no painel de cada provedor). Limpar o histórico sem rotacionar não resolve: forks, clones e caches já têm a chave.
2. Parar de versionar:
```bash
cat >> .gitignore <<'EOF'
.env
.env.*
!.env.example
*.pem
*.key
service-account*.json
EOF
git rm --cached .env .env.local 2>/dev/null
git commit -m "chore(security): stop tracking env files"
```
3. Criar `.env.example` só com nomes, sem valores.
4. (Opcional, destrutivo — só com OK explícito do dono do repo) reescrever histórico com `git filter-repo --path .env --invert-paths` ou BFG, depois `git push --force` e avisar o time para reclonar.
5. Prevenção: pre-commit com gitleaks (`gitleaks protect --staged`) e GitHub Secret Scanning + Push Protection ativos.

---

## C03 · Usar apenas Public Key no DB

**Severidade base:** CRÍTICO

**O que é:** o cliente (navegador/app) só pode falar com o banco usando a chave pública (Supabase `anon` / `sb_publishable_`, Firebase web config), que respeita RLS/regras. A chave de serviço (`service_role` / `sb_secret_`, Firebase Admin SDK, connection string do Postgres) ignora todas as regras — no front, ela dá acesso total ao banco para qualquer visitante.

**Como detectar:**
- Scanner: JWT com `"role":"service_role"` em qualquer arquivo, `sb_secret_`, `SUPABASE_SERVICE_ROLE_KEY` referenciada em arquivo de cliente ou com prefixo público, `firebase-admin` importado em código de cliente, `DATABASE_URL` com prefixo público, drivers de banco (`pg`, `mysql2`, `mongoose`, `@prisma/client`) importados em componente `"use client"`.
- Manual: procure clientes "admin" (`supabaseAdmin`, `createClient(url, SERVICE_ROLE)`) e confirme que só são importados em código de servidor.

**FALHA:** service role / admin SDK / connection string acessível no cliente.
**ATENÇÃO:** cliente admin num arquivo compartilhado (`lib/supabase.ts`) importado tanto por server quanto por client.
**OK:** cliente usa só a chave pública; cliente admin isolado em código server-only.
**N/A:** app sem banco acessado pelo cliente (só backend próprio falando com o banco) — aí o foco vai para C06/C07.

**Como corrigir:**
```ts
// lib/supabase/client.ts — navegador: SÓ chave pública
import { createBrowserClient } from "@supabase/ssr";
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY! // ou PUBLISHABLE_KEY
);

// lib/supabase/admin.ts — só servidor
import "server-only";
import { createClient } from "@supabase/supabase-js";
export const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // sem NEXT_PUBLIC_
);
```
Use o admin só quando precisar ignorar RLS de propósito (webhooks, jobs), sempre depois de autenticar/autorizar a requisição. Se a service role vazou: **rotacione** (Supabase → Settings → API; nas chaves novas, revogue a `sb_secret_` antiga). Firebase: Admin SDK só em Cloud Functions/servidor.

---

## C04 · Ativar RLS

**Severidade base:** CRÍTICO

**O que é:** com a chave pública no front (C03), quem protege os dados é o Row Level Security (Supabase/Postgres) ou as Security Rules (Firebase). Tabela sem RLS = qualquer pessoa com a anon key (que está no seu site) lê e escreve tudo. É a falha nº 1 de apps feitos com Lovable/Bolt/Supabase.

**Duas camadas, não uma.** O GRANT decide se o papel (`anon` = visitante sem login, `authenticated` = qualquer conta logada) pode rodar SELECT, INSERT, UPDATE ou DELETE na tabela. A RLS decide quais linhas ele vê. Até 30/10/2026, todo projeto Supabase antigo dava SELECT, INSERT, UPDATE e DELETE para `anon` e `authenticated` em toda tabela nova do `public`, e a RLS era a única barreira: sem margem de erro, uma policy errada vira vazamento. A partir de 30/10/2026 a tabela nova nasce sem GRANT (em projeto criado depois de 30/05/2026, já era assim; as tabelas antigas continuam com o que tinham; fonte: [changelog do Supabase](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically)). Quem receber o erro 42501 vai cair na tentação do GRANT em massa, que reabre tudo.

**Como detectar:**
- Scanner (lê as migrations comando por comando, na ordem, sem comentários):
  - tabelas sem `enable row level security` (`tabela_sem_rls`) e `disable row level security` (`rls_desativado`);
  - policies abertas separadas por público: `policy_publica_leitura` e `policy_publica_escrita` (sem `to` ou `to anon`/`public`: visitante sem login) e `policy_qualquer_logado_leitura` e `policy_qualquer_logado_escrita` (`to authenticated using (true)` ou só `auth.uid() is not null`). Leitura de tabela com nome de catálogo (CID, CBHPM, TUSS, estados, categorias, planos) cai para confiança baixa; com nome de dado de usuário (perfis, pacientes, pedidos, mensagens, documentos) sobe;
  - `anon_com_escrita`: o anon recebe INSERT/UPDATE/DELETE por GRANT (comum em schema exportado por `supabase db pull`, que escreve um GRANT por tabela);
  - `grant_em_massa_tabelas` e `grant_execute_em_massa`: `grant ... on all tables/functions in schema public`;
  - `privilegio_padrao_aberto`: `alter default privileges ... grant` para anon/authenticated, que abre todo objeto novo;
  - `funcao_security_definer_exposta`: função `security definer` no `public` que o visitante chama por `/rest/v1/rpc/<nome>`, incluindo o caso de quem revogou só do `anon` (o `anon` herda de `PUBLIC`, que tem EXECUTE por padrão), e `security_definer_sem_search_path`;
  - `view_ignora_rls` (view sem `security_invoker`), `view_materializada_exposta`, `auto_expose_ligado` (`[api] auto_expose_new_tables = true` no `supabase/config.toml`) e `permissoes_do_banco_nao_verificadas` (migrations sem nenhum GRANT ou REVOKE: o estado real só aparece no banco);
  - Firebase: em `firestore.rules`/`storage.rules`/`database.rules.json`, `allow read, write: if true`, regra de "modo de teste" (`request.time < timestamp.date(...)`), `".read": true` na raiz.
- O que as migrations não mostram, só o banco mostra: os GRANTs que o Supabase deu sozinho, o que foi mudado pelo painel e o estado depois de 30/10. Rode as consultas de `references/stacks/baas.md` → "Consulta de permissões" (só leitura): pelo MCP/conector do Supabase, se houver, ou peça ao usuário para rodar no SQL Editor e colar o resultado.
- Se não houver migrations no repo, o estado real está só no banco. Opções:
  - Se houver MCP do Supabase conectado, use-o para rodar as queries abaixo (somente leitura).
  - Senão, peça ao usuário rodar no SQL Editor e colar o resultado:
```sql
-- tabelas do schema public sem RLS
select tablename, rowsecurity from pg_tables where schemaname = 'public' order by 2, 1;
-- policies existentes
select tablename, policyname, cmd, roles, qual, with_check from pg_policies where schemaname = 'public';
-- buckets públicos do Storage
select id, public from storage.buckets;
```
- Revise cada policy pelo público e pela operação:
  - `using (true)` em SELECT `to authenticated` numa tabela de catálogo (CID, CBHPM, lista de especialidades): normalmente OK, porque é dado de referência que todo usuário vê;
  - o mesmo para `anon` ou sem `to`: leitura pública sem login, OK só se a tabela não tem nada de usuário;
  - INSERT `to anon` com `with check (true)` em formulário público (contato, lista de espera): aceitável com captcha ou rate limit e sem leitura pública da tabela;
  - UPDATE, DELETE ou `for all` com `true`, para `anon` ou `authenticated`: quase nunca é intencional (qualquer conta altera a linha das outras).
- Outros back-ends gerenciados entram aqui também: **PocketBase** (API rule vazia `""` = pública; `null` = só superusuário), **Appwrite** (permissões com `Role.any()` em escrita), **Convex** (não tem RLS: a autorização fica dentro de cada função — ver C06), **Bubble** (privacy rules). Ver `references/stacks/baas.md`.
- Com a URL publicada e o OK do dono, `check_url.py --sondar-dados` usa a chave pública do próprio site para contar quantas linhas cada tabela do Supabase devolve sem login e testar Firestore/Realtime DB/Storage. É a prova mais forte desta checagem.

**FALHA:** tabela com dados de usuário sem RLS; policy permissiva em escrita; leitura aberta (pública ou de qualquer conta) em tabela com dado de usuário; função `security definer` que apaga ou altera dado chamável sem login; GRANT em massa para `anon`; Firebase em modo teste/`if true`.
**ATENÇÃO:** não foi possível verificar (sem migrations e sem acesso ao banco) — marque e deixe a consulta de permissões como ação manual; `anon` com INSERT/UPDATE/DELETE por GRANT em tabelas com RLS (a RLS segura, mas sem margem de erro); privilégio padrão que abre todo objeto novo; view sem `security_invoker`; policy `using (true)` em leitura de tabela que pode ter dado sensível.
**OK:** todas as tabelas do schema exposto com RLS e policies por dono (`auth.uid()`), revisadas; `anon` só com o que o visitante precisa (normalmente SELECT em poucas tabelas, ou nada); funções `security definer` fechadas para quem não usa.
**N/A:** sem Supabase/Firebase/PostgREST e banco não exposto ao cliente. Atenção: Supabase usado "só como Postgres" ainda expõe o schema `public` pela Data API (com a anon key) se ela não foi desativada — aí RLS continua obrigatório; sem saber se a Data API está ligada, é ATENÇÃO.

**Como corrigir:**
```sql
alter table public.profiles enable row level security;

-- leitura: só o dono
create policy "profiles_select_own" on public.profiles
  for select to authenticated using ((select auth.uid()) = user_id);
-- escrita: só o dono, e não deixa trocar o dono
create policy "profiles_update_own" on public.profiles
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "profiles_insert_own" on public.profiles
  for insert to authenticated with check ((select auth.uid()) = user_id);
```
- RLS ligado sem nenhuma policy = ninguém acessa via anon key (seguro por padrão; libere só o necessário).
- Colunas que o usuário não pode mudar (`role`, `plan`, `credits`): não confie só em RLS por linha — use trigger, coluna em tabela separada ou `revoke update (role) on profiles from authenticated` (ver C08).
- Views: crie com `with (security_invoker = true)` para respeitarem RLS. Funções `security definer` expostas via RPC ignoram RLS — revise.
- **GRANT por tabela, nunca em massa.** Tirar do `anon` o que o visitante não usa, e devolver só o necessário, objeto por objeto:
```sql
-- antes de mexer: salve o resultado da "Consulta de permissões" (references/stacks/baas.md)
revoke insert, update, delete, truncate on table public.profiles from anon;
grant select, insert, update, delete on table public.profiles to authenticated;  -- só se o app escreve logado
alter table public.profiles enable row level security;
-- função interna: revogar de public E de anon (o anon herda de PUBLIC); se o app não chama, de authenticated também
revoke execute on function public.apagar_usuario(uuid) from public, anon, authenticated;
-- função que o front chama logado (supabase.rpc): só ela, só para authenticated, e ela confere auth.uid() por dentro
revoke execute on function public.meus_pedidos() from public, anon;
grant execute on function public.meus_pedidos() to authenticated;
```
  - **Cuidado na volta:** depois de revogar o `anon` em massa, não devolva `grant execute on all functions in schema public to authenticated`. As funções internas, fechadas de propósito (as que apagam, mudam papel ou leem tudo), voltam a abrir. Liste as funções que o front chama por `supabase.rpc('...')` e conceda só essas.
  - Privilégio padrão: `alter default privileges for role postgres in schema public revoke select, insert, update, delete on tables from anon, authenticated;` faz o objeto novo nascer fechado. Ele só vale para objetos criados pelo papel indicado (`for role`).
  - Teste depois de mudar: um visitante sem login e duas contas diferentes (a A não lê nem altera a linha da B).
- Firebase:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```
- Gere a migration com as policies (para ficar versionado) e aplique via `supabase db push` ou SQL Editor (ação manual se o Claude não tiver acesso ao banco).

---

## C05 · Criptografia de dados

**Severidade base:** ALTO

**O que é:** dado sensível (CPF, RG, dados de saúde, documentos, tokens OAuth de terceiros, chaves de API de clientes) não deve ficar em texto puro no banco quando um vazamento de backup/dump o expõe direto. Dado de cartão nunca deve ser armazenado — use tokenização do gateway. Em trânsito, conexão com o banco via TLS. LGPD: dado sensível exige medidas de segurança proporcionais (art. 46).

**Como detectar:**
- Scanner: colunas com nomes sensíveis em schemas/migrations (`cpf`, `rg`, `card_number`, `cvv`, `numero_cartao`, `access_token`, `refresh_token`, `diagnostico`…), uso de cripto fraca (`createCipher(` sem IV, `aes-*-ecb`, `DES`), sinais de criptografia (pgcrypto, Supabase Vault, `createCipheriv('aes-256-gcm')`, Fernet, KMS).
- Manual: liste quais dados sensíveis o app guarda e como.

**FALHA:** número de cartão/CVV armazenado; tokens de terceiros ou dado sensível em texto puro sem nenhuma proteção; algoritmo quebrado (ECB, DES, `createCipher`).
**ATENÇÃO:** dado pessoal comum (CPF, telefone) em texto puro com RLS correto — recomende criptografia em nível de aplicação ou ao menos mascaramento + controle de acesso; criptografia presente mas com chave hardcoded.
**OK:** sensíveis cifrados (aplicação com AES-256-GCM e chave fora do código, pgcrypto/Vault), cartão tokenizado no gateway.
**N/A:** app não guarda nenhum dado pessoal/sensível.

**Como corrigir (Node, AES-256-GCM):**
```ts
import "server-only";
import { createCipheriv, createDecipheriv, randomBytes } from "crypto";
const KEY = Buffer.from(process.env.DATA_ENCRYPTION_KEY!, "base64"); // 32 bytes, gere com: openssl rand -base64 32

export function encrypt(plain: string) {
  const iv = randomBytes(12);
  const c = createCipheriv("aes-256-gcm", KEY, iv);
  const enc = Buffer.concat([c.update(plain, "utf8"), c.final()]);
  return [iv, c.getAuthTag(), enc].map(b => b.toString("base64")).join(".");
}
export function decrypt(payload: string) {
  const [iv, tag, enc] = payload.split(".").map(s => Buffer.from(s, "base64"));
  const d = createDecipheriv("aes-256-gcm", KEY, iv);
  d.setAuthTag(tag);
  return Buffer.concat([d.update(enc), d.final()]).toString("utf8");
}
```
Supabase: para segredos de integração use Vault (`select vault.create_secret('valor', 'nome')`). Python: `cryptography.fernet`. Se precisar buscar por CPF, guarde também um hash HMAC do CPF para lookup. Pagamentos: Stripe/Mercado Pago/Pagar.me tokenizam — guarde só o id do cliente/cartão do gateway.

---

## C06 · Auth server-side

**Severidade base:** CRÍTICO

**O que é:** quem decide se a requisição está autenticada é o servidor, em toda rota/ação. Esconder botão, redirecionar no `useEffect` ou checar só no middleware não protege nada: a API continua aberta para `curl`.

**Como detectar:**
- Scanner: lista arquivos de rota (`app/**/route.ts`, `pages/api/**`, Server Actions `"use server"`, Express/Fastify/Hono, FastAPI/Flask/Django, Supabase Edge Functions) sem marcador de auth aparente; `supabase.auth.getSession()` em código de servidor; versão do Next vulnerável ao bypass de middleware (CVE-2025-29927).
- Manual (obrigatório): abra cada rota que lê/escreve dado de usuário e confirme que ela valida a sessão/token **dentro do handler** (ou em wrapper aplicado a ela) antes de qualquer acesso a dado. Rotas intencionalmente públicas (landing, webhook com assinatura, health check) devem ser listadas como tal.
- Server Actions do Next são endpoints públicos: cada uma precisa checar auth.
- Webhooks: devem verificar assinatura (`stripe.webhooks.constructEvent`, header de assinatura do Mercado Pago/Asaas).
- Supabase Edge Functions com `verify_jwt = false` em `supabase/config.toml` aceitam chamada sem login: só é aceitável com verificação própria dentro da função (webhook com assinatura, por exemplo). E `verify_jwt = true` também não prova login: ele aceita a chave pública (publishable/anon) que está no site. Dentro da função, identifique o usuário com `auth.getUser()`/`getClaims()` e responda 401 se não houver.
- Convex: `query`/`mutation`/`action` exportadas são públicas; use `internalQuery`/`internalMutation` para o que é interno e cheque `ctx.auth.getUserIdentity()` no resto.
- Laravel, Rails, Django/DRF, Spring, .NET e Go: o scanner avalia rota a rota quando dá (grupos de middleware no Laravel, `before_action` herdado no Rails, `DEFAULT_PERMISSION_CLASSES` no DRF, `permitAll()` no Spring). Ver `references/stacks/`.

**FALHA:** rota/ação que mexe em dado privado sem verificação de auth no servidor; auth só no cliente; webhook sem verificação de assinatura; `getSession()` usado como prova de identidade no servidor.
**ATENÇÃO:** auth só no `middleware.ts` (defesa única numa camada que já teve bypass); rotas sem auth que você não conseguiu classificar como públicas.
**OK:** todas as rotas privadas validam sessão no servidor; públicas listadas e justificadas.

**Como corrigir:**
```ts
// Next.js + Supabase (servidor): use getUser(), que valida o JWT no Auth server
import { createClient } from "@/lib/supabase/server";
export async function POST(req: Request) {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) return Response.json({ error: "unauthorized" }, { status: 401 });
  // ... daqui pra baixo, use user.id (nunca um userId vindo do body)
}
```
```ts
// Server Action
"use server";
export async function updateProfile(input: unknown) {
  const user = await requireUser(); // lança se não autenticado
  // ...
}
```
```ts
// Express
function requireAuth(req, res, next) {
  const token = req.cookies.session ?? req.headers.authorization?.replace("Bearer ", "");
  try { req.user = jwt.verify(token, process.env.JWT_SECRET, { algorithms: ["HS256"] }); next(); }
  catch { res.status(401).json({ error: "unauthorized" }); }
}
app.use("/api/private", requireAuth);
```
```py
# FastAPI
@app.get("/me")
def me(user: User = Depends(get_current_user)): ...
```
- Middleware do Next serve para redirecionar páginas, não como única barreira. Atualize o Next para versão corrigida (≥ 12.3.5 / 13.5.9 / 14.2.25 / 15.2.3) se estiver abaixo.
- JWT próprio: fixe o algoritmo, valide `exp`, `iss`, `aud`; segredo forte em env.

---

## C07 · Restringir acessos

**Severidade base:** CRÍTICO

**O que é:** autenticado não é autorizado. Usuário A não pode ler/editar recurso do usuário B trocando o id na URL (IDOR/BOLA — o risco nº 1 de APIs no OWASP). Rotas de admin exigem papel de admin verificado no servidor. Menor privilégio também vale para CORS, chaves de serviço e contas de banco.

**Como detectar:**
- Scanner: buscas por id vindo do request (`where: { id: params.id }`, `findById(req.params.id)`, `.eq('id', ...)`), `userId`/`role`/`isAdmin` lidos do body/query, rotas `/admin` sem checagem de papel, CORS `*` (pior com `credentials: true`).
- Manual: para cada rota que recebe um id, confirme que a consulta filtra pelo dono (`where: { id, userId: user.id }`) ou checa papel/permissão. Com Supabase + RLS correto (C04), queries feitas com o cliente do usuário já são filtradas — mas queries com `supabaseAdmin` não.

**FALHA:** consulta/alteração por id sem filtro de dono nem checagem de permissão; papel/dono vindo do cliente; admin verificado só no front; CORS refletindo qualquer origem com credenciais.
**ATENÇÃO:** CORS `*` sem credenciais em API que não é pública; multi-tenant sem filtro por tenant em alguma rota.
**OK:** toda leitura/escrita amarrada ao usuário/tenant da sessão; papéis checados no servidor; CORS com allowlist.

**Como corrigir:**
```ts
// Prisma: o dono faz parte do WHERE
const doc = await prisma.document.findFirst({ where: { id: params.id, ownerId: user.id } });
if (!doc) return Response.json({ error: "not found" }, { status: 404 }); // 404, não 403, para não confirmar existência
```
```ts
// papel checado no servidor, a partir do banco/claims — nunca do body
if (user.app_metadata?.role !== "admin") return Response.json({ error: "forbidden" }, { status: 403 });
```
```ts
// CORS com allowlist
app.use(cors({ origin: ["https://meuapp.com.br"], credentials: true }));
```
Supabase: papéis em `app_metadata` (só o servidor altera), nunca em `user_metadata` (o próprio usuário altera).

---

## C08 · Bloquear Mass Assignment

**Severidade base:** ALTO

**O que é:** jogar o body inteiro no banco (`prisma.user.update({ data: req.body })`, `.insert(body)`, `Object.assign(user, req.body)`) deixa o usuário mandar campos extras: `role: "admin"`, `plan: "pro"`, `credits: 999999`, `ownerId` de outra pessoa.

**Como detectar:**
- Scanner: `data: req.body`/`data: body`, `.create(req.body)`, `.update(body)`, `.insert(body)`, `...req.body`, `Object.assign(x, req.body)`, `**request.json`, Django `fields = '__all__'`, Rails `permit!`, Laravel `$guarded = []`.
- Manual: siga o caminho do input até o banco em rotas de criação/edição, inclusive Server Actions recebendo `FormData`/objeto.
- Supabase: update direto do front em tabela com colunas sensíveis (`role`, `credits`) é mass assignment também — RLS de linha não impede mudar a coluna.

**FALHA:** objeto do request passado direto para criação/edição em entidade com campo sensível.
**ATENÇÃO:** passado direto mas a entidade não tem campo sensível hoje (frágil: o próximo campo adicionado vira brecha).
**OK:** allowlist explícita de campos (schema de validação com objeto estrito, `pick`, DTO).

**Como corrigir:**
```ts
import { z } from "zod";
const UpdateProfile = z.object({
  name: z.string().min(1).max(80),
  bio: z.string().max(500).optional(),
}).strict(); // rejeita campos extras

const input = UpdateProfile.parse(await req.json());
await prisma.user.update({ where: { id: user.id }, data: input });
```
Supabase (colunas que o usuário não pode alterar):
```sql
revoke update on public.profiles from authenticated;
grant update (name, bio, avatar_url) on public.profiles to authenticated;
```
Django: `fields = ["name", "bio"]` no form/serializer, `read_only_fields` para o resto.

---

## C09 · Proteger cookies

**Severidade base:** ALTO

**O que é:** token de sessão em `localStorage` é legível por qualquer script (um XSS rouba a sessão). Cookie de sessão deve ser `HttpOnly` (JS não lê), `Secure` (só HTTPS) e `SameSite=Lax` ou `Strict` (mitiga CSRF).

**Como detectar:**
- Scanner: `localStorage.setItem` com token/jwt/session, `document.cookie =` com token, `httpOnly: false`, `secure: false`, `sameSite: 'none'`, `res.cookie(` sem flags, Django `SESSION_COOKIE_SECURE = False`.
- Se houver URL: `check_url.py` lê `Set-Cookie` e confere as flags.
- Supabase: `@supabase/supabase-js` puro no navegador guarda a sessão em `localStorage` (padrão aceito pelo Supabase para SPA). Em Next.js prefira `@supabase/ssr` (cookies). Registre como ATENÇÃO BAIXO em SPA, não como FALHA.

**FALHA:** token de sessão próprio em `localStorage`/cookie legível por JS; cookie de sessão sem `HttpOnly` ou sem `Secure` em produção; `SameSite=None` sem proteção CSRF.
**ATENÇÃO:** flags não verificáveis no código (definidas pela lib/plataforma) e sem URL para checar.
**OK:** sessão em cookie `HttpOnly; Secure; SameSite=Lax` (ou gerenciada por lib que faz isso: NextAuth/Auth.js, Clerk, `@supabase/ssr`, Lucia, Better Auth).

**Como corrigir:**
```ts
// Next.js
import { cookies } from "next/headers";
(await cookies()).set("session", token, {
  httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7,
});
```
```ts
// Express
res.cookie("session", token, { httpOnly: true, secure: true, sameSite: "lax", maxAge: 7 * 864e5 });
```
```py
# Django settings.py
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
```
Se precisar de `SameSite=None` (iframe/terceiros), adicione token CSRF.

Se migrar o token de `localStorage` para cookie não cabe antes do lançamento, o status continua ATENÇÃO (não OK), com controles compensatórios na correção: CSP forte (C18), token de acesso curto (≤ 1h) + refresh com rotação e revogação no logout, e zero `dangerouslySetInnerHTML`/`v-html` sem sanitização (C14).

---

## C10 · Hash nas senhas

**Severidade base:** CRÍTICO

**O que é:** se o app guarda senha própria, só hash lento e com salt: Argon2id (preferido), bcrypt (custo ≥ 10, ideal 12) ou scrypt. Nunca texto puro, nunca MD5/SHA1/SHA256 "puro" (são rápidos: GPU quebra bilhões por segundo).

**Como detectar:**
- Scanner: `createHash('md5'|'sha1'|'sha256')` ou `hashlib.md5/sha*` perto de `password`/`senha`; coluna `password`/`senha` sem "hash" no nome; criação de usuário gravando senha direto; bcrypt com custo < 10; presença de bcrypt/argon2.
- Manual: descubra quem gerencia senha. Supabase Auth, Firebase Auth, Clerk, Auth0, Cognito, NextAuth com OAuth, Better Auth → o provedor faz o hash (marque **OK** citando o provedor, ou **N/A** se só houver login social/magic link).

**FALHA:** senha em texto puro, hash rápido sem KDF, ou senha "criptografada" reversível (AES) em vez de hash.
**ATENÇÃO:** bcrypt com custo < 10; hash correto mas sem política mínima de senha (≥ 8 caracteres, checar vazadas).
**OK:** Argon2id/bcrypt/scrypt com parâmetros adequados, ou auth gerenciada.
**N/A:** app não tem login por senha.

**Como corrigir:**
```ts
import { hash, verify } from "@node-rs/argon2"; // ou "argon2"
const passwordHash = await hash(password); // defaults seguros (argon2id)
const ok = await verify(user.passwordHash, password);
```
```ts
import bcrypt from "bcryptjs";
const passwordHash = await bcrypt.hash(password, 12);
```
```py
from argon2 import PasswordHasher
ph = PasswordHasher(); h = ph.hash(password); ph.verify(h, password)
```
Migração de base com hash fraco: no próximo login bem-sucedido, re-hasheie com Argon2id; para usuários inativos, force reset de senha. Senhas em texto puro já gravadas: hasheie em lote via migration e trate como incidente (avaliar comunicação LGPD).

---

## C11 · Rate limit

**Severidade base:** ALTO

**O que é:** limite de requisições por IP/usuário em login, cadastro, reset de senha, OTP, formulários e — principalmente — endpoints que chamam IA ou mandam e-mail/SMS. Sem isso: força bruta de senha, enumeração, spam e conta da OpenAI/Anthropic estourando em uma noite.

**Como detectar:**
- Scanner: libs (`@upstash/ratelimit`, `express-rate-limit`, `rate-limiter-flexible`, `@nestjs/throttler`, `@fastify/rate-limit`, `hono-rate-limiter`, Arcjet, `slowapi`, `flask-limiter`, `django-ratelimit`, DRF throttling, `rack-attack`), chamadas `rateLimit(`/`Ratelimit`, e se há endpoints de IA no servidor.
- Manual: pergunte se existe rate limit fora do código (Cloudflare WAF/Rate Limiting, Vercel Firewall, API Gateway, Kong, nginx `limit_req`). Supabase Auth já limita os endpoints de auth dele (e-mails, OTP) — registre isso.

**FALHA:** nenhum rate limit em endpoint de IA, envio de e-mail/SMS, login/cadastro próprio.
**ATENÇÃO:** sem rate limit no código mas usuário diz que tem no edge (peça print/config); limite só em memória em ambiente serverless (cada instância tem seu contador — ineficaz).
**OK:** limites nas rotas sensíveis, com storage compartilhado (Redis/Upstash) em serverless.

**Como corrigir (serverless / Next.js com Upstash):**
```ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
const ratelimit = new Ratelimit({ redis: Redis.fromEnv(), limiter: Ratelimit.slidingWindow(10, "1 m") });

export async function POST(req: Request) {
  const user = await requireUser();
  const { success } = await ratelimit.limit(`chat:${user.id}`);
  if (!success) return Response.json({ error: "too many requests" }, { status: 429 });
  // ...
}
```
Express: `app.use("/api/auth", rateLimit({ windowMs: 15 * 60_000, limit: 20, standardHeaders: true }))` (com `app.set("trust proxy", 1)` atrás de proxy). FastAPI: `slowapi`. Para IA, além de rate limit: teto de tokens por requisição (`max_tokens`), cota diária por usuário e alerta de gasto no painel do provedor.

---

## C12 · Bot protection

**Severidade base:** MÉDIO

**O que é:** CAPTCHA/desafio invisível em cadastro, login, reset de senha, contato e qualquer formulário público. Rate limit (C11) segura volume; bot protection segura automação distribuída (cadastro em massa, spam, credential stuffing).

**Como detectar:**
- Scanner: Cloudflare Turnstile, reCAPTCHA, hCaptcha, Vercel BotID, Arcjet, ALTCHA, honeypot; se há formulários públicos/cadastro; se o token é verificado no servidor (`siteverify`) ou repassado ao Supabase (`captchaToken`).
- Manual: confirme que o token é validado no servidor. Widget só no front sem verificação = enfeite.

**FALHA:** cadastro/login/contato públicos sem nenhuma proteção anti-bot (em app que vai receber tráfego aberto).
**ATENÇÃO:** widget presente sem verificação no servidor; proteção só em parte dos formulários.
**OK:** formulários públicos protegidos e token verificado no servidor (ou pelo Supabase Auth com captcha habilitado).
**N/A:** app sem formulário público (uso interno atrás de SSO, por exemplo).

**Como corrigir (Turnstile):**
```tsx
// front
import { Turnstile } from "@marsidev/react-turnstile";
<Turnstile siteKey={process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY!} onSuccess={setToken} />
```
```ts
// servidor
const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
  method: "POST",
  body: new URLSearchParams({ secret: process.env.TURNSTILE_SECRET_KEY!, response: token, remoteip: ip }),
});
if (!(await r.json()).success) return Response.json({ error: "bot" }, { status: 400 });
```
Supabase Auth: habilite CAPTCHA em Authentication → Settings e passe `options: { captchaToken }` no `signUp`/`signInWithPassword`. Honeypot (campo escondido que humano não preenche) é um complemento barato.

---

## C13 · Queries parametrizadas

**Severidade base:** CRÍTICO

**O que é:** nunca montar SQL concatenando input. Use parâmetros/placeholders ou query builder/ORM. Vale para NoSQL (operadores `$` injetados) e para filtros do PostgREST/Supabase montados com string.

**Como detectar:**
- Scanner: `$queryRawUnsafe`/`$executeRawUnsafe`, `.query(\`... ${x}\`)`, `"SELECT ..." + x`, `sql.unsafe(`, `sql.raw(` com variável, Python `execute(f"...")`/`%`/`.format`, Django `.raw(f"...")`, SQLAlchemy `text(f"...")`, Mongo `find(req.body)`/`$where`, Supabase `.or(\`...${x}\`)`, PHP `mysqli_query` com `$_GET`.
- **Não são falha:** template tags seguras — Prisma `` $queryRaw`... ${x}` `` (sem parênteses), `` sql`...` `` (postgres.js, Drizzle, @vercel/postgres, Slonik), `knex.raw('... ?', [x])`.

**FALHA:** qualquer SQL/filtro montado com valor do usuário por concatenação/interpolação.
**ATENÇÃO:** interpolação de valor que hoje não vem do usuário (constante, enum interno) — frágil; nome de coluna/ordenação dinâmicos sem allowlist.
**OK:** todas as queries parametrizadas.
**N/A:** app sem banco/consultas próprias.

**Como corrigir:**
```ts
// ❌ await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE email = '${email}'`)
// ✅
await prisma.$queryRaw`SELECT id, name FROM users WHERE email = ${email}`;
// ✅ pg
await pool.query("SELECT id, name FROM users WHERE email = $1", [email]);
```
```py
cur.execute("SELECT id FROM users WHERE email = %s", (email,))   # psycopg
session.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
```
```ts
// Supabase: evite .or() com string interpolada; use filtros encadeados
supabase.from("posts").select("id,title").ilike("title", `%${term}%`); // valor parametrizado pela lib
```
Mongo: valide o tipo (`z.string()`) antes de usar em `find`, ou use `mongo-sanitize`. Ordenação/coluna dinâmica: allowlist (`["created_at","name"].includes(sort)`).

---

## C14 · Validação dos inputs

**Severidade base:** ALTO

**O que é:** todo dado que entra no servidor (body, query, params, headers, FormData, payload de webhook) é validado no servidor com schema — tipo, tamanho, formato, faixa. Validação no front é UX, não segurança. Na saída, conteúdo do usuário renderizado como HTML precisa ser sanitizado (XSS).

**Como detectar:**
- Scanner: presença de lib de schema (zod, yup, joi, valibot, class-validator, ajv, express-validator, pydantic, marshmallow, DRF serializers), rotas sem uso aparente de validação, sinks de XSS (`dangerouslySetInnerHTML`, `v-html`, `{@html}`, `.innerHTML =`, `document.write`, `eval`, `new Function`, `|safe`, `mark_safe`, `rehype-raw`).
- Manual: confira as rotas principais (as mesmas de C06). Para cada sink de XSS, veja se o conteúdo vem do usuário/LLM e se passa por DOMPurify/sanitização.
- Apps com LLM: saída do modelo é input não confiável — não renderize como HTML cru, não execute (`eval`) e não use para montar SQL/shell. Se o agente tem ferramentas com efeito (enviar e-mail, apagar, pagar), exija confirmação humana ou allowlist (prompt injection).

**FALHA:** rotas que escrevem no banco/disparam ações sem validação de schema; `eval`/`new Function` com input; HTML do usuário/LLM renderizado sem sanitização.
**ATENÇÃO:** lib de validação existe mas não cobre todas as rotas; `dangerouslySetInnerHTML` com conteúdo estático/confiável não comprovado.
**OK:** schema em todas as entradas do servidor; HTML dinâmico sanitizado.

**Como corrigir:**
```ts
import { z } from "zod";
const CreatePost = z.object({
  title: z.string().trim().min(3).max(120),
  body: z.string().max(10_000),
  tags: z.array(z.string().max(30)).max(10).default([]),
});
const parsed = CreatePost.safeParse(await req.json());
if (!parsed.success) return Response.json({ error: parsed.error.flatten() }, { status: 400 });
```
```tsx
import DOMPurify from "isomorphic-dompurify";
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />
```
FastAPI: modelos Pydantic nos parâmetros já validam. Markdown de LLM: `react-markdown` sem `rehype-raw` (ou com `rehype-sanitize`).

---

## C15 · Evitar vazamento de conteúdo

**Severidade base:** MÉDIO

**O que é:** o app não pode entregar mais informação do que deveria: stack trace e mensagem de erro interna na resposta, modo debug ligado, source maps públicos (código-fonte completo legível), logs com senha/token/CPF, arquivos sensíveis servidos publicamente (`/.env`, `/.git/`, dumps `.sql`).

**Como detectar:**
- Scanner: `productionBrowserSourceMaps: true`, `sourcemap: true` no Vite, `DEBUG = True`, Flask `debug=True`, `err.stack`/`traceback` na resposta, `res.json(err)`, `console.log` com dado sensível, arquivos sensíveis em `public/`/`static/`, `express.static` servindo a raiz do projeto.
- Com URL: `check_url.py` testa `/.env`, `/.git/config`, source maps dos bundles e cabeçalhos que revelam versão (`X-Powered-By`, `Server`).

**FALHA:** stack trace/erro de banco devolvido ao cliente; debug ligado em produção (Flask debug = CRÍTICO); `.env`/`.git` acessíveis; logs com senhas/tokens.
**ATENÇÃO:** source maps públicos (código exposto facilita ataque, mas não é falha por si); `X-Powered-By`; `console.log` de objetos de usuário inteiros.
**OK:** erros genéricos para o cliente (detalhe só no log interno/Sentry), debug off, nada sensível servido.

**Como corrigir:**
```ts
try { /* ... */ }
catch (err) {
  console.error("[orders.create]", err); // log interno (ou Sentry)
  return Response.json({ error: "Erro interno. Tente novamente." }, { status: 500 });
}
```
- Next: `productionBrowserSourceMaps: false` (padrão) e `poweredByHeader: false`. Vite: `build.sourcemap: false` ou `"hidden"` (gera para Sentry sem publicar).
- Django: `DEBUG = os.getenv("DEBUG") == "1"`; Flask: nunca `debug=True` fora do local.
- Logs: redaction de campos (`password`, `token`, `authorization`, `cpf`) — ex.: `pino({ redact: ["req.headers.authorization", "*.password"] })`.
- Tire `.env`, dumps e backups de `public/`.

---

## C16 · Restringir uploads

**Severidade base:** ALTO

**O que é:** upload é porta de entrada para malware, XSS (SVG/HTML servido no seu domínio), path traversal e conta de storage estourada. Controles: allowlist de tipo validada no servidor (pelos bytes do arquivo, não pela extensão/`Content-Type` do cliente), limite de tamanho, nome gerado pelo servidor, bucket privado com URL assinada, sem servir HTML/SVG inline.

**Como detectar:**
- Scanner: multer/formidable/busboy/`formData().get('file')`/`UploadFile`/`request.FILES`/`storage.from().upload`/S3 presigned/uploadthing; presença de limite de tamanho e checagem de tipo; `originalname`/`file.name` usado no caminho; buckets `public: true`; `image/svg+xml` permitido.
- Manual: verifique policies do Storage (Supabase: `storage.objects`) — quem pode subir/ler em qual pasta.

**FALHA:** upload sem limite de tamanho ou sem validação de tipo no servidor; nome original usado no caminho; HTML/SVG aceito e servido do mesmo domínio; bucket público com arquivos privados de usuários.
**ATENÇÃO:** validação só por extensão/`Content-Type`; presigned URL sem `content-length-range`; bucket público só com arquivos realmente públicos (avatar) — ok se intencional.
**OK:** allowlist + magic bytes + limite + nome aleatório + storage privado/assinado.
**N/A:** app sem upload.

**Como corrigir:**
```ts
import { fileTypeFromBuffer } from "file-type";
const MAX = 5 * 1024 * 1024;
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp", "application/pdf"]);

const file = (await req.formData()).get("file") as File;
if (!file || file.size > MAX) return Response.json({ error: "arquivo inválido" }, { status: 400 });
const buf = Buffer.from(await file.arrayBuffer());
const type = await fileTypeFromBuffer(buf);
if (!type || !ALLOWED.has(type.mime)) return Response.json({ error: "tipo não permitido" }, { status: 415 });
const key = `${user.id}/${crypto.randomUUID()}.${type.ext}`; // nunca file.name
await supabaseAdmin.storage.from("uploads").upload(key, buf, { contentType: type.mime });
```
Multer: `multer({ limits: { fileSize: 5e6, files: 1 }, fileFilter })`. Supabase Storage: bucket privado + policy por pasta (`(storage.foldername(name))[1] = auth.uid()::text`) + `createSignedUrl` para leitura; configure `file_size_limit` e `allowed_mime_types` no bucket. Sirva downloads com `Content-Disposition: attachment` e, se possível, de um domínio separado.

---

## C17 · Limitar respostas de API

**Severidade base:** MÉDIO

**O que é:** a API devolve só o que a tela precisa, em páginas. Sem isso: `password_hash`, e-mails de outros usuários, campos internos e listas de 100 mil registros saem numa resposta (vazamento + DoS + conta de banda).

**Como detectar:**
- Scanner: `findMany()` sem `take`, `.select('*')` sem `.range()`/`.limit()`, `SELECT *`, `res.json(user)`/objeto inteiro de usuário, `limit` vindo da query sem teto, GraphQL sem limite de profundidade/complexidade e com introspection em produção.
- Manual: abra as respostas das rotas principais e veja os campos.

**FALHA:** resposta inclui campos sensíveis (hash de senha, tokens, dados de outros usuários); listagem sem paginação em tabela que cresce com uso.
**ATENÇÃO:** `select *` devolvendo campos internos não sensíveis; paginação com `limit` sem teto.
**OK:** seleção explícita de campos/DTO, paginação com máximo (ex.: 50/100).

**Como corrigir:**
```ts
const limit = Math.min(Number(searchParams.get("limit")) || 20, 100);
const items = await prisma.post.findMany({
  where: { ownerId: user.id },
  select: { id: true, title: true, createdAt: true }, // nunca o objeto inteiro
  take: limit, skip: offset, orderBy: { createdAt: "desc" },
});
```
```ts
supabase.from("posts").select("id,title,created_at").range(from, from + limit - 1);
```
GraphQL: `graphql-depth-limit`/GraphQL Armor, desabilitar introspection em produção.

---

## C18 · Security headers

**Severidade base:** MÉDIO

**O que é:** cabeçalhos que mandam o navegador se defender: `Content-Security-Policy` (limita de onde vêm scripts — principal mitigação de XSS), `Strict-Transport-Security` (HSTS), `X-Frame-Options: DENY` ou `frame-ancestors 'none'` (clickjacking), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (câmera, microfone, geolocalização). Remover `X-Powered-By`.

**Como detectar:**
- Scanner: `headers()` no `next.config.*`, `helmet`, `vercel.json`/`netlify.toml`/`_headers`, nginx `add_header`, Django `SecurityMiddleware`/`django-csp`, `flask-talisman`.
- Com URL: `check_url.py` mostra os cabeçalhos reais (a verdade; plataformas adicionam alguns sozinhas — a Vercel, por exemplo, já manda HSTS).

**FALHA:** nenhum dos cabeçalhos principais configurado (sem CSP **e** sem anti-clickjacking **e** sem nosniff).
**ATENÇÃO:** parte configurada; CSP com `'unsafe-inline'`/`'unsafe-eval'` em `script-src` (melhor que nada, mas fraco); sem URL para confirmar.
**OK:** os seis presentes (CSP pode começar em `Content-Security-Policy-Report-Only` e endurecer depois).

**Como corrigir (Next.js):**
```js
// next.config.js
const securityHeaders = [
  { key: "Content-Security-Policy", value: [
      "default-src 'self'",
      "script-src 'self'",              // adicione domínios necessários (analytics, Stripe, Turnstile)
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "connect-src 'self' https://*.supabase.co",
      "frame-ancestors 'none'",
      "base-uri 'self'", "form-action 'self'",
    ].join("; ") },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
module.exports = {
  poweredByHeader: false,
  async headers() { return [{ source: "/(.*)", headers: securityHeaders }]; },
};
```
Express: `app.use(helmet())` + `app.disable("x-powered-by")`. Vercel estático/Vite: bloco `headers` no `vercel.json`. Netlify: arquivo `_headers`. Django: `SECURE_HSTS_SECONDS`, `X_FRAME_OPTIONS = "DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF = True`, `django-csp`. Teste a CSP no navegador antes de publicar (ela quebra scripts de terceiros não listados) — comece com Report-Only se tiver dúvida.

---

## C19 · Forçar HTTPS

**Severidade base:** ALTO

**O que é:** todo tráfego em HTTPS: HTTP redireciona (301/308) para HTTPS, HSTS ativo, nenhuma chamada/recurso `http://` (mixed content), conexões do servidor para banco/APIs com TLS e verificação de certificado ligada.

**Como detectar:**
- Scanner: URLs `http://` hardcoded (fora localhost), `rejectUnauthorized: false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, Python `verify=False`, `sslmode=disable`, `ssl: false`, Django `SECURE_SSL_REDIRECT`, plataforma de deploy.
- Com URL: `check_url.py` testa o redirect de `http://` e o HSTS.
- Vercel, Netlify, Cloudflare Pages, Render, Railway e Fly forçam HTTPS por padrão — VPS/nginx próprio, não.

**FALHA:** site acessível em HTTP sem redirect; verificação TLS desligada em produção; chamadas a APIs/assets via `http://`.
**ATENÇÃO:** redirect ok mas sem HSTS; não dá pra confirmar sem URL e o deploy é em VPS próprio.
**OK:** redirect + HSTS + nada `http://` + TLS verificado.

**Como corrigir:**
- nginx:
```nginx
server { listen 80; server_name meuapp.com.br; return 301 https://$host$request_uri; }
# no bloco 443:
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```
- Express atrás de proxy: `app.set("trust proxy", 1); app.use((req, res, next) => req.secure ? next() : res.redirect(301, "https://" + req.headers.host + req.url));`
- Remova `rejectUnauthorized: false`/`verify=False`; se o banco usa certificado próprio, passe o CA (`ssl: { ca: fs.readFileSync("ca.pem") }`).
- Troque `http://` por `https://` nas URLs; Cloudflare: "Always Use HTTPS" + SSL "Full (strict)".

---

## C20 · Scan de dependências

**Severidade base:** ALTO

**O que é:** dependências com vulnerabilidade conhecida são o caminho mais fácil de ataque. Precisa de lockfile versionado, auditoria sem vulnerabilidades altas/críticas em produção e atualização automática (Dependabot/Renovate).

**Como detectar:**
- Scanner: lockfile, Dependabot/Renovate, roda `npm audit --omit=dev`/`pnpm audit --prod`/`yarn audit --groups dependencies`/`bun audit --prod`/`pip-audit`/`osv-scanner` quando possível (precisa de rede) e separa três grupos:
  - `vulnerabilidades_altas` (confiança alta): pacote de produção que o código do app importa, ou que não deu para saber;
  - `vulnerabilidades_so_no_build` (média): pacote em `dependencies` que só a config do build (`vite.config`, `postcss.config`…), os scripts e os testes usam, ou ferramenta de build (vite, esbuild, tailwind, eslint…). Não vai para o navegador nem para o servidor. Acontece quando o pacote de build foi instalado sem `-D`;
  - `vulnerabilidades_so_dev` (baixa): só em `devDependencies` (roda uma segunda auditoria, completa, para comparar).
  - A decisão de cada pacote fica em `C20.sinais.auditoria.<ferramenta>.decisao`. Se você rodar a auditoria à mão, use as mesmas flags de produção e separe o que é build e dev antes de dar FALHA.
- Também checa versões do Next.js afetadas por:
  - **CVE-2025-29927** (bypass de middleware): corrigido em 12.3.5, 13.5.9, 14.2.25, 15.2.3.
  - **CVE-2025-66478 / CVE-2025-55182 "React2Shell"** (RCE, CVSS 10, App Router): Next 15.x/16.x — corrigido em 15.0.5, 15.1.9, 15.2.6, 15.3.6, 15.4.8, 15.5.7, 16.0.7. Se ficou exposto sem patch, a recomendação oficial é rotacionar os segredos do app.
  - **Boletins de 2026** (julho, agosto, 22/set, 30/set e 14/out): RCEs críticas (função `use cache` devolvendo typed arrays, otimização de imagem com SVG/AVIF via sharp, servidor Windows), SSRF na otimização de imagem e cache poisoning. **Mínimo seguro em 27/10/2026: 15.5.28 (Maintenance LTS) e 16.4.1 (Active LTS).** As linhas 13.x e 14.x não recebem mais correção. Fontes: [nextjs.org/blog/nextjs-security-update-october-14-2026](https://nextjs.org/blog/nextjs-security-update-october-14-2026) e [september-2026-security-release](https://nextjs.org/blog/september-2026-security-release). O scanner acusa como `next_boletins_2026` ou `next_linha_sem_suporte`; boletins mais novos aparecem no `npm audit`.
- Outras linguagens: `composer audit` (PHP), `pip-audit` (Python), `bundle-audit` (Ruby), `govulncheck ./...` (Go), `dotnet list package --vulnerable` (.NET), `mvn org.owasp:dependency-check-maven:check` ou `./gradlew dependencyCheckAnalyze` (Java), e `osv-scanner scan source -r .` para todas de uma vez. O scanner roda as que estiverem instaladas.
- Se a auditoria não rodou (sem rede/sem npm), deixe o comando como ação manual e marque ATENÇÃO.

**FALHA:** vulnerabilidade crítica/alta em dependência de produção que o app usa; Next.js numa das faixas acima; sem lockfile.
**ATENÇÃO:** alta/crítica só em pacote de build ou de dev (o servidor de desenvolvimento e o CI ficam expostos, o app publicado não); só moderadas; auditoria não executada; sem Dependabot/Renovate. Projeto Yarn 2+ (berry): `yarn npm audit --environment production`.
**OK:** auditoria limpa (ou só baixas/dev) + lockfile + atualização automática.

**Como corrigir:**
```bash
npm audit --omit=dev            # ver
npm audit fix                   # corrige o que não quebra semver
npm install next@latest         # framework: suba para a última da sua linha
npx fix-react2shell-next        # ferramenta oficial da Vercel para o React2Shell
pip-audit -r requirements.txt   # Python
```
`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
```
`npm audit fix --force` pode quebrar (major) — rode build/testes depois. Remova dependências não usadas (`npx depcheck`).

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
