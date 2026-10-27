#!/usr/bin/env python3
# check-pre-lancamento · conferência de autoria e integridade da skill
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
# Aviso obrigatório: mantenha estas linhas e os créditos de autoria em qualquer cópia ou derivado.
"""Confere se esta cópia da skill é a oficial, se foi modificada e se os créditos continuam lá.

Uso:
    python3 autoria.py            # resumo legível
    python3 autoria.py --json     # resultado em JSON (o scan.py usa a função verificar())
    python3 autoria.py --gerar    # (mantenedor) regrava o AUTORIA.json com os hashes da versão

Nada sai da máquina: só lê os arquivos da própria skill. O manifesto AUTORIA.json traz o hash
SHA-256 de cada arquivo da versão publicada em https://github.com/dantaspaulo/check-pre-lancamento.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import AUTORIA, CREDITO, VERSION, creditos_intactos  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
MANIFESTO = "AUTORIA.json"
MARCAS = ("Paulo Sérgio Dantas", "dantaspaulo/check-pre-lancamento")
IGNORAR = {MANIFESTO, ".DS_Store"}
TEXTO = (".md", ".py", ".txt")


def _arquivos(base):
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).parts
        if p.is_file() and p.name not in IGNORAR and "__pycache__" not in rel and not any(x.startswith(".") for x in rel):
            yield p  # pastas e arquivos ocultos (.pytest_cache, .DS_Store…) não fazem parte da skill


def _hash(p):
    # normaliza fim de linha para o hash não mudar com o autocrlf do Git no Windows
    data = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def verificar(base=SKILL_DIR):
    base = Path(base)
    out = {"versao": VERSION, "manifesto": False, "oficial": False, "modificados": [], "faltando": [], "sem_credito": []}
    for p in _arquivos(base):
        if p.suffix in TEXTO:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if not all(m in txt for m in MARCAS):
                out["sem_credito"].append(str(p.relative_to(base)).replace("\\", "/"))
    man = base / MANIFESTO
    if man.exists():
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
            out["manifesto"] = True
            esperado = data.get("arquivos") or {}
            for rel, h in esperado.items():
                p = base / rel
                if not p.exists():
                    out["faltando"].append(rel)
                elif _hash(p) != h:
                    out["modificados"].append(rel)
            out["oficial"] = (data.get("repositorio") == AUTORIA["repositorio"] and not out["modificados"]
                              and not out["faltando"] and data.get("versao") == VERSION)
        except Exception as e:
            out["erro_manifesto"] = f"{type(e).__name__}: {e}"
    out["creditos_removidos"] = bool(out["sem_credito"]) or not creditos_intactos()
    return out


def gerar(base=SKILL_DIR):
    base = Path(base)
    arquivos = {str(p.relative_to(base)).replace("\\", "/"): _hash(p) for p in _arquivos(base)}
    data = {"skill": AUTORIA["skill"], "versao": VERSION, "autor": AUTORIA["autor"], "repositorio": AUTORIA["repositorio"],
            "licenca": AUTORIA["licenca"], "impressao": AUTORIA["impressao"], "arquivos": arquivos}
    (base / MANIFESTO).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main():
    ap = argparse.ArgumentParser(description=f"Confere autoria e integridade · {CREDITO}")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gerar", action="store_true", help="(mantenedor) regrava AUTORIA.json")
    args = ap.parse_args()
    if args.gerar:
        d = gerar()
        print(f"AUTORIA.json gravado: {len(d['arquivos'])} arquivos, versão {d['versao']}")
        return
    r = verificar()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(CREDITO)
    if r["creditos_removidos"]:
        print("⚠️  Os créditos de autoria foram removidos ou alterados nesta cópia (isso viola a licença).")
        for x in r["sem_credito"][:20]:
            print(f"   sem crédito: {x}")
    if r["oficial"]:
        print("✅ Cópia oficial e íntegra.")
    elif r["manifesto"]:
        print("ℹ️  Cópia modificada (" + ", ".join(r["modificados"][:10] + r["faltando"][:10]) + ").")
    else:
        print("ℹ️  Sem manifesto de integridade: não dá para confirmar se é a versão oficial.")
    print(f"Versão oficial e gratuita: {AUTORIA['repositorio']}")


if __name__ == "__main__":
    main()
