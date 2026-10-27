---
name: check-pre-lancamento
description: "Check pré-lançamento de app: 20 checagens de segurança e 10 de prontidão, com nota, veredito e correções prontas. Use quando o usuário disser check, revisa antes de lançar, vou colocar no ar, deploy, publicar, meu app tá seguro?, auditoria ou pentest, ou pedir revisão de um repo, MVP ou site. Serve para app de Lovable, Bolt, v0, Replit, Base44, Cursor e Claude Code e para código próprio de front e back: React, Next.js, Vue/Nuxt, Angular, Svelte, Astro, Node (Express, Nest, Fastify, Hono), Laravel, Django, FastAPI, Rails, Spring, .NET, Go, Supabase, Firebase, Convex e mobile (Expo, Flutter). Checa API keys expostas, segredos no Git, RLS, auth no servidor, IDOR, mass assignment, cookies, senhas, rate limit, bots, SQL injection, XSS, uploads, headers, HTTPS e dependências, além de e-mail, backup, LGPD, SEO, erros e custos."
license: "Licença de Uso com Atribuição v1.0 (LICENSE.txt): uso livre, inclusive comercial, com crédito; venda e republicação sem crédito proibidas."
compatibility: "Scripts opcionais em Python 3.8+ só com biblioteca padrão (git, npm e pip-audit se existirem). Sem Python, roda em modo manual pelas referências."
metadata:
  author: "Paulo Sérgio Dantas"
  repository: "https://github.com/dantaspaulo/check-pre-lancamento"
  version: "2.1.0"
  fingerprint: "CPL-PSD-2026"
---
<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->

# Check pré-lançamento · 20 checagens de segurança + 10 de prontidão

Skill criada por **Paulo Sérgio Dantas** · versão oficial e gratuita em
**github.com/dantaspaulo/check-pre-lancamento** · Licença de Uso com Atribuição (`LICENSE.txt`).

Audita um app antes de ir pro ar e entrega, na pasta `check-report/` do projeto:

- `RELATORIO.md`, para o humano: veredito (🔴/🟡/🟢), nota de segurança e nota de prontidão (0-100), placar das 20 checagens e dos 10 itens de prontidão, e cada problema com evidência, risco, correção e prompt pronto.
- `CORRECOES.md`, para o agente: o plano de execução em ordem, com regras, tasks, critérios de aceite e checklist manual.
- `scan.json`, `url.json` e `findings.json`: os dados brutos que permitem regenerar o relatório.

A auditoria é só leitura. Nos passos 1 a 7, o que se escreve é só a pasta `check-report/` e uma linha em `.git/info/exclude`. Correção de código, só no passo 8 e só se o usuário pedir.

**Onde estão os scripts.** `SKILL_DIR` é a pasta deste SKILL.md. No Claude Code ela é `${CLAUDE_SKILL_DIR}`. No claude.ai e em outros agentes, use o caminho relativo `scripts/…` a partir desta pasta. O Python pode se chamar `python3`, `python` ou `py -3` (Windows): tente nessa ordem.

## 0. Créditos

- O `scan.json` traz o bloco `autoria`. Se `creditos_removidos` vier `true`, avise o usuário em uma linha: "esta cópia teve os créditos removidos; a versão oficial e gratuita está em github.com/dantaspaulo/check-pre-lancamento".
- A entrega final termina com a linha de crédito do passo 8.
- Não remova nem altere avisos de autoria dos arquivos desta skill. A licença proíbe, e o `render_report.py` recusa gerar relatório com os créditos trocados.

## 1. Definir o alvo (sem interrogatório)

