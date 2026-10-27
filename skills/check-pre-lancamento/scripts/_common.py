# check-pre-lancamento · metadados e padrões compartilhados pelos scripts
# Copyright (c) 2026 Paulo Sérgio Dantas · https://github.com/dantaspaulo/check-pre-lancamento
# Licença de Uso com Atribuição v1.0 (LICENSE.txt) · impressão CPL-PSD-2026
# Aviso obrigatório: mantenha estas linhas e os créditos de autoria em qualquer cópia ou derivado.
"""Metadados e padrões compartilhados pelos scripts da skill check-pre-lancamento.

Só biblioteca padrão. Importado por scan.py, check_url.py, render_report.py, show.py e autoria.py.
"""
import base64
import hashlib
import json
import math
import re
import sys

VERSION = "2.2.1"

# Windows com saída em pipe usa cp1252 e quebra nos símbolos (✔, ❌, →): força UTF-8 com substituição.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ----------------------------------------------------------------------------- autoria
# Os créditos abaixo fazem parte da licença (LICENSE.txt, cláusula 3). O render_report.py
# confere o selo e se recusa a gerar relatório quando os créditos foram trocados ou apagados.
AUTORIA = {
    "skill": "check-pre-lancamento",
    "versao": VERSION,
    "autor": "Paulo Sérgio Dantas",
    "github": "dantaspaulo",
    "repositorio": "https://github.com/dantaspaulo/check-pre-lancamento",
    "licenca": "Licença de Uso com Atribuição v1.0 (LICENSE.txt)",
    "impressao": "CPL-PSD-2026",
}
SELO_AUTORIA = "cb6453268d4b63eae51cff76"
CREDITO = (f"{AUTORIA['skill']} v{VERSION} · por {AUTORIA['autor']} · "
           f"{AUTORIA['repositorio'].replace('https://', '')}")


def selo(autoria=None):
    a = autoria or AUTORIA
    base = f"{a.get('autor')}|{a.get('repositorio')}|{a.get('impressao')}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def creditos_intactos():
    return selo() == SELO_AUTORIA


def banner():
    return f"{CREDITO} · licença: {AUTORIA['licenca']}"


# ----------------------------------------------------------------------------- checagens
# id -> (título, severidade base). Peso na nota: CRITICO 10 · ALTO 6 · MEDIO 3 · BAIXO 1
CHECKS = {
    "C01": ("Esconder API Keys", "CRITICO"),
    "C02": ("Limpar secrets do Git", "CRITICO"),
    "C03": ("Usar apenas Public Key no DB", "CRITICO"),
    "C04": ("Ativar RLS", "CRITICO"),
    "C05": ("Criptografia de dados", "ALTO"),
    "C06": ("Auth server-side", "CRITICO"),
    "C07": ("Restringir acessos", "CRITICO"),
    "C08": ("Bloquear Mass Assignment", "ALTO"),
    "C09": ("Proteger cookies", "ALTO"),
    "C10": ("Hash nas senhas", "CRITICO"),
    "C11": ("Rate limit", "ALTO"),
    "C12": ("Bot protection", "MEDIO"),
    "C13": ("Queries parametrizadas", "CRITICO"),
    "C14": ("Validação dos inputs", "ALTO"),
    "C15": ("Evitar vazamento de conteúdo", "MEDIO"),
    "C16": ("Restringir uploads", "ALTO"),
    "C17": ("Limitar respostas de API", "MEDIO"),
    "C18": ("Security headers", "MEDIO"),
    "C19": ("Forçar HTTPS", "ALTO"),
    "C20": ("Scan de dependências", "ALTO"),
}

# Prontidão para o lançamento: não entra na nota de segurança, tem nota própria.
PRONTIDAO = {
    "P01": ("Configuração de produção", "ALTO"),
    "P02": ("Erros e logs monitorados", "ALTO"),
    "P03": ("Backup e recuperação", "ALTO"),
    "P04": ("Deploy, migrations e rollback", "MEDIO"),
    "P05": ("Uptime e alertas", "MEDIO"),
    "P06": ("E-mail e domínio", "ALTO"),
    "P07": ("LGPD, privacidade e termos", "ALTO"),
    "P08": ("SEO e compartilhamento", "MEDIO"),
    "P09": ("Performance e experiência", "MEDIO"),
    "P10": ("Custos e limites de gasto", "ALTO"),
}

