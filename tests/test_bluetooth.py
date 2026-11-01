import asyncio
import unittest
from unittest import mock

from meshcore import EventType

from bluetooth import NOME_DESCONHECIDO, SERVICO_SERIAL, filtrar_radios
from radio import Radio, RadioErro, endereco_bluetooth


class Filtro(unittest.TestCase):
    def test_deixa_so_radios_e_ordena_pelo_sinal(self):
        achados = [
            ("A", "MeshCore-Longe", -90, []),
            ("B", "Fone de ouvido", -30, ["0000110b-0000-1000-8000-00805f9b34fb"]),
            ("C", None, -20, []),
            ("D", "MeshCore-Perto", -50, []),
        ]
        self.assertEqual([r["endereco"] for r in filtrar_radios(achados)], ["D", "A"])

    def test_radio_sem_nome_e_reconhecido_pelo_servico(self):
        achados = [("E", None, -40, [SERVICO_SERIAL.upper()])]
        self.assertEqual(filtrar_radios(achados), [{"endereco": "E", "nome": NOME_DESCONHECIDO, "rssi": -40}])


class Destino(unittest.TestCase):
    def test_endereco(self):
        self.assertEqual(endereco_bluetooth("ble:44:1B:F6:91:2D:75"), "44:1B:F6:91:2D:75")
        self.assertIsNone(endereco_bluetooth("COM9"))
        self.assertIsNone(endereco_bluetooth("/dev/ttyACM0"))


class Conexao(unittest.TestCase):
    def setUp(self):
        pausa = mock.patch("radio.PAUSA_TENTATIVAS_BLUETOOTH_S", 0)
        pausa.start()
        self.addCleanup(pausa.stop)

    def rodar(self, radio, **falso):
        async def conectar():
            with mock.patch("radio.MeshCore") as meshcore:
                meshcore.create_ble = mock.AsyncMock(**falso)
                self.criar = meshcore.create_ble
                await radio.conectar("ble:AA:BB")

        asyncio.run(conectar())

    def test_falha_nao_guarda_o_destino_e_explica_o_pareamento(self):
        for falso in ({"return_value": None}, {"side_effect": OSError("falhou")}):
            radio = Radio()
            with self.assertRaises(RadioErro) as erro:
                self.rodar(radio, **falso)
            self.assertEqual(self.criar.await_count, 3)
            self.assertIsNone(radio.porta)
            self.assertIn("pareado", str(erro.exception))
            self.assertEqual(radio.erro, str(erro.exception))

    def test_falha_passageira_conecta_na_tentativa_seguinte(self):
        radio = Radio()
        falso = mock.MagicMock(is_connected=True)
        contatos = mock.MagicMock(payload={"c": {}})
        contatos.type = None
        falso.commands.get_contacts = mock.AsyncMock(return_value=contatos)
        self.rodar(radio, side_effect=[OSError("Insufficient Authentication"), falso])
        self.assertEqual(self.criar.await_count, 2)
        self.assertEqual(radio.porta, "ble:AA:BB")
        self.assertIsNone(radio.erro)
        self.assertTrue(radio.conectado)

    def test_falha_ao_ler_contatos_fecha_a_conexao(self):
        radio = Radio()
        falso = mock.MagicMock(is_connected=True, disconnect=mock.AsyncMock())
        falso.commands.get_contacts = mock.AsyncMock(
            return_value=mock.MagicMock(type=EventType.ERROR, payload={"reason": "sem resposta"})
        )
        with self.assertRaises(RadioErro):
            self.rodar(radio, return_value=falso)
        falso.disconnect.assert_awaited_once()
        self.assertIsNone(radio.mc)
        self.assertIsNone(radio.porta)
        self.assertFalse(radio.conectado)
        self.assertIn("contatos", radio.erro)

    def test_nome_informado_pelo_radio(self):
        radio = Radio()
        self.assertIsNone(radio.nome_informado())
        radio.mc = mock.MagicMock(self_info={"name": "1D1CCA98"})
        self.assertEqual(radio.nome_informado(), "MeshCore-1D1CCA98")
        radio.mc = mock.MagicMock(self_info={})
        self.assertIsNone(radio.nome_informado())


if __name__ == "__main__":
    unittest.main()
