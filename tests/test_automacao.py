import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from automacao import (
    calcular_espera,
    calcular_media,
    calcular_proximo,
    consultar,
    extrair_posicao,
    intervalo_real,
)
from banco import Banco

GPS = [{"type": "gps", "value": {"latitude": -23.1, "longitude": -46.8, "altitude": 700}}]


class RadioFalso:
    conectado = True

    def __init__(self, respostas, hops=2):
        self.respostas = list(respostas)
        self.contatos = {"a": {"out_path_len": hops}}
        self.esperas = []
        self.rotas_apagadas = 0

    async def pedir_telemetria(self, chave, espera):
        self.esperas.append(espera)
        return self.respostas.pop(0)

    def tem_rota(self, chave):
        return self.contatos[chave]["out_path_len"] >= 0

    async def apagar_rota(self, chave):
        self.rotas_apagadas += 1
        self.contatos[chave]["out_path_len"] = -1


class Calculos(unittest.TestCase):
    def test_espera(self):
        self.assertEqual(calcular_espera(None), 30)
        self.assertEqual(calcular_espera(2), 10)
        self.assertEqual(calcular_espera(8), 24)
        self.assertEqual(calcular_espera(15), 45)
        self.assertEqual(calcular_espera(30), 60)

    def test_intervalo_real(self):
        self.assertEqual(intervalo_real(15, None), 15)
        self.assertEqual(intervalo_real(15, 2), 15)
        self.assertEqual(intervalo_real(15, 8), 24)
        self.assertEqual(intervalo_real(15, 15), 45)
        self.assertEqual(intervalo_real(600, 15), 600)

    def test_media(self):
        self.assertEqual(calcular_media(None, 4), 4)
        self.assertAlmostEqual(calcular_media(2, 12), 5)

    def test_recuo(self):
        self.assertEqual([calcular_proximo(0, 15, f) for f in range(5)], [15, 30, 60, 120, 240])
        self.assertEqual(calcular_proximo(0, 18000, 3), 18000)
        self.assertEqual(calcular_proximo(0, 3600, 9), 14400)

    def test_posicao(self):
        zerada = [{"type": "gps", "value": {"latitude": 0.0, "longitude": 0.0, "altitude": 0}}]
        self.assertIsNone(extrair_posicao(zerada))
        self.assertIsNone(extrair_posicao([{"type": "voltage", "value": 4}]))
        self.assertEqual(extrair_posicao(GPS)["latitude"], -23.1)


class Consulta(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.pasta.cleanup)
        self.banco = Banco(Path(self.pasta.name))
        self.addCleanup(self.banco.con.close)
        self.banco.adicionar("a", "A", 15)

    def item(self):
        return self.banco.rastreados()[0]

    def consultar(self, radio, vezes=1):
        for _ in range(vezes):
            asyncio.run(consultar(radio, self.banco, self.item()))

    def test_sucesso_conta_do_inicio_do_pedido(self):
        radio = RadioFalso([(GPS, 2.0), (GPS, 2.0)])
        inicio = time.time()
        self.consultar(radio)
        item = self.item()
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["rtt_medio"], 2.0)
        self.assertLess(abs(item["proximo_em"] - inicio - 15), 1)
        self.consultar(radio)
        self.assertEqual(radio.esperas, [30, 10])

    def test_rota_lenta_aumenta_o_intervalo(self):
        radio = RadioFalso([(GPS, 15.0)])
        inicio = time.time()
        self.consultar(radio)
        self.assertLess(abs(self.item()["proximo_em"] - inicio - 45), 1)

    def test_falha_descarta_a_media_e_mede_de_novo(self):
        radio = RadioFalso([(GPS, 2.0), (None, 10.0), (GPS, 15.0)])
        self.consultar(radio, 2)
        item = self.item()
        self.assertEqual(item["status"], "sem_resposta")
        self.assertIsNone(item["rtt_medio"])
        self.assertEqual(radio.rotas_apagadas, 0)
        self.consultar(radio)
        self.assertEqual(radio.esperas, [30, 10, 30])
        self.assertEqual(self.item()["rtt_medio"], 15.0)
        self.assertEqual(self.item()["falhas"], 0)

    def test_duas_falhas_apagam_a_rota_uma_vez(self):
        radio = RadioFalso([(None, 30.0)] * 3)
        self.consultar(radio, 3)
        self.assertEqual(radio.rotas_apagadas, 1)
        self.assertEqual(self.item()["falhas"], 3)

    def test_sem_gps_conta_como_resposta(self):
        radio = RadioFalso([([{"type": "voltage", "value": 4}], 3.0)])
        self.consultar(radio)
        item = self.item()
        self.assertEqual(item["status"], "sem_gps")
        self.assertEqual(item["rtt_medio"], 3.0)
        self.assertEqual(item["falhas"], 0)
        self.assertEqual(radio.rotas_apagadas, 0)


if __name__ == "__main__":
    unittest.main()