SEVERITY_WEIGHT = {"CRITICO": 10, "ALTO": 6, "MEDIO": 3, "BAIXO": 1}
SEVERITY_ORDER = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
SEVERITY_LABEL = {"CRITICO": "CRÍTICO", "ALTO": "ALTO", "MEDIO": "MÉDIO", "BAIXO": "BAIXO"}
SEVERITY_ICON = {"CRITICO": "🔴", "ALTO": "🟠", "MEDIO": "🟡", "BAIXO": "⚪"}

STATUS_VALUE = {"OK": 1.0, "ATENCAO": 0.5, "FALHA": 0.0}
STATUS_LABEL = {"OK": "✅ OK", "ATENCAO": "⚠️ ATENÇÃO", "FALHA": "❌ FALHA", "NA": "➖ N/A", "NAO_AVALIADO": "⚪ NÃO AVALIADO"}

# ----------------------------------------------------------------------------- variáveis públicas
# Prefixos que fazem a variável de ambiente ir parar no bundle do navegador/app.
PUBLIC_ENV_PREFIXES = (
    "NEXT_PUBLIC_", "VITE_", "REACT_APP_", "EXPO_PUBLIC_", "NUXT_PUBLIC_", "PUBLIC_", "GATSBY_",
    "VUE_APP_", "NG_APP_", "MIX_", "NX_PUBLIC_", "BUN_PUBLIC_", "STORYBOOK_", "SANITY_STUDIO_",
    "REDWOOD_ENV_", "PLASMO_PUBLIC_", "WXT_",
)
# Pedaços de nome que indicam segredo (não deveria ter prefixo público).
SECRET_ENV_HINTS = (
    "SECRET", "SERVICE_ROLE", "SERVICE_KEY", "SERVICE_ACCOUNT", "PRIVATE_KEY", "PRIVATE_TOKEN",
    "OPENAI", "ANTHROPIC", "CLAUDE", "GEMINI", "GROQ", "MISTRAL", "DEEPSEEK", "PERPLEXITY", "COHERE",
    "XAI_", "OPENROUTER", "REPLICATE", "HUGGINGFACE", "HF_TOKEN", "ELEVENLABS", "PINECONE",
    "STRIPE_SK", "SK_LIVE", "DATABASE_URL", "DB_URL", "DB_PASS", "POSTGRES", "MONGO", "REDIS_URL",
    "ADMIN_KEY", "ADMIN_TOKEN", "ADMIN_PASS", "WEBHOOK", "ACCESS_TOKEN", "REFRESH_TOKEN", "AUTH_TOKEN",
    "MERCADOPAGO", "MERCADO_PAGO", "ASAAS", "PAGARME", "PAGSEGURO", "GERENCIANET", "EFI_", "IUGU",
    "TWILIO_AUTH", "SENDGRID", "RESEND", "BREVO", "MAILGUN", "POSTMARK", "AWS_SECRET",
    "PASSWORD", "PASSWD", "JWT_SECRET", "JWT_KEY", "JWT_PRIVATE", "SIGNING", "ENCRYPTION", "HMAC",
    "ZAPI", "Z_API", "EVOLUTION", "WHATSAPP_TOKEN", "META_ACCESS", "FB_ACCESS", "SENTRY_AUTH",
    "GITHUB_TOKEN", "NPM_TOKEN", "CLOUDFLARE_API", "VERCEL_TOKEN", "FIREBASE_ADMIN", "SUPABASE_SERVICE",
)
# Nomes que parecem segredo mas são públicos por design.
PUBLIC_ENV_ALLOW = (
    "ANON_KEY", "PUBLISHABLE", "PUBLIC_KEY", "SITE_KEY", "SITEKEY", "MEASUREMENT_ID", "APP_ID",
    "PROJECT_ID", "AUTH_DOMAIN", "STORAGE_BUCKET", "MESSAGING_SENDER_ID", "_URL_PUBLIC", "POSTHOG_KEY",
    "SENTRY_DSN", "GA_ID", "GTM_ID", "CLIENT_ID", "PUBLIC_URL", "SUPABASE_URL", "API_URL", "BASE_URL",
    "SITE_URL", "APP_URL", "FIREBASE_API_KEY", "MIXPANEL_TOKEN", "SEGMENT_WRITE_KEY", "ALGOLIA_SEARCH",
    "ALGOLIA_APP_ID", "ONESIGNAL_APP_ID", "PUSHER_APP_KEY", "PUSHER_KEY", "REVERB_APP_KEY", "VAPID_PUBLIC",
    "CONVEX_URL", "WEBHOOK_PATH",
)

