#!/usr/bin/env python3
# check-pre-lancamento · scanner de triagem (20 checagens de segurança + 10 de prontidão)
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
# Aviso obrigatório: mantenha estas linhas e os créditos de autoria em qualquer cópia ou derivado.
"""check-pre-lancamento · scanner de triagem das 20 checagens + 10 de prontidão.

Uso:
    python3 scan.py [RAIZ] [--out ARQUIVO.json] [--no-git-history] [--no-audit] [--ignorar PASTA] [--varrer-tudo] [--quiet]

Só stdlib. Não altera nada no projeto. Gera um JSON com achados por checagem
(arquivo:linha, trecho com segredos mascarados, confiança) e sinais de contexto
(stack, plataforma, libs presentes, rotas encontradas). É TRIAGEM: falso positivo existe e
"sem achados" não prova que está seguro — a decisão final é feita lendo o código.
Cobre apps de plataforma (Lovable, Bolt, v0, Replit, Base44…) e código próprio de front e back
(React, Next, Vue/Nuxt, Angular, Svelte, Node, Laravel, Django, Rails, Spring, .NET, Go…).
"""
import argparse
import bisect
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    AUTORIA, CHECKS, CREDITO, PRONTIDAO, PUBLIC_ENV_ALLOW, PUBLIC_ENV_PREFIXES, SECRET_ENV_HINTS, SECRET_PATTERNS,
    VERSION, banner, creditos_intactos, decode_jwt_payload, iter_secret_matches, looks_placeholder, looks_random,
    mask, mask_secrets,
)

ALL_IDS = {**CHECKS, **PRONTIDAO}
SKIP_DIRS = {
    ".git", "node_modules", ".next", ".nuxt", ".svelte-kit", ".output", ".vercel", ".netlify",
    "dist", "build", "out", "coverage", ".turbo", ".cache", ".parcel-cache", "vendor", "venv",
    ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", "target", "bin", "obj",
    ".idea", ".vscode", ".expo", "Pods", ".gradle", ".dart_tool", "check-report", ".terraform",
    "storybook-static", ".docusaurus", "bower_components", "jspm_packages", ".yarn", ".angular",
    ".astro", ".wrangler", ".serverless", ".aws-sam", ".firebase", "pb_data", "DerivedData", ".vinxi",
    ".react-router", ".pnpm-store", "site-packages", ".bundle", "tmp",
}
CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro",
            ".py", ".rb", ".php", ".go", ".java", ".kt", ".cs", ".rs", ".dart", ".swift", ".erb", ".ex", ".exs",
            ".razor", ".cshtml", ".scala", ".groovy"}
CONFIG_EXT = {".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".rules", ".xml", ".properties",
              ".tf", ".plist", ".gradle", ".kts", ".csproj", ".env", ".hcl", ".sh", ".bash", ".zsh", ".ps1", ".nix", ".mod"}
SQL_EXT = {".sql", ".prisma", ".graphql", ".gql"}
DOC_EXT = {".md", ".mdx", ".txt", ".html", ".htm", ".rst"}
NOEXT_NAMES = {"Dockerfile", "Containerfile", "_headers", "_redirects", ".npmrc", ".yarnrc", ".pypirc", "Procfile",
               "Caddyfile", "nginx.conf", ".htaccess", "Makefile", ".netrc", ".dev.vars", ".envrc", "Gemfile",
               "Pipfile", "Podfile", "Jenkinsfile", ".replit", ".cursorrules", ".windsurfrules", "CNAME"}
MAX_FILES = 25_000
# Pastas de skills/worktrees de agentes de código: não são código do app (e esta skill pode estar lá).
AGENT_DIR_RX = re.compile(r"(^|/)\.(?:claude|agents|cursor|github|codex|gemini|opencode|windsurf|devin|kiro|goose)/"
                          r"(?:skills|worktrees|plugins)$")
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock", "poetry.lock",
             "Pipfile.lock", "Gemfile.lock", "composer.lock", "Cargo.lock", "go.sum", "uv.lock"}
MAX_FILE = 1_500_000
TEST_PATH_RX = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e|cypress|playwright|fixtures?|mocks?|__mocks__|stories)/|"
                          r"\.(spec|test|stories)\.[cm]?[jt]sx?$|(^|/)test_[\w]+\.py$|_test\.(py|go)$")
GENERATED_RX = re.compile(r"\.gen\.|\.generated\.|(^|/)(__generated__|generated)/|\.d\.ts$")
MAX_PER_RULE = 25
JWT_RX = next(rx for pid, rx, _c, _d in SECRET_PATTERNS if pid == "jwt")

ENV_FILE_RX = re.compile(r"^\.env(\..+)?$|^\.dev\.vars$|^\.envrc$")
ENV_EXAMPLE_RX = re.compile(r"\.(example|sample|template|dist|defaults?)$", re.I)
SENSITIVE_TRACKED_RX = re.compile(
    r"(^|/)(\.env(\.[\w.-]+)?|\.envrc|\.dev\.vars|id_rsa|id_ed25519|id_ecdsa|[\w.-]*\.pem|[\w.-]*\.key|[\w.-]*\.p12|"
    r"[\w.-]*\.pfx|[\w.-]*\.jks|[\w.-]*\.keystore|credentials\.json|service[-_]?account[\w.-]*\.json|"
    r"serviceAccountKey[\w.-]*\.json|[\w.-]*firebase-adminsdk[\w.-]*\.json|\.npmrc|\.pypirc|\.netrc|"
    r"[\w.-]*\.sqlite3?|[\w.-]*\.db|[\w.-]*\.dump|[\w.-]*\.sql\.gz)$", re.I)


def is_env_example(name):
    return bool(ENV_EXAMPLE_RX.search(name))


def is_sensitive_path(rel):
    rel = rel.replace("\\", "/")
    if not SENSITIVE_TRACKED_RX.search(rel):
        return False
    base = rel.rsplit("/", 1)[-1]
    if base.startswith(".env") and is_env_example(base):
        return False
    if base.endswith(".key") and ("i18n" in rel or "locale" in rel):
        return False
    return True


# ----------------------------------------------------------------------------- utilidades

class SourceFile:
    __slots__ = ("rel", "path", "text", "ext", "name", "kind", "_offsets", "_lines", "side", "zona", "_code", "_code_lines")

    def __init__(self, root, path, text):
        self.path = path
        self.rel = str(path.relative_to(root)).replace("\\", "/").encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        self.text = text
        self.name = path.name
        self.ext = path.suffix.lower()
        if self.name.startswith(".env") or self.name in (".dev.vars", ".envrc"):
            self.kind = "env"
        elif self.ext in CODE_EXT:
            self.kind = "code"
        elif self.ext in SQL_EXT:
            self.kind = "sql"
        elif self.ext in DOC_EXT:
            self.kind = "doc"
        else:
            self.kind = "config"
        self._offsets = None
        self._lines = None
        self.side = None
        self.zona = "app"
        self._code = None
        self._code_lines = None

    @property
    def lines(self):
        if self._lines is None:
            self._lines = self.text.split("\n")
        return self._lines

    @property
    def code(self):
        """Texto sem comentários (mesmo tamanho, mesmas linhas). Só em código, SQL e HTML; o resto volta igual."""
        if self._code is None:
            comenta = self.kind in ("code", "sql") or self.ext in (".html", ".htm", ".rules") or self.name == "database.rules.json"
            self._code = tirar_comentarios(self.text, self.ext) if comenta else self.text
        return self._code

    @property
    def code_lines(self):
        if self._code_lines is None:
            self._code_lines = self.code.split("\n")
        return self._code_lines

    def lineno(self, offset):
        if self._offsets is None:
            offs = [0]
            for i, ch in enumerate(self.text):
                if ch == "\n":
                    offs.append(i + 1)
            self._offsets = offs
        return bisect.bisect_right(self._offsets, offset)

    def line(self, n):
        ls = self.lines
        return ls[n - 1] if 0 < n <= len(ls) else ""

    def window(self, n, before=3, after=3, codigo=False):
        ls = self.code_lines if codigo else self.lines
        return "\n".join(ls[max(0, n - 1 - before): min(len(ls), n + after)])


def snippet(text):
    s = mask_secrets(text.strip()[:2000])
    return s[:180] + ("…" if len(s) > 180 else "")


def chunks(ln, size=4000, overlap=400):
    """Pedaços com sobreposição para linhas longas (bundle minificado): segredo no meio não escapa."""
    if len(ln) <= size:
        yield 0, ln
        return
    for i in range(0, len(ln), size - overlap):
        yield i, ln[i:i + size]


def run(cmd, cwd, timeout=60, inp=None):
    cmd = [shutil.which(cmd[0]) or cmd[0]] + list(cmd[1:])
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=inp,
                           encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # pragma: no cover
        return 1, "", str(e)


def parse_version(v):
    if not v:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)(?:-([\w.]+))?", v)
    if not m:
        m2 = re.search(r"(\d+)(?:\.(\d+))?", v)
        if not m2:
            return None
        return (int(m2.group(1)), int(m2.group(2) or 0), 0, None)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


# ----------------------------------------------------------------------------- comentários
# O texto de cada comentário vira espaço e as quebras de linha ficam: offsets e números de linha continuam
# valendo, e nenhuma regra dispara em código comentado, nota ou TODO. Strings são respeitadas.
_NAO_QUEBRA = re.compile(r"[^\n]")
_STR_LINHA = r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
_STR_CRASE = r"`(?:\\.|[^`\\]){0,100000}`"
_COM_C = r"/\*[\s\S]*?\*/|(?<![:\\])//[^\n]*"
_COM_HTML = r"<!--[\s\S]*?-->"
_COMENTARIO_RX = {
    "c": re.compile(rf"(?P<s>{_STR_LINHA}|{_STR_CRASE})|(?P<c>{_COM_C})"),
    "c_html": re.compile(rf"(?P<s>{_STR_LINHA}|{_STR_CRASE})|(?P<c>{_COM_HTML}|{_COM_C})"),
    "html": re.compile(rf"(?P<s>{_STR_LINHA})|(?P<c>{_COM_HTML})"),
    "php": re.compile(rf"(?P<s>{_STR_LINHA})|(?P<c>{_COM_HTML}|{_COM_C}|#(?!\[)[^\n]*)"),
    "hash": re.compile(r'(?P<s>"""[\s\S]{0,200000}?"""|\'\'\'[\s\S]{0,200000}?\'\'\'|' + _STR_LINHA + r")|(?P<c>(?<![$?])#(?!\{)[^\n]*)"),
    "sql": re.compile(r"(?P<s>'(?:''|[^']){0,100000}'|\"(?:\"\"|[^\"\n]){0,1000}\")|(?P<c>--[^\n]*|/\*[\s\S]*?\*/)"),
}
_MODO_COMENTARIO = {".py": "hash", ".rb": "hash", ".ex": "hash", ".exs": "hash", ".graphql": "hash", ".gql": "hash",
                    ".php": "php", ".sql": "sql", ".erb": "html", ".html": "html", ".htm": "html", ".vue": "c_html",
                    ".svelte": "c_html", ".astro": "c_html", ".razor": "c_html", ".cshtml": "c_html"}


def tirar_comentarios(text, ext):
    if not any(m in text for m in ("//", "/*", "#", "--", "<!--")):
        return text
    rx = _COMENTARIO_RX[_MODO_COMENTARIO.get(ext, "c")]
    return rx.sub(lambda m: m.group(0) if m.group("c") is None else _NAO_QUEBRA.sub(" ", m.group("c")), text)


# ----------------------------------------------------------------------------- .gitignore e --ignorar
def _padrao_para_regex(pat):
    """Padrão no formato do .gitignore → regex sobre o caminho relativo (separador '/')."""
    so_pasta = pat.endswith("/")
    pat = pat.rstrip("/")
    ancorado = "/" in pat
    pat = pat.lstrip("/")
    i, out = 0, []
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pat.startswith("/**", i) and i + 3 == len(pat):
            out.append("/.*")
            i += 3
            continue
        if pat.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        c = pat[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[" and pat.find("]", i + 2) != -1:
            j = pat.find("]", i + 2)
            corpo = pat[i + 1:j]
            out.append("[" + ("^" + corpo[1:] if corpo.startswith("!") else corpo).replace("\\", "\\\\") + "]")
            i = j
        elif c == "\\" and i + 1 < len(pat):
            i += 1
            out.append(re.escape(pat[i]))
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + ("" if ancorado else "(?:.*/)?") + "".join(out) + ("/.+" if so_pasta else "(?:/.*)?") + "$")


def ler_padroes(texto, base=""):
    """Linhas no formato do .gitignore → [(negado, regex, pasta_base, texto_original)]."""
    pads = []
    for ln in texto.splitlines():
        ln = re.sub(r"(?<!\\)[ \t]+$", "", ln.rstrip("\r"))
        if not ln or ln.startswith("#"):
            continue
        neg = ln.startswith("!")
        if neg:
            ln = ln[1:]
        if ln.startswith(("\\#", "\\!")):
            ln = ln[1:]
        if ln.strip("/"):
            try:
                pads.append((neg, _padrao_para_regex(ln), base, ("!" if neg else "") + ln))
            except re.error:
                continue  # padrão que o scanner não entende: segue sem ele
    return pads


def casa_padroes(pads, rel):
    """Último padrão que casa decide (como no git). Devolve o texto do padrão que ignorou, ou None."""
    quem = None
    for neg, rx, base, txt in pads:
        if base and not rel.startswith(base):
            continue
        if rx.match(rel[len(base):] if base else rel):
            quem = None if neg else txt
    return quem


# Pastas da raiz que não entram no app publicado: documentação e exemplos (com package.json próprio, são app).
FORA_DO_BUILD = {"docs", "doc", "documentation", "documentacao", "documentação", "examples", "example", "exemplos",
                 "exemplo", "samples", "sample"}
ARQUIVO_IGNORAR = ".check-pre-lancamento-ignore"


# ----------------------------------------------------------------------------- SQL em comandos
_SQL_TOKEN = re.compile(r"\$(?:[A-Za-z_]\w*)?\$|'(?:''|[^']){0,100000}'|;")
_CORPO_DOLAR = re.compile(r"\$(\w*)\$[\s\S]*?\$\1\$")


def sql_comandos(code):
    """[(offset, texto normalizado sem corpo de função, texto cru)] de cada comando SQL.
    Recebe o texto já sem comentários; respeita strings e corpos $$...$$ (que têm ';' dentro)."""
    out, ini, tag = [], 0, None
    for m in _SQL_TOKEN.finditer(code):
        tok = m.group(0)
        if tag is not None:
            if tok == tag:
                tag = None
            continue
        if tok.startswith("$"):
            tag = tok
            continue
        if tok == ";":
            out.append((ini, code[ini:m.end()]))
            ini = m.end()
    if code[ini:].strip():
        out.append((ini, code[ini:]))
    res = []
    for off, cru in out:
        lead = len(cru) - len(cru.lstrip())
        norm = re.sub(r"\s+", " ", _CORPO_DOLAR.sub("$$", cru).replace('"', "")).strip().rstrip(";").strip().lower()
        if norm:
            res.append((off + lead, norm, cru))
    return res


def _nome_sql(n):
    n = n.strip().replace('"', "").lower()
    return n if "." in n else "public." + n


# Palavras do nome da tabela que indicam catálogo (dado de referência) ou dado de usuário.
_CATALOGO = {"cid", "cbhpm", "tuss", "cnae", "ncm", "cfop", "ibge", "cep", "ceps", "pais", "paises", "country", "countries",
             "estado", "estados", "state", "states", "uf", "ufs", "cidade", "cidades", "city", "cities", "municipio", "municipios",
             "bairro", "bairros", "categoria", "categorias", "category", "categories", "tipo", "tipos", "type", "types", "tag",
             "tags", "plano", "planos", "plan", "plans", "preco", "precos", "price", "prices", "pricing", "faq", "faqs", "feriado",
             "feriados", "holiday", "holidays", "moeda", "moedas", "currency", "currencies", "idioma", "idiomas", "language",
             "languages", "especialidade", "especialidades", "specialty", "specialties", "procedimento", "procedimentos",
             "catalog", "catalogo", "catalogs", "lookup", "lookups", "referencia", "referencias", "tabela", "tabelas", "enum",
             "enums", "status", "unidade", "unidades", "unit", "units", "feature", "features", "product", "products",
             "produto", "produtos", "config", "configs", "configuracao", "configuracoes"}
_DADO_PESSOAL = {"user", "users", "usuario", "usuarios", "profile", "profiles", "perfil", "perfis", "cliente", "clientes",
                 "customer", "customers", "paciente", "pacientes", "patient", "patients", "pedido", "pedidos", "order", "orders",
                 "payment", "payments", "pagamento", "pagamentos", "invoice", "invoices", "fatura", "faturas", "message",
                 "messages", "mensagem", "mensagens", "chat", "chats", "conversa", "conversas", "document", "documents",
                 "documento", "documentos", "file", "files", "arquivo", "arquivos", "appointment", "appointments",
                 "agendamento", "agendamentos", "consulta", "consultas", "prontuario", "prontuarios", "address", "addresses",
                 "endereco", "enderecos", "card", "cards", "cartao", "cartoes", "subscription", "subscriptions", "assinatura",
                 "assinaturas", "transaction", "transactions", "transacao", "transacoes", "lead", "leads", "contact",
                 "contacts", "contato", "contatos", "note", "notes", "nota", "notas", "account", "accounts", "conta", "contas",
                 "member", "members", "membro", "membros", "session", "sessions", "token", "tokens", "log", "logs", "audit",
                 "employee", "employees", "funcionario", "funcionarios", "aluno", "alunos", "student", "students"}


def tipo_de_tabela(nome):
    """'catalogo', 'pessoal' ou '' pelo nome da tabela (a última palavra pesa mais: user_types é catálogo)."""
    pals = [re.sub(r"\d+$", "", p) for p in nome.split(".")[-1].split("_") if p]
    if not pals:
        return ""
    if pals[-1] in _CATALOGO:
        return "catalogo"
    if any(p in _DADO_PESSOAL for p in pals):
        return "pessoal"
    return "catalogo" if any(p in _CATALOGO for p in pals) else ""


# ----------------------------------------------------------------------------- dependências só de build
FERRAMENTA_DE_BUILD_RX = re.compile(
    r"^(?:vite|esbuild|rollup|webpack(?:-cli|-dev-server)?|rspack|@rspack/.+|parcel|turbo|typescript|ts-node|tsx|tsup|"
    r"@vitejs/.+|vite-plugin-.+|@vite-pwa/.+|tailwindcss|@tailwindcss/.+|postcss(?:-.+)?|autoprefixer|sass|less|stylus|terser|"
    r"@babel/.+|babel-.+|@swc/.+|eslint(?:-.+)?|@eslint/.+|@typescript-eslint/.+|prettier(?:-.+)?|@types/.+|lovable-tagger|"
    r"vitest|@vitest/.+|jest(?:-.+)?|@jest/.+|playwright|@playwright/.+|cypress|@testing-library/.+|nodemon|concurrently|"
    r"cross-env|husky|lint-staged|@commitlint/.+|drizzle-kit|prisma|supabase|wrangler|vercel|netlify-cli|@cloudflare/workers-types|"
    r"@storybook/.+|storybook|rimraf|npm-run-all2?|dotenv-cli|@biomejs/biome|knip|depcheck|patch-package|eslint-config-next|"
    r"@next/eslint-plugin-next|@nuxt/devtools|@sveltejs/vite-plugin-svelte|@sveltejs/adapter-.+|@astrojs/check|electron-builder|"
    r"@electron-forge/.+|@tauri-apps/cli|@capacitor/cli)$")
ARQUIVO_DE_BUILD_RX = re.compile(r"(^|/)[\w.-]*\.config\.[cm]?[jt]sx?$|(^|/)(scripts|tools|\.storybook|\.husky|bin)/|"
                                 r"(^|/)(gulpfile|gruntfile|webpack\.[\w.-]+|rollup\.[\w.-]+)\.[cm]?[jt]s$", re.I)


# ----------------------------------------------------------------------------- scanner

