"""Zero-Docker local installer/launcher for Knowledge Fabric."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VENV=ROOT/".venv"

def main():
    if not VENV.exists():
        subprocess.check_call([sys.executable,"-m","venv",str(VENV)])
    py=VENV/"Scripts"/"python.exe" if os.name=="nt" else VENV/"bin"/"python"
    pip=[str(py),"-m","pip"]
    subprocess.check_call(pip+["install","--upgrade","pip"])
    subprocess.check_call(pip+["install","-e","."])
    print("Knowledge Fabric installed in .venv")
    print("Start with: kf start")
if __name__=="__main__": main()
