"""Janela propria do programa, usando o motor web do sistema."""

import sys
import threading
from pathlib import Path

TITULO = "Meshcore Tracker"
ARQUIVO_ICONE = "icone.ico" if sys.platform == "win32" else "icone-256.png"
ICONE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets" / ARQUIVO_ICONE


class Janela:
    def __init__(self, url, pasta_dados):
        self.url = url
        self.pasta_dados = pasta_dados
        self.janela = None

    def abrir(self):
        """Bloqueia ate a janela fechar. Falha se o sistema nao tiver o motor web."""
        import webview

        self.janela = webview.create_window(
            TITULO, self.url, width=1100, height=680, min_size=(800, 500), maximized=True, text_select=True
        )
        # Manter os dados da janela guarda em cache os mapas ja baixados.
        webview.start(
            gui="edgechromium" if sys.platform == "win32" else "gtk",
            private_mode=False,
            storage_path=str(self.pasta_dados / "janela"),
            icon=str(ICONE) if ICONE.exists() else None,
        )

    def mostrar(self):
        """Traz a janela para a frente. Retorna False se ela nao existir."""
        if self.janela is None:
            return False
        self.janela.restore()
        self.janela.on_top = True
        self.janela.on_top = False
        return True

    def fechar(self):
        # Da tempo de a resposta do pedido de saida chegar antes de fechar.
        if self.janela is not None:
            threading.Timer(0.2, self.janela.destroy).start()
