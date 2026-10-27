<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Prontidão para o lançamento · P01 a P10

Dez itens que não são falha de segurança mas derrubam um lançamento. O e-mail de cadastro não chega. O site sai com `noindex` e some do Google. A conta da IA estoura numa noite. O erro em produção passa sem ninguém ver.

Têm nota própria, que não entra na nota de segurança. Uma FALHA de severidade ALTA ou CRÍTICA aqui impede o veredito 🟢.

O scanner traz sinais em `scan.json → prontidao.Pxx`. O `check_url.py` traz o lado público (`pagina`, `dns_email`, `certificado`). Muita coisa só existe no painel (backup, SMTP, alerta de gasto). Pergunte em uma linha ou deixe ATENÇÃO com o caminho exato no painel.

| ID | Item | Severidade base |
|---|---|---|
| P01 | Configuração de produção | ALTO |
| P02 | Erros e logs monitorados | ALTO |
| P03 | Backup e recuperação | ALTO |
| P04 | Deploy, migrations e rollback | MÉDIO |
| P05 | Uptime e alertas | MÉDIO |
| P06 | E-mail e domínio | ALTO |
| P07 | LGPD, privacidade e termos | ALTO |
| P08 | SEO e compartilhamento | MÉDIO |
| P09 | Performance e experiência | MÉDIO |
| P10 | Custos e limites de gasto | ALTO |

Status como nas checagens: FALHA (viu o problema), ATENÇÃO (indício ou não verificável daqui), OK (verificado, com evidência), N/A (não se aplica, com o porquê).

---

## P01 · Configuração de produção

**O que é:** o app roda em produção com as variáveis certas, sem modo debug, sem chave de teste e sem endereço de desenvolvimento.

**Sinais:** `sem_env_example`, `env_nao_documentada` (variáveis usadas no código fora do `.env.example`), `localhost_no_cliente`, `chave_de_teste_em_producao`; nas checagens de segurança, `django_debug`, `laravel_debug_producao` e `flask_debug` (C15).

**FALHA:**
- chave de pagamento de teste (`sk_test_`, `pk_test_`, `TEST-`) configurada para produção, porque aí ninguém é cobrado;
- URL `http://localhost` fixa no código do cliente;
- debug ligado em produção.

**ATENÇÃO:** variáveis usadas no código que não estão documentadas no `.env.example` (risco de deploy sem elas); `NODE_ENV` não definido como `production` no start de um servidor Node (o Express mostra stack trace e roda mais lento).

**OK:** `.env.example` cobre o que o código lê, a produção tem variáveis próprias (painel da Vercel, Netlify, Render ou Railway, ou um cofre), e debug fica desligado.

**Como corrigir:**
- Gere o `.env.example` a partir de `prontidao.P01.sinais.faltando_no_exemplo`, só com nomes e sem valores.
- Troque URL fixa por variável: `const API = import.meta.env.VITE_API_URL` (pública: só endereço, nunca chave).
- Confira no painel da hospedagem que cada variável do `.env.example` existe no ambiente *Production* e não só no *Preview*.
- Pagamento: chaves live no ambiente de produção e webhook de produção cadastrado no painel do gateway (Stripe, Mercado Pago, Asaas, Efí, Pagar.me).

## P02 · Erros e logs monitorados

**O que é:** quando algo quebra em produção, alguém fica sabendo antes do cliente reclamar, e com o contexto para corrigir.

**Sinais:** `sem_monitoramento_de_erros`; `prontidao.P02.sinais.tela_de_erro_no_front` (error boundary, `error.tsx`, `+error.svelte`, `error.vue`).

**FALHA:** nenhum monitoramento de erro em app com usuários reais.
**ATENÇÃO:** monitoramento só no front ou só no back; erro do usuário mostrando tela branca (sem error boundary); log sem retenção.
**OK:** SDK de erros nos dois lados (Sentry, Bugsnag, Rollbar, Datadog, Highlight, PostHog error tracking ou OpenTelemetry), com alerta por e-mail ou chat, e tela de erro amigável.

**Como corrigir:** Sentry é o caminho mais curto na maioria das stacks: `npx @sentry/wizard@latest -i nextjs` (ou `reactNative`, `sveltekit`, `remix`), `sentry/sentry-laravel`, `sentry-sdk` (Python), `sentry-rails`, `io.sentry:sentry-spring-boot-starter-jakarta`, `Sentry.AspNetCore`, `github.com/getsentry/sentry-go`. Junto vão:
- source maps enviados ao Sentry e não publicados (C15);
- `beforeSend` apagando PII (LGPD);
- alerta para erro novo.

