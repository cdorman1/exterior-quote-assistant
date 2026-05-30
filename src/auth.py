from __future__ import annotations

import base64
import hashlib
import hmac
import os
from secrets import compare_digest

from dotenv import load_dotenv
import streamlit as st

AUTH_SESSION_KEY = "eqa_authenticated"
USERNAME_SESSION_KEY = "eqa_username"

load_dotenv()


def _get_setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_auth_config() -> dict[str, str]:
    return {
        "username": _get_setting("APP_AUTH_USERNAME"),
        "password_hash": _get_setting("APP_AUTH_PASSWORD_HASH"),
    }


def hash_password(password: str, salt: bytes | None = None, iterations: int = 260_000) -> str:
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, hash_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def is_authenticated() -> bool:
    return bool(st.session_state.get(AUTH_SESSION_KEY))


def login(username: str, password: str) -> bool:
    config = get_auth_config()
    if not config["username"] or not config["password_hash"]:
        return False
    if not compare_digest(username, config["username"]):
        return False
    if not verify_password(password, config["password_hash"]):
        return False
    st.session_state[AUTH_SESSION_KEY] = True
    st.session_state[USERNAME_SESSION_KEY] = username
    return True


def logout() -> None:
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state.pop(USERNAME_SESSION_KEY, None)


def require_auth() -> str:
    config = get_auth_config()
    if not config["username"] or not config["password_hash"]:
        st.error("Application authentication is not configured.")
        st.stop()

    if is_authenticated():
        return str(st.session_state.get(USERNAME_SESSION_KEY) or config["username"])

    st.title("Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if login(username, password):
            st.rerun()
        st.error("Invalid username or password.")

    st.stop()


def password_hash_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate an APP_AUTH_PASSWORD_HASH value.")
    parser.add_argument("password", help="Plaintext password to hash")
    args = parser.parse_args()
    print(hash_password(args.password))


if __name__ == "__main__":
    password_hash_cli()
