"""Meshcore Tracker: telemetria periodica de contatos MeshCore, com mapa."""

import argparse
import asyncio
import contextlib
import json
import logging
import logging.handlers
import re
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
from bluetooth import NOME_DESCONHECIDO, procurar_radios
from janela import Janela
from portas import listar_portas
from radio import PAREIA_NO_PROGRAMA, TIPOS_CONTATO, PareamentoFalhou, PinNecessario, Radio, RadioErro, endereco_bluetooth
from versao import VERSAO

logger = logging.getLogger("tracker")

EMPACOTADO = getattr(sys, "frozen", False)
PASTA_STATIC = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "static"
INTERVALO_PADRAO_S = 10 * 60


class ExigeJson(BaseHTTPMiddleware):
    """Impede que outros sites acionem o radio: formularios nao enviam JSON sem preflight."""

    async def dispatch(self, request, call_next):
        if request.method != "GET" and request.headers.get("content-type") != "application/json":
            return JSONResponse({"erro": "Envie application/json."}, status_code=415)
        return await call_next(request)


class SempreRevalidar(BaseHTTPMiddleware):
    """A janela guarda cache em disco: sem isto, uma atualizacao ainda mostraria a pagina antiga."""

    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta


def erro(mensagem, status=400):
    return JSONResponse({"erro": mensagem}, status_code=status)


def criar_app(banco, encerrar, mostrar_janela):
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
            "nome_radio": banco.config("nome_radio"),
            "erro": radio.erro,
            "estado_desde": radio.estado_desde(),
            "pareia_no_programa": PAREIA_NO_PROGRAMA,
            "intervalos": INTERVALOS_S,
            "rastreados": rastreados_com_rota(),
        })

    async def portas(request):
        return JSONResponse(listar_portas())

    def nomes_bluetooth():
        return json.loads(banco.config("nomes_bluetooth") or "{}")

    async def procurar_bluetooth(request):
        try:
            radios = await procurar_radios()
        except RadioErro as falha:
            return erro(str(falha))
        # Alguns radios anunciam sem nome: usa o nome informado na ultima conexao.
        nomes = nomes_bluetooth()
        for item in radios:
            if item["nome"] == NOME_DESCONHECIDO:
                item["nome"] = nomes.get(item["endereco"], NOME_DESCONHECIDO)
        return JSONResponse(radios)

    async def conectar(request):
        dados = await corpo(request)
        porta = dados.get("porta")
        if not porta or not isinstance(porta, str):
            return erro("Escolha uma porta ou um rádio.")
        nome = dados.get("nome")
        pin = dados.get("pin")
        if pin is not None and not (isinstance(pin, str) and re.fullmatch("[0-9]{6}", pin)):
            return erro("O PIN tem 6 números.")
        try:
            await radio.conectar(porta, pin)
        except PinNecessario:
            # A tela vai pedir o PIN: ainda nao e um erro.
            radio.erro = None
            return JSONResponse({"precisa_pin": True})
        except PareamentoFalhou as falha:
            return JSONResponse({"erro": str(falha), "pareamento": True}, status_code=400)
        except RadioErro as falha:
            return erro(str(falha))
        endereco = endereco_bluetooth(porta)
        if endereco:
            nome = radio.nome_informado() or nome
            if nome and nome != NOME_DESCONHECIDO:
                banco.salvar_config("nomes_bluetooth", json.dumps({**nomes_bluetooth(), endereco: nome}, ensure_ascii=False))
        banco.salvar_config("porta", porta)
        banco.salvar_config("nome_radio", nome if isinstance(nome, str) else None)
        return JSONResponse({"ok": True})

    async def desconectar(request):
        await radio.desconectar()
        banco.salvar_config("porta", None)
        banco.salvar_config("nome_radio", None)
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

    async def mostrar(request):
        return JSONResponse({"janela": mostrar_janela()})

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
            Route("/api/bluetooth/procurar", procurar_bluetooth, methods=["POST"]),
            Route("/api/conectar", conectar, methods=["POST"]),
            Route("/api/desconectar", desconectar, methods=["POST"]),
            Route("/api/contatos", contatos),
            Route("/api/contatos/atualizar", atualizar_contatos, methods=["POST"]),
            Route("/api/rastreados", adicionar, methods=["POST"]),
            Route("/api/rastreados/{chave}", alterar, methods=["PATCH"]),
            Route("/api/rastreados/{chave}", remover, methods=["DELETE"]),
            Route("/api/rastreados/{chave}/pedir", pedir_agora, methods=["POST"]),
            Route("/api/encerrar", sair, methods=["POST"]),
            Route("/api/mostrar", mostrar, methods=["POST"]),
            Mount("/static", StaticFiles(directory=PASTA_STATIC)),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]),
            Middleware(ExigeJson),
            Middleware(SempreRevalidar),
        ],
        lifespan=ciclo,
    )


