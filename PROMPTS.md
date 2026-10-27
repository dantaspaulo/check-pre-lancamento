<!-- Gerado por tools/build.py a partir de skills/check-pre-lancamento/references/prompts-pos-analise.md. Edite lá e rode python3 tools/build.py. -->
<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Prompts para depois da análise

Prompts prontos para colar no agente (Claude Code, claude.ai, Codex, Cursor, Copilot, Gemini, Lovable, Bolt, Replit) depois que o check gerou a pasta `check-report/` com `RELATORIO.md`, `CORRECOES.md` e `findings.json`. Cada um funciona sozinho: o agente que for executar não precisa ter visto a análise.

- **Claude Code, Codex, Cursor e outros com acesso à pasta:** abra o agente na raiz do projeto e cole o prompt.
- **claude.ai, Lovable, Bolt e outros chats:** anexe ou cole o `RELATORIO.md` e o `CORRECOES.md` antes do prompt.
- O `RELATORIO.md` já traz no fim os prompts que combinam com o que foi achado. Esta é a lista completa.

| | Prompt | Quando usar |
|---|---|---|
| PA01 | Resolver primeiro o que impede o lançamento | veredito 🔴, falha crítica |
| PA02 | Rotacionar chaves vazadas | C01 ou C02 com falha |
| PA03 | Corrigir na ordem, uma task por vez | qualquer item aberto |
| PA04 | Revisar as permissões do Supabase, tabela por tabela | C03, C04 ou C07 com Supabase |
| PA05 | Regra fixa para o agente não reabrir o banco | C04 com Supabase |
| PA06 | Testar se um usuário vê dado de outro | C04, C06 ou C07 |
| PA07 | Fechar o cadastro: captcha, e-mail confirmado e senha forte | C10, C11 ou C12 |
| PA08 | Termos de Uso e Política de Privacidade | P07 |
| PA09 | Headers de segurança sem quebrar o site | C18 ou C19 |
| PA10 | Dependências vulneráveis sem quebrar o build | C20 |
| PA11 | Backup e teste de restauração | P03 |
| PA12 | Erro e queda avisando antes do usuário | P02 ou P05 |
| PA13 | Checklist do dia do lançamento | sempre, antes de lançar |
| PA14 | Conferir de novo e comparar com a análise anterior | depois de corrigir |
| PA15 | Explicar o relatório para quem não é técnico | sempre |

---

## PA01 · Resolver primeiro o que impede o lançamento
<!-- quando: critico -->
**Quando usar:** o veredito saiu 🔴 ou há falha crítica. Resolve hoje só o que derruba o lançamento.

```text
Leia check-report/RELATORIO.md e check-report/CORRECOES.md. Hoje quero resolver só o que impede o lançamento: os itens 🔴 Críticos e as ações urgentes fora do código.
1. Liste esses itens em ordem de risco, cada um com uma frase dizendo o que um atacante consegue fazer.
2. Para cada chave exposta, me passe o passo a passo para gerar uma nova e revogar a antiga no painel do provedor. Eu faço essa parte: você não toca em chave real e nunca escreve o valor de uma chave no chat, em código ou em commit.
3. Corrija no código só esses itens, um por vez, seguindo as regras do topo do CORRECOES.md. Depois de cada um, rode build e testes e me mostre a prova de que fechou.
Não mexa em ATENÇÃO nem em prontidão agora. Se uma correção depender de decisão minha, pare e pergunte.
```

## PA02 · Rotacionar chaves vazadas
<!-- quando: C01,C02 -->
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

## PA03 · Corrigir na ordem, uma task por vez
<!-- quando: abertos -->
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

## PA04 · Revisar as permissões do Supabase, tabela por tabela
<!-- quando: C03,C04,C07 se supabase -->
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

## PA05 · Regra fixa para o agente não reabrir o banco
<!-- quando: C04 se supabase -->
**Quando usar:** depois de arrumar as permissões, para que a próxima tabela criada por IA não volte a abrir o banco. A partir de 30/10/2026 o Supabase não dá mais GRANT automático para tabela nova no public, e a "correção" mais comum do erro 42501 é o GRANT em massa.