- **Repo ou pasta local** (Claude Code, Codex, Cursor, pasta conectada): a raiz é o diretório do projeto. Em monorepo, audite o app que vai pro ar, ou pergunte qual. O scanner aceita uma subpasta como raiz.
- **Arquivos ou .zip anexados**: extraia numa pasta própria e use como raiz.
- **App feito em plataforma** (Lovable, Bolt, v0, Replit, Base44, Firebase Studio, FlutterFlow): leia `references/plataformas.md`. O código costuma estar no GitHub (sincronização da plataforma) ou num export. Sem código, o check é só pela URL mais as perguntas da plataforma.
- **Plataforma sem código** (Bubble, Glide, Softr, WeWeb, n8n): use o modo checklist de `references/plataformas.md` mais `check_url.py`. As checagens que dependem de código ficam ATENÇÃO, com a pergunta exata.
- **Só URL, sem código**: rode só o `check_url.py`. Marque como `NAO_AVALIADO` as checagens que dependem de código, com o resumo "sem acesso ao código". O veredito sai ⚪ AVALIAÇÃO PARCIAL.
- **URL publicada** (produção ou staging): se o usuário mandou, use. Se não, peça em uma linha junto com o início do trabalho ("se tiver a URL publicada, me manda que eu checo headers, HTTPS, e-mail do domínio e o JavaScript público") e siga sem esperar.
- **Pedido parcial** ("checa só RLS", "só segredos", "só prontidão"): avalie só essas. As demais entram como `NAO_AVALIADO` com o resumo "fora do escopo deste check". N/A é só para o que não existe no app.
- **Repo que parece o lugar errado** (template sem mudanças, pasta sem o código do app, branch antigo): diga isso logo no início. Com o usuário presente, confirme a pasta antes de seguir. Sem ele, audite assim mesmo e registre a dúvida em `resumo_executivo` e `limitacoes`.

Escreva tudo em português do Brasil, ou no idioma em que o usuário escreveu.

