"""Conexao com o companion, por USB ou Bluetooth. Um unico comando usa o radio por vez."""

import asyncio
import logging
import time

from meshcore import EventType, MeshCore
from meshcore.ble_cx import BLEConnection

logger = logging.getLogger("tracker")

TIPOS_CONTATO = {1: "companion", 2: "repeater", 3: "room", 4: "sensor"}
ESPERA_MAXIMA_S = 60
PREFIXO_BLUETOOTH = "ble:"
ESPERA_CONEXAO_BLUETOOTH_S = 20
TENTATIVAS_BLUETOOTH = 3
PAUSA_TENTATIVAS_BLUETOOTH_S = 3
ESPERA_SOLTAR_BLUETOOTH_S = 5


class RadioErro(Exception):
    pass


def endereco_bluetooth(destino):
    """Retorna o endereco se o destino for Bluetooth, ou None se for uma porta USB."""
    return destino[len(PREFIXO_BLUETOOTH):] if destino.startswith(PREFIXO_BLUETOOTH) else None


class Radio:
    def __init__(self):
        self.mc = None
        self.porta = None
        self.contatos = {}
        self.erro = None
        self._trava = asyncio.Lock()
        self._ultimo_estado = False
        self._estado_desde = time.time()

    @property
    def conectado(self):
        return self.mc is not None and self.mc.is_connected

    def estado_desde(self):
        """Momento da ultima mudanca entre conectado e desconectado."""
        if self.conectado != self._ultimo_estado:
            self._ultimo_estado = self.conectado
            self._estado_desde = time.time()
        return self._estado_desde

    def nome_informado(self):
        """Nome que o proprio radio informa ao conectar, no formato anunciado por Bluetooth."""
        nome = (self.mc.self_info or {}).get("name") if self.mc else None
        return f"MeshCore-{nome}" if nome else None

    async def conectar(self, destino):
        """O destino e uma porta USB ou PREFIXO_BLUETOOTH mais o endereco do radio."""
        async with self._trava:
            await self._fechar()
            endereco = endereco_bluetooth(destino)
            try:
                self.mc = await (self._abrir_bluetooth(endereco) if endereco else self._abrir_usb(destino))
                await self._ler_contatos()
            except RadioErro as falha:
                # Sem os contatos a conexao nao serve: nao fica aberta pela metade.
                await self._fechar()
                self.erro = str(falha)
                raise
            self.porta = destino
            self.erro = None

    async def _abrir_usb(self, porta):
        try:
            mc = await MeshCore.create_serial(porta, 115200)
        except PermissionError:
            # A biblioteca reabre a porta quando o node nao responde, e essa
            # reabertura tambem da "Acesso negado".
            raise RadioErro("Acesso negado: a porta está ocupada ou o rádio não tem o firmware Companion USB.") from None
        except Exception as falha:
            raise RadioErro(f"Não foi possível abrir {porta}: {falha}") from None
        if mc is None:
            raise RadioErro("O rádio não respondeu. Ele está com o firmware Companion USB?")
        return mc

    async def _abrir_bluetooth(self, endereco):
        aviso = (
            "Não foi possível conectar por Bluetooth. Confira se o rádio está ligado, com o firmware "
            "Companion Bluetooth, pareado neste computador e sem outro aparelho conectado a ele."
        )
        # Logo apos conectar, o enlace pode ainda nao estar criptografado, e a tentativa falha.
        for tentativa in range(1, TENTATIVAS_BLUETOOTH + 1):
            # Conectar pelo endereco faz o Bleak procurar o anuncio, de onde vem o tipo do endereco.
            # Sem esse tipo, o Windows pode nao reconhecer o pareamento.
            conexao = BLEConnection(address=endereco)
            mc = MeshCore(conexao)
            try:
                resposta = await asyncio.wait_for(mc.connect(), ESPERA_CONEXAO_BLUETOOTH_S)
                if resposta is not None:
                    return mc
                logger.warning("Bluetooth, tentativa %d: o radio nao respondeu", tentativa)
            except Exception as falha:
                logger.warning("Bluetooth, tentativa %d: %r", tentativa, falha)
            await self._soltar_bluetooth(mc, conexao)
            if tentativa < TENTATIVAS_BLUETOOTH:
                await asyncio.sleep(PAUSA_TENTATIVAS_BLUETOOTH_S)
        raise RadioErro(aviso)

    async def _soltar_bluetooth(self, mc, conexao):
        """A biblioteca so fecha o que marcou como conectado. Se a falha veio antes disso,
        o enlace ficaria aberto, o radio pararia de anunciar e as proximas tentativas falhariam."""
        try:
            await asyncio.wait_for(mc.disconnect(), ESPERA_SOLTAR_BLUETOOTH_S)
            if conexao.client is not None:
                await asyncio.wait_for(conexao.client.disconnect(), ESPERA_SOLTAR_BLUETOOTH_S)
        except Exception as falha:
            logger.warning("Bluetooth, ao soltar a conexao: %r", falha)

    async def desconectar(self):
        async with self._trava:
            self.porta = None
            self.erro = None
            await self._fechar()

    async def atualizar_contatos(self):
        async with self._trava:
            if not self.conectado:
                raise RadioErro("Radio desconectado.")
            await self._ler_contatos()

    async def sincronizar_contatos(self):
        """Busca so o que mudou no radio, como uma rota nova aprendida pelo firmware."""
        async with self._trava:
            if self.conectado and self.mc.contacts_dirty:
                await self.mc.ensure_contacts(follow=True)
                self.contatos = dict(self.mc.contacts)

    async def pedir_telemetria(self, chave, espera):
        """Retorna a lista LPP e os segundos ate a resposta; a lista e None se nao houve resposta.

        O radio pode sugerir mais tempo que `espera`, ate o limite de ESPERA_MAXIMA_S.
        """
        async with self._trava:
            if not self.conectado:
                raise RadioErro("Radio desconectado.")
            inicio = time.monotonic()
            pedido = self.mc.commands.req_telemetry_sync(self.contatos[chave], min_timeout=espera)
            try:
                lpp = await asyncio.wait_for(pedido, ESPERA_MAXIMA_S)
            except asyncio.TimeoutError:
                lpp = None
            return lpp, time.monotonic() - inicio

    def tem_rota(self, chave):
        return self.contatos.get(chave, {}).get("out_path_len", -1) >= 0

    async def apagar_rota(self, chave):
        """O proximo pedido sai por flood e pode descobrir um caminho novo."""
        async with self._trava:
            if not self.conectado:
                raise RadioErro("Radio desconectado.")
            resultado = await self.mc.commands.reset_path(chave)
            if resultado.type == EventType.ERROR:
                raise RadioErro(f"Erro ao apagar a rota: {resultado.payload}")
            self.contatos[chave]["out_path_len"] = -1
            self.contatos[chave]["out_path"] = ""

    async def _fechar(self):
        mc, self.mc = self.mc, None
        if mc is not None:
            await mc.disconnect()

    async def _ler_contatos(self):
        resultado = await self.mc.commands.get_contacts()
        if resultado.type == EventType.ERROR:
            raise RadioErro(f"Erro ao ler os contatos: {resultado.payload}")
        self.contatos = dict(resultado.payload)
