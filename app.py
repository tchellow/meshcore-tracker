"""Meshcore Tracker: telemetria periodica de contatos MeshCore, com mapa."""

import argparse
import asyncio
import contextlib
import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import automacao
from banco import INTERVALOS_S, Banco, pasta_dados
from portas import listar_portas
from radio import TIPOS_CONTATO, Radio, RadioErro
from versao import VERSAO

EMPACOTADO = getattr(sys, "frozen", False)
PASTA_STATIC = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "static"
INTERVALO_PADRAO_S = 10 * 60


class ExigeJson(BaseHTTPMiddleware):
    """Impede que outros sites acionem o radio: formularios nao enviam JSON sem preflight."""

    async def dispatch(self, request, call_next):
        if request.method != "GET" and request.headers.get("content-type") != "application/json":
            return JSONResponse({"erro": "Envie application/json."}, status_code=415)
        return await call_next(request)


def erro(mensagem, status=400):
    return JSONResponse({"erro": mensagem}, status_code=status)


def criar_app(banco, encerrar):
    radio = Radio()

    async def corpo(request):
        with contextlib.suppress(ValueError):
            dados = await request.json()
            if isinstance(dados, dict):
                return dados
        return {}

    async def pagina(request):
        return FileResponse(PASTA_STATIC / "index.html")

    def rastreados_com_rota():
        itens = banco.rastreados()
        for item in itens:
            contato = radio.contatos.get(item["chave"], {})
            item["hops"] = contato.get("out_path_len")
            item["intervalo_real_s"] = automacao.intervalo_real(item["intervalo_s"], item["rtt_medio"])
        return itens

    async def estado(request):
        return JSONResponse({
            "versao": VERSAO,
            "conectado": radio.conectado,
            "porta": radio.porta,
            "erro": radio.erro,
            "estado_desde": radio.estado_desde(),
            "intervalos": INTERVALOS_S,
            "rastreados": rastreados_com_rota(),
        })

    async def portas(request):
        return JSONResponse(listar_portas())

    async def conectar(request):
        porta = (await corpo(request)).get("porta")
        if not porta or not isinstance(porta, str):
            return erro("Escolha uma porta.")
        try:
            await radio.conectar(porta)
        except RadioErro as falha:
            return erro(str(falha))
        banco.salvar_config("porta", porta)
        return JSONResponse({"ok": True})

    async def desconectar(request):
        await radio.desconectar()
        banco.salvar_config("porta", None)
        return JSONResponse({"ok": True})

    async def contatos(request):
        return JSONResponse([
            {
                "chave": chave,
                "nome": contato.get("adv_name") or chave[:12],
                "tipo": TIPOS_CONTATO.get(contato.get("type"), "outro"),
            }
            for chave, contato in radio.contatos.items()
        ])

    async def atualizar_contatos(request):
        try:
            await radio.atualizar_contatos()
        except RadioErro as falha:
            return erro(str(falha))
        return JSONResponse({"ok": True})

    async def adicionar(request):
        dados = await corpo(request)
        contato = radio.contatos.get(dados.get("chave"))
        if contato is None:
            return erro("Contato nao encontrado no radio.")
        chave = dados["chave"]
        banco.adicionar(chave, contato.get("adv_name") or chave[:12], INTERVALO_PADRAO_S)
        return JSONResponse({"ok": True})

    async def alterar(request):
        dados = await corpo(request)
        ativo = dados.get("ativo")
        if ativo is not None and not isinstance(ativo, bool):
            return erro("Valor invalido para ativo.")
        intervalo = dados.get("intervalo_s")
        if intervalo is not None and intervalo not in INTERVALOS_S:
            return erro("Escolha um intervalo da lista.")
        banco.alterar(request.path_params["chave"], ativo, intervalo)
        return JSONResponse({"ok": True})

    async def remover(request):
        banco.remover(request.path_params["chave"])
        return JSONResponse({"ok": True})

    async def pedir_agora(request):
        banco.pedir_agora(request.path_params["chave"])
        return JSONResponse({"ok": True})

    async def sair(request):
        encerrar()
        return JSONResponse({"ok": True})

    @contextlib.asynccontextmanager
    async def ciclo(app):
        # Volta a usar a ultima porta escolhida, para continuar sozinho apos reiniciar.
        radio.porta = banco.config("porta")
        tarefa = asyncio.create_task(automacao.rodar(radio, banco))
        yield
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa
        await radio.desconectar()

    return Starlette(
        routes=[
            Route("/", pagina),
            Route("/api/estado", estado),
            Route("/api/portas", portas),
            Route("/api/conectar", conectar, methods=["POST"]),
            Route("/api/desconectar", desconectar, methods=["POST"]),
            Route("/api/contatos", contatos),
            Route("/api/contatos/atualizar", atualizar_contatos, methods=["POST"]),
            Route("/api/rastreados", adicionar, methods=["POST"]),
            Route("/api/rastreados/{chave}", alterar, methods=["PATCH"]),
            Route("/api/rastreados/{chave}", remover, methods=["DELETE"]),
            Route("/api/rastreados/{chave}/pedir", pedir_agora, methods=["POST"]),
            Route("/api/encerrar", sair, methods=["POST"]),
            Mount("/static", StaticFiles(directory=PASTA_STATIC)),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]),
            Middleware(ExigeJson),
        ],
        lifespan=ciclo,
    )


def configurar_logs(pasta):
    """Empacotado, o programa nao tem terminal: os registros vao para um arquivo."""
    formato = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if EMPACOTADO:
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = logging.handlers.RotatingFileHandler(
            pasta / "tracker.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8"
        )
        logging.basicConfig(level=logging.INFO, format=formato, handlers=[arquivo])
    else:
        logging.basicConfig(level=logging.INFO, format=formato)
    logging.getLogger("meshcore").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)


def ja_esta_aberto(url):
    try:
        with urllib.request.urlopen(f"{url}/api/estado", timeout=2) as resposta:
            return "versao" in json.load(resposta)
    except (OSError, ValueError):
        return False


def abrir_navegador(url):
    # O empacotador do Linux altera LD_LIBRARY_PATH, o que pode impedir o navegador de abrir.
    if EMPACOTADO and sys.platform.startswith("linux"):
        original = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = original
    webbrowser.open(url)


def abrir_quando_pronto(url, porta):
    for _ in range(100):
        with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", porta), timeout=1):
            abrir_navegador(url)
            return
        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta-web", type=int, default=8790)
    parser.add_argument("--dados", type=Path, default=None, help="pasta do banco de dados")
    parser.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args()

    pasta = args.dados or pasta_dados()
    configurar_logs(pasta)

    url = f"http://127.0.0.1:{args.porta_web}"

    # Abrir o programa de novo so mostra a janela do que ja esta rodando.
    if ja_esta_aberto(url):
        if not args.sem_navegador:
            abrir_navegador(url)
        return

    print(f"Meshcore Tracker {VERSAO} em {url} (use Sair no menu da engrenagem)", flush=True)
    if not args.sem_navegador:
        threading.Thread(target=abrir_quando_pronto, args=(url, args.porta_web), daemon=True).start()

    servidor = None

    def encerrar():
        servidor.should_exit = True

    app = criar_app(Banco(pasta), encerrar)
    # log_config=None evita o formatador do uvicorn, que falha sem terminal.
    configuracao = uvicorn.Config(app, host="127.0.0.1", port=args.porta_web, log_config=None)
    servidor = uvicorn.Server(configuracao)
    servidor.run()


if __name__ == "__main__":
    main()
