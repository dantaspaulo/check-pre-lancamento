# Histórico de versões

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [2.2.1] · 2026-10-27

### Mudou
- Ajuste no texto de apresentação dos prompts de engenharia (PA16 a PA21).

## [2.2.0] · 2026-10-27

### Novo
- **Seis prompts de engenharia para depois do lançamento (PA16 a PA21):** duas requisições ao mesmo tempo (pedido duplicado, cupom usado duas vezes), webhook e pagamento que aguentam repetição, regra de negócio que o navegador decide, testes de integração nos fluxos que não podem quebrar, dividir arquivo grande sem mudar comportamento e um raio-x de engenharia só de leitura. Os temas vieram de uma sugestão de usuário.
- O relatório traz o PA17 por extenso quando o C06 ou o C08 ficam abertos e o assunto é webhook ou pagamento, o PA18 com C07 ou C08 abertos e o PA19 com P04 aberto. Os demais prompts de engenharia aparecem citados no fim, com link para a ordem sugerida.

### Corrigido
Uma revisão adversarial da 2.1.0 achou 15 problemas, todos reproduzidos e agora cobertos por teste. Três eram regressões: a 2.0.0 achava e a 2.1.0 deixou de achar.
- **Regressões da 2.1.0:**
  - policy, RLS e GRANT dentro de bloco `DO $$ ... $$` (o jeito comum de criar policy idempotente) não eram lidos;
  - `using(true)` e `with check(true)` sem espaço antes do parêntese passavam sem achado;
  - um apóstrofo dentro de `$$...$$` ou um `\'` numa string `E'...'` juntava todos os comandos seguintes num só.
- **Pasta do scan dentro de outro repositório que a ignora** (um zip extraído em `tmp/`): tudo virava "ignorado" e nenhuma regra rodava. O `.gitignore` agora só vale quando a raiz tem arquivo versionado e não é ignorada pelo repositório de cima.
- **Zip sem git:** o arquivo que casa com o `.gitignore` está versionado (veio no zip), então continua nas regras de código e com a confiança normal. Arquivo versionado dentro de pasta ignorada também continua valendo, e o `.env` de pasta ignorada passa pela busca de segredo.
- **Template de servidor:** em PHP, Blade, ERB, Razor e no HTML do Django, Jinja ou Thymeleaf, o `<!-- -->` não é mais tratado como comentário, porque o servidor executa o que está dentro dele.
- **Regex literal do JavaScript** como `/\/*$/` não abre mais um comentário falso, e o leitor de comentários ficou linear (um caso de 16 mil linhas caiu de 25 s para menos de 1 s).
- **C20:** pacote importado em `src/.../tools/`, servidor chamado no script `start` (como o `serve`) e o runtime do framework (Next, Nuxt, SvelteKit, Express…) voltam a contar como produção.
- **P07:** o link para a política do Google, do Stripe e de outros terceiros (o aviso do reCAPTCHA, por exemplo) não conta mais como página legal do app.
- **Funções:** `drop function` e uma sobrecarga nova voltam ao padrão do Postgres (EXECUTE para PUBLIC) em vez de herdar o REVOKE da função antiga.
- **Outros:** `config.toml` salvo com CRLF (Windows); regras de função e view só valem com Supabase ou PostgREST (Rails, Prisma e cia. não expõem o banco); tabela temporária não conta como tabela do schema; GRANT em massa num schema não atinge as tabelas de outro; `revoke grant option for` não tira mais o privilégio; FIFO no lugar do arquivo de ignorar não trava o scan; o aviso de "apaga dados" não dispara mais no privilégio `truncate` de um REVOKE; e `stack` em lista não quebra o relatório.

## [2.1.0] · 2026-10-27

Feita a partir do retorno de quem rodou a 2.0.0 num app React + Vite + Supabase + Cloudflare com uns 1.500 arquivos.