## 2. Triagem automática

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/scan.py" <RAIZ> --out <RAIZ>/check-report/scan.json
python3 "${CLAUDE_SKILL_DIR}/scripts/check_url.py" <URL> --out <RAIZ>/check-report/url.json   # só se tiver URL
```

- **`scan.py`** (só stdlib, não altera nada) faz o seguinte:
  - detecta stack e plataforma, lista rotas de 20+ frameworks e procura 50+ formatos de segredo;
  - varre o histórico do git;
  - analisa migrations e regras (Supabase, Firebase, PocketBase, Appwrite, Convex);
  - aplica regras por framework (Laravel, Django, Rails, Spring, .NET, Go, Angular, mobile…);
  - coleta os sinais de prontidão;
  - roda `npm`/`pnpm`/`yarn`/`bun audit` (só produção, e separa o que é só de build e só de dev), `pip-audit`, `composer audit`, `osv-scanner`, `govulncheck` e `bundle-audit` quando existem.
  - Sem rede, use `--no-audit`. Com histórico gigante, `--no-git-history`, e registre em `limitacoes`.
  - Comentário não dispara regra (código comentado não roda). O que o `.gitignore` ignora e as pastas fora do build (`docs/`, `examples/` na raiz) ficam fora das regras de código. Segredo continua sendo procurado em todas elas (no que o git ignora, com confiança baixa: não vai para o repositório, mas vaza se entrar no build). Para tirar outra pasta (cópias locais, sincronização, rascunhos), use `--ignorar pasta/` (repete ou separa por vírgula) ou um arquivo `.check-pre-lancamento-ignore` na raiz, no formato do `.gitignore`. `--varrer-tudo` desliga tudo isso. O que ficou de fora vem em `cobertura_do_scan` e em `avisos`, e vai para `cobertura` no `findings.json`.
- **`check_url.py`** faz só GETs normais no domínio do usuário. Ele olha:
  - headers, cookies, CORS, redirect HTTP→HTTPS e certificado;
  - arquivos expostos (`/.env`, `/.git`, actuator, logs);
  - chaves e source maps nos bundles JS;
  - SEO e compartilhamento (título, og:image, robots, sitemap, 404);
  - compressão, cache, tempo de resposta;
  - DNS de e-mail (SPF, DMARC, DKIM). Use `--sem-dns` para pular.
- **`--sondar-dados`** (só com o OK explícito do dono do app): com a chave pública que o próprio site entrega, o `check_url.py` pergunta ao Supabase quantas linhas um visitante sem login lê (só a contagem) e testa Firestore, Realtime DB e Storage do Firebase (lê no máximo 1 documento e descarta). Nunca escreve. É a prova mais forte de RLS e regras abertas em app de Lovable/Bolt/FlutterFlow.
- Se `gitleaks` estiver instalado (veja `ferramentas_disponiveis`), rode `gitleaks detect --redact --no-banner -v` para C02.
- O `scan.json` pode ser grande. Filtre por item: `python3 -c "import json;d=json.load(open('check-report/scan.json'));print(json.dumps(d['checks']['C04'],ensure_ascii=False,indent=1))"`, ou `jq '.prontidao.P06'`.
- **Sem Python** (Lovable, Bolt, Replit e outros agentes que só leem e editam): faça a triagem lendo os arquivos, guiado pela seção "Como detectar" de cada checagem em `references/checks.md` e pela stack em `references/stacks/`. Mais lento, mesmo critério. Em `limitacoes`, diga que o scanner não rodou.

A sugestão do scanner (`FALHA_PROVAVEL`, `REVISAR`, `REVISAO_MANUAL`, `SEM_ACHADOS`, `NA_PROVAVEL`, `VERIFICAR_FORA_DO_REPO`…) é só ponto de partida:
- falso positivo existe, e "sem achados" não é "OK";
- os sinais de rota são por arquivo: um arquivo com auth numa rota pode ter outra rota pública ao lado;
- tudo o que estiver em `avisos` (clone raso, histórico parcial, auditoria não executada, projeto grande cortado) vai para `limitacoes`.

## 3. Revisão do código (é aqui que está o valor)

Leia `references/checks.md` inteiro antes de decidir qualquer status. Ele é o critério de FALHA/ATENÇÃO/OK/N/A e traz as correções gerais. Para a stack do projeto (campo `stack` do scan), abra a seção correspondente:

| Stack detectada | Referência |
|---|---|
| React/Vite, Next.js, Remix, Vue/Nuxt, Svelte/SvelteKit, Angular, Astro, Expo/RN, Flutter, Electron/Tauri, extensões | `references/stacks/front-e-mobile.md` |
| Express, Fastify, Nest, Hono, Koa, Elysia, Adonis, tRPC, GraphQL, Workers, Lambda | `references/stacks/back-js.md` |
| Laravel, Symfony, Django/DRF, Flask, FastAPI, Rails | `references/stacks/back-php-python-ruby.md` |
| Spring Boot, ASP.NET Core, Go | `references/stacks/back-java-dotnet-go.md` |
| Supabase, Firebase, Convex, PocketBase, Appwrite, Clerk/Auth0/Auth.js/Better Auth | `references/stacks/baas.md` |
| Lovable, Bolt, v0, Replit, Base44, Bubble, FlutterFlow… (campo `plataforma`) | `references/plataformas.md` |

a. **Mapear a superfície**: stack, provedor de auth, onde está o banco, quem fala com ele (cliente ou servidor), rotas (`checks.C06.sinais.rotas`), uploads, chamadas de IA, e-mail/SMS, pagamento. Abra o manifesto de dependências (`package.json`, `composer.json`, `requirements`, `pom.xml`, `go.mod`, `*.csproj`), as configs, os middlewares, os clientes do banco e as rotas principais.

b. **Confirmar os achados**: abra cada arquivo:linha de confiança alta e média e descarte o falso positivo. Exemplos: a `anon key` do Supabase não é segredo; `$queryRaw` com template tag é seguro; `{!! csrf_field() !!}` é seguro. Confiança baixa é só pista.
   Arquivo que pode ter segredo (`.env*`, configs, clientes do banco, achados de C01/C02/C03) se abre com `python3 "${CLAUDE_SKILL_DIR}/scripts/show.py" <arquivo> [--linhas 10-40]`. Ele mascara os valores, esconde corpo de chave privada e mostra o `role` de JWTs. Assim a chave real nunca entra na conversa.

c. **Revisão semântica das rotas** (o scanner não resolve sozinho). Para cada rota, Server Action, controller, Edge/Cloud Function ou função Convex que lê ou escreve dado de usuário, responda:
   - valida sessão no servidor (C06)?
   - filtra pelo dono ou checa papel (C07)?
   - restringe os campos aceitos (C08)?
   - valida o input com schema (C14)?
   - tem rate limit, se for sensível (C11)?
   - devolve só os campos necessários, com paginação (C17)?

   Com mais de 25 rotas, priorize dinheiro, dados pessoais, admin, IA e upload. Se houver subagentes, divida por grupo de rotas e passe a cada um o trecho do `checks.md` e da stack correspondente.

d. **Estado do build**: se as dependências já estão instaladas, rode o typecheck/build que o projeto tiver, sem instalar nada durante a auditoria. Se não builda, ou se faltam peças óbvias (o scan aponta em `C14.sinais`), registre em `preparacao` (vira a Task 0) e em `limitacoes`.

e. **O que não está no repo**: RLS sem migrations (C04), rate limit e WAF no edge (C11), headers e HTTPS sem URL (C18/C19), auditoria sem rede (C20), backup, SMTP e alertas de custo (P03, P06, P10). Se houver conector/MCP do Supabase, Vercel, Firebase ou Cloudflare, use só para leitura. Sem isso, marque ATENÇÃO e escreva em `acao_manual` o comando, a query ou o caminho exato no painel para o usuário conferir.

f. **Permissões do banco (Supabase)**: as migrations não mostram os GRANTs que o próprio Supabase deu, nem o que foi mudado pelo painel. Com o OK do dono, rode as três consultas de `references/stacks/baas.md` → "Consulta de permissões" (só leitura, pelo MCP ou pedindo ao usuário que rode no SQL Editor). É assim que aparece o `anon` com GRANT em tudo e o privilégio padrão que abre todo objeto novo. A partir de 30/10/2026 a tabela nova nasce sem GRANT: o erro 42501 no app não se corrige com GRANT em massa.

## 4. Prontidão para o lançamento (P01–P10)

Leia `references/prontidao.md`. São 10 itens que não são de segurança, mas derrubam lançamento:

| | | | |
|---|---|---|---|
| **P01** configuração de produção | **P02** erros e logs monitorados | **P03** backup e recuperação | **P04** deploy, migrations e rollback |
| **P05** uptime e alertas | **P06** e-mail e domínio | **P07** LGPD, privacidade e termos | **P08** SEO e compartilhamento |
| **P09** performance e experiência | **P10** custos e limites de gasto | | |

O scan traz sinais em `prontidao.Pxx`, e o `check_url.py` traz o lado público. Vários itens dependem de painel (backup, SMTP, alerta de gasto): pergunte em uma linha ou deixe como ATENÇÃO com a ação manual. A prontidão tem nota própria e não muda a nota de segurança, mas uma falha alta de prontidão impede o veredito 🟢.

## 5. Decidir status e severidade

Siga "Regras gerais de status" do `checks.md`. Em resumo:

- **FALHA**: você viu o problema (arquivo:linha ou resposta do site).
- **ATENÇÃO**: indício, ou não verificável daqui, sempre dizendo o que validar.
- **OK**: verificado, com evidência.
- **N/A**: a superfície não existe, com o porquê.
- **NÃO AVALIADO** (`NAO_AVALIADO`): não foi olhado nesta rodada (pedido parcial, sem código). Não entra na nota e impede o veredito 🟢.
- Nas checagens semânticas (C06, C07, C08, C14, C17), OK só depois de revisar as rotas.
- A severidade efetiva parte da base e muda pelo contexto. Exemplos: chave Stripe de teste é ALTO; endpoint de IA sem rate limit é ALTO; Flask `debug=True` é CRÍTICO; `noindex` em produção é ALTO na prontidão. Justifique no `risco`.

## 6. Escrever `findings.json`

Leia `references/report-format.md` (esquema, exemplos e como escrever bons prompts de correção) e grave `<RAIZ>/check-report/findings.json` com as 20 checagens em `checks` e os 10 itens em `prontidao`. O relatório vale a pena quando tem:

- **Evidência concreta**: `arquivo:linha — o que tem lá`, nunca o valor do segredo.
- **Risco em linguagem de atacante**: o que alguém consegue fazer, em 1-2 frases. Na prontidão, o efeito no lançamento.
- **Correção na stack do projeto**: o código da referência adaptado aos arquivos e às libs reais dele, não genérico.
- **Prompt autocontido**: o agente que for executar não viu esta análise. Diga os arquivos, o que mudar, as restrições e como verificar.
- **Ordem real de execução**: use `depende_de` quando uma correção precisa de outra antes. O render respeita a dependência mesmo contra a severidade.
- **Decisões de produto no topo**: perguntas que só o dono responde e que mudam várias correções vão em `decisoes_pendentes`.
- **Cobertura honesta**: em `cobertura`, liste o que foi olhado e o que ficou de fora, inclusive as pastas que o scanner deixou fora das regras de código. O que não foi olhado não está aprovado.
- **Prompts do próximo passo**: o `render_report.py` põe no fim do relatório os prompts de `references/prompts-pos-analise.md` que combinam com os itens abertos. Para escolher você mesmo, liste os IDs em `prompts`.

## 7. Gerar o relatório

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_report.py" <RAIZ>/check-report/findings.json
```