# ----------------------------------------------------------------------------- padrões de segredo
# (id, regex, confiança, descrição). Ordem importa: do mais específico ao mais genérico.
SECRET_PATTERNS = [
    # só conta como chave se vier o corpo base64 em seguida (ou o fim da linha, num .pem); "pem.replace('-----BEGIN…','')" não é chave
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"
                               r"(?=(?:\\n|\\r|\s|\"|')*[A-Za-z0-9+/]{40}|\s*$)"), "alta", "Chave privada"),
    ("gcp_service_account", re.compile(r"\"type\"\s*:\s*\"service_account\""), "alta", "JSON de service account do Google Cloud/Firebase"),
    ("anthropic_key", re.compile(r"\bsk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{20,}"), "alta", "Chave da API da Anthropic"),
    ("openrouter_key", re.compile(r"\bsk-or-v1-[a-f0-9]{64}\b"), "alta", "Chave da OpenRouter"),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}"), "alta", "Chave da API da OpenAI (ou compatível: DeepSeek, Moonshot…)"),
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{48,}\b"), "alta", "Chave da Groq"),
    ("xai_key", re.compile(r"\bxai-[A-Za-z0-9]{70,}\b"), "alta", "Chave da xAI (Grok)"),
    ("perplexity_key", re.compile(r"\bpplx-[A-Za-z0-9]{40,}\b"), "alta", "Chave da Perplexity"),
    ("huggingface_token", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"), "alta", "Token do Hugging Face"),
    ("replicate_token", re.compile(r"\br8_[A-Za-z0-9]{36,}\b"), "alta", "Token da Replicate"),
    ("elevenlabs_key", re.compile(r"\bsk_[a-f0-9]{48}\b"), "media", "Chave da ElevenLabs (ou outra sk_ hexadecimal)"),
    ("stripe_live", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}"), "alta", "Chave secreta live (Stripe, Clerk ou Pagar.me)"),
    ("stripe_test", re.compile(r"\b(?:sk|rk)_test_[0-9A-Za-z]{16,}"), "media", "Chave secreta de teste (Stripe, Clerk ou Pagar.me)"),
    ("stripe_webhook", re.compile(r"\bwhsec_[A-Za-z0-9+/=]{20,}"), "alta", "Segredo de webhook (Stripe, Svix, Clerk)"),
    ("supabase_secret", re.compile(r"\bsb_secret_[A-Za-z0-9_\-]{20,}"), "alta", "Chave secreta Supabase (sb_secret)"),
    ("supabase_pat", re.compile(r"\bsbp_[a-f0-9]{40}\b"), "alta", "Token pessoal do Supabase (controla todos os seus projetos)"),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "alta", "AWS Access Key ID"),
    ("aws_secret", re.compile(r"(?i)aws_?secret_?access_?key\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}"), "alta", "AWS Secret Access Key"),
    ("google_oauth_secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_\-]{28}\b"), "alta", "Client secret do Google OAuth"),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})"), "alta", "Token do GitHub"),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}"), "alta", "Token do GitLab"),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "alta", "Token do npm"),
    ("pypi_token", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{50,}"), "alta", "Token do PyPI"),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "alta", "Token do Slack"),
    ("slack_webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"), "alta", "Webhook do Slack"),
    ("discord_webhook", re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]{30,}"), "alta", "Webhook do Discord"),
    ("telegram_bot_token", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b"), "alta", "Token de bot do Telegram"),
    ("meta_token", re.compile(r"\bEAA[A-Za-z0-9]{90,}"), "alta", "Token da Meta (Facebook, Instagram, WhatsApp Cloud API)"),
    ("sendgrid_key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"), "alta", "Chave SendGrid"),
    ("resend_key", re.compile(r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,}\b"), "alta", "Chave da Resend"),
    ("brevo_key", re.compile(r"\bxkeysib-[a-f0-9]{64}-[A-Za-z0-9]{16}\b"), "alta", "Chave da Brevo (Sendinblue)"),
    ("mailgun_key", re.compile(r"\bkey-[0-9a-f]{32}\b"), "media", "Chave da Mailgun"),
    ("mailchimp_key", re.compile(r"\b[0-9a-f]{32}-us\d{1,2}\b"), "alta", "Chave da Mailchimp"),
    ("twilio_api_key", re.compile(r"\bSK[0-9a-f]{32}\b"), "media", "API key da Twilio"),
    ("shopify_token", re.compile(r"\bshp(?:at|ss|ca|pa)_[a-fA-F0-9]{32}\b"), "alta", "Token da Shopify"),
    ("mercadopago_token", re.compile(r"\b(?:APP_USR|TEST)-\d{10,}-\d{6}-[a-f0-9]{32}-\d{5,}"), "alta", "Access token Mercado Pago"),
    ("asaas_key", re.compile(r"\$aact_[A-Za-z0-9_=\-]{20,}"), "alta", "Chave da API Asaas"),
    ("efi_secret", re.compile(r"\bClient_Secret_[A-Za-z0-9]{30,}\b"), "alta", "Client Secret da Efí (Gerencianet)"),
    ("digitalocean_token", re.compile(r"\bdo[por]_v1_[a-f0-9]{64}\b"), "alta", "Token da DigitalOcean"),
    ("netlify_token", re.compile(r"\bnfp_[A-Za-z0-9]{36,}\b"), "alta", "Token da Netlify"),
    ("sentry_token", re.compile(r"\bsntr[ysu]_[A-Za-z0-9_=+/\-]{40,}"), "alta", "Token de autenticação do Sentry"),
    ("posthog_personal", re.compile(r"\bphx_[A-Za-z0-9]{40,}\b"), "alta", "Chave pessoal da API do PostHog"),
    ("linear_key", re.compile(r"\blin_api_[A-Za-z0-9]{40}\b"), "alta", "Chave da Linear"),
    ("notion_token", re.compile(r"\b(?:secret_[A-Za-z0-9]{43}|ntn_[A-Za-z0-9]{40,})\b"), "alta", "Token de integração do Notion"),
    ("airtable_pat", re.compile(r"\bpat[A-Za-z0-9]{14}\.[a-f0-9]{64}\b"), "alta", "Token da Airtable"),
    ("pinecone_key", re.compile(r"\bpcsk_[A-Za-z0-9_]{50,}\b"), "alta", "Chave da Pinecone"),
    ("doppler_token", re.compile(r"\bdp\.(?:pt|st|sa|ct|scim|audit)\.[A-Za-z0-9]{40,}\b"), "alta", "Token da Doppler"),
    ("fcm_server_key", re.compile(r"\bAAAA[A-Za-z0-9_\-]{7}:[A-Za-z0-9_\-]{140}\b"), "alta", "Server key do Firebase Cloud Messaging"),
    ("django_secret", re.compile(r"django-insecure-[A-Za-z0-9!@#$%^&*(\-_=+)]{30,}"), "alta", "SECRET_KEY padrão do Django (django-insecure)"),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "media", "Google API key (pública se for config do Firebase; secreta se for Gemini/Maps sem restrição)"),
    ("db_url_password", re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?|mssql|sqlserver)://[^:\s/\"'@]+:([^@\s\"']{3,})@[^\s\"']+"), "alta", "Connection string de banco com senha"),
    ("jdbc_password", re.compile(r"jdbc:[a-z0-9]+://[^\s\"']+?[?&;]password=([^&;\s\"']{4,})", re.I), "alta", "URL JDBC com senha"),
    ("adonet_password", re.compile(r"(?i)\b(?:Server|Data Source)\s*=\s*[^;\"'\n]{2,100};(?=[^\"'\n]{0,300}?\b(?:Database|Initial Catalog|User ?Id|Uid)\s*=)"
                                   r"[^\"'\n]{0,300}?\b(?:Password|Pwd)\s*=\s*([^;\"'\s]{4,})"), "alta", "Connection string com senha (.NET / SQL Server)"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "media", "JWT embutido no código"),
    ("generic_assignment", re.compile(
        r"(?i)\b([A-Za-z0-9_]*(?:api[_-]?key|apikey|secret|token|passwd|password|senha|private[_-]?key|access[_-]?key|auth[_-]?key)[A-Za-z0-9_]*)\b"
        r"[\"']?\s*(?::|=|=>)\s*[\"'`]([^\"'`\s]{12,})[\"'`]"), "media", "Valor que parece segredo atribuído direto no código"),
]

