"""Teste de bancada: conecta no companion USB e pede telemetria de um contato.

Uso:
  python teste_telemetria.py                                 lista as portas
  python teste_telemetria.py --porta COM5                    lista os contatos
  python teste_telemetria.py --porta COM5 --contato "Nome"   pede a telemetria
"""

import argparse
import asyncio
import json
import sys

from meshcore import EventType, MeshCore
from serial.tools import list_ports

TIPOS_CONTATO = {1: "companion", 2: "repeater", 3: "room", 4: "sensor"}


def listar_portas():
    portas = list(list_ports.comports())
    if not portas:
        print("Nenhuma porta serial encontrada. O node esta ligado na USB?")
    for porta in portas:
        print(f"{porta.device}  {porta.description}")


def extrair_posicao(lpp):
    """Retorna o primeiro GPS da telemetria, ou None se nao houver."""
    for item in lpp:
        if item.get("type") == "gps":
            return item["value"]
    return None


def achar_contato(contatos, nome):
    """Procura pelo nome exato; se nao achar, por parte do nome."""
    nome = nome.casefold()
    exatos = [c for c in contatos if c.get("adv_name", "").casefold() == nome]
    return exatos or [c for c in contatos if nome in c.get("adv_name", "").casefold()]


def imprimir_contatos(contatos):
    print(f"{len(contatos)} contato(s):")
    for c in contatos:
        tipo = TIPOS_CONTATO.get(c.get("type"), f"tipo {c.get('type')}")
        print(f"  {c.get('adv_name', '?')}  [{tipo}]  {c.get('public_key', '')[:12]}")


def imprimir_telemetria(lpp):
    if lpp is None:
        print("SEM RESPOSTA: o node nao respondeu dentro do tempo limite.")
        return False

    print("Resposta recebida:")
    print(json.dumps(lpp, indent=2, ensure_ascii=False))

    posicao = extrair_posicao(lpp)
    if posicao is None:
        print("RESPONDEU SEM GPS: verifique a permissao de localizacao e o fix do GPS.")
        return False

    print(f"POSICAO: {posicao['latitude']}, {posicao['longitude']}"
          f"  altitude {posicao.get('altitude')} m")
    return True


async def executar(porta, nome, espera):
    mc = await MeshCore.create_serial(porta, 115200)
    if mc is None:
        print("O node nao respondeu. Ele esta com o firmware Companion USB?")
        return 1
    try:
        resultado = await mc.commands.get_contacts()
        if resultado.type == EventType.ERROR:
            print(f"Erro ao ler os contatos: {resultado.payload}")
            return 1
        contatos = list(resultado.payload.values())

        if nome is None:
            imprimir_contatos(contatos)
            return 0

        encontrados = achar_contato(contatos, nome)
        if len(encontrados) != 1:
            print(f'{len(encontrados)} contatos correspondem a "{nome}".')
            imprimir_contatos(encontrados or contatos)
            return 1

        contato = encontrados[0]
        print(f"Pedindo telemetria de {contato['adv_name']} (ate {espera} s)...")
        lpp = await mc.commands.req_telemetry_sync(contato, min_timeout=espera)
        return 0 if imprimir_telemetria(lpp) else 1
    finally:
        await mc.disconnect()


def main():
    # Nomes de node costumam ter emoji, que o console do Windows nao aceita por padrao.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--porta", help="ex.: COM5 ou /dev/ttyUSB0")
    parser.add_argument("--contato", help="nome do contato")
    parser.add_argument("--espera", type=int, default=30, help="segundos de espera (padrao 30)")
    args = parser.parse_args()

    if args.porta is None:
        listar_portas()
        return 0

    try:
        return asyncio.run(executar(args.porta, args.contato, args.espera))
    except PermissionError as erro:
        # A biblioteca reabre a porta quando o node nao responde, e essa reabertura
        # tambem da "Acesso negado". Nao significa necessariamente porta ocupada.
        print(f"Acesso negado em {args.porta}: {erro}")
        print("A porta pode estar ocupada, ou o node nao tem o firmware Companion USB.")
        return 1
    except Exception as erro:
        print(f"Falha ao usar a porta {args.porta}: {erro}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
