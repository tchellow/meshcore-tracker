"""Gera os icones PNG e ICO a partir de um PNG de 512 px renderizado de static/icone.svg.

Uso: python scripts/gerar_icones.py caminho/do/icone-512.png
Requer Pillow, que nao e dependencia do programa.
"""

import sys
from pathlib import Path

from PIL import Image

PASTA = Path(__file__).resolve().parent.parent / "assets"
TAMANHOS_ICO = [16, 24, 32, 48, 64, 128, 256]


def main():
    origem = Image.open(sys.argv[1]).convert("RGBA")
    PASTA.mkdir(exist_ok=True)
    origem.resize((256, 256), Image.LANCZOS).save(PASTA / "icone-256.png")
    origem.save(PASTA / "icone.ico", sizes=[(t, t) for t in TAMANHOS_ICO])


if __name__ == "__main__":
    main()
