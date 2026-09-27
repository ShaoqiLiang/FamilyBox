"""把完整性材料嵌入发行包（S2a）——release.bat 在 PyInstaller 之后调用。

用法：uv run python scripts/embed_integrity.py [target_root]
target_root 默认 dist\\FamilyBox。在 <root>\\_internal\\integrity\\ 写入：
  manifest.sha256 / manifest.sha256.sig / release_public.pem / build_info.txt
清单覆盖 <root> 下除 _internal/integrity 外的全部文件，行格式与
scripts/sign_release.py 一致（sha256sum 兼容）；运行时 window/integrity.py
按同一规则复核。私钥缺失则报错退出——发行包必须带签名。
"""

from __future__ import annotations

import argparse
import base64
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "dist" / "FamilyBox"
PRIVATE = REPO / "keys" / "release_private.pem"
PUBLIC = REPO / "keys" / "release_public.pem"

INTEGRITY = "_internal/integrity"
_PSS = padding.PSS(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    salt_length=padding.PSS.DIGEST_LENGTH,
)

sys.path.insert(0, str(REPO / "scripts"))
from fbenc import sha256_fingerprint  # noqa: E402
from sign_release import sha256_file  # noqa: E402


def collect(root: Path, skip: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for p in sorted(root.rglob("*")):
        if p == skip or skip in p.parents:
            continue
        if p.is_file():
            out.append((p.relative_to(root).as_posix(), p))
    return out


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except OSError, subprocess.SubprocessError:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Embed integrity manifest into a packaged dist (S2a)"
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    if not (root / "FamilyBox.exe").is_file():
        print(
            f"[ERROR] FamilyBox.exe not found under {root} — package first "
            "(release.bat step 4)",
            file=sys.stderr,
        )
        return 1
    if not PRIVATE.is_file() or not PUBLIC.is_file():
        print(
            "[ERROR] release keypair missing under keys/ — run: "
            "uv run python scripts/gen_keys.py --release",
            file=sys.stderr,
        )
        return 1

    idir = root / INTEGRITY
    idir.mkdir(parents=True, exist_ok=True)
    for old in idir.iterdir():
        if old.is_file():
            old.unlink()

    entries = collect(root, idir)
    if not entries:
        print(f"[ERROR] no files to manifest under {root}", file=sys.stderr)
        return 1
    lines = [f"{sha256_file(path)}  {rel}" for rel, path in entries]
    manifest = ("\n".join(lines) + "\n").encode("utf-8")

    priv = serialization.load_pem_private_key(PRIVATE.read_bytes(), password=None)
    sig = priv.sign(manifest, _PSS, hashes.SHA256())  # type: ignore[attr-defined]

    (idir / "manifest.sha256").write_bytes(manifest)
    (idir / "manifest.sha256.sig").write_text(
        base64.b64encode(sig).decode("ascii") + "\n", encoding="ascii"
    )
    (idir / "release_public.pem").write_bytes(PUBLIC.read_bytes())
    (idir / "build_info.txt").write_text(
        f"commit={git_commit()}\n"
        f"builtAt={datetime.now().isoformat(timespec='seconds')}\n",
        encoding="ascii",
    )

    print(f"embedded   : {idir}")
    print(f"files      : {len(entries)}")
    pub = serialization.load_pem_public_key(PUBLIC.read_bytes())
    print(f"fingerprint: {sha256_fingerprint(pub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