def configurar_logs(pasta, em_arquivo):
    """Instalado, o programa nao tem terminal: os registros vao para um arquivo."""
    formato = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if em_arquivo:
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


def mostrar_o_que_esta_aberto(url):
    """Pede para a copia aberta mostrar a janela. Sem janela, ela esta usando o navegador."""
    pedido = urllib.request.Request(
        f"{url}/api/mostrar", data=b"{}", method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            if json.load(resposta)["janela"]:
                return
    except (OSError, ValueError, KeyError):
        logger.exception("A copia aberta nao respondeu")
    webbrowser.open(url)


def rodar_com_interface(servidor, url, pasta, usar_janela):
    """O servidor roda em segundo plano, e a interface fica na linha principal."""
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    while not servidor.started:
        if not linha.is_alive():
            logger.error("Nao foi possivel iniciar o servidor em %s", url)
            return 1
        time.sleep(0.05)

    if usar_janela is not None:
        try:
            usar_janela.abrir()
        except Exception:
            # Sem o motor web do sistema, o navegador ainda atende.
            logger.exception("Nao foi possivel abrir a janela; usando o navegador")
            usar_janela.janela = None
        else:
            servidor.should_exit = True
            linha.join(timeout=10)
            return 0

    webbrowser.open(url)
    try:
        while linha.is_alive():
            linha.join(timeout=1)
    except KeyboardInterrupt:
        servidor.should_exit = True
        linha.join(timeout=10)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta-web", type=int, default=8790)
    parser.add_argument("--dados", type=Path, default=None, help="pasta do banco de dados")
    parser.add_argument("--navegador", action="store_true", help="usa o navegador em vez da janela")
    parser.add_argument("--sem-navegador", action="store_true", help="roda sem nenhuma interface")
    parser.add_argument("--registro-em-arquivo", action="store_true")
    args = parser.parse_args()

    pasta = args.dados or pasta_dados()
    configurar_logs(pasta, EMPACOTADO or args.registro_em_arquivo)

    url = f"http://127.0.0.1:{args.porta_web}"

    # Abrir o programa de novo so mostra o que ja esta rodando.
    if ja_esta_aberto(url):
        if not args.sem_navegador:
            mostrar_o_que_esta_aberto(url)
        return 0

    print(f"Meshcore Tracker {VERSAO} em {url}", flush=True)

    janela = None if args.navegador or args.sem_navegador else Janela(url, pasta)
    servidor = None

    def encerrar():
        servidor.should_exit = True
        if janela is not None:
            janela.fechar()

    def mostrar_janela():
        return janela is not None and janela.mostrar()

    app = criar_app(Banco(pasta), encerrar, mostrar_janela)
    # log_config=None evita o formatador do uvicorn, que falha sem terminal.
    configuracao = uvicorn.Config(app, host="127.0.0.1", port=args.porta_web, log_config=None)
    servidor = uvicorn.Server(configuracao)

    if args.sem_navegador:
        servidor.run()
        return 0
    return rodar_com_interface(servidor, url, pasta, janela)


if __name__ == "__main__":
    sys.exit(main())
