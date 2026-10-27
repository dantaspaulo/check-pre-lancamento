<!-- check-pre-lancamento v2.0.0 · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · CPL-PSD-2026 -->
# Correções · AgendaFácil (exemplo fictício)

> Plano de correção gerado pelo check-pre-lancamento em 2026-10-27 (nota de segurança 49/100, prontidão 60/100, veredito: NÃO LANCE AINDA).
> Para executar, abra o seu agente (Claude Code, Codex, Cursor…) na raiz do projeto e diga: **"Leia check-report/CORRECOES.md e aplique as correções na ordem, uma por vez."**

## Regras de execução (para o agente)

1. Uma task por vez, na ordem abaixo. Antes de mexer, leia os arquivos citados e confirme que o problema ainda existe — se já foi corrigido, marque e siga.
2. Não quebre funcionalidade: depois de cada task rode o que existir de build, lint, typecheck e testes. Se quebrar, conserte antes de seguir.
3. Se o projeto usa git, faça um commit por task: `fix(security): [Cxx] <resumo>` (prontidão: `chore(launch): [Pxx] <resumo>`).
4. Nunca escreva valor de segredo em código, commit, log ou chat. Use variáveis de ambiente e só referencie pelo nome.
5. Itens marcados **Ação manual** não são seus (rotacionar chave, painel do Supabase/Firebase, DNS, Cloudflare): liste-os para o humano no final.
6. Não reescreva histórico do git (filter-repo/BFG), não faça force push e não apague dados sem confirmação explícita do humano.
7. Se a correção depender de decisão de produto (essa rota deveria ser pública? esse campo pode ser editado pelo usuário?), pare e pergunte.
8. Prefira a menor mudança que resolve. Nada de refatoração não pedida.
9. Ao terminar, rode o scanner de novo e atualize o relatório (veja "Validação final").

## Antes de começar: decisões do humano

Pergunte ao humano e espere a resposta antes das tasks afetadas. Não decida por ele.

- [ ] A função lembrete é chamada só pelo cron, ou também pelo app?

## Ordem de execução

| Task | Check | Severidade | Status | Depende de | O quê |
|---|---|---|---|---|---|
| 1 | C01 Esconder API Keys | CRÍTICO | ❌ FALHA | — | Chave da OpenAI no bundle do navegador via VITE_OPENAI_API_KEY. |
| 2 | C04 Ativar RLS | CRÍTICO | ❌ FALHA | — | Tabela agendamentos sem RLS: 1.204 linhas visíveis para qualquer visitante. |
| 3 | C11 Rate limit | ALTO | ❌ FALHA | 1 | Função de resumo com IA sem limite por usuário. |
| 4 | C06 Auth server-side | ALTO | ⚠️ ATENÇÃO | — | Edge Function lembrete com verify_jwt = false e sem checagem de usuário no código. |
| 5 | C18 Security headers | MÉDIO | ❌ FALHA | — | Site publicado sem CSP, sem X-Frame-Options e sem nosniff (check_url.py). |
| 6 | P06 E-mail e domínio | ALTO | ❌ FALHA | — | Confirmação de cadastro pelo SMTP padrão do Supabase; domínio sem DMARC. |
| 7 | P02 Erros e logs monitorados | ALTO | ⚠️ ATENÇÃO | — | Nenhum monitoramento de erro: erro em produção passa sem ninguém ver. |
| 8 | P03 Backup e recuperação | ALTO | ⚠️ ATENÇÃO | — | Projeto no plano gratuito do Supabase: sem backup diário conferido. |
| 9 | P10 Custos e limites de gasto | ALTO | ⚠️ ATENÇÃO | 3 | Sem limite de gasto configurado na OpenAI. |
| 10 | P08 SEO e compartilhamento | MÉDIO | ❌ FALHA | — | index.html com o título e a imagem de compartilhamento do template ("Lovable App"). |

## Task 1 · [C01] Esconder API Keys — CRÍTICO

**Problema:** Chave da OpenAI no bundle do navegador via VITE_OPENAI_API_KEY.

