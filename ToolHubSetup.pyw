"""ToolHubSetup – installiert ToolHub (Manager + Store für die Tool-Sammlung) aus GitHub.

Ablauf: Installationsart wählen (mit Python / als .exe) → ToolHub-Release laden →
SHA-256 prüfen → nach %LOCALAPPDATA%\\ToolHub\\apps\\ToolHub entpacken → Verknüpfungen → starten.
Weitere Tools installiert man danach bequem im ToolHub-Store.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from tkinter import messagebox, ttk

OWNER = "r79jv66tjh-byte"
REPO = "toolhub"
NAME = "ToolHub"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
UA = {"User-Agent": "ToolHubSetup"}
CREATE_NO_WINDOW = 0x08000000
INSTALL_FILE = ".toolhub-install.json"


def apps_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ToolHub" / "apps"


def target_dir() -> Path:
    return apps_dir() / NAME


def find_python() -> str | None:
    for cand in ("py", "python"):
        exe = shutil.which(cand)
        if exe and "WindowsApps" not in exe:
            try:
                out = subprocess.run([exe, "-c", "import sys;print(sys.version_info[:2] >= (3, 10))"],
                                     capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
                if out.stdout.strip() == "True":
                    return exe
            except (OSError, subprocess.TimeoutExpired):
                pass
    return None


def pythonw_for(py: str) -> str:
    """pythonw.exe zum gefundenen Interpreter (für Start ohne Konsolenfenster)."""
    out = subprocess.run([py, "-c", "import sys;print(sys.executable)"], capture_output=True, text=True,
                         creationflags=CREATE_NO_WINDOW)
    exe = Path(out.stdout.strip())
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def installed() -> dict | None:
    try:
        return json.loads((target_dir() / INSTALL_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def make_shortcut(lnk: Path, target: str, args: str, workdir: str, icon: str) -> None:
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
          "$s.TargetPath=$env:TGT;$s.Arguments=$env:ARGS;$s.WorkingDirectory=$env:WD;"
          "$s.IconLocation=$env:ICO;$s.Save()")
    env = {**os.environ, "LNK": str(lnk), "TGT": target, "ARGS": args, "WD": workdir, "ICO": icon}
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True,
                   creationflags=CREATE_NO_WINDOW)


def install(mode: str, desktop: bool, log, progress) -> list[str]:
    """Installiert/aktualisiert ToolHub. Liefert den Startbefehl (Liste)."""
    py = None
    if mode == "python":
        py = find_python()
        if not py:
            raise RuntimeError("Python 3.10+ wurde nicht gefunden.")
    log("Frage neueste ToolHub-Version bei GitHub ab …")
    rel = json.loads(get(API))
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    manifest = json.loads(get(assets["manifest.json"]))
    fname = f"{NAME}-source.zip" if mode == "python" else f"{NAME}.exe"
    want = manifest["files"][fname]["sha256"]
    apps = apps_dir()
    apps.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=apps, prefix=".setup-") as tmp:
        tmp = Path(tmp)
        dl = tmp / fname
        log(f"Lade {fname} ({rel['tag_name']}) …")
        req = urllib.request.Request(assets[fname], headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r, open(dl, "wb") as f:
            total, done = int(r.headers.get("Content-Length") or 0), 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if total:
                    progress(done / total)
        if sha256(dl) != want:
            raise RuntimeError("Prüfsumme stimmt nicht – Download abgebrochen.")
        log("Prüfsumme OK, installiere …")
        stage = tmp / "stage"
        if mode == "python":
            with zipfile.ZipFile(dl) as z:
                if any(m.startswith("/") or ".." in Path(m).parts for m in z.namelist()):
                    raise RuntimeError("Ungültiges Archiv.")
                z.extractall(tmp / "x")
            shutil.move(str(tmp / "x" / NAME), str(stage))
        else:
            stage.mkdir()
            shutil.move(str(dl), str(stage / fname))
        (stage / INSTALL_FILE).write_text(json.dumps(
            {"name": NAME, "repo": REPO, "version": rel["tag_name"], "mode": mode,
             "category": "", "installed_at": time.strftime("%Y-%m-%d %H:%M")}, indent=2), encoding="utf-8")
        target = target_dir()
        old = target.with_name(NAME + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if target.exists():
            try:
                target.rename(old)
            except OSError as e:
                raise RuntimeError("ToolHub läuft noch – bitte erst schließen.") from e
        shutil.move(str(stage), str(target))
        shutil.rmtree(old, ignore_errors=True)

    target = target_dir()
    if mode == "python":
        cmd = [pythonw_for(py), str(target / "ToolHub.pyw")]
        icon = cmd[0]
    else:
        cmd = [str(target / "ToolHub.exe")]
        icon = cmd[0]
    log("Lege Verknüpfungen an …")
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "ToolHub.lnk"
    args = subprocess.list2cmdline(cmd[1:])
    make_shortcut(start_menu, cmd[0], args, str(target), icon)
    if desktop:
        make_shortcut(Path.home() / "Desktop" / "ToolHub.lnk", cmd[0], args, str(target), icon)
    log(f"ToolHub {rel['tag_name']} installiert.")
    return cmd


class Setup(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ToolHub Setup")
        self.geometry("560x420")
        self.resizable(False, False)
        self.py = find_python()
        inst = installed()
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="ToolHub Setup", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(f, text="Installiert ToolHub – den Manager für alle Tools mit eingebautem Store "
                          "(weitere Tools installieren, Updates, Claude-Anbindung).",
                  wraplength=520).pack(anchor="w", pady=(4, 12))
        if inst:
            ttk.Label(f, text=f"Bereits installiert: {inst.get('version')} – Setup aktualisiert auf die neueste Version.",
                      foreground="#15803d", wraplength=520).pack(anchor="w", pady=(0, 8))
        self.mode = tk.StringVar(value=(inst or {}).get("mode") or ("python" if self.py else "exe"))
        box = ttk.LabelFrame(f, text="Installationsart", padding=10)
        box.pack(fill="x")
        ttk.Radiobutton(box, text="Mit Python (empfohlen: alle Funktionen inkl. Claude-Schnittstelle)",
                        value="python", variable=self.mode).pack(anchor="w")
        ttk.Label(box, text=("Python gefunden: " + self.py) if self.py else
                  "Python nicht gefunden – kann über winget (offizielles Paket) installiert werden.",
                  foreground="#6b7280", wraplength=480).pack(anchor="w", padx=20)
        ttk.Radiobutton(box, text="Als .exe (ohne Python, ohne Claude-Schnittstelle)",
                        value="exe", variable=self.mode).pack(anchor="w", pady=(6, 0))
        self.desktop = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Verknüpfung auf dem Desktop", variable=self.desktop).pack(anchor="w", pady=(10, 0))
        ttk.Label(f, text=f"Ziel: {target_dir()}", foreground="#6b7280").pack(anchor="w", pady=(4, 0))
        self.pb = ttk.Progressbar(f, maximum=1.0)
        self.pb.pack(fill="x", pady=(14, 4))
        self.status = ttk.Label(f, text="", wraplength=520)
        self.status.pack(anchor="w")
        self.btn = ttk.Button(f, text="Aktualisieren" if inst else "Installieren", command=self.start)
        self.btn.pack(side="bottom", anchor="e")

    def log(self, text):
        self.after(0, lambda: self.status.config(text=text))

    def progress(self, v):
        self.after(0, lambda: self.pb.configure(value=v))

    def start(self):
        mode = self.mode.get()
        if mode == "python" and not self.py:
            if not messagebox.askyesno("Python fehlt", "Python 3.13 jetzt über winget installieren "
                                                       "(offizielles Paket der Python Software Foundation)?"):
                return
            self.btn.config(state="disabled")
            self.log("Installiere Python über winget … (kann einige Minuten dauern)")
            threading.Thread(target=self._install_python, daemon=True).start()
            return
        self.btn.config(state="disabled")
        threading.Thread(target=self._run, args=(mode,), daemon=True).start()

    def _install_python(self):
        try:
            r = subprocess.run(["winget", "install", "-e", "--id", "Python.Python.3.13", "--scope", "user",
                                "--accept-package-agreements", "--accept-source-agreements", "--silent"],
                               capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            # PATH der laufenden Sitzung kennt die neue Installation noch nicht -> Standardpfad prüfen
            guess = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python313" / "python.exe"
            self.py = find_python() or (str(guess) if guess.exists() else None)
            if not self.py:
                raise RuntimeError("Python-Installation fehlgeschlagen:\n" + (r.stderr or r.stdout)[-600:])
        except (OSError, RuntimeError) as e:
            self.after(0, lambda: (messagebox.showerror("Python", f"{e}\n\nTipp: „Als .exe“ wählen."),
                                   self.btn.config(state="normal")))
            return
        self._run("python")

    def _run(self, mode):
        global find_python
        py = self.py
        if mode == "python" and py:
            find_python = lambda: py  # noqa: E731 – nach winget-Installation den bekannten Pfad nutzen
        try:
            cmd = install(mode, self.desktop.get(), self.log, self.progress)
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: (messagebox.showerror("Setup", str(e)), self.btn.config(state="normal")))
            return

        def done():
            self.pb.configure(value=1.0)
            if messagebox.askyesno("Fertig", "ToolHub ist installiert. Jetzt starten?\n\n"
                                             "Weitere Tools installierst du dort über „🛒 Store“."):
                subprocess.Popen(cmd, cwd=str(target_dir()))
            self.destroy()
        self.after(0, done)


if __name__ == "__main__":
    Setup().mainloop()
