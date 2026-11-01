"""Compila o programa para Windows com o PyInstaller em dist/meshcore-tracker.

O pacote do Ubuntu nao usa este script: ele roda no Python e no WebKit do sistema.

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
        f"--add-data={RAIZ / 'assets' / 'icone.ico'}{os.pathsep}assets",
        "--collect-submodules=meshcore",
        "--collect-submodules=cayennelpp",
        "--collect-submodules=uvicorn",
        "--collect-submodules=bleak",
        "--collect-submodules=winrt",
    ]
    argumentos.append(f"--icon={RAIZ / 'assets' / 'icone.ico'}")
    PyInstaller.__main__.run(argumentos + sys.argv[1:])


if __name__ == "__main__":
    main()
