"""验签发行物（sign_release.py 的对偶，S1）。

用法：uv run python scripts/verify_release.py <file|dir> [--pub keys/release_public.pem]

先打印所用公钥的 SHA256 指纹——请与 README 公布的指纹核对（信任锚），
然后依次校验：
  1) <target>.sha256.sig 是对 <target>.sha256 的有效 RSA-PSS(SHA-256) 签名；
  2) target 的全部文件重算哈希与清单逐条一致；清单缺失项、磁盘多出项均 FAIL。
退出码 0 = 全部通过；非 0 = 有失败项。
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PUB = REPO / "keys" / "release_public.pem"

sys.path.insert(0, str(REPO / "scripts"))
from fbenc import sha256_fingerprint  # noqa: E402
from sign_release import collect_entries, sha256_file  # noqa: E402

_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
_PSS = padding.PSS(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    salt_length=padding.PSS.DIGEST_LENGTH,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a signed release (S1)")
    parser.add_argument("target", type=Path, help="file or directory to verify")
    parser.add_argument("--pub", type=Path, default=DEFAULT_PUB)
    args = parser.parse_args()

    target = args.target.resolve()
    manifest_path = Path(str(target) + ".sha256")
    sig_path = Path(str(target) + ".sha256.sig")

    for p in (target, manifest_path, sig_path, args.pub):
        if not p.exists():
            print(f"[FAIL] missing: {p}", file=sys.stderr)
            return 1

    print(f"public key : {args.pub}")
    pub = serialization.load_pem_public_key(args.pub.read_bytes())
    print(f"             {sha256_fingerprint(pub)}")
    print("             ^ must match the fingerprint published in README")

    manifest = manifest_path.read_bytes()
    try:
        pub.verify(  # type: ignore[attr-defined]
            base64.b64decode(sig_path.read_text(encoding="ascii")),
            manifest,
            _PSS,
            hashes.SHA256(),
        )
    except InvalidSignature:
        print(
            "[FAIL] signature INVALID — manifest is not from the release key",
            file=sys.stderr,
        )
        return 1
    print(f"[OK] signature valid over {manifest_path.name}")

    expected: dict[str, str] = {}
    problems: list[str] = []
    for line in manifest.decode("utf-8").splitlines():
        m = _LINE.match(line)
        if not m:
            problems.append(f"manifest line malformed: {line!r}")
            continue
        expected[m.group(2)] = m.group(1)

    actual = dict(collect_entries(target))
    for rel, path in actual.items():
        if rel not in expected:
            problems.append(f"file on disk but not in manifest: {rel}")
        elif expected[rel] != sha256_file(path):
            problems.append(f"hash mismatch: {rel}")
    for rel in expected:
        if rel not in actual:
            problems.append(f"in manifest but missing on disk: {rel}")

    if problems:
        for p in problems:
            print(f"[FAIL] {p}", file=sys.stderr)
        return 1
    print(f"[OK] {len(expected)}/{len(expected)} entries match manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
