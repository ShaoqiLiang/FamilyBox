"""D1/A1 资产测试：FBENC2 混合加密（RSA+AES）可解密、防篡改、图标规格、
asset_path 解析、密文入库纪律。解密属 dev/打包环节（fbenc + 本地 RSA 私钥）。"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from window.resources import asset_path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fbenc import InvalidTag, decrypt_bytes, encrypt_bytes  # noqa: E402


class TestEncryptedAssets:
    def test_all_enc_assets_decrypt_to_expected_magic(self) -> None:
        cases = [
            ("logo.png.enc", b"\x89PNG"),
            ("logo2.png.enc", b"\x89PNG"),
            ("logo.webm.enc", b"\x1a\x45\xdf\xa3"),  # EBML/Matroska
            ("icon.png.enc", b"\x89PNG"),
        ]
        for name, magic in cases:
            data = decrypt_bytes(asset_path(f"assets/{name}").read_bytes())
            assert data[:4] == magic, name

    def test_ico_enc_decrypts_with_multi_sizes(self) -> None:
        data = decrypt_bytes(asset_path("assets/familybox.ico.enc").read_bytes())
        assert data[:4] == b"\x00\x00\x01\x00"  # ICONDIR: reserved=0, type=1
        count = struct.unpack("<H", data[4:6])[0]
        sizes = {
            256 if data[6 + i * 16] == 0 else data[6 + i * 16] for i in range(count)
        }
        assert {16, 32, 48, 256} <= sizes

    def test_roundtrip_encrypt_decrypt(self) -> None:
        blob = b"FamilyBox FBENC2 roundtrip \x00\xff"
        assert decrypt_bytes(encrypt_bytes(blob)) == blob

    def test_decrypt_rejects_cleartext(self) -> None:
        with pytest.raises(ValueError):
            decrypt_bytes(asset_path("resources.py").read_bytes())

    def test_decrypt_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            decrypt_bytes(b"junk-data-00")

    def test_tampered_ciphertext_fails_auth(self) -> None:
        """GCM 认证标签：翻转密文最后一字节必须解密失败。"""
        blob = bytearray(encrypt_bytes(b"tamper probe \x00\x01\x02"))
        blob[-1] ^= 0xFF
        with pytest.raises(InvalidTag):
            decrypt_bytes(bytes(blob))


class TestCiphertextOnlyPolicy:
    """资产目录只允许密文——派生图标同样不得以明文落盘。"""

    def test_no_plaintext_assets_in_assets_dir(self) -> None:
        assets_dir = asset_path("assets")
        for name in (
            "icon.png",
            "familybox.ico",
            "logo.png",
            "logo2.png",
            "logo.webm",
        ):
            assert not (assets_dir / name).exists(), name


class TestIconAssets:
    def test_icon_png_enc_is_32x32(self) -> None:
        data = decrypt_bytes(asset_path("assets/icon.png.enc").read_bytes())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", data[16:24])
        assert (w, h) == (32, 32)


class TestAssetPath:
    def test_enc_resolves_inside_package_assets(self) -> None:
        p = asset_path("assets/logo2.png.enc")
        assert p.is_file()
        assert p.parent.name == "assets"
        assert p.parent.parent.name == "window"

    def test_dev_decrypted_working_copy_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """asset_path 优先取 build/assets 明文工作副本（dev 解密产物）。"""
        import window.resources as res

        probe = tmp_path / "src" / "window" / "resources.py"
        probe.parent.mkdir(parents=True)
        probe.write_bytes(b"#")
        monkeypatch.setattr(
            res, "__file__", str(tmp_path / "src" / "window" / "resources.py")
        )
        (tmp_path / "build" / "assets").mkdir(parents=True)
        (tmp_path / "build" / "assets" / "icon.png").write_bytes(b"decrypted")
        assert res.asset_path("assets/icon.png").read_bytes() == b"decrypted"
