#!/usr/bin/env python3
# check-pre-lancamento · gera os cartões SVG animados do README
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
"""Uso: python3 assets/gerar.py

Mesmo desenho do perfil github.com/dantaspaulo (cartões escuros, borda com luz que corre, brilho
que passa, itens que sobem em sequência), com a paleta verde do check. Cada bloco sai em versão
de computador e de celular; o README troca com <picture>.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "check-pre-lancamento" / "scripts"))
from _common import CHECKS, PRONTIDAO, SECRET_PATTERNS, VERSION  # noqa: E402

C = dict(fundo="#0B110D", caixa="#111A14", borda="#1F3326", borda2="#2B4A36", tinta="#EAFBEF", corpo="#C2DCCB",
         suave="#8FB09B", apagado="#7A9886", destaque="#2BFA59", claro="#8CFFA8", escuro="#13A83C", aceso="#0F2A18",
         brilho="#D6FFE2", tinta_escura="#04140A")
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
OUT = Path(__file__).resolve().parent


def css():
    return f"""
.up{{animation:up .8s cubic-bezier(.2,.7,.2,1) both}}
@keyframes up{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
.run{{stroke-dasharray:9 91;animation:run 7s linear infinite}}
@keyframes run{{to{{stroke-dashoffset:-100}}}}
.shine{{animation:shine 8s ease-in-out infinite}}
@keyframes shine{{0%,72%{{transform:translateX(-420px)}}100%{{transform:translateX(1300px)}}}}
.ok{{stroke-dasharray:24;animation:ok .5s ease both}}
@keyframes ok{{from{{stroke-dashoffset:24}}to{{stroke-dashoffset:0}}}}
.nb{{font:800 15px {SANS};fill:{C['tinta_escura']}}}
.it{{font:600 15px {SANS};fill:{C['tinta']}}}
.hd{{font:700 11px {SANS};letter-spacing:1.6px;fill:{C['destaque']}}}
.nn{{font:400 46px {SERIF};fill:url(#g)}}
.nl{{font:500 13.5px {SANS};fill:{C['corpo']}}}
.mk{{font:400 20px {SERIF};fill:{C['destaque']}}}
.mt{{font:700 16px {SANS};fill:{C['tinta']}}}
.ms{{font:500 12.5px {SANS};fill:{C['suave']}}}
"""


def defs():
    return (f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["claro"]}"/>'
            f'<stop offset="1" stop-color="{C["escuro"]}"/></linearGradient>'
            f'<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="{C["brilho"]}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{C["brilho"]}" stop-opacity=".08"/><stop offset="1" stop-color="{C["brilho"]}" stop-opacity="0"/>'
            f'</linearGradient></defs>')


def moldura(pfx, w, h, rx=18):
    return (f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{rx}" fill="{C["fundo"]}" stroke="{C["borda"]}"/>'
            f'<clipPath id="c{pfx}"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{rx}"/></clipPath>'
            f'<g clip-path="url(#c{pfx})"><g class="shine"><rect x="0" y="-20" width="150" height="{h+40}" fill="url(#sh)" transform="skewX(-18)"/></g></g>'
            f'<rect class="run" x="1" y="1" width="{w-2}" height="{h-2}" rx="{rx}" fill="none" stroke="url(#g)" stroke-width="1.6" pathLength="100"/>')


def salvar(nome, w, h, titulo, corpo, extra=""):
    (OUT / nome).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(titulo)}">\n'
        f'<title>{escape(titulo)}</title>\n<!-- check-pre-lancamento · Paulo Sérgio Dantas · github.com/dantaspaulo/check-pre-lancamento -->\n'
        f'<style>{css()}{extra}</style>\n{defs()}\n{corpo}\n</svg>\n', encoding="utf-8")


def atraso(s):
    return f'style="animation-delay:{s:.2f}s"'


def lista(nome, itens, rotulo, prefixo_num, colunas, largura):
    """Grade de itens numerados (como o post): selo verde com o número + título + traço de 'ok' que desenha."""
    n = len(itens)
    linhas = -(-n // colunas)
    pad, gap, ih = 22, 10, 44
    cw = (largura - 2 * pad - (colunas - 1) * 14) / colunas
    h = 58 + linhas * (ih + gap) - gap + pad
    corpo = [moldura(nome[:3], largura, h), f'<text class="hd" x="{pad}" y="36">{escape(rotulo)}</text>']
    for i, (cid, titulo) in enumerate(itens):
        col, lin = (i // linhas, i % linhas) if colunas > 1 else (0, i)
        x = pad + col * (cw + 14)
        y = 52 + lin * (ih + gap)
        d = 0.15 + i * 0.06
        num = cid[1:] if prefixo_num == "" else cid
        corpo.append(
            f'<g class="up" {atraso(d)}><rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ih}" rx="11" fill="{C["caixa"]}" stroke="{C["borda"]}"/>'
            f'<rect x="{x + 6:.1f}" y="{y + 6}" width="{32 if prefixo_num == "" else 40}" height="{ih - 12}" rx="8" fill="{C["destaque"]}"/>'
            f'<text class="nb" x="{x + (22 if prefixo_num == "" else 26):.1f}" y="{y + 27}" text-anchor="middle">{escape(num)}</text>'
            f'<text class="it" x="{x + (50 if prefixo_num == "" else 58):.1f}" y="{y + 27}">{escape(titulo)}</text>'
            f'<path class="ok" {atraso(d + .35)} d="M{x + cw - 30:.1f} {y + 23} l5 5 l10 -11" fill="none" stroke="{C["destaque"]}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round"/></g>')
    salvar(nome, largura, h, rotulo + ": " + ", ".join(t for _, t in itens), "".join(corpo))


def numeros():
    stacks = 30
    N = [("20", ["checagens", "de segurança"]), ("10", ["itens de", "prontidão"]),
         (f"{len(SECRET_PATTERNS) - 1}+", ["formatos de", "chave secreta"]), (f"{stacks}+", ["stacks e", "plataformas"])]
    tit = ", ".join(f"{v} {' '.join(r)}" for v, r in N)

    def cel(d, cx, v, r):
        return (f'<g class="up" {atraso(d)}><text class="nn" x="{cx}" y="0" text-anchor="middle">{escape(v)}</text></g>'
                f'<g class="up" {atraso(d + .2)}>' + "".join(f'<text class="nl" x="{cx}" y="{30 + k * 19}" text-anchor="middle">{escape(t)}</text>'
                                                         for k, t in enumerate(r)) + "</g>")
    w, h = 860, 156
    colw = w / len(N)
    corpo = [moldura("num", w, h)]
    for i, (v, r) in enumerate(N):
        corpo.append(f'<g transform="translate(0,74)">{cel(.15 + i * .18, colw / 2 + i * colw, v, r)}</g>')
        if i:
            corpo.append(f'<line x1="{i * colw:.1f}" y1="34" x2="{i * colw:.1f}" y2="{h - 34}" stroke="{C["borda"]}"/>')
    salvar("numeros.svg", w, h, tit, "".join(corpo))
    w, h = 420, 270
    corpo = [moldura("nuc", w, h)]
    for i, (v, r) in enumerate(N):
        lin, k = divmod(i, 2)
        corpo.append(f'<g transform="translate(0,{72 + lin * 125})">{cel(.15 + i * .15, 105 + k * 210, v, r)}</g>')
    corpo.append(f'<line x1="28" y1="135" x2="{w - 28}" y2="135" stroke="{C["borda"]}"/>')
    salvar("numeros-celular.svg", w, h, tit, "".join(corpo))


def fluxo():
    S = [("Varredura", ["scanner lê o código,", "o git e o site no ar"]), ("Revisão", ["o agente confirma cada", "achado rota a rota"]),
         ("Relatório", ["veredito, notas e", "evidência com arquivo:linha"]), ("Correção", ["prompts prontos, uma", "task por vez, com commit"])]
    n, ciclo = len(S), 9
    trecho = 75 / (n - 1)
    tit = "Como funciona: " + ", ".join(s for s, _ in S)

    def nos(p):
        return "".join(f"@keyframes {p}{i}{{0%,{max(trecho * i - 1, 0):.0f}%{{fill:{C['fundo']};stroke:{C['borda2']}}}"
                       f"{trecho * i + 3:.0f}%,90%{{fill:{C['aceso']};stroke:{C['destaque']}}}100%{{fill:{C['fundo']};stroke:{C['borda2']}}}}}"
                       f".{p}{i}{{animation:{p}{i} {ciclo}s ease infinite}}" for i in range(n))

    def trilho(eixo, dist):
        return (f".tr{{stroke-dasharray:100;stroke-dashoffset:100;animation:tr {ciclo}s ease-in-out infinite}}"
                f"@keyframes tr{{0%{{stroke-dashoffset:100;opacity:1}}75%,92%{{stroke-dashoffset:0;opacity:1}}100%{{stroke-dashoffset:0;opacity:0}}}}"
                f".pt{{animation:pt {ciclo}s ease-in-out infinite}}"
                f"@keyframes pt{{0%{{transform:translate{eixo}(0);opacity:1}}75%{{transform:translate{eixo}({dist:.1f}px);opacity:1}}92%{{opacity:0}}100%{{transform:translate{eixo}(0);opacity:0}}}}")
    w, h = 860, 196
    xs = [w / n / 2 + i * w / n for i in range(n)]
    corpo = [moldura("flu", w, h), f'<line x1="{xs[0]:.1f}" y1="62" x2="{xs[-1]:.1f}" y2="62" stroke="{C["borda"]}" stroke-width="2"/>',
             f'<line class="tr" x1="{xs[0]:.1f}" y1="62" x2="{xs[-1]:.1f}" y2="62" stroke="{C["destaque"]}" stroke-width="2.4" pathLength="100"/>']
    for i, ((nome, sub), x) in enumerate(zip(S, xs)):
        corpo.append(f'<circle class="fd{i}" cx="{x:.1f}" cy="62" r="22" fill="{C["fundo"]}" stroke="{C["borda2"]}" stroke-width="1.6"/>'
                     f'<text class="mk" x="{x:.1f}" y="69" text-anchor="middle">{i + 1}</text>'
                     f'<g class="up" {atraso(.15 + i * .15)}><text class="mt" x="{x:.1f}" y="120" text-anchor="middle">{escape(nome)}</text>'
                     + "".join(f'<text class="ms" x="{x:.1f}" y="{143 + k * 18}" text-anchor="middle">{escape(t)}</text>' for k, t in enumerate(sub)) + "</g>")
    corpo.append(f'<circle class="pt" cx="{xs[0]:.1f}" cy="62" r="5" fill="{C["claro"]}"/>')
    salvar("fluxo.svg", w, h, tit, "".join(corpo), nos("fd") + trilho("X", xs[-1] - xs[0]))
    ys = [62 + i * 92 for i in range(n)]
    w, h = 420, ys[-1] + 62
    corpo = [moldura("flc", w, h), f'<line x1="56" y1="{ys[0]}" x2="56" y2="{ys[-1]}" stroke="{C["borda"]}" stroke-width="2"/>',
             f'<line class="tr" x1="56" y1="{ys[0]}" x2="56" y2="{ys[-1]}" stroke="{C["destaque"]}" stroke-width="2.4" pathLength="100"/>']
    for i, ((nome, sub), y) in enumerate(zip(S, ys)):
        corpo.append(f'<circle class="fe{i}" cx="56" cy="{y}" r="22" fill="{C["fundo"]}" stroke="{C["borda2"]}" stroke-width="1.6"/>'
                     f'<text class="mk" x="56" y="{y + 7}" text-anchor="middle">{i + 1}</text>'
                     f'<g class="up" {atraso(.15 + i * .15)}><text class="mt" x="96" y="{y - 4}">{escape(nome)}</text>'
                     f'<text class="ms" x="96" y="{y + 16}">{escape(" ".join(sub))}</text></g>')
    corpo.append(f'<circle class="pt" cx="56" cy="{ys[0]}" r="5" fill="{C["claro"]}"/>')
    salvar("fluxo-celular.svg", w, h, tit, "".join(corpo), nos("fe") + trilho("Y", ys[-1] - ys[0]))


def main():
    chk = [(cid, t) for cid, (t, _s) in CHECKS.items()]
    pro = [(cid, t) for cid, (t, _s) in PRONTIDAO.items()]
    lista("checagens.svg", chk, "AS 20 CHECAGENS DE SEGURANÇA", "", 2, 860)
    lista("checagens-celular.svg", chk, "AS 20 CHECAGENS DE SEGURANÇA", "", 1, 420)
    lista("prontidao.svg", pro, "OS 10 ITENS DE PRONTIDÃO PARA O LANÇAMENTO", "P", 2, 860)
    lista("prontidao-celular.svg", pro, "OS 10 ITENS DE PRONTIDÃO", "P", 1, 420)
    numeros()
    fluxo()
    print(f"SVGs gerados em {OUT} (skill v{VERSION})")


if __name__ == "__main__":
    main()
