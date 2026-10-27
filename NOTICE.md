# Aviso de autoria

**check-pre-lancamento** foi criada por **Paulo Sérgio Dantas**.

- Repositório oficial: https://github.com/dantaspaulo/check-pre-lancamento
- Impressão da obra: `CPL-PSD-2026`
- Licença: [Licença de Uso com Atribuição v1.0](LICENSE)

## Como dar o crédito

Ao compartilhar, mostrar num vídeo, num post ou numa aula, use:

> check-pre-lancamento, skill de Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento

Ao redistribuir uma cópia ou uma versão modificada (o que a licença só permite de graça), coloque no início da descrição:

> Baseado em check-pre-lancamento, de Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento

## O que não pode sair

Os avisos de autoria fazem parte da licença e precisam continuar em toda cópia:

1. As linhas `Copyright` e `Aviso obrigatório` no topo de cada script e de cada referência.
2. Os metadados `author`, `repository` e `fingerprint` do `SKILL.md`.
3. O manifesto `AUTORIA.json`, que tem o hash de cada arquivo da versão oficial.
4. O rodapé de crédito dos relatórios (`RELATORIO.md` e `CORRECOES.md`) e das saídas dos scripts.
5. As verificações de autoria: o `render_report.py` se recusa a gerar relatório quando os créditos foram trocados, e o `scan.py` avisa quando a cópia perdeu os créditos.

## Como saber se a sua cópia é a oficial

```bash
python3 skills/check-pre-lancamento/scripts/autoria.py
```

O script compara cada arquivo com o manifesto da versão publicada e diz se a cópia é oficial, se foi modificada ou se perdeu os créditos. Nada sai da sua máquina.

## Como achar cópias

A impressão `CPL-PSD-2026` está em todos os arquivos. Uma busca no GitHub mostra onde mais ela aparece:
[github.com/search?q="CPL-PSD-2026"&type=code](https://github.com/search?q=%22CPL-PSD-2026%22&type=code).
Quem apaga a impressão costuma esquecer os textos. Busque também por uma frase própria das referências, por exemplo
[`"Prontidão para o lançamento (10 itens)"`](https://github.com/search?q=%22Prontid%C3%A3o+para+o+lan%C3%A7amento+%2810+itens%29%22&type=code).

## Viu uma cópia sem crédito ou sendo vendida?

Mande o link para **contato@paulosdantas.adv.br**. A versão oficial é gratuita e fica só neste repositório.