# Padrões cuja parte variável precisa parecer aleatória (corta falso positivo de nome de função).
RANDOM_REQUIRED = {"resend_key", "elevenlabs_key", "twilio_api_key", "mailgun_key"}
# Padrões que não se mascaram pelo match inteiro (o valor está num grupo ou o match não é o segredo).
GROUP1_MASK = {"db_url_password", "jdbc_password", "adonet_password"}
PEM_RX = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----).*")
# bloco PEM inteiro, inclusive em várias linhas (relatório e evidências podem trazer a chave colada)
PEM_BLOCK_RX = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)")
# usuário:senha@ em qualquer URL (guloso até o último @, para senha que contém @)
URL_USERINFO_RX = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)([^\s/\"'?#<>]*)@")
URL_TOKEN_RX = re.compile(r"(?i)([?&;](?:api[_-]?key|apikey|key|token|access_token|auth|sig|signature|secret|password|pwd)=)([^&\s\"'#]{4,})")
URL_PATH_TOKEN_RX = re.compile(r"(?<=/)([A-Za-z0-9_\-]{24,})(?=[/?#\s\"']|$)")
_KEY = (r"[\w.\-]*(?:pass(?:word|wd)?|pwd|senha|secret|token|api[_-]?key|apikey|private[_-]?key|access[_-]?key|"
        r"auth[_-]?key|credential|_auth)[\w.\-]*")
# chave: valor sem aspas (properties, yaml, ini, toml, .npmrc, .netrc…)
KV_RX = re.compile(r"(?im)((?:^|[\s,{;(:/])[\"']?" + _KEY + r"[\"']?\s*(?:[:=]|=>)\s*[\"'`]?)([^\s\"'`,;}{)#]{4,})")
_KV_KEEP = re.compile(r"(?i)true|false|null|none|nil|\d+|await|new|require|undefined|this|self|string|number|boolean|any|"
                      r"str|int|bool|optional|required|hidden|password|text|secret|token")

PLACEHOLDER_HINTS = (
    "xxx", "your", "seu_", "sua_", "example", "exemplo", "placeholder", "changeme", "change_me",
    "<", ">", "${", "{{", "dummy", "sample", "fake", "mock", "test123", "000000", "...", "****",
    "insert", "replace", "todo", "redacted", "aqui", "here", "process.env", "import.meta",
    "os.environ", "getenv", "env(", "config.",
)


def looks_placeholder(value: str) -> bool:
    v = value.lower()
    if any(h in v for h in PLACEHOLDER_HINTS):
        return True
    if len(set(v)) <= 4:  # aaaa..., 1111...
        return True
    return False


def looks_random(value: str) -> bool:
    """Heurística para valores genéricos: segredo real mistura classes de caractere e tem entropia."""
    if not value:
        return False
    classes = sum(bool(re.search(rx, value)) for rx in (r"[a-z]", r"[A-Z]", r"\d"))
    if classes < 2:
        return False
    if re.fullmatch(r"[a-z]+(?:[_\-.][a-z]+)+", value):  # snake/kebab-case comum
        return False
    freq = {c: value.count(c) for c in set(value)}
    entropy = -sum((n / len(value)) * math.log2(n / len(value)) for n in freq.values())
    return entropy >= 3.0


def decode_jwt_payload(token: str):
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()).decode("utf-8", "ignore"))
    except Exception:
        return None


