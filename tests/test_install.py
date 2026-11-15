import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SETUP = Path(__file__).resolve().parent.parent / "ToolHubSetup.pyw"
_loader = importlib.machinery.SourceFileLoader("toolhubsetup", str(SETUP))
_spec = importlib.util.spec_from_loader("toolhubsetup", _loader)
assert _spec is not None
setup = importlib.util.module_from_spec(_spec)
_loader.exec_module(setup)

EXE = b"MZ fake ToolHub executable"


class Download(io.BytesIO):
    """Stands in for the HTTP response of urlopen; only GitHub is replaced, the install runs for real."""

    headers = {"Content-Length": "0"}

    def __enter__(self) -> "Download":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class InstallTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        environment = mock.patch.dict(
            os.environ, {"LOCALAPPDATA": str(self.root / "local"), "APPDATA": str(self.root / "roaming")}
        )
        environment.start()
        self.addCleanup(environment.stop)
        shortcuts = mock.patch.object(setup, "make_shortcut")
        self.shortcut = shortcuts.start()
        self.addCleanup(shortcuts.stop)

    def serve(self, name: str, payload: bytes, digest: str) -> None:
        release = {
            "tag_name": "v9.9.9",
            "assets": [
                {"name": "manifest.json", "browser_download_url": "https://example.invalid/manifest.json"},
                {"name": name, "browser_download_url": f"https://example.invalid/{name}"},
            ],
        }
        manifest = {"files": {name: {"sha256": digest}}}
        api = {setup.API: json.dumps(release).encode(), "https://example.invalid/manifest.json": json.dumps(manifest).encode()}
        patches = [
            mock.patch.object(setup, "get", side_effect=lambda url: api[url]),
            mock.patch.object(setup.urllib.request, "urlopen", side_effect=lambda _request, **_options: Download(payload)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def install(self, mode: str = "exe") -> list[str]:
        return setup.install(mode, desktop=False, log=lambda _text: None, progress=lambda _value: None)

    def test_exe_is_installed_with_record_and_start_menu_entry(self) -> None:
        self.serve("ToolHub.exe", EXE, hashlib.sha256(EXE).hexdigest())
        command = self.install()
        target = self.root / "local" / "ToolHub" / "apps" / "ToolHub"
        self.assertEqual(command, [str(target / "ToolHub.exe")])
        self.assertEqual((target / "ToolHub.exe").read_bytes(), EXE)
        record = json.loads((target / setup.INSTALL_FILE).read_text(encoding="utf-8"))
        self.assertEqual((record["version"], record["mode"]), ("v9.9.9", "exe"))
        self.assertEqual(self.shortcut.call_count, 1)

    def test_wrong_checksum_installs_nothing(self) -> None:
        self.serve("ToolHub.exe", EXE, "0" * 64)
        with self.assertRaisesRegex(RuntimeError, "Prüfsumme"):
            self.install()
        self.assertFalse((self.root / "local" / "ToolHub" / "apps" / "ToolHub").exists())
        self.shortcut.assert_not_called()

    def test_archive_escaping_the_folder_is_rejected(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ToolHub/../../evil.txt", "x")
        payload = buffer.getvalue()
        self.serve("ToolHub-source.zip", payload, hashlib.sha256(payload).hexdigest())
        with mock.patch.object(setup, "find_python", return_value="python"):
            with self.assertRaisesRegex(RuntimeError, "Ungültiges Archiv"):
                self.install("python")
        self.assertFalse(any(self.root.rglob("evil.txt")))


if __name__ == "__main__":
    unittest.main()
