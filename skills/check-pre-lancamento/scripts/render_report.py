#!/usr/bin/env python3
# check-pre-lancamento · gera RELATORIO.md e CORRECOES.md
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
# Aviso obrigatório: mantenha estas linhas e os créditos de autoria em qualquer cópia ou derivado.
"""check-pre-lancamento · gera RELATORIO.md e CORRECOES.md a partir do findings.json.

Uso:
    python3 render_report.py check-report/findings.json [--out check-report/]

Calcula notas e veredito de forma determinística, ordena por prioridade e mascara
qualquer coisa com cara de segredo antes de escrever (defesa extra: o relatório
nunca deve carregar uma chave real). Esquema do JSON: references/report-format.md.
"""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    AUTORIA, CHECKS, CREDITO, PRONTIDAO, SELO_AUTORIA, SEVERITY_ICON, SEVERITY_LABEL, SEVERITY_ORDER, SEVERITY_WEIGHT,
    STATUS_LABEL, STATUS_VALUE, VERSION, mask_secrets, selo,
)

VALID_STATUS = {"OK", "ATENCAO", "FALHA", "NA", "NAO_AVALIADO"}
VALID_SEV = set(SEVERITY_WEIGHT)
SKILL_DIR = Path(__file__).resolve().parent.parent
ALL = {**CHECKS, **PRONTIDAO}
# Trava de autoria (LICENSE.txt, cláusula 3): o relatório só sai com os créditos originais.
_SELO = "cb6453268d4b63eae51cff76"
MARCA = f"<!-- {CREDITO} · {AUTORIA['impressao']} -->"


def trava_de_autoria():
    if not (selo() == SELO_AUTORIA == _SELO and AUTORIA["autor"] in CREDITO and AUTORIA["repositorio"].replace("https://", "") in CREDITO):
        sys.exit("Os créditos de autoria desta skill foram alterados ou removidos, o que a licença não permite.\n"
                 "Baixe a versão oficial e gratuita em https://github.com/dantaspaulo/check-pre-lancamento")


def norm_status(s):
    s = (s or "").upper().replace("Ç", "C").replace("Ã", "A").replace("/", "").replace(" ", "")
    s = s.replace("_", "")
    return {"ATENÇÃO": "ATENCAO", "N/A": "NA", "NAOSEAPLICA": "NA", "NAOAVALIADO": "NAO_AVALIADO", "NÃOAVALIADO": "NAO_AVALIADO"}.get(s, s)


def norm_sev(s):
    s = (s or "").upper().replace("Í", "I").replace("É", "E")
    return s


def fence(text, lang=""):
    longest = max([len(m) for m in re.findall(r"`{3,}", text)] + [2])
    f = "`" * (longest + 1)
    return f"{f}{lang}\n{text.strip()}\n{f}"


# Correções que costumam abrir outro buraco. Quando o texto da correção traz uma delas, o relatório e o plano
# ganham o aviso logo abaixo, para o agente que executar não precisar lembrar.
CUIDADOS = (
    (re.compile(r"grant\s+(?:all(?:\s+privileges)?|execute)\s+on\s+all\s+(?:functions|routines|procedures)\s+in\s+schema", re.I),
     "Esta correção devolve EXECUTE em todas as funções do schema: as internas, fechadas de propósito, voltam a abrir. "
     "Liste as funções que o app chama por rpc() e conceda só essas, uma a uma, só ao papel que chama."),
    (re.compile(r"grant\s+[\w\s,()]+?\s+on\s+all\s+tables\s+in\s+schema\s+[\w\s,]+?\s+to\s+[\w\s,\"]*\b(?:anon|authenticated|public)\b", re.I),
     "GRANT em todas as tabelas reabre também as privadas e as que ainda não têm RLS. Dê GRANT por tabela, só ao papel que precisa."),
    (re.compile(r"revoke\s+[\w\s,()]+?\s+on\s+all\s+(?:tables|functions|routines|procedures)\s+in\s+schema\s+[\w\s,]+?\s+from\s+"
                r"[\w\s,\"]*\b(?:anon|authenticated|public)\b", re.I),
     "Revogação em massa: antes, salve o estado atual com a consulta de permissões (references/stacks/baas.md) e liste o que o app "
     "usa sem login e logado (supabase.from e supabase.rpc). Depois devolva só o necessário, objeto por objeto, nunca em massa. "
     "Em funções, o Postgres dá EXECUTE a PUBLIC por padrão: revogar só do anon não fecha."),
    (re.compile(r"disable\s+row\s+level\s+security", re.I),
     "Desligar a RLS deixa a tabela inteira aberta para quem tem GRANT nela. Isso nunca é a correção."),
    (re.compile(r"(?:^|;|\bthen\b)[ \t]*(?:drop\s+(?:table|schema|database)\b|truncate\b(?:\s+table)?\s+(?!on\b)[\w\"])", re.I | re.M),
     "Este comando apaga dados. Só com backup conferido e o OK explícito do humano."),
)


