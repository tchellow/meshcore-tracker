"""Conexao com o companion, por USB ou Bluetooth. Um unico comando usa o radio por vez."""

import asyncio
import logging
import sys
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
# Nos outros sistemas, o pareamento continua sendo feito nas configuracoes.
PAREIA_NO_PROGRAMA = sys.platform == "win32"
ESPERA_PAREAMENTO_S = 30
TENTATIVAS_PAREAMENTO = 8
PAUSA_TENTATIVAS_PAREAMENTO_S = 2
PAREAMENTO_NAO_ATENDIDO = "O rádio não atendeu ao pareamento. Confira se está ligado, perto e sem outro aparelho conectado a ele."
ERRO_FIRMWARE_USB = (
    "Não foi possível conectar pela USB. Verifique se o rádio está com o firmware Companion USB: "
    "com firmware Bluetooth ou Wi-Fi, ele não responde pelo cabo. Confira também se outro programa está usando a porta."
)
SILENCIO_CONTATOS_S = 10
LIMITE_LEITURA_CONTATOS_S = 180
ERRO_LEITURA_CONTATOS = "O rádio parou de enviar a lista de contatos. Confira o sinal e tente conectar de novo."


class RadioErro(Exception):
    pass


class PinNecessario(RadioErro):
    pass


class PareamentoFalhou(RadioErro):
    pass


class ConexaoBluetooth(BLEConnection):
    """A biblioteca esquece o cliente quando detecta uma queda e, marcada como desconectada,
    nao o fecha mais. Mas o Windows mantem o enlace enquanto o cliente nao for fechado:
    o radio para de anunciar e nenhuma nova conexao funciona ate o programa terminar."""

    def __init__(self, address):
        self.ultimo_cliente = None
        super().__init__(address=address)

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, valor):
        self._client = valor
        if valor is not None:
            self.ultimo_cliente = valor

    async def soltar(self):
        if self.ultimo_cliente is not None:
            await self.ultimo_cliente.disconnect()


def endereco_bluetooth(destino):
    """Retorna o endereco se o destino for Bluetooth, ou None se for uma porta USB."""
    return destino[len(PREFIXO_BLUETOOTH):] if destino.startswith(PREFIXO_BLUETOOTH) else None


async def _dispositivo_windows(endereco):
    from winrt.windows.devices.bluetooth import BluetoothLEDevice

    return await BluetoothLEDevice.from_bluetooth_address_async(int(endereco.replace(":", ""), 16))


async def precisa_parear(endereco):
    """Na duvida responde que nao: a conexao tenta e explica a falha."""
    if not PAREIA_NO_PROGRAMA:
        return False
    try:
        dispositivo = await _dispositivo_windows(endereco)
        if dispositivo is None:
            return False
        try:
            return not dispositivo.device_information.pairing.is_paired
        finally:
            dispositivo.close()
    except Exception as falha:
        logger.warning("Nao foi possivel consultar o pareamento: %r", falha)
        return False


async def _tentar_parear(endereco, pin):
    """Retorna se pareou e se o Windows chegou a pedir o PIN."""
    from winrt.windows.devices.enumeration import DevicePairingKinds, DevicePairingResultStatus

    pediu_pin = False

    def pedido(_, args):
        nonlocal pediu_pin
        pediu_pin = True
        if args.pairing_kind == DevicePairingKinds.PROVIDE_PIN:
            args.accept(pin)
        else:
            args.accept()

    dispositivo = await _dispositivo_windows(endereco)
    if dispositivo is None:
        raise PareamentoFalhou(PAREAMENTO_NAO_ATENDIDO)
    try:
        personalizado = dispositivo.device_information.pairing.custom
        token = personalizado.add_pairing_requested(pedido)
        tipos = DevicePairingKinds.PROVIDE_PIN | DevicePairingKinds.CONFIRM_ONLY | DevicePairingKinds.CONFIRM_PIN_MATCH
        try:
            resultado = await asyncio.wait_for(personalizado.pair_async(tipos), ESPERA_PAREAMENTO_S)
        except asyncio.TimeoutError:
            # O Windows pode concluir o pareamento sem avisar: vale o estado real.
            if await precisa_parear(endereco):
                raise PareamentoFalhou(PAREAMENTO_NAO_ATENDIDO) from None
            return True, pediu_pin
        finally:
            personalizado.remove_pairing_requested(token)
    finally:
        dispositivo.close()
    pareou = resultado.status in (DevicePairingResultStatus.PAIRED, DevicePairingResultStatus.ALREADY_PAIRED)
    if not pareou:
        logger.warning("Pareamento: %s, pediu o PIN: %s", DevicePairingResultStatus(resultado.status).name, pediu_pin)
    return pareou, pediu_pin


