"""Сертификат приложения OPC UA-сервера эмулятора.

При первом запуске в каталоге PKI (по умолчанию ``pki/``, в .gitignore) создаются закрытый ключ
RSA (PEM) и самоподписанный сертификат X.509 (DER) с ApplicationUri сервера в subjectAltName —
этого требует политика Basic256Sha256. Повторный запуск берёт готовые файлы; сертификат с
истёкшим сроком или чужим URI создаётся заново.

Клиент (Telegraf, UaExpert, отчёт) должен доверять этому сертификату: файл ``server_cert.der``
кладут в доверенные клиента (docs/security.md).
"""

from __future__ import annotations

import contextlib
import socket
from pathlib import Path

from asyncua.crypto.cert_gen import setup_self_signed_certificate
from cryptography.x509.oid import ExtendedKeyUsageOID

KEY_FILE = "server_key.pem"
CERT_FILE = "server_cert.der"


async def ensure_server_certificate(pki_dir: Path, app_uri: str, hostname: str = "") -> tuple[Path, Path]:
    """Создать (если нужно) ключ и сертификат; вернуть пути (сертификат, ключ)."""
    pki_dir.mkdir(parents=True, exist_ok=True)
    key_path = pki_dir / KEY_FILE
    cert_path = pki_dir / CERT_FILE
    host = hostname or socket.gethostname()
    await setup_self_signed_certificate(
        key_path,
        cert_path,
        app_uri,
        host,
        [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH],
        {
            "countryName": "RU",
            "organizationName": "plc-iiot-stack demo",
            "commonName": "KNS-1 PLC emulator",
        },
    )
    with contextlib.suppress(OSError):  # на Windows права задаёт ACL каталога
        key_path.chmod(0o600)
    return cert_path, key_path
