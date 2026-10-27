<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Apps feitos em plataforma · Lovable, Bolt, v0, Replit, Base44, FlutterFlow, Bubble…

Como auditar app criado em plataforma de IA ou no-code: onde está o código, o que a plataforma já faz por você e o que costuma ficar aberto. O critério continua sendo o `checks.md`. Aqui está o *onde* e o *como* de cada plataforma.

O scanner detecta algumas (campo `plataforma` do `scan.json`): `lovable`, `bolt`, `replit`, `base44`, `firebase-studio`, `cursor`, `windsurf`, `claude-code`. As outras, pergunte.

> Painéis e nomes de menu mudam com frequência. Quando citar um caminho de menu na `acao_manual`, escreva "(o nome do menu pode ter mudado)" e descreva o que procurar.

## Índice
- [Como pegar o código](#como-pegar-o-código)
- [Lovable](#lovable) · [Bolt](#bolt) · [v0](#v0) · [Replit](#replit) · [Base44](#base44)
- [Firebase Studio e FlutterFlow](#firebase-studio-e-flutterflow)
- [Cursor, Windsurf, Claude Code, Codex, Copilot](#cursor-windsurf-claude-code-codex-copilot)
- [Sem código: Bubble, Glide, Softr, WeWeb, Xano, n8n](#sem-código-bubble-glide-softr-weweb-xano-n8n)
- [Perguntas para o dono (modo checklist)](#perguntas-para-o-dono-modo-checklist)

## Como pegar o código

| Plataforma | Caminho mais comum |
|---|---|
| Lovable | integração com GitHub (sincroniza o repo); depois `git clone` |
| Bolt | baixar o projeto (zip) ou conectar ao GitHub |
| v0 | sincronizar com GitHub ou baixar; o deploy fica na Vercel |
| Replit | o próprio workspace é o projeto (o agente roda lá) ou conexão com GitHub |
| Base44 | exportar o código, quando o plano permitir; senão, modo checklist + URL |
| FlutterFlow | baixar o código (Dart) ou enviar ao GitHub, nos planos que permitem |
| Bubble, Glide, Softr | não há código: modo checklist + `check_url.py` |

Com o código em mãos, siga o fluxo normal do SKILL.md. Sem ele, rode `check_url.py` (com `--sondar-dados`, se o dono autorizar) e use as perguntas do fim deste arquivo.

## Lovable

**O que é:** React + Vite + TypeScript no front. O back fica no Supabase (integração ou Lovable Cloud, que roda sobre Supabase) e em Edge Functions.

**O que costuma ficar aberto:**
- **C04 RLS**: é a falha nº 1. Tabela criada pelo agente sem policy, ou policy `using (true)`. Rode `check_url.py --sondar-dados` (com OK) para provar o que um visitante lê, e as queries de RLS do `checks.md`.
- **C01/C03**: tudo em `src/` vai para o navegador. Chave da OpenAI, Stripe secret ou service role no front é falha. Segredo mora nos *secrets* das Edge Functions (`Deno.env.get`).
- **C06**: Edge Function com `verify_jwt = false` em `supabase/config.toml` sem checar o usuário dentro dela (`edge_function_sem_jwt`).
- **C12**: cadastro aberto sem captcha. O Supabase Auth tem captcha (hCaptcha/Turnstile) nas configurações de autenticação.
- **P06**: e-mail de confirmação pelo SMTP padrão do Supabase, que é só para teste: ele só entrega para a equipe do projeto e tem limite de poucas mensagens por hora. Usuário de verdade não recebe nada. Configure SMTP próprio.
- **P08**: `index.html` com o título, a descrição ("Lovable Generated Project") e a og:image do template, e `lang="en"` (`titulo_padrao_de_template`, `lang_en_em_site_pt`). SPA sem SSR também indexa mal. Considere pré-renderizar as páginas públicas.

**O que já existe:** a Lovable tem uma checagem de segurança antes de publicar. Recomende rodar e colar o resultado, mas não use como prova de OK: ela olha principalmente o banco.

## Bolt

**O que é:** projetos Vite/React, Next.js ou Expo gerados no navegador. Banco e auth por integração (Supabase ou o banco da própria plataforma). Deploy na Netlify ou na hospedagem do Bolt. A pasta `.bolt/` indica o projeto.

**O que costuma ficar aberto:** os mesmos pontos da Lovable (RLS, chave no front, Edge Function aberta). Some a eles:
- `netlify.toml` sem `[[headers]]`, logo C18;
- variáveis de ambiente que existem só no ambiente do Bolt e não no deploy (P01).

## v0

**O que é:** Next.js (App Router) + shadcn/ui. Deploy na Vercel, com banco por integração (Supabase, Neon, Upstash…).

**O que costuma ficar aberto:**
- Server Actions e Route Handlers sem checagem de sessão (C06). Cada Server Action é um endpoint público.
- `NEXT_PUBLIC_` em chave secreta (C01).
- `next.config` sem `headers()` (C18).
- Versão do Next em faixa vulnerável (C20). Confira `next_cve_2025_29927` e `next_react2shell`.
- Variáveis só no ambiente *Preview* da Vercel e não em *Production* (P01).

## Replit

**O que é:** o Agent gera apps completos (Node/Express + React, Python/Flask ou FastAPI, e outros), com banco Postgres da plataforma, auth da plataforma opcional e deploy pela própria Replit.

**O que costuma ficar aberto:**
- **C01/C02:** chave colada no código em vez de no painel de *Secrets* (que vira variável de ambiente). Confira o histórico do git do workspace.
- **C06/C07:** rotas Express/Flask sem middleware de auth, ou IDOR por id na URL.
- **C15:** servidor rodando em modo dev no deploy (`NODE_ENV` não definido, Flask `debug=True`).
- **P01:** secret que existe no workspace mas não na configuração do deploy.
- **P03:** banco de produção sem backup conferido.

## Base44

**O que é:** plataforma com back-end próprio (entidades, auth, integrações) e SDK `@base44/sdk`.

**O que olhar:**
- permissões de cada entidade (quem lê e quem escreve: público, usuário logado, dono do registro, admin). É o equivalente de RLS (C04/C07);
- visibilidade do app (público ou privado) e quem pode se cadastrar (C06/C12);
- chaves de integração guardadas como secret da plataforma e não em texto do app (C01);
- funções de back-end que recebem dados do cliente sem validar (C14).

Sem código exportado, use o modo checklist.

## Firebase Studio e FlutterFlow

**Firebase Studio** (pasta `.idx/`): app web ou mobile com Firebase.
- `firestore.rules` e `storage.rules` (C04) e Admin SDK só no servidor (C03).
- App Check ligado (C12/C11).
- Chave de API do Google restrita por domínio ou app no Google Cloud Console (C01).

**FlutterFlow:** gera app Flutter com Firebase ou Supabase.
- Chamadas de API configuradas no FlutterFlow com chave no cabeçalho vão dentro do app instalado, ou seja, são públicas (C01). Mova essas chamadas para uma Cloud Function ou Edge Function.
- Regras do Firestore geradas pela ferramenta precisam ser revisadas coleção por coleção (C04).
- Com Supabase, RLS em todas as tabelas (C04).
- Versão web: rode `check_url.py`.

## Cursor, Windsurf, Claude Code, Codex, Copilot

Não são plataformas de app, são editores e agentes: o código é seu, em qualquer stack. Siga a referência da stack em `references/stacks/`. Arquivos `.cursorrules`, `CLAUDE.md` e `AGENTS.md` às vezes têm instrução útil ("o banco é X", "deploy na Y"). Leia antes de concluir onde fica o quê. Esses arquivos também podem conter segredo colado por engano (C01/C02).

## Sem código: Bubble, Glide, Softr, WeWeb, Xano, n8n

Não há repositório: a auditoria é a URL (`check_url.py`) mais as perguntas abaixo. Marque como ATENÇÃO o que só o dono pode confirmar no painel, com o caminho exato.

**Bubble:**
- **C04/C07, regras de privacidade (privacy rules) de cada tipo de dado.** Sem regra, os dados podem ser lidos pela API do Bubble e pelo navegador, mesmo que a página esconda. Para cada tipo com dado pessoal: "visível apenas para o criador/dono".
- **C06, condição de página.** "Só quando o usuário está logado" na página é só visual. O que protege é a privacy rule.
- **C06/C11, Data API e workflows de API.** Exponha só o necessário. Workflow de API "pode rodar sem autenticação" é endpoint público.
- **C16, arquivos enviados.** Marque como privados e ligados ao dono.
- **C12:** captcha no cadastro, se houver plugin ou opção no plano.

**Glide / Softr / WeWeb:**
- **C04/C07:** regras de linha (row owners), permissões por usuário e visibilidade de tabelas e páginas.
- **C06:** página ou tela "pública" com dado privado.
- **C03:** no WeWeb com Supabase ou Xano, a segurança está no back (RLS ou auth dos endpoints).

**Xano:**
- **C06:** endpoint sem "requires authentication".
- **C07:** filtro por `auth.id`.
- **C11:** rate limit.
- **C14:** validação de input nos endpoints.

**n8n:**
- **C06:** nó Webhook sem autenticação (header, basic ou JWT), com URL que circula.
- **C01:** credenciais no editor e não em nó de código.
- **C15/P07:** dados de execução com PII guardados por tempo indefinido. Configure a retenção.

## Perguntas para o dono (modo checklist)

Use quando não houver código ou para fechar o que o código não mostra. Uma pergunta por item, sim ou não, na ordem.

1. **C01** Alguma chave secreta (OpenAI, Stripe secret, service role) foi colada na tela, num componente ou numa chamada de API configurada no app?
2. **C04** Todas as tabelas/coleções com dado de usuário têm regra "só o dono lê e escreve"? (Supabase: RLS + policies; Firebase: rules; Bubble: privacy rules.)
3. **C06** Tem página ou função que só deveria funcionar logado? A regra está no servidor/banco ou só escondida na tela?
4. **C07** Um usuário consegue ver o pedido ou o perfil de outro trocando o número na URL?
5. **C11/C12** O cadastro, o login e as funções que chamam IA ou mandam e-mail têm limite de uso e captcha?
6. **C16** Arquivos enviados pelos usuários são privados?
7. **P03** O banco tem backup automático? Já testou restaurar?
8. **P06** O e-mail de cadastro sai por um provedor seu (SMTP próprio), com SPF/DKIM/DMARC no domínio?
9. **P07** Tem política de privacidade, termos e um jeito de o usuário excluir a conta?
10. **P10** Tem limite e alerta de gasto na IA e na nuvem?

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