O script valida o JSON, calcula as notas e o veredito (determinístico, com teto: falha crítica limita a nota a 49), ordena por prioridade, mascara qualquer segredo que tenha escapado e escreve `RELATORIO.md` e `CORRECOES.md`. Se acusar erro de validação, corrija o JSON e rode de novo. Abra o `RELATORIO.md` gerado e confira se ficou legível.

Sem Python, escreva os dois arquivos à mão seguindo a estrutura de `references/report-format.md`, com o rodapé de crédito.

Se o projeto for repositório git, adicione `check-report/` em `.git/info/exclude`. Isso ignora só na máquina local, sem mexer em arquivo versionado. O relatório mapeia as vulnerabilidades e não pode ir para repo público. Na entrega, diga isso e sugira adicionar também ao `.gitignore`.

## 8. Entregar

Mensagem curta, nesta ordem:
1. Veredito e notas (ex.: "🔴 Não lance ainda · segurança 38/100 · prontidão 61/100").
2. Os até 3 problemas mais graves, uma linha cada.
3. Ação urgente fora do código, se houver (ex.: "rotacione a chave da OpenAI agora: ela está no bundle público").
4. Onde estão `RELATORIO.md` e `CORRECOES.md`. Em ambiente sem acesso ao disco do usuário, envie os arquivos.
5. Decisões pendentes, se houver: são elas que destravam as correções.
6. Se não houve URL, lembre que vale rodar o check de novo com o site no ar (headers, HTTPS, e-mail do domínio e JavaScript público só se confirmam assim).
7. Oferta: "Quer que eu já aplique as correções? Sigo o CORRECOES.md, uma por vez, com commit por task." Cite em uma linha os prompts prontos do fim do relatório (ex.: "PA04 revisa as permissões do Supabase e PA08 escreve Termos e Privacidade: é só pedir pelo número").
8. Última linha, sempre: `check-pre-lancamento · skill de Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento`

