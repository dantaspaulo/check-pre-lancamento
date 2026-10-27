<!-- check-pre-lancamento v2.1.0 · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · CPL-PSD-2026 -->
# Check pré-lançamento · AgendaFácil (exemplo fictício)

**Data:** 2026-10-27  
**Stack:** Vite + React (Lovable) + Supabase + Netlify  
**Escopo:** repo completo (branch main) + https://agendafacil.com.br, com --sondar-dados autorizado pelo dono  

## 🔴 Veredito: NÃO LANCE AINDA

**Nota de segurança: 49/100** · **Nota de prontidão: 60/100**  
Há falha crítica aberta. Corrija os itens críticos antes de colocar no ar (ou tire do ar se já está publicado).

| ❌ Falhas | ⚠️ Atenção | ✅ OK | ➖ N/A |
|---|---|---|---|
| 4 | 1 | 13 | 2 |

Falhas por severidade: 2 críticos · 1 alto · 1 médio

> O app está bem encaminhado, mas tem duas falhas que impedem o lançamento: a chave da OpenAI está no site e a tabela de agendamentos está aberta para qualquer visitante. As duas se corrigem em menos de uma hora. Na prontidão, o e-mail de confirmação não vai chegar sem SMTP próprio.

## Placar das 20 checagens

| # | Checagem | Status | Severidade | O que encontrei |
|---|---|---|---|---|
| 01 | Esconder API Keys | ❌ FALHA | 🔴 CRÍTICO | Chave da OpenAI no bundle do navegador via VITE_OPENAI_API_KEY. |
| 02 | Limpar secrets do Git | ✅ OK | — | Nenhum arquivo sensível versionado; .gitignore cobre .env*; histórico limpo (gitleaks sem achados). |
| 03 | Usar apenas Public Key no DB | ✅ OK | — | O front usa só a chave pública do Supabase; nenhum service role no código do cliente. |
| 04 | Ativar RLS | ❌ FALHA | 🔴 CRÍTICO | Tabela agendamentos sem RLS: 1.204 linhas visíveis para qualquer visitante. |
| 05 | Criptografia de dados | ✅ OK | — | Sem dado de cartão; telefone guardado com RLS (após a correção do C04). |
| 06 | Auth server-side | ⚠️ ATENÇÃO | 🟠 ALTO | Edge Function lembrete com verify_jwt = false e sem checagem de usuário no código. |
| 07 | Restringir acessos | ✅ OK | — | Todas as leituras usam o cliente autenticado; RLS (após C04) filtra por clínica. |
| 08 | Bloquear Mass Assignment | ✅ OK | — | Updates do front só mexem em colunas liberadas (grant update por coluna). |
| 09 | Proteger cookies | ✅ OK | — | Sessão gerenciada pelo supabase-js em SPA (padrão aceito); sem token próprio. |
| 10 | Hash nas senhas | ✅ OK | — | Senhas gerenciadas pelo Supabase Auth. |
| 11 | Rate limit | ❌ FALHA | 🟠 ALTO | Função de resumo com IA sem limite por usuário. |
| 12 | Bot protection | ✅ OK | — | Captcha do Supabase Auth (Turnstile) ligado no cadastro. |
| 13 | Queries parametrizadas | ➖ N/A | — | Sem SQL próprio: todas as consultas passam pelo supabase-js. |
| 14 | Validação dos inputs | ✅ OK | — | Formulários validados com zod no front e checagem no banco; sem HTML dinâmico. |
| 15 | Evitar vazamento de conteúdo | ✅ OK | — | Sem source maps públicos; erros genéricos na tela. |
| 16 | Restringir uploads | ➖ N/A | — | O app não tem upload de arquivos. |
| 17 | Limitar respostas de API | ✅ OK | — | Listagens com .range() e colunas explícitas. |
| 18 | Security headers | ❌ FALHA | 🟡 MÉDIO | Site publicado sem CSP, sem X-Frame-Options e sem nosniff (check_url.py). |
| 19 | Forçar HTTPS | ✅ OK | — | HTTP redireciona para HTTPS com 301; HSTS ativo pela Netlify. |
| 20 | Scan de dependências | ✅ OK | — | npm audit sem vulnerabilidade alta ou crítica; lockfile versionado; Dependabot ativo. |

## Prontidão para o lançamento (10 itens)

