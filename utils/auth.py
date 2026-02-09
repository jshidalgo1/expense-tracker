import streamlit as st
import streamlit_authenticator as stauth


def _to_dict(value):
    if hasattr(value, "items"):
        return {key: _to_dict(item) for key, item in value.items()}
    return value


def get_authenticator():
    if "credentials" not in st.secrets or "cookie" not in st.secrets:
        st.error("Missing authentication secrets. Add credentials and cookie to .streamlit/secrets.toml.")
        st.stop()

    config = _to_dict(st.secrets)

    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        auto_hash=False,
    )
