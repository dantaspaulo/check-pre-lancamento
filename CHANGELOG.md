# Histórico de versões

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versões seguem [SemVer](https://semver.org/lang/pt-BR/).

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