### Novo
- **Prompts para depois da análise:** 15 prompts prontos em [PROMPTS.md](PROMPTS.md) (resolver o que impede o lançamento, trocar chaves, revisar permissões do Supabase, testar se um usuário vê dado de outro, Termos e Privacidade, backup, checklist do lançamento e outros). O `RELATORIO.md` termina com os que combinam com o que foi achado, e o agente aceita o pedido pelo número ("roda o PA04").
- **Permissões do banco nas migrations (Supabase/PostgREST).** O scanner agora lê as migrations comando por comando, na ordem, e acusa:
  - `anon` com INSERT/UPDATE/DELETE por GRANT, inclusive no formato do `supabase db pull`;
  - GRANT em massa (`on all tables`, `on all functions`) e privilégio padrão que abre todo objeto novo;
  - função `security definer` que o visitante chama por `/rest/v1/rpc`, inclusive quando só o `anon` foi revogado e o `PUBLIC` continua com EXECUTE;
  - função `security definer` sem `search_path`, view sem `security_invoker`, materialized view exposta e `auto_expose_new_tables = true`;
  - tabela usada pelo app sem GRANT nas migrations (P04), que quebra num projeto novo a partir da mudança do Supabase de 30/10/2026.
- **Consulta de permissões (só leitura)** em `references/stacks/baas.md`, para ver o que o `anon` e o `authenticated` podem de fato no banco, com uma receita para tirar acesso do `anon` sem quebrar o app.
- **Aviso automático no plano de correção:** se uma correção traz GRANT ou REVOKE em massa, `disable row level security`, `drop` ou `truncate`, o `RELATORIO.md` e o `CORRECOES.md` ganham um aviso de cuidado logo abaixo. O plano ganhou a regra de nunca devolver permissão em massa: depois de revogar o `anon`, um `grant execute on all functions` reabre as funções internas fechadas de propósito.
- **P07:** link para `/termos` ou `/privacidade` sem página nem rota vira `link_legal_sem_pagina` (aceite de texto que não existe não vale, LGPD art. 9º, § 1º).
- **`bun audit`** para projetos com `bun.lock`/`bun.lockb`.
- **`--ignorar PASTA`** (ou `--ignore`) e o arquivo `.check-pre-lancamento-ignore`, no formato do `.gitignore`. `--varrer-tudo` volta ao comportamento antigo.

### Mudou
- **O scanner respeita o `.gitignore`** (pelo `git check-ignore`) e deixa fora das regras de código as pastas `docs/` e `examples/` da raiz. Chave secreta continua sendo procurada em todas essas pastas (no que o git ignora, com confiança baixa: não vai para o repositório, mas vaza se entrar no build), e o que ficou de fora aparece em `cobertura_do_scan` e nos avisos. Uma pasta `docs/` com `index.html`, `CNAME` ou `_config.yml` é tratada como site publicado (GitHub Pages), não como documentação.
- **Comentário não dispara regra:** o código é lido sem os comentários em JS/TS, Python, PHP, Ruby, SQL, HTML, Vue, Svelte e regras do Firebase. Os números de linha continuam os mesmos.
- **Policies separadas por público:** `policy_publica_leitura`, `policy_publica_escrita`, `policy_qualquer_logado_leitura` e `policy_qualquer_logado_escrita` substituem `policy_permissiva` e `policy_qualquer_logado`. Leitura de tabela com nome de catálogo (CID, CBHPM, TUSS, estados, categorias) cai para confiança baixa; com nome de dado de usuário, sobe.
- **C20 separa produção, build e dev:** alta/crítica em pacote que só a config do build, os scripts e os testes usam vira `vulnerabilidades_so_no_build` (média), e o que existe só em `devDependencies` vira `vulnerabilidades_so_dev` (baixa). Antes, um `vite` em `dependencies` derrubava o C20 para FALHA.
- As regras `security_definer`, `view_sem_security_invoker` e `grant_para_anon` deram lugar às novas regras de permissão.

### Corrigido
- A página legal contava como existente quando o app só tinha um link para ela, e o padrão `tos` casava com palavras como "photos".

## [2.0.0] · 2026-10-27

Primeira versão pública.

### Novo
- **10 itens de prontidão para o lançamento (P01–P10):** configuração de produção, erros e logs, backup, deploy e migrations, uptime, e-mail e domínio (SPF/DKIM/DMARC), LGPD, SEO e compartilhamento, performance e custos. Eles têm nota própria.
- **Código próprio de front e back, além das plataformas:**
  - regras e detecção de rotas para Laravel, Django/DRF, Rails, Spring Boot, ASP.NET Core, Go, Nuxt, SvelteKit, Angular, Astro, Remix/React Router, Convex, tRPC, Workers e Lambda;
  - mobile e desktop: Expo/React Native, Flutter, Electron e Tauri.
