"""Abre o programa compilado, confere que ele responde e o encerra pelo menu Sair.

Uso: python scripts/testar_binario.py caminho/do/executavel
Nao abre nenhuma porta serial nem transmite nada.
"""

import json
import subprocess
import sys
import tempfile
import time
import urllib.request

PORTA = 8795
BASE = f"http://127.0.0.1:{PORTA}"


def chamar(caminho, metodo="GET"):
    dados = None if metodo == "GET" else b"{}"
    cabecalhos = {} if metodo == "GET" else {"Content-Type": "application/json"}
    pedido = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers=cabecalhos)
    with urllib.request.urlopen(pedido, timeout=5) as resposta:
        return resposta.read()


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        processo = subprocess.Popen(
            [sys.argv[1], "--sem-navegador", "--porta-web", str(PORTA), "--dados", pasta]
        )
        try:
            for _ in range(120):
                try:
                    estado = json.loads(chamar("/api/estado"))
                    break
                except OSError:
                    if processo.poll() is not None:
                        raise SystemExit(f"O programa fechou com o codigo {processo.returncode}.")
                    time.sleep(0.5)
            else:
                raise SystemExit("O programa nao respondeu.")

            print("versao:", estado["versao"])
            pagina = chamar("/").decode("utf-8")
            assert "Meshcore Tracker" in pagina, "pagina inicial incorreta"
            assert chamar("/static/icone.svg").startswith(b"<svg"), "icone ausente"
            print("portas:", json.loads(chamar("/api/portas")))

            chamar("/api/encerrar", "POST")
            codigo = processo.wait(timeout=20)
            assert codigo == 0, f"encerrou com o codigo {codigo}"
            print("OK")
        finally:
            if processo.poll() is None:
                processo.kill()


if __name__ == "__main__":
    main()
