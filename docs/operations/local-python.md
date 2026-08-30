# Local Python deployment (no Docker)

Knowledge Fabric is designed to run directly from Python on Windows, macOS, or Linux.

## One step

Windows PowerShell:

```powershell
python .\local_install.py
.\.venv\Scripts\Activate.ps1
python .\run_local.py
```

macOS/Linux:

```bash
python3 local_install.py
source .venv/bin/activate
python run_local.py
```

Open `http://127.0.0.1:5050`.

The installer creates an isolated virtual environment and installs the package in editable mode. Docker is not required.