## P03 · Backup e recuperação

**O que é:** se o banco for apagado, corrompido ou sequestrado, dá para voltar, e alguém já testou isso.

**Sinais:** `prontidao.P03.sinais.scripts_de_backup`. Quase sempre o backup fica no painel do provedor, fora do repo.

**FALHA:** banco de produção sem backup (VPS com Postgres ou MySQL próprio sem rotina de dump; plano que não inclui backup e nada externo).
**ATENÇÃO:** backup existe mas a restauração nunca foi testada; backup só no mesmo servidor ou na mesma conta; uploads e storage sem backup.
**OK:** backup automático com retenção definida, cópia fora do provedor principal e um teste de restauração registrado.

**Onde conferir (ação manual):**
- **Supabase:** Database → Backups (os planos pagos têm backup diário; PITR é add-on). No plano gratuito, faça `supabase db dump` agendado para um bucket.
- **Firebase:** agende export (`gcloud firestore export gs://…`) ou ative backups agendados do Firestore.
- **Neon, PlanetScale, RDS, Cloud SQL:** retenção e PITR no painel.
- **VPS:** `pg_dump`/`mysqldump` em cron enviando para um bucket externo (S3, R2, B2), com retenção e alerta se falhar.

## P04 · Deploy, migrations e rollback

**O que é:** dá para recriar o banco e o ambiente a partir do repo, cada deploy é testado antes, e existe caminho de volta se a versão nova quebrar.

**Sinais:** `banco_sem_migrations`, `sem_testes`, `sem_ci`, `tabela_sem_grant_explicito`; sinais `ci`, `arquivos_de_teste`, `migrations`.

**Supabase a partir de 30/10/2026:** tabela nova no schema `public` não ganha mais GRANT automático para `anon`, `authenticated` e `service_role` (as que já existiam mantêm o acesso). Migration que só cria a tabela e a RLS recria um banco que não funciona: num projeto novo (staging, branch, restauração depois de um desastre) o app recebe erro 42501 nas tabelas sem GRANT. O scanner aponta como `tabela_sem_grant_explicito` as tabelas que o app usa (`supabase.from('...')`) e que nenhuma migration libera. Correção: GRANT por tabela, só ao papel que precisa, na mesma migration da RLS e das policies (ver `references/stacks/baas.md`). Nunca GRANT em massa.

**FALHA:** schema de produção alterado à mão sem migration (não reproduzível); deploy sem build verde.
**ATENÇÃO:** sem testes automatizados nos fluxos críticos (cadastro, login, pagamento); sem CI; nenhum plano de rollback.
**OK:** migrations versionadas, CI rodando build e testes a cada push, e rollback conhecido (redeploy da versão anterior na Vercel/Netlify, tag da imagem anterior, migration reversível).

**Como corrigir:**
- Gere a migration do estado atual: `supabase db diff -f inicial`, `prisma migrate dev`, `php artisan make:migration`, `python manage.py makemigrations`.
- CI mínimo no GitHub Actions: instalar → lint → typecheck → build → testes.
- Um teste de ponta a ponta do fluxo de dinheiro, mesmo que um só.

## P05 · Uptime e alertas

**O que é:** se o site cair às 3h, alguém é avisado, e o certificado e o domínio não vencem sem aviso.

**Sinais:** `sem_health_check`; no `check_url.py`, `certificado_vencendo` e `certificado.dias`.

**FALHA:** certificado vencendo em menos de 7 dias sem renovação automática; domínio vencendo.
**ATENÇÃO:** nenhum monitor de uptime; sem rota de health check; ninguém definido para receber o alerta.
**OK:** monitor externo (UptimeRobot, Better Stack, Uptime Kuma, Checkly) batendo numa rota de health a cada 1-5 minutos, com alerta no celular, mais certificado com renovação automática.

**Como corrigir:**
- Crie `/health` (ou use o `/up` do Laravel 11+ e o `/actuator/health` do Spring) checando o banco com uma query leve.
- Cadastre o monitor.
- Ative a renovação automática do domínio no registrador (Registro.br, Cloudflare etc.).