class Scanner:
    def __init__(self, root, args):
        self.root = Path(root).resolve()
        self.args = args
        self.files = []
        self.skipped = 0
        self.truncated = False
        self.findings = {cid: [] for cid in ALL_IDS}
        self.rule_counts = {}
        self.omitted = {}
        self.signals = {cid: {} for cid in ALL_IDS}
        self.deps = set()
        self.dev_only = set()
        self.dep_versions = {}
        self.py_deps = set()
        self.pkg_scripts = {}
        self.stack = {}
        self.platform = []
        self.app_roots = []  # pastas de app que vira binário (Electron, Tauri, extensão): lá dentro tudo é cliente
        self.public_prefixes = list(PUBLIC_ENV_PREFIXES)
        self.tools = {}
        self.git = {"repo": False}
        self.routes = []
        self.avisos = []
        self.so_segredos = []  # fora do build ou --ignorar: ainda passam pela busca de segredo
        self.zonas = {}
        self._gitignores = []
        self._uso_cache = {}

    # -- registro --------------------------------------------------------------
    def add(self, cid, rule, f=None, line=None, text=None, conf="media", note=""):
        key = (cid, rule)
        self.rule_counts[key] = self.rule_counts.get(key, 0) + 1
        if self.rule_counts[key] > MAX_PER_RULE:
            self.omitted[key] = self.omitted.get(key, 0) + 1
            return
        rel = f if isinstance(f, str) else (f.rel if f is not None else "")
        if cid not in ("C01", "C02") and rel and TEST_PATH_RX.search(rel):
            conf, note = "baixa", note + " (arquivo de teste)"
        item = {"regra": rule, "confianca": conf, "nota": note}
        if f is not None:
            item["arquivo"] = f if isinstance(f, str) else f.rel
        if line:
            item["linha"] = line
        if text is not None:
            item["trecho"] = snippet(text)
        self.findings[cid].append(item)

    def rx_rule(self, cid, rule, rx, files, conf, note, skip_line=None, near=None, near_window=5, flags=0, comentarios=False):
        """Regra por regex. Por padrão não olha comentários (código comentado não roda); comentarios=True olha."""
        pattern = re.compile(rx, flags) if isinstance(rx, str) else rx
        for f in files:
            for m in pattern.finditer(f.text if comentarios else f.code):
                n = f.lineno(m.start())
                ln = f.line(n)
                if skip_line and re.search(skip_line, ln):
                    continue
                if near and not re.search(near, f.window(n, near_window, near_window, codigo=not comentarios), re.I):
                    continue
                if len(ln) > 400:  # linha minificada: o trecho é a vizinhança do achado
                    col = m.start() - (f._offsets[n - 1] if f._offsets else 0)
                    ln = "…" + ln[max(0, col - 80): col + 200] + "…"
                self.add(cid, rule, f, n, ln, conf, note)

    # -- coleta ----------------------------------------------------------------
    def collect(self):
        lidos = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = os.path.relpath(dirpath, self.root).replace("\\", "/")
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d != ".git"
                           and not AGENT_DIR_RX.search(f"{rel_dir}/{d}")]
            if ".gitignore" in filenames:
                self._gitignores.append("" if rel_dir == "." else rel_dir + "/")
            if len(lidos) >= MAX_FILES:
                self.truncated = True
                break
            for fn in filenames:
                p = Path(dirpath) / fn
                ext = p.suffix.lower()
                if fn in LOCKFILES or fn.endswith((".min.js", ".min.css", ".map", ".chunk.js")):
                    continue
                if GENERATED_RX.search(str(Path(dirpath, fn).relative_to(self.root)).replace("\\", "/")):
                    continue
                if not (ext in CODE_EXT or ext in CONFIG_EXT or ext in SQL_EXT or ext in DOC_EXT
                        or fn in NOEXT_NAMES or fn.startswith(".env")):
                    continue
                try:
                    st = p.stat()
                    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:  # FIFO, /dev/zero, socket…
                        self.skipped += 1
                        continue
                    raw = p.read_bytes()
                except Exception:
                    self.skipped += 1
                    continue
                if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                    text = raw.decode("utf-16", "replace")  # .env salvo pelo PowerShell
                elif b"\x00" in raw[:2000]:
                    self.skipped += 1  # binário
                    continue
                else:
                    text = raw.decode("utf-8-sig", "replace")
                lidos.append(SourceFile(self.root, p, text))
        self.classificar_zonas(lidos)
        # .env fica sempre (o que tem prefixo público vai pro bundle mesmo ignorado pelo git), menos dentro de pasta ignorada
        self.files = [f for f in lidos if f.zona == "app" or (f.kind == "env" and f.zona != "gitignore_pasta")]
        # zip sem git não diz o que está versionado, e arquivo ignorado vai para o deploy feito da máquina: segredo é procurado em tudo
        self.so_segredos = [f for f in lidos if f.zona != "app" and f.kind != "env"]

    def classificar_zonas(self, arquivos):
        """Marca o que fica fora das regras de código: .gitignore, pastas fora do build (docs/, examples/) e --ignorar."""
        z = {"metodo_gitignore": None, "padroes_ignorar": [], "gitignore": {}, "fora_do_build": {}, "ignorado": {}}
        self.zonas = z
        if getattr(self.args, "varrer_tudo", False):
            z["metodo_gitignore"] = "desligado (--varrer-tudo)"
            return
        rels = [f.rel for f in arquivos]
        pastas = sorted({"/".join(r.split("/")[:k]) + "/" for r in rels for k in range(1, r.count("/") + 1)})
        ign_arq, ign_pasta = set(), set()
        rc, out = 1, ""
        if rels:
            rc, out, _e = run(["git", "-c", "core.quotePath=false", "check-ignore", "--stdin", "-z"], self.root, 60,
                              inp="\0".join(rels + pastas) + "\0")
        if rc in (0, 1) and rels:
            z["metodo_gitignore"] = "git check-ignore (respeita .gitignore, .git/info/exclude e o exclude global)"
            hits = {p for p in out.split("\0") if p}
            ign_pasta = {p for p in hits if p.endswith("/")}
            ign_arq = hits - ign_pasta
        elif self._gitignores:
            z["metodo_gitignore"] = ".gitignore lido pelo scanner (pasta sem git)"
            pads = []
            for base in sorted(self._gitignores, key=len):
                try:
                    pads += ler_padroes((self.root / base / ".gitignore").read_text(errors="ignore"), base)
                except Exception:
                    pass
            ign_pasta = {d for d in pastas if casa_padroes(pads, d + "\x00")}
            ign_arq = {r for r in rels if casa_padroes(pads, r)}
        else:
            z["metodo_gitignore"] = "sem .gitignore"
        pedidos = [p.strip() for a in (getattr(self.args, "ignorar", None) or []) for p in a.split(",") if p.strip()]
        arq = self.root / ARQUIVO_IGNORAR
        if arq.is_file():
            try:
                pedidos += arq.read_text(errors="ignore").splitlines()
                z["arquivo_ignorar"] = ARQUIVO_IGNORAR
            except Exception:
                pass
        user_pads = ler_padroes("\n".join(re.sub(r"^\./", "", p.strip()) for p in pedidos))
        z["padroes_ignorar"] = [t for *_x, t in user_pads]
        # pasta com package.json ou com site publicado (GitHub Pages serve /docs) é app, não documentação
        com_package = {f.rel.split("/")[0] for f in arquivos if f.rel.count("/") == 1 and
                       f.name in ("package.json", "index.html", "CNAME", "_config.yml")}
        for f in arquivos:
            partes = f.rel.split("/")
            topo = next((d for d in ("/".join(partes[:k]) + "/" for k in range(1, len(partes))) if d in ign_pasta), None)
            if topo:
                f.zona, chave, grupo = "gitignore_pasta", "gitignore", topo
            elif f.rel in ign_arq:
                f.zona, chave, grupo = "gitignore", "gitignore", f.rel
                if f.kind == "env":
                    continue  # continua sendo lido
            elif user_pads and casa_padroes(user_pads, f.rel):
                f.zona, chave, grupo = "ignorado", "ignorado", casa_padroes(user_pads, f.rel)
            elif len(partes) > 1 and partes[0].lower() in FORA_DO_BUILD and partes[0] not in com_package:
                f.zona, chave, grupo = "fora_do_build", "fora_do_build", partes[0] + "/"
            else:
                continue
            z[chave][grupo] = z[chave].get(grupo, 0) + 1

    def resumo_zonas(self):
        z = self.zonas or {}

        def bloco(d):
            itens = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
            return {"arquivos": sum(d.values()), "pastas": [{"caminho": k, "arquivos": v} for k, v in itens[:15]],
                    "mais_pastas": max(0, len(itens) - 15)}
        out = {"gitignore": z.get("metodo_gitignore"), "ignorados_pelo_gitignore": bloco(z.get("gitignore", {})),
               "fora_do_build": bloco(z.get("fora_do_build", {})),
               "ignorados_a_pedido": {**bloco(z.get("ignorado", {})), "padroes": z.get("padroes_ignorar", [])}}
        if z.get("arquivo_ignorar"):
            out["ignorados_a_pedido"]["arquivo"] = z["arquivo_ignorar"]
        partes = []
        for chave, rotulo in (("ignorados_pelo_gitignore", "do .gitignore"), ("fora_do_build", "fora do build"),
                              ("ignorados_a_pedido", "por --ignorar/" + ARQUIVO_IGNORAR)):
            b = out[chave]
            if b["arquivos"]:
                nomes = ", ".join(p["caminho"] for p in b["pastas"][:4]) + ("…" if len(b["pastas"]) > 4 else "")
                partes.append(f"{b['arquivos']} {rotulo} ({nomes})")
        if partes:
            self.avisos.append("Fora das regras de código: " + "; ".join(partes) + ". Segredos continuam sendo procurados em "
                               "todas essas pastas (no que o .gitignore ignora, com confiança baixa: não vai para o Git, mas vaza se "
                               "entrar no build). Use --varrer-tudo para incluir tudo.")
        return out

    def code(self):
        return [f for f in self.files if f.kind == "code"]

    def server_code(self):
        return [f for f in self.code() if f.side != "client"]

    def client_code(self):
        return [f for f in self.code() if f.side == "client"]

    # -- dependências e stack --------------------------------------------------
    def load_deps(self):
        for f in self.files:
            if f.name == "package.json":
                try:
                    data = json.loads(f.text)
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    block = data.get(key)
                    if not isinstance(block, dict):
                        continue
                    if key in ("dependencies", "devDependencies") and "electron" in block:
                        self.app_roots.append(f.rel.rsplit("/", 1)[0] + "/" if "/" in f.rel else "")
                    for name, ver in block.items():
                        self.deps.add(name.lower())
                        if key == "devDependencies":
                            self.dev_only.add(name.lower())
                        if key == "dependencies" or name.lower() not in self.dep_versions:
                            self.dep_versions[name.lower()] = str(ver)
                if isinstance(data.get("scripts"), dict):
                    for k, v in data["scripts"].items():
                        self.pkg_scripts[f"{f.rel}:{k}"] = str(v)
            elif f.name.startswith("requirements") and f.ext in (".txt", ".in"):
                for ln in f.lines:
                    ln = ln.split("#")[0].strip()
                    if ln and not ln.startswith("-"):
                        self.py_deps.add(re.split(r"[=<>~!;\[ ]", ln, 1)[0].lower())
            elif f.name in ("pyproject.toml", "Pipfile"):
                for m in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(?:[=<>~!]=?|"|\s*=)', f.text, re.M):
                    self.py_deps.add(m.group(1).lower())
            elif f.name == "Gemfile":
                for m in re.finditer(r"gem\s+['\"]([\w\-]+)", f.text):
                    self.deps.add("gem:" + m.group(1).lower())
            elif f.name == "composer.json":
                try:
                    data = json.loads(f.text)
                    for key in ("require", "require-dev"):
                        block = data.get(key) if isinstance(data, dict) else None
                        for name in (block if isinstance(block, dict) else {}):
                            self.deps.add("composer:" + name.lower())
                            if key == "require-dev":
                                self.dev_only.add("composer:" + name.lower())
                except Exception:
                    pass
            elif f.name == "go.mod":
                for m in re.finditer(r"(?m)^\s*(?:require\s+)?([a-z0-9.\-]+\.[a-z]{2,}/[\w.\-/]+)\s+v\d", f.text):
                    self.deps.add("go:" + m.group(1).lower())
            elif f.name == "pom.xml":
                for m in re.finditer(r"<artifactId>\s*([\w.\-]+)\s*</artifactId>", f.text):
                    self.deps.add("mvn:" + m.group(1).lower())
            elif f.name in ("build.gradle", "build.gradle.kts"):
                for m in re.finditer(r"['\"]([\w.\-]+):([\w.\-]+)(?::[^'\"]*)?['\"]", f.text):
                    self.deps.add("mvn:" + m.group(2).lower())
            elif f.ext == ".csproj":
                for m in re.finditer(r"<PackageReference\s+Include=\"([^\"]+)\"", f.text):
                    self.deps.add("nuget:" + m.group(1).lower())
                if re.search(r"Sdk=\"Microsoft\.NET\.Sdk\.Web\"", f.text):
                    self.deps.add("nuget:microsoft.aspnetcore")
            elif f.name == "Cargo.toml":
                sec = re.search(r"(?ms)^\[dependencies\](.*?)(?:^\[|\Z)", f.text)
                for m in re.finditer(r"(?m)^\s*([\w\-]+)\s*=", sec.group(1) if sec else ""):
                    self.deps.add("cargo:" + m.group(1).lower())
            elif f.name == "pubspec.yaml":
                for m in re.finditer(r"(?m)^\s{2}([a-z0-9_]+):", f.text):
                    self.deps.add("pub:" + m.group(1).lower())
                if re.search(r"(?m)^\s+sdk:\s*flutter", f.text):
                    self.deps.add("pub:flutter")
            elif f.name == "mix.exs":
                for m in re.finditer(r"\{:([a-z0-9_]+),", f.text):
                    self.deps.add("hex:" + m.group(1).lower())

        def has(*names):
            return any(n in self.deps for n in names)

        def has_prefix(*prefixes):
            return any(d.startswith(p) for d in self.deps for p in prefixes)

        def py(*names):
            return any(n in self.py_deps for n in names)

        paths = {f.rel for f in self.files}
        s = {}
        s["nextjs"] = has("next")
        s["next_app_router"] = s["nextjs"] and any(re.search(r"(^|/)app/(.*/)?(page|layout|route)\.(t|j)sx?$", p) for p in paths)
        s["nuxt"] = has("nuxt")
        s["remix"] = has_prefix("@remix-run/")
        s["sveltekit"] = has("@sveltejs/kit")
        s["astro"] = has("astro")
        s["vite"] = has("vite")
        s["cra"] = has("react-scripts")
        s["react"] = has("react")
        s["vue"] = has("vue")
        s["expo_rn"] = has("expo", "react-native")
        s["express"] = has("express")
        s["fastify"] = has("fastify")
        s["nestjs"] = has("@nestjs/core")
        s["hono"] = has("hono")
        s["supabase"] = has("@supabase/supabase-js", "@supabase/ssr") or py("supabase") or any(p.startswith("supabase/") for p in paths)
        s["firebase"] = has("firebase", "firebase-admin") or any(p.endswith(("firestore.rules", "database.rules.json")) for p in paths)
        s["prisma"] = has("prisma", "@prisma/client")
        s["drizzle"] = has("drizzle-orm")
        s["mongoose"] = has("mongoose", "mongodb")
        s["django"] = py("django")
        s["flask"] = py("flask")
        s["fastapi"] = py("fastapi")
        s["rails"] = "gem:rails" in self.deps
        s["laravel"] = "composer:laravel/framework" in self.deps
        s["flutter"] = any(p.endswith("pubspec.yaml") for p in paths)
        s["vercel"] = any(p in ("vercel.json",) for p in paths) or (self.root / ".vercel").exists()
        s["netlify"] = any(p in ("netlify.toml", "_headers", "public/_headers") for p in paths)
        s["cloudflare"] = any(p.startswith("wrangler.") for p in paths)
        s["docker"] = any(p.endswith(("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml")) for p in paths)
        s["llm_sdk"] = has("openai", "@anthropic-ai/sdk", "ai", "langchain", "@langchain/core", "@google/generative-ai",
                           "@google/genai", "groq-sdk", "@mistralai/mistralai", "ollama", "replicate", "cohere-ai") \
            or has_prefix("@ai-sdk/") or py("openai", "anthropic", "langchain", "google-generativeai", "google-genai", "litellm", "groq")
        # front-end e app cliente
        s["angular"] = has("@angular/core")
        s["svelte"] = has("svelte") and not s["sveltekit"]
        s["solid"] = has("solid-js", "@solidjs/start")
        s["qwik"] = has("@builder.io/qwik")
        s["react_router7"] = has("@react-router/dev", "@react-router/node")
        s["gatsby"] = has("gatsby")
        s["electron"] = has("electron")
        s["tauri"] = has("@tauri-apps/api", "@tauri-apps/cli") or any(p.startswith("src-tauri/") for p in paths)
        s["capacitor"] = has("@capacitor/core", "@ionic/angular", "@ionic/react", "@ionic/vue")
        s["browser_extension"] = any(f.name == "manifest.json" and '"manifest_version"' in f.text for f in self.files)
        s["android"] = any(p.endswith("AndroidManifest.xml") for p in paths)
        s["ios"] = any(p.endswith("Info.plist") for p in paths)
        # back-end JS/TS
        s["koa"] = has("koa")
        s["hapi"] = has("@hapi/hapi")
        s["adonis"] = has("@adonisjs/core")
        s["elysia"] = has("elysia")
        s["trpc"] = has("@trpc/server")
        s["graphql"] = has("graphql", "@apollo/server", "graphql-yoga", "type-graphql", "@nestjs/graphql", "mercurius")
        # BaaS e auth
        s["convex"] = has("convex") or any(p.startswith("convex/") for p in paths)
        s["pocketbase"] = has("pocketbase") or any(p.startswith("pb_migrations/") or p.endswith("pb_schema.json") for p in paths)
        s["appwrite"] = has("appwrite", "node-appwrite") or any(p == "appwrite.json" for p in paths)
        s["clerk"] = has_prefix("@clerk/")
        s["auth0"] = has_prefix("@auth0/")
        s["nextauth"] = has("next-auth") or has_prefix("@auth/")
        s["better_auth"] = has("better-auth")
        # PHP, Python, Ruby, Java, .NET, Go, Rust, Elixir
        s["symfony"] = has_prefix("composer:symfony/framework-bundle")
        s["wordpress"] = any(p.endswith("wp-config.php") or p.startswith("wp-content/") for p in paths)
        s["drf"] = py("djangorestframework")
        s["spring"] = any(d.startswith("mvn:spring-boot") for d in self.deps)
        s["spring_security"] = "mvn:spring-boot-starter-security" in self.deps
        s["aspnet"] = any(d.startswith(("nuget:microsoft.aspnetcore", "nuget:swashbuckle")) for d in self.deps)
        s["go_web"] = any(d.startswith(("go:github.com/gin-gonic/gin", "go:github.com/labstack/echo", "go:github.com/gofiber/fiber",
                                        "go:github.com/go-chi/chi", "go:github.com/gorilla/mux")) for d in self.deps) \
            or any(f.ext == ".go" and "net/http" in f.text for f in self.files[:3000])
        s["rust_web"] = any(d in self.deps for d in ("cargo:axum", "cargo:actix-web", "cargo:rocket", "cargo:warp"))
        s["phoenix"] = "hex:phoenix" in self.deps
        # deploy
        s["render"] = "render.yaml" in paths
        s["railway"] = any(p in ("railway.json", "railway.toml") for p in paths)
        s["fly"] = "fly.toml" in paths
        s["heroku"] = "Procfile" in paths
        s["firebase_hosting"] = "firebase.json" in paths
        s["aws"] = any(p.endswith(("serverless.yml", "template.yaml", "cdk.json", "amplify.yml")) for p in paths)
        s["kubernetes"] = any(re.search(r"(^|/)(k8s|kubernetes|helm|charts)/", p) for p in paths)
        s["frontend_spa"] = (s["vite"] or s["cra"] or s["angular"] or s["svelte"] or s["solid"]) and not any(
            s[k] for k in ("nextjs", "nuxt", "remix", "sveltekit", "express", "fastify", "nestjs", "hono", "koa", "elysia",
                           "laravel", "rails", "django", "flask", "fastapi", "spring", "aspnet", "react_router7", "adonis"))
        s["backend_python"] = s["django"] or s["flask"] or s["fastapi"]
        s["app_cliente_binario"] = any(s[k] for k in ("expo_rn", "flutter", "electron", "tauri", "capacitor", "browser_extension"))
        self.stack = {k: v for k, v in s.items() if v}
        for f in self.files:  # raízes de app que vira binário na máquina do usuário
            if f.name == "manifest.json" and '"manifest_version"' in f.text:
                self.app_roots.append(f.rel.rsplit("/", 1)[0] + "/" if "/" in f.rel else "")
        for p_ in paths:
            if "src-tauri/" in p_:
                self.app_roots.append(p_.split("src-tauri/")[0])
        self.app_roots = sorted(set(self.app_roots))

        # plataforma de criação (muda as dicas: Lovable, Bolt, Replit, Base44…)
        html_idx = next((f for f in self.files if f.rel in ("index.html", "public/index.html")), None)
        idx = html_idx.text.lower() if html_idx else ""
        plat = []
        if "lovable-tagger" in self.deps or "lovable" in idx or (self.root / ".lovable").exists():
            plat.append("lovable")
        if any(p.startswith(".bolt/") for p in paths):
            plat.append("bolt")
        if (self.root / ".replit").exists() or "replit.nix" in paths:
            plat.append("replit")
        if has("@base44/sdk") or "base44" in idx:
            plat.append("base44")
        if any(p.startswith(".idx/") for p in paths):
            plat.append("firebase-studio")
        if (self.root / ".cursor").exists() or ".cursorrules" in paths:
            plat.append("cursor")
        if (self.root / ".windsurfrules").exists() or (self.root / ".windsurf").exists():
            plat.append("windsurf")
        if (self.root / "CLAUDE.md").exists() or (self.root / ".claude").exists():
            plat.append("claude-code")
        self.platform = plat

        # Vite com envPrefix próprio: esses prefixos também vão pro navegador
        for f in self.files:
            if re.match(r"vite\.config\.(t|j|m|c)s$", f.name):
                m = re.search(r"envPrefix\s*:\s*(\[[^\]]*\]|['\"][^'\"]*['\"])", f.text)
                if m:
                    found = re.findall(r"['\"]([^'\"]*)['\"]", m.group(1))
                    if "" in found:
                        n = f.lineno(m.start())
                        self.add("C01", "vite_envprefix_vazio", f, n, f.line(n), "alta",
                                 "envPrefix vazio: o Vite expõe TODAS as variáveis de ambiente no bundle do navegador")
                    self.public_prefixes += [p for p in found if p and p not in self.public_prefixes]

        for f in self.files:
            f.side = self.classify_side(f)

    def classify_side(self, f):
        if f.kind != "code":
            return None
        p = "/" + f.rel
        head = f.text[:400]
        st = self.stack
        if re.search(r"^\s*['\"]use server['\"]", head, re.M):
            return "server"
        if re.search(r"^\s*['\"]use client['\"]", head, re.M):
            return "client"
        if re.search(r"\+api\.(t|j)sx?$", p):
            return "server"  # rota de API do Expo Router roda no servidor
        # app que vira binário/pacote na máquina do usuário: tudo é cliente (chave dentro dele é pública)
        if f.ext in (".dart", ".swift") or (st.get("android") and f.ext in (".kt", ".java") and "/src/main/" in p
                                            and not st.get("spring")):
            return "client"
        if self.app_roots and any(f.rel.startswith(r) for r in self.app_roots) and \
                f.ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".rs"):
            return "client"  # Electron, Tauri ou extensão: só dentro da pasta desse app
        if st.get("nextjs") and re.search(r"/pages/(?!api/)", p) and re.search(
                r"\bexport\s+(?:async\s+)?(?:const|function)\s+(?:getServerSideProps|getStaticProps)\b", f.text):
            return "unknown"  # o Next tira o getServerSideProps do bundle
        if re.search(r"/(resources/(js|ts)|app/javascript|wwwroot|ClientApp|src/main/resources/static|public|static|assets)/", p) \
                and f.ext not in (".py", ".rb", ".php", ".go", ".java", ".kt", ".cs", ".rs"):
            return "client"
        if st.get("angular") and re.search(r"/(src/app|src/environments|projects/[^/]+/src)/", p) and not re.search(r"\.server\.ts$|/server\.ts$", p):
            return "client"
        if st.get("nuxt"):
            if re.search(r"/server/|\.server\.(t|j)s$", p):
                return "server"
            if re.search(r"/(pages|components|composables|layouts|plugins|middleware|stores|utils|app)/|\.client\.(t|j)s$|/app\.vue$", p):
                return "client"
        if st.get("sveltekit"):
            if re.search(r"/lib/server/|\+(page|layout)\.server\.(t|j)s$|\+server\.(t|j)s$|hooks\.server\.(t|j)s$", p):
                return "server"
            if re.search(r"\+(page|layout)\.(t|j)s$|\.svelte$", p):
                return "client"  # +page.ts roda também no navegador
        if st.get("convex") and re.search(r"^/convex/", p):
            return "server"
        if f.ext in (".py", ".rb", ".php", ".go", ".java", ".kt", ".cs", ".rs", ".ex", ".exs", ".razor", ".cshtml", ".scala", ".groovy"):
            return "server"
        if f.ext == ".astro":
            return "unknown"  # frontmatter roda no servidor; <script> vai pro navegador
        if re.search(r"/(api|server|backend|functions|supabase/functions|netlify/functions|edge-functions|actions|"
                     r"workers?|cron|jobs|scripts|migrations|prisma|db|database|seeds?|webhooks?|lib/server|server-only)/", p):
            return "server"
        if re.search(r"(\.server\.(t|j)sx?|/middleware\.(t|j)s|/proxy\.(t|j)s|/route\.(t|j)s|\+page\.server\.(t|j)s|\+server\.(t|j)s|"
                     r"\.config\.(t|j|m|c)s|/server\.(t|j)s|/app\.(t|j)s|/index\.(t|j)s)$", p) and not self.stack.get("frontend_spa"):
            if p.endswith(("/app.ts", "/app.js", "/index.ts", "/index.js")) and not any(self.stack.get(k) for k in ("express", "fastify", "nestjs", "hono")):
                pass
            else:
                return "server"
        if "import \"server-only\"" in f.text or "import 'server-only'" in f.text:
            return "server"
        if f.ext in (".vue", ".svelte", ".astro"):
            return "client"
        if re.search(r"/(public|static|assets)/", p):
            return "client"
        if self.stack.get("expo_rn") or self.stack.get("frontend_spa"):
            return "client"
        if re.search(r"/(components|hooks|contexts?|providers|store|stores|screens|views|pages)/", p) and not re.search(r"/pages/api/", p):
            return "client"
        if self.stack.get("nextjs") and re.search(r"/app/", p):
            return "server"  # server component por padrão
        return "unknown"

    # -- C01 / C03 segredos ----------------------------------------------------
    def scan_secrets(self):
        fora = {id(f): f.zona for f in self.so_segredos}
        for f in self.files + self.so_segredos:
            if f.kind == "env" and not is_env_example(f.name):
                self.scan_env_file(f)
                continue
            client = f.side == "client"
            for n, full in enumerate(f.lines, 1):
              seen_here = set()
              for _off, chunk in chunks(full):
                for pid, value, conf, desc in iter_secret_matches(chunk):
                    if (pid, value) in seen_here:
                        continue
                    seen_here.add((pid, value))
                    ln = chunk
                    if len(full) > 400:  # linha minificada: o trecho é só a vizinhança do achado
                        i = chunk.find(value)
                        ln = "…" + chunk[max(0, i - 60): i + len(value) + 60] + "…"
                    if pid == "jwt":
                        payload = decode_jwt_payload(value) or {}
                        role = str(payload.get("role", ""))
                        if role == "service_role":
                            self.add("C03", "service_role_jwt", f, n, ln, "alta",
                                     "JWT com role=service_role (ignora RLS) no código" + (" de cliente" if client else ""))
                            self.add("C01", "service_role_jwt", f, n, ln, "alta", "Service role hardcoded")
                        elif role in ("anon", "authenticated"):
                            continue
                        else:
                            self.add("C01", "jwt_hardcoded", f, n, ln, "baixa", "JWT hardcoded — confirme se é token real")
                        continue
                    if pid == "supabase_secret":
                        self.add("C03", "supabase_secret_key", f, n, ln, "alta", "Chave sb_secret_ (acesso total, ignora RLS) no código")
                    if pid == "google_api_key" and f.kind == "code" and re.search(r"firebase|apiKey\s*:", f.window(n, 6, 6)):
                        conf = "baixa"
                        desc = "Google API key em config do Firebase (pública por design; restrinja no console do Google Cloud)"
                    if f.kind == "doc":
                        conf = "media" if conf == "alta" else "baixa"
                    if re.search(r"(^|/)(tests?|__tests__|spec|fixtures?|mocks?|__mocks__|examples?)/", f.rel):
                        conf = "baixa" if conf != "alta" else "media"
                    note = desc + (" — arquivo vai pro navegador/app" if client else "")
                    if fora.get(id(f), "").startswith("gitignore"):
                        if not re.search(r"(^|/)(public|static|www|wwwroot|assets|dist|build)/", f.rel):
                            conf = "baixa"
                        note += " (arquivo ignorado pelo git: não vai para o repositório, mas vaza se entrar no build ou num deploy feito da sua máquina)"
                    elif id(f) in fora:
                        note += " (pasta fora das regras de código; se o arquivo está no Git, a chave vazou do mesmo jeito)"
                    if client and conf == "media" and pid not in ("google_api_key", "generic_assignment", "stripe_test"):
                        conf = "alta"
                    self.add("C01", pid, f, n, ln, conf, note)

        # valores sem aspas em arquivos de configuração (application.properties, *.yml, *.ini, *.toml)
        cfg_rx = re.compile(r"(?im)^[ \t]*([\w.\-]*(?:password|passwd|secret|api[_-]?key|apikey|token|private[_-]?key|access[_-]?key)[\w.\-]*)"
                            r"\s*[:=]\s*([^\s#'\"${}<>][^\s#'\"]{7,})\s*$")
        for f in self.files + self.so_segredos:
            if f.kind != "config" or f.ext not in (".properties", ".yml", ".yaml", ".ini", ".toml", ".cfg", ".conf"):
                continue
            for m in cfg_rx.finditer(f.text):
                val = m.group(2)
                if looks_placeholder(val) or not looks_random(val) or re.fullmatch(r"[A-Z0-9_]+", val) or val.startswith(("http", "/")):
                    continue
                n = f.lineno(m.start())
                self.add("C01", "config_com_segredo", f, n, f.line(n), "alta",
                         f"{m.group(1)} com valor real em arquivo de configuração — mova para variável de ambiente/cofre")

        # injeção de env no bundle pela config do build (next.config env, Vite define, Webpack DefinePlugin, Expo extra)
        secretish = r"[A-Z0-9_]*(?:SECRET|SERVICE_ROLE|PRIVATE|OPENAI|ANTHROPIC|GEMINI|STRIPE_S|DATABASE_URL|PASSWORD|TOKEN|API_KEY)[A-Z0-9_]*"
        for f in self.files:
            if re.match(r"next\.config\.(js|mjs|ts|cjs)$", f.name):
                m = re.search(r"\benv\s*:\s*\{([^}]*)\}", f.text, re.S)
                if m:
                    for k in re.finditer(r"\b(" + secretish + r")\s*:", m.group(1)):
                        if not self.public_env_is_secret(k.group(1)):
                            continue
                        n = f.lineno(m.start())
                        self.add("C01", "next_config_env_secreto", f, n, f.line(n), "alta",
                                 f"next.config env.{k.group(1)}: tudo em `env` é embutido no JavaScript do navegador")
            if re.match(r"(vite|vitest|astro|nuxt|svelte)\.config\.(t|j|m|c)s$", f.name) or re.match(r"webpack[\w.\-]*\.(t|j|m|c)s$", f.name):
                for m in re.finditer(r"['\"]process\.env['\"]\s*:\s*(?:JSON\.stringify\()?\s*process\.env\b|"
                                     r"DefinePlugin\(\s*\{\s*['\"]process\.env['\"]\s*:\s*JSON\.stringify\(\s*process\.env\s*\)", f.text):
                    n = f.lineno(m.start())
                    self.add("C01", "bundle_recebe_todo_env", f, n, f.line(n), "alta",
                             "A config do build injeta process.env inteiro no bundle: todas as variáveis vão pro navegador")
                for m in re.finditer(r"['\"]process\.env\.(" + secretish + r")['\"]\s*:", f.text):
                    if self.public_env_is_secret(m.group(1)):
                        n = f.lineno(m.start())
                        self.add("C01", "define_segredo_no_bundle", f, n, f.line(n), "alta",
                                 f"define/DefinePlugin embute process.env.{m.group(1)} no JavaScript do navegador")
            if re.match(r"nuxt\.config\.(t|j|m)s$", f.name):
                m = re.search(r"runtimeConfig\s*:\s*\{[\s\S]*?\bpublic\s*:\s*\{([^}]*)\}", f.text)
                if m:
                    for k in re.finditer(r"\b([A-Za-z_]*(?:[Ss]ecret|SECRET|[Pp]rivate|serviceRole|ServiceRole|openai|Openai|OPENAI|[Pp]assword|apiSecret)[A-Za-z_]*)\s*:", m.group(1)):
                        n = f.lineno(m.start(1) + k.start())
                        self.add("C01", "nuxt_runtime_public_segredo", f, n, f.line(n), "alta",
                                 f"runtimeConfig.public.{k.group(1)}: tudo em `public` vai para o navegador (use a raiz do runtimeConfig, só servidor)")
            if f.name in ("app.json", "app.config.js", "app.config.ts") and re.search(r"\"?expo\"?\s*:|\bexpo\b", f.text[:3000]):
                m = re.search(r"\bextra\s*[\"']?\s*:\s*\{", f.text)
                if m:
                    blk = f.text[m.end(): m.end() + 2000]
                    for k in re.finditer(r"[\"']?([A-Za-z_]*(?:secret|Secret|SECRET|privateKey|serviceRole|openai|OPENAI|apiSecret)[A-Za-z_]*)[\"']?\s*:", blk):
                        n = f.lineno(m.end() + k.start())
                        self.add("C01", "expo_extra_segredo", f, n, f.line(n), "alta",
                                 f"Expo extra.{k.group(1)}: o que está em `extra` vai dentro do app instalado")

        # variáveis públicas carregando segredo (referências no código)
        rx = re.compile(r"(?:process\.env|import\.meta\.env)\.((?:%s)[A-Z0-9_]+)" % "|".join(self.public_prefixes))
        for f in self.code():
            for m in rx.finditer(f.text):
                name = m.group(1)
                if self.public_env_is_secret(name):
                    n = f.lineno(m.start())
                    self.add("C01", "public_env_secret", f, n, f.line(n), "alta",
                             f"{name}: variável com prefixo público vai pro bundle do navegador")
                    if re.search(r"SERVICE_ROLE|SERVICE_KEY|SECRET_KEY|SB_SECRET", name):
                        self.add("C03", "public_env_service_role", f, n, f.line(n), "alta",
                                 f"{name}: chave de serviço exposta via prefixo público")

        self.rx_rule("C01", "dangerously_allow_browser", r"dangerouslyAllowBrowser\s*:\s*true", self.code(), "alta",
                     "SDK de IA configurado para rodar no navegador — a chave vai junto")
        self.rx_rule("C01", "llm_api_from_client",
                     r"https://(?:api\.openai\.com|api\.anthropic\.com|api\.groq\.com|api\.mistral\.ai|api\.deepseek\.com|"
                     r"api\.perplexity\.ai|generativelanguage\.googleapis\.com|openrouter\.ai/api)",
                     self.client_code(), "media", "Chamada direta à API de IA a partir do cliente (exige chave no navegador)")

        # C03: admin/service no cliente
        client = self.client_code()
        self.rx_rule("C03", "service_role_in_client",
                     r"SERVICE_ROLE|service_role|serviceRole|SUPABASE_SECRET|supabaseAdmin|SB_SECRET", client, "alta",
                     "Referência à chave de serviço/cliente admin em código de cliente")
        self.rx_rule("C03", "firebase_admin_in_client", r"(?:from|require\()\s*['\"]firebase-admin", client, "alta",
                     "firebase-admin (acesso total) importado em código de cliente")
        self.rx_rule("C03", "db_driver_in_client",
                     r"(?:from|require\()\s*['\"](?:pg|mysql2(?:/promise)?|mongoose|mongodb|@prisma/client|postgres|"
                     r"@neondatabase/serverless|@planetscale/database)['\"]", client, "media",
                     "Driver de banco importado em código de cliente — connection string iria pro navegador")
        if self.stack.get("supabase"):
            self.signals["C03"]["supabase"] = True
            anon = any(re.search(r"ANON_KEY|PUBLISHABLE", f.text) for f in client)
            self.signals["C03"]["cliente_usa_chave_publica"] = anon

    def public_env_is_secret(self, name):
        up = name.upper()
        if any(a in up for a in PUBLIC_ENV_ALLOW) or "MAPBOX" in up:
            return False
        if not any(h in up for h in SECRET_ENV_HINTS):
            return False
        # o nome em si já é o segredo (URL de banco, webhook) ou termina em algo com cara de credencial
        if re.search(r"DATABASE_URL|DB_URL|REDIS_URL|MONGO(DB)?_UR[IL]|POSTGRES_UR[IL]|WEBHOOK", up):
            return True
        return bool(re.search(r"(?:KEY|SECRET|TOKEN|PASSWORD|PASS|PWD|PRIVATE|CREDENTIALS?|DSN|ROLE)(?:_|$)", up))

    def scan_env_file(self, f):
        for n, ln in enumerate(f.lines, 1):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", ln)
            if not m:
                continue
            name, value = m.group(1), m.group(2).strip().strip("'\"")
            if not value or looks_placeholder(value):
                continue
            if re.match(r"pk[._]", value) or (not looks_random(value) and not value.startswith("eyJ")):
                continue  # chave publicável (pk_live_, pk.eyJ… do Mapbox) ou valor que não parece segredo
            if name.startswith(tuple(self.public_prefixes)) and self.public_env_is_secret(name):
                self.add("C01", "public_env_secret", f, n, f"{name}={mask(value)}", "alta",
                         f"{name} tem prefixo público: o valor vai pro bundle do navegador")
                if re.search(r"SERVICE_ROLE|SERVICE_KEY|SECRET_KEY|SB_SECRET", name.upper()):
                    self.add("C03", "public_env_service_role", f, n, f"{name}={mask(value)}", "alta",
                             "Chave de serviço com prefixo público")
            if value.startswith("eyJ"):
                payload = decode_jwt_payload(value) or {}
                if payload.get("role") == "service_role" and name.startswith(tuple(self.public_prefixes)):
                    self.add("C03", "public_env_service_role", f, n, f"{name}={mask(value)}", "alta",
                             "Valor é um JWT service_role exposto com prefixo público")

    # -- C02 git ---------------------------------------------------------------
    def scan_git(self):
        rc, out, _ = run(["git", "rev-parse", "--is-inside-work-tree"], self.root, 15)
        if rc != 0 or out.strip() != "true":
            self.signals["C02"]["repo_git"] = False
            return
        self.git["repo"] = True
        self.signals["C02"]["repo_git"] = True
        rc, out, _ = run(["git", "rev-parse", "--is-shallow-repository"], self.root, 15)
        if out.strip() == "true":
            self.git["clone_raso"] = True
            self.avisos.append("Clone raso (shallow): o histórico do git está incompleto — C02 não cobre commits antigos")
        rc, out, _ = run(["git", "remote", "-v"], self.root, 15)
        remotes = sorted({mask_secrets(re.sub(r"//[^/@\s]+@", "//***@", l.split()[1])) for l in out.splitlines() if len(l.split()) > 1})
        self.signals["C02"]["remotes"] = remotes
        if re.search(r"https?://[^/\s:]+:[^@\s]+@", out):
            self.add("C02", "token_no_remote", None, None, None, "media",
                     "URL do remote contém credencial embutida (.git/config) — prefira credential helper/SSH")
        rc, out, _ = run(["git", "ls-files", "-z"], self.root, 60)
        tracked = [p for p in out.split("\x00") if p]
        self.signals["C02"]["arquivos_rastreados"] = len(tracked)
        for p in tracked:
            if is_sensitive_path(p):
                conf, note = "alta", "Arquivo sensível versionado no Git"
                base = p.rsplit("/", 1)[-1]
                if re.search(r"\.(pem|crt|cer|key)$", base, re.I):
                    try:
                        txt = (self.root / p).read_text(errors="ignore")[:200_000]
                    except Exception:
                        txt = ""
                    if txt and "PRIVATE KEY" not in txt:
                        conf, note = "baixa", f"{base} versionado só com certificado público (sem chave privada) — normalmente ok"
                if base in (".npmrc", ".yarnrc", ".pypirc", ".netrc"):
                    try:
                        txt = (self.root / p).read_text(errors="ignore")
                    except Exception:
                        txt = ""
                    if not re.search(r"(?i)_authToken|_auth\s*=|password|passwd|token\s*=|//[^\s]+:_", txt):
                        conf, note = "baixa", f"{base} versionado sem token aparente (só configuração) — ok, confira se continua assim"
                    else:
                        note = f"{base} versionado com credencial de registro de pacotes"
                if base.startswith(".env"):  # inclui .envrc
                    try:
                        txt = (self.root / p).read_text(errors="ignore")
                        pairs = [(m.group(1).upper(), m.group(2).strip().strip("'\"")) for m in
                                 re.finditer(r"(?m)^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*(.+)$", txt)]
                        real = []
                        for k, v in pairs:
                            if not v or looks_placeholder(v) or " " in v:
                                continue
                            specific = any(pid != "generic_assignment" for pid, *_ in iter_secret_matches(v))
                            secretish = re.search(r"SECRET|KEY|TOKEN|PASS|PRIVATE|CREDENTIAL|AUTH", k) and looks_random(v) and len(v) >= 12
                            if specific or secretish:
                                real.append(k)
                        if not real:
                            secret_keys = [k for k, v in pairs if v and re.search(r"SECRET|KEY|TOKEN|PASS|PRIVATE|CREDENTIAL|AUTH|DATABASE_URL|DSN", k)]
                            if secret_keys:
                                conf, note = "media", "Arquivo .env versionado — valores parecem placeholders, confirme (e pare de versionar)"
                            else:
                                conf, note = "baixa", "Arquivo .env versionado sem variáveis de segredo (só config pública) — ok, mas prefira .env.example"
                    except Exception:
                        pass
                self.add("C02", "arquivo_sensivel_rastreado", p, None, None, conf, note)
        gi = self.root / ".gitignore"
        gitignore = gi.read_text(errors="ignore") if gi.exists() else ""
        rc_ci, _o, _e = run(["git", "check-ignore", "-q", "--no-index", ".env"], self.root, 15)
        covers_env = rc_ci == 0 if rc_ci in (0, 1) else bool(re.search(
            r"^\s*/?(\*\*/)?\.env(\*|\.\*|\.local)?\s*$|^\s*\*\.env\s*$|^\s*/?\.env\*", gitignore, re.M))
        self.signals["C02"]["gitignore_cobre_env"] = covers_env
        if not covers_env:
            self.add("C02", "gitignore_sem_env", ".gitignore" if gi.exists() else None, None, None, "media",
                     ".gitignore não cobre arquivos .env" if gi.exists() else "Projeto sem .gitignore")
        # arquivos sensíveis que já entraram no histórico
        rc, out, _ = run(["git", "log", "--all", "--diff-filter=A", "--name-only", "--format="], self.root, 120)
        ever = sorted({p for p in out.splitlines() if p and is_sensitive_path(p)})
        tracked_set = set(tracked)
        for p in ever:
            if p not in tracked_set:
                self.add("C02", "arquivo_sensivel_no_historico", p, None, None, "alta",
                         "Arquivo sensível foi commitado no passado (continua no histórico) — rotacione o que havia nele")
        if not self.args.no_git_history:
            self.scan_git_history()
        else:
            self.avisos.append("Histórico do git não varrido (--no-git-history)")
        for tool in ("gitleaks", "trufflehog"):
            self.tools[tool] = bool(shutil.which(tool))

    def scan_git_history(self):
        start = time.time()
        high = [(pid, rx) for pid, rx, conf, _ in SECRET_PATTERNS if conf == "alta" and pid != "db_url_password"]
        try:
            p = subprocess.Popen(["git", "-c", "core.quotePath=false", "log", "--all", "-p", "--no-color", "-U0", "--no-ext-diff",
                                  "--format=commit:%h"], cwd=self.root, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, errors="ignore")
        except Exception:
            return
        commit, path, lines_read, found = "", "", 0, set()
        try:
            for ln in p.stdout:
                lines_read += 1
                if lines_read > 3_000_000 or time.time() - start > 90:
                    self.signals["C02"]["historico_parcial"] = True
                    self.avisos.append("Histórico do git lido parcialmente (limite de tempo/tamanho)")
                    break
                if ln.startswith("commit:"):
                    commit = ln[7:].strip()
                    continue
                if ln.startswith("+++ "):
                    path = ln[6:].strip() if ln.startswith("+++ b/") else (ln[7:].strip().rstrip('"') if ln.startswith('+++ "b/') else "")
                    continue
                if not ln.startswith("+") or not path:
                    continue
                base = path.rsplit("/", 1)[-1]
                if base in LOCKFILES or base.endswith((".min.js", ".map")):
                    continue
                if len(ln) > 20000:
                    ln = ln[:20000]
                jm = JWT_RX.search(ln)
                if jm and (decode_jwt_payload(jm.group(0)) or {}).get("role") == "service_role":
                    key = ("service_role_jwt", mask(jm.group(0)), path)
                    if key not in found:
                        found.add(key)
                        self.add("C02", "segredo_no_historico", path, None, f"commit {commit}: {ln[1:]}", "alta",
                                 "JWT service_role em commit do histórico — rotacione a chave no Supabase")
                for pid, rx in high:
                    m = rx.search(ln)
                    if m and not looks_placeholder(m.group(0)):
                        key = (pid, mask(m.group(0)), path)
                        if key in found:
                            continue
                        found.add(key)
                        self.add("C02", "segredo_no_historico", path, None, f"commit {commit}: {ln[1:]}", "alta",
                                 f"Segredo ({pid}) em commit do histórico — rotacione a chave")
        finally:
            try:
                p.kill()
            except Exception:
                pass
        self.signals["C02"]["linhas_de_historico_lidas"] = lines_read

    # -- C04 RLS, policies, grants, funções e views (Supabase/PostgREST) ------------
    PAPEIS_SERVICO = {"service_role", "postgres", "supabase_admin", "supabase_auth_admin", "supabase_storage_admin",
                      "dashboard_user", "supabase_realtime_admin", "authenticator", "pgbouncer", "supabase_read_only_user"}
    FUNCAO_PERIGOSA_RX = re.compile(r"delete|drop|truncate|purge|wipe|reset|admin|grant|revoke|promote|set_?role|impersonat|bypass|"
                                    r"exec|_sql|sql_|all_users|apagar|excluir|remover|tornar_admin|alterar_papel|update_user")
    ESCRITA = {"insert", "update", "delete"}
    PAPEIS_API = {"anon", "authenticated", "public"}

    def scan_rls(self):
        self.scan_sql_banco()
        self.scan_supabase_api_config()
        self.scan_firebase_rules()

    def _avaliar_policy(self, f, n, ln, nome, tabela, resto, cont):
        cabeca = re.split(r"\b(?:using|with check)\b", resto, 1)[0]
        if re.search(r"user_metadata|raw_user_meta_data", resto):
            self.add("C07", "policy_usa_user_metadata", f, n, ln, "alta",
                     "Policy decide acesso por user_metadata — o próprio usuário consegue editar esse campo")
        if re.search(r"\bas restrictive\b", cabeca):
            return  # policy restritiva só tira acesso
        m = re.search(r"\bfor (all|select|insert|update|delete)\b", cabeca)
        cmd = m.group(1) if m else "all"
        m = re.search(r"\bto ([\w$, ]+?)\s*$", cabeca)
        roles = {r.strip() for r in m.group(1).split(",") if r.strip()} if m else {"public"}
        if roles <= self.PAPEIS_SERVICO:
            return
        aberta = re.search(r"\b(?:using|with check) \(\s*(?:\(\s*)?(?:true|1\s*=\s*1)(?:\s*\))?\s*\)", resto)
        logado = re.search(r"\b(?:using|with check) \(\s*\(?\s*(?:auth\.role\(\)\s*=\s*'authenticated'|\(?\s*(?:select )?auth\.uid\(\)\s*\)?"
                           r"\s+is not null)\s*\)?\s*\)", resto)
        if not aberta and not logado:
            return
        publico = bool(roles & {"public", "anon"}) and bool(aberta)
        escrita = cmd != "select"
        so_insert = cmd == "insert"
        tipo = tipo_de_tabela(tabela)
        storage = tabela == "storage.objects"
        quem = ", ".join(sorted(roles))
        dica = {"catalogo": " Parece catálogo (dado de referência): normalmente ok.",
                "pessoal": " O nome da tabela parece dado de usuário: confirme.", "": ""}[tipo]
        if publico and escrita:
            regra, conf = "policy_publica_escrita", "media" if so_insert and not storage else "alta"
            nota = (f"Policy {nome} ({cmd}) em {tabela}, para {quem}, sem condição: " +
                    ("qualquer visitante insere linhas. Em formulário público é o esperado, desde que tenha captcha ou rate limit e "
                     "não exista leitura pública da tabela." if so_insert and not storage else "qualquer visitante, sem login, "
                     + ("sobe arquivo em qualquer bucket." if storage else "altera ou apaga.")))
        elif publico:
            regra = "policy_publica_leitura"
            conf = "alta" if storage or tipo == "pessoal" else "baixa" if tipo == "catalogo" else "media"
            nota = (f"Policy {nome} (select) em {tabela}, para {quem}: leitura pública, sem login." +
                    (" Em storage.objects isso libera todos os buckets, inclusive os privados." if storage else dica))
        elif escrita:
            regra, conf = "policy_qualquer_logado_escrita", "media" if so_insert else "alta"
            nota = (f"Policy {nome} ({cmd}) em {tabela} só exige estar logado, sem checar o dono: qualquer conta " +
                    ("insere linha em nome de qualquer um (amarre user_id = auth.uid() no with check)." if so_insert
                     else "altera ou apaga linha de outra conta. O cadastro é aberto?"))
        else:
            regra = "policy_qualquer_logado_leitura"
            conf = "alta" if tipo == "pessoal" else "baixa" if tipo == "catalogo" else "media"
            nota = f"Policy {nome} (select) em {tabela}: qualquer conta logada lê todas as linhas." + dica
        cont[regra.replace("policy_", "").replace("qualquer_", "")] += 1
        self.add("C04", regra, f, n, ln, conf, nota)

    def scan_sql_banco(self):
        """Lê as migrations comando por comando, na ordem, sem comentários: tabelas e RLS, policies (separando visitante de
        conta logada), GRANT/REVOKE, privilégios padrão, funções SECURITY DEFINER e views."""
        sql_files = sorted([f for f in self.files if f.ext == ".sql"], key=lambda f: f.rel)
        supa = bool(self.stack.get("supabase")) or any("supabase/" in f.rel for f in sql_files)
        expostos = {"public", "storage", "graphql_public", "realtime"}  # Data API, Storage e Realtime leem estes
        cfg = next((f for f in self.files if f.rel.endswith("supabase/config.toml")), None)
        sec = re.search(r"(?ms)^\[api\][ \t]*$(.*?)(?=^\[[\w.\-]+\][ \t]*$|\Z)", cfg.text) if cfg else None
        m = re.search(r"(?m)^[ \t]*schemas[ \t]*=[ \t]*\[([^\]]*)\]", sec.group(1)) if sec else None
        if m:
            expostos |= {x.strip().strip("'\"").lower() for x in m.group(1).split(",") if x.strip()}

        def exposto(nome_completo):
            return nome_completo.split(".", 1)[0] in expostos
        nome = r"([\w$]+(?:\.[\w$]+)?)"
        create_rx = re.compile(r"^create (?:(?:global |local )?(?:temp|temporary|unlogged) )?table (?:if not exists )?" + nome)
        alter_rx = re.compile(r"^alter table (?:if exists )?(?:only )?" + nome)
        policy_rx = re.compile(r'^create policy ("(?:[^"]|"")*"|[\w$]+) on ("?[\w$]+"?(?:\."?[\w$]+"?)?)(.*)$')
        grant_rx = re.compile(r"^grant (.+?) on (.+?) to (.+?)(?: with grant option)?(?: granted by [\w$]+)?$")
        revoke_rx = re.compile(r"^revoke (?:grant option for )?(.+?) on (.+?) from (.+?)(?: granted by [\w$]+)?(?: cascade| restrict)?$")
        adp_rx = re.compile(r"^alter default privileges(?: for (?:role|user) [\w$, ]+?)?(?: in schema ([\w$, ]+?))? (grant|revoke) "
                            r"(?:grant option for )?(.+?) on (tables|functions|routines|sequences|types|schemas) (?:to|from) (.+?)"
                            r"(?: with grant option)?(?: cascade| restrict)?$")
        func_rx = re.compile(r"^create (?:or replace )?(?:function|procedure) " + nome + r"\s*\(")
        alter_func_rx = re.compile(r"^alter (?:function|procedure|routine) " + nome + r"\s*\(")
        view_rx = re.compile(r"^create (?:or replace )?(?:temp |temporary )?(?:recursive )?(materialized )?view (?:if not exists )?" + nome)
        alter_view_rx = re.compile(r"^alter (?:materialized )?view (?:if exists )?" + nome + r" (set|reset) \(([^)]*)\)")
        invoker_falso = re.compile(r"security_invoker\s*=\s*'?(?:false|off|0|no)\b")

        def privs(txt):
            out = set()
            for x in re.sub(r"\([^)]*\)", "", txt).split(","):
                x = x.strip()
                if x in ("all", "all privileges"):
                    out |= {"select", "insert", "update", "delete", "truncate", "references", "trigger", "execute", "usage"}
                elif x:
                    out.add(x)
            return out

        def papeis(txt):
            return {p.strip() for p in re.sub(r"\bgroup\b", "", txt).split(",") if p.strip()} & self.PAPEIS_API

        def alvo(txt):
            txt = txt.strip()
            m = re.match(r"all (tables|functions|routines|procedures|sequences) in schema ([\w$, ]+)$", txt)
            if m:
                tipo = "functions" if m.group(1) in ("functions", "routines", "procedures") else m.group(1)
                return "todas_" + tipo, [x.strip() for x in m.group(2).split(",")]
            m = re.match(r"(?:function|routine|procedure) (.+)$", txt)
            if m:
                nomes = re.findall(r"([\w$]+(?:\.[\w$]+)?)\s*(?:\(|,|$)", re.sub(r"\([^)]*\)", "()", m.group(1)))
                return "functions", [_nome_sql(x) for x in nomes]
            if re.match(r"(?:sequence|schema|database|large object|foreign|language|tablespace|type|domain|parameter) ", txt):
                return None, []
            return "tables", [_nome_sql(x) for x in re.sub(r"^table ", "", txt).split(",") if x.strip()]

        created, enabled, disabled = {}, set(), {}
        tab = {p: {} for p in self.PAPEIS_API}   # papel -> relação -> privilégios dados nas migrations
        revogado = {}                            # relação -> papéis que perderam o select
        adp_tab, adp_fun, adp_origem = {}, {}, {}
        funcs, views = {}, {}
        massa_tab, massa_fun, padrao, origem_anon = [], [], [], []
        houve_permissao = False
        cont = {"publica_leitura": 0, "publica_escrita": 0, "logado_leitura": 0, "logado_escrita": 0}

        def dar(t, quem, pv, onde):
            for p in quem:
                tab[p].setdefault(t, set()).update(pv)
                if "select" in pv and t in revogado:
                    revogado[t].discard(p)
            if pv & self.ESCRITA and quem & {"anon", "public"}:
                origem_anon.append(onde)

        for f in sql_files:
            for off, norm, cru in sql_comandos(f.code):
                n = f.lineno(off)
                ln = f.line(n)
                onde = (f, n, ln)
                m = create_rx.match(norm)
                if m:
                    t = _nome_sql(m.group(1))
                    if exposto(t) and t not in created:
                        created[t] = (f, n)
                        for p, pv in adp_tab.items():
                            if pv:
                                dar(t, {p}, pv, adp_origem.get(p, onde))
                    continue
                m = alter_rx.match(norm)
                if m:
                    t = _nome_sql(m.group(1))
                    if "enable row level security" in norm:
                        enabled.add(t)
                        disabled.pop(t, None)
                    if "disable row level security" in norm:
                        disabled[t] = (f, n)
                        enabled.discard(t)
                    continue
                if norm.startswith("create policy "):
                    m = policy_rx.match(re.sub(r"\s+", " ", _CORPO_DOLAR.sub("$$", cru)).strip().rstrip(";").strip().lower())
                    if m and exposto(_nome_sql(m.group(2))):  # policy em schema que a API não expõe não abre nada sozinha
                        self._avaliar_policy(f, n, ln, m.group(1).strip('"').replace('""', '"'), _nome_sql(m.group(2)),
                                             m.group(3).replace('"', ""), cont)
                    continue
                m = adp_rx.match(norm)
                if m:
                    houve_permissao = True
                    if not {x.strip() for x in (m.group(1) or "public").split(",")} & expostos:
                        continue
                    op, pv, objt, quem = m.group(2), privs(m.group(3)), m.group(4), papeis(m.group(5))
                    for p in quem:
                        if objt == "tables":
                            atual = adp_tab.setdefault(p, set())
                            (atual.update if op == "grant" else atual.difference_update)(pv)
                            adp_origem[p] = onde
                        elif objt in ("functions", "routines") and "execute" in pv:
                            adp_fun[p] = op == "grant"
                    if op == "grant" and quem and objt in ("tables", "functions", "routines", "sequences"):
                        padrao.append((f, n, ln, objt, sorted(quem), pv))
                    continue
                m = grant_rx.match(norm) if norm.startswith("grant ") else None
                if m:
                    houve_permissao = True
                    pv, (tipo, objs), quem = privs(m.group(1)), alvo(m.group(2)), papeis(m.group(3))
                    if not quem or not tipo:
                        continue
                    if tipo == "todas_tables" and set(objs) & expostos:
                        for t in list(created) + list(views):
                            dar(t, quem, pv, onde)
                        massa_tab.append((f, n, ln, sorted(quem), pv))
                    elif tipo == "tables":
                        for t in objs:
                            dar(t, quem, pv, onde)
                    elif tipo == "todas_functions" and set(objs) & expostos and "execute" in pv:
                        publicas = [fn for k, fn in funcs.items() if k.split(".", 1)[0] in set(objs) & expostos]
                        for fn in publicas:
                            for p in quem:
                                if fn["exec"][p] is False:  # tinha sido fechada de propósito
                                    fn.setdefault("reaberta", {})[p] = f"{f.rel}:{n}"
                                fn["exec"][p] = True
                        massa_fun.append((f, n, ln, sorted(quem), sum(1 for fn in publicas if fn["secdef"] and not fn["trigger"])))
                    elif tipo == "functions" and "execute" in pv:
                        for nf in objs:
                            if nf in funcs:
                                for p in quem:
                                    funcs[nf]["exec"][p] = True
                    continue
                m = revoke_rx.match(norm) if norm.startswith("revoke ") else None
                if m:
                    houve_permissao = True
                    pv, (tipo, objs), quem = privs(m.group(1)), alvo(m.group(2)), papeis(m.group(3))
                    if not quem or not tipo:
                        continue
                    if tipo in ("tables", "todas_tables"):
                        alvos = objs if tipo == "tables" else [t for t in list(created) + list(views) if t.split(".", 1)[0] in objs]
                        for t in alvos:
                            for p in quem:
                                if t in tab[p]:
                                    tab[p][t] -= pv
                                if "select" in pv:
                                    revogado.setdefault(t, set()).add(p)
                    elif tipo in ("functions", "todas_functions") and "execute" in pv:
                        alvos = objs if tipo == "functions" else [k for k in funcs if k.split(".", 1)[0] in objs]
                        for nf in alvos:
                            if nf in funcs:
                                for p in quem:
                                    funcs[nf]["exec"][p] = False
                    continue
                m = func_rx.match(norm)
                if m:
                    nf = _nome_sql(m.group(1))
                    attrs = {"secdef": " security definer" in norm, "search_path": " set search_path" in norm,
                             "trigger": bool(re.search(r"\breturns (?:event_)?trigger\b", norm)), "f": f, "n": n, "ln": ln}
                    if nf in funcs:
                        funcs[nf].update(attrs)
                    else:
                        funcs[nf] = {"nome": nf, **attrs, "exec": {"public": adp_fun.get("public", True), "anon": adp_fun.get("anon", True),
                                                                    "authenticated": adp_fun.get("authenticated", True)}}
                    continue
                m = alter_func_rx.match(norm)
                if m:
                    fn = funcs.get(_nome_sql(m.group(1)))
                    if fn:
                        if " security definer" in norm:
                            fn["secdef"] = True
                        if " security invoker" in norm:
                            fn["secdef"] = False
                        if " set search_path" in norm:
                            fn["search_path"] = True
                    continue
                m = view_rx.match(norm)
                if m:
                    v = _nome_sql(m.group(2))
                    opts = re.search(r"\bwith \(([^)]*security_invoker[^)]*)\)", norm)
                    if exposto(v):
                        views[v] = {"f": f, "n": n, "ln": ln, "mat": bool(m.group(1)),
                                    "invoker": bool(opts) and not invoker_falso.search(opts.group(1))}
                    continue
                m = alter_view_rx.match(norm)
                if m and _nome_sql(m.group(1)) in views and "security_invoker" in m.group(3):
                    views[_nome_sql(m.group(1))]["invoker"] = m.group(2) == "set" and not invoker_falso.search(m.group(3))

        sem_rls = {t for t in created if t not in enabled}
        if supa:  # Postgres comum (Prisma, Rails…) sem Supabase não expõe tabela ao navegador
            for t, (f, n) in created.items():
                if t in enabled or t in disabled:
                    continue
                pv_anon = (tab["anon"].get(t, set()) | tab["public"].get(t, set())) & {"select", "insert", "update", "delete"}
                self.add("C04", "tabela_sem_rls", f, n, f.line(n), "alta" if "supabase/" in f.rel else "media",
                         f"Tabela {t} criada sem 'enable row level security' nas migrations"
                         + (f" (e o anon tem {', '.join(sorted(pv_anon))} nela por GRANT)" if pv_anon else ""))
        for t, (f, n) in disabled.items():
            self.add("C04", "rls_desativado", f, n, f.line(n), "alta", f"RLS desativado explicitamente em {t}")

        anon_w = sorted({t for p in ("anon", "public") for t, pv in tab[p].items() if pv & self.ESCRITA})
        if anon_w and origem_anon:
            f0, n0, ln0 = origem_anon[0]
            nomes = ", ".join(t.split(".", 1)[-1] for t in anon_w[:12]) + ("…" if len(anon_w) > 12 else "")
            self.add("C04", "anon_com_escrita", f0, n0, ln0, "alta" if any(t in sem_rls for t in anon_w) else "media",
                     f"O papel anon (visitante sem login) recebe INSERT/UPDATE/DELETE por GRANT em {len(anon_w)} tabela(s)"
                     + (" (formato de schema exportado por supabase db pull/dump)" if len(anon_w) >= 5 else "") + f": {nomes}. "
                     "Hoje só a RLS separa o visitante dos dados, e uma policy errada vira escrita pública. Revogue a escrita do anon "
                     "nas tabelas que o visitante não escreve (quase sempre todas).")
        visivel = {"select", "insert", "update", "delete", "truncate"}
        for f, n, ln, quem, pv in massa_tab:
            anon = bool(set(quem) & {"anon", "public"})
            self.add("C04", "grant_em_massa_tabelas", f, n, ln, "alta" if anon and pv & self.ESCRITA and sem_rls else "media",
                     f"GRANT {', '.join(sorted(pv & visivel))} em todas as tabelas do schema public para {', '.join(quem)}: reabre também "
                     "as tabelas privadas e as que ainda não têm RLS. É a correção errada mais comum para o erro 42501 (permission "
                     "denied) que vem com a mudança do Supabase de 30/10/2026. Dê GRANT por tabela, só ao papel que precisa.")
        for f, n, ln, quem, k in massa_fun:
            self.add("C04", "grant_execute_em_massa", f, n, ln, "alta" if k else "media",
                     f"GRANT EXECUTE em todas as funções do schema public para {', '.join(quem)}: devolve também as funções internas "
                     "que tinham sido fechadas de propósito" + ((" (1 delas é SECURITY DEFINER e ignora a RLS)" if k == 1 else
                                                                 f" ({k} delas são SECURITY DEFINER e ignoram a RLS)") if k else "")
                     + ". Conceda só as funções que o app chama por rpc(), uma a uma.")
        relevante = {"tables": {"select", "insert", "update", "delete", "truncate"}, "functions": {"execute"},
                     "routines": {"execute"}, "sequences": {"usage", "select", "update"}}
        for f, n, ln, objt, quem, pv in padrao:
            efeito = {"tables": "toda tabela nova", "functions": "toda função nova", "routines": "toda função nova",
                      "sequences": "toda sequence nova"}[objt]
            self.add("C04", "privilegio_padrao_aberto", f, n, ln, "baixa" if objt == "sequences" else "media",
                     f"alter default privileges: {efeito} no schema public nasce com {', '.join(sorted(pv & relevante[objt])) or 'tudo'} para "
                     f"{', '.join(quem)}" + (". Se uma tabela sair sem RLS, ela abre sozinha." if objt == "tables" else
                                             ". Qualquer um chama por /rest/v1/rpc: revogue o padrão e conceda função a função."
                                             if objt != "sequences" else "."))
        for fn in funcs.values():
            if not fn["secdef"]:
                continue
            if not fn["search_path"]:
                self.add("C04", "security_definer_sem_search_path", fn["f"], fn["n"], fn["ln"], "media",
                         f"{fn['nome']}() é SECURITY DEFINER sem 'set search_path': um objeto com o mesmo nome em outro schema "
                         "sequestra a função (lint 0011 do Supabase). Use set search_path = '' e nomes qualificados (public.tabela).")
            if fn["trigger"] or not exposto(fn["nome"]) or fn["nome"].split(".", 1)[0] in ("storage", "realtime"):
                continue
            e = fn["exec"]
            curto = fn["nome"].split(".", 1)[1]
            perigosa = bool(self.FUNCAO_PERIGOSA_RX.search(curto))
            reab = fn.get("reaberta") or {}
            if e["public"] or e["anon"]:
                falta = (": revogou de public, mas falta revogar de anon" if not e["public"] else
                         ": revogou de anon, mas o anon também herda de public" if not e["anon"] else "")
                volta = next((onde for p, onde in reab.items() if p in ("anon", "public")), None)
                self.add("C04", "funcao_security_definer_exposta", fn["f"], fn["n"], fn["ln"], "alta" if perigosa or volta else "media",
                         f"{curto}() é SECURITY DEFINER (roda com o poder do dono e ignora a RLS) e o visitante sem login chama por "
                         f"/rest/v1/rpc/{curto}{falta}" + (f". Ela tinha sido fechada e foi reaberta pelo GRANT em massa em {volta}" if volta else "")
                         + f". Se o app não usa antes do login: revoke execute on function {fn['nome']}(…) from public, anon; se é "
                         "interna, mova para um schema que a API não expõe.")
            elif e["authenticated"]:
                volta = reab.get("authenticated")
                self.add("C04", "funcao_security_definer_exposta", fn["f"], fn["n"], fn["ln"],
                         ("alta" if perigosa else "media") if volta else "baixa",
                         f"{curto}() é SECURITY DEFINER e qualquer conta logada chama por /rest/v1/rpc/{curto}"
                         + (f": ela tinha sido fechada de propósito e o GRANT EXECUTE em massa em {volta} reabriu. Revogue de novo e "
                            "conceda só as funções que o app chama por rpc()." if volta else
                            ": confirme que ela confere auth.uid() ou o papel antes de agir."))
        for v, d in views.items():
            if {"anon", "authenticated"} <= revogado.get(v, set()):
                continue
            if d["mat"]:
                self.add("C04", "view_materializada_exposta", d["f"], d["n"], d["ln"], "baixa",
                         f"Materialized view {v} no schema public não tem RLS: tire do schema exposto ou revogue de anon e authenticated.")
            elif not d["invoker"]:
                self.add("C04", "view_ignora_rls", d["f"], d["n"], d["ln"], "media",
                         f"View {v} sem security_invoker: roda com o dono e entrega as linhas que a RLS das tabelas esconderia (lint 0010 "
                         "do Supabase). Use with (security_invoker = true) ou revogue de anon e authenticated.")

        if supa and created and any(f.rel.startswith("supabase/migrations/") for f in sql_files):
            usadas = set()
            for f in self.code():
                for m in re.finditer(r"\.from\(\s*['\"`]([\w-]+)['\"`]\s*\)", f.code):
                    if "storage" not in f.code[max(0, m.start() - 40): m.start()]:
                        usadas.add("public." + m.group(1).lower())
            com_grant = {t for p in self.PAPEIS_API for t, pv in tab[p].items() if pv & {"select", "insert", "update", "delete"}}
            sem_grant = sorted(t for t in usadas & set(created) if t not in com_grant)
            if sem_grant:
                f0, n0 = created[sem_grant[0]]
                self.add("P04", "tabela_sem_grant_explicito", f0, n0, f0.line(n0), "baixa",
                         f"{len(sem_grant)} tabela(s) que o app usa não recebem GRANT nas migrations ("
                         + ", ".join(t.split(".", 1)[1] for t in sem_grant[:10]) + ("…" if len(sem_grant) > 10 else "") + "). A partir de "
                         "30/10/2026 tabela nova no public não ganha acesso automático: num projeto novo (staging, branch, restauração) "
                         "o app dá erro 42501 nelas. Ponha na migration o GRANT de cada tabela só para o papel que precisa, junto com a RLS.")
        if supa and created and not houve_permissao:
            self.add("C04", "permissoes_do_banco_nao_verificadas", None, None, None, "baixa",
                     "As migrations não têm GRANT nem REVOKE: o que anon e authenticated podem fazer segue o padrão do projeto (até "
                     "30/10/2026, toda tabela nova no public ganhava SELECT, INSERT, UPDATE e DELETE para os dois, e toda função é "
                     "executável por todos). A RLS é a única barreira. Rode a consulta de permissões de references/stacks/baas.md.")

        sig = self.signals["C04"]
        sig["tabelas_nas_migrations"] = len(created)
        sig["tabelas_com_rls"] = len([t for t in created if t in enabled])
        if self.stack.get("supabase") and not created:
            sig["rls_nao_verificavel_pelo_repo"] = True
        if sql_files:
            sig["politicas_abertas"] = cont
            sig["grants_ou_revokes_nas_migrations"] = houve_permissao
            sig["tabelas_com_escrita_do_anon_por_grant"] = len(anon_w)
            sig["funcoes_security_definer"] = sum(1 for fn in funcs.values() if fn["secdef"])
        if supa:
            sig["consulta_de_permissoes"] = "references/stacks/baas.md → Supabase → Consulta de permissões (só leitura)"

    def scan_supabase_api_config(self):
        cfg = next((f for f in self.files if f.rel.endswith("supabase/config.toml")), None)
        if not cfg:
            return
        sec = re.search(r"(?ms)^\[api\][ \t]*$(.*?)(?=^\[[\w.\-]+\][ \t]*$|\Z)", cfg.text)
        m = re.search(r"(?m)^[ \t]*auto_expose_new_tables[ \t]*=[ \t]*true\b", sec.group(1)) if sec else None
        if m:
            n = cfg.lineno(sec.start(1) + m.start())
            self.add("C04", "auto_expose_ligado", cfg, n, cfg.line(n), "media",
                     "[api] auto_expose_new_tables = true: toda tabela, view, sequence e função nova no public nasce acessível pela "
                     "Data API. O Supabase remove essa opção em 30/10/2026; passe a dar GRANT por tabela na migration, junto com a RLS.")

    def scan_firebase_rules(self):
        # Firebase
        for f in self.files:
            if f.name.endswith(".rules") or f.name in ("firestore.rules", "storage.rules"):
                self.signals["C04"]["firebase_rules"] = True
                self.rx_rule("C04", "firebase_if_true", r"allow\s+[\w,\s]+:\s*if\s+true\s*;", [f], "alta", "Regra Firebase liberada para todos (if true)")
                self.rx_rule("C04", "firebase_sem_condicao", r"allow\s+(?:read|write|get|list|create|update|delete)(?:\s*,\s*\w+)*\s*;", [f], "alta",
                             "Regra Firebase sem condição — libera para todos")
                self.rx_rule("C04", "firebase_modo_teste", r"request\.time\s*<\s*timestamp\.date\(", [f], "alta",
                             "Regras em 'modo de teste' (aberto para todos até a data)")
            if f.name == "database.rules.json":
                self.signals["C04"]["firebase_rules"] = True
                self.rx_rule("C04", "rtdb_publico", r"\"\.(?:read|write)\"\s*:\s*true", [f], "alta", "Realtime Database com leitura/escrita pública")

    # -- C05 criptografia --------------------------------------------------------
    def scan_crypto(self):
        schema_files = [f for f in self.files if f.ext in (".sql", ".prisma") or re.search(r"(models\.py|schema\.(t|j)s|entities?/)", f.rel)]
        self.rx_rule("C05", "dado_de_cartao", r"(?i)\b(card_?number|numero_?(?:do_?)?cartao|cartao_?credito|credit_?card_?number|cvv|cvc|card_?cvv)\b",
                     schema_files, "alta", "Campo de cartão no schema — não armazene dados de cartão, use tokenização do gateway")
        self.rx_rule("C05", "coluna_sensivel", r"(?i)\b(cpf|rg|cnh|passaporte|passport|ssn|access_?token|refresh_?token|api_?secret|"
                     r"client_?secret|diagnostico|diagnosis|prontuario|medical_?record|health_?data|dados_?saude)\b",
                     schema_files, "baixa", "Coluna com dado sensível — confirme criptografia/necessidade")
        self.rx_rule("C05", "cripto_fraca", r"createCipher\(|aes-\d{3}-ecb|AES\.MODE_ECB|des-ede|DESede|\bdes-cbc\b|\bRC4\b|"
                     r"Cipher\.getInstance\(\s*\"AES\"\s*\)|\"AES/ECB/|CipherMode\.ECB",
                     self.code(), "alta", "Algoritmo/modo de criptografia inseguro")
        enc = [f.rel for f in self.files if re.search(r"pgcrypto|pgp_sym_encrypt|vault\.create_secret|vault\.decrypted_secrets|"
                                                       r"createCipheriv\(\s*['\"]aes-256-gcm|Fernet\(|client-kms|kms\.encrypt|"
                                                       r"crypto\.subtle\.encrypt|libsodium|tweetnacl|@47ng/cloak|prisma-field-encryption",
                                                       f.text)]
        self.signals["C05"]["criptografia_encontrada_em"] = enc[:10]

    # -- C06 / C07 / C14 rotas -------------------------------------------------
    AUTH_RX = re.compile(
        r"getServerSession|\bauth\(\)|getUser\(|currentUser\(|getAuth\(|verifyIdToken|jwt\.verify|jwtVerify|requireAuth|"
        r"requireUser|requireSession|withAuth|isAuthenticated|ensureAuth|authenticate|protectedProcedure|authedProcedure|"
        r"clerkClient|auth\.protect|getKindeServerSession|validateRequest|auth\.api\.getSession|getToken\(|getClaims\(|"
        r"Depends\(\s*\w*(?:current_user|get_user|auth|verify)|\bCurrentUser\b|current_active_(?:user|superuser)|login_required|LoginRequiredMixin|IsAuthenticated|"
        r"permission_classes|passport\.authenticate|req\.user\b|request\.user\b|verifySession|session\?*\.user|"
        r"constructEvent|verifyWebhook|stripe-signature|x-hub-signature|x-signature|svix|verifySignature|"
        r"validateSignature|timingSafeEqual|ctx\.(?:auth|session|user)|locals\.(?:user|session)|"
        # ler o header de quem chama conta; mandar Authorization/x-api-key para a OpenAI não conta
        r"headers?(?:\(\))?\.get\(\s*['\"](?:authorization|x-api-key)['\"]|headers\[\s*['\"](?:authorization|x-api-key)['\"]\s*\]|"
        r"getHeader\(\s*['\"]authorization|req\.header\(\s*['\"](?:authorization|x-api-key)|"
        # Laravel, Rails, Spring, ASP.NET, Go, Convex, Firebase, Nuxt, Remix
        r"middleware\(\s*\[?\s*['\"]auth|auth:sanctum|auth:api|Auth::(?:user|id|check|guard)\(|auth\(\)->(?:user|id|check)\(|"
        r"\$this->authorize\(|Gate::(?:allows|authorize|denies|check)|before_action\s+:authenticate|authenticate_user!|"
        r"current_user\b|@PreAuthorize|@Secured|@RolesAllowed|\.authenticated\(\)|@AuthenticationPrincipal|\[Authorize|"
        r"RequireAuthorization\(|User\.Identity|ClaimsPrincipal|getUserIdentity\(|getAuthUserId\(|request\.auth\b|"
        r"context\.auth\b|requireUserSession\(|getUserSession\(|serverSupabaseUser\(|requireUserId\(|getUserId\(|"
        r"AuthMiddleware|RequireAuth|jwtauth|echojwt|jwtware|middleware\.JWT|ensureAuthenticated|event\.context\.(?:user|auth|session)|@UseGuards\(|AuthGuard\(|\bjwt\(\s*\{|bearerAuth\(|basicAuth\(|jwtPayload|ctx\.state\.user", re.I)
    COMMENT_RX = re.compile(r"/\*[\s\S]*?\*/|(?<![:\"'])//[^\n]*|^\s*#[^\n]*", re.M)

    def sem_comentarios(self, text):
        return self.COMMENT_RX.sub("", text)

    INPUT_RX = re.compile(r"req\.body|req\.json\(\)|request\.json\(\)|await\s+request\.json|formData\(\)|req\.query|"
                          r"searchParams|request\.get_json|request\.(?:form|args|data|POST|GET)|ctx\.request\.body|c\.req\.json|"
                          r"\$request->(?:all|input|get|post|only|except|json|validated)\(|\$_(?:GET|POST|REQUEST)\b|\bparams\[|"
                          r"@RequestBody|@RequestParam|@PathVariable|\[FromBody\]|\[FromQuery\]|readBody\(|getQuery\(|getRouterParam\(|"
                          r"c\.(?:ShouldBind\w*|Bind\w*|Query|Param|PostForm|FormValue|BodyParser)\(|r\.(?:FormValue|URL\.Query)\(|"
                          r"event\.body|ctx\.req\.|args\.\w+", re.I)
    VALID_RX = re.compile(r"\.(?:parse|safeParse|parseAsync|safeParseAsync|validate|validateSync|validateAsync|assert)\(|"
                          r"z\.object|v\.object|yup\.|Joi\.|t\.Object|validationResult|celebrate|BaseModel|Serializer|"
                          r"forms?\.Form|ValidationPipe|class-validator|@Is[A-Z]\w*\(|zValidator|ajv|typia|arktype|"
                          r"Schema\b|schema\b|validator\b|\$request->validate\(|Validator::make\(|FormRequest|@Valid\b|@Validated\b|"
                          r"ModelState\.IsValid|AbstractValidator<|readValidatedBody\(|getValidatedQuery\(|binding:\"required|"
                          r"validate\.Struct\(|\bargs\s*:\s*\{|v\.(?:string|number|id|object|boolean|array)\(|params\.require\(|\.permit\(", re.I)

    def route_kind(self, f):
        p = "/" + f.rel
        t = f.text
        if re.search(r"/app/(.*/)?route\.(t|j)sx?$", p):
            return "next-route-handler"
        if re.search(r"/pages/api/", p):
            return "next-pages-api"
        if re.search(r"^\s*['\"]use server['\"]", t[:400], re.M):
            return "server-action"
        if re.search(r"/supabase/functions/[^/]+/index\.(t|j)s$", p):
            return "supabase-edge-function"
        if re.search(r"/netlify/functions/", p) or re.search(r"^/api/.+\.(?:m|c)?(?:t|j)sx?$", p):
            return "serverless-function"
        if re.search(r"\+server\.(t|j)s$|\+page\.server\.(t|j)s$", p):
            return "sveltekit-endpoint"
        if re.search(r"\b(?:app|router|server|api|routes?)\.(?:get|post|put|patch|delete|all|route)\s*\(\s*['\"`]/", t):
            return "http-router"
        if re.search(r"@(?:app|router|api|bp|blueprint)\.(?:get|post|put|patch|delete|api_route|route)\(", t):
            return "python-router"
        if re.search(r"@(?:Get|Post|Put|Patch|Delete)\(", t) and "@Controller" in t:
            return "nest-controller"
        if f.name == "views.py" and re.search(r"def \w+\(\s*request|class \w+\(.*(?:View|ViewSet)\)", t):
            return "django-view"
        if re.search(r"functions\.https\.on(?:Request|Call)|onRequest\(|onCall\(", t):
            return "cloud-function"
        if f.ext == ".php" and re.search(r"/app/Http/Controllers/", p):
            return "laravel-controller"
        if f.ext == ".rb" and re.search(r"/app/controllers/.*_controller\.rb$", p):
            return "rails-controller"
        if f.ext in (".java", ".kt") and re.search(r"@(?:Rest)?Controller\b", t) and re.search(r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping", t):
            return "spring-controller"
        if f.ext == ".cs" and (re.search(r"\[ApiController\]|:\s*ControllerBase\b|:\s*Controller\b", t) or re.search(r"\.Map(?:Get|Post|Put|Patch|Delete)\(", t)):
            return "aspnet-endpoint"
        if f.ext == ".go" and re.search(r"\.(?:GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete|HandleFunc|Handle)\(\s*\"/", t):
            return "go-handler"
        if self.stack.get("nuxt") and re.search(r"/server/(?:api|routes)/", p) and "defineEventHandler" in t:
            return "nuxt-server-route"
        if re.search(r"/src/pages/.*\.(t|j)s$", p) and re.search(r"export\s+(?:const|async\s+function|function)\s+(?:GET|POST|PUT|PATCH|DELETE|ALL)\b", t):
            return "astro-endpoint"
        if re.search(r"/app/routes/", p) and re.search(r"export\s+(?:async\s+)?function\s+(?:loader|action)\b|export\s+const\s+(?:loader|action)\s*=", t):
            return "remix-route"
        if self.stack.get("convex") and re.search(r"^/convex/", p) and re.search(r"\b(?:query|mutation|action|httpAction)\s*\(", t):
            return "convex-function"
        if re.search(r"export\s+default\s*\{\s*(?:async\s+)?fetch\s*\(", t):
            return "worker"
        if re.search(r"exports\.handler\s*=|export\s+(?:const|async\s+function)\s+handler\b", t) and re.search(r"event\.(?:body|queryStringParameters|pathParameters)", t):
            return "lambda"
        if re.search(r"new\s+(?:Elysia|Hono|Koa)\(", t) and re.search(r"\.(?:get|post|put|patch|delete)\(\s*['\"`]/", t):
            return "http-router"
        return None

    def scan_routes(self):
        app_ctrl = next((f for f in self.files if f.rel.endswith("app/controllers/application_controller.rb")), None)
        rails_app_auth = bool(app_ctrl and re.search(r"before_action\s+:authenticate", app_ctrl.text))
        laravel_routes = any(re.search(r"(^|/)routes/[\w\-]+\.php$", f.rel) for f in self.files)
        # auth global: Spring Security nega tudo que não foi liberado; ASP.NET com FallbackPolicy exige login por padrão
        spring_global = any(f.ext in (".java", ".kt") and "SecurityFilterChain" in f.text
                            and re.search(r"anyRequest\(\)\s*\.\s*(?:authenticated|hasRole|hasAuthority|hasAnyRole|access)\(", f.text)
                            for f in self.code())
        aspnet_global = any(f.ext == ".cs" and re.search(r"FallbackPolicy\s*=[\s\S]{0,200}?RequireAuthenticatedUser\(\)|"
                                                         r"MapControllers\(\)\s*\.\s*RequireAuthorization\(", f.text) for f in self.code())
        nest_global = any(f.ext in (".ts", ".js") and re.search(r"provide\s*:\s*APP_GUARD", f.text) for f in self.code())
        self.signals["C06"]["auth_global"] = [k for k, v in (("NestJS APP_GUARD global", nest_global),
                                                              ("Spring Security anyRequest().authenticated()", spring_global),
                                                              ("ASP.NET FallbackPolicy/RequireAuthorization global", aspnet_global)) if v]
        for f in self.code():
            if f.side == "client":
                continue
            kind = self.route_kind(f)
            if not kind:
                continue
            has_auth = bool(self.AUTH_RX.search(self.sem_comentarios(f.text)))
            if kind == "rails-controller" and rails_app_auth and not re.search(r"skip_before_action\s+:authenticate", f.text):
                has_auth = True  # herda o before_action do ApplicationController
            if kind == "laravel-controller" and laravel_routes:
                has_auth = True  # no Laravel a auth fica no arquivo de rotas, avaliado rota a rota em scan_routes_frameworks
            if (kind == "nest-controller" and nest_global) or (kind == "spring-controller" and spring_global) or (kind == "aspnet-endpoint" and aspnet_global
                                                                   and not re.search(r"\[AllowAnonymous\]|AllowAnonymous\(\)", f.text)):
                has_auth = True  # vale a regra global; exceções (permitAll, AllowAnonymous) são vistas em outras regras
            reads_input = bool(self.INPUT_RX.search(f.text)) or kind == "server-action"
            validates = bool(self.VALID_RX.search(f.text))
            if kind == "python-router" and self.stack.get("fastapi"):
                reads_input = reads_input or bool(re.search(r"@\w+\.(?:post|put|patch)\(", f.text))
                validates = True  # FastAPI valida pelos type hints (Pydantic); revise tipos frouxos (dict/Any)
            info = {"arquivo": f.rel, "tipo": kind, "auth_aparente": has_auth, "le_input": reads_input, "validacao_aparente": validates}
            self.routes.append(info)
            public_hint = re.search(r"(health|status|ping|webhook|public|og|sitemap|robots|auth/callback|callback|login|signup|"
                                    r"register|cadastro|forgot|reset|verify|confirm|cron)", f.rel, re.I)
            if not has_auth:
                conf = "baixa" if public_hint else "media"
                note = "Sem verificação de auth aparente" + (" (nome sugere rota pública — confirme)" if public_hint else " — confirme se a rota deveria ser pública")
                if "webhook" in f.rel.lower():
                    note = "Webhook sem verificação de assinatura aparente"
                    conf = "media"
                self.add("C06", "rota_sem_auth_aparente", f, None, None, conf, note)
            if reads_input and not validates and kind != "next-route-handler" or (kind == "next-route-handler" and reads_input and not validates):
                self.add("C14", "rota_sem_validacao_aparente", f, None, None, "media", "Rota lê input sem schema de validação aparente")
            if re.search(r"/admin", "/" + f.rel, re.I) and not re.search(r"role|isAdmin|is_admin|is_staff|is_superuser|permission|"
                                                                          r"hasRole|can\(|ability|admin\s*===|=== ?['\"]admin", f.text):
                self.add("C07", "admin_sem_checagem_de_papel", f, None, None, "media", "Rota de admin sem checagem de papel aparente")

        self.signals["C06"]["rotas_encontradas"] = len(self.routes)
        self.signals["C06"]["rotas"] = self.routes[:200]
        server = self.server_code()
        self.rx_rule("C06", "getSession_no_servidor", r"auth\.getSession\(\)", server, "media",
                     "supabase.auth.getSession() no servidor não valida o JWT — use getUser()/getClaims()",
                     skip_line=r"^\s*//")
        mw = [f for f in self.files if re.search(r"(^|/)(src/)?(middleware|proxy)\.(t|j)s$", f.rel)]
        if mw:
            mw_auth = any(self.AUTH_RX.search(self.sem_comentarios(f.text)) for f in mw)
            self.signals["C06"]["middleware_com_auth"] = mw_auth
            no_auth = [r for r in self.routes if not r["auth_aparente"]]
            if mw_auth and self.routes and len(no_auth) >= max(1, len(self.routes) // 2):
                self.add("C06", "auth_so_no_middleware", mw[0], None, None, "media",
                         "Auth parece estar só no middleware — rotas não revalidam a sessão (defesa única)")

        # C07 identidade vinda do cliente / IDOR
        self.rx_rule("C07", "identidade_do_cliente",
                     r"(?:req\.body|req\.query|req\.params|body|input|payload)\??\.(?:userId|user_id|ownerId|owner_id|tenantId|tenant_id|"
                     r"role|isAdmin|is_admin|plan)\b|(?:searchParams|formData|params)\.get\(\s*['\"](?:userId|user_id|ownerId|owner_id|role|isAdmin)['\"]"
                     r"|request\.(?:json|form|args|data)(?:\.get\(|\[)\s*['\"](?:user_id|owner_id|role|is_admin|tenant_id)['\"]",
                     server, "media", "Identidade/papel vindo do request — o servidor deve usar o usuário da sessão")
        self.rx_rule("C07", "busca_por_id_do_request",
                     r"where\s*:\s*\{\s*id\s*:\s*(?:params|req\.params|req\.query|body|searchParams|input|args)\b|"
                     r"findBy(?:Id|Pk)\(\s*(?:req\.params|params|req\.query|body|id)\b|"
                     r"\.eq\(\s*['\"]id['\"]\s*,\s*(?:params|req\.|body|searchParams|input|id\b)",
                     server, "baixa", "Busca por id vindo do request — confirme filtro por dono/permissão (IDOR)",
                     skip_line=r"userId|user_id|ownerId|owner_id|user\.id|tenant|auth\.uid")
        self.rx_rule("C07", "user_metadata_para_papel",
                     r"user_metadata\??\.\s*(?:role|is_?admin|plan|tier)|raw_user_meta_data\s*->>?\s*'(?:role|is_admin|plan)'",
                     self.files, "alta", "Papel/plano lido de user_metadata — editável pelo próprio usuário (use app_metadata)")
        cors_files = self.code() + [f for f in self.files if f.kind == "config"]
        for f in cors_files:
            wild = re.search(r"origin\s*:\s*['\"]\*['\"]|origin\s*:\s*true\b|Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|"
                             r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]|CORS_ALLOW_ALL_ORIGINS\s*=\s*True|CORS_ORIGIN_ALLOW_ALL\s*=\s*True", f.text)
            if wild:
                creds = re.search(r"credentials\s*:\s*true|allow_credentials\s*=\s*True|Access-Control-Allow-Credentials['\"]?\s*[,:]\s*['\"]true", f.text)
                n = f.lineno(wild.start())
                self.add("C07", "cors_aberto", f, n, f.line(n), "alta" if creds else "media",
                         "CORS liberado para qualquer origem" + (" COM credenciais" if creds else ""))
        self.rx_rule("C07", "cors_sem_opcoes", r"\bcors\(\s*\)|\.enableCors\(\s*\)", self.server_code(), "baixa", "cors()/enableCors() sem opções libera qualquer origem")

    # -- C06/C07 por framework (rota a rota, quando dá) ----------------------------
    def scan_routes_frameworks(self):
        # Laravel: cada Route:: com ou sem middleware de auth (grupo ou encadeado)
        for f in self.files:
            if not (f.ext == ".php" and re.search(r"(^|/)routes/[\w\-]+\.php$", f.rel)):
                continue
            stack = []  # um item por chave aberta: True se a chave abriu um grupo com middleware de auth
            auth_mw = re.compile(r"middleware\(\s*\[?[^)]*['\"]auth|['\"]middleware['\"]\s*=>\s*\[?\s*['\"]auth")
            for n, ln in enumerate(f.lines, 1):
                # junta a cadeia ->prefix()->middleware()->group( quebrada em várias linhas (só a cadeia desta rota)
                chain, j = [ln], n - 1
                while chain[0].lstrip().startswith("->") and j > 0 and not f.lines[j - 1].rstrip().endswith((";", "{", "}")):
                    chain.insert(0, f.lines[j - 1])
                    j -= 1
                opens_auth = "group(" in ln and bool(auth_mw.search(" ".join(chain)))
                code_ln = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", "''", ln)  # {tenant} dentro de string não é chave
                for ch in code_ln:
                    if ch == "{":
                        stack.append(opens_auth)
                        opens_auth = False
                    elif ch == "}" and stack:
                        stack.pop()
                in_auth = any(stack)
                m = re.search(r"Route::(get|post|put|patch|delete|any|match|resource|apiResource)\(\s*['\"]([^'\"]*)", ln)
                if not m:
                    continue
                chained = bool(re.search(r"->middleware\(\s*\[?[^)]*['\"]auth", ln))
                path = m.group(2)
                public_hint = re.search(r"(login|register|cadastro|password|senha|webhook|health|up$|status|callback|verify|"
                                        r"sanctum/csrf|public|^/?$)", path, re.I)
                info = {"arquivo": f.rel, "linha": n, "tipo": "laravel-route", "metodo": m.group(1), "caminho": path,
                        "auth_aparente": in_auth or chained}
                self.routes.append(info)
                if not (in_auth or chained) and m.group(1) in ("post", "put", "patch", "delete", "any", "resource", "apiResource") and not public_hint:
                    self.add("C06", "laravel_rota_sem_auth", f, n, ln, "media",
                             f"Route::{m.group(1)}('{path}') fora de grupo com middleware auth — confirme se é pública")
                if re.search(r"admin", path, re.I) and not (in_auth or chained):
                    self.add("C07", "laravel_admin_sem_auth", f, n, ln, "alta", f"Rota de admin '{path}' sem middleware de auth")
        # Supabase Edge Functions com verify_jwt = false
        cfg = next((f for f in self.files if f.rel.endswith("supabase/config.toml")), None)
        if cfg:
            for m in re.finditer(r"(?ms)^\[functions\.([\w\-]+)\][^\[]*?verify_jwt\s*=\s*false", cfg.text):
                fn = m.group(1)
                code = next((f for f in self.files if re.search(r"supabase/functions/%s/index\.(t|j)s$" % re.escape(fn), f.rel)), None)
                has_auth = bool(code and self.AUTH_RX.search(self.sem_comentarios(code.text)))
                n = cfg.lineno(m.start())
                self.add("C06", "edge_function_sem_jwt", cfg, n, cfg.line(n), "media" if has_auth or "webhook" in fn else "alta",
                         f"Edge Function '{fn}' com verify_jwt = false: qualquer um chama sem login"
                         + (" (há verificação no código — confirme)" if has_auth else " e o código não verifica auth"))
            if re.search(r"(?ms)^\[auth\.email\][^\[]*?enable_confirmations\s*=\s*false", cfg.text):
                self.signals["C06"]["supabase_confirmacao_email_desligada"] = True
            m = re.search(r"(?m)^\s*minimum_password_length\s*=\s*(\d+)", cfg.text)
            if m and int(m.group(1)) < 8:
                self.add("C10", "senha_minima_curta", cfg, cfg.lineno(m.start()), cfg.line(cfg.lineno(m.start())), "media",
                         f"Supabase Auth aceita senha com {m.group(1)} caracteres (use ≥ 8 e checagem de senha vazada)")
            if re.search(r"(?ms)^\[auth\.captcha\][^\[]*?enabled\s*=\s*true", cfg.text):
                self.signals["C12"]["supabase_captcha_config"] = True
        # Convex: query/mutation/action exportadas são públicas por padrão
        for f in self.files:
            if not (self.stack.get("convex") and f.rel.startswith("convex/") and f.kind == "code") or "_generated" in f.rel:
                continue
            for m in re.finditer(r"export\s+const\s+(\w+)\s*=\s*(query|mutation|action)\s*\(\s*\{", f.text):
                body = f.text[m.end(): m.end() + 2500]
                end = re.search(r"\n\}\);?", body)
                body = body[: end.start()] if end else body
                if not re.search(r"getUserIdentity\(|getAuthUserId\(|requireUser|ctx\.auth", body):
                    n = f.lineno(m.start())
                    self.add("C06", "convex_funcao_publica_sem_auth", f, n, f.line(n), "media" if m.group(2) == "query" else "alta",
                             f"Convex {m.group(2)} '{m.group(1)}' pública sem checar ctx.auth (use internal{m.group(2).title()} se for interna)")
                if not re.search(r"\bargs\s*:", body) and m.group(2) != "query":
                    n = f.lineno(m.start())
                    self.add("C14", "convex_sem_validador", f, n, f.line(n), "media", f"Convex {m.group(2)} '{m.group(1)}' sem `args` (validação)")
        # tRPC: mutation em publicProcedure
        self.rx_rule("C06", "trpc_mutation_publica", r"publicProcedure[\s\S]{0,300}?\.mutation\(", self.server_code(), "baixa",
                     "Mutation tRPC em publicProcedure — confirme que pode rodar sem login")
        server = self.server_code()
        # Spring Security liberando tudo
        self.rx_rule("C06", "spring_permit_all_geral", r"anyRequest\(\)\s*\.\s*permitAll\(\)|requestMatchers\(\s*\"/\*\*\"\s*\)\s*\.\s*permitAll\(\)|"
                     r"antMatchers\(\s*\"/\*\*\"\s*\)\s*\.\s*permitAll\(\)", server, "alta", "Spring Security libera todas as rotas (permitAll em /** ou anyRequest)")
        # DRF sem permissão padrão (o padrão é AllowAny)
        if self.stack.get("drf"):
            settings = [f for f in self.files if f.name == "settings.py" or re.search(r"/settings/[\w]+\.py$", f.rel)]
            if settings and not any("DEFAULT_PERMISSION_CLASSES" in f.text for f in settings):
                self.add("C06", "drf_sem_permissao_padrao", settings[0], None, None, "media",
                         "Django REST Framework sem DEFAULT_PERMISSION_CLASSES: o padrão é AllowAny (toda view nova nasce pública)")
        self.rx_rule("C06", "drf_allow_any", r"permission_classes\s*=\s*[\[(]\s*AllowAny", server, "baixa", "View DRF com AllowAny — confirme que é pública")
        self.rx_rule("C06", "rails_skip_auth", r"skip_before_action\s+:authenticate_user!", server, "baixa", "Controller pula authenticate_user! — confirme as ações públicas")
        self.rx_rule("C09", "csrf_desligado", r"skip_before_action\s+:verify_authenticity_token|@csrf_exempt|csrf\(\)\s*\.\s*disable\(\)|"
                     r"csrf\(\s*(?:AbstractHttpConfigurer::disable|\w+\s*->\s*\w+\.disable\(\))\s*\)|\$except\s*=\s*\[\s*['\"]\*['\"]|"
                     r"(?:validateCsrfTokens|preventRequestForgery)\(\s*except:\s*\[\s*['\"]\*['\"]",
                     server, "media", "Proteção CSRF desligada — ok só para API sem cookie de sessão (token no header)")
        self.rx_rule("C06", "aspnet_allow_anonymous", r"\[AllowAnonymous\]", server, "baixa", "[AllowAnonymous] — confirme que a ação é pública")
        self.rx_rule("C06", "jwt_decode_sem_verificar", r"\bjwt\.decode\(|jwt_decode\(|jose\.decodeJwt\(", server, "media",
                     "Token decodificado sem verificar assinatura (decode ≠ verify) — confirme que não é usado como prova de identidade",
                     skip_line=r"verify|options=\{\s*['\"]verify_signature['\"]\s*:\s*True")
        self.rx_rule("C06", "jwt_alg_none", r"algorithms?\s*[:=]\s*\[?\s*['\"]none['\"]", server, "alta", "JWT aceitando algoritmo 'none'")

    # -- regras por framework (front e back além de Node/Next/Supabase) ----------
    def scan_frameworks(self):
        code, server, client = self.code(), self.server_code(), self.client_code()
        cfg = [f for f in self.files if f.kind == "config"]
        php = [f for f in code if f.ext == ".php"]
        rb = [f for f in code if f.ext in (".rb", ".erb")]
        jvm = [f for f in code if f.ext in (".java", ".kt", ".scala", ".groovy")]
        cs = [f for f in code if f.ext in (".cs", ".razor", ".cshtml")]
        go = [f for f in code if f.ext == ".go"]
        R = self.rx_rule
        # C01 app cliente compilado
        R("C01", "dart_define_segredo", r"String\.fromEnvironment\(\s*['\"][A-Z0-9_]*(?:SECRET|OPENAI|API_KEY|TOKEN|SERVICE)[A-Z0-9_]*['\"]",
          [f for f in code if f.ext == ".dart"], "media", "--dart-define com segredo: o valor fica dentro do app compilado")
        # C08 mass assignment
        R("C08", "laravel_request_all", r"(?:::create|->create|->update|->fill|->forceFill|::insert|->insert|::updateOrCreate|->firstOrCreate)\(\s*\$request->(?:all|input)\(\)",
          php, "alta", "Model recebe $request->all(): o usuário manda campos extras (role, is_admin…) — use $request->validated() ou only()")
        R("C08", "laravel_unguard", r"Model::unguard\(\)|\$guarded\s*=\s*\[\s*\]", php, "media", "Model sem proteção de mass assignment")
        R("C08", "adonis_request_all", r"\.(?:create|merge|fill|updateOrCreate|createMany)\(\s*request\.(?:all|body)\(\)", server, "alta",
          "Model do Adonis recebe request.all()/body() inteiro — use request.validateUsing(validator) ou request.only([...])")
        R("C08", "rails_params_direto", r"\.(?:new|create|update|update_attributes|assign_attributes)\(\s*params\[:\w+\]\s*\)", rb, "media",
          "Model recebe params[:x] direto — use strong params (params.require(:x).permit(...))")
        R("C08", "nest_validationpipe_sem_whitelist", r"new\s+ValidationPipe\(\s*\)", server, "media",
          "ValidationPipe sem whitelist: true / forbidNonWhitelisted: true — campos extras passam")
        R("C08", "merge_profundo_com_body", r"(?:_\.merge|merge|deepmerge|lodash\.merge)\(\s*[\w.]+\s*,\s*(?:req\.body|body|request\.body)\b", server, "media",
          "Merge profundo com o body (mass assignment e prototype pollution)")
        R("C08", "go_bind_e_salva", r"(?:ShouldBindJSON|BindJSON|BodyParser)\(\s*&(\w+)\)[\s\S]{0,400}?\.(?:Save|Create|Updates)\(\s*&?\1\b", go, "baixa",
          "Struct preenchida pelo request vai direto ao banco — confira se tem campo que o usuário não pode mudar")
        entities = sorted({m.group(1) for f in jvm for m in re.finditer(r"@Entity[\s\S]{0,300}?class\s+(\w+)", f.text)})
        if entities:
            R("C08", "spring_entity_no_requestbody", r"@RequestBody\s+(?:@Valid\s+)?(?:%s)\b" % "|".join(map(re.escape, entities)), jvm, "media",
              "Controller recebe a @Entity direto no @RequestBody — use DTO com só os campos editáveis")
            R("C17", "spring_retorna_entity", r"public\s+(?:ResponseEntity<\s*)?(?:List<\s*)?(?:%s)\b[^(]*\(" % "|".join(map(re.escape, entities)),
              [f for f in jvm if re.search(r"@RestController", f.text)], "baixa", "Controller devolve a @Entity inteira — risco de expor campos internos")
        # C09 cookies e armazenamento de token no app
        R("C09", "laravel_cookie_inseguro", r"['\"]http_only['\"]\s*=>\s*false|['\"]same_site['\"]\s*=>\s*['\"]none['\"]", php, "alta",
          "config/session.php com cookie de sessão inseguro")
        R("C09", "laravel_secure_default_false", r"['\"]secure['\"]\s*=>\s*env\(\s*['\"]SESSION_SECURE_COOKIE['\"]\s*(?:,\s*false)?\s*\)", php, "baixa",
          "Cookie de sessão só fica Secure se SESSION_SECURE_COOKIE=true no .env de produção — confirme")
        non_js = [f for f in code + cfg if f.ext not in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro")]
        R("C09", "httponly_false_generico", r"(?i)\bhttp_?only\s*[:=]\s*false|SecurePolicy\s*=\s*CookieSecurePolicy\.None|"
          r"cookie\.secure\s*[=:]\s*false|cookie\.http-only\s*[=:]\s*false", non_js, "alta", "Cookie de sessão sem HttpOnly/Secure",
          skip_line=r"^\s*(//|#|\*)")
        R("C09", "token_em_asyncstorage", r"AsyncStorage\.setItem\(\s*['\"`][^'\"`]*(?:token|jwt|session|auth)", code, "media",
          "Token em AsyncStorage (texto puro no aparelho) — use expo-secure-store/Keychain", flags=re.I)
        R("C09", "token_em_sharedpreferences", r"(?:setString|putString)\(\s*['\"][^'\"]*(?:token|jwt|session|auth)", [f for f in code if f.ext in (".dart", ".kt", ".java")],
          "media", "Token em SharedPreferences (texto puro) — use flutter_secure_storage/EncryptedSharedPreferences", flags=re.I)
        if self.stack.get("expo_rn"):
            R("C09", "supabase_sessao_asyncstorage", r"storage\s*:\s*AsyncStorage\b", code, "baixa",
              "Sessão do Supabase em AsyncStorage (texto puro no aparelho) — prefira um adaptador com expo-secure-store")
        if "react-scripts" in self.deps and not any(re.search(r"GENERATE_SOURCEMAP\s*=\s*false", x.text) for x in self.files
                                                      if x.kind == "env" or x.name == "package.json"):
            self.add("C15", "cra_sourcemap_padrao", "package.json", None, None, "baixa",
                     "Create React App gera source map público por padrão: defina GENERATE_SOURCEMAP=false no build")
        # C10 senhas
        R("C10", "spring_noop_encoder", r"NoOpPasswordEncoder|\{noop\}", jvm + cfg, "alta", "Senha sem hash (NoOpPasswordEncoder/{noop})")
        R("C10", "hash_rapido_jvm_cs_go", r"MessageDigest\.getInstance\(\s*\"(?:MD5|SHA-1|SHA-256)\"|(?:MD5|SHA1|SHA256)\.Create\(\)|md5\.Sum\(|sha1\.Sum\(|sha256\.Sum256\(",
          jvm + cs + go, "alta", "Hash rápido perto de senha — use bcrypt/Argon2id", near=r"(?i)pass(word)?|senha|pwd")
        R("C10", "laravel_bcrypt_rounds_baixo", r"['\"]rounds['\"]\s*=>\s*env\(\s*['\"]BCRYPT_ROUNDS['\"]\s*,\s*[4-9]\s*\)", php, "media", "bcrypt com custo < 10")
        # C11 rate limit em outros frameworks (sinal para não acusar falta à toa)
        rl_rx = (r"throttle:|RateLimiter::for\(|Rack::Attack|rack-attack|bucket4j|RateLimiter\b|AddRateLimiter|UseRateLimiter|"
                 r"\[EnableRateLimiting|x/time/rate|tollbooth|httprate|ulule/limiter|nuxt-security|sveltekit-rate-limiter|"
                 r"@convex-dev/rate-limiter|limiter\.Limit|rateLimitMiddleware|limiter\.New\(|gofiber/fiber/v\d/middleware/limiter|"
                 r"type\s*=\s*\"ratelimit\"|\"ratelimits\"\s*:|\[\[ratelimits\]\]|RATE_LIMITER\.limit\(")
        extra_rl = [f.rel for f in code + cfg if re.search(rl_rx, f.text)]
        if extra_rl:
            self.signals["C11"]["rate_limit_framework_em"] = extra_rl[:10]
        R("C11", "next_image_wildcard", r"hostname\s*:\s*['\"]\*\*['\"]", [f for f in self.files if re.match(r"next\.config\.", f.name)], "media",
          "images.remotePatterns com hostname '**': qualquer um usa seu otimizador de imagens (custo e abuso)")
        # C12 sinais extras
        bot_extra = [f.rel for f in code + cfg if re.search(r"initializeAppCheck|ReCaptcha(?:V3|Enterprise)Provider|laravel-cloudflare-turnstile|"
                                                            r"no-captcha|django-recaptcha|recaptcha/api|cf-turnstile|hcaptcha", f.text, re.I)]
        if bot_extra:
            self.signals["C12"]["protecao_framework_em"] = bot_extra[:10]
        # C13 injeção em PHP, Ruby, Java, C#, Go
        R("C13", "laravel_raw_interpolado", r"(?:DB::raw|whereRaw|selectRaw|orderByRaw|havingRaw|DB::select|DB::statement|DB::update|DB::delete)\(\s*\"[^\"\n]*\$\w+|"
          r"(?:DB::raw|whereRaw|selectRaw|orderByRaw|DB::select|DB::statement)\([^;\n]*\.\s*\$(?:request|_GET|_POST|\w+)", php, "alta",
          "SQL cru do Laravel com variável interpolada/concatenada — use bindings (?)")
        R("C13", "rails_sql_interpolado", r"\.(?:where|order|group|having|joins|select|find_by_sql|pluck|exists\?)\(\s*\"[^\"\n]*#\{", rb, "alta",
          "SQL com interpolação #{} no Rails — use where(\"x = ?\", valor) ou hash")
        R("C13", "rails_order_params", r"\.order\(\s*params\[", rb, "media", "order(params[...]) sem allowlist")
        R("C13", "jvm_sql_concatenado", r"(?:createQuery|createNativeQuery|prepareStatement|executeQuery|executeUpdate|query|update|execute)\(\s*\"[^\"\n]*"
          r"(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)[^\"\n]*\"\s*\+", jvm, "alta", "SQL montado por concatenação (JPA/JDBC)", flags=re.I)
        R("C13", "jvm_string_format_sql", r"String\.format\(\s*\"[^\"\n]*(?:SELECT|INSERT|UPDATE|DELETE)\b", jvm, "alta", "SQL montado com String.format", flags=re.I)
        R("C13", "dotnet_sql_raw_interpolado", r"(?:FromSqlRaw|ExecuteSqlRaw|ExecuteSqlRawAsync|SqlQueryRaw)\(\s*\$\"|new\s+SqlCommand\(\s*\$?\"[^\"\n]*\"\s*\+|"
          r"new\s+SqlCommand\(\s*\$\"", cs, "alta", "SQL cru com interpolação no .NET — use FromSqlInterpolated ou parâmetros")
        R("C13", "go_sql_sprintf", r"\.(?:Query|QueryRow|Exec|QueryContext|ExecContext|Raw|Where|Order)\(\s*fmt\.Sprintf\(|"
          r"\.(?:Query|QueryRow|Exec|Raw|Where)\(\s*\"[^\"\n]*\"\s*\+", go, "alta", "SQL montado com fmt.Sprintf/concatenação no Go — use placeholders")
        # C14 XSS, SSRF, path traversal, desserialização
        R("C14", "angular_bypass_sanitizer", r"bypassSecurityTrust(?:Html|Script|Style|Url|ResourceUrl)\(", code, "media",
          "Angular: bypassSecurityTrust* desliga a sanitização — confirme que o conteúdo é confiável")
        R("C14", "blade_sem_escape", r"\{!!\s*\$(?!errors)[\w\->\[\]'\"]+\s*!!\}", [f for f in php if f.name.endswith(".blade.php")], "media",
          "Blade {!! !!} imprime HTML sem escapar (XSS se vier do usuário)")
        R("C14", "rails_html_safe", r"\.html_safe\b|\braw\(", rb, "media", "html_safe/raw no Rails — HTML sem escape")
        R("C14", "go_template_html", r"template\.HTML\(", go, "media", "template.HTML desliga o escape do html/template")
        R("C14", "django_autoescape_off", r"\{%\s*autoescape\s+off\s*%\}", [f for f in self.files if f.ext in (".html", ".htm", ".txt")], "media",
          "Template Django com autoescape off")
        R("C14", "thymeleaf_utext", r"th:utext\s*=", [f for f in self.files if f.ext in (".html", ".htm")], "media",
          "Thymeleaf th:utext imprime HTML sem escapar")
        R("C07", "aspnet_cors_qualquer_origem", r"SetIsOriginAllowed\(\s*\w+\s*=>\s*true\s*\)", cs, "alta",
          "CORS do .NET aceita qualquer origem (com AllowCredentials, qualquer site lê dados logados)")
        R("C15", "go_pprof_exposto", r"_\s+\"net/http/pprof\"", go, "media", "net/http/pprof importado: /debug/pprof exposto se o mux padrão estiver na internet")
        R("C14", "ssrf_url_do_usuario", r"(?:fetch|axios(?:\.\w+)?|got|request|requests\.(?:get|post)|httpx\.(?:get|post)|urlopen|http\.Get|HttpClient\.\w+Async)\(\s*"
          r"(?:req\.(?:body|query|params)|request\.(?:args|json|form|GET|POST)|body|params|input|searchParams\.get)\b[\w.\[\]'\"]*",
          server, "media", "Requisição para URL vinda do usuário (SSRF) — valide contra allowlist de domínios")
        R("C14", "path_traversal", r"(?:sendFile|readFile|readFileSync|createReadStream|open|send_file|File\.ReadAll\w*|os\.Open|ioutil\.ReadFile)\(\s*"
          r"(?:path\.join\([^)]*)?(?:req\.(?:query|params|body)|request\.(?:args|GET|query_params)|params|input)\b", server, "media",
          "Arquivo aberto com caminho vindo do usuário (path traversal)")
        R("C14", "open_redirect", r"(?:res\.redirect|redirect|Redirect|redirect_to)\(\s*(?:req\.query|request\.(?:args|GET)|params)\b[\w.\[\]'\"]*", server, "baixa",
          "Redirect para destino vindo do usuário (open redirect) — use allowlist")
        R("C14", "desserializacao_insegura", r"pickle\.loads?\(|yaml\.load\((?![^)]*SafeLoader)|unserialize\(\s*\$_|ObjectInputStream\(|BinaryFormatter|"
          r"Marshal\.load\(|node-serialize", server, "media", "Desserialização insegura (pode executar código)")
        R("C14", "exec_shell_go_jvm", r"exec\.Command\(\s*\"(?:sh|bash|cmd)\"\s*,\s*\"(?:-c|/c)\"|Runtime\.getRuntime\(\)\.exec\(|ProcessBuilder\(",
          go + jvm, "baixa", "Execução de comando do sistema — confira se recebe input")
        R("C14", "webview_origem_aberta", r"originWhitelist=\{\s*\[\s*['\"]\*['\"]\s*\]\s*\}|setJavaScriptEnabled\(true\)", code, "baixa",
          "WebView aceitando qualquer origem/JS — risco se carregar conteúdo de terceiros")
        # C15 vazamento e debug por framework
        R("C15", "spring_actuator_aberto", r"management\.endpoints\.web\.exposure\.include\s*[=:]\s*['\"]?\*|include:\s*['\"]\*['\"]", cfg, "alta",
          "Spring Actuator expõe todos os endpoints (env, heapdump…)")
        R("C15", "spring_stacktrace", r"server\.error\.include-stacktrace\s*[=:]\s*always|include-stacktrace:\s*always", cfg, "media", "Stack trace na resposta de erro")
        R("C15", "h2_console", r"spring\.h2\.console\.enabled\s*[=:]\s*true", cfg, "alta", "Console do H2 ligado (acesso total ao banco)")
        R("C15", "rails_erros_detalhados", r"consider_all_requests_local\s*=\s*true", [f for f in rb if "production" in f.rel], "alta",
          "Rails em produção mostrando erro detalhado")
        R("C15", "aspnet_developer_exception", r"UseDeveloperExceptionPage\(\)", cs, "media",
          "UseDeveloperExceptionPage — confirme que está dentro de if (env.IsDevelopment())", skip_line=r"IsDevelopment")
        R("C15", "django_allowed_hosts_aberto", r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]\s*\]", code, "media", "ALLOWED_HOSTS = ['*']")
        R("C15", "php_debug_leftover", r"\b(?:dd|dump|var_dump|print_r|phpinfo)\(", [f for f in php if "/app/" in "/" + f.rel or "/routes/" in "/" + f.rel],
          "baixa", "dd()/var_dump()/phpinfo() esquecido no código")
        R("C15", "gin_debug", r"gin\.SetMode\(\s*gin\.DebugMode\s*\)", go, "baixa", "Gin em modo debug")
        R("C15", "angular_sourcemap_prod", r"\"sourceMap\"\s*:\s*true", [f for f in cfg if f.name == "angular.json"], "baixa",
          "angular.json com sourceMap: true — confira se não está na configuração de produção")
        R("C15", "webpack_sourcemap", r"devtool\s*:\s*['\"](?:source-map|inline-source-map|eval-source-map)['\"]",
          [f for f in code if "webpack" in f.name or "craco" in f.name], "baixa", "Webpack gera source map público")
        R("C15", "swagger_publico", r"SwaggerModule\.setup\(|app\.UseSwaggerUI\(|springdoc\.swagger-ui\.enabled\s*[=:]\s*true", code + cfg, "baixa",
          "Documentação da API pública — desative ou proteja em produção", skip_line=r"IsDevelopment|NODE_ENV")
        R("C15", "android_debuggable", r"android:debuggable\s*=\s*\"true\"", cfg, "alta", "App Android com debuggable=true")
        R("C15", "directory_listing", r"(?m)^\s*autoindex\s+on\s*;|Options\s+[+]?Indexes", [f for f in self.files if f.name in ("nginx.conf", ".htaccess") or f.ext == ".conf"],
          "media", "Listagem de diretório ligada no servidor web")
        for f in self.files:
            if ENV_FILE_RX.match(f.name) and not is_env_example(f.name) and re.search(r"(?m)^\s*APP_DEBUG\s*=\s*true", f.text) \
                    and re.search(r"(?m)^\s*APP_ENV\s*=\s*prod", f.text):
                self.add("C15", "laravel_debug_producao", f, None, None, "alta", "APP_ENV=production com APP_DEBUG=true")
        debug_libs = [d for d in ("composer:barryvdh/laravel-debugbar", "composer:fruitcake/laravel-debugbar")
                      if d in self.deps and d not in self.dev_only]
        if debug_libs:
            self.add("C15", "debugbar_em_producao", "composer.json", None, None, "media", "laravel-debugbar no require (não só no require-dev)")
        # C16 uploads em outros frameworks
        R("C16", "nome_original_framework", r"getClientOriginalName\(\)|getOriginalFilename\(\)|\.FileName\b|header\.Filename", code, "media",
          "Nome original do arquivo enviado em uso — gere o nome no servidor", near=r"(?i)store|save|path|copy|move|write|create|join|Combine")
        # C17 respostas
        for f in php:
            if re.search(r"/Models/User\.php$", f.rel) and "password" in f.text and not re.search(
                    r"\$hidden\s*=\s*\[[^\]]*['\"]password|#\[\s*Hidden\(\s*\[[^\]]*['\"]password", f.text):
                self.add("C17", "laravel_user_sem_hidden", f, None, None, "media",
                         "Model User sem $hidden com 'password': o hash da senha sai em todo JSON que devolve o usuário")
        R("C17", "laravel_all_sem_paginacao", r"return\s+[\w\\]+::all\(\)|response\(\)->json\(\s*[\w\\]+::all\(\)", php, "baixa", "Model::all() na resposta — pagine")
        R("C17", "rails_render_model", r"render\s+json:\s*@?(?:user|users|account|customer)s?\b(?!\.\w)", rb, "media",
          "render json: do model inteiro (inclui password_digest e campos internos)")
        # C18 headers: sinais por framework
        hdr = {"Spring Security (padrão: nosniff, X-Frame-Options, HSTS)": self.stack.get("spring_security"),
               "Rails (padrão: X-Frame-Options, nosniff, Referrer-Policy)": self.stack.get("rails"),
               "nuxt-security": "nuxt-security" in self.deps,
               "hono secureHeaders": any("secureHeaders(" in f.text for f in server),
               "@fastify/helmet": "@fastify/helmet" in self.deps,
               "SvelteKit kit.csp": any(f.name.startswith("svelte.config") and re.search(r"\bcsp\s*:", f.text) for f in self.files),
               "Django CSP": any(re.search(r"SECURE_CSP|CSP_DEFAULT_SRC|ContentSecurityPolicyMiddleware|csp\.middleware", f.text) for f in code)}
        self.signals["C18"]["defaults_do_framework"] = [k for k, v in hdr.items() if v]
        # C19 HTTPS em apps e frameworks
        R("C19", "android_cleartext", r"usesCleartextTraffic\s*=\s*\"true\"|cleartextTrafficPermitted\s*=\s*\"true\"", cfg, "alta",
          "Android permite tráfego sem HTTPS (cleartext)")
        for f in self.files:
            if f.name == "Info.plist" and re.search(r"<key>NSAllowsArbitraryLoads</key>\s*<true\s*/>", f.text):
                self.add("C19", "ios_arbitrary_loads", f, None, None, "alta", "iOS com NSAllowsArbitraryLoads = true (ATS desligado)")
        R("C19", "flutter_certificado_aceito", r"badCertificateCallback\s*=\s*\([^)]*\)\s*=>\s*true", [f for f in code if f.ext == ".dart"], "alta",
          "Flutter aceitando qualquer certificado TLS")
        R("C19", "rails_force_ssl_off", r"config\.force_ssl\s*=\s*false", rb, "media", "Rails com force_ssl = false")
        R("C19", "django_ssl_redirect_off", r"SECURE_SSL_REDIRECT\s*=\s*False", code, "baixa", "SECURE_SSL_REDIRECT = False (ok se o proxy redireciona)")
        R("C19", "aspnet_https_metadata_off", r"RequireHttpsMetadata\s*=\s*false", cs, "media", "JWT aceitando metadata sem HTTPS")
        # C04 BaaS além do Supabase/Firebase
        for f in self.files:
            if re.search(r"(^|/)pb_migrations/.+\.js$|pb_schema\.json$", f.rel):
                for m in re.finditer(r"[\"']?(list|view|create|update|delete)Rule[\"']?\s*[:=]\s*[\"']{2}", f.text):
                    n = f.lineno(m.start())
                    write = m.group(1) in ("create", "update", "delete")
                    self.add("C04", "pocketbase_regra_publica", f, n, f.line(n), "alta" if write else "media",
                             f"PocketBase {m.group(1)}Rule vazia = aberta para qualquer um" + ("" if write else " (leitura: confirme se é pública)"))
        R("C04", "appwrite_permissao_any", r"Permission\.(?:write|update|delete|create)\(\s*Role\.any\(\)\s*\)|\"(?:write|update|delete|create)\(\\\"any\\\"\)\"",
          code + cfg, "alta", "Appwrite: qualquer visitante pode escrever/apagar")
        R("C04", "appwrite_leitura_publica_ou_qualquer_conta", r"Permission\.read\(\s*Role\.any\(\)\s*\)|Permission\.(?:write|update|delete)\(\s*Role\.users\(\)\s*\)",
          code + cfg, "media", "Appwrite: leitura pública ou escrita para qualquer conta (cadastro aberto) — confirme se é intencional")
        for f in self.files:
            if f.name.endswith(".rules") or f.name in ("firestore.rules", "storage.rules"):
                self.rx_rule("C04", "firebase_qualquer_logado", r"allow\s+[\w,\s]+:\s*if\s+request\.auth\s*!=\s*null\s*;", [f], "media",
                             "Regra Firebase 'request.auth != null' sem checar o dono: qualquer conta (cadastro é aberto) lê/escreve tudo")
            if re.search(r"(^|/)pb_migrations/.+\.js$|pb_schema\.json$", f.rel):
                self.rx_rule("C04", "pocketbase_qualquer_logado",
                             r"(?:list|view|update|delete)Rule[\"']?\s*[:=]\s*[\"']\s*@request\.auth\.id\s*!=\s*(?:''|\"\"|\\\"\\\")\s*[\"']", [f], "media",
                             "PocketBase: regra só exige estar logado, sem checar o dono do registro")
        R("C07", "clerk_unsafe_metadata_papel", r"unsafeMetadata\??\.\s*(?:role|isAdmin|is_admin|plan|tier)", self.files, "alta",
          "Clerk unsafeMetadata é editável pelo próprio usuário: papel/plano vai em publicMetadata/privateMetadata")

    # -- C08 mass assignment -----------------------------------------------------
    def scan_mass_assignment(self):
        server = self.server_code()
        body = r"(?:req\.body|request\.body|ctx\.request\.body|body|await\s+req(?:uest)?\.json\(\)|await\s+c\.req\.json\(\)|payload)"
        for rule, rx, note in (
            ("data_do_request", r"\bdata\s*:\s*" + body + r"\s*[,}\n]", "ORM recebendo o body inteiro (data: body)"),
            ("create_update_com_body", r"\.(?:create|insert|update|upsert|createMany|updateMany|findOneAndUpdate|findByIdAndUpdate|"
                                       r"updateOne|insertOne|insertMany|build)\(\s*" + body + r"\s*[,)]",
             "Criação/atualização com o body inteiro"),
            ("spread_do_body", r"\.\.\.\s*(?:req\.body|request\.body|body|payload)\b", "Spread do body em objeto que pode ir ao banco"),
            ("object_assign_body", r"Object\.assign\([^,\n]+,\s*(?:req\.body|request\.body|body)\b", "Object.assign com o body"),
        ):
            pattern = re.compile(rx)
            for f in server:
                parsed = bool(re.search(r"\.(?:parse|safeParse|parseAsync|pick|omit)\(|\.strict\(\)", f.text))
                for m in pattern.finditer(f.text):
                    n = f.lineno(m.start())
                    self.add("C08", rule, f, n, f.line(n), "baixa" if parsed else "media",
                             note + (" (há validação no arquivo — confirme se o objeto validado é estrito)" if parsed else ""))
        self.rx_rule("C08", "django_fields_all", r"fields\s*=\s*['\"]__all__['\"]", server, "media", "Form/serializer com fields='__all__'")
        self.rx_rule("C08", "python_kwargs_do_request", r"\*\*\s*(?:request\.(?:json|data|POST|get_json\(\))|payload|body|data)(?:\.(?:dict|model_dump)\(\))?\s*\)",
                     server, "baixa", "Objeto do request expandido direto em construtor/ORM")
        self.rx_rule("C08", "rails_permit_all", r"params\.permit!", server, "alta", "params.permit! libera todos os campos")
        self.rx_rule("C08", "laravel_guarded_vazio", r"\$guarded\s*=\s*\[\s*\]", server, "media", "Model Laravel sem campos protegidos")

    # -- C09 cookies -------------------------------------------------------------
    def scan_cookies(self):
        code = self.code()
        self.rx_rule("C09", "token_em_localstorage", r"localStorage\.setItem\(\s*['\"`][^'\"`]*(?:token|jwt|\\bauth\\b|auth[_-]?(?:token|data|state|session|user)|session[_-]?(?:id|token|key)|access[_-]?token|refresh[_-]?token|id[_-]?token|sb-[\\w-]*-auth)",
                     code, "alta", "Token de sessão em localStorage (legível por qualquer script/XSS)", flags=re.I)
        self.rx_rule("C09", "token_em_sessionstorage", r"sessionStorage\.setItem\(\s*['\"`][^'\"`]*(?:token|jwt|\\bauth\\b|auth[_-]?(?:token|data|state|session|user)|session[_-]?(?:id|token|key)|access[_-]?token|refresh[_-]?token|id[_-]?token|sb-[\\w-]*-auth)",
                     code, "media", "Token em sessionStorage (legível por JS)", flags=re.I)
        self.rx_rule("C09", "document_cookie_token", r"document\.cookie\s*=\s*['\"`]?\s*(?:token|jwt|\\bauth\\b|auth[_-]?(?:token|data|state|session|user)|session[_-]?(?:id|token|key)|access[_-]?token|refresh[_-]?token|id[_-]?token|sb-[\\w-]*-auth)", code, "alta",
                     "Cookie de sessão escrito via JS (não pode ser HttpOnly)", flags=re.I)
        self.rx_rule("C09", "httponly_false", r"httpOnly\s*:\s*false", code, "alta", "Cookie com httpOnly: false",
                     skip_line=r"(?i)xsrf|csrf")  # cookie de CSRF double-submit precisa ser lido pelo JS
        self.rx_rule("C09", "secure_false", r"\bsecure\s*:\s*false", code, "media", "Cookie com secure: false (ok só em dev)",
                     near=r"cookie|session")
        self.rx_rule("C09", "samesite_none", r"sameSite\s*:\s*['\"]none['\"]", code, "media", "SameSite=None exige proteção CSRF", flags=re.I)
        self.rx_rule("C09", "django_cookie_inseguro", r"(?:SESSION_COOKIE_SECURE|CSRF_COOKIE_SECURE|SESSION_COOKIE_HTTPONLY)\s*=\s*False",
                     code, "alta", "Cookie de sessão/CSRF inseguro no Django")
        for f in self.server_code():
            for m in re.finditer(r"\.(?:cookie|set_cookie)\(\s*['\"][^'\"]+['\"]", f.text):
                n = f.lineno(m.start())
                if not re.search(r"httpOnly|httponly|HttpOnly", f.window(n, 0, 6)):
                    self.add("C09", "cookie_sem_flags", f, n, f.line(n), "baixa", "Cookie definido sem httpOnly visível — confira as flags")

    # -- C10 senhas ----------------------------------------------------------------
    def scan_passwords(self):
        code = self.code()
        self.rx_rule("C10", "hash_rapido", r"createHash\(\s*['\"](?:md5|sha1|sha256|sha512)['\"]\)", code, "alta",
                     "Hash rápido (MD5/SHA) perto de senha — use Argon2id/bcrypt", near=r"(?i)passw(?:or)?d|\\bpasswd\\b|\\bsenha\\b|\\bpwd\\b")
        self.rx_rule("C10", "hash_rapido_py", r"hashlib\.(?:md5|sha1|sha256|sha512)\(", code, "alta",
                     "Hash rápido (hashlib) perto de senha", near=r"(?i)passw(?:or)?d|\\bpasswd\\b|\\bsenha\\b|\\bpwd\\b")
        self.rx_rule("C10", "md5_php_sql", r"\b(?:md5|sha1)\(\s*\$?\w*(?:pass|senha)", code + [f for f in self.files if f.ext == ".sql"], "alta",
                     "MD5/SHA1 aplicado em senha", flags=re.I)
        for f in code:
            for m in re.finditer(r"bcrypt\w*\.(?:hash|hashSync|genSalt|genSaltSync)\([^)\n]*?\b([4-9])\s*\)", f.text):
                n = f.lineno(m.start())
                self.add("C10", "bcrypt_custo_baixo", f, n, f.line(n), "media", f"bcrypt com custo {m.group(1)} (use ≥ 10, ideal 12)")
        schema = [f for f in self.files if f.ext in (".sql", ".prisma") or re.search(r"(models\.py|schema\.(t|j)s)$", f.rel)]
        self.rx_rule("C10", "coluna_senha_sem_hash", r"(?im)^\s*\"?(?:password|senha|pass|pwd)\"?\s+(?:text|varchar|character varying|string)\b",
                     schema, "media", "Coluna de senha sem 'hash' no nome — confirme que guarda hash, não a senha")
        hash_lib = any(d in self.deps for d in ("bcrypt", "bcryptjs", "argon2", "@node-rs/argon2", "@node-rs/bcrypt", "scrypt-js")) or \
            any(d in self.py_deps for d in ("passlib", "argon2-cffi", "bcrypt", "pwdlib")) or \
            any(re.search(r"Argon2Hasher|BcryptHasher|PasswordHash\(|CryptContext\(|PasswordHasher\(|make_password|generate_password_hash", f.text)
                for f in self.server_code())
        for f in self.server_code():
            if re.search(r"bcrypt|argon2|scrypt|pbkdf2|hashPassword|make_password|generate_password_hash|password_hash\(|pwdlib|passlib", f.text, re.I):
                continue
            for m in re.finditer(r"\bpassword\s*:\s*(?:req\.body\.password|body\.password|input\.password|data\.password|password)\s*[,}\n]", f.text):
                n = f.lineno(m.start())
                if re.search(r"signUp|signIn|auth\.|login|createUserWith|credentials|verify|compare|supabase|firebase|clerk", f.window(n, 4, 1), re.I):
                    continue
                if re.search(r"\.(?:create|insert|save|update|upsert)\(", f.window(n, 6, 2)):
                    self.add("C10", "senha_gravada_direto", f, n, f.line(n), "media", "Senha parece ser gravada sem hash")
        managed = []
        for name, rx in (("Supabase Auth", r"auth\.(?:signUp|signInWithPassword|signInWithOtp|signInWithOAuth)"),
                         ("NextAuth/Auth.js", r"next-auth|@auth/"), ("Clerk", r"@clerk/"), ("Firebase Auth", r"firebase/auth|getAuth\("),
                         ("Auth0", r"@auth0/"), ("Better Auth", r"better-auth"), ("Lucia", r"\blucia\b"), ("Cognito/Amplify", r"aws-amplify|cognito"),
                         ("Django auth", r"django\.contrib\.auth"), ("Devise", r"devise")):
            if any(re.search(rx, f.text) for f in self.code()[:4000]) or any(re.search(rx, d) for d in self.deps):
                managed.append(name)
        self.signals["C10"]["auth_gerenciada"] = managed
        self.signals["C10"]["lib_de_hash"] = hash_lib

    # -- C11 / C12 abuso -----------------------------------------------------------
    def scan_abuse(self):
        rl_libs = ("@upstash/ratelimit", "express-rate-limit", "rate-limiter-flexible", "express-slow-down", "@nestjs/throttler",
                   "@fastify/rate-limit", "hono-rate-limiter", "koa-ratelimit", "@arcjet/next", "@arcjet/node", "@arcjet/bun",
                   "next-rate-limit", "lru-cache-ratelimit", "limiter", "bottleneck", "@vercel/firewall", "@adonisjs/limiter",
                   "elysia-rate-limit", "@nest-lab/throttler-storage-redis")
        py_rl = ("slowapi", "flask-limiter", "django-ratelimit", "fastapi-limiter")
        found = [d for d in rl_libs if d in self.deps] + [d for d in py_rl if d in self.py_deps]
        code_rl = [f.rel for f in self.server_code() if re.search(r"\b(?:rateLimit|RateLimiter|Ratelimit|rateLimiter|slowDown|"
                                                                   r"ThrottlerGuard|@Throttle|limiter\.limit|DEFAULT_THROTTLE_RATES|"
                                                                   r"throttle_classes|arcjet)\b", f.text)]
        llm_files = [f.rel for f in self.server_code() if re.search(r"(?:from|require\()\s*['\"](?:openai|@anthropic-ai/sdk|ai|@ai-sdk/[\w-]+|"
                                                                    r"@google/genai|@google/generative-ai|langchain|@langchain/[\w-]+|groq-sdk)['\"]|"
                                                                    r"^\s*(?:from|import)\s+(?:openai|anthropic|langchain|litellm)|"
                                                                    r"OpenAI::(?:client|factory|Client)|Anthropic::Client|sashabaranov/go-openai|"
                                                                    r"openai-go|anthropic-sdk-go|com\.openai|OpenAIClient\(|AnthropicClient\(|"
                                                                    r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com", f.text, re.M)]
        mail_files = [f.rel for f in self.server_code() if re.search(r"(?:from|require\()\s*['\"](?:resend|nodemailer|@sendgrid/mail|twilio|"
                                                                     r"postmark|mailgun\.js|@aws-sdk/client-ses)['\"]", f.text)]
        self.signals["C11"].update({"libs": found, "uso_no_codigo": code_rl[:10], "endpoints_de_ia": llm_files[:20],
                                    "envio_email_sms": mail_files[:10]})
        no_max_tokens = [r for r in llm_files if not re.search(r"max_?(?:output_?|completion_?)?tokens|maxTokens|maxOutputTokens|max_tokens_to_sample",
                                                                 next((f.text for f in self.files if f.rel == r), ""), re.I)]
        if no_max_tokens:
            self.signals["C11"]["ia_sem_teto_de_tokens"] = no_max_tokens[:10]
        if not found and not code_rl and not self.signals["C11"].get("rate_limit_framework_em"):
            if llm_files:
                self.add("C11", "ia_sem_rate_limit", llm_files[0], None, None, "alta",
                         f"Nenhum rate limit no código e {len(llm_files)} arquivo(s) chamam IA — risco de conta da API explodir")
            elif self.routes:
                gerenciada = [n for n, ok in (("Supabase Auth", self.stack.get("supabase")), ("Firebase Auth", self.stack.get("firebase")),
                                              ("Clerk", self.stack.get("clerk")), ("Better Auth", self.stack.get("better_auth")),
                                              ("Auth0", self.stack.get("auth0"))) if ok]
                self.add("C11", "sem_rate_limit", None, None, None, "baixa" if gerenciada else "media",
                         "Nenhum rate limit encontrado no código — confirme se existe no edge (Cloudflare/WAF/API Gateway)" +
                         (f"; o login já é limitado por {', '.join(gerenciada)}, confira as demais rotas" if gerenciada else ""))

        bot_rx = r"turnstile|recaptcha|hcaptcha|botid|@arcjet|altcha|friendly-challenge|captchaToken|honeypot|cf-turnstile"
        bot_files = [f.rel for f in self.code() if re.search(bot_rx, f.text, re.I)] + (self.signals["C12"].get("protecao_framework_em") or [])
        if self.signals["C12"].get("supabase_captcha_config"):
            bot_files.append("supabase/config.toml ([auth.captcha] enabled)")
        verify = [f.rel for f in self.code() if re.search(r"siteverify|captchaToken|checkBotId|arcjet|enforceAppCheck|consumeAppCheckToken|"
                                                          r"ValidTurnstile|Rule::turnstile|['\"]recaptcha['\"]|NoCaptcha|captcha_response|"
                                                          r"verify_recaptcha|ReCaptchaField", f.text)]
        if self.signals["C12"].get("supabase_captcha_config"):
            verify.append("supabase/config.toml")
        forms = [f.rel for f in self.code() if f.side != "server" and not TEST_PATH_RX.search(f.rel) and re.search(r"<form\b|onSubmit=|handleSubmit\(|v-on:submit|@submit", f.text)]
        signup = [f.rel for f in self.code() if not TEST_PATH_RX.search(f.rel) and re.search(r"auth\.signUp\(|createUserWithEmailAndPassword|/signup|/register|/cadastro|"
                                                          r"signUp\.create|registerUser", f.text)]
        self.signals["C12"].update({"protecao_encontrada_em": bot_files[:10], "verificacao_servidor_em": verify[:10],
                                    "formularios": len(forms), "fluxo_de_cadastro_em": signup[:10]})
        if not bot_files and (signup or forms):
            self.add("C12", "sem_bot_protection", (signup or forms)[0], None, None, "media",
                     "Formulários/cadastro sem CAPTCHA/Turnstile/BotID aparente")
        elif bot_files and not verify:
            self.add("C12", "captcha_sem_verificacao", bot_files[0], None, None, "media",
                     "Widget anti-bot presente mas sem verificação no servidor (siteverify/captchaToken) aparente")
        if not forms and not signup:
            self.signals["C12"]["sem_formularios"] = True

    # -- C13 / C14 injeção -------------------------------------------------------------
    def scan_injection(self):
        code = self.code()
        server = self.server_code()
        self.rx_rule("C13", "raw_unsafe", r"\$(?:queryRawUnsafe|executeRawUnsafe)\(", code, "alta",
                     "Prisma *Unsafe — confirme que não há input interpolado (prefira $queryRaw com template tag)")
        sqlkw = re.compile(r"\b(select|insert|update|delete|where|from|values|order\s+by)\b", re.I)
        for f in code:
            for m in re.finditer(r"\.(?:query|execute|raw|exec|unsafe|prepare|run|all|get)\(\s*`\s*((?:select|insert|update|delete|with|merge|replace|upsert)\b[^`]{0,800}?)\$\{",
                                 f.code, re.I):
                if sqlkw.search(m.group(1)):
                    n = f.lineno(m.start())
                    self.add("C13", "sql_template_interpolado", f, n, f.line(n), "alta", "SQL montado com interpolação de template string")
        var_sql = [
            (r"(?:const|let|var)\s+(\w+)\s*=\s*`\s*(?:select|insert|update|delete|with)\b[^`]*\$\{", r"\.(?:query|execute|raw|unsafe|prepare|run|all|get)\(\s*%s\b"),
            (r"(\w+)\s*=\s*f(['\"]{1,3})\s*(?:select|insert|update|delete|with)\b[^\n]*?\{", r"\.execute(?:many)?\(\s*%s\b"),
            (r"\$(\w+)\s*=\s*\"\s*(?:select|insert|update|delete)\b[^\"\n]*\$\w+", r"(?:mysqli_query|mysql_query|->query|->exec|->prepare)\([^)]*\$%s\b"),
        ]
        for f in code:
            for decl, call in var_sql:
                for m in re.finditer(decl, f.code, re.I):
                    if re.search(call % re.escape(m.group(1)), f.code[m.end(): m.end() + 3000]):
                        n = f.lineno(m.start())
                        self.add("C13", "sql_montado_em_variavel", f, n, f.line(n), "alta",
                                 f"SQL montado com interpolação na variável '{m.group(1)}' e executado depois")
        self.rx_rule("C13", "query_builder_interpolado",
                     r"\.(?:where|andWhere|orWhere|having|orderBy|whereRaw|orWhereRaw|havingRaw|orderByRaw|joinRaw|fromRaw)\(\s*`[^`]*\$\{",
                     server, "alta", "Query builder (TypeORM, knex, Sequelize…) com string interpolada — use parâmetros")
        self.rx_rule("C13", "sql_concatenado", r"['\"](?:SELECT|INSERT|UPDATE|DELETE|WITH)\b[^'\"\n]*['\"]\s*\+\s*[A-Za-z_$]", code, "media",
                     "SQL montado por concatenação", flags=re.I)
        self.rx_rule("C13", "py_execute_fstring", r"\.execute(?:many)?\(\s*f['\"]", code, "alta", "execute() com f-string")
        self.rx_rule("C13", "py_execute_format", r"\.execute(?:many)?\(\s*['\"][^'\"\n]*['\"]\s*(?:%\s*[\w(]|\.format\()", code, "alta",
                     "execute() com formatação de string (% ou .format)")
        self.rx_rule("C13", "orm_raw_fstring", r"(?:\.raw|\btext|\.extra)\(\s*f['\"]", code, "alta", "SQL cru com f-string (Django raw / SQLAlchemy text)")
        self.rx_rule("C13", "nosql_body_direto", r"\.(?:find|findOne|deleteMany|deleteOne|updateMany|updateOne|countDocuments)\(\s*"
                                                 r"(?:req\.body|req\.query|body|request\.json)\s*[,)]", server, "alta",
                     "Query NoSQL com objeto do request (injeção de operadores $)")
        self.rx_rule("C13", "nosql_where", r"['\"]\$where['\"]|\$where\s*:", server, "media", "$where executa JavaScript no Mongo")
        self.rx_rule("C13", "postgrest_filtro_string", r"\.(?:or|filter|not)\(\s*`[^`\n]*\$\{", code, "media",
                     "Filtro do Supabase/PostgREST montado com string interpolada — input pode injetar filtros")
        self.rx_rule("C13", "php_query_superglobal", r"(?:mysqli_query|mysql_query|->query|->exec)\([^;\n]*\$_(?:GET|POST|REQUEST|COOKIE)",
                     code, "alta", "Query com superglobal do PHP")

        # C14
        val_libs = [d for d in ("zod", "yup", "joi", "valibot", "class-validator", "ajv", "superstruct", "@sinclair/typebox",
                                "express-validator", "celebrate", "arktype", "typia", "@vinejs/vine", "@hapi/joi", "elysia", "@adonisjs/validator") if d in self.deps]
        val_libs += [d for d in ("pydantic", "marshmallow", "djangorestframework", "cerberus", "fastapi") if d in self.py_deps]
        val_libs += [d for d in ("go:github.com/go-playground/validator/v10", "go:github.com/go-ozzo/ozzo-validation/v4",
                                 "nuget:fluentvalidation", "nuget:fluentvalidation.aspnetcore", "mvn:spring-boot-starter-validation")
                     if d in self.deps]
        imported = sorted({m.group(1) for f in self.code() for m in re.finditer(
            r"(?:from|require\()\s*['\"](zod|yup|joi|valibot|class-validator|ajv|superstruct|express-validator|arktype|@sinclair/typebox)['\"]", f.text)})
        missing_dep = [lib for lib in imported if lib not in self.deps]
        val_libs = sorted(set(val_libs) | set(imported))
        if missing_dep:
            self.signals["C14"]["importada_mas_fora_do_package_json"] = missing_dep
        self.signals["C14"]["libs_de_validacao"] = val_libs
        builtin_validation = any(self.stack.get(k) for k in ("laravel", "rails", "django", "spring", "aspnet", "adonis", "phoenix", "symfony"))
        if not val_libs and not builtin_validation and any(r.get("le_input") for r in self.routes):
            self.add("C14", "sem_lib_de_validacao", None, None, None, "media", "Nenhuma lib de validação de schema e há rotas lendo input")
        for rule, rx, conf, note, skip in (
            ("dangerously_set_inner_html", r"dangerouslySetInnerHTML", "media", "HTML injetado no React — precisa de sanitização", None),
            ("v_html", r"\bv-html\s*=", "media", "v-html renderiza HTML cru", None),
            ("svelte_html", r"\{@html\s", "media", "{@html} renderiza HTML cru", None),
            ("inner_html", r"\.(?:innerHTML|outerHTML)\s*[+]?=\s*(?!['\"`]{2})", "media", "innerHTML com conteúdo dinâmico", None),
            ("eval", r"(?<![\w.])eval\(|new Function\(", "media", "eval/new Function — execução de código", r"^\s*(//|#)"),
            ("document_write", r"document\.write\(", "baixa", "document.write", None),
            ("jinja_safe", r"\|\s*safe\b|mark_safe\(|Markup\(", "baixa", "Conteúdo marcado como seguro (sem escape)", None),
            ("render_template_string", r"render_template_string\(", "media", "render_template_string (SSTI se houver input)", None),
            ("jinja_sem_autoescape", r"jinja2\.Template\(|(?<!\w)Template\(\s*(?:f?['\"])|Environment\((?![^)]*autoescape)", "baixa",
             "Template Jinja2 sem autoescape explícito — HTML com dado do usuário vira XSS", r"autoescape"),
            ("rehype_raw", r"rehype-raw|rehypeRaw", "media", "Markdown com HTML cru (saída de LLM/usuário vira XSS)", None),
            ("shell_interpolado", r"(?:exec|execSync|spawn|spawnSync|execa)\(\s*`[^`\n]*\$\{", "alta", "Comando de shell montado com interpolação", None),
            ("py_shell", r"(?:os\.system|os\.popen|subprocess\.(?:run|call|Popen|check_output|check_call))\(\s*f['\"]", "alta",
             "Comando de shell com f-string", None),
            ("shell_true", r"shell\s*=\s*True", "media", "subprocess com shell=True", None),
        ):
            pattern = re.compile(rx)
            for f in code:
                sanitized = bool(re.search(r"DOMPurify|sanitize|sanitizeHtml|xss\(|bleach|rehype-sanitize", f.code))
                for m in pattern.finditer(f.code):
                    n = f.lineno(m.start())
                    ln = f.line(n)
                    if skip and re.search(skip, ln):
                        continue
                    c = conf
                    if rule in ("dangerously_set_inner_html", "v_html", "svelte_html", "inner_html", "rehype_raw") and sanitized:
                        c = "baixa"
                    self.add("C14", rule, f, n, ln, c, note + (" (há sanitização no arquivo — confirme)" if c == "baixa" and sanitized else ""))

    # -- C15 vazamento ---------------------------------------------------------------
    def scan_leaks(self):
        code = self.code()
        cfg = code + [f for f in self.files if f.kind == "config"]
        self.rx_rule("C15", "source_maps_producao", r"productionBrowserSourceMaps\s*:\s*true", cfg, "alta", "Source maps públicos em produção (código-fonte legível)")
        self.rx_rule("C15", "vite_sourcemap", r"sourcemap\s*:\s*true", [f for f in cfg if "vite.config" in f.name or "vite" in f.rel], "media",
                     "Vite gera source maps públicos (use false ou 'hidden')")
        self.rx_rule("C15", "django_debug", r"(?m)^\s*DEBUG\s*=\s*True", code, "alta", "DEBUG = True fixo")
        self.rx_rule("C15", "flask_debug", r"\.run\([^)\n]*debug\s*=\s*True", code, "alta", "Flask debug=True — debugger interativo permite executar código")
        self.rx_rule("C15", "stack_na_resposta", r"(?:json|send|write|end|jsonify|Response)\([^)\n]*\b(?:err|error|e|ex|exception)\.stack", code, "alta",
                     "Stack trace devolvido ao cliente")
        self.rx_rule("C15", "erro_inteiro_na_resposta", r"(?:\.json|\.send|jsonify)\(\s*(?:err|error|e|ex)\s*[,)]", self.server_code(), "media",
                     "Objeto de erro inteiro devolvido ao cliente")
        self.rx_rule("C15", "mensagem_interna", r"(?:\.json|Response\.json|NextResponse\.json|jsonify)\(\s*\{[^}\n]*\b(?:err|error|e)\.message",
                     self.server_code(), "baixa", "Mensagem de erro interna devolvida (pode vazar SQL/infra)")
        self.rx_rule("C15", "traceback_na_resposta", r"traceback\.format_exc\(\)", code, "media", "Traceback possivelmente devolvido na resposta",
                     near=r"return|Response|jsonify|HTTPException")
        self.rx_rule("C15", "log_sensivel", r"console\.(?:log|info|debug|warn)\([^)\n]*(?:password|senha|token|secret|apiKey|api_key|authorization|cpf|cardNumber)",
                     code, "media", "Log com dado sensível", flags=re.I)
        self.rx_rule("C15", "log_sensivel_py", r"(?:print|logger\.\w+|logging\.\w+)\([^)\n]*(?:password|senha|token|secret|api_key|cpf)",
                     [f for f in code if f.ext == ".py"], "media", "Log com dado sensível", flags=re.I)
        self.rx_rule("C15", "static_na_raiz", r"express\.static\(\s*(?:__dirname|['\"]\.\/?['\"]|process\.cwd\(\))\s*\)", code, "media",
                     "express.static servindo a raiz do projeto (pode expor .env/código)")
        infra = [f for f in self.files if f.kind == "config" or f.name in ("Dockerfile",)]
        self.rx_rule("C15", "traefik_api_insecure", r"--api\.insecure=true|api\.insecure\s*[:=]\s*true", infra, "media",
                     "Dashboard do Traefik sem autenticação (api.insecure)")
        self.rx_rule("C15", "painel_de_banco", r"(?m)^\s*(?:image:\s*)?['\"]?(?:adminer|phpmyadmin/phpmyadmin|phpmyadmin|dpage/pgadmin4|mongo-express)\b",
                     [f for f in infra if re.search(r"compose|docker", f.name, re.I)], "baixa",
                     "Painel de banco no Compose — garanta que não fica exposto na internet em produção")
        if self.stack.get("fastapi"):
            apps = [f for f in self.server_code() if re.search(r"=\s*FastAPI\(", f.text)]
            if apps and not any(re.search(r"docs_url\s*=|openapi_url\s*=", f.text) for f in apps):
                self.add("C15", "fastapi_docs_publico", apps[0], None, None, "baixa",
                         "/docs e /openapi.json públicos em produção (mapa da API para atacante) — desative ou proteja")
        for f in self.files:
            if re.search(r"(^|/)(public|static|www|wwwroot)/", f.rel) and re.search(r"(\.env(\.|$)|\.sql$|\.bak$|\.dump$|\.log$|\.sqlite3?$|\.pem$|\.key$)", f.name):
                self.add("C15", "arquivo_sensivel_publico", f, None, None, "alta", "Arquivo sensível dentro da pasta pública (servido pela web)")

    # -- C16 uploads -------------------------------------------------------------------
    def scan_uploads(self):
        code = self.code()
        up_rx = re.compile(r"multer|formidable|busboy|express-fileupload|\.get\(\s*['\"](?:file|files|upload|image|avatar|document)['\"]\)|"
                           r"UploadFile|request\.FILES|\.storage\s*\.from\([^)]*\)\s*\.upload\(|uploadBytes(?:Resumable)?\(|PutObjectCommand|"
                           r"createPresignedPost|getSignedUrl|uploadthing|createUploadthing|type=['\"]file['\"]|"
                           r"\$request->file\(|->hasFile\(|MultipartFile|IFormFile|FormFile\(|has_(?:one|many)_attached|"
                           r"models\.(?:File|Image)Field\(|readMultipartFormData\(|@fastify/multipart|ImagePicker|image_picker|DocumentPicker")
        up_files = [f for f in code if up_rx.search(f.text)]
        server_up = [f for f in up_files if f.side != "client"]
        client_up = [f for f in up_files if f.side == "client"]
        self.signals["C16"]["upload_em"] = [f.rel for f in up_files][:15]
        if not up_files:
            self.signals["C16"]["sem_upload"] = True
            return
        size_rx = re.compile(r"fileSize|maxFileSize|MAX_FILE_SIZE|MAX_UPLOAD|max_size|maxSize|\.size\s*>|size\s*>\s*\d|content-length-range|"
                             r"['\"]max:\d+|max-file-size|MaxRequestBodySize|RequestSizeLimit|MaxMultipartMemory|ParseMultipartForm\(|"
                             r"ContentLength|file_size_limit|fileSizeLimit|MAX_CONTENT_LENGTH|DATA_UPLOAD_MAX_MEMORY_SIZE|maxFileSize", re.I)
        type_rx = re.compile(r"fileFilter|mimetype|file-type|fileTypeFrom|python-magic|\bmagic\.|allowed_mime|ALLOWED_TYPES|allowedTypes|"
                             r"['\"]mimes:|['\"]mimetypes:|content_type:\s*\{|validates\s+:\w+,\s*content_type|ContentType\s*(?:==|!=|\.StartsWith)|"
                             r"DetectContentType\(|getContentType\(\)|"
                             r"allowedMimeTypes|allowed_mime_types|content_type\s*(?:in|not in|==)|\.type\s*(?:===|!==|\.startsWith)|"
                             r"\.includes\(\s*\w*\.type\)|image/(?:jpeg|png|webp)", re.I)
        scope = server_up or client_up
        if not any(size_rx.search(f.text) for f in up_files):
            self.add("C16", "upload_sem_limite", scope[0], None, None, "media", "Upload sem limite de tamanho aparente")
        if not any(type_rx.search(f.text) for f in server_up):
            self.add("C16", "upload_sem_validacao_tipo", scope[0], None, None, "media" if server_up else "baixa",
                     "Upload sem validação de tipo no servidor aparente" + ("" if server_up else " (upload direto do cliente: valide via policy/bucket)"))
        self.rx_rule("C16", "nome_original_no_caminho", r"(?:path\.join|path\.resolve|`[^`\n]*\$\{)[^\n]*(?:originalname|originalFilename|file\.name\b|\.filename\b)",
                     up_files, "media", "Nome original do arquivo usado no caminho (path traversal/sobrescrita)", skip_line=r"secure_filename|randomUUID|uuid|nanoid")
        self.rx_rule("C16", "svg_permitido", r"image/svg\+xml", up_files, "media", "SVG aceito no upload (pode carregar XSS)")
        self.rx_rule("C16", "bucket_publico", r"createBucket\([^)]*public\s*:\s*true", code, "media", "Bucket criado como público")
        self.rx_rule("C16", "bucket_publico_sql", r"insert\s+into\s+storage\.buckets[^;]*\btrue\b", [f for f in self.files if f.ext == ".sql"],
                     "media", "Bucket do Supabase Storage público — confirme que só guarda arquivos públicos", flags=re.I | re.S)

    # -- C17 respostas -----------------------------------------------------------------
    def scan_responses(self):
        server = self.server_code()
        for f in server:
            for m in re.finditer(r"\.findMany\(", f.code):
                n = f.lineno(m.start())
                if not re.search(r"\btake\s*:", f.window(n, 0, 12)):
                    self.add("C17", "findmany_sem_take", f, n, f.line(n), "baixa", "findMany sem take (listagem sem limite)")
            for m in re.finditer(r"\.select\(\s*['\"]\*['\"]\s*\)", f.code):
                n = f.lineno(m.start())
                if re.search(r"\.(?:range|limit|single|maybeSingle)\(", f.window(n, 2, 6)):
                    self.add("C17", "select_estrela", f, n, f.line(n), "baixa", "select('*') devolve todas as colunas — confira se há campo sensível na resposta")
                else:
                    self.add("C17", "select_estrela_sem_limite", f, n, f.line(n), "media", "select('*') sem limite — todas as colunas e todas as linhas")
            for m in re.finditer(r"(?i)['\"`]\s*SELECT\s+\*\s+FROM\b[^'\"`]*['\"`]", f.code):
                n = f.lineno(m.start())
                if not re.search(r"(?i)\blimit\b|\bwhere\s+\w*id\s*=", m.group(0)):
                    self.add("C17", "sql_select_estrela_sem_limit", f, n, f.line(n), "baixa", "SELECT * sem LIMIT — todas as colunas e linhas")
        self.rx_rule("C17", "objeto_usuario_inteiro", r"(?:res\.json|res\.send|NextResponse\.json|Response\.json|jsonify|c\.json)\(\s*(?:user|users|profile|account|customer|member)s?\s*[,)]",
                     server, "media", "Objeto de usuário inteiro na resposta — risco de expor hash/tokens/campos internos")
        self.rx_rule("C17", "limit_sem_teto", r"(?:take|limit|per_?page|pageSize)\s*[:=]\s*(?:Number|parseInt|int|\+)\s*\(?\s*(?:req\.query|searchParams|query|request\.args)",
                     server, "media", "Limite de página vindo do request sem teto", skip_line=r"Math\.min|min\(")
        self.rx_rule("C17", "limit_sem_teto_fastapi", r"\blimit\s*:\s*int\s*=\s*\d+", [f for f in server if f.ext == ".py"], "baixa",
                     "Parâmetro limit sem teto (use Query(le=100))", skip_line=r"\ble\s*=")
        gql = [d for d in ("@apollo/server", "apollo-server", "apollo-server-express", "graphql-yoga", "mercurius", "type-graphql", "@nestjs/graphql") if d in self.deps]
        if gql:
            armor = any(d in self.deps for d in ("graphql-depth-limit", "@escape.tech/graphql-armor", "graphql-query-complexity", "graphql-validation-complexity")) \
                or any(re.search(r"queryDepth\s*:|depthLimit\(|maxDepth", f.text) for f in self.server_code())
            if not armor:
                self.add("C17", "graphql_sem_limite", None, None, None, "media", "GraphQL sem limite de profundidade/complexidade")
            self.rx_rule("C17", "graphql_introspection", r"introspection\s*:\s*true", self.code(), "media", "Introspection do GraphQL ligada")

    # -- C18 / C19 infra ---------------------------------------------------------------
    def scan_headers_https(self):
        pool = [f for f in self.files if f.kind in ("code", "config") or f.name in ("_headers", "nginx.conf", "Caddyfile", ".htaccess")]
        joined = {f.rel: f.text for f in pool}
        helmet = any(d in self.deps for d in ("helmet", "koa-helmet", "@fastify/helmet"))
        talisman = "flask-talisman" in self.py_deps
        django_sec = any("SecurityMiddleware" in t for t in joined.values())
        found = {}
        for key, rx in (("CSP", r"Content-Security-Policy"), ("HSTS", r"Strict-Transport-Security|SECURE_HSTS_SECONDS|\bhsts\b"),
                        ("X-Frame-Options", r"X-Frame-Options|frame-ancestors|frameguard|X_FRAME_OPTIONS"),
                        ("X-Content-Type-Options", r"X-Content-Type-Options|nosniff|SECURE_CONTENT_TYPE_NOSNIFF"),
                        ("Referrer-Policy", r"Referrer-Policy|referrerPolicy|SECURE_REFERRER_POLICY"),
                        ("Permissions-Policy", r"Permissions-Policy|permissionsPolicy|PERMISSIONS_POLICY")):
            where = [p for p, t in joined.items() if re.search(rx, t, re.I)]
            found[key] = where[:5]
        if helmet:
            for k in ("CSP", "HSTS", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy"):
                found[k] = found[k] or ["(helmet)"]
        if talisman:
            for k in ("CSP", "HSTS", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy"):
                found[k] = found[k] or ["(flask-talisman)"]
        if django_sec:
            found["X-Content-Type-Options"] = found["X-Content-Type-Options"] or ["(Django SecurityMiddleware)"]
        self.signals["C18"]["headers_no_codigo"] = found
        self.signals["C18"]["helmet"] = helmet
        missing = [k for k, v in found.items() if not v]
        fw = self.signals["C18"].get("defaults_do_framework") or []
        if len(missing) == 6 and fw:
            self.add("C18", "headers_pelo_framework", None, None, None, "baixa",
                     "Nenhum header escrito no código, mas o framework/módulo manda alguns por padrão (" + "; ".join(fw) +
                     ") — confirme com check_url.py quais saem de fato (CSP quase nunca vem pronta)")
        elif len(missing) == 6:
            self.add("C18", "sem_security_headers", None, None, None, "media",
                     "Nenhum security header configurado no código (a plataforma pode adicionar alguns — confirme com check_url.py)")
        elif missing:
            self.add("C18", "headers_faltando", None, None, None, "baixa", "Headers não encontrados no código: " + ", ".join(missing))
        for p, t in joined.items():
            m = re.search(r"script-src[^;\"'`]*'unsafe-(?:inline|eval)'", t)
            if m:
                self.add("C18", "csp_unsafe", p, None, None, "baixa", "CSP com 'unsafe-inline'/'unsafe-eval' em script-src")
        if self.stack.get("nextjs"):
            nc = [f for f in self.files if re.match(r"next\.config\.(js|mjs|ts|cjs)$", f.name)]
            if nc and not any(re.search(r"poweredByHeader\s*:\s*false", f.text) for f in nc):
                self.add("C18", "x_powered_by", nc[0], None, None, "baixa", "Next.js envia X-Powered-By (poweredByHeader: false)")
        if self.stack.get("express") and not helmet and not any(re.search(r"disable\(\s*['\"]x-powered-by", t) for t in joined.values()):
            self.add("C18", "x_powered_by", None, None, None, "baixa", "Express envia X-Powered-By (use helmet ou app.disable('x-powered-by'))")

        # C19
        cfg_code = [f for f in self.files if f.kind in ("code", "config") and f.kind != "env"]
        self.rx_rule("C19", "tls_verificacao_desligada", r"rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED['\"]?\s*[=:]\s*['\"]?0|"
                                                         r"InsecureSkipVerify\s*:\s*true|CURLOPT_SSL_VERIFYPEER\s*,\s*(?:false|0)",
                     cfg_code, "alta", "Verificação de certificado TLS desligada")
        self.rx_rule("C19", "py_verify_false", r"verify\s*=\s*False", [f for f in cfg_code if f.ext == ".py"], "alta", "requests/httpx com verify=False")
        self.rx_rule("C19", "db_sem_tls", r"sslmode=(?:disable|allow)|\bssl\s*:\s*false", cfg_code, "media", "Conexão com banco sem TLS")
        for f in self.server_code():
            for m in re.finditer(r"new\s+(?:pg\.)?(?:Pool|Client)\(\s*\{[^}]*connectionString[^}]*\}", f.text):
                if "ssl" not in m.group(0):
                    n = f.lineno(m.start())
                    self.add("C19", "pg_sem_ssl", f, n, f.line(n), "baixa",
                             "pg sem opção ssl — sem sslmode=require na DATABASE_URL a conexão vai sem TLS")
        http_rx = (r"['\"`(]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|host\.docker\.internal|"
                   r"[\w.-]*\.local\b|[\w.-]*\.test\b|[\w.-]*\.internal\b|example\.|www\.w3\.org|w3\.org|schemas\.|json-schema\.org|purl\.org|"
                   r"ns\.adobe|www\.apache\.org|xml\.org|xmlpull|java\.sun|opensource\.org|www\.gnu\.org|\$\{|['\"`)])[^\s'\"`)]+")
        self.rx_rule("C19", "url_http", http_rx, [f for f in cfg_code if not f.name.endswith((".svg", ".xml"))], "baixa",
                     "URL http:// (mixed content / tráfego sem TLS)", skip_line=r"^\s*(//|#|\*)")
        platform = [k for k in ("vercel", "netlify", "cloudflare") if self.stack.get(k)]
        for f in self.files:
            if f.name in ("render.yaml", "fly.toml", "railway.json", "railway.toml", "app.yaml", "amplify.yml", "firebase.json"):
                platform.append(f.name)
        self.signals["C19"]["plataforma_com_https_automatico"] = platform
        self.signals["C19"]["redirect_no_codigo"] = any(re.search(r"x-forwarded-proto|SECURE_SSL_REDIRECT\s*=\s*True|return 301 https|"
                                                                  r"force_ssl|requireHTTPS|enforce-https|express-sslify|redirections\.entrypoint\.scheme=https|redirectscheme|"
                                                                  r"RedirectScheme|redirect-to-https|always_use_https|ssl_redirect", t, re.I)
                                                        for t in joined.values())

    # -- P01–P10 prontidão para o lançamento ----------------------------------------
    ENV_REF_RX = re.compile(
        r"process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]|import\.meta\.env\.([A-Z][A-Z0-9_]+)|"
        r"os\.environ(?:\.get)?\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]|os\.environ\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]|os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]|"
        r"\benv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]|ENV(?:\.fetch\(|\[)\s*['\"]([A-Z][A-Z0-9_]+)['\"]|System\.getenv\(\s*\"([A-Z][A-Z0-9_]+)\"|"
        r"Deno\.env\.get\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]|os\.Getenv\(\s*\"([A-Z][A-Z0-9_]+)\"|GetEnvironmentVariable\(\s*\"([A-Z][A-Z0-9_]+)\"")
    RUNTIME_ENV = {"NODE_ENV", "PORT", "HOST", "HOME", "PATH", "PWD", "CI", "TZ", "LANG", "HOSTNAME", "DEBUG", "VERCEL", "VERCEL_ENV",
                   "VERCEL_URL", "NETLIFY", "RENDER", "FLY_APP_NAME", "RAILWAY_ENVIRONMENT", "NEXT_RUNTIME", "APP_ENV", "ENV",
                   "ENVIRONMENT", "PYTHONPATH", "SHELL", "USER", "TERM", "DENO_DEPLOYMENT_ID", "K_SERVICE", "GITHUB_ACTIONS"}

    def scan_prontidao(self):
        sig = self.signals
        code = self.code()
        paths = [f.rel for f in self.files]
        # P01 — variáveis documentadas, localhost no cliente, chave de teste no .env de produção
        refs = {}
        for f in code + [x for x in self.files if x.kind == "config" and x.ext in (".yml", ".yaml", ".toml")]:
            if TEST_PATH_RX.search(f.rel):
                continue
            for m in self.ENV_REF_RX.finditer(f.text):
                name = next(g for g in m.groups() if g)
                if name in self.RUNTIME_ENV or name.startswith(("npm_", "VERCEL_GIT")):
                    continue
                # variável com valor padrão é opcional: env('X', 'padrão'), getenv("X", "padrão"), process.env.X || 'padrão'
                after = f.text[m.end(): m.end() + 40]
                if re.match(r"\s*(?:['\"]\s*)?(?:,|\)\s*(?:\|\||\?\?|or\b)|\s*(?:\|\||\?\?))", after):
                    continue
                refs.setdefault(name, f.rel)
        examples = [f for f in self.files if f.kind == "env" and is_env_example(f.name)] + \
                   [f for f in self.files if f.name in ("example.env", "env.example", ".env.dist")]
        documented = {m.group(1) for f in examples for m in re.finditer(r"(?m)^\s*#?\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", f.text)}
        documented |= {"SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL", "SUPABASE_PUBLISHABLE_KEYS",
                       "SUPABASE_SECRET_KEYS", "SUPABASE_JWKS"}  # injetadas pelo Supabase nas Edge Functions
        sig["P01"]["variaveis_usadas_no_codigo"] = len(refs)
        sig["P01"]["arquivo_de_exemplo"] = [f.rel for f in examples][:5]
        if refs and not examples:
            self.add("P01", "sem_env_example", None, None, None, "media",
                     f"{len(refs)} variáveis de ambiente usadas no código e nenhum .env.example para lembrar quais configurar em produção")
        elif refs:
            missing = sorted(n for n in refs if n not in documented)
            if missing:
                sig["P01"]["faltando_no_exemplo"] = missing[:40]
                self.add("P01", "env_nao_documentada", examples[0], None, None, "baixa",
                         f"{len(missing)} variável(is) usadas no código fora do .env.example: " + ", ".join(missing[:12]))
        for f in self.client_code():
            if TEST_PATH_RX.search(f.rel):
                continue
            for m in re.finditer(r"['\"`]https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?[^'\"`]*['\"`]", f.code):
                n = f.lineno(m.start())
                ln = f.line(n)
                if re.search(r"process\.env|import\.meta\.env|__DEV__|isDev|development", ln):
                    continue
                self.add("P01", "localhost_no_cliente", f, n, ln, "media", "URL de localhost fixa no código do cliente — em produção a chamada quebra")
        for f in self.files:
            if f.kind == "env" and re.search(r"\.env\.prod(uction)?$", f.name) and re.search(r"\b(?:sk|pk)_test_|\bTEST-\d{6,}", f.text):
                self.add("P01", "chave_de_teste_em_producao", f, None, None, "alta", "Chave de TESTE no .env de produção — pagamento não cobra de verdade")
        # P02 — monitoramento de erros
        err_libs = sorted({d for d in self.deps if re.match(r"(@sentry/|sentry-|@bugsnag/|rollbar|@honeybadger-io/|dd-trace|@datadog/|newrelic|"
                                                            r"@highlight-run/|logrocket|@opentelemetry/|@axiomhq/|@logtail/|@vercel/otel|"
                                                            r"composer:sentry/|gem:sentry|mvn:sentry|nuget:sentry|go:github\.com/getsentry)", d)}
                         | {d for d in self.py_deps if d.startswith(("sentry-sdk", "rollbar", "ddtrace", "opentelemetry", "newrelic", "bugsnag"))})
        sig["P02"]["monitoramento_de_erros"] = err_libs
        boundaries = [p for p in paths if re.search(r"(^|/)(global-)?error\.(t|j)sx?$|\+error\.svelte$|(^|/)error\.vue$|ErrorBoundary", p)] + \
                     [f.rel for f in code if re.search(r"componentDidCatch|ErrorBoundary|errorElement\s*[:=]", f.text)][:5]
        sig["P02"]["tela_de_erro_no_front"] = boundaries[:8]
        if not err_libs:
            self.add("P02", "sem_monitoramento_de_erros", None, None, None, "media",
                     "Nenhum SDK de monitoramento de erros (Sentry, Bugsnag, Datadog, OpenTelemetry…): erro em produção passa sem ninguém ver")
        # P03 — backup (quase sempre fora do repo)
        sig["P03"]["scripts_de_backup"] = [f.rel for f in self.files if re.search(
            r"pg_dump|mysqldump|mongodump|litestream|wal-g|pgbackrest|firestore export|supabase db dump|pg_basebackup", f.text)][:10]
        # P04 — CI, testes, migrations
        ci = [p for p in paths if re.search(r"^\.github/workflows/.+\.ya?ml$|^\.gitlab-ci\.yml$|^bitbucket-pipelines\.yml$|"
                                            r"^\.circleci/config\.yml$|^azure-pipelines\.yml$|^Jenkinsfile$", p)]
        tests = [p for p in paths if TEST_PATH_RX.search(p)]
        migr = sorted({m.group(0) for p in paths for m in [re.search(r"^(?:.*/)?(supabase/migrations|prisma/migrations|database/migrations|"
                                                                     r"db/migrate|alembic/versions|migrations|drizzle|pb_migrations)/", p)] if m})
        sig["P04"].update({"ci": ci[:10], "arquivos_de_teste": len(tests), "migrations": migr[:10]})
        uses_db = any(self.stack.get(k) for k in ("prisma", "drizzle", "supabase", "laravel", "rails", "django", "mongoose"))
        if uses_db and not migr:
            self.add("P04", "banco_sem_migrations", None, None, None, "media",
                     "O app usa banco mas não há migrations versionadas: o schema de produção não é reproduzível")
        if not tests:
            self.add("P04", "sem_testes", None, None, None, "baixa", "Nenhum teste automatizado: cada deploy é no escuro")
        if not ci:
            self.add("P04", "sem_ci", None, None, None, "baixa", "Sem CI (build e testes automáticos a cada push)")
        # P05 — health check
        health = [f.rel for f in code if re.search(r"['\"`]/(?:api/)?(?:health|healthz|healthcheck|status|ping|up|livez|readyz)['\"`]|"
                                                   r"health\s*:\s*['\"]/up['\"]|actuator/health|MapHealthChecks|AddHealthChecks", f.text)] + \
                 [p for p in paths if re.search(r"/(health|healthz|status)/route\.(t|j)s$|/api/health\.", p)] + \
                 (["(spring-boot-starter-actuator: /actuator/health)"] if "mvn:spring-boot-starter-actuator" in self.deps else [])
        sig["P05"]["health_check"] = health[:8]
        backend = any(self.stack.get(k) for k in ("express", "fastify", "nestjs", "hono", "koa", "elysia", "laravel", "rails", "django",
                                                  "flask", "fastapi", "spring", "aspnet", "go_web", "nextjs", "nuxt", "sveltekit", "remix"))
        if backend and not health:
            self.add("P05", "sem_health_check", None, None, None, "baixa",
                     "Sem rota de health check (/health ou /up) para o monitor de uptime saber se o app está de pé")
        # P06 — e-mail
        mail = sorted({d for d in self.deps if d in ("resend", "@sendgrid/mail", "postmark", "nodemailer", "mailgun.js", "@aws-sdk/client-ses",
                                                    "@getbrevo/brevo", "@react-email/components", "composer:resend/resend-laravel")})
        sig["P06"]["provedor_de_email"] = mail
        supa_mail = any(re.search(r"auth\.(?:signUp|signInWithOtp|resetPasswordForEmail)\(", f.text) for f in code)
        cfg = next((f for f in self.files if f.rel.endswith("supabase/config.toml")), None)
        if supa_mail:
            smtp = bool(cfg and re.search(r"(?ms)^\[auth\.email\.smtp\][^\[]*?enabled\s*=\s*true", cfg.text))
            sig["P06"]["supabase_auth_envia_email"] = True
            sig["P06"]["supabase_smtp_proprio_no_config"] = smtp
            if not smtp:
                self.add("P06", "supabase_smtp_padrao", cfg or None, None, None, "media",
                         "Supabase Auth manda e-mail (cadastro/OTP/reset) e o config não tem SMTP próprio: o SMTP padrão é só para teste "
                         "(limite baixo e entrega restrita) — confira em Authentication → SMTP Settings")
        for f in self.files:
            if f.kind == "env" and is_env_example(f.name) and re.search(r"(?m)^\s*MAIL_MAILER\s*=\s*log\b", f.text):
                self.add("P06", "laravel_mail_log", f, None, None, "baixa", "MAIL_MAILER=log no exemplo: confira o provedor de e-mail no ambiente de produção")
        # P07 — LGPD. Página que existe (arquivo, rota ou link externo) é diferente de link para página: aceite de termos
        # que levam a um 404 não informa nada ao titular.
        conceito = {"privacidade": "privacidade", "privacy": "privacidade", "politica": "privacidade", "lgpd": "privacidade",
                    "termos": "termos", "terms": "termos"}
        chave = r"(privacidade|privacy|politica|lgpd|termos|terms)"

        def conceitos_em(txt):
            t = re.sub(r"(?<=[a-z])(?=[A-Z])", "-", txt).lower().replace("í", "i")
            return {conceito[m.group(1)] for m in re.finditer(r"(?:^|[^a-z])" + chave, t)}
        nao_pagina = re.compile(r"(?i)checkbox|aceite|accept|consent|banner|modal|dialog|link|footer|rodape|button|botao|toggle|switch")
        ext_pagina = re.compile(r"\.(?:[cm]?[jt]sx?|vue|svelte|astro|mdx?|html?|php|erb|cshtml|razor|py|rb|hbs|njk|liquid)$", re.I)
        paginas, tem = [], set()
        for p in paths:
            base = p.rsplit("/", 1)[-1]
            if not ext_pagina.search(base) or TEST_PATH_RX.search(p) or nao_pagina.search(base):
                continue
            achou = conceitos_em(re.sub(r"\.[\w.]+$", "", base))
            for d in p.split("/")[:-1]:
                achou |= conceitos_em(d) | ({"privacidade", "termos"} if d.lower() == "legal" else set())
            if achou:
                paginas.append(p)
                tem |= achou
        rota_rx = re.compile(r"""(?:\bpath\s*[:=(]\s*|\bpath=\s*\{?\s*|createFileRoute\(\s*|Route::(?:get|view|any|match)\(\s*|\bget\s+|\bpath\(\s*)"""
                             r"""['"`]/?((?:[\w-]+/)*[\w-]*""" + chave + r"""[\w-]*)/?['"`]""", re.I)
        link_rx = re.compile(r"""['"`](/(?:[\w-]+/)*[\w-]*""" + chave + r"""[\w-]*)/?['"`]""", re.I)
        externo_rx = re.compile(r"""https?://[^'"`\s)]*""" + chave, re.I)
        links, fora = [], set()
        for f in code + [x for x in self.files if x.ext in (".html", ".htm")]:
            t = f.code
            for m in rota_rx.finditer(t):
                fora |= conceitos_em(m.group(1))
            for m in externo_rx.finditer(t):
                fora |= conceitos_em(m.group(0).split("//", 1)[-1])
            for m in link_rx.finditer(t):
                if not re.match(r"/(?:api|rest|v\d+|functions|graphql|trpc|auth|storage|_next|static|assets)/", m.group(1), re.I):
                    links.append((m.group(1), f, f.lineno(m.start())))
        tem |= fora
        faltando = [(p, f, n) for p, f, n in links if conceitos_em(p) - tem]
        legal = paginas + ([f"rota ou link externo ({', '.join(sorted(fora))})"] if fora else [])
        trackers_rx = {"Google Analytics/Tag Manager": r"gtag\(|googletagmanager\.com|google-analytics\.com|@next/third-parties|react-ga4",
                       "Meta Pixel": r"fbq\(|connect\.facebook\.net", "Hotjar": r"hotjar", "Microsoft Clarity": r"clarity\.ms",
                       "TikTok Pixel": r"analytics\.tiktok\.com|ttq\.", "LinkedIn Insight": r"snap\.licdn\.com",
                       "Mixpanel": r"mixpanel", "PostHog": r"posthog"}
        trackers = [k for k, rx in trackers_rx.items() if any(re.search(rx, f.text) for f in code + [x for x in self.files if x.ext in (".html", ".htm")])]
        consent = [f.rel for f in code if re.search(r"cookieconsent|cookie-consent|CookieConsent|react-cookie-consent|vanilla-cookieconsent|"
                                                   r"cookiebot|onetrust|osano|klaro|tarteaucitron|cookiehub|consentimento|consent_?mode|gtag\(\s*['\"]consent",
                                                   f.text, re.I)]
        delete_flow = [f.rel for f in code if re.search(r"deleteUser\(|deleteAccount|delete_account|excluir[_ -]?conta|apagar[_ -]?conta|"
                                                       r"auth\.admin\.deleteUser|accounts?/delete|destroyAccount", f.text, re.I)]
        sig["P07"].update({"paginas_legais": sorted(set(legal))[:10], "rastreadores": trackers, "consentimento_em": consent[:5],
                           "exclusao_de_conta_em": delete_flow[:5]})
        if faltando:
            sig["P07"]["links_sem_pagina"] = sorted({p for p, _f, _n in faltando})[:10]
        has_users = bool(self.signals["C10"].get("auth_gerenciada")) or any(r.get("tipo") for r in self.routes) and any(
            re.search(r"signUp|register|cadastro|login", f.text) for f in code[:3000])
        if faltando:
            p, f, n = faltando[0]
            self.add("P07", "link_legal_sem_pagina", f, n, f.line(n), "media",
                     f"O app aponta para {p}, mas não achei a página nem a rota: o link dá 404, e aceite de termos que o titular não "
                     "consegue ler não vale (LGPD art. 9º, § 1º)" + (f". Outros: {', '.join(sorted({x for x, *_ in faltando[1:]})[:5])}"
                                                                   if len({x for x, *_ in faltando}) > 1 else ""))
        elif has_users and not tem:
            self.add("P07", "sem_politica_de_privacidade", None, None, None, "media",
                     "O app coleta dados de usuários e não há página de política de privacidade/termos aparente (LGPD art. 9º)")
        if trackers and not consent:
            self.add("P07", "rastreador_sem_consentimento", None, None, None, "media",
                     "Rastreadores (" + ", ".join(trackers) + ") sem banner de consentimento de cookies aparente")
        if has_users and not delete_flow:
            self.add("P07", "sem_exclusao_de_conta", None, None, None, "baixa",
                     "Sem fluxo aparente para o usuário excluir a conta e os dados (direito do titular, LGPD art. 18)")
        # P08 — SEO e compartilhamento
        html = [f for f in self.files if f.ext in (".html", ".htm") and not TEST_PATH_RX.search(f.rel)]
        layouts = [f for f in code if re.search(r"(^|/)(app/layout|src/app/layout|pages/_app|pages/_document|app\.vue|nuxt\.config|"
                                                r"src/routes/\+layout|src/app\.html)", f.rel)]
        default_title = re.compile(r"<title>\s*(?:Vite \+ \w+(?: \+ TS)?|Vite App|React App|Create Next App|Lovable(?: App)?|Bolt|Svelte(?:Kit)? app|"
                                   r"Nuxt|Angular\w*|My App|Untitled|Document)\s*</title>|title\s*:\s*['\"](?:Create Next App|v0 App|My App)['\"]|"
                                   r"Generated by create next app|Lovable Generated Project|lovable\.dev/opengraph|Created with v0|Generated by v0", re.I)
        for f in html + layouts:
            m = default_title.search(f.text)
            if m:
                n = f.lineno(m.start())
                self.add("P08", "titulo_padrao_de_template", f, n, f.line(n), "media",
                         "Título/descrição/imagem de compartilhamento ainda são os do template (é o que aparece no Google e no WhatsApp)")
        for f in html + layouts + [x for x in self.files if x.kind == "config"]:
            for m in re.finditer(r"<meta[^>]+name=['\"]robots['\"][^>]+noindex|robots\s*:\s*\{[^}]*index\s*:\s*false|X-Robots-Tag['\"]?\s*[,:]\s*['\"][^'\"]*noindex", f.text, re.I):
                n = f.lineno(m.start())
                self.add("P08", "noindex_no_codigo", f, n, f.line(n), "alta", "noindex no código: o Google não vai indexar o site (sobra de staging?)")
        for f in self.files:
            if f.name == "robots.txt" and re.search(r"(?ims)User-agent:\s*\*\s*(?:\n\s*#[^\n]*)*\n\s*Disallow:\s*/\s*$", f.text):
                self.add("P08", "robots_bloqueia_tudo", f, None, None, "alta", "robots.txt bloqueia o site inteiro (Disallow: /)")
        sitemap = [p for p in paths if re.search(r"sitemap\.(xml|ts|js|mjs)$|sitemap-index", p)] + \
                  [d for d in self.deps if d in ("next-sitemap", "@astrojs/sitemap", "@nuxtjs/sitemap", "vite-plugin-sitemap", "sitemap")]
        sig["P08"]["sitemap"] = sitemap[:5]
        for f in html:
            if f.rel not in ("index.html", "public/index.html", "src/index.html", "src/app.html"):
                continue
            t = f.text
            if not re.search(r"property=['\"]og:(?:title|image)['\"]", t) and self.stack.get("frontend_spa"):
                self.add("P08", "sem_open_graph", f, None, None, "baixa", "index.html sem og:title/og:image: link compartilhado sai sem prévia")
            m = re.search(r"<html[^>]*\blang=['\"]en['\"]", t)
            if m and re.search(r"[ãõçáéíóú]", t + " ".join(x.text[:4000] for x in code[:40]), re.I):
                self.add("P08", "lang_en_em_site_pt", f, f.lineno(m.start()), f.line(f.lineno(m.start())), "baixa",
                         '<html lang="en"> num site em português (leitor de tela e Google leem como inglês)')
            if not re.search(r"<meta[^>]+name=['\"]viewport['\"]", t):
                self.add("P09", "sem_viewport", f, None, None, "media", "Sem meta viewport: no celular a página abre minúscula")
            if re.search(r"href=['\"]/vite\.svg['\"]", t):
                self.add("P08", "favicon_padrao", f, None, None, "baixa", "Favicon ainda é o do template (vite.svg)")
        # P09 — imagens pesadas e página 404
        big = []
        for d in ("public", "static", "assets", "src/assets", "app/assets", "resources/images", "wwwroot"):
            base = self.root / d
            if not base.is_dir():
                continue
            for dp, dn, fn in os.walk(base):
                dn[:] = [x for x in dn if x not in SKIP_DIRS]
                for name in fn:
                    if name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".mp4", ".mov")):
                        try:
                            size = (Path(dp) / name).stat().st_size
                        except OSError:
                            continue
                        if size > 500_000:
                            big.append((str((Path(dp) / name).relative_to(self.root)).replace("\\", "/"), size))
        big.sort(key=lambda x: -x[1])
        sig["P09"]["arquivos_pesados"] = [f"{p} ({s // 1024} KB)" for p, s in big[:15]]
        if big:
            total = sum(s for _, s in big)
            self.add("P09", "imagens_pesadas", big[0][0], None, None, "media" if total > 5_000_000 else "baixa",
                     f"{len(big)} imagem(ns)/vídeo(s) acima de 500 KB ({total // 1024} KB no total) — comprima/converta para WebP/AVIF")
        nf = [p for p in paths if re.search(r"not-found\.(t|j)sx?$|(^|/)404\.(html|tsx?|jsx?|vue|svelte|astro)$|\+error\.svelte$|(^|/)error\.vue$", p)] + \
             [f.rel for f in code if re.search(r"path\s*[:=]\s*['\"]\*\*?['\"]", f.text)][:3]
        sig["P09"]["pagina_404"] = nf[:5]
        if not nf and (self.stack.get("frontend_spa") or self.stack.get("nextjs") or self.stack.get("nuxt")):
            self.add("P09", "sem_pagina_404", None, None, None, "baixa", "Sem página 404 própria aparente")
        # P10 — custos (quase sempre fora do repo)
        sig["P10"]["ia_sem_teto_de_tokens"] = self.signals["C11"].get("ia_sem_teto_de_tokens", [])
        for f in self.files:
            if f.name == "vercel.json" and re.search(r"\"schedule\"\s*:\s*\"\*\s+\*\s+\*\s+\*\s+\*\"", f.text):
                self.add("P10", "cron_a_cada_minuto", f, None, None, "baixa", "Cron rodando a cada minuto (custo de execução)")
        if sig["P10"]["ia_sem_teto_de_tokens"]:
            self.add("P10", "ia_sem_max_tokens", sig["P10"]["ia_sem_teto_de_tokens"][0], None, None, "media",
                     "Chamada de IA sem teto de tokens (max_tokens): uma resposta longa ou um abuso custa caro")

    # -- C20 dependências --------------------------------------------------------------
    def installed_version(self, pkg):
        nm = self.root / "node_modules" / pkg / "package.json"
        if nm.exists():
            try:
                return json.loads(nm.read_text(errors="ignore")).get("version"), "node_modules"
            except Exception:
                pass
        lock = self.root / "package-lock.json"
        if lock.exists():
            try:
                data = json.loads(lock.read_text(errors="ignore"))
                v = (data.get("packages", {}).get("node_modules/" + pkg) or {}).get("version") or \
                    (data.get("dependencies", {}).get(pkg) or {}).get("version")
                if v:
                    return v, "package-lock.json"
            except Exception:
                pass
        pnpm = self.root / "pnpm-lock.yaml"
        if pnpm.exists():
            t = pnpm.read_text(errors="ignore")
            m = re.search(r"(?m)^\s{2,}['\"]?/?%s@(\d+\.\d+\.\d+[\w.\-]*)" % re.escape(pkg), t) or \
                re.search(r"(?m)^\s+%s:\s*\n\s+specifier:[^\n]*\n\s+version:\s*['\"]?(\d+\.\d+\.\d+[\w.\-]*)" % re.escape(pkg), t)
            if m:
                return m.group(1), "pnpm-lock.yaml"
        yarn = self.root / "yarn.lock"
        if yarn.exists():
            t = yarn.read_text(errors="ignore")
            m = re.search(r'(?m)^"?%s@[^\n]*:\n\s+version:?\s+"?(\d+\.\d+\.\d+[\w.\-]*)' % re.escape(pkg), t)
            if m:
                return m.group(1), "yarn.lock"
        bun = self.root / "bun.lock"
        if bun.exists():
            m = re.search(r'"%s@(\d+\.\d+\.\d+[\w.\-]*)"' % re.escape(pkg), bun.read_text(errors="ignore"))
            if m:
                return m.group(1), "bun.lock"
        if pkg in self.dep_versions:
            v = self.dep_versions[pkg].strip()
            if re.fullmatch(r"=?\d+\.\d+\.\d+(?:-[\w.]+)?", v):
                return v.lstrip("="), "package.json (versão exata)"
            return v, "package.json (range declarado)"
        return None, None

    def scan_deps(self):
        names = {f.name for f in self.files} | {p.name for p in self.root.iterdir() if p.is_file()}
        locks = sorted(n for n in LOCKFILES if n in names or (self.root / n).exists())
        self.signals["C20"]["lockfiles"] = locks
        dependabot = any((self.root / ".github" / n).exists() for n in ("dependabot.yml", "dependabot.yaml"))
        renovate = any((self.root / n).exists() for n in ("renovate.json", "renovate.json5", ".renovaterc", ".renovaterc.json", ".github/renovate.json"))
        self.signals["C20"]["atualizacao_automatica"] = {"dependabot": dependabot, "renovate": renovate}
        has_node = (self.root / "package.json").exists()
        has_py = bool(self.py_deps)
        if has_node and not any(l in locks for l in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock")):
            self.add("C20", "sem_lockfile", "package.json", None, None, "media", "Projeto Node sem lockfile versionado")
        if not dependabot and not renovate:
            self.add("C20", "sem_atualizacao_automatica", None, None, None, "baixa", "Sem Dependabot/Renovate")

        if "next" in self.deps:
            v, src = self.installed_version("next")
            pv = parse_version(v)
            self.signals["C20"]["next_version"] = {"versao": v, "fonte": src}
            if pv:
                M, m, p, pre = pv
                vt = (M, m, p)
                conf = "alta" if src and "range" not in src else "media"
                suffix = "" if conf == "alta" else " (versão mínima do range no package.json — confira a instalada)"
                if (11, 1, 4) <= vt < (12, 3, 5) or (13, 0, 0) <= vt < (13, 5, 9) or (14, 0, 0) <= vt < (14, 2, 25) or (15, 0, 0) <= vt < (15, 2, 3):
                    self.add("C20", "next_cve_2025_29927", "package.json", None, f"next {v}", conf,
                             "Next.js vulnerável a CVE-2025-29927 (bypass de middleware/auth). Corrigido em 12.3.5 / 13.5.9 / 14.2.25 / 15.2.3" + suffix)
                    self.add("C06", "next_middleware_bypass", "package.json", None, f"next {v}", conf,
                             "Versão do Next permite pular o middleware (CVE-2025-29927) — auth só no middleware cai")
                fixed = {(15, 0): 5, (15, 1): 9, (15, 2): 6, (15, 3): 6, (15, 4): 8, (15, 5): 7, (16, 0): 7}
                vuln = False
                if (M, m) in fixed and p < fixed[(M, m)]:
                    vuln = True
                if M == 14 and m == 3 and pre and "canary" in pre:
                    vuln = True
                if vuln and self.stack.get("next_app_router"):
                    self.add("C20", "next_react2shell", "package.json", None, f"next {v}", conf,
                             "Next.js vulnerável a CVE-2025-66478/CVE-2025-55182 'React2Shell' (RCE, CVSS 10) — atualize e rotacione segredos" + suffix)
                # Boletins de 2026 (jul, ago, set e 14/out): RCEs críticas (use cache, otimização de imagem SVG/AVIF, Windows),
                # SSRF e cache poisoning. Mínimo seguro em 27/10/2026: 15.5.28 (Maintenance LTS) e 16.4.1 (Active LTS).
                # Fonte: nextjs.org/blog/nextjs-security-update-october-14-2026 e september-2026-security-release.
                if (M == 16 and vt < (16, 4, 1)) or (M == 15 and vt < (15, 5, 28)):
                    self.add("C20", "next_boletins_2026", "package.json", None, f"next {v}", conf,
                             "Next.js abaixo do mínimo seguro de 2026 (15.5.28 / 16.4.1): RCEs críticas e SSRF corrigidas em jul–out/2026 — "
                             "atualize para a última da sua linha" + suffix)
                elif 13 <= M <= 14:
                    self.add("C20", "next_linha_sem_suporte", "package.json", None, f"next {v}", conf,
                             f"Next.js {M}.x não recebe mais correção de segurança e está na faixa das RCEs de 2026 — migre para 15.5.28+ ou 16.4.1+" + suffix)
                elif M <= 12:
                    self.add("C20", "next_linha_sem_suporte", "package.json", None, f"next {v}", "media" if conf == "alta" else conf,
                             f"Next.js {M}.x sem suporte há anos — migre para uma linha mantida (15.5 ou 16)" + suffix)
        if not self.args.no_audit:
            self.run_audits(locks, has_py)
        if not any(a.get("executado") for a in (self.signals["C20"].get("auditoria") or {}).values()):
            self.signals["C20"]["auditoria_executada"] = False
            self.add("C20", "auditoria_nao_executada", None, None, None, "baixa",
                     "Auditoria de dependências não executada (--no-audit, sem rede ou ferramenta ausente) — rode npm audit/pip-audit")
            self.avisos.append("Auditoria de dependências não executada")

    JS_AUDITORIAS = (  # lockfile, ferramenta, comando só de produção, comando completo (para separar o que é só de dev)
        ("package-lock.json", "npm", ["npm", "audit", "--json", "--omit=dev"], ["npm", "audit", "--json"]),
        ("pnpm-lock.yaml", "pnpm", ["pnpm", "audit", "--json", "--prod"], ["pnpm", "audit", "--json"]),
        ("yarn.lock", "yarn", ["yarn", "audit", "--json", "--groups", "dependencies"], ["yarn", "audit", "--json"]),
        ("bun.lock", "bun", ["bun", "audit", "--json", "--prod"], ["bun", "audit", "--json"]),
        ("bun.lockb", "bun", ["bun", "audit", "--json", "--prod"], ["bun", "audit", "--json"]),
    )

    def run_audits(self, locks, has_py):
        audits = {}
        js = next((x for x in self.JS_AUDITORIAS if x[0] in locks and shutil.which(x[1])), None)
        if js:
            _lk, tool, prod, completo = js
            rc, out, err = run(prod, self.root, 150)
            a = self.parse_js_audit(out, rc, err)
            a["comando"] = " ".join(prod)
            if a.get("executado"):
                rc2, out2, err2 = run(completo, self.root, 150)
                b = self.parse_js_audit(out2, rc2, err2)
                if b.get("executado"):
                    ja = {x["pacote"] for x in a["achados"]}
                    a["so_dev"] = [x for x in b["achados"] if x["pacote"] not in ja]
            audits[tool] = a
        req = next((p for p in ("requirements.txt", "requirements/prod.txt", "requirements/base.txt") if (self.root / p).exists()), None)
        if has_py and req and shutil.which("pip-audit"):
            cmd = ["pip-audit", "-f", "json", "-r", req]
            rc, out, err = run(cmd, self.root, 180)
            try:
                data = json.loads(out)
                deps = data.get("dependencies", data) if isinstance(data, dict) else data
                vulns = [(d["name"], v["id"]) for d in deps for v in d.get("vulns", [])]
                audits["pip-audit"] = {"executado": True, "total": len(vulns), "exemplos": vulns[:15]}
            except Exception:
                audits["pip-audit"] = {"executado": False, "erro": (err or out)[:300]}
        if "composer.lock" in locks and shutil.which("composer"):
            rc, out, err = run(["composer", "audit", "--format=json", "--no-dev", "--locked"], self.root, 150)
            try:
                data = json.loads(out)
                adv = [(pkg, a.get("cve") or a.get("advisoryId"), (a.get("severity") or "").lower())
                       for pkg, lst in (data.get("advisories") or {}).items() for a in (lst if isinstance(lst, list) else lst.values())]
                counts = {}
                for _p, _i, sev in adv:
                    counts[sev or "unknown"] = counts.get(sev or "unknown", 0) + 1
                audits["composer"] = {"executado": True, "vulnerabilidades": counts,
                                      "pacotes": sorted({f"{p} ({s or '?'})" for p, _i, s in adv if s in ("critical", "high")})[:20]}
            except Exception:
                audits["composer"] = {"executado": False, "erro": (err or out)[:300]}
        if shutil.which("osv-scanner") and not any(a.get("executado") for a in audits.values()):
            rc, out, err = run(["osv-scanner", "scan", "source", "-r", "--format", "json", "."], self.root, 240)
            try:
                data = json.loads(out)
                vul = [v for r in data.get("results", []) for p in r.get("packages", []) for v in p.get("vulnerabilities", [])]
                audits["osv-scanner"] = {"executado": True, "total": len(vul), "exemplos": [(v.get("id"), "") for v in vul[:15]]}
            except Exception:
                audits["osv-scanner"] = {"executado": False, "erro": (err or out)[:300]}
        if (self.root / "go.mod").exists() and shutil.which("govulncheck"):
            rc, out, err = run(["govulncheck", "./..."], self.root, 240)
            n = len(set(re.findall(r"\bGO-\d{4}-\d+\b", out)))
            audits["govulncheck"] = {"executado": rc in (0, 3), "total": n}
        if any(f.ext == ".csproj" for f in self.files) and shutil.which("dotnet"):
            rc, out, err = run(["dotnet", "list", "package", "--vulnerable", "--include-transitive"], self.root, 240)
            sev = re.findall(r"\b(Critical|High|Moderate|Low)\b", out)
            audits["dotnet"] = {"executado": rc == 0, "vulnerabilidades": {s.lower(): sev.count(s) for s in set(sev)}}
        if (self.root / "Gemfile.lock").exists() and shutil.which("bundle-audit"):
            rc, out, err = run(["bundle-audit", "check", "--update"], self.root, 180)
            audits["bundle-audit"] = {"executado": True, "total": len(re.findall(r"(?m)^Name:", out))}
        for tool in ("osv-scanner", "pip-audit", "npm", "pnpm", "yarn", "composer", "govulncheck", "bundle-audit", "gitleaks", "trufflehog"):
            self.tools[tool] = bool(shutil.which(tool))
        self.signals["C20"]["auditoria"] = audits
        for name, a in audits.items():
            if name in ("npm", "pnpm", "yarn", "bun"):
                if a.get("executado"):
                    self.decidir_auditoria_js(a)
                continue
            v = a.get("vulnerabilidades") or {}
            crit, high = int(v.get("critical", 0) or 0), int(v.get("high", 0) or 0)
            if crit or high:
                self.add("C20", "vulnerabilidades_altas", None, None, None, "alta",
                         f"{name} audit: {crit} crítica(s), {high} alta(s) em dependências de produção" +
                         (": " + ", ".join(a.get("pacotes", [])[:8]) if a.get("pacotes") else ""))
            elif int(v.get("moderate", 0) or 0):
                self.add("C20", "vulnerabilidades_moderadas", None, None, None, "baixa", f"{name} audit: {v.get('moderate')} moderada(s)")
            if name == "pip-audit" and a.get("total"):
                self.add("C20", "vulnerabilidades_python", None, None, None, "alta", f"pip-audit: {a['total']} vulnerabilidade(s): " +
                         ", ".join(f"{n} ({i})" for n, i in a["exemplos"][:8]))
            if name in ("osv-scanner", "govulncheck", "bundle-audit") and a.get("total"):
                self.add("C20", "vulnerabilidades_" + name.replace("-", "_"), None, None, None, "alta",
                         f"{name}: {a['total']} vulnerabilidade(s) conhecida(s) — rode a ferramenta para ver a lista")

    SEV_ORDEM = {"critical": 4, "high": 3, "moderate": 2, "low": 1, "info": 0}

    @classmethod
    def parse_js_audit(cls, out, rc, err):
        """npm (7+ e 6), pnpm, yarn 1 e bun → {executado, vulnerabilidades, achados: [{pacote, severidade, raizes}], pacotes}.
        'raizes' são as dependências diretas que puxam o pacote vulnerável (é por elas que se sabe se vai para produção)."""
        txt = (out or "").strip()
        if not txt:
            return {"executado": False, "erro": (err or "sem saída")[:300]}
        achados, counts = {}, {}

        def add(pkg, sev, raizes):
            if not pkg:
                return
            atual = achados.get(pkg)
            if not atual or cls.SEV_ORDEM.get(sev, 0) > cls.SEV_ORDEM.get(atual["severidade"], 0):
                achados[pkg] = {"pacote": pkg, "severidade": sev or "unknown", "raizes": set(raizes) | (atual["raizes"] if atual else set())}
            else:
                atual["raizes"] |= set(raizes)

        def raiz_do_caminho(c):
            partes = [x for x in c.split(">") if x]
            if partes and (partes[0] == "." or "__" in partes[0]) and len(partes) > 1:
                partes = partes[1:]  # pnpm põe o importador (raiz ou pasta do workspace) na frente
            return partes[0] if partes else ""

        try:
            data = json.loads(txt)
        except Exception:
            data = None
        if isinstance(data, dict) and data.get("type") in ("auditSummary", "auditAdvisory", "info", "warning"):
            data = None  # yarn 1 com uma linha só
        if data is None:  # yarn 1: um JSON por linha
            for ln in txt.splitlines():
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                if o.get("type") == "auditSummary":
                    counts = (o.get("data") or {}).get("vulnerabilities") or {}
                elif o.get("type") == "auditAdvisory":
                    adv = (o.get("data") or {}).get("advisory") or {}
                    caminhos = [p for fi in adv.get("findings") or [] for p in fi.get("paths") or []]
                    add(adv.get("module_name"), adv.get("severity"), [raiz_do_caminho(c) for c in caminhos])
            if not counts and not achados:
                return {"executado": False, "erro": (err or txt)[:300]}
        elif isinstance(data, dict) and isinstance(data.get("vulnerabilities"), dict):  # npm 7+
            vul = data["vulnerabilities"]

            def raizes(nome):
                fila, vistos, out = [nome], {nome}, []
                while fila:
                    k = fila.pop()
                    v = vul.get(k) or {}
                    if v.get("isDirect"):
                        out.append(k)
                    for e in v.get("effects") or []:
                        if e not in vistos:
                            vistos.add(e)
                            fila.append(e)
                return out
            for nome, info in vul.items():
                if isinstance(info, dict) and any(isinstance(x, dict) for x in info.get("via") or []):
                    add(nome, info.get("severity"), raizes(nome))  # só quem tem o aviso, não quem depende dele
            counts = (data.get("metadata") or {}).get("vulnerabilities") or {}
        elif isinstance(data, dict) and isinstance(data.get("advisories"), dict):  # npm 6 e pnpm
            for adv in data["advisories"].values():
                if isinstance(adv, dict):
                    caminhos = [p for fi in adv.get("findings") or [] for p in fi.get("paths") or []]
                    add(adv.get("module_name"), adv.get("severity"), [raiz_do_caminho(c) for c in caminhos])
            counts = (data.get("metadata") or {}).get("vulnerabilities") or {}
        elif isinstance(data, dict) and "error" in data and "metadata" not in data:
            return {"executado": False, "erro": json.dumps(data["error"], ensure_ascii=False)[:300]}
        elif isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):  # bun: resposta crua do registro
            for pkg, lst in data.items():
                for adv in lst:
                    if isinstance(adv, dict):
                        add(pkg, adv.get("severity"), [])
            for x in achados.values():
                counts[x["severidade"]] = counts.get(x["severidade"], 0) + 1
        else:
            return {"executado": False, "erro": txt[:300]}
        lista = sorted(({**x, "raizes": sorted(r for r in x["raizes"] if r)} for x in achados.values()),
                       key=lambda x: (-cls.SEV_ORDEM.get(x["severidade"], 0), x["pacote"]))
        return {"executado": True, "vulnerabilidades": counts, "achados": lista,
                "pacotes": [f"{x['pacote']} ({x['severidade']})" for x in lista if x["severidade"] in ("critical", "high")][:20]}

    def uso_da_dependencia(self, pkg):
        """'producao' se o código do app importa o pacote; 'build' se só a config do build, scripts e testes usam
        (ou é ferramenta de build conhecida); None quando não deu para saber."""
        if pkg in self._uso_cache:
            return self._uso_cache[pkg]
        rx = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]%s(?:/[^'"]*)?['"]""" % re.escape(pkg))
        onde = set()
        for f in self.code():
            if pkg in f.text and rx.search(f.code):
                onde.add("build" if TEST_PATH_RX.search(f.rel) or ARQUIVO_DE_BUILD_RX.search(f.rel) else "producao")
        if "producao" in onde:
            r = "producao"
        elif onde or FERRAMENTA_DE_BUILD_RX.match(pkg):
            r = "build"
        else:
            curto = pkg.rsplit("/", 1)[-1]
            r = "build" if any(re.search(r"(?:^|[\s;&|(])%s(?:\s|$)" % re.escape(curto), v) for v in self.pkg_scripts.values()) else None
        self._uso_cache[pkg] = r
        return r

    def decidir_auditoria_js(self, a):
        """Separa o que vai para produção do que só roda no build e do que é só de dev, e decide a confiança de cada um."""
        alta_sev = ("critical", "high")
        prod, build = [], []
        for x in a.get("achados") or []:
            if x["severidade"] not in alta_sev:
                continue
            raizes = x["raizes"] or ([x["pacote"]] if x["pacote"] in self.deps else [])
            usos = {self.uso_da_dependencia(r) for r in raizes}
            x["uso"] = "build" if raizes and usos == {"build"} else "producao" if "producao" in usos else "desconhecido"
            (build if x["uso"] == "build" else prod).append(x)

        def fmt(lst):
            itens = []
            for x in lst[:8]:
                via = [r for r in x["raizes"] if r != x["pacote"]][:2]
                itens.append(f"{x['pacote']} ({x['severidade']}" + (f" via {'/'.join(via)}" if via else "") + ")")
            return ", ".join(itens) + ("…" if len(lst) > 8 else "")
        cmd = a.get("comando", "audit")
        if prod:
            crit = sum(1 for x in prod if x["severidade"] == "critical")
            self.add("C20", "vulnerabilidades_altas", None, None, None, "alta",
                     f"`{cmd}`: {crit} crítica(s) e {len(prod) - crit} alta(s) em dependências de produção: {fmt(prod)}")
        if build:
            self.add("C20", "vulnerabilidades_so_no_build", None, None, None, "media",
                     f"`{cmd}` acusou alta/crítica em pacote que só roda no build, nos testes ou nas ferramentas ({fmt(build)}): ele não "
                     "vai para o navegador nem para o servidor. Atualize quando puder e, se estiver em dependencies, mova para devDependencies.")
        mod = [x for x in a.get("achados") or [] if x["severidade"] == "moderate"]
        if not prod and not build and mod:
            self.add("C20", "vulnerabilidades_moderadas", None, None, None, "baixa", f"`{cmd}`: {len(mod)} moderada(s): {fmt(mod)}")
        dev = [x for x in a.get("so_dev") or [] if x["severidade"] in alta_sev]
        if dev:
            self.add("C20", "vulnerabilidades_so_dev", None, None, None, "baixa",
                     f"{len(dev)} pacote(s) com alta/crítica só em devDependencies ({fmt(dev)}): ficam na máquina de quem desenvolve e no "
                     "CI, não no app publicado. Atualize na rotina.")
        a["decisao"] = {"producao": [f"{x['pacote']} ({x['uso']})" for x in prod], "so_build": [x["pacote"] for x in build],
                        "so_dev": [x["pacote"] for x in dev]}
        a["achados"] = (a.get("achados") or [])[:40]
        a["so_dev"] = (a.get("so_dev") or [])[:40]

    # -- consolidação ------------------------------------------------------------------
    SEMANTIC = {"C06", "C07", "C08", "C14", "C17"}

    def suggestion(self, cid):
        items = self.findings[cid]
        confs = {i["confianca"] for i in items}
        sig = self.signals[cid]
        if "alta" in confs:
            return "FALHA_PROVAVEL"
        if items:
            return "REVISAR"
        if cid == "C04" and not self.stack.get("supabase") and not sig.get("firebase_rules") and not self.stack.get("firebase"):
            return "NA_PROVAVEL"
        if cid == "C04" and sig.get("rls_nao_verificavel_pelo_repo"):
            return "VERIFICAR_FORA_DO_REPO"
        if cid == "C16" and sig.get("sem_upload"):
            return "NA_PROVAVEL"
        if cid == "C12" and sig.get("sem_formularios"):
            return "NA_PROVAVEL"
        if cid == "C10" and self.signals["C10"].get("auth_gerenciada") and not self.signals["C10"].get("lib_de_hash"):
            return "PROVAVEL_AUTH_GERENCIADA"
        if cid == "C02" and not sig.get("repo_git"):
            return "SEM_GIT"
        if cid in self.SEMANTIC:
            return "REVISAO_MANUAL"
        if cid in ("P03", "P05", "P06", "P10"):
            return "VERIFICAR_FORA_DO_REPO"
        return "SEM_ACHADOS"

    def run_all(self):
        t0 = time.time()
        errors = []
        for step in (self.collect, self.load_deps):
            try:
                step()
            except Exception as e:
                errors.append(f"{step.__name__}: {type(e).__name__}: {e}")
        steps = [self.scan_secrets, self.scan_git, self.scan_rls, self.scan_crypto, self.scan_routes, self.scan_routes_frameworks,
                 self.scan_frameworks, self.scan_mass_assignment, self.scan_cookies, self.scan_passwords, self.scan_abuse,
                 self.scan_injection, self.scan_leaks, self.scan_uploads, self.scan_responses,
                 self.scan_headers_https, self.scan_deps, self.scan_prontidao]
        for step in steps:
            try:
                step()
            except Exception as e:  # um passo quebrado não derruba o scan inteiro
                errors.append(f"{step.__name__}: {type(e).__name__}: {e}")
        self.signals["C06"]["rotas_encontradas"] = len(self.routes)  # inclui as rotas do Laravel, lidas depois
        self.signals["C06"]["rotas"] = self.routes[:200]
        if self.truncated:
            self.avisos.append(f"Projeto grande: só os primeiros {MAX_FILES} arquivos foram lidos — rode por subpasta (app que vai pro ar)")
        try:
            from autoria import verificar as verificar_autoria
            autoria = verificar_autoria()
        except Exception as e:  # pragma: no cover
            autoria = {"erro": f"{type(e).__name__}: {e}"}
        autoria["creditos_intactos"] = creditos_intactos()
        cobertura = self.resumo_zonas()
        conf_rank = {"alta": 0, "media": 1, "baixa": 2}
        result = {
            "ferramenta": f"check-pre-lancamento/scan.py {VERSION}",
            "credito": CREDITO,
            "autoria": {**AUTORIA, **autoria},
            "raiz": str(self.root),
            "duracao_s": round(time.time() - t0, 1),
            "arquivos_analisados": len(self.files),
            "arquivos_ignorados": self.skipped,
            "cobertura_do_scan": cobertura,
            "stack": sorted(self.stack.keys()),
            "plataforma": self.platform,
            "rotas_encontradas": len(self.routes),
            "ferramentas_disponiveis": self.tools,
            "git": self.git,
            "erros_do_scanner": errors,
            "avisos": self.avisos,
            "checks": {},
            "prontidao": {},
        }
        for group, table in (("checks", CHECKS), ("prontidao", PRONTIDAO)):
            for cid, (title, sev) in table.items():
                items = sorted(self.findings[cid], key=lambda i: (conf_rank.get(i["confianca"], 3), i.get("arquivo", ""), i.get("linha", 0)))
                omitted = {rule: n for (c, rule), n in self.omitted.items() if c == cid}
                result[group][cid] = {
                    "titulo": title,
                    "severidade_base": sev,
                    "sugestao": self.suggestion(cid),
                    "achados": items,
                    "omitidos_por_limite": omitted,
                    "sinais": self.signals[cid],
                }
        return result


def print_summary(res):
    icon = {"FALHA_PROVAVEL": "❌", "REVISAR": "⚠️ ", "REVISAO_MANUAL": "🔍", "SEM_ACHADOS": "·", "NA_PROVAVEL": "➖",
            "VERIFICAR_FORA_DO_REPO": "🔍", "PROVAVEL_AUTH_GERENCIADA": "·", "SEM_GIT": "➖"}
    print(f"\n{banner()}")
    print(f"scan em {res['duracao_s']}s · {res['arquivos_analisados']} arquivos · {res['rotas_encontradas']} rotas · "
          f"stack: {', '.join(res['stack']) or 'não detectada'}" + (f" · plataforma: {', '.join(res['plataforma'])}" if res["plataforma"] else ""))
    a = res.get("autoria") or {}
    if not a.get("creditos_intactos", True) or a.get("creditos_removidos"):
        print("⚠️  Cópia sem os créditos originais. A versão oficial e gratuita está em " + AUTORIA["repositorio"])
    if res["erros_do_scanner"]:
        print("erros do scanner:", *res["erros_do_scanner"], sep="\n  ")
    if res.get("avisos"):
        print("avisos de cobertura (levar para 'limitacoes' e 'cobertura'):", *res["avisos"], sep="\n  ")
    for group, title in (("checks", "Segurança (20)"), ("prontidao", "Prontidão para o lançamento (10)")):
        print(f"\n{title}")
        for cid, c in res[group].items():
            n = len(c["achados"]) + sum(c["omitidos_por_limite"].values())
            alta = sum(1 for x in c["achados"] if x["confianca"] == "alta")
            print(f"{icon.get(c['sugestao'], '?')} {cid} {c['titulo']:<32} {c['sugestao']:<26} achados: {n:<3} (alta: {alta})")
    print("\nTriagem automática: confirme cada achado lendo o código. 'SEM_ACHADOS' não é 'OK'.")


def main():
    ap = argparse.ArgumentParser(description=f"Scanner de triagem das 20 checagens + 10 de prontidão · {CREDITO}")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", help="caminho do JSON de saída (padrão: <raiz>/check-report/scan.json)")
    ap.add_argument("--no-git-history", action="store_true", help="não varre o histórico do git (mais rápido)")
    ap.add_argument("--no-audit", action="store_true", help="não roda npm/pnpm/yarn/bun/pip audit (sem rede)")
    ap.add_argument("--ignorar", "--ignore", action="append", metavar="PADRAO",
                    help="pasta ou padrão do .gitignore fora das regras de código (repete ou separa por vírgula); "
                         "segredos continuam sendo procurados. Também lê " + ARQUIVO_IGNORAR + " na raiz")
    ap.add_argument("--varrer-tudo", "--all-files", dest="varrer_tudo", action="store_true",
                    help="não respeita .gitignore, pastas fora do build (docs/, examples/) nem --ignorar")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.exit(f"raiz inválida: {root}")
    res = Scanner(root, args).run_all()
    out = Path(args.out) if args.out else root / "check-report" / "scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print_summary(res)
        print(f"\nJSON completo: {out}")


if __name__ == "__main__":
    main()