Não entra na nota de segurança. Mede o que costuma derrubar um lançamento mesmo com o app seguro: e-mail que não chega, site fora do Google, conta de nuvem estourada, erro sem ninguém ver.

| # | Item | Status | Severidade | O que encontrei |
|---|---|---|---|---|
| P01 | Configuração de produção | ✅ OK | — | Variáveis do código documentadas no .env.example; sem localhost no cliente. |
| P02 | Erros e logs monitorados | ⚠️ ATENÇÃO | 🟠 ALTO | Nenhum monitoramento de erro: erro em produção passa sem ninguém ver. |
| P03 | Backup e recuperação | ⚠️ ATENÇÃO | 🟠 ALTO | Projeto no plano gratuito do Supabase: sem backup diário conferido. |
| P04 | Deploy, migrations e rollback | ✅ OK | — | Migrations versionadas em supabase/migrations; build no CI a cada push. |
| P05 | Uptime e alertas | ➖ N/A | — | Hospedagem estática na Netlify com certificado automático; monitor de uptime fica como melhoria. |
| P06 | E-mail e domínio | ❌ FALHA | 🟠 ALTO | Confirmação de cadastro pelo SMTP padrão do Supabase; domínio sem DMARC. |
| P07 | LGPD, privacidade e termos | ✅ OK | — | Política de privacidade e termos no rodapé e no cadastro; exclusão de conta em Configurações. |
| P08 | SEO e compartilhamento | ❌ FALHA | 🟡 MÉDIO | index.html com o título e a imagem de compartilhamento do template ("Lovable App"). |
| P09 | Performance e experiência | ✅ OK | — | LCP de 1,9 s no PageSpeed (celular); imagens em WebP. |
| P10 | Custos e limites de gasto | ⚠️ ATENÇÃO | 🟠 ALTO | Sem limite de gasto configurado na OpenAI. |

## Decisões que só você pode tomar

Responda antes de aplicar as correções — várias delas dependem disso.

- [ ] A função lembrete é chamada só pelo cron, ou também pelo app?

## O que corrigir (por prioridade)

### 1. 🔴 [C01] Esconder API Keys — CRÍTICO · ❌ FALHA

**O que encontrei:** Chave da OpenAI no bundle do navegador via VITE_OPENAI_API_KEY.

**Evidências:**
- src/lib/ai.ts:4 — new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true })
- https://agendafacil.com.br/assets/index-8f2c.js → sk-pro…****

**Risco:** Qualquer visitante abre o DevTools, copia a chave e usa a sua conta da OpenAI à vontade, até estourar o limite do cartão.

**Como corrigir:**

Mover a chamada para uma Edge Function do Supabase que lê `OPENAI_API_KEY` com `Deno.env.get`, exige usuário logado e tem limite por usuário. O front chama `supabase.functions.invoke('resumo')`.

**Você precisa fazer (fora do código):** Rotacionar a chave na OpenAI (platform.openai.com → API keys) e cadastrar a nova com `supabase secrets set OPENAI_API_KEY=...`.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Em src/lib/ai.ts a OpenAI é instanciada no navegador com VITE_OPENAI_API_KEY e dangerouslyAllowBrowser. Crie supabase/functions/resumo/index.ts que valida o JWT do usuário (supabase.auth.getUser com o header Authorization), valida o body com zod (texto até 4.000 caracteres) e chama a OpenAI com Deno.env.get('OPENAI_API_KEY') e max_tokens 600. Troque a chamada em src/lib/ai.ts por supabase.functions.invoke('resumo'). Remova VITE_OPENAI_API_KEY do .env e do .env.example. Verifique: grep -rn "VITE_OPENAI\|dangerouslyAllowBrowser" src vazio e npm run build passando. Não tente rotacionar a chave: é ação manual.
```

### 2. 🔴 [C04] Ativar RLS — CRÍTICO · ❌ FALHA

**O que encontrei:** Tabela agendamentos sem RLS: 1.204 linhas visíveis para qualquer visitante.

**Evidências:**
- supabase/migrations/20261003_init.sql:12 — create table public.agendamentos (sem enable row level security)
- check_url.py --sondar-dados → agendamentos: 1.204 linhas visíveis sem login

**Risco:** Qualquer pessoa, com a chave pública que está no site, lê nome, telefone e horário de todos os pacientes e pode apagar a agenda inteira.

**Como corrigir:**

```sql
alter table public.agendamentos enable row level security;
create policy ag_select_own on public.agendamentos for select to authenticated using ((select auth.uid()) = clinica_id);
```

**Você precisa fazer (fora do código):** Aplicar a migration (supabase db push) e rodar de novo o check com --sondar-dados para ver 0 linhas.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Crie a migration supabase/migrations/<timestamp>_rls_agendamentos.sql com: enable row level security em public.agendamentos; policies de select/insert/update/delete para authenticated restritas a (select auth.uid()) = clinica_id (with check igual em insert/update). Não aplique no banco: só gere o arquivo. Depois liste as telas que leem agendamentos e confirme que usam o cliente autenticado.
```