**Arquivos:** `src/lib/ai.ts`, `supabase/functions/resumo/index.ts`

**Evidências:**
- src/lib/ai.ts:4 — new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true })
- https://agendafacil.com.br/assets/index-8f2c.js → sk-pro…****

**O que fazer:**

Em src/lib/ai.ts a OpenAI é instanciada no navegador com VITE_OPENAI_API_KEY e dangerouslyAllowBrowser. Crie supabase/functions/resumo/index.ts que valida o JWT do usuário (supabase.auth.getUser com o header Authorization), valida o body com zod (texto até 4.000 caracteres) e chama a OpenAI com Deno.env.get('OPENAI_API_KEY') e max_tokens 600. Troque a chamada em src/lib/ai.ts por supabase.functions.invoke('resumo'). Remova VITE_OPENAI_API_KEY do .env e do .env.example. Verifique: grep -rn "VITE_OPENAI\|dangerouslyAllowBrowser" src vazio e npm run build passando. Não tente rotacionar a chave: é ação manual.

**Critério de aceite:**
- [ ] Nenhuma referência a VITE_OPENAI_API_KEY em src/
- [ ] A função recusa chamada sem login (401)

**Ação manual (humano):** Rotacionar a chave na OpenAI (platform.openai.com → API keys) e cadastrar a nova com `supabase secrets set OPENAI_API_KEY=...`.

## Task 2 · [C04] Ativar RLS — CRÍTICO

**Problema:** Tabela agendamentos sem RLS: 1.204 linhas visíveis para qualquer visitante.

**Arquivos:** `supabase/migrations/`

**Evidências:**
- supabase/migrations/20261003_init.sql:12 — create table public.agendamentos (sem enable row level security)
- check_url.py --sondar-dados → agendamentos: 1.204 linhas visíveis sem login

**O que fazer:**

Crie a migration supabase/migrations/<timestamp>_rls_agendamentos.sql com: enable row level security em public.agendamentos; policies de select/insert/update/delete para authenticated restritas a (select auth.uid()) = clinica_id (with check igual em insert/update). Não aplique no banco: só gere o arquivo. Depois liste as telas que leem agendamentos e confirme que usam o cliente autenticado.

**Critério de aceite:**
- [ ] agendamentos com RLS ligado
- [ ] Visitante sem login recebe 0 linhas

**Ação manual (humano):** Aplicar a migration (supabase db push) e rodar de novo o check com --sondar-dados para ver 0 linhas.

## Task 3 · [C11] Rate limit — ALTO

**Problema:** Função de resumo com IA sem limite por usuário.

**Depende de:** Task 1 (C01) — se ainda não foi feita, faça antes.

**O que fazer:**

Na Edge Function resumo (criada na task do C01), antes de chamar a OpenAI, conte as chamadas do usuário nas últimas 24 h numa tabela public.uso_ia (user_id, criado_em) com RLS; acima de 20, responda 429. Registre cada chamada. Verifique: a 21ª chamada do mesmo usuário recebe 429.

## Task 4 · [C06] Auth server-side — ALTO

**Problema:** Edge Function lembrete com verify_jwt = false e sem checagem de usuário no código.

**Arquivos:** `supabase/functions/lembrete/index.ts`, `supabase/config.toml`

**Evidências:**
- supabase/config.toml:8 — [functions.lembrete] verify_jwt = false

**O que fazer:**

Em supabase/functions/lembrete/index.ts, exija o header x-cron-secret igual a Deno.env.get('CRON_SECRET') usando comparação em tempo constante e responda 401 caso contrário. Mantenha verify_jwt = false só se o cron não mandar JWT. Verifique com curl sem header: deve dar 401.

**Ação manual (humano):** Cadastrar CRON_SECRET com supabase secrets set e no agendador.

## Task 5 · [C18] Security headers — MÉDIO

**Problema:** Site publicado sem CSP, sem X-Frame-Options e sem nosniff (check_url.py).

**O que fazer:**

