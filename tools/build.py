#!/usr/bin/env python3
# check-pre-lancamento · empacota a skill para distribuição
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
"""Uso:
    python3 tools/build.py           # regrava AUTORIA.json e gera dist/check-pre-lancamento.zip e .skill
    python3 tools/build.py --check   # (CI) confere créditos em todos os arquivos e se o AUTORIA.json está em dia

O zip tem a pasta check-pre-lancamento/ na raiz, que é o formato que o claude.ai, a Lovable e os
instaladores esperam. O .skill é o mesmo zip com outra extensão.
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "check-pre-lancamento"
DIST = ROOT / "dist"
sys.path.insert(0, str(SKILL / "scripts"))
import autoria  # noqa: E402
from _common import VERSION  # noqa: E402

LIMITE_ARQUIVO = 1_000_000  # Lovable aceita até 1 MB por arquivo dentro do zip
PROMPTS_FONTE = SKILL / "references" / "prompts-pos-analise.md"
PROMPTS_RAIZ = ROOT / "PROMPTS.md"


def prompts_da_raiz():
    """PROMPTS.md da raiz = cópia da biblioteca que vai dentro da skill (fonte única: references/prompts-pos-analise.md)."""
    corpo = PROMPTS_FONTE.read_text(encoding="utf-8")
    aviso = ("<!-- Gerado por tools/build.py a partir de skills/check-pre-lancamento/references/prompts-pos-analise.md. "
             "Edite lá e rode python3 tools/build.py. -->\n")
    return aviso + corpo


def conferir():
    erros = []
    if not PROMPTS_RAIZ.exists() or PROMPTS_RAIZ.read_text(encoding="utf-8") != prompts_da_raiz():
        erros.append("PROMPTS.md da raiz fora de sincronia com references/prompts-pos-analise.md: rode python3 tools/build.py")
    r = autoria.verificar()
    if r["sem_credito"]:
        erros.append("arquivos sem crédito de autoria: " + ", ".join(r["sem_credito"]))
    if r["creditos_removidos"]:
        erros.append("créditos do _common.py alterados (selo não confere)")
    if not r["manifesto"]:
        erros.append("AUTORIA.json ausente: rode python3 tools/build.py")
    elif r["modificados"] or r["faltando"]:
        erros.append("AUTORIA.json desatualizado (" + ", ".join(r["modificados"] + r["faltando"]) + "): rode python3 tools/build.py")
    man = json.loads((SKILL / "AUTORIA.json").read_text(encoding="utf-8")) if (SKILL / "AUTORIA.json").exists() else {}
    novos = [str(p.relative_to(SKILL)).replace("\\", "/") for p in autoria._arquivos(SKILL)
             if str(p.relative_to(SKILL)).replace("\\", "/") not in (man.get("arquivos") or {})]
    if novos:
        erros.append("arquivos fora do AUTORIA.json: " + ", ".join(novos))
    for p in autoria._arquivos(SKILL):
        if p.stat().st_size > LIMITE_ARQUIVO:
            erros.append(f"{p.name} passa de 1 MB (a Lovable recusa)")
    versoes = {
        "plugin.json": json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
        "marketplace.json": json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["plugins"][0]["version"],
    }
    for nome, v in versoes.items():
        if v != VERSION:
            erros.append(f"{nome} está na versão {v}, a skill na {VERSION}")
    return erros


def empacotar():
    PROMPTS_RAIZ.write_text(prompts_da_raiz(), encoding="utf-8")
    autoria.gerar()
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / "check-pre-lancamento.zip"
    # zip reproduzível: data fixa, ordem fixa e fim de linha LF, então o mesmo código gera o mesmo hash em qualquer máquina
    arquivos = sorted(list(autoria._arquivos(SKILL)) + [SKILL / "AUTORIA.json"], key=lambda p: str(p.relative_to(SKILL)))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arquivos:
            info = zipfile.ZipInfo("check-pre-lancamento/" + str(p.relative_to(SKILL)).replace("\\", "/"), date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copyfile(zip_path, DIST / "check-pre-lancamento.skill")
    h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (DIST / "SHA256SUMS.txt").write_text(f"{h}  check-pre-lancamento.zip\n{h}  check-pre-lancamento.skill\n", encoding="utf-8")
    return zip_path, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        erros = conferir()
        if erros:
            print("✘ " + "\n✘ ".join(erros))
            sys.exit(1)
        print(f"✔ créditos em todos os arquivos, AUTORIA.json em dia, versão {VERSION}")
        return
    zip_path, h = empacotar()
    erros = conferir()
    if erros:
        print("✘ " + "\n✘ ".join(erros))
        sys.exit(1)
    print(f"✔ {zip_path} ({zip_path.stat().st_size // 1024} KB) · sha256 {h}")


if __name__ == "__main__":
    main()