def cuidados(*textos):
    t = "\n".join(x for x in textos if x)
    return [aviso for rx, aviso in CUIDADOS if rx.search(t)]


def carregar_prompts():
    """Lê references/prompts-pos-analise.md: [{id, titulo, quando, uso, texto}]."""
    try:
        txt = (SKILL_DIR / "references" / "prompts-pos-analise.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    except Exception:
        return []
    out = []
    for m in re.finditer(r"(?ms)^## (PA\d{2}) · (.+?)\n(.*?)(?=^## PA\d{2} · |^---[ \t]*$|\Z)", txt):
        corpo = m.group(3)
        q = re.search(r"<!--\s*quando:\s*(.+?)\s*-->", corpo)
        b = re.search(r"```text\n(.*?)\n```", corpo, re.S)
        uso = re.search(r"\*\*Quando usar:\*\*\s*(.+)", corpo)
        if b:
            out.append({"id": m.group(1), "titulo": m.group(2).strip(), "quando": (q.group(1) if q else "sempre").lower(),
                        "uso": uso.group(1).strip() if uso else "", "texto": b.group(1).strip()})
    return out


def escolher_prompts(lib, every, meta, maximo=5):
    """(prompts por extenso, prompts de engenharia só citados) que combinam com o que ficou aberto.
    Com "prompts" no findings.json, vale a escolha de quem escreveu."""
    por_id = {p["id"]: p for p in lib}
    engenharia = [p for p in lib if "engenharia" in p["quando"]]
    pedidos = meta.get("prompts") or []
    pedidos = [str(x).strip().upper() for x in (re.split(r"[,\s]+", pedidos) if isinstance(pedidos, str) else pedidos) if str(x).strip()]
    if pedidos:
        sel = [por_id[i] for i in pedidos if i in por_id]
        return sel, [p for p in engenharia if p not in sel]
    abertos = {c["id"] for c in every if c["status"] in ("FALHA", "ATENCAO")}
    if not abertos:
        return [p for p in lib if p["quando"].startswith("sempre")][:2], engenharia
    critico = any(c["status"] == "FALHA" and c["severidade"] == "CRITICO" for c in every)
    contexto = " ".join([meta.get("stack") or ""] + [(c.get("resumo") or "") + " " + (c.get("correcao") or "") for c in every]).lower()
    escolhidos = []
    for p in lib:
        q = p["quando"]
        se = re.search(r"\bse ([\w|]+)", q)
        if se and not any(w and w in contexto for w in se.group(1).split("|")):
            continue
        ids = {i.upper() for i in re.findall(r"\b[cp]\d{2}\b", q)}
        if (q.startswith("critico") and critico) or (q.startswith("abertos") and p["id"] != "PA14") or ids & abertos:
            escolhidos.append(p)
    final = escolhidos[:maximo - 1]
    if "PA14" in por_id:
        final.append(por_id["PA14"])
    return final, [p for p in engenharia if p not in final]


def clean(x):
    if isinstance(x, str):
        return mask_secrets(x)
    if isinstance(x, list):
        return [clean(i) for i in x]
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    return x


def _parse(items, table, label, errors):
    out = {}
    for c in items:
        cid = (c.get("id") or "").upper()
        if cid not in table:
            errors.append(f"id inválido em '{label}': {cid!r}")
            continue
        st = norm_status(c.get("status"))
        if st not in VALID_STATUS:
            errors.append(f"{cid}: status inválido {c.get('status')!r} (use OK, ATENCAO, FALHA, NA ou NAO_AVALIADO)")
            continue
        sev = norm_sev(c.get("severidade") or table[cid][1])
        if sev not in VALID_SEV:
            errors.append(f"{cid}: severidade inválida {c.get('severidade')!r}")
            continue
        c["status"], c["severidade"], c["id"] = st, sev, cid
        if st in ("FALHA", "ATENCAO"):
            for field in ("resumo", "risco", "correcao", "prompt"):
                if not (c.get(field) or "").strip():
                    errors.append(f"{cid}: campo '{field}' obrigatório quando status é {st}")
        elif not (c.get("resumo") or "").strip():
            errors.append(f"{cid}: campo 'resumo' obrigatório (diga por que está OK/N/A)")
        out[cid] = clean(c)
    return out


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = []
    checks = _parse(data.get("checks", []), CHECKS, "checks", errors)
    missing = [cid for cid in CHECKS if cid not in checks]
    if missing:
        errors.append("faltando checagens: " + ", ".join(missing) + " (todas as 20 entram; use NA com resumo se não avaliou)")
    pront = _parse(data.get("prontidao", []), PRONTIDAO, "prontidao", errors)
    if pront:
        miss_p = [cid for cid in PRONTIDAO if cid not in pront]
        if miss_p:
            errors.append("faltando itens de prontidão: " + ", ".join(miss_p) + " (com 'prontidao' no JSON, os 10 entram; use NA se não se aplica)")
    if errors:
        sys.exit("findings.json inválido:\n  - " + "\n  - ".join(errors))
    meta = {k: v for k, v in data.items() if k not in ("checks", "prontidao")}
    if isinstance(meta.get("stack"), (list, tuple)):
        meta["stack"] = ", ".join(str(x) for x in meta["stack"])
    return clean(meta), checks, pront


def score(checks):
    num = den = 0.0
    for cid, c in checks.items():
        if c["status"] in ("NA", "NAO_AVALIADO"):
            continue
        w = SEVERITY_WEIGHT[c["severidade"]]  # peso pela severidade efetiva
        den += w
        num += w * STATUS_VALUE[c["status"]]
    if not den:
        return None  # nada avaliado: sem nota (aparece como "—")
    s = round(100 * num / den)
    # teto para a nota não contradizer o veredito: falha crítica ≤ 49, falha alta ou atenção crítica ≤ 79
    if any(c["status"] == "FALHA" and c["severidade"] == "CRITICO" for c in checks.values()):
        s = min(s, 49)
    elif any((c["status"] == "FALHA" and c["severidade"] == "ALTO") or (c["status"] == "ATENCAO" and c["severidade"] == "CRITICO")
             for c in checks.values()):
        s = min(s, 79)
    return s


def verdict(checks, pront=None):
    fails = [c for c in checks.values() if c["status"] == "FALHA"]
    warns = [c for c in checks.values() if c["status"] == "ATENCAO"]
    if any(c["severidade"] == "CRITICO" for c in fails):
        return "🔴", "NÃO LANCE AINDA", "Há falha crítica aberta. Corrija os itens críticos antes de colocar no ar (ou tire do ar se já está publicado)."
    if any(c["severidade"] == "ALTO" for c in fails) or any(c["severidade"] == "CRITICO" for c in warns):
        return "🟡", "AJUSTES ANTES DO LANÇAMENTO", "Sem falha crítica confirmada, mas há falhas altas ou pontos críticos a validar. Resolva antes de abrir para o público."
    if any(c["status"] == "NAO_AVALIADO" for c in checks.values()) or all(c["status"] == "NA" for c in checks.values()):
        return "⚪", "AVALIAÇÃO PARCIAL", "Só parte das checagens de segurança foi avaliada. Isto não libera o lançamento: rode o check completo antes de abrir para o público."
    if pront and any(c["status"] == "FALHA" and c["severidade"] in ("CRITICO", "ALTO") for c in pront.values()):
        return "🟡", "AJUSTES ANTES DO LANÇAMENTO", "A segurança não tem falha crítica ou alta, mas a prontidão tem falha alta (e-mail, backup, LGPD, custos…) que atrapalha o lançamento."
    return "🟢", "PRONTO PARA LANÇAR", "Nenhuma falha crítica ou alta. Os itens restantes são melhorias para as próximas sprints."


def priority(c):
    return (SEVERITY_ORDER[c["severidade"]], 0 if c["status"] == "FALHA" else 1, c["id"])


def order_items(items):
    """Ordena por prioridade, mas uma task nunca vem antes das que ela depende (depende_de)."""
    ids = {c["id"] for c in items}
    deps = {c["id"]: [d.upper() for d in (c.get("depende_de") or []) if d.upper() in ids and d.upper() != c["id"]] for c in items}
    remaining = sorted(items, key=priority)
    done, out = set(), []
    while remaining:
        nxt = next((c for c in remaining if all(d in done for d in deps[c["id"]])), remaining[0])  # ciclo: segue a prioridade
        out.append(nxt)
        done.add(nxt["id"])
        remaining.remove(nxt)
    return out


def fmt_nota(x):
    return "—" if x is None else f"{x}/100"


def short(text, n=110):
    text = (text or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:—-") + "…"


def render(meta, checks, pront, outdir):
    today = meta.get("data") or date.today().isoformat()
    projeto = meta.get("projeto") or "Projeto"
    nota = score(checks)
    nota_p = score(pront) if pront else None
    icon, label, explain = verdict(checks, pront)
    open_sec = order_items([c for c in checks.values() if c["status"] in ("FALHA", "ATENCAO")])
    open_p = order_items([c for c in pront.values() if c["status"] in ("FALHA", "ATENCAO")]) if pront else []
    open_items = open_sec + open_p
    task_no = {c["id"]: i for i, c in enumerate(open_items, 1)}
    decisoes = meta.get("decisoes_pendentes") or []
    preparacao = meta.get("preparacao") or []
    every = list(checks.values()) + list((pront or {}).values())
    ok_items = [c for c in every if c["status"] == "OK"]
    na_items = [c for c in every if c["status"] == "NA"]
    nao_av = [c for c in every if c["status"] == "NAO_AVALIADO"]
    count = {s: sum(1 for c in checks.values() if c["status"] == s) for s in VALID_STATUS}
    by_sev = {s: sum(1 for c in open_sec if c["status"] == "FALHA" and c["severidade"] == s) for s in VALID_SEV}
    rel_dir = meta.get("pasta_relatorio") or "check-report"

    # ------------------------------------------------------------------ RELATORIO
    L = [MARCA]
    L.append(f"# Check pré-lançamento · {projeto}\n")
    L.append(f"**Data:** {today}  ")
    if meta.get("stack"):
        L.append(f"**Stack:** {meta['stack']}  ")
    if meta.get("escopo"):
        L.append(f"**Escopo:** {meta['escopo']}  ")
    L.append("")
    L.append(f"## {icon} Veredito: {label}\n")
    L.append(f"**Nota de segurança: {fmt_nota(nota)}**" + (f" · **Nota de prontidão: {fmt_nota(nota_p)}**" if pront else "") + "  ")
    L.append(f"{explain}\n")
    if count["NAO_AVALIADO"]:
        L.append(f"| ❌ Falhas | ⚠️ Atenção | ✅ OK | ➖ N/A | ⚪ Não avaliado |\n|---|---|---|---|---|\n"
                 f"| {count['FALHA']} | {count['ATENCAO']} | {count['OK']} | {count['NA']} | {count['NAO_AVALIADO']} |\n")
    else:
        L.append(f"| ❌ Falhas | ⚠️ Atenção | ✅ OK | ➖ N/A |\n|---|---|---|---|\n| {count['FALHA']} | {count['ATENCAO']} | {count['OK']} | {count['NA']} |\n")
    if count["FALHA"]:
        parts = [f"{by_sev[s]} {SEVERITY_LABEL[s].lower()}{'s' if by_sev[s] > 1 else ''}" for s in ("CRITICO", "ALTO", "MEDIO", "BAIXO") if by_sev[s]]
        L.append("Falhas por severidade: " + " · ".join(parts) + "\n")
    if meta.get("resumo_executivo"):
        L.append("> " + meta["resumo_executivo"].strip().replace("\n", "\n> ") + "\n")

    L.append("## Placar das 20 checagens\n")
    L.append("| # | Checagem | Status | Severidade | O que encontrei |")
    L.append("|---|---|---|---|---|")
    for cid in CHECKS:
        c = checks[cid]
        sev = f"{SEVERITY_ICON[c['severidade']]} {SEVERITY_LABEL[c['severidade']]}" if c["status"] in ("FALHA", "ATENCAO") else "—"
        resumo = (c.get("resumo") or "").replace("|", "\\|").replace("\n", " ")
        L.append(f"| {cid[1:]} | {ALL[cid][0]} | {STATUS_LABEL[c['status']]} | {sev} | {resumo} |")
    L.append("")
    if pront:
        L.append("## Prontidão para o lançamento (10 itens)\n")
        L.append("Não entra na nota de segurança. Mede o que costuma derrubar um lançamento mesmo com o app seguro: "
                 "e-mail que não chega, site fora do Google, conta de nuvem estourada, erro sem ninguém ver.\n")
        L.append("| # | Item | Status | Severidade | O que encontrei |")
        L.append("|---|---|---|---|---|")
        for cid in PRONTIDAO:
            c = pront[cid]
            sev = f"{SEVERITY_ICON[c['severidade']]} {SEVERITY_LABEL[c['severidade']]}" if c["status"] in ("FALHA", "ATENCAO") else "—"
            resumo = (c.get("resumo") or "").replace("|", "\\|").replace("\n", " ")
            L.append(f"| {cid} | {PRONTIDAO[cid][0]} | {STATUS_LABEL[c['status']]} | {sev} | {resumo} |")
        L.append("")
    else:
        L.append("> Prontidão para o lançamento (P01–P10) não avaliada nesta rodada.\n")

    if decisoes:
        L.append("## Decisões que só você pode tomar\n")
        L.append("Responda antes de aplicar as correções — várias delas dependem disso.\n")
        for d in decisoes:
            L.append(f"- [ ] {d}")
        L.append("")
    if open_items:
        L.append("## O que corrigir (por prioridade)\n" if open_sec else "## Prontidão: o que ajustar antes de divulgar\n")
        for i, c in enumerate(open_items, 1):
            cid = c["id"]
            if open_sec and cid.startswith("P") and open_items[i - 2]["id"].startswith("C"):
                L.append("## Prontidão: o que ajustar antes de divulgar\n")
            L.append(f"### {i}. {SEVERITY_ICON[c['severidade']]} [{cid}] {ALL[cid][0]} — {SEVERITY_LABEL[c['severidade']]} · {STATUS_LABEL[c['status']]}\n")
            L.append(f"**O que encontrei:** {c['resumo'].strip()}\n")
            dep = [d for d in (c.get("depende_de") or []) if d.upper() in task_no]
            if dep:
                L.append("**Depende de:** " + ", ".join(f"item {task_no[d.upper()]} ({d.upper()})" for d in dep) + "\n")
            ev = c.get("evidencias") or []
            if ev:
                L.append("**Evidências:**")
                for e in ev[:12]:
                    L.append(f"- {e}")
                if len(ev) > 12:
                    L.append(f"- … e mais {len(ev) - 12} ocorrência(s)")
                L.append("")
            L.append(f"**Risco:** {c['risco'].strip()}\n")
            L.append(f"**Como corrigir:**\n\n{c['correcao'].strip()}\n")
            for aviso in cuidados(c.get("correcao"), c.get("prompt")):
                L.append(f"> ⚠️ **Cuidado:** {aviso}\n")
            if c.get("acao_manual"):
                L.append(f"**Você precisa fazer (fora do código):** {c['acao_manual'].strip()}\n")
            L.append("**Prompt pronto para o agente (Claude, Codex, Cursor…):**\n")
            L.append(fence(c["prompt"], "text") + "\n")
    if ok_items:
        L.append("## O que está OK\n")
        for c in sorted(ok_items, key=lambda c: c["id"]):
            L.append(f"- **[{c['id']}] {ALL[c['id']][0]}** — {c['resumo'].strip()}")
        L.append("")
    if nao_av:
        L.append("## Não avaliado nesta rodada\n")
        L.append("Não está aprovado: só não foi olhado.\n")
        for c in sorted(nao_av, key=lambda c: c["id"]):
            L.append(f"- **[{c['id']}] {ALL[c['id']][0]}** — {c['resumo'].strip()}")
        L.append("")
    if na_items:
        L.append("## Não se aplica\n")
        for c in sorted(na_items, key=lambda c: c["id"]):
            L.append(f"- **[{c['id']}] {ALL[c['id']][0]}** — {c['resumo'].strip()}")
        L.append("")
    manual = [c for c in open_items if c.get("acao_manual")] + [c for c in ok_items + na_items if c.get("acao_manual")]
    seen = {re.sub(r"\W+", " ", c["acao_manual"]).strip().lower() for c in manual}
    extra_manual = []
    for a in meta.get("acoes_manuais") or []:
        key = re.sub(r"\W+", " ", a).strip().lower()
        if key not in seen:
            seen.add(key)
            extra_manual.append(a)
    if manual or extra_manual:
        L.append("## Checklist manual (fora do código)\n")
        for c in manual:
            L.append(f"- [ ] **[{c['id']}]** {c['acao_manual'].strip()}")
        for a in extra_manual:
            L.append(f"- [ ] {a}")
        L.append("")
    L.append("## Próximos passos\n")
    if open_items:
        L.append(f"1. Abra o seu agente (Claude Code, Codex, Cursor…) na raiz do projeto e peça: **\"Leia {rel_dir}/CORRECOES.md e aplique as correções na ordem, uma por vez.\"**")
        step = 2
        if decisoes:
            L.insert(len(L) - 1, "1. Responda as decisões pendentes acima — elas mudam parte das correções.")
            L[-1] = L[-1].replace("1. ", "2. ", 1)
            step = 3
        if manual or extra_manual:
            L.append(f"{step}. Faça o checklist manual (o que o agente não pode fazer por você).")
            step += 1
        L.append(f"{step}. Rode o check de novo para confirmar que tudo virou ✅.")
    else:
        L.append("1. Mantenha Dependabot/Renovate ativo e rode este check a cada release grande.")
    sel, depois = escolher_prompts(carregar_prompts(), every, meta)
    if sel or depois:
        L.append("\n## Prompts prontos para o próximo passo\n")
        L.append("Copie e cole no seu agente, aberto na pasta do projeto. No claude.ai ou em outro chat, anexe antes este relatório e o "
                 f"`CORRECOES.md`. A lista completa está em [PROMPTS.md]({AUTORIA['repositorio']}/blob/main/PROMPTS.md).\n")
        pasta = rel_dir.rstrip("/") + "/"
        for p in sel:
            L.append(f"### {p['id']} · {p['titulo']}\n")
            if p["uso"]:
                L.append(f"**Quando usar:** {p['uso']}\n")
            L.append(fence(p["texto"].replace("check-report/", pasta), "text") + "\n")
        if depois:
            L.append("**Depois do lançamento (engenharia):** " + " · ".join(f"{p['id']} {p['titulo']}" for p in depois)
                     + f". Estão no [PROMPTS.md]({AUTORIA['repositorio']}/blob/main/PROMPTS.md), com a ordem sugerida.\n")
    cob = meta.get("cobertura") or []
    if cob:
        L.append("\n## Cobertura desta análise\n")
        L.append("O que foi olhado e o que ficou de fora. O que não foi olhado não está aprovado.\n")
        for x in cob:
            L.append(f"- {x}")
    if meta.get("limitacoes"):
        L.append("\n**Limitações desta análise:** " + meta["limitacoes"].strip())
    L.append("\n---")
    L.append(f"Gerado pela skill **[check-pre-lancamento]({AUTORIA['repositorio']})** v{VERSION} · criada por "
             f"**{AUTORIA['autor']}** · [github.com/{AUTORIA['github']}](https://github.com/{AUTORIA['github']})  ")
    L.append("Triagem automatizada + revisão de código por IA. Ajuda muito, mas não substitui pentest profissional em app que lida com dinheiro, saúde ou dado sensível em escala.")
    (outdir / "RELATORIO.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ CORRECOES
    C = [MARCA]
    C.append(f"# Correções · {projeto}\n")
    C.append(f"> Plano de correção gerado pelo check-pre-lancamento em {today} (nota de segurança {fmt_nota(nota)}"
             + (f", prontidão {fmt_nota(nota_p)}" if pront else "") + f", veredito: {label}).")
    C.append(f"> Para executar, abra o seu agente (Claude Code, Codex, Cursor…) na raiz do projeto e diga: **\"Leia {rel_dir}/CORRECOES.md e aplique as correções na ordem, uma por vez.\"**\n")
    C.append("## Regras de execução (para o agente)\n")
    C.append("1. Uma task por vez, na ordem abaixo. Antes de mexer, leia os arquivos citados e confirme que o problema ainda existe — se já foi corrigido, marque e siga.")
    C.append("2. Não quebre funcionalidade: depois de cada task rode o que existir de build, lint, typecheck e testes. Se quebrar, conserte antes de seguir.")
    C.append("3. Se o projeto usa git, faça um commit por task: `fix(security): [Cxx] <resumo>` (prontidão: `chore(launch): [Pxx] <resumo>`).")
    C.append("4. Nunca escreva valor de segredo em código, commit, log ou chat. Use variáveis de ambiente e só referencie pelo nome.")
    C.append("5. Itens marcados **Ação manual** não são seus (rotacionar chave, painel do Supabase/Firebase, DNS, Cloudflare): liste-os para o humano no final.")
    C.append("6. Não reescreva histórico do git (filter-repo/BFG), não faça force push e não apague dados sem confirmação explícita do humano.")
    C.append("7. Se a correção depender de decisão de produto (essa rota deveria ser pública? esse campo pode ser editado pelo usuário?), pare e pergunte.")
    C.append("8. Prefira a menor mudança que resolve. Nada de refatoração não pedida.")
    C.append("9. Mudança de permissão no banco (GRANT, REVOKE, policy, função): antes, salve o estado atual; depois, teste com um "
             "visitante sem login e com duas contas diferentes. Nunca devolva permissão em massa (`on all tables`, `on all functions`).")
    C.append("10. Ao terminar, rode o scanner de novo e atualize o relatório (veja \"Validação final\").\n")
    if decisoes:
        C.append("## Antes de começar: decisões do humano\n")
        C.append("Pergunte ao humano e espere a resposta antes das tasks afetadas. Não decida por ele.\n")
        for d in decisoes:
            C.append(f"- [ ] {d}")
        C.append("")
    if preparacao:
        C.append("## Task 0 · Preparação\n")
        C.append("O projeto precisa estar neste estado antes da Task 1 (sem isso, build/testes das próximas tasks não dizem nada):\n")
        for p_ in preparacao:
            C.append(f"- [ ] {p_}")
        C.append("")
    if open_items:
        C.append("## Ordem de execução\n")
        C.append("| Task | Check | Severidade | Status | Depende de | O quê |")
        C.append("|---|---|---|---|---|---|")
        for i, c in enumerate(open_items, 1):
            dep = ", ".join(str(task_no[d.upper()]) for d in (c.get("depende_de") or []) if d.upper() in task_no) or "—"
            C.append(f"| {i} | {c['id']} {ALL[c['id']][0]} | {SEVERITY_LABEL[c['severidade']]} | {STATUS_LABEL[c['status']]} | {dep} | {short(c.get('resumo'))} |")
        C.append("")
        for i, c in enumerate(open_items, 1):
            cid = c["id"]
            C.append(f"## Task {i} · [{cid}] {ALL[cid][0]} — {SEVERITY_LABEL[c['severidade']]}\n")
            C.append(f"**Problema:** {c['resumo'].strip()}\n")
            dep = [d.upper() for d in (c.get("depende_de") or []) if d.upper() in task_no]
            if dep:
                C.append("**Depende de:** " + ", ".join(f"Task {task_no[d]} ({d})" for d in dep) + " — se ainda não foi feita, faça antes.\n")
            arq = c.get("arquivos") or []
            if arq:
                C.append("**Arquivos:** " + ", ".join(f"`{a}`" for a in arq[:15]) + "\n")
            ev = c.get("evidencias") or []
            if ev:
                C.append("**Evidências:**")
                for e in ev[:12]:
                    C.append(f"- {e}")
                C.append("")
            C.append("**O que fazer:**\n")
            C.append(c["prompt"].strip() + "\n")
            for aviso in cuidados(c.get("correcao"), c.get("prompt")):
                C.append(f"> ⚠️ **Cuidado:** {aviso}\n")
            crit = c.get("criterios_aceite") or []
            if crit:
                C.append("**Critério de aceite:**")
                for k in crit:
                    C.append(f"- [ ] {k}")
                C.append("")
            if c.get("acao_manual"):
                C.append(f"**Ação manual (humano):** {c['acao_manual'].strip()}\n")
    else:
        C.append("Nenhuma correção pendente. 🎉\n")
    if manual or extra_manual:
        C.append("## Checklist manual (repasse ao humano no final)\n")
        for c in manual:
            C.append(f"- [ ] **[{c['id']}]** {c['acao_manual'].strip()}")
        for a in extra_manual:
            C.append(f"- [ ] {a}")
        C.append("")
    scan_cmd = meta.get("comando_scan") or f"python3 {SKILL_DIR}/scripts/scan.py . --out {rel_dir}/scan.json"
    C.append("## Validação final\n")
    C.append(f"- [ ] Rodar de novo o scanner: `{scan_cmd}` e confirmar que os achados de confiança alta sumiram.")
    C.append("- [ ] Build e testes passando.")
    C.append("- [ ] Atualizar `findings.json` com os novos status e regenerar o relatório (`render_report.py`).")
    C.append("- [ ] Entregar ao humano: o que foi corrigido (por task), o que ficou pendente e o checklist manual.")
    C.append(f"\n---\n<sub>Plano gerado pela skill check-pre-lancamento v{VERSION} · por {AUTORIA['autor']} · {AUTORIA['repositorio']}</sub>")
    (outdir / "CORRECOES.md").write_text("\n".join(C) + "\n", encoding="utf-8")
    return nota, nota_p, label, count


def main():
    ap = argparse.ArgumentParser(description=f"Gera RELATORIO.md e CORRECOES.md · {CREDITO}")
    ap.add_argument("findings")
    ap.add_argument("--out", help="pasta de saída (padrão: a pasta do findings.json)")
    args = ap.parse_args()
    trava_de_autoria()
    meta, checks, pront = load(args.findings)
    outdir = Path(args.out) if args.out else Path(args.findings).resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)
    nota, nota_p, label, count = render(meta, checks, pront, outdir)
    print(CREDITO)
    print(f"Segurança {fmt_nota(nota)}" + (f" · prontidão {fmt_nota(nota_p)}" if nota_p is not None else " · prontidão não avaliada") +
          f" · {label} · falhas {count['FALHA']} · atenção {count['ATENCAO']} · ok {count['OK']} · n/a {count['NA']}")
    print(f"→ {outdir / 'RELATORIO.md'}\n→ {outdir / 'CORRECOES.md'}")


if __name__ == "__main__":
    main()
