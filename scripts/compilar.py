"""Compila o programa com o PyInstaller em dist/meshcore-tracker.

Uso: python scripts/compilar.py [opcoes extras do PyInstaller, como --distpath]
"""

import os
import sys
from pathlib import Path

import PyInstaller.__main__

RAIZ = Path(__file__).resolve().parent.parent


def main():
    os.chdir(RAIZ)
    argumentos = [
        str(RAIZ / "app.py"),
        "--name=meshcore-tracker",
        "--noconfirm",
        "--clean",
        "--windowed",
        f"--add-data={RAIZ / 'static'}{os.pathsep}static",
        "--collect-submodules=meshcore",
        "--collect-submodules=cayennelpp",
        "--collect-submodules=uvicorn",
        # O programa so usa USB. A biblioteca trata o Bluetooth como opcional.
        "--exclude-module=bleak",
    ]
    if sys.platform == "win32":
        argumentos.append(f"--icon={RAIZ / 'assets' / 'icone.ico'}")
    PyInstaller.__main__.run(argumentos + sys.argv[1:])


if __name__ == "__main__":
    main()
