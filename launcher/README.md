# Moodar Launcher (POC)

This is a minimal proof-of-concept launcher written in Go. It:

- Checks the latest GitHub Release for a repository.
- Downloads a release asset (zip) whose name starts with a given prefix (default `project-`).
- Optionally downloads a `.sha256` checksum asset and verifies the archive.
- Extracts the archive to a temporary location and atomically replaces the project root (creates a backup).
- Runs `scripts/start_server.py` from the project root after applying the update.

Build:

```bash
# requires Go installed
go build -o moodar-launcher ./launcher
```

Usage examples:

```bash
# Dry-run (asks for confirmation)
./moodar-launcher --owner=JoaoAndrad --repo=DashboardAutomatizadoMoodar --project=/path/to/moodar --asset=project-

# Automatic apply
./moodar-launcher --owner=JoaoAndrad --repo=DashboardAutomatizadoMoodar --project=/path/to/moodar --asset=project- --auto
```

Notes:

- This is intentionally a small, easy-to-review PoC. It does not attempt advanced safety features like GPG-signed releases or differential update strategies.
- Test thoroughly on a copy of the project before using in production.