### 3. 🟠 [C11] Rate limit — ALTO · ❌ FALHA

**O que encontrei:** Função de resumo com IA sem limite por usuário.

**Depende de:** item 1 (C01)

**Risco:** Um script chama a função milhares de vezes e a conta da OpenAI explode em uma noite.

**Como corrigir:**

Limite de 20 resumos por usuário por dia, guardado numa tabela de uso, e max_tokens na chamada.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Na Edge Function resumo (criada na task do C01), antes de chamar a OpenAI, conte as chamadas do usuário nas últimas 24 h numa tabela public.uso_ia (user_id, criado_em) com RLS; acima de 20, responda 429. Registre cada chamada. Verifique: a 21ª chamada do mesmo usuário recebe 429.
```

### 4. 🟠 [C06] Auth server-side — ALTO · ⚠️ ATENÇÃO

**O que encontrei:** Edge Function lembrete com verify_jwt = false e sem checagem de usuário no código.

**Evidências:**
- supabase/config.toml:8 — [functions.lembrete] verify_jwt = false

**Risco:** Qualquer um chama a função e dispara lembretes por WhatsApp para a lista inteira, gastando os seus créditos.

**Como corrigir:**

Se a função é chamada só pelo cron, exigir um segredo no header (comparação em tempo constante). Se é chamada pelo app, voltar verify_jwt = true.

**Você precisa fazer (fora do código):** Cadastrar CRON_SECRET com supabase secrets set e no agendador.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Em supabase/functions/lembrete/index.ts, exija o header x-cron-secret igual a Deno.env.get('CRON_SECRET') usando comparação em tempo constante e responda 401 caso contrário. Mantenha verify_jwt = false só se o cron não mandar JWT. Verifique com curl sem header: deve dar 401.
```

### 5. 🟡 [C18] Security headers — MÉDIO · ❌ FALHA

**O que encontrei:** Site publicado sem CSP, sem X-Frame-Options e sem nosniff (check_url.py).

**Risco:** Sem CSP, um XSS vira roubo de sessão; sem anti-clickjacking, o site pode ser embutido num iframe malicioso.

**Como corrigir:**

