#!/usr/bin/env python3
# check-pre-lancamento · mostra um arquivo com os segredos mascarados
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
# Aviso obrigatório: mantenha estas linhas e os créditos de autoria em qualquer cópia ou derivado.
"""check-pre-lancamento · mostra um arquivo com os segredos mascarados.

Uso:
    python3 show.py ARQUIVO [--linhas 10-40]

Use no lugar de abrir direto arquivos que podem ter segredo (.env*, configs, clientes do
banco, arquivos apontados pelo scanner em C01/C02/C03). Assim o valor real nunca entra na
conversa, no relatório ou em log. Só stdlib.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CREDITO, SECRET_PATTERNS, decode_jwt_payload, looks_placeholder, mask, mask_secrets  # noqa: E402

JWT_RX = next(rx for pid, rx, _c, _d in SECRET_PATTERNS if pid == "jwt")

# Em arquivos .env, só deixa à mostra valores de chaves claramente não secretas (e mesmo assim passa pela máscara)
NON_SECRET_KEY = re.compile(r"(_URL|_HOST|_PORT|_NAME|_ENV|_MODE|_REGION|_DOMAIN|_PATH|_DIR|_LEVEL|_VERSION|_ID|NODE_ENV|DEBUG|PORT)$")
ENV_LINE = re.compile(r"^(\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*)(.*)$")
SECRET_FILES = (".npmrc", ".pypirc", ".netrc", "_netrc", ".envrc", ".dev.vars", ".yarnrc", ".yarnrc.yml")
PEM_B = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY")
PEM_E = re.compile(r"-----END [A-Z0-9 ]*PRIVATE KEY")


def mask_env_line(line):
    line = line.lstrip("﻿")
    m = ENV_LINE.match(line)
    if not m:
        return mask_secrets(line)
    key = m.group(1).split("=")[0].replace("export", "").strip().upper()
    value = m.group(2).strip().strip("'\"")
    if not value or looks_placeholder(value) or value.lower() in ("true", "false", "yes", "no", "on", "off"):
        return line
    if NON_SECRET_KEY.search(key):
        return mask_secrets(line)  # URL de webhook, broker com senha, RPC com chave no caminho: a máscara decide
    return m.group(1) + mask(value)


def read_text_any(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if raw[:4000].count(b"\x00") > len(raw[:4000]) // 4:  # UTF-16 sem BOM (PowerShell)
        return raw.decode("utf-16-le", "replace")
    return raw.decode("utf-8-sig", "replace")


def main():
    ap = argparse.ArgumentParser(description=f"Mostra um arquivo com os segredos mascarados · {CREDITO}")
    ap.add_argument("arquivo")
    ap.add_argument("--linhas", help="intervalo, ex.: 10-40")
    args = ap.parse_args()
    path = args.arquivo
    name = os.path.basename(path)
    is_env = name.startswith(".env") or name.endswith(".env") or name.startswith("env.") or name in SECRET_FILES
    lines = read_text_any(path).split("\n")
    start, end = 1, len(lines)
    if args.linhas:
        a, _, b = args.linhas.partition("-")
        start, end = max(1, int(a)), min(len(lines), int(b or a))
    width = len(str(end))
    in_pem = False  # estado do PEM calculado desde a primeira linha, para --linhas no meio de uma chave
    for ln in lines[:start - 1]:
        if PEM_B.search(ln):
            in_pem = not PEM_E.search(ln)
        elif in_pem and PEM_E.search(ln):
            in_pem = False
    for n in range(start, end + 1):
        ln = lines[n - 1]
        if PEM_B.search(ln):
            in_pem = not PEM_E.search(ln)
        elif in_pem:
            if PEM_E.search(ln):
                in_pem = False
            else:
                print(f"{n:>{width}}  …[conteúdo da chave privada ocultado]")
                continue
        if name in (".netrc", "_netrc"):
            ln = re.sub(r"(?i)\b(password|passwd)\s+\S+", r"\1 ****", ln)
        out = mask_env_line(ln) if is_env else mask_secrets(ln)
        if len(out) > 3000:  # mascara antes, corta depois
            out = out[:3000] + " …[linha cortada]"
        roles = [str((decode_jwt_payload(m.group(0)) or {}).get("role", "?")) for m in JWT_RX.finditer(ln)]
        if roles:
            out += "   ⟵ JWT role=" + ",".join(roles)
        print(f"{n:>{width}}  {out}")


if __name__ == "__main__":
    main()