async def parear(endereco, pin):
    """Pareia com o PIN informado, que nao e guardado nem registrado.

    O Windows as vezes recusa na hora, sem pedir o PIN, e aceita logo depois. Se pediu o PIN
    e nao pareou, o PIN foi recusado: repetir nao ajuda.
    """
    for tentativa in range(1, TENTATIVAS_PAREAMENTO + 1):
        pareou, pediu_pin = await _tentar_parear(endereco, pin)
        if pareou:
            return
        if pediu_pin:
            raise PareamentoFalhou("O rádio recusou o pareamento. Confira o PIN.")
        if tentativa < TENTATIVAS_PAREAMENTO:
            await asyncio.sleep(PAUSA_TENTATIVAS_PAREAMENTO_S)
    raise PareamentoFalhou(PAREAMENTO_NAO_ATENDIDO)


class Radio:
    def __init__(self):
        self.mc = None
        self._conexao_bluetooth = None
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

    async def conectar(self, destino, pin=None):
        """O destino e uma porta USB ou PREFIXO_BLUETOOTH mais o endereco do radio.

        Um radio Bluetooth sem pareamento levanta PinNecessario, a menos que venha o PIN.
        """
        async with self._trava:
            await self._fechar()
            endereco = endereco_bluetooth(destino)
            try:
                if endereco and await precisa_parear(endereco):
                    if pin is None:
                        raise PinNecessario("O rádio não está pareado neste computador. Clique em Desconectar e depois em Conectar para informar o PIN.")
                    await parear(endereco, pin)
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
        except Exception as falha:
            # A biblioteca reabre a porta quando o node nao responde, e essa
            # reabertura tambem da "Acesso negado". O pyserial embrulha o erro em outra excecao.
            if isinstance(falha, PermissionError) or "PermissionError" in str(falha):
                raise RadioErro(ERRO_FIRMWARE_USB) from None
            raise RadioErro(f"Não foi possível abrir {porta}: {falha}") from None
        if mc is None:
            raise RadioErro(ERRO_FIRMWARE_USB)
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
            conexao = ConexaoBluetooth(address=endereco)
            mc = MeshCore(conexao)
            try:
                resposta = await asyncio.wait_for(mc.connect(), ESPERA_CONEXAO_BLUETOOTH_S)
                if resposta is not None:
                    self._conexao_bluetooth = conexao
                    return mc
                logger.warning("Bluetooth, tentativa %d: o radio nao respondeu", tentativa)
            except Exception as falha:
                logger.warning("Bluetooth, tentativa %d: %r", tentativa, falha)
            await self._soltar_bluetooth(mc, conexao)
            if tentativa < TENTATIVAS_BLUETOOTH:
                await asyncio.sleep(PAUSA_TENTATIVAS_BLUETOOTH_S)
        raise RadioErro(aviso)

    async def _soltar_bluetooth(self, mc, conexao):
        """Um passo com falha nao pode impedir o outro: o enlace aberto bloquearia o radio."""
        for passo in (mc.disconnect, conexao.soltar):
            try:
                await asyncio.wait_for(passo(), ESPERA_SOLTAR_BLUETOOTH_S)
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
        conexao, self._conexao_bluetooth = self._conexao_bluetooth, None
        if conexao is not None:
            await self._soltar_bluetooth(mc, conexao)
        elif mc is not None:
            await mc.disconnect()

    async def _ler_contatos(self):
        """Na biblioteca, o tempo limite vale para a lista inteira, que pode levar mais de um
        minuto por Bluetooth. Aqui, o que indica falha e o radio parar de enviar."""
        mc = self.mc
        ultimo = time.monotonic()

        def chegou(_):
            nonlocal ultimo
            ultimo = time.monotonic()

        assinatura = mc.subscribe(EventType.NEXT_CONTACT, chegou)
        leitura = asyncio.create_task(mc.commands.get_contacts(timeout=LIMITE_LEITURA_CONTATOS_S))
        try:
            while not leitura.done():
                await asyncio.wait({leitura}, timeout=SILENCIO_CONTATOS_S / 5)
                if not leitura.done() and time.monotonic() - ultimo > SILENCIO_CONTATOS_S:
                    raise RadioErro(ERRO_LEITURA_CONTATOS)
        finally:
            leitura.cancel()
            mc.unsubscribe(assinatura)
        resultado = leitura.result()
        if resultado.type == EventType.ERROR:
            logger.warning("Leitura dos contatos: %s", resultado.payload)
            raise RadioErro(ERRO_LEITURA_CONTATOS)
        self.contatos = dict(resultado.payload)
