"""Procura radios MeshCore que estejam anunciando por Bluetooth."""

import logging

from radio import RadioErro

PREFIXO_NOME = "MeshCore"
# Servico serial usado pelo firmware. Alguns radios o anunciam sem enviar o nome.
SERVICO_SERIAL = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NOME_DESCONHECIDO = "Rádio sem nome"
TEMPO_PROCURA_S = 8

logger = logging.getLogger("tracker")


def filtrar_radios(achados):
    """Recebe (endereco, nome, rssi, servicos) e deixa so os radios, com o sinal mais forte primeiro."""
    radios = []
    for endereco, nome, rssi, servicos in achados:
        com_nome = bool(nome) and nome.startswith(PREFIXO_NOME)
        com_servico = SERVICO_SERIAL in [servico.lower() for servico in servicos]
        if com_nome or com_servico:
            radios.append({"endereco": endereco, "nome": nome or NOME_DESCONHECIDO, "rssi": rssi})
    return sorted(radios, key=lambda radio: radio["rssi"], reverse=True)


async def procurar_radios():
    try:
        from bleak import BleakScanner

        achados = await BleakScanner.discover(timeout=TEMPO_PROCURA_S, return_adv=True)
    except Exception as falha:
        logger.warning("Falha ao procurar por Bluetooth: %s", falha)
        raise RadioErro("Não foi possível usar o Bluetooth. Ele está ligado neste computador?") from None
    return filtrar_radios(
        (dispositivo.address, anuncio.local_name or dispositivo.name, anuncio.rssi, anuncio.service_uuids)
        for dispositivo, anuncio in achados.values()
    )
