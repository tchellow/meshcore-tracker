"""Testa a janela do programa: abrir, abrir de novo, fechar a janela e sair pelo programa.

Uso: python scripts/testar_janela.py caminho/do/executavel [captura.png]
Precisa de uma area de trabalho. No Linux, tambem de wmctrl e, para a captura, ImageMagick.
Nao abre nenhuma porta serial nem transmite nada.
"""

import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PORTA = 8796
BASE = f"http://127.0.0.1:{PORTA}"
TITULO = "Meshcore Tracker"


def chamar(caminho, metodo="GET"):
    dados = None if metodo == "GET" else b"{}"
    cabecalhos = {} if metodo == "GET" else {"Content-Type": "application/json"}
    pedido = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers=cabecalhos)
    with urllib.request.urlopen(pedido, timeout=5) as resposta:
        return json.load(resposta)


def abrir(executavel, pasta):
    processo = subprocess.Popen([executavel, "--porta-web", str(PORTA), "--dados", pasta])
    for _ in range(120):
        try:
            chamar("/api/estado")
            return processo
        except OSError:
            if processo.poll() is not None:
                raise SystemExit(f"O programa fechou com o codigo {processo.returncode}.")
            time.sleep(0.5)
    processo.kill()
    raise SystemExit("O programa nao respondeu.")


def janela_existe():
    if sys.platform == "win32":
        comando = (
            f"@(Get-Process | Where-Object {{ $_.MainWindowTitle -eq '{TITULO}' }}).Count"
        )
        saida = subprocess.run(["powershell", "-NoProfile", "-Command", comando], capture_output=True, text=True)
        return saida.stdout.strip() not in ("", "0")
    saida = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True)
    return TITULO in saida.stdout


def fechar_janela():
    if sys.platform == "win32":
        comando = (
            f"Get-Process | Where-Object {{ $_.MainWindowTitle -eq '{TITULO}' }} "
            "| ForEach-Object { [void]$_.CloseMainWindow() }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", comando], check=True)
    else:
        subprocess.run(["wmctrl", "-c", TITULO], check=True)


def esperar(condicao, segundos, mensagem):
    fim = time.time() + segundos
    while time.time() < fim:
        if condicao():
            return
        time.sleep(0.5)
    raise SystemExit(mensagem)


def capturar(caminho):
    if sys.platform == "win32":
        comando = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$t=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$b=New-Object System.Drawing.Bitmap $t.Width,$t.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($b);"
            "$g.CopyFromScreen($t.Location,[System.Drawing.Point]::Empty,$t.Size);"
            f"$b.Save('{caminho}')"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", comando], check=False)
    else:
        subprocess.run(["import", "-window", "root", caminho], check=False)


def main():
    executavel = sys.argv[1]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        processo = abrir(executavel, pasta)
        try:
            esperar(janela_existe, 30, "A janela nao apareceu.")
            print("janela aberta")

            # Da tempo de a pagina e o mapa carregarem antes da captura.
            time.sleep(15)
            if len(sys.argv) > 2:
                capturar(sys.argv[2])

            segunda = subprocess.run([executavel, "--porta-web", str(PORTA), "--dados", pasta], timeout=30)
            assert segunda.returncode == 0, f"segunda copia: codigo {segunda.returncode}"
            assert processo.poll() is None, "a segunda copia encerrou a primeira"
            assert chamar("/api/mostrar", "POST")["janela"] is True, "a janela nao foi mostrada"
            print("abrir de novo: ok")

            fechar_janela()
            codigo = processo.wait(timeout=30)
            assert codigo == 0, f"fechar a janela: codigo {codigo}"
            try:
                chamar("/api/estado")
                raise SystemExit("O servidor continuou rodando depois de fechar a janela.")
            except OSError:
                pass
            print("fechar a janela encerrou o programa: ok")

            processo = abrir(executavel, pasta)
            esperar(janela_existe, 30, "A janela nao apareceu na segunda abertura.")
            chamar("/api/encerrar", "POST")
            codigo = processo.wait(timeout=30)
            assert codigo == 0, f"sair: codigo {codigo}"
            esperar(lambda: not janela_existe(), 15, "A janela ficou aberta depois de sair.")
            print("sair pelo programa fechou a janela: ok")
            print("OK")
        finally:
            if processo.poll() is None:
                processo.kill()


if __name__ == "__main__":
    main()