```text
Adicione ao arquivo de instruções do agente deste projeto (CLAUDE.md, AGENTS.md ou o equivalente da ferramenta) uma seção "Banco de dados: permissões" com estas regras, adaptadas ao projeto:
- Toda tabela nova nasce na migration com GRANT só para o papel que precisa (nunca "on all tables"), RLS ligada e policies que checam o dono (auth.uid()) ou a organização. Policy de insert e update tem with check.
- Erro 42501 ou "permission denied" não se corrige com GRANT em massa: diga qual papel e qual tabela precisam de acesso e peça confirmação.
- Nunca "grant execute on all functions". Função SECURITY DEFINER nova sai com set search_path = '' e com EXECUTE revogado de public e de anon.
- View nova sai com security_invoker = true.
- Antes de mudar permissão, salvar o estado atual. Depois, testar com visitante sem login e com duas contas diferentes.
Mostre o texto antes de salvar.
```

## PA06 · Testar se um usuário vê dado de outro
<!-- quando: C04,C06,C07 -->
**Quando usar:** o relatório marcou auth no servidor, controle de acesso ou RLS. É a prova de que o dado de um cliente não aparece para outro.

```text
Quero confirmar que um usuário não consegue ver nem alterar dado de outro.
1. Use só o ambiente local ou de staging, com duas contas de teste criadas para isso. Nunca use conta de cliente real nem o banco de produção.
2. Liste as rotas, Server Actions, Edge/Cloud Functions e tabelas que recebem um id (pedido, documento, perfil, arquivo).
3. Para cada uma, escreva um teste automatizado em que a conta A tenta ler, editar e apagar o recurso da conta B. O teste passa só se receber 403/404 ou zero linhas. Inclua também um visitante sem login.
4. Rode os testes e me mostre o resultado. O que falhar vira task no check-report/CORRECOES.md, com o arquivo e a linha.
```

## PA07 · Fechar o cadastro: captcha, e-mail confirmado e senha forte
<!-- quando: C10,C11,C12 -->
**Quando usar:** o cadastro e o login aceitam robô, e-mail falso ou senha fraca.

```text
Quero fechar o cadastro e o login contra robô e conta falsa, sem atrapalhar quem é de verdade.
1. Veja como funcionam hoje: o provedor de auth, as telas e a configuração (supabase/config.toml ou o painel do provedor).
2. Proponha: captcha (Cloudflare Turnstile ou hCaptcha) no cadastro, no login e no "esqueci a senha"; confirmação de e-mail obrigatória; senha com no mínimo 8 caracteres e checagem de senha vazada, se o provedor tiver; limite de tentativas.
3. Faça a parte do código: o widget, o envio do token para o provedor e a mensagem de erro amigável. Me liste a parte do painel com o caminho exato de cada opção.
4. Teste e me mostre: cadastro sem captcha falha, e conta com e-mail não confirmado não entra.
```

## PA08 · Termos de Uso e Política de Privacidade
<!-- quando: P07 -->
**Quando usar:** faltam as páginas legais, ou o cadastro pede aceite de termos que não existem. Aceite de um texto que o titular não consegue ler não vale (LGPD, art. 9º, § 1º).

```text
Preciso das páginas de Termos de Uso e de Política de Privacidade antes de lançar.
1. Leia o código e liste, com arquivo e linha, todo dado pessoal que o app coleta (cadastro, formulários, uploads, analytics, cookies, integrações) e para onde cada um vai (banco, provedores, IA, e-mail, pagamento).
2. Com essa lista, escreva as duas páginas em português simples: quem é o controlador, quais dados, para quê, a base legal de cada tratamento, com quem compartilha, por quanto tempo guarda, os direitos do titular e como exercê-los. Deixe [NOME DA EMPRESA], [CNPJ], [ENDEREÇO] e [E-MAIL DO ENCARREGADO] para eu preencher. Não invente fato sobre a empresa.
3. Crie as rotas /termos e /privacidade no padrão do projeto, com link no rodapé e no cadastro. Se o cadastro tem caixa de aceite, registre a data e a versão do texto aceito.
4. Marque no topo das duas páginas: "Rascunho: revisar com advogado antes de publicar".
```

## PA09 · Headers de segurança sem quebrar o site
<!-- quando: C18,C19 -->
**Quando usar:** faltam headers, a CSP é fraca ou o HTTPS não é forçado.

```text
Quero ligar os headers de segurança sem quebrar o site.
1. Descubra onde o site é servido (Vercel, Netlify, Cloudflare, Nginx, servidor próprio) e onde os headers ficam nesse caso.
2. Adicione Strict-Transport-Security, X-Content-Type-Options, Referrer-Policy, Permissions-Policy e frame-ancestors (ou X-Frame-Options).
3. Monte a Content-Security-Policy a partir do que o site carrega de verdade (scripts, fontes, imagens, APIs, Supabase, analytics) e ligue primeiro como Content-Security-Policy-Report-Only. Me diga como ver as violações no console do navegador.
4. Depois de uma semana sem violação, troque para a CSP valendo. Confira com o check_url.py do check-pre-lancamento.
```