Adicionar headers no netlify.toml (bloco [[headers]]) ou no provedor de hospedagem.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Crie ou edite netlify.toml com [[headers]] for = "/*" contendo Content-Security-Policy (default-src 'self'; connect-src 'self' https://*.supabase.co; frame-ancestors 'none'), X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin e Permissions-Policy camera=(), microphone=(), geolocation=(). Teste no navegador que o login continua funcionando.
```

## Prontidão: o que ajustar antes de divulgar

### 6. 🟠 [P06] E-mail e domínio — ALTO · ❌ FALHA

**O que encontrei:** Confirmação de cadastro pelo SMTP padrão do Supabase; domínio sem DMARC.

**Evidências:**
- supabase/config.toml sem [auth.email.smtp]
- check_url.py → agendafacil.com.br sem DMARC

**Risco:** No lançamento, o e-mail de confirmação não chega (o SMTP padrão é só para teste) e as pessoas não conseguem entrar.

**Como corrigir:**

Configurar a Resend como SMTP no Supabase e publicar SPF, DKIM e DMARC.

**Você precisa fazer (fora do código):** DNS no Registro.br e SMTP no painel do Supabase.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Liste ao humano os passos: criar conta na Resend, verificar o domínio, publicar os registros DNS mostrados e _dmarc com p=quarantine, e preencher Authentication → SMTP Settings no Supabase. Depois traduza os templates de e-mail do Supabase Auth para português.
```

### 7. 🟠 [P02] Erros e logs monitorados — ALTO · ⚠️ ATENÇÃO

**O que encontrei:** Nenhum monitoramento de erro: erro em produção passa sem ninguém ver.

**Risco:** No dia do lançamento, um erro na tela de agendamento derruba as marcações e você só fica sabendo pelo WhatsApp dos clientes.

**Como corrigir:**

Instalar o Sentry no front (@sentry/react) com alerta por e-mail.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Instale @sentry/react, inicialize em src/main.tsx com o DSN de VITE_SENTRY_DSN, envolva o App num Sentry.ErrorBoundary com uma tela de erro amigável e configure beforeSend para remover e-mail e telefone. Verifique: npm run build passando.
```

### 8. 🟠 [P03] Backup e recuperação — ALTO · ⚠️ ATENÇÃO

**O que encontrei:** Projeto no plano gratuito do Supabase: sem backup diário conferido.

**Risco:** Um delete errado apaga a agenda de todas as clínicas sem caminho de volta.

**Como corrigir:**

Subir para um plano com backup diário ou agendar `supabase db dump` para um bucket externo.

**Você precisa fazer (fora do código):** Conferir em Supabase → Database → Backups e testar uma restauração.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Crie .github/workflows/backup.yml que roda diariamente supabase db dump e envia o arquivo para um bucket (credenciais em secrets do GitHub). Não coloque nenhuma credencial no arquivo.
```

### 9. 🟠 [P10] Custos e limites de gasto — ALTO · ⚠️ ATENÇÃO

**O que encontrei:** Sem limite de gasto configurado na OpenAI.

**Depende de:** item 3 (C11)

**Risco:** Mesmo com o limite por usuário, um pico no lançamento pode gerar uma fatura alta.

**Como corrigir:**

Definir um orçamento mensal e um alerta na OpenAI.

**Você precisa fazer (fora do código):** Configurar o orçamento na OpenAI.

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Nada a mudar no código. Liste ao humano: OpenAI → Settings → Limits, orçamento mensal e alerta em 50% e 80%.
```

### 10. 🟡 [P08] SEO e compartilhamento — MÉDIO · ❌ FALHA

**O que encontrei:** index.html com o título e a imagem de compartilhamento do template ("Lovable App").

**Evidências:**
- index.html:5 — <title>Lovable App</title>
- index.html:8 — og:image de lovable.dev

**Risco:** No Google e no WhatsApp o link aparece como "Lovable App", com a imagem da plataforma: parece golpe e derruba o clique.

**Como corrigir:**

Título, descrição, og:image próprios e lang="pt-BR".

**Prompt pronto para o agente (Claude, Codex, Cursor…):**

```text
Em index.html troque o title para "AgendaFácil · agenda online para clínicas", a meta description, og:title, og:description e og:image (public/og.png, 1200×630) e defina <html lang="pt-BR">. Verifique com npm run build.
```

## O que está OK

- **[C02] Limpar secrets do Git** — Nenhum arquivo sensível versionado; .gitignore cobre .env*; histórico limpo (gitleaks sem achados).
- **[C03] Usar apenas Public Key no DB** — O front usa só a chave pública do Supabase; nenhum service role no código do cliente.
- **[C05] Criptografia de dados** — Sem dado de cartão; telefone guardado com RLS (após a correção do C04).
- **[C07] Restringir acessos** — Todas as leituras usam o cliente autenticado; RLS (após C04) filtra por clínica.
- **[C08] Bloquear Mass Assignment** — Updates do front só mexem em colunas liberadas (grant update por coluna).
- **[C09] Proteger cookies** — Sessão gerenciada pelo supabase-js em SPA (padrão aceito); sem token próprio.
- **[C10] Hash nas senhas** — Senhas gerenciadas pelo Supabase Auth.
- **[C12] Bot protection** — Captcha do Supabase Auth (Turnstile) ligado no cadastro.
- **[C14] Validação dos inputs** — Formulários validados com zod no front e checagem no banco; sem HTML dinâmico.
- **[C15] Evitar vazamento de conteúdo** — Sem source maps públicos; erros genéricos na tela.
- **[C17] Limitar respostas de API** — Listagens com .range() e colunas explícitas.
- **[C19] Forçar HTTPS** — HTTP redireciona para HTTPS com 301; HSTS ativo pela Netlify.
- **[C20] Scan de dependências** — npm audit sem vulnerabilidade alta ou crítica; lockfile versionado; Dependabot ativo.
- **[P01] Configuração de produção** — Variáveis do código documentadas no .env.example; sem localhost no cliente.
- **[P04] Deploy, migrations e rollback** — Migrations versionadas em supabase/migrations; build no CI a cada push.
- **[P07] LGPD, privacidade e termos** — Política de privacidade e termos no rodapé e no cadastro; exclusão de conta em Configurações.
- **[P09] Performance e experiência** — LCP de 1,9 s no PageSpeed (celular); imagens em WebP.

## Não se aplica

- **[C13] Queries parametrizadas** — Sem SQL próprio: todas as consultas passam pelo supabase-js.
- **[C16] Restringir uploads** — O app não tem upload de arquivos.
- **[P05] Uptime e alertas** — Hospedagem estática na Netlify com certificado automático; monitor de uptime fica como melhoria.

## Checklist manual (fora do código)

- [ ] **[C01]** Rotacionar a chave na OpenAI (platform.openai.com → API keys) e cadastrar a nova com `supabase secrets set OPENAI_API_KEY=...`.
- [ ] **[C04]** Aplicar a migration (supabase db push) e rodar de novo o check com --sondar-dados para ver 0 linhas.
- [ ] **[C06]** Cadastrar CRON_SECRET com supabase secrets set e no agendador.
- [ ] **[P06]** DNS no Registro.br e SMTP no painel do Supabase.
- [ ] **[P03]** Conferir em Supabase → Database → Backups e testar uma restauração.
- [ ] **[P10]** Configurar o orçamento na OpenAI.

## Próximos passos

1. Responda as decisões pendentes acima — elas mudam parte das correções.
2. Abra o seu agente (Claude Code, Codex, Cursor…) na raiz do projeto e peça: **"Leia check-report/CORRECOES.md e aplique as correções na ordem, uma por vez."**
3. Faça o checklist manual (o que o agente não pode fazer por você).
4. Rode o check de novo para confirmar que tudo virou ✅.

## Prompts prontos para o próximo passo

Copie e cole no seu agente, aberto na pasta do projeto. No claude.ai ou em outro chat, anexe antes este relatório e o `CORRECOES.md`. A lista completa está em [PROMPTS.md](https://github.com/dantaspaulo/check-pre-lancamento/blob/main/PROMPTS.md).

### PA01 · Resolver primeiro o que impede o lançamento

**Quando usar:** o veredito saiu 🔴 ou há falha crítica. Resolve hoje só o que derruba o lançamento.

```text
Leia check-report/RELATORIO.md e check-report/CORRECOES.md. Hoje quero resolver só o que impede o lançamento: os itens 🔴 Críticos e as ações urgentes fora do código.
1. Liste esses itens em ordem de risco, cada um com uma frase dizendo o que um atacante consegue fazer.
2. Para cada chave exposta, me passe o passo a passo para gerar uma nova e revogar a antiga no painel do provedor. Eu faço essa parte: você não toca em chave real e nunca escreve o valor de uma chave no chat, em código ou em commit.
3. Corrija no código só esses itens, um por vez, seguindo as regras do topo do CORRECOES.md. Depois de cada um, rode build e testes e me mostre a prova de que fechou.
Não mexa em ATENÇÃO nem em prontidão agora. Se uma correção depender de decisão minha, pare e pergunte.
```

### PA02 · Rotacionar chaves vazadas

**Quando usar:** o relatório achou chave no código, no bundle do navegador ou no histórico do git. Tirar a chave do código não basta: quem copiou continua com ela.

```text
O check-report/RELATORIO.md apontou chaves expostas (C01 e C02). Me guie na troca de cada uma, sem nunca mostrar o valor de nenhuma chave no chat.
Para cada chave:
1. de qual provedor ela é e onde, no painel, gerar a nova;
2. onde atualizar: variáveis de ambiente da hospedagem, Edge/Cloud Functions, CI e o .env local (que não vai para o git);
3. como revogar a antiga e como confirmar que ela parou de funcionar;
4. como testar que o app funciona com a nova.
Depois, tire do código as chaves que estavam escritas nele e leia cada uma do ambiente (process.env, Deno.env ou equivalente). Chave de servidor nunca pode ter prefixo público (NEXT_PUBLIC_, VITE_, EXPO_PUBLIC_).
Se a chave está no histórico do git, trocar a chave já resolve. Reescrever o histórico é opcional e só com o meu OK.
No fim, rode de novo a busca de segredos do check-pre-lancamento.
```

### PA03 · Corrigir na ordem, uma task por vez

**Quando usar:** sempre que o relatório tiver FALHA ou ATENÇÃO. É o prompt principal.

```text
Leia check-report/CORRECOES.md e aplique as correções na ordem, uma task por vez, seguindo as regras do topo do arquivo.
Para cada task:
1. Antes de mexer, me diga em até 3 linhas o que vai mudar, em quais arquivos e o que pode quebrar.
2. Faça a menor mudança que resolve. Nada de refatoração fora da task.
3. Rode o que o projeto tiver de build, lint, typecheck e testes. Se quebrar, conserte antes de seguir.
4. Se o projeto usa git, faça um commit por task com a mensagem sugerida.
5. O que for "Ação manual" é meu: anote e me entregue a lista no final.
Pare e me pergunte antes de: mexer em permissão de banco (GRANT, REVOKE, policy, função), apagar dado, reescrever histórico do git ou decidir algo de produto.
No fim, me mostre uma tabela com a task, o que foi feito e como você provou que funcionou.
```

### PA04 · Revisar as permissões do Supabase, tabela por tabela

**Quando usar:** o app usa Supabase e o relatório marcou RLS, policies, grants, funções ou views. Este é o prompt que evita o erro mais comum: revogar o `anon` em massa e depois "consertar" devolvendo EXECUTE em todas as funções, o que reabre as internas.

```text
Quero revisar as permissões do banco Supabase sem quebrar o app. Até eu aprovar, é só leitura.
1. Rode, ou me peça para rodar no SQL Editor, as três consultas da seção "Consulta de permissões" de references/stacks/baas.md da skill check-pre-lancamento. Salve o resultado em check-report/permissoes-antes.md: é o retrato de antes.
2. Monte uma tabela com cada tabela, view e função do schema public: o que anon e authenticated podem fazer hoje, se a RLS está ligada, quais policies existem e o que o app realmente usa. Para saber o que o app usa, procure cada supabase.from('...') e supabase.rpc('...') no código e diga se roda antes ou depois do login.
3. Proponha uma migration que deixa cada papel só com o que precisa:
   - GRANT por tabela, nunca "on all tables";
   - RLS ligada em todas as tabelas, com policies que checam o dono (auth.uid()) ou a organização;
   - views com security_invoker = true;
   - funções SECURITY DEFINER com set search_path = '' e EXECUTE revogado de public e de anon. Revogar só do anon não fecha: o Postgres dá EXECUTE a PUBLIC por padrão.
4. Não devolva EXECUTE em massa ("grant execute on all functions in schema public"): as funções internas, fechadas de propósito, voltam a abrir. Conceda só as funções que o app chama por rpc(), uma a uma, e só ao papel que chama.
5. Me mostre a migration e espere o meu OK. Depois de aplicada, teste com um visitante sem login e com duas contas logadas diferentes: a conta A não pode ler nem alterar dado da conta B.
```

### PA14 · Conferir de novo e comparar com a análise anterior

**Quando usar:** depois de aplicar as correções.

```text
Antes de tudo, copie check-report/findings.json para check-report/findings-anterior.json. Depois rode o check-pre-lancamento de novo neste projeto.
Com o relatório novo, me mostre:
1. as notas antes e depois;
2. o que fechou (com a prova), o que continua aberto e o que apareceu de novo;
3. se alguma correção abriu outro problema (por exemplo, permissão devolvida em massa ou rota que perdeu a checagem de login).
Não marque nada como OK sem evidência.
```


## Cobertura desta análise

O que foi olhado e o que ficou de fora. O que não foi olhado não está aprovado.

- scan.py: 214 arquivos, histórico do git completo, npm audit executado
- check_url.py: site publicado, DNS de e-mail e sondagem do Supabase (somente contagem)
- Revisadas as 6 Edge Functions e as 9 telas que gravam dados
- Fora do escopo: painel da Netlify e app mobile (não existe)

---
Gerado pela skill **[check-pre-lancamento](https://github.com/dantaspaulo/check-pre-lancamento)** v2.1.0 · criada por **Paulo Sérgio Dantas** · [github.com/dantaspaulo](https://github.com/dantaspaulo)  
Triagem automatizada + revisão de código por IA. Ajuda muito, mas não substitui pentest profissional em app que lida com dinheiro, saúde ou dado sensível em escala.