def mask(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "****"
    keep = 6 if len(value) > 20 else 3
    return value[:keep] + "…****"


def _userinfo(m):
    user, sep, _pw = m.group(2).partition(":")
    return m.group(1) + (user + ":****" if sep else "****") + "@"


def _kv(m):
    v = m.group(2)
    if looks_placeholder(v) or _KV_KEEP.fullmatch(v) or re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[\w$]+)+\(?\)?", v):
        return m.group(0)
    if re.fullmatch(r"[A-Za-z_$][\w$]*", v) and not looks_random(v):  # identificador de código, não valor
        return m.group(0)
    return m.group(1) + mask(v)


def mask_secrets(text: str) -> str:
    """Mascara qualquer coisa que pareça segredo. Usado em trechos, no show.py e no relatório final."""
    if not text:
        return text
    out = PEM_BLOCK_RX.sub("-----BEGIN PRIVATE KEY----- …[conteúdo da chave privada ocultado]", text)
    out = PEM_RX.sub(r"\1 …[conteúdo da chave privada ocultado]", out)
    for pid, rx, _conf, _desc in SECRET_PATTERNS:
        if pid in ("private_key", "gcp_service_account"):
            continue
        if pid == "generic_assignment":
            out = rx.sub(lambda m: m.group(0).replace(m.group(2), mask(m.group(2)))
                         if not looks_placeholder(m.group(2)) and looks_random(m.group(2)) else m.group(0), out)
        elif pid in GROUP1_MASK:
            out = rx.sub(lambda m: m.group(0).replace(m.group(1), "****"), out)
        else:
            out = rx.sub(lambda m: mask(m.group(0)), out)
    out = URL_USERINFO_RX.sub(_userinfo, out)
    out = URL_TOKEN_RX.sub(lambda m: m.group(1) + mask(m.group(2)), out)
    out = URL_PATH_TOKEN_RX.sub(lambda m: mask(m.group(1)) if looks_random(m.group(1)) else m.group(1), out)
    out = KV_RX.sub(_kv, out)
    return out