- **Plataformas:** detecção de Lovable, Bolt, Replit, Base44 e Firebase Studio, com um guia por plataforma (incluindo as de no-code, como Bubble, Glide, Softr, WeWeb, Xano e n8n) e o modo checklist para quando não há código.
- **Mais de 50 formatos de segredo**, entre eles Anthropic, OpenRouter, Groq, xAI, Hugging Face, Resend, Brevo, Meta/WhatsApp, Efí, Supabase PAT, Django `django-insecure` e connection strings JDBC e .NET.
- **Segredo injetado no bundle pela config do build:** `env` do `next.config`, `define` do Vite, `DefinePlugin`, `envPrefix` vazio e `extra` do Expo.
- **`check_url.py`:**
  - CORS refletido, certificado TLS e variante `www`;
  - SEO e compartilhamento: título de template, og:image, `noindex`, robots, sitemap e soft 404;
  - compressão, cache e peso do JavaScript;
  - DNS de e-mail;
  - sondagem opcional (`--sondar-dados`) do que o Supabase e o Firebase entregam sem login, só leitura.
- **Mais auditorias de dependências:** `composer audit`, `osv-scanner`, `govulncheck` e `bundle-audit`.
- **Relatório:**
  - nota de prontidão, seção de cobertura e teto de nota coerente com o veredito;
  - plano de correção com as tasks de prontidão depois das de segurança.
- **Autoria:**
  - licença com atribuição, `NOTICE.md`, `CITATION.cff` e impressão `CPL-PSD-2026` em todos os arquivos;
  - manifesto `AUTORIA.json` com o hash de cada arquivo, conferido pelo `autoria.py`;
  - o relatório se recusa a sair quando os créditos são trocados.
- **Instalação** em Claude Code (plugin ou pasta), claude.ai, Codex, Cursor, GitHub Copilot, Gemini CLI, Antigravity, Windsurf, OpenCode, Kiro, Lovable, Bolt e Replit, ou pelo `npx skills`.
- **Testes:** suíte com 11 projetos de exemplo montados na hora, um servidor local para o `check_url.py` e o teste da trava de autoria.

### Corrigido
A revisão adversarial antes do lançamento achou 25 pontos, todos tratados e cobertos por teste. Entre eles:
- **Máscara de segredo:**
  - valor sem aspas em `.properties`, `.yml` e `.ini`;
  - `usuário:senha@` em qualquer URL;
  - token no caminho ou na query;
  - chave privada em várias linhas;
  - `.env` com BOM ou em UTF-16;
  - `--linhas` no meio de um PEM;
  - `.npmrc` e `.netrc`.
- **`check_url.py`:**
  - recusa URL com senha;
  - não segue redirect, sitemap nem source map para outro domínio;
  - não aciona `/actuator/heapdump`;
  - a sondagem do Supabase pede 1 linha e só conta a tabela exposta;
  - timeout total;
  - JS com gzip;
  - domínios de plataforma (`vercel.app`, `lovable.app`…) não viram achado de e-mail.
- **Robustez:**
  - `package.json` fora do formato não derruba o scan;
  - FIFO e arquivo especial são ignorados;
  - nome de arquivo inválido;
  - saída UTF-8 no Windows;
  - `npm.cmd`.
- **Precisão:**
  - RLS só é cobrado em projeto Supabase;
  - auth em comentário ou em header enviado para a OpenAI não conta;
  - SQL montado numa variável é detectado;
  - linha minificada é varrida em pedaços;
  - `.github/` é varrida;
  - variável pública só é segredo se o nome tiver cara de segredo;
  - regras de cookie, hash e chave privada mais precisas;
  - parser de rotas do Laravel com cadeia em várias linhas.
- **Relatório:** status `NAO_AVALIADO` e veredito ⚪ AVALIAÇÃO PARCIAL para check incompleto.
- **Next.js:** mínimo seguro dos boletins de 2026 (15.5.28 e 16.4.1).
- Corpo de chave privada que aparecia no `scan.json`, no `show.py` e no relatório quando estava na mesma linha do cabeçalho (JSON de service account).
- `Gemfile`, `Pipfile` e `.replit` não eram lidos (o Rails e as dependências do Pipfile não eram detectados).
- Pastas de skills de agentes (`.claude/skills`, `.agents/skills`…) eram varridas como se fossem código do app.
