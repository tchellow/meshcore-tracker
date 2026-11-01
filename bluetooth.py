"""Procura radios MeshCore por Bluetooth: os que estao anunciando e os ja pareados no sistema."""

import logging
import sys

from radio import RadioErro

PREFIXO_NOME = "MeshCore"
# Servico serial usado pelo firmware. Alguns radios o anunciam sem enviar o nome.
SERVICO_SERIAL = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NOME_DESCONHECIDO = "Rádio sem nome"
TEMPO_PROCURA_S = 8

logger = logging.getLogger("tracker")


def filtrar_radios(achados):
    """Recebe (endereco, nome, rssi, servicos) e deixa so os radios."""
    radios = []
    for endereco, nome, rssi, servicos in achados:
        com_nome = bool(nome) and nome.startswith(PREFIXO_NOME)
        com_servico = SERVICO_SERIAL in [servico.lower() for servico in servicos]
        if com_nome or com_servico:
            radios.append({"endereco": endereco, "nome": nome or NOME_DESCONHECIDO, "rssi": rssi})
    return radios


def combinar_com_pareados(anunciados, pareados):
    """Um radio pareado pode nao anunciar, por exemplo se o sistema estiver conectado a ele.

    Fica na lista sem sinal (rssi None). O nome do pareamento vale para quem anuncia sem nome.
    """
    radios = {radio["endereco"]: dict(radio, pareado=False) for radio in anunciados}
    for endereco, nome in pareados.items():
        radio = radios.setdefault(endereco, {"endereco": endereco, "nome": nome, "rssi": None})
        radio["pareado"] = True
        if radio["nome"] == NOME_DESCONHECIDO:
            radio["nome"] = nome
    sem_sinal = -1000
    return sorted(radios.values(), key=lambda r: sem_sinal if r["rssi"] is None else r["rssi"], reverse=True)


def endereco_do_id_windows(identificador):
    """O id termina no endereco: BluetoothLE#BluetoothLEaa:bb:...-d7:32:33:fd:bb:ba"""
    return identificador.rsplit("-", 1)[-1].upper()


async def _pareados_windows():
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
    from winrt.windows.devices.enumeration import DeviceInformation

    seletor = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
    dispositivos = await DeviceInformation.find_all_async_aqs_filter(seletor)
    return {
        endereco_do_id_windows(dispositivo.id): dispositivo.name
        for dispositivo in dispositivos
        if dispositivo.name.startswith(PREFIXO_NOME)
    }


async def _pareados():
    if sys.platform != "win32":
        return {}
    try:
        return await _pareados_windows()
    except Exception as falha:
        # A lista de pareados so complementa a procura.
        logger.warning("Nao foi possivel listar os radios pareados: %r", falha)
        return {}


async def procurar_radios():
    try:
        from bleak import BleakScanner

        achados = await BleakScanner.discover(timeout=TEMPO_PROCURA_S, return_adv=True)
    except Exception as falha:
        logger.warning("Falha ao procurar por Bluetooth: %s", falha)
        raise RadioErro("Não foi possível usar o Bluetooth. Ele está ligado neste computador?") from None
    anunciados = filtrar_radios(
        (dispositivo.address, anuncio.local_name or dispositivo.name, anuncio.rssi, anuncio.service_uuids)
        for dispositivo, anuncio in achados.values()
    )
    return combinar_com_pareados(anunciados, await _pareados())