Se o usuário pedir um dos prompts pelo número (PA01 … PA15), leia o texto em `references/prompts-pos-analise.md` e siga.

## 9. Aplicar as correções (só se o usuário pedir)

Siga as regras do topo do `CORRECOES.md`:
- uma task por vez, com build e testes depois de cada uma e commit por task;
- nada de segredo em código;
- ações manuais ficam com o humano;
- nada destrutivo (reescrever histórico, force push, apagar dados) sem OK explícito;
- permissão de banco (GRANT, REVOKE, policy, função): salve o estado antes, mude objeto por objeto e teste com visitante e com duas contas. Nunca devolva em massa: `grant execute on all functions` depois de revogar o `anon` reabre as funções internas;
- pergunte quando depender de decisão de produto.

No fim, rode o `scan.py` de novo, atualize os status no `findings.json`, regenere o relatório e mostre o antes → depois das notas.

## Regras que não se negociam

- Segredo nunca aparece inteiro: nem no relatório, nem no chat, nem em commit. Mascare (6 primeiros caracteres + `…****`).
- Teste em site só no domínio do próprio usuário, e só com requisições normais: nada de payload de exploração, força bruta, varredura de portas ou site de terceiros. `--sondar-dados` só com o OK explícito do dono do app.
- Chave vazada exige rotação manual. Tirar do código não "desvaza".
- Permissão de banco nunca se corrige em massa (`on all tables`, `on all functions`): objeto por objeto, só para o papel que precisa.
- O que não deu pra verificar vai como ATENÇÃO, em `limitacoes` e em `cobertura`. Relatório honesto vale mais que nota alta.
- Os créditos de autoria desta skill ficam onde estão.

