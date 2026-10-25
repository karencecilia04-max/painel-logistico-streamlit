"""Login com Google (OIDC nativo do Streamlit) e lista de e-mails ou domínios autorizados.

Configuração em .streamlit/secrets.toml, conforme secrets.toml.example.
Sem a seção [auth], o app abre sem login: é o caso da demonstração pública.
"""
import streamlit as st


def _cfg(secao: str) -> dict:
    try:
        return dict(st.secrets.get(secao, {}))
    except Exception:
        return {}


def _autorizado(email: str) -> bool:
    acesso = _cfg("acesso")
    email = (email or "").lower().strip()
    emails = {e.lower().strip() for e in acesso.get("emails", [])}
    dominios = {d.lower().strip().lstrip("@") for d in acesso.get("dominios", [])}
    return email in emails or email.split("@")[-1] in dominios


def exigir_login() -> None:
    if not _cfg("auth"):
        return

    if not st.user.is_logged_in:
        _, centro, _ = st.columns([1, 2, 1])
        with centro:
            from core.ui import LOGO
            if LOGO.exists():
                st.image(str(LOGO), width=260)
            st.markdown("## Painel Logístico")
            st.write("Acesso restrito à equipe. Entre com sua conta Google corporativa.")
            st.button("Entrar com Google", on_click=st.login, type="primary", width="stretch")
        st.stop()

    if not _autorizado(st.user.get("email", "")):
        st.error(f"O e-mail **{st.user.get('email')}** não tem acesso a esta plataforma. Fale com o administrador.")
        st.button("Sair", on_click=st.logout)
        st.stop()

    with st.sidebar:
        st.caption(f"Conectado como **{st.user.get('name') or st.user.get('email')}**")
        st.button("Sair", on_click=st.logout, width="stretch")
