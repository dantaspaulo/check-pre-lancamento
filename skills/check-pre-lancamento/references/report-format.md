<!-- check-pre-lancamento · Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição v1.0 (LICENSE.txt) · CPL-PSD-2026 -->
# Formato do `findings.json` e como escrever as correções

`render_report.py` lê este arquivo e gera `RELATORIO.md` e `CORRECOES.md`. Ele recusa o JSON se faltar alguma das 20 checagens, algum dos 10 itens de prontidão (quando o bloco `prontidao` existe) ou algum campo obrigatório.

## Esquema

```json
{
  "projeto": "nome do app",
  "data": "AAAA-MM-DD",
  "stack": "Next.js 15 (App Router) + Supabase + Vercel",
  "escopo": "repo completo (branch main) + https://meuapp.com.br",
  "resumo_executivo": "2-3 frases: o estado geral e o que mais importa agora.",
  "limitacoes": "o que não foi possível verificar e por quê (opcional)",
  "decisoes_pendentes": ["pergunta de produto que muda várias correções (opcional)"],
  "preparacao": ["o que precisa estar pronto antes da Task 1, ex.: projeto buildando (opcional)"],
  "acoes_manuais": ["ação manual que não pertence a uma checagem específica (opcional)"],
  "cobertura": ["o que foi olhado e o que ficou de fora, uma linha por item (recomendado)"],
  "prompts": ["PA04", "PA08"],
  "pasta_relatorio": "check-report",
  "comando_scan": "python3 ~/.claude/skills/check-pre-lancamento/scripts/scan.py . --out check-report/scan.json",
  "checks": [
    {
      "id": "C01",
      "status": "FALHA",
      "severidade": "CRITICO",
      "resumo": "uma frase: o que encontrei (ou por que está OK/N/A)",
      "evidencias": ["arquivo:linha — descrição sem o valor do segredo"],
      "arquivos": ["caminhos que a correção vai tocar"],
      "risco": "o que um atacante consegue fazer, 1-2 frases",
      "correcao": "markdown curto com o que fazer, com código da stack do projeto",
      "prompt": "instrução autocontida para o Claude Code aplicar a correção",
      "criterios_aceite": ["condição verificável 1", "condição verificável 2"],
      "depende_de": ["C06"],
      "acao_manual": "o que o humano precisa fazer fora do código (opcional)"
    }
  ],
  "prontidao": [
    { "id": "P06", "status": "FALHA", "severidade": "ALTO", "resumo": "...", "risco": "...", "correcao": "...", "prompt": "...",
      "acao_manual": "Supabase → Authentication → SMTP Settings: configurar o provedor" }
  ]
}
```

O bloco `prontidao` usa os mesmos campos de `checks`, com ids `P01` … `P10` (critério em `references/prontidao.md`). Ele é opcional para o script, mas a skill sempre preenche os 10: quando o bloco existe, todos entram, com `NA` e resumo para o que não se aplica.

| Campo | Obrigatório | Valores |
|---|---|---|
| `id` | sempre | `C01` … `C20` |
| `status` | sempre | `FALHA`, `ATENCAO`, `OK`, `NA` (não existe no app), `NAO_AVALIADO` (não foi olhado) |
| `severidade` | opcional (padrão = base) | `CRITICO`, `ALTO`, `MEDIO`, `BAIXO` — severidade efetiva |
| `resumo` | sempre | 1 frase. Em OK/N/A, diga a evidência ou o motivo |
| `risco`, `correcao`, `prompt` | FALHA e ATENCAO | texto/markdown |
| `evidencias`, `arquivos`, `criterios_aceite` | recomendados em FALHA/ATENCAO | listas de strings |
| `depende_de` | quando houver | IDs de checagens que precisam ser corrigidas antes desta |
| `acao_manual` | quando houver | texto |

Campos de topo opcionais: `decisoes_pendentes` aparece no relatório antes do plano e no `CORRECOES.md` como "pergunte antes de começar"; `preparacao` vira a Task 0; `acoes_manuais` entra no checklist manual.