## PA10 · Dependências vulneráveis sem quebrar o build
<!-- quando: C20 -->
**Quando usar:** a auditoria de dependências acusou vulnerabilidade.

```text
Leia o C20 do check-report/RELATORIO.md e o bloco checks.C20.sinais.auditoria do check-report/scan.json.
1. Separe o que vai para produção (o navegador ou o servidor) do que só roda no build, nos testes ou no dev. npm audit --omit=dev mostra só o de produção.
2. Para cada vulnerabilidade de produção, diga a versão corrigida, se é atualização major e o que muda.
3. Atualize uma dependência por vez, com build e testes depois de cada uma. Nada de "npm audit fix --force" sem me mostrar antes o que ele vai trocar.
4. Pacote que só roda no build e está em dependencies: mova para devDependencies.
5. Ligue o Dependabot ou o Renovate, se ainda não tiver.
```

## PA11 · Backup e teste de restauração
<!-- quando: P03 -->
**Quando usar:** não está claro se dá para recuperar o banco se algo der errado.

```text
Quero ter certeza de que consigo recuperar o banco se algo der errado.
1. Descubra onde está o banco e qual backup existe hoje (plano do provedor, PITR, dump agendado). O que não der para ver no código, me pergunte.
2. Escreva o passo a passo para restaurar num banco novo, nunca o de produção, e um script de dump, se fizer sentido.
3. Me diga como testar a restauração uma vez antes do lançamento e o que conferir depois (contagem de linhas das tabelas principais, login de uma conta de teste).
Nada de comando que apague ou sobrescreva dados.
```

## PA12 · Erro e queda avisando antes do usuário
<!-- quando: P02,P05 -->
**Quando usar:** não há monitoramento de erros nem de uptime.

```text
Quero saber de um erro ou de uma queda em produção antes do usuário reclamar.
1. Proponha o mínimo: um serviço de erros (Sentry ou equivalente), uma rota /health e um monitor de uptime com alerta no meu e-mail ou celular.
2. Instale e configure no código: chave por variável de ambiente, sem dado pessoal nos eventos e source maps enviados de forma privada (não publicados).
3. Me liste o que eu preciso fazer nos painéis.
4. Gere um erro de teste e me mostre que ele chegou.
```

## PA13 · Checklist do dia do lançamento
<!-- quando: sempre -->
**Quando usar:** no dia de colocar no ar.

```text
Vou lançar o app. Monte o checklist do dia, curto e em ordem, a partir do check-report/RELATORIO.md e do que você vê no projeto: variáveis de ambiente de produção, chaves de produção (não as de teste), domínio e HTTPS, e-mail do domínio (SPF, DKIM e DMARC), SMTP próprio no envio de e-mail do login, backup ligado, monitor de erros e de uptime, limite de gasto nos provedores (IA, nuvem, banco), analytics e cookies, páginas legais, página 404 e plano para voltar a versão anterior.
Para cada item, diga como confirmar em um minuto e marque o que o relatório já confirmou e o que falta.
```

## PA14 · Conferir de novo e comparar com a análise anterior
<!-- quando: abertos -->
**Quando usar:** depois de aplicar as correções.

```text
Antes de tudo, copie check-report/findings.json para check-report/findings-anterior.json. Depois rode o check-pre-lancamento de novo neste projeto.
Com o relatório novo, me mostre:
1. as notas antes e depois;
2. o que fechou (com a prova), o que continua aberto e o que apareceu de novo;
3. se alguma correção abriu outro problema (por exemplo, permissão devolvida em massa ou rota que perdeu a checagem de login).
Não marque nada como OK sem evidência.
```

## PA15 · Explicar o relatório para quem não é técnico
<!-- quando: sempre -->
**Quando usar:** para mostrar a sócio, cliente ou gestor.

```text
Leia check-report/RELATORIO.md e me explique como se eu não fosse técnico: o que está em risco, o que alguém mal-intencionado conseguiria fazer, o que precisa ser feito antes de lançar e quanto tempo cada coisa leva, mais ou menos. Até 15 linhas, sem jargão. Termine com uma frase dizendo se dá para lançar e com qual condição.
```

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