## P06 · E-mail e domínio

**O que é:** o e-mail de cadastro, confirmação, reset de senha e recibo chega na caixa de entrada, e não no spam nem em lugar nenhum.

**Sinais:**
- scan: `supabase_smtp_padrao` (Supabase Auth mandando e-mail sem SMTP próprio no config), `laravel_mail_log`, `provedor_de_email`;
- `check_url.py`: `sem_spf`, `sem_dmarc`, `dmarc_p_none`, `dns_email.dkim_seletores_achados`.

**FALHA:**
- app que depende de e-mail (cadastro com confirmação, OTP, reset) usando o SMTP padrão do Supabase em produção. Ele é só para teste: entrega apenas para os e-mails da equipe do projeto, com limite de cerca de 2 mensagens por hora, que pode mudar (supabase.com/docs/guides/auth/auth-smtp);
- domínio que envia e-mail sem SPF;
- provedor não configurado em produção.

**ATENÇÃO:** sem DMARC (Gmail e Yahoo exigem de quem envia em volume desde 2024); DMARC em `p=none`; DKIM não encontrado nos seletores comuns (confira o seletor do seu provedor); remetente `noreply@` de domínio que não é seu.

**OK:** provedor transacional (Resend, Postmark, SES, SendGrid, Brevo, Mailgun) com domínio verificado, SPF + DKIM + DMARC publicados, e o e-mail de teste chegando na caixa de entrada do Gmail e do Outlook.

**Como corrigir:**
- **Supabase:** Authentication → Emails → SMTP Settings → servidor do provedor (ex.: `smtp.resend.com`, porta 465). Personalize os templates em português.
- **DNS** (no Registro.br, Cloudflare etc.): o registro SPF/DKIM que o provedor mostrar, mais `_dmarc.seudominio.com.br TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@seudominio.com.br"`.
- Teste com um envio real para o Gmail e confira em "Mostrar original" que SPF, DKIM e DMARC estão como PASS.

## P07 · LGPD, privacidade e termos

**O que é:** quem coleta dado pessoal no Brasil precisa dizer o que coleta e por quê, ter base legal, permitir que o titular exerça os direitos dele e pedir consentimento quando a base legal é consentimento (cookie de marketing, por exemplo).

**Sinais:** `sem_politica_de_privacidade`, `link_legal_sem_pagina`, `rastreador_sem_consentimento`, `sem_exclusao_de_conta`; sinais `paginas_legais`, `links_sem_pagina`, `rastreadores`, `consentimento_em`.

O scanner separa página que existe (arquivo de página, rota declarada ou link externo para o texto) de link para página. `link_legal_sem_pagina` é o cadastro que pede "li e aceito os Termos" com link para `/termos` sem nenhuma página ou rota com esse nome: o link dá 404 e o aceite não vale. Confirme abrindo o link no app: rota montada por constante (`path: ROTAS.TERMOS`) o scanner não enxerga.

**FALHA:** app com cadastro e sem política de privacidade (LGPD art. 9º: informação clara sobre o tratamento); aceite de termos ou de política que leva a uma página inexistente (art. 9º, § 1º: o consentimento é nulo se a informação não foi apresentada antes, com transparência); Meta Pixel ou Google Analytics/Ads carregando antes de qualquer consentimento em site que usa a base legal de consentimento.
**ATENÇÃO:** sem termos de uso; sem canal do titular (e-mail do encarregado/DPO); sem como excluir a conta e os dados (art. 18); dado sensível (saúde, biometria) sem base legal específica (art. 11); venda online sem a informação do direito de arrependimento de 7 dias (CDC art. 49).
**OK:** política e termos acessíveis no rodapé e no cadastro, banner de cookies que bloqueia rastreador até o aceite (Consent Mode v2 no Google), canal do titular e exclusão de conta funcionando.

**Como corrigir:**
- Páginas `/privacidade` e `/termos` no rodapé e com link no cadastro.
- Banner de consentimento: `vanilla-cookieconsent`, Cookiebot ou CookieHub, com o Google Consent Mode v2.
- Rota de exclusão que apaga ou anonimiza os dados do usuário (e no Supabase, `auth.admin.deleteUser` no servidor).
- Sem promessa jurídica no texto: a política descreve o que o app faz de verdade. Peça revisão de um advogado quando houver dado sensível.