- **`cobertura`**: inclua o que o scanner deixou fora das regras de código (`scan.json → cobertura_do_scan` e a linha "Fora das regras de código" em `avisos`): pastas do `.gitignore`, pastas fora do build (`docs/`, `examples/`) e o que veio de `--ignorar`. Exemplo: "fora das regras de código: arquivos-locais/ e .ds-sync/ (.gitignore), docs/ (fora do build); segredos procurados também em docs/".
- **`prompts`**: os IDs da biblioteca `references/prompts-pos-analise.md` que vão no fim do `RELATORIO.md`, na ordem. Sem o campo, o `render_report.py` escolhe sozinho pelos itens abertos (até 4 mais o PA14, de conferir de novo).
- **Cuidados automáticos:** se `correcao` ou `prompt` trouxer GRANT ou REVOKE em massa (`on all tables`, `on all functions`), `disable row level security`, `drop table` ou `truncate`, o relatório e o plano ganham um aviso de cuidado logo abaixo. Prefira escrever a correção objeto por objeto, para o aviso nem precisar aparecer.

**Notas** (calculadas pelo script, uma de segurança e uma de prontidão):
- Cada item pesa pela severidade **efetiva**: CRÍTICO 10, ALTO 6, MÉDIO 3, BAIXO 1.
- OK conta 100%, ATENÇÃO 50%, FALHA 0%. N/A e NÃO AVALIADO saem da conta (sem nada avaliado, a nota aparece como "—"). OK/N/A sem `severidade` usa a base.
- Há um teto para a nota não contradizer o veredito: com falha crítica, no máximo 49; com falha alta ou atenção crítica, no máximo 79.

**Ordem das tasks:** primeiro segurança, depois prontidão. Dentro de cada bloco: severidade efetiva → FALHA antes de ATENÇÃO → ID, sempre respeitando `depende_de`.

**Veredito:**
- 🔴 qualquer FALHA de segurança com severidade efetiva CRÍTICO;
- 🟡 FALHA de segurança ALTO, ATENÇÃO de segurança CRÍTICO, ou FALHA de prontidão ALTO/CRÍTICO;
- ⚪ AVALIAÇÃO PARCIAL quando alguma checagem de segurança ficou `NAO_AVALIADO` (ou todas são N/A): não libera o lançamento;
- 🟢 o resto.

**Rodapé e marca de autoria:** os dois arquivos saem com a marca da skill (comentário na primeira linha e rodapé com crédito). Faz parte da licença. Não remova.

## Exemplos de entradas

FALHA bem escrita:

```json
{
  "id": "C04",
  "status": "FALHA",
  "severidade": "CRITICO",
  "resumo": "Tabela orders criada sem RLS e policy de update em profiles com using (true).",
  "evidencias": [
    "supabase/migrations/20260101_init.sql:14 — create table public.orders (sem enable row level security)",
    "supabase/migrations/20260101_init.sql:31 — policy \"update profiles\" for update using (true)"
  ],
  "arquivos": ["supabase/migrations/"],
  "risco": "Qualquer visitante, com a anon key que está no site, lê e altera todos os pedidos e edita o perfil de qualquer usuário (inclusive o campo role).",
  "correcao": "Criar migration que liga RLS em `orders` e troca as policies por regras de dono (`auth.uid() = user_id`). Ver código abaixo.\n\n```sql\nalter table public.orders enable row level security;\ncreate policy orders_select_own on public.orders for select to authenticated using ((select auth.uid()) = user_id);\n```",
  "prompt": "Crie a migration supabase/migrations/<timestamp>_rls_hardening.sql que: (1) faz `alter table public.orders enable row level security`; (2) cria policies de select/insert/update/delete em orders restritas a `(select auth.uid()) = user_id`; (3) remove a policy \"update profiles\" e cria `profiles_update_own` com using e with check `(select auth.uid()) = id`; (4) faz `revoke update on public.profiles from authenticated` e `grant update (name, avatar_url) on public.profiles to authenticated` para impedir alteração de role. Não aplique no banco: só gere o arquivo. Depois, liste as telas do app que leem orders e confirme que todas usam o cliente autenticado (não o admin).",
  "criterios_aceite": [
    "Toda tabela do schema public nas migrations tem enable row level security",
    "Nenhuma policy de escrita com using (true) ou with check (true)",
    "Usuário autenticado não consegue alterar a coluna role"
  ],
  "acao_manual": "Aplicar a migration no projeto Supabase (supabase db push ou SQL Editor) e rodar a query de verificação de RLS do checks.md."
}
```

