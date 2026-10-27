#!/usr/bin/env python3
# check-pre-lancamento · gera o ícone do plugin e a imagem de compartilhamento do repositório
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
"""Uso (precisa do Pillow, só para o mantenedor): python3 tools/imagens.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FUNDO, CAIXA, VERDE, CLARO, TINTA, SUAVE = "#0B110D", "#111A14", "#2BFA59", "#8CFFA8", "#EAFBEF", "#8FB09B"
FONTES = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTES_REG = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def fonte(lista, tamanho):
    for f in lista:
        if Path(f).exists():
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default()


def escudo(d, cx, cy, s, cor, borda=None, largura=0):
    pts = [(cx, cy - s), (cx + s * .82, cy - s * .62), (cx + s * .78, cy + s * .18), (cx, cy + s),
           (cx - s * .78, cy + s * .18), (cx - s * .82, cy - s * .62)]
    d.polygon(pts, fill=cor, outline=borda, width=largura)


def check(d, cx, cy, s, cor, w):
    d.line([(cx - s * .42, cy + s * .02), (cx - s * .1, cy + s * .34), (cx + s * .46, cy - s * .3)], fill=cor, width=w, joint="curve")


def icone():
    n = 1024
    im = Image.new("RGB", (n, n), FUNDO)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([40, 40, n - 40, n - 40], radius=200, fill=CAIXA, outline="#1F3326", width=6)
    escudo(d, n / 2, n / 2 + 10, 330, VERDE)
    check(d, n / 2, n / 2 + 20, 300, FUNDO, 64)
    out = ROOT / ".claude-plugin" / "icon.png"
    im.resize((512, 512), Image.LANCZOS).save(out)
    return out


def social():
    w, h = 1280, 640
    im = Image.new("RGB", (w, h), FUNDO)
    d = ImageDraw.Draw(im)
    for i in range(0, w, 32):
        d.line([(i, 0), (i, h)], fill="#0E1611")
    d.rounded_rectangle([36, 36, w - 36, h - 36], radius=36, outline="#1F3326", width=3)
    escudo(d, 1040, 300, 170, VERDE)
    check(d, 1040, 305, 160, FUNDO, 34)
    d.text((90, 110), "check-pre-lancamento", font=fonte(FONTES, 64), fill=VERDE)
    d.text((90, 205), "20 checagens de segurança", font=fonte(FONTES, 48), fill=TINTA)
    d.text((90, 265), "+ 10 de prontidão", font=fonte(FONTES, 48), fill=TINTA)
    d.text((90, 325), "antes de lançar seu app", font=fonte(FONTES, 48), fill=TINTA)
    d.text((90, 420), "Lovable · Bolt · v0 · Replit · React · Next · Vue · Angular", font=fonte(FONTES_REG, 28), fill=SUAVE)
    d.text((90, 460), "Node · Laravel · Django · Rails · Spring · .NET · Go · Supabase", font=fonte(FONTES_REG, 28), fill=SUAVE)
    d.text((90, 540), "por Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento", font=fonte(FONTES_REG, 26), fill=CLARO)
    out = ROOT / "assets" / "social-preview.png"
    im.save(out, optimize=True)
    return out


if __name__ == "__main__":
    print(icone())
    print(social())