def iter_secret_matches(line: str):
    """Yield (pattern_id, matched_value, confiança, descrição) para uma linha."""
    seen_spans = []
    for pid, rx, conf, desc in SECRET_PATTERNS:
        for m in rx.finditer(line):
            span = m.span()
            if any(s[0] <= span[0] < s[1] for s in seen_spans):
                continue
            c = conf
            if pid == "generic_assignment":
                value = m.group(2)
                if looks_placeholder(value) or not looks_random(value):
                    continue
                if value.startswith(("http://", "https://", "/", "./")) and "@" not in value:
                    continue
                if re.fullmatch(r"[A-Z0-9_]+", value):  # nome de env, não valor
                    continue
            elif pid in GROUP1_MASK:
                value = m.group(0)
                pw = m.group(1).lower()
                if looks_placeholder(pw) or pw in ("password", "postgres", "root", "pass", "senha", "user", "secret", "admin"):
                    c = "baixa"
                if any(h in value for h in ("localhost", "127.0.0.1", "@db:", "@postgres:", "@mysql:", "@mongo:", "@redis:",
                                             "host.docker.internal", "Server=.;", "(localdb)")):
                    c = "baixa"
            else:
                value = m.group(0)
                if looks_placeholder(value):
                    continue
                if pid in RANDOM_REQUIRED and not looks_random(re.sub(r"^[A-Za-z]+[-_]", "", value)):
                    continue
            seen_spans.append(span)
            yield pid, value, c, desc
