# ToolHubSetup

Installiert **[ToolHub](https://github.com/r79jv66tjh-byte/toolhub)** – den Manager für eine Sammlung kleiner
Windows-Tools – direkt aus GitHub. Weitere Tools (DownloadSorter, TidyKit, FileProbe, GameWarden, MemTrainer,
SafeKeep, DiskFormatter, PartitionEditor, IsoFlasher) installierst und aktualisierst du danach im ToolHub-**Store**.

## Benutzung

1. `ToolHubSetup.exe` aus den [Releases](https://github.com/r79jv66tjh-byte/toolhubsetup/releases/latest) laden und starten.
2. Installationsart wählen:
   - **Mit Python** (empfohlen): alle Funktionen inkl. Claude-Schnittstelle. Fehlt Python, bietet das Setup an,
     das offizielle Paket über `winget` zu installieren.
   - **Als .exe**: läuft ohne Python, ohne Claude-Schnittstelle.
3. ToolHub wird nach `%LOCALAPPDATA%\ToolHub\apps\ToolHub` installiert, mit Startmenü- und optional
   Desktop-Verknüpfung. Keine Administratorrechte nötig.

Erneut ausführen = auf die neueste ToolHub-Version aktualisieren. Jeder Download wird per SHA-256 gegen das
`manifest.json` des Releases geprüft.

Hinweis: Die .exe ist nicht code-signiert, Windows SmartScreen zeigt deshalb evtl. „Unbekannter Herausgeber“.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
