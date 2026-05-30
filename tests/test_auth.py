from unittest.mock import Mock

from src import auth


def test_require_auth_stops_when_auth_is_unconfigured(monkeypatch):
    monkeypatch.setattr(auth, "get_auth_config", lambda: {"username": "", "password_hash": ""})
    stop = Mock(side_effect=RuntimeError("stopped"))
    monkeypatch.setattr(auth.st, "stop", stop)
    monkeypatch.setattr(auth.st, "error", Mock())

    try:
        auth.require_auth()
    except RuntimeError as exc:
        assert str(exc) == "stopped"

    auth.st.error.assert_called_once()
    stop.assert_called_once()


def test_require_auth_returns_authenticated_username(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_auth_config",
        lambda: {"username": "admin", "password_hash": "pbkdf2_sha256$260000$salt$hash"},
    )
    monkeypatch.setattr(auth, "is_authenticated", lambda: True)
    monkeypatch.setitem(auth.st.session_state, auth.USERNAME_SESSION_KEY, "estimator")

    assert auth.require_auth() == "estimator"
