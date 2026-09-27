"""发行包完整性自检（S2a）——帮助菜单手动触发，结果经弹窗展示。

定位（AGENTS.md Release signing）：防"安装副本损坏/被改动"（病毒、误伤、
手工 patch），**不防蓄意重打包**——嵌入材料可被整体替换，出处证明依赖
下载时的外部清单（scripts/sign_release.py）+ README 公示指纹。

发行包布局（scripts/embed_integrity.py 打包后写入）：
  <root>/FamilyBox.exe
  <root>/_internal/integrity/manifest.sha256      清单："<sha256>  <相对路径>"（UTF-8/LF）
  <root>/_internal/integrity/manifest.sha256.sig  RSA-PSS(SHA-256) 签名（base64 文本）
  <root>/_internal/integrity/release_public.pem   签名公钥（指纹须与 README 一致）
  <root>/_internal/integrity/build_info.txt       commit=/builtAt=（S3 关于框来源行）

清单行格式与 scripts/sign_release.py 完全一致（sha256sum 兼容），复核规则
（相对根目录、排除 _internal/integrity 自身）也与其保持镜像。
开发/源码模式无 _internal/integrity → status="unsigned"，菜单项弹"未打包"提示。
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

INTEGRITY_DIR = "_internal/integrity"
MANIFEST_NAME = "manifest.sha256"
SIG_NAME = "manifest.sha256.sig"
PUBKEY_NAME = "release_public.pem"
BUILD_INFO_NAME = "build_info.txt"

_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
_CHUNK = 1 << 20
_PSS = padding.PSS(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    salt_length=padding.PSS.DIGEST_LENGTH,
)


@dataclass
class IntegrityReport:
    """status: ok = 全部一致；fail = 存在问题；unsigned = 无嵌入材料（开发模式）。"""

    status: str
    fingerprint: str | None = None
    files_checked: int = 0
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def install_root() -> Path:
    """冻结 = exe 所在目录；开发 = 仓库根（其下无 _internal/integrity → unsigned）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def fingerprint_of(pem: bytes) -> str:
    """公钥指纹（SHA256 over SPKI DER），格式与 scripts/fbenc.py 一致。"""
    pub = serialization.load_pem_public_key(pem)
    assert isinstance(pub, rsa.RSAPublicKey)
    der = pub.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    digest = hashlib.sha256(der).hexdigest().upper()
    return "SHA256:" + ":".join(digest[i : i + 4] for i in range(0, len(digest), 4))


def build_commit(root: Path | None = None) -> str | None:
    """build_info.txt 里的 commit=（S3 关于框来源行）；缺失/损坏返回 None。"""
    path = (root or install_root()) / INTEGRITY_DIR / BUILD_INFO_NAME
    try:
        for line in path.read_text(encoding="ascii").splitlines():
            if line.startswith("commit="):
                value = line.split("=", 1)[1].strip()
                return value or None
    except OSError, UnicodeDecodeError:
        return None
    return None


def _collect(root: Path, skip: Path) -> list[tuple[str, Path]]:
    """(相对路径, 绝对路径) 列表；跳过完整性目录自身，相对路径 POSIX 斜杠。"""
    out: list[tuple[str, Path]] = []
    for p in sorted(root.rglob("*")):
        if p == skip or skip in p.parents:
            continue
        if p.is_file():
            out.append((p.relative_to(root).as_posix(), p))
    return out


def verify_installation(
    root: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> IntegrityReport:
    """验签清单 → 逐文件对哈希。多出的文件记 warning 不判失败（用户可能放 ROM）。

    progress(done_bytes, total_bytes)：对预计哈希字节数逐块上报（S2a 进度条）；
    无法读取的文件记 unreadable，进度最终仍收尾到 (total, total)。
    """
    base = (root or install_root()).resolve()
    idir = base / INTEGRITY_DIR
    manifest_path = idir / MANIFEST_NAME
    sig_path = idir / SIG_NAME
    pub_path = idir / PUBKEY_NAME
    if not (manifest_path.is_file() and sig_path.is_file() and pub_path.is_file()):
        return IntegrityReport(status="unsigned")

    report = IntegrityReport(status="fail")
    try:
        report.fingerprint = fingerprint_of(pub_path.read_bytes())
        pub = serialization.load_pem_public_key(pub_path.read_bytes())
        assert isinstance(pub, rsa.RSAPublicKey)
        manifest = manifest_path.read_bytes()
        pub.verify(
            base64.b64decode(sig_path.read_text(encoding="ascii")),
            manifest,
            _PSS,
            hashes.SHA256(),
        )
    except InvalidSignature, ValueError, OSError:
        report.problems.append("signature:manifest.sha256")
        return report

    expected: dict[str, str] = {}
    for line in manifest.decode("utf-8").splitlines():
        m = _LINE.match(line)
        if not m:
            report.problems.append(f"format:{line[:72]}")
            continue
        expected[m.group(2)] = m.group(1)

    actual = dict(_collect(base, idir))
    for rel in actual:
        if rel not in expected:
            report.warnings.append(f"extra:{rel}")

    todo = [(rel, path) for rel, path in actual.items() if rel in expected]
    total = 0
    for _, path in todo:
        try:
            total += path.stat().st_size
        except OSError:
            pass
    done = 0
    for rel, path in todo:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(_CHUNK)
                    if not chunk:
                        break
                    digest.update(chunk)
                    done += len(chunk)
        except OSError:
            report.problems.append(f"unreadable:{rel}")
        if progress is not None:
            progress(min(done, total), total)
        if rel in expected and digest.hexdigest() != expected[rel]:
            report.problems.append(f"hash:{rel}")
    if progress is not None:
        progress(total, total)
    for rel in expected:
        if rel not in actual:
            report.problems.append(f"missing:{rel}")

    report.files_checked = len(actual)
    if not report.problems:
        report.status = "ok"
    return report
