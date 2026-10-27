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
| PA16 | Duas requisições ao mesmo tempo | engenharia: estoque, vaga, cupom, crédito ou saldo |
| PA17 | Webhook e pagamento que aguentam repetição | engenharia: C06 com webhook ou pagamento |
| PA18 | Regra de negócio que o navegador decide | engenharia: C07 ou C08 |
| PA19 | Testes de integração nos fluxos que não podem quebrar | engenharia: P04, antes de mudança grande |
| PA20 | Dividir um arquivo grande sem mudar o que o app faz | engenharia: depois do PA19 |
| PA21 | Raio-x de engenharia, sem alterar nada | engenharia: para escolher por onde começar |

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

## Engenharia: depois do lançamento

Os prompts PA16 a PA21 vão além das 30 checagens. Eles tratam de defeitos que aparecem cedo em app feito rápido com IA: pedido duplicado, webhook processado duas vezes, regra que o navegador decide e mudança que quebra outra coisa sem ninguém ver. Os temas vieram de uma sugestão de usuário, a partir de um material de @manodeyvin; os textos foram escritos para esta skill.

Antes de colar qualquer um deles:
- trabalhe numa branch separada, se o projeto usa git;
- leia o plano que o agente propõe antes de deixar ele mexer;
- toda migration passa pelos seus olhos antes de rodar, e teste nenhum encosta no banco de produção;
- se não entendeu o que o prompt vai fazer, pergunte ao agente antes de colar.

Ordem sugerida: PA21 (raio-x, só leitura) → PA19 (testes, para travar o comportamento de hoje) → PA18 (regra no navegador) → PA16 e PA17 (corrida e repetição, onde mora o dinheiro) → PA20 (dividir arquivo grande, com os testes já protegendo).

## PA16 · Duas requisições ao mesmo tempo
<!-- quando: engenharia -->
**Quando usar:** o app vende, reserva ou consome algo limitado (estoque, vaga, cupom, crédito, convite, saldo). Clique duplo, duas abas abertas ou o celular reenviando não podem virar dois pedidos.

```text
Quero saber se o app aguenta a mesma ação chegando duas vezes ao mesmo tempo (clique duplo, duas abas, o celular reenviando).
1. Se não estiver claro no código, me pergunte o que é limitado neste app: estoque, vagas, cupons, créditos, saldo, convites. Depois liste, com arquivo e linha, cada ponto em que esse recurso é conferido e em seguida alterado.
2. Antes de corrigir, escreva para cada ponto um teste que dispara as duas chamadas em paralelo e mostra o estrago (dois pedidos, saldo negativo, cupom usado duas vezes). Rode e me mostre falhando.
3. A correção fica no banco, que é quem enxerga as duas chamadas: restrição única; ou uma instrução só que confere e altera junto, olhando quantas linhas mudaram; ou transação que trava a linha. Nada de infraestrutura nova para isso (Redis, fila, trava em memória): se achar que o banco não resolve, me convença antes.
4. Rode os testes de novo e me mostre passando. Travar o botão na tela é conforto para o usuário, não proteção.
Me mostre o plano antes de mexer e cada migration antes de rodar. Se a restrição única esbarrar em registros duplicados que já existem, liste-os para mim e pare: não apague nada.
```

## PA17 · Webhook e pagamento que aguentam repetição
<!-- quando: C06,C08 se webhook|pagamento|checkout|stripe|assinatura · engenharia -->
**Quando usar:** o app recebe webhook de pagamento (Stripe, Mercado Pago, Asaas, Efí, Pagar.me) ou cobra, libera plano ou credita saldo. O gateway reenvia o mesmo evento, e o segundo envio não pode liberar o plano de novo.

```text
O gateway de pagamento reenvia webhook quando não recebe resposta a tempo, às vezes fora de ordem e às vezes em dobro. Quero ter certeza de que nada acontece duas vezes por causa disso.
1. Monte uma tabela com cada webhook que o app recebe (arquivo e linha) e estas colunas: a assinatura é conferida com o corpo bruto antes de qualquer outra coisa? Um evento repetido é barrado por restrição única no id do evento? O app consulta o gateway para saber o estado atual, em vez de confiar na ordem de chegada? Ele responde 2xx rápido e deixa o trabalho pesado para depois?
2. Faça a mesma conferência nas rotas que cobram, liberam plano, creditam saldo ou mandam e-mail de compra: um clique repetido cria a segunda cobrança?
3. Corrija o que faltar. Nas chamadas que o app faz ao gateway, use a chave de idempotência dele, criada uma vez por operação e reaproveitada na nova tentativa. A chave nunca é e-mail, CPF ou outro dado da pessoa.
4. Escreva testes que entregam o mesmo evento duas vezes, uma depois da outra e as duas juntas, e provam que o efeito (plano liberado, crédito, e-mail) aconteceu uma vez só.
Não mexa em preço, plano nem regra de cobrança. Me mostre a tabela e o plano antes de alterar código.
```

## PA18 · Regra de negócio que o navegador decide
<!-- quando: C07,C08 · engenharia -->
**Quando usar:** o relatório marcou controle de acesso ou mass assignment, ou o app calcula preço, desconto, frete, limite de plano ou permissão na tela.

