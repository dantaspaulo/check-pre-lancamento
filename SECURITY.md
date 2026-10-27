# Segurança da própria skill

A skill é feita para ler código com segredos, por isso ela mesma segue regras rígidas:

- roda localmente, sem telemetria;
- nunca imprime uma chave inteira (mascaramento em `scan.json`, `url.json`, relatórios e no `show.py`);
- não escreve fora de `check-report/` durante a auditoria;
- no site, faz só requisições normais e só no domínio indicado pelo usuário;
- a sondagem de dados (`--sondar-dados`) só lê, só roda quando o dono do app autoriza e, no Supabase, pede apenas a contagem de linhas.

## Achou uma falha na skill?

Exemplos: um segredo que escapa do mascaramento, um script que escreve onde não devia, uma requisição que não é passiva.

Não abra issue pública. Mande os detalhes para **contato@paulosdantas.adv.br** ou use **Security → Report a vulnerability** aqui no GitHub. A resposta vem em até 5 dias úteis, e a correção sai num release com o crédito para quem reportou, se a pessoa quiser.

Falso positivo, falso negativo ou sugestão de regra nova podem ir em issue normal.