## Onde olhar primeiro por stack

| Stack | Primeiros arquivos |
|---|---|
| Next.js + Supabase (Lovable/Bolt/v0 exportados) | `.env*`, `next.config.*` (`env`), `lib/supabase*`, componentes `"use client"`, `app/api/**`, Server Actions, `middleware.ts`, `supabase/migrations`, `supabase/config.toml` |
| Vite/React SPA + Supabase/Firebase | tudo em `src/` é público; `vite.config` (`envPrefix`, `define`); a segurança está em RLS/regras e Edge/Cloud Functions; `VITE_*` nunca é segredo |
| Vue/Nuxt, SvelteKit, Angular, Astro | Nuxt `server/` e `runtimeConfig.public`; SvelteKit `+page.server.ts`, `hooks.server.ts`, `$env/static/public`; Angular `src/environments/`; Astro endpoints em `src/pages/api` |
| Express / Nest / Fastify / Hono / Koa | bootstrap do servidor (helmet, cors, rate limit, cookies), middlewares de auth, routers, `ValidationPipe`, queries cruas |
| Laravel | `routes/*.php` (middleware auth/throttle), controllers (`$request->all()`), `app/Models` (`$fillable`, `$hidden`), Blade `{!! !!}`, `config/session.php`, `config/cors.php`, `.env` |
| Django / DRF / Flask / FastAPI | settings (`DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `SECURE_*`, `DEFAULT_PERMISSION_CLASSES`), views, serializers, `execute`/`raw` |
| Rails | `config/routes.rb`, controllers (`before_action`, strong params), `config/environments/production.rb`, `.html_safe` |
| Spring Boot / ASP.NET Core / Go | `SecurityFilterChain`, `application.properties`, controllers e DTOs; `Program.cs`, `appsettings*.json`, `[Authorize]`; handlers, middleware e `fmt.Sprintf` em SQL |
| Firebase / Convex / PocketBase / Appwrite | `firestore.rules`/`storage.rules`, App Check; funções em `convex/`; `pb_migrations`; permissões das coleções |
| Mobile (Expo/RN/Flutter) e desktop (Electron/Tauri) | o app inteiro é cliente: chave no app é chave pública; `app.json` `extra`, `--dart-define`, AsyncStorage/SharedPreferences, `AndroidManifest.xml`, `Info.plist` |

---
<sub>check-pre-lancamento v2.1.0 · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0</sub>
