"""生成品牌素材 RSA 密钥对（FBENC2 混合加密用）。

用法：uv run python scripts/gen_keys.py
写入 keys/logo_private.pem（PKCS8，本机，gitignored）与 keys/logo_public.pem。
已存在时拒绝覆盖（防误删真私钥）；磁盘上的 .pem 不加密保存，请自行备份 keys/。
"""

from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path(__file__).resolve().parents[1] / "keys"
PRIVATE = KEYS_DIR / "logo_private.pem"
PUBLIC = KEYS_DIR / "logo_public.pem"


def main() -> int:
    if PRIVATE.exists() or PUBLIC.exists():
        print(
            "[ERROR] key files already exist — refusing to overwrite:", file=sys.stderr
        )
        print(f"  {PRIVATE}\n  {PUBLIC}", file=sys.stderr)
        return 1
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    PUBLIC.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"{PRIVATE}\n{PUBLIC}")
    print("keep keys/ local — the private key must never be committed or shipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
