"""FBENC2 混合加密（RSA-4096-OAEP 包裹 AES-256-GCM 数据密钥；dev/打包侧）。

格式：FBENC2 魔数(6B) | RSA-OAEP-SHA256 包裹的 AES-256 密钥(512B @RSA-4096)
      | GCM nonce(12B) | AES-256-GCM 密文（含 16B 认证标签）。

密钥：keys/logo_private.pem（解密，本机，gitignored）/ logo_public.pem（加密）。
每次加密随机生成 AES 数据密钥——无口令可猜，暴力破解 = 分解 RSA-4096。
运行时不解密：明文仅存在于 prepare_assets（开发）与打包（发行）环节，
由 scripts/prepare_assets.py / release.bat 产出到 build/assets/。
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"FBENC2"
NONCE_LEN = 12
KEYS_DIR = Path(__file__).resolve().parents[1] / "keys"
PRIVATE_KEY_FILE = KEYS_DIR / "logo_private.pem"
PUBLIC_KEY_FILE = KEYS_DIR / "logo_public.pem"

_OAEP = rsa_padding.OAEP(
    mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)

__all__ = [
    "MAGIC",
    "InvalidTag",
    "decrypt_bytes",
    "encrypt_bytes",
    "load_private_key",
    "load_public_key",
]


def load_private_key() -> object:
    return serialization.load_pem_private_key(
        PRIVATE_KEY_FILE.read_bytes(), password=None
    )


def load_public_key() -> object:
    return serialization.load_pem_public_key(PUBLIC_KEY_FILE.read_bytes())


def encrypt_bytes(data: bytes) -> bytes:
    """信封加密：随机 AES-256 密钥 + GCM，公钥包裹密钥。加密只需公钥。"""
    aes_key = os.urandom(32)
    nonce = os.urandom(NONCE_LEN)
    pub = load_public_key()
    wrapped = pub.encrypt(aes_key, _OAEP)  # type: ignore[attr-defined]
    ct = AESGCM(aes_key).encrypt(nonce, data, None)
    return MAGIC + wrapped + nonce + ct


def decrypt_bytes(blob: bytes) -> bytes:
    """解信封；魔数不符抛 ValueError，密文被篡改抛 InvalidTag。"""
    priv = load_private_key()
    klen = priv.key_size // 8  # type: ignore[attr-defined]
    head = len(MAGIC) + klen
    if blob[: len(MAGIC)] != MAGIC or len(blob) < head + NONCE_LEN + 16:
        raise ValueError("not an FBENC2 blob")
    wrapped = blob[len(MAGIC) : head]
    nonce = blob[head : head + NONCE_LEN]
    ct = blob[head + NONCE_LEN :]
    aes_key = priv.decrypt(wrapped, _OAEP)  # type: ignore[attr-defined]
    return AESGCM(aes_key).decrypt(nonce, ct, None)
