from pathlib import Path

root = Path(__file__).resolve().parents[1]

blocked = []
for p in root.rglob("*"):
    if not p.is_file() or ".git" in p.parts:
        continue
    if p.name in {".env", ".env.local", ".env.production", "credentials.json", "secrets.json"}:
        blocked.append(str(p))
    if p.suffix in {".pem", ".key"}:
        blocked.append(str(p))

if blocked:
    raise SystemExit("Potential secret files found:\n" + "\n".join(blocked))

print("Repository hygiene check: PASS")
