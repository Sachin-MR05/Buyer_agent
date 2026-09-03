from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import Settings


class TokenCipherError(Exception):
    """The stored auth token could not be decrypted (wrong/rotated key, or
    corrupted data)."""


class TokenCipher:
    """Encrypts/decrypts merchant auth tokens with a server-side Fernet key.

    This is the ONLY place in the service that ever sees a plaintext auth
    token outside of the single moment it's needed to call a merchant. It
    is never logged, never returned by any API response, and never stored
    unencrypted.
    """

    def __init__(self, settings: Settings):
        self._fernet = Fernet(settings.registry_encryption_key.encode())

    def encrypt(self, plaintext_token: str) -> str:
        return self._fernet.encrypt(plaintext_token.encode()).decode()

    def decrypt(self, ciphertext_token: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext_token.encode()).decode()
        except InvalidToken as exc:
            raise TokenCipherError("Stored auth token could not be decrypted") from exc
