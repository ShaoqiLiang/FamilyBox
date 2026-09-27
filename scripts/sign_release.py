"""对发行物生成签名清单（软件出处证明，S1）。

用法：uv run python scripts/sign_release.py <file|dir> [--key keys/release_private.pem]

<target> 可以是单个发行文件（MSI / 发行 zip）或整个发行目录（如 dist\\FamilyBox）。
与 target 同目录产出两个文件：
  <target>.sha256      清单：每行 "<sha256>  <相对路径>"，UTF-8 + LF，sha256sum 兼容
  <target>.sha256.sig  用 RSA-PSS(SHA-256) 对清单字节做的签名（base64 文本）

使用者凭 README 公示的公钥指纹核对 keys/release_public.pem 后运行
scripts/verify_release.py 验证。签名清单防篡改与冒名；信任锚说明见 README。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

REPO = Path(__file__).resolve().parents[1]
DEFAULT_KEY = REPO / "keys" / "release_private.pem"

sys.path.insert(0, str(REPO / "scripts"))
from fbenc import sha256_fingerprint  # noqa: E402

_CHUNK = 1 << 20
_PSS = padding.PSS(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    salt_length=padding.PSS.DIGEST_LENGTH,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_entries(target: Path) -> list[tuple[str, Path]]:
    """(相对路径, 绝对路径) 列表；文件 → 单条，目录 → 递归全部普通文件（排序）。"""
    if target.is_file():
        return [(target.name, target)]
    return [
        (p.relative_to(target).as_posix(), p)
        for p in sorted(target.rglob("*"))
        if p.is_file()
    ]


def build_manifest(entries: list[tuple[str, Path]]) -> bytes:
    lines = [f"{sha256_file(path)}  {rel}" for rel, path in entries]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign a release artifact (S1)")
    parser.add_argument("target", type=Path, help="file or directory to sign")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.exists():
        print(f"[ERROR] target not found: {target}", file=sys.stderr)
        return 1
    if not args.key.exists():
        print(
            f"[ERROR] signing key missing: {args.key}\n"
            "        run: uv run python scripts/gen_keys.py --release",
            file=sys.stderr,
        )
        return 1

    entries = collect_entries(target)
    if not entries:
        print(f"[ERROR] target contains no files: {target}", file=sys.stderr)
        return 1
    manifest = build_manifest(entries)

    priv = serialization.load_pem_private_key(args.key.read_bytes(), password=None)
    sig = priv.sign(  # type: ignore[attr-defined]
        manifest,
        _PSS,
        hashes.SHA256(),
    )

    manifest_path = Path(str(target) + ".sha256")
    sig_path = Path(str(target) + ".sha256.sig")
    manifest_path.write_bytes(manifest)
    sig_path.write_text(base64.b64encode(sig).decode("ascii") + "\n", encoding="ascii")

    print(f"files      : {len(entries)}")
    print(f"manifest   : {manifest_path}")
    print(f"signature  : {sig_path}")
    print(f"signed with: {sha256_fingerprint(priv.public_key())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