## P08 · SEO e compartilhamento

**O que é:** o site aparece no Google e o link compartilhado no WhatsApp ou LinkedIn sai com título, descrição e imagem certos.

**Sinais:**
- scan: `titulo_padrao_de_template` (ex.: "Lovable App", "Vite + React", "Create Next App", "Lovable Generated Project"), `noindex_no_codigo`, `robots_bloqueia_tudo`, `sem_open_graph`, `lang_en_em_site_pt`, `favicon_padrao`;
- `check_url.py`: `noindex_em_producao`, `sem_og_image`, `sem_meta_description`, `sem_sitemap`, `soft_404`, `variante_www_fora_do_ar`.

**FALHA:** `noindex` ou `robots.txt` com `Disallow: /` em produção (o site não entra no Google; costuma ser sobra de staging); título ou imagem de compartilhamento do template.
**ATENÇÃO:** sem og:image ou meta description; `lang="en"` em site em português; sem sitemap; SPA respondendo 200 para página inexistente; `www` ou o domínio sem `www` fora do ar.
**OK:** título e descrição próprios por página, og:image 1200×630, `lang="pt-BR"`, sitemap enviado ao Google Search Console, robots liberando produção.

**Como corrigir:**
- **Next.js:** `export const metadata = { title, description, openGraph: { images: ['/og.png'] } }` no `app/layout.tsx` e por página, mais `app/sitemap.ts` e `app/robots.ts`.
- **Vite/SPA** (Lovable/Bolt): edite o `index.html` (title, description, og:title, og:description, og:image, `lang="pt-BR"`). Para várias páginas, pré-renderize (`vite-plugin-prerender`) ou migre as páginas públicas para SSR/SSG.
- Remova o `noindex` do ambiente de produção (deixe só no preview).
- Cadastre o domínio no Google Search Console.

## P09 · Performance e experiência

**O que é:** a página abre rápido no 4G e funciona no celular, e o erro e o "não encontrado" têm tela própria.

**Sinais:**
- scan: `imagens_pesadas`, `sem_viewport`, `sem_pagina_404`;
- `check_url.py`: `resposta_lenta`, `sem_compressao`, `javascript_pesado`, `assets_sem_cache`, `soft_404`.

**FALHA:** sem meta viewport (o celular abre a versão de desktop); primeira página com vários MB de imagem.
**ATENÇÃO:** JS acima de ~1,5 MB na primeira página; resposta acima de ~1,8 s; HTML sem compressão; assets sem cache longo; sem 404 própria.
**OK:** LCP abaixo de 2,5 s no PageSpeed Insights (celular), imagens em WebP/AVIF com tamanho certo, compressão e cache ativos, 404 e tela de erro próprias.

**Como corrigir:**
- Converta as imagens (`npx sharp-cli` ou squoosh) e use `<img loading="lazy" width height>` ou `next/image`.
- Divida o código por rota (`React.lazy`, import dinâmico).
- Ative compressão no servidor ou CDN.
- Rode `https://pagespeed.web.dev` no celular e cole o resultado no relatório (ação manual).

## P10 · Custos e limites de gasto

**O que é:** um pico de uso, um bot ou um loop não vira uma fatura impagável.

**Sinais:** `ia_sem_max_tokens`, `cron_a_cada_minuto`; nas checagens de segurança, `ia_sem_rate_limit` e `next_image_wildcard` (C11).

**FALHA:** chamada de IA sem rate limit (C11) e sem limite de gasto no provedor.
**ATENÇÃO:**
- sem `max_tokens` nas chamadas de IA;
- sem alerta de orçamento na nuvem;
- plano com cobrança por uso sem teto (Vercel sem Spend Management, Supabase sem spend cap, Firebase Blaze sem alerta);
- cron muito frequente.

**OK:** limite e alerta de gasto configurados em cada provedor pago, teto de tokens por requisição e cota por usuário.

**Onde conferir (ação manual):**
- **OpenAI:** Settings → Limits (orçamento mensal e alertas).
- **Anthropic:** Console → Limits (spend limit).
- **Google Cloud/Firebase:** Billing → Budgets & alerts.
- **Vercel:** Settings → Billing → Spend Management.
- **Supabase:** Organization → Billing → Spend cap.
- **AWS:** Budgets.
- **Cloudflare:** notificações de uso.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