OK e N/A:

```json
{ "id": "C10", "status": "OK", "resumo": "Senhas gerenciadas pelo Supabase Auth (bcrypt); o app não armazena senha própria." }
{ "id": "C16", "status": "NA", "resumo": "O app não tem upload de arquivos." }
```

ATENÇÃO (não verificável daqui):

```json
{
  "id": "C11",
  "status": "ATENCAO",
  "severidade": "ALTO",
  "resumo": "Nenhum rate limit no código; usuário disse que usa Cloudflare, mas não há evidência de regra de rate limiting.",
  "risco": "A rota /api/chat chama a OpenAI: sem limite, um script pode gerar milhares de requisições e estourar a fatura em horas.",
  "correcao": "Adicionar @upstash/ratelimit na rota /api/chat (10 req/min por usuário) e/ou regra de Rate Limiting no Cloudflare para /api/*.",
  "prompt": "...",
  "acao_manual": "Confirmar no painel Cloudflare → Security → WAF → Rate limiting rules se existe regra para /api/*."
}
```

## Como escrever o `prompt` de correção

Quem executa é um Claude Code numa sessão nova, que não viu esta auditoria. O prompt precisa funcionar sozinho:

1. **Onde**: arquivos e linhas exatos (ou a pasta e o padrão de busca, se forem muitos).
2. **O quê**: a mudança concreta, com nomes reais de funções, variáveis e libs do projeto. Se precisar instalar lib, diga qual.
3. **Restrições**: não quebrar a interface da rota, não renomear tabela, não commitar segredo, não aplicar migration em produção, etc.
4. **Como verificar**: build/testes, um teste manual (`curl` sem cookie deve dar 401), ou uma busca que precisa voltar vazia (`grep -r "dangerouslyAllowBrowser" src/` vazio).
5. **O que não é dele**: se houver parte manual (rotacionar chave, mexer no painel), diga explicitamente para listar ao humano e não tentar fazer.

Ruim: "Corrija a exposição da API key."

Bom: "Em `src/components/Chat.tsx` o SDK da OpenAI é instanciado no navegador com `dangerouslyAllowBrowser: true` usando `NEXT_PUBLIC_OPENAI_API_KEY`. Crie `app/api/chat/route.ts` (runtime nodejs) que recebe `{ message: string }`, valida com zod (máx. 4.000 caracteres), exige usuário autenticado via `createClient()` de `@/lib/supabase/server` + `auth.getUser()` (401 se não houver) e chama a OpenAI com `process.env.OPENAI_API_KEY`. Troque a chamada em `Chat.tsx` por `fetch('/api/chat')`. Renomeie a variável para `OPENAI_API_KEY` em `.env.local` e `.env.example` (sem valor no example). Verifique: `grep -rn \"NEXT_PUBLIC_OPENAI\\|dangerouslyAllowBrowser\" src app` vazio e `npm run build` passando. Não tente rotacionar a chave — isso é ação manual do humano."

## Tom

- Direto, sem alarmismo e sem jargão desnecessário: o leitor pode ser um founder que fez o app com IA.
- Explique o risco pelo efeito ("qualquer um lê todos os pedidos"), não pela sigla ("IDOR").
- Sem elogio vazio. Se algo está bem feito, o resumo do OK basta.

---
<sub>check-pre-lancamento · por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento · Licença de Uso com Atribuição</sub>
