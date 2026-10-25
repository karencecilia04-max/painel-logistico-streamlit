"""Confere o conteúdo dos Secrets SEM mostrar nenhum valor secreto.

Uso:
  1. Copie todo o texto do painel Secrets do Streamlit Cloud.
  2. Cole num arquivo .streamlit/secrets.toml nesta pasta (ele NÃO vai para o GitHub).
  3. No terminal, dentro desta pasta:  python conferir_secrets.py
"""
import re
import sys
import tomllib
from pathlib import Path

arq = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
erros, avisos = [], []

bruto = arq.read_bytes()
if bruto.startswith(b"\xef\xbb\xbf"):
    avisos.append("O arquivo começa com um caractere invisível (BOM). No painel do Streamlit isso não acontece; aqui foi ignorado.")
    bruto = bruto[3:]
try:
    s = tomllib.loads(bruto.decode("utf-8"))
except tomllib.TOMLDecodeError as e:
    print(f"ERRO DE FORMATO (o Streamlit não consegue ler NADA dos Secrets): {e}")
    print("   Dicas: textos sempre entre aspas; listas como [\"a\", \"b\"]; cada [seção] aparece uma vez só.")
    sys.exit(1)

# ---- [auth]
auth = s.get("auth")
if not auth:
    erros.append("Falta a seção [auth].")
else:
    for chave in ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url"):
        if not str(auth.get(chave, "")).strip():
            erros.append(f"[auth] falta '{chave}'.")
    extras = set(auth) - {"redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url", "expose_tokens"}
    if extras:
        erros.append(f"[auth] tem chaves que o Streamlit não reconhece: {sorted(extras)}")
    ru = auth.get("redirect_uri", "")
    if ru and not re.fullmatch(r"https://[a-z0-9-]+\.streamlit\.app/oauth2callback|http://localhost:\d+/oauth2callback", ru):
        erros.append(f"[auth] redirect_uri com formato inesperado: '{ru}' (deve ser https://SEU-APP.streamlit.app/oauth2callback, sem barra no fim).")
    if auth.get("client_id") and not str(auth["client_id"]).endswith(".apps.googleusercontent.com"):
        erros.append("[auth] client_id deve terminar em .apps.googleusercontent.com.")
    if auth.get("client_secret") and not str(auth["client_secret"]).startswith("GOCSPX-"):
        avisos.append("[auth] client_secret normalmente começa com GOCSPX-.")
    if len(str(auth.get("cookie_secret", ""))) < 32:
        erros.append("[auth] cookie_secret muito curto (use o comando de gerar com 48+ caracteres).")
    if auth.get("server_metadata_url") != "https://accounts.google.com/.well-known/openid-configuration":
        erros.append("[auth] server_metadata_url deve ser exatamente https://accounts.google.com/.well-known/openid-configuration")
    for chave, valor in auth.items():
        if isinstance(valor, str) and valor != valor.strip():
            erros.append(f"[auth] '{chave}' tem espaço no começo ou no fim.")

# ---- [acesso]
acesso = s.get("acesso", {})
emails, dominios = acesso.get("emails", []), acesso.get("dominios", [])
if not emails and not dominios:
    erros.append("[acesso] nenhum e-mail ou domínio liberado: ninguém conseguiria entrar.")
publicos = {"gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br", "uol.com.br", "bol.com.br"}
for d in dominios:
    if str(d).lower().lstrip("@") in publicos:
        erros.append(f"[acesso] o domínio '{d}' libera QUALQUER pessoa com esse e-mail. Deixe dominios = [] e liste os e-mails.")

# ---- [planilhas]
pl = s.get("planilhas", {})
for chave in ("followup", "encerrados", "tarifas"):
    v = str(pl.get(chave, ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{25,}", v):
        erros.append(f"[planilhas] '{chave}' ausente ou inválido (deve ser só o ID, o trecho entre /d/ e /edit).")

# ---- [gcp_service_account]
gcp = s.get("gcp_service_account", {})
for chave in ("type", "project_id", "private_key_id", "private_key", "client_email", "token_uri"):
    v = str(gcp.get(chave, ""))
    if not v or v in ("...",) or "..." in v and chave != "private_key":
        erros.append(f"[gcp_service_account] '{chave}' ausente ou ainda com valor de exemplo.")
pk = str(gcp.get("private_key", ""))
if pk and (not pk.startswith("-----BEGIN PRIVATE KEY-----\n") or not pk.rstrip().endswith("-----END PRIVATE KEY-----") or "MIIE..." in pk):
    erros.append("[gcp_service_account] private_key incompleta ou com quebra de linha errada (use o bloco gerado a partir do .json).")
if gcp.get("client_email") and not str(gcp["client_email"]).endswith(".iam.gserviceaccount.com"):
    erros.append("[gcp_service_account] client_email deve terminar em .iam.gserviceaccount.com.")

desconhecidas = set(s) - {"auth", "acesso", "planilhas", "gcp_service_account"}
if desconhecidas:
    avisos.append(f"Seções extras (ignoradas pelo app): {sorted(desconhecidas)}")

print(f"Arquivo: {arq}\n")
for a in avisos:
    print("AVISO:", a)
for e in erros:
    print("ERRO:", e)
if not erros:
    print("Formato OK.")
    print(f"   Conta de serviço: {gcp.get('client_email')}. Compartilhe as 3 planilhas com ela como Leitor.")
    print(f"   Endereço de retorno: {auth.get('redirect_uri')}. Precisa estar cadastrado igual no cliente OAuth.")
    print(f"   Pessoas liberadas: {len(emails)} e-mail(s), {len(dominios)} domínio(s).")
