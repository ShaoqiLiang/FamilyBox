"""生成 RSA 密钥对：品牌素材（FBENC2）或发行签名（软件出处证明）。

用法：
  uv run python scripts/gen_keys.py             :: logo 素材密钥（FBENC2 加解密用）
  uv run python scripts/gen_keys.py --release   :: 发行签名密钥（长期身份，S1）

私钥写入 keys/（PKCS8，本机，gitignored）；磁盘上的 .pem 不加密保存，请自行备份 keys/。
已存在时拒绝覆盖（防误删真私钥）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

REPO = Path(__file__).resolve().parents[1]
KEYS_DIR = REPO / "keys"

sys.path.insert(0, str(REPO / "scripts"))
from fbenc import sha256_fingerprint  # noqa: E402

TARGETS = {
    "logo": ("logo_private.pem", "logo_public.pem"),
    "release": ("release_private.pem", "release_public.pem"),
}


def generate(which: str) -> int:
    private = KEYS_DIR / TARGETS[which][0]
    public = KEYS_DIR / TARGETS[which][1]
    if private.exists() or public.exists():
        print(
            "[ERROR] key files already exist — refusing to overwrite:", file=sys.stderr
        )
        print(f"  {private}\n  {public}", file=sys.stderr)
        return 1
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"{private}\n{public}")
    print(
        f"public key fingerprint (publish in README):\n  {sha256_fingerprint(key.public_key())}"
    )
    print("keep keys/ local — the private key must never be committed or shipped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate FamilyBox RSA keypairs")
    parser.add_argument(
        "--release",
        action="store_true",
        help="generate the long-lived release signing keypair instead of logo keys",
    )
    args = parser.parse_args()
    return generate("release" if args.release else "logo")


if __name__ == "__main__":
    raise SystemExit(main())
