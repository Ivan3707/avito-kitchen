import secrets
from hashlib import sha256


def generate_action_token() -> str:
    return secrets.token_urlsafe(32)


def hash_action_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()
