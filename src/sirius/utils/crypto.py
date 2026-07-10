from __future__ import annotations

from cryptography.fernet import Fernet
from loguru import logger

_PREFIX = "enc::"


class ContentCipher:
    """Fernet encryption for sensitive memory contents. No key = passthrough."""

    def __init__(self, key: str | None) -> None:
        self._fernet = None
        if key:
            try:
                self._fernet = Fernet(key.encode())
            except Exception:
                logger.warning(
                    "ENCRYPTION_KEY is not a valid Fernet key — encryption is DISABLED. "
                    "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                )

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, text: str) -> str:
        if not self._fernet:
            return text
        return _PREFIX + self._fernet.encrypt(text.encode()).decode()

    def decrypt(self, text: str) -> str:
        if not text.startswith(_PREFIX):
            return text
        if not self._fernet:
            raise ValueError("Encrypted content found but ENCRYPTION_KEY is not set.")
        return self._fernet.decrypt(text[len(_PREFIX):].encode()).decode()