Crie ou edite netlify.toml com [[headers]] for = "/*" contendo Content-Security-Policy (default-src 'self'; connect-src 'self' https://*.supabase.co; frame-ancestors 'none'), X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin e Permissions-Policy camera=(), microphone=(), geolocation=(). Teste no navegador que o login continua funcionando.

## Task 6 · [P06] E-mail e domínio — ALTO

**Problema:** Confirmação de cadastro pelo SMTP padrão do Supabase; domínio sem DMARC.

**Evidências:**
- supabase/config.toml sem [auth.email.smtp]
- check_url.py → agendafacil.com.br sem DMARC

**O que fazer:**

Liste ao humano os passos: criar conta na Resend, verificar o domínio, publicar os registros DNS mostrados e _dmarc com p=quarantine, e preencher Authentication → SMTP Settings no Supabase. Depois traduza os templates de e-mail do Supabase Auth para português.

**Ação manual (humano):** DNS no Registro.br e SMTP no painel do Supabase.

## Task 7 · [P02] Erros e logs monitorados — ALTO

**Problema:** Nenhum monitoramento de erro: erro em produção passa sem ninguém ver.

**O que fazer:**

Instale @sentry/react, inicialize em src/main.tsx com o DSN de VITE_SENTRY_DSN, envolva o App num Sentry.ErrorBoundary com uma tela de erro amigável e configure beforeSend para remover e-mail e telefone. Verifique: npm run build passando.

## Task 8 · [P03] Backup e recuperação — ALTO

**Problema:** Projeto no plano gratuito do Supabase: sem backup diário conferido.

**O que fazer:**

Crie .github/workflows/backup.yml que roda diariamente supabase db dump e envia o arquivo para um bucket (credenciais em secrets do GitHub). Não coloque nenhuma credencial no arquivo.

**Ação manual (humano):** Conferir em Supabase → Database → Backups e testar uma restauração.

## Task 9 · [P10] Custos e limites de gasto — ALTO

**Problema:** Sem limite de gasto configurado na OpenAI.

**Depende de:** Task 3 (C11) — se ainda não foi feita, faça antes.

**O que fazer:**

Nada a mudar no código. Liste ao humano: OpenAI → Settings → Limits, orçamento mensal e alerta em 50% e 80%.

**Ação manual (humano):** Configurar o orçamento na OpenAI.

## Task 10 · [P08] SEO e compartilhamento — MÉDIO

**Problema:** index.html com o título e a imagem de compartilhamento do template ("Lovable App").

**Evidências:**
- index.html:5 — <title>Lovable App</title>
- index.html:8 — og:image de lovable.dev

**O que fazer:**

Em index.html troque o title para "AgendaFácil · agenda online para clínicas", a meta description, og:title, og:description e og:image (public/og.png, 1200×630) e defina <html lang="pt-BR">. Verifique com npm run build.

## Checklist manual (repasse ao humano no final)

- [ ] **[C01]** Rotacionar a chave na OpenAI (platform.openai.com → API keys) e cadastrar a nova com `supabase secrets set OPENAI_API_KEY=...`.
- [ ] **[C04]** Aplicar a migration (supabase db push) e rodar de novo o check com --sondar-dados para ver 0 linhas.
- [ ] **[C06]** Cadastrar CRON_SECRET com supabase secrets set e no agendador.
- [ ] **[P06]** DNS no Registro.br e SMTP no painel do Supabase.
- [ ] **[P03]** Conferir em Supabase → Database → Backups e testar uma restauração.
- [ ] **[P10]** Configurar o orçamento na OpenAI.

## Validação final

- [ ] Rodar de novo o scanner: `python3 /Users/paulosdantas/Code/check-pre-lancamento/skills/check-pre-lancamento/scripts/scan.py . --out check-report/scan.json` e confirmar que os achados de confiança alta sumiram.
- [ ] Build e testes passando.
- [ ] Atualizar `findings.json` com os novos status e regenerar o relatório (`render_report.py`).
- [ ] Entregar ao humano: o que foi corrigido (por task), o que ficou pendente e o checklist manual.

---
<sub>Plano gerado pela skill check-pre-lancamento v2.0.0 · por Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento</sub>
