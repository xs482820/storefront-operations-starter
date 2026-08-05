from app.core.security import create_access_token, decode_access_token


def test_access_token_carries_session_version() -> None:
    token = create_access_token("employee_01", expires_minutes=5, session_version=4)
    assert decode_access_token(token)["sv"] == 4
