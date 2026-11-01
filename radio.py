"""Conexao USB com o companion. Um unico comando usa o radio por vez."""

import asyncio
import time

from meshcore import EventType, MeshCore

TIPOS_CONTATO = {1: "companion", 2: "repeater", 3: "room", 4: "sensor"}
ESPERA_MAXIMA_S = 60


class RadioErro(Exception):
    pass


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

    async def conectar(self, porta):
        async with self._trava:
            await self._fechar()
            try:
                mc = await MeshCore.create_serial(porta, 115200)
            except PermissionError:
                # A biblioteca reabre a porta quando o node nao responde, e essa
                # reabertura tambem da "Acesso negado".
                self.erro = "Acesso negado: a porta esta ocupada ou o radio nao tem o firmware Companion USB."
                raise RadioErro(self.erro) from None
            except Exception as erro:
                self.erro = f"Nao foi possivel abrir {porta}: {erro}"
                raise RadioErro(self.erro) from None
            if mc is None:
                self.erro = "O radio nao respondeu. Ele esta com o firmware Companion USB?"
                raise RadioErro(self.erro)
            self.mc = mc
            self.porta = porta
            self.erro = None
            await self._ler_contatos()

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