```text
Tudo o que roda no navegador o usuário consegue ler e mudar: pelo DevTools ou chamando a API direto. Quero achar o que o app decide no lado errado.
1. Liste o que é calculado ou decidido só no front: preço, desconto, frete, total do carrinho, limite do plano, papel de admin, botão que aparece só para quem pode e validação de formulário. Para cada item, diga se o servidor confere de novo ou aceita o valor que chega do navegador.
2. Para cada item que o servidor aceita, me mostre como alguém mudaria o resultado (o corpo da requisição alterado, a chamada feita direto na API).
3. Leve a decisão para o servidor (rota de API, Server Action ou Edge Function): ele recalcula a partir do que está no banco e ignora o valor do cliente. A tela continua calculando, mas só para mostrar.
4. Campos que o usuário não pode mudar (papel, plano, saldo, status de pagamento) só mudam pelo servidor: confira também o banco e as policies.
5. Teste cada correção mandando o valor adulterado direto para a rota e provando que o servidor ignora.
Primeiro me entregue a lista. Depois corrija um item por vez, com o meu OK em cada um.
```

## PA19 · Testes de integração nos fluxos que não podem quebrar
<!-- quando: P04 · engenharia -->
**Quando usar:** o app não tem testes (P04) ou você vai pedir à IA uma mudança grande. É a rede de segurança: avisa na hora quando algo quebrou, antes do cliente.

```text
Quero uma rede de segurança antes de pedir mudanças maiores: testes que passam pelas rotas de verdade e por um banco de teste, para eu saber na hora quando algo quebrou.
1. Leia o check-report/RELATORIO.md e o código e escolha os 3 a 5 fluxos que mais doem se quebrarem (normalmente cadastro e login, pagamento, e o que mostra ou altera dado de cliente). Me diga quais escolheu e por quê.
2. Para cada fluxo, monte uma tabela com duas colunas: "o que tem que acontecer" e "o que nunca pode acontecer" (por exemplo: cobrar duas vezes, outra conta ver o pedido, entrar sem confirmar o e-mail). Espere eu revisar: essa tabela é a especificação.
3. Use a ferramenta de teste que o projeto já tem; se não houver, proponha uma e espere o meu OK. Os testes rodam contra um banco separado (Supabase local, container ou projeto de teste), nunca contra produção. Só o que é de fora (gateway, e-mail, APIs de terceiros) é simulado; o banco e a regra testada, nunca.
4. Cada linha da tabela vira um teste. Inclua sempre um caso com duas chamadas simultâneas e um com a conta errada.
5. Rode e me mostre o resultado. Se um teste falhar porque o código está errado, ele continua falhando e o problema vai para o check-report/CORRECOES.md; se o teste estiver errado, me pergunte antes de mudá-lo. Nunca apague nem desligue teste para a suíte ficar verde.
No fim, me diga o comando que roda tudo e coloque esse comando no CI, se o projeto tiver.
```

## PA20 · Dividir um arquivo grande sem mudar o que o app faz
<!-- quando: engenharia -->
**Quando usar:** existe aquele arquivo que ninguém quer abrir, e cada mudança nele quebra outra coisa. Rode depois do PA19.

```text
O arquivo [CAMINHO DO ARQUIVO] cresceu demais e qualquer mudança nele quebra outra coisa. Quero dividi-lo sem mudar o que o app faz.
1. Antes de mover qualquer linha, garanta que existe teste do comportamento atual desse arquivo. Se não houver, escreva testes que registram o que ele faz hoje, mesmo o que parecer errado (o PA19 ajuda nisso).
2. Separe o conteúdo em três grupos: o que é tela e reação do usuário, o que é regra (cálculo, validação, decisão) e o que fala com o banco ou com serviço de fora. Aponte também o que está duplicado e o que depende de estado global.
3. Proponha a nova divisão de arquivos no padrão que o projeto já usa, sem lib nova.
4. Faça em passos pequenos: cada passo move um pedaço e termina com os testes passando. O que outros arquivos, o banco ou quem chama a API enxergam (nomes de rotas, props e colunas) continua igual.
Bug que aparecer no caminho você anota numa lista e não corrige agora. Espere o meu OK no plano antes do primeiro passo.
```

## PA21 · Raio-x de engenharia, sem alterar nada
<!-- quando: engenharia -->
**Quando usar:** para saber por qual dos PA16 a PA20 começar. Só lê o código.

```text
Quero um raio-x de engenharia do app sem mudar nada: nesta tarefa você só lê o código e roda comandos que não alteram nada (nada de instalar, migrar ou gravar em banco).
Responda com arquivo e linha:
1. Testes: existe suíte? Ela chama as rotas de verdade ou testa funções soltas com tudo simulado? Usa um banco separado do de produção? Quais fluxos de dinheiro e de permissão estão sem teste?
2. Decisão no navegador: preço, desconto, limite de plano ou permissão que o servidor não confere de novo.
3. Corrida: pontos que leem, decidem e gravam um recurso limitado sem proteção no banco.
4. Repetição: webhook sem conferência de assinatura ou sem barreira para evento repetido, e chamada ao gateway sem chave de idempotência.
5. Arquivos que misturam tela, regra e banco, com o maior candidato a dividir.
Grave em check-report/ENGENHARIA.md uma tabela por tema (achado, risco alto, médio ou baixo, arquivo e linha, correção sugerida), com os 5 piores no topo. O que não deu para olhar vai numa seção "Não verificado", com o motivo. Termine com a ordem em que rodar o PA16 a PA20 neste projeto.
```

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
