"""Monta o conteúdo do painel *Secrets* do Streamlit Cloud a partir das credenciais do Google.

Uso (no terminal, dentro da pasta do projeto):
    python gerar_secrets.py

O script pede: o arquivo .json da conta de serviço, o Client ID e o Client secret do login Google,
o endereço do app, os e-mails autorizados e os links das 3 planilhas. Gera .streamlit/secrets.toml (que NÃO vai para o GitHub).
Depois, copie o conteúdo desse arquivo e cole em Streamlit Cloud, em App > Settings > Secrets.
"""
import json
import re
import secrets
from getpass import getpass
from pathlib import Path


def id_da_planilha(link: str) -> str:
    """Aceita o link completo (…/spreadsheets/d/<ID>/edit…) ou só o ID."""
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", link)
    valor = m.group(1) if m else link.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", valor):
        raise SystemExit(f"Link de planilha inválido: {link!r}")
    return valor


def toml_str(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)  # aspas e \n escapados do jeito que o TOML aceita


def main():
    print("\n=== Gerador de secrets do Painel Logístico ===\n")
    caminho = input("1) Caminho do arquivo .json da conta de serviço (pode arrastar o arquivo aqui): ").strip().strip('"')
    conta = json.loads(Path(caminho).read_text(encoding="utf-8"))
    print(f"   Conta de serviço: {conta['client_email']}")

    client_id = input("2) Client ID do login Google (termina em .apps.googleusercontent.com): ").strip()
    client_secret = getpass("3) Client secret do login Google (não aparece ao digitar): ").strip()
    url = input("4) Endereço do app (ex.: https://painel-logistico.streamlit.app): ").strip().rstrip("/")
    emails = [e.strip().lower() for e in input("5) E-mails autorizados, separados por vírgula: ").split(",") if e.strip()]
    dominios = [d.strip().lower().lstrip("@") for d in
                input("6) Domínio inteiro autorizado (opcional, ex.: empresa.com.br. Enter para pular): ").split(",") if d.strip()]
    print("7) Cole o link de cada planilha (o mesmo da barra do navegador):")
    planilhas = {nome: id_da_planilha(input(f"   - {rotulo}: ")) for nome, rotulo in
                 [("followup", "Follow-up (aba Consolidado)"), ("encerrados", "Processos encerrados (aba CONCLUIDOS)"),
                  ("tarifas", "Tarifas / calculadora")]}

    linhas = [
        "[auth]",
        f"redirect_uri = {toml_str(url + '/oauth2callback')}",
        f"cookie_secret = {toml_str(secrets.token_urlsafe(48))}",
        f"client_id = {toml_str(client_id)}",
        f"client_secret = {toml_str(client_secret)}",
        'server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"',
        "",
        "[acesso]",
        f"emails = {json.dumps(emails, ensure_ascii=False)}",
        f"dominios = {json.dumps(dominios, ensure_ascii=False)}",
        "",
        "[planilhas]",
    ] + [f"{k} = {toml_str(v)}" for k, v in planilhas.items()] + [
        "",
        "[gcp_service_account]",
    ] + [f"{k} = {toml_str(str(v))}" for k, v in conta.items()]

    destino = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nGerado: {destino}")
    print("  Abra esse arquivo, copie TODO o conteúdo e cole em Streamlit Cloud, em Settings > Secrets.")
    print("  Depois de colar, guarde o .json num lugar seguro ou apague. Não envie por e-mail nem chat.\n")


if __name__ == "__main__":
    main()
