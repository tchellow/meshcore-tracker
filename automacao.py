"""Laco da automacao: pede telemetria dos contatos ativos, um de cada vez."""

import asyncio
import logging
import math
import time

from radio import ESPERA_MAXIMA_S, RadioErro

ESPERA_INICIAL_S = 30
ESPERA_MINIMA_S = 10
FATOR_RTT = 3
PESO_NOVA_MEDICAO = 0.3
FALHAS_PARA_APAGAR_ROTA = 2
PAUSA_ENTRE_PEDIDOS_S = 5
RECONEXAO_S = 15
RECUO_MAXIMO_S = 4 * 60 * 60

logger = logging.getLogger("tracker")


def extrair_posicao(lpp):
    """Retorna o primeiro GPS valido. Latitude e longitude zeradas indicam GPS sem fix."""
    for item in lpp:
        if item.get("type") == "gps":
            valor = item["value"]
            if valor["latitude"] or valor["longitude"]:
                return valor
    return None


def calcular_proximo(agora, intervalo_s, falhas):
    """Sem resposta, o intervalo dobra a cada falha para nao ocupar a malha a toa."""
    return agora + max(intervalo_s, min(intervalo_s * 2 ** min(falhas, 10), RECUO_MAXIMO_S))


def calcular_espera(rtt_medio):
    """Sem medicao recente usa a espera inicial. Toda falha descarta a media, por isso um
    contato que ficou lento volta a ter tempo de responder e de ser medido de novo."""
    if rtt_medio is None:
        return ESPERA_INICIAL_S
    return min(max(FATOR_RTT * rtt_medio, ESPERA_MINIMA_S), ESPERA_MAXIMA_S)


def calcular_media(rtt_medio, rtt):
    if rtt_medio is None:
        return rtt
    return rtt_medio + PESO_NOVA_MEDICAO * (rtt - rtt_medio)


def intervalo_real(intervalo_s, rtt_medio):
    """O intervalo escolhido e um minimo: um contato lento e consultado com menos frequencia."""
    if rtt_medio is None:
        return intervalo_s
    return max(intervalo_s, math.ceil(FATOR_RTT * rtt_medio))


async def consultar(radio, banco, item):
    chave = item["chave"]
    agora = time.time()
    inicio = agora

    if chave not in radio.contatos:
        falhas = item["falhas"] + 1
        banco.registrar_tentativa(chave, "sem_contato", agora, calcular_proximo(agora, item["intervalo_s"], falhas), falhas)
        return

    lpp, rtt = await radio.pedir_telemetria(chave, calcular_espera(item["rtt_medio"]))

    # Se o cabo saiu durante o pedido, a culpa nao e do node: tenta de novo ao reconectar.
    if lpp is None and not radio.conectado:
        return

    agora = time.time()
    if lpp is None:
        falhas = item["falhas"] + 1
        banco.registrar_tentativa(chave, "sem_resposta", agora, calcular_proximo(agora, item["intervalo_s"], falhas), falhas)
        banco.descartar_media(chave)
        # Uma falha pode ser so um pacote perdido. Duas seguidas indicam rota quebrada.
        if falhas >= FALHAS_PARA_APAGAR_ROTA and radio.tem_rota(chave):
            await radio.apagar_rota(chave)
            logger.info("Rota de %s apagada apos %d falhas", item["nome"], falhas)
        return

    media = calcular_media(item["rtt_medio"], rtt)
    banco.registrar_medicao(chave, rtt, media)
    banco.registrar_resposta(chave, lpp, agora)
    posicao = extrair_posicao(lpp)
    if posicao:
        banco.registrar_posicao(chave, posicao, agora)
    status = "ok" if posicao else "sem_gps"
    proximo = max(inicio + intervalo_real(item["intervalo_s"], media), agora)
    banco.registrar_tentativa(chave, status, agora, proximo, 0)


async def rodar(radio, banco):
    proxima_reconexao = 0
    while True:
        await asyncio.sleep(1)
        radio.estado_desde()
        try:
            if not radio.conectado:
                if radio.porta and time.time() >= proxima_reconexao:
                    proxima_reconexao = time.time() + RECONEXAO_S
                    await radio.conectar(radio.porta)
                continue

            await radio.sincronizar_contatos()
            item = banco.proximo_pendente(time.time())
            if item:
                await consultar(radio, banco, item)
                await asyncio.sleep(PAUSA_ENTRE_PEDIDOS_S)
        except RadioErro as erro:
            logger.warning("%s", erro)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha na automacao")
            await asyncio.sleep(RECONEXAO_S)
