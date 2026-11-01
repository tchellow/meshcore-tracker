import asyncio
import unittest
from unittest import mock

from meshcore import EventType

from bluetooth import (
    NOME_DESCONHECIDO,
    SERVICO_SERIAL,
    combinar_com_pareados,
    endereco_do_id_windows,
    filtrar_radios,
)
from radio import Radio, RadioErro, endereco_bluetooth


class Filtro(unittest.TestCase):
    def test_deixa_so_radios_e_ordena_pelo_sinal(self):
        achados = [
            ("A", "MeshCore-Longe", -90, []),
            ("B", "Fone de ouvido", -30, ["0000110b-0000-1000-8000-00805f9b34fb"]),
            ("C", None, -20, []),
            ("D", "MeshCore-Perto", -50, []),
        ]
        self.assertEqual({r["endereco"] for r in filtrar_radios(achados)}, {"A", "D"})
        ordenados = combinar_com_pareados(filtrar_radios(achados), {})
        self.assertEqual([r["endereco"] for r in ordenados], ["D", "A"])

    def test_radio_sem_nome_e_reconhecido_pelo_servico(self):
        achados = [("E", None, -40, [SERVICO_SERIAL.upper()])]
        self.assertEqual(filtrar_radios(achados), [{"endereco": "E", "nome": NOME_DESCONHECIDO, "rssi": -40}])


class Pareados(unittest.TestCase):
    def test_pareado_sem_anuncio_entra_na_lista_depois_dos_que_anunciam(self):
        anunciados = [{"endereco": "A", "nome": "MeshCore-A", "rssi": -90}]
        radios = combinar_com_pareados(anunciados, {"B": "MeshCore-B"})
        self.assertEqual([r["endereco"] for r in radios], ["A", "B"])
        self.assertIsNone(radios[1]["rssi"])
        self.assertTrue(radios[1]["pareado"])
        self.assertFalse(radios[0]["pareado"])

    def test_nome_do_pareamento_vale_para_quem_anuncia_sem_nome(self):
        anunciados = [{"endereco": "A", "nome": NOME_DESCONHECIDO, "rssi": -40}]
        radios = combinar_com_pareados(anunciados, {"A": "MeshCore-1D1CCA98"})
        self.assertEqual(radios, [{"endereco": "A", "nome": "MeshCore-1D1CCA98", "rssi": -40, "pareado": True}])

    def test_endereco_do_id_windows(self):
        identificador = "BluetoothLE#BluetoothLEe0:d4:64:32:7e:45-d7:32:33:fd:bb:ba"
        self.assertEqual(endereco_do_id_windows(identificador), "D7:32:33:FD:BB:BA")


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

    def novo_mc(self, **resposta):
        """Radio falso cuja conexao devolve ou levanta o que for pedido."""
        return mock.MagicMock(
            is_connected=True,
            connect=mock.AsyncMock(**resposta),
            disconnect=mock.AsyncMock(),
        )

    def rodar(self, radio, *instancias):
        self.clientes = []

        def nova_conexao(**_):
            conexao = mock.MagicMock()
            conexao.client.disconnect = mock.AsyncMock()
            self.clientes.append(conexao.client)
            return conexao

        async def conectar():
            with mock.patch("radio.MeshCore", side_effect=list(instancias)), \
                    mock.patch("radio.BLEConnection", side_effect=nova_conexao):
                await radio.conectar("ble:AA:BB")

        asyncio.run(conectar())

    def test_falha_nao_guarda_o_destino_e_explica_o_pareamento(self):
        for resposta in ({"return_value": None}, {"side_effect": OSError("falhou")}):
            radio = Radio()
            with self.assertRaises(RadioErro) as erro:
                self.rodar(radio, *[self.novo_mc(**resposta) for _ in range(3)])
            self.assertEqual(len(self.clientes), 3)
            self.assertIsNone(radio.porta)
            self.assertIn("pareado", str(erro.exception))
            self.assertEqual(radio.erro, str(erro.exception))

    def test_cada_tentativa_com_falha_solta_o_enlace(self):
        radio = Radio()
        with self.assertRaises(RadioErro):
            self.rodar(radio, *[self.novo_mc(side_effect=OSError("Insufficient Authentication")) for _ in range(3)])
        for cliente in self.clientes:
            cliente.disconnect.assert_awaited_once()

    def test_falha_passageira_conecta_na_tentativa_seguinte(self):
        radio = Radio()
        falso = self.novo_mc(return_value=object())
        contatos = mock.MagicMock(payload={"c": {}})
        contatos.type = None
        falso.commands.get_contacts = mock.AsyncMock(return_value=contatos)
        self.rodar(radio, self.novo_mc(side_effect=OSError("Insufficient Authentication")), falso)
        self.assertEqual(len(self.clientes), 2)
        self.clientes[0].disconnect.assert_awaited_once()
        self.clientes[1].disconnect.assert_not_awaited()
        self.assertEqual(radio.porta, "ble:AA:BB")
        self.assertIsNone(radio.erro)
        self.assertTrue(radio.conectado)

    def test_falha_ao_ler_contatos_fecha_a_conexao(self):
        radio = Radio()
        falso = self.novo_mc(return_value=object())
        falso.commands.get_contacts = mock.AsyncMock(
            return_value=mock.MagicMock(type=EventType.ERROR, payload={"reason": "sem resposta"})
        )
        with self.assertRaises(RadioErro):
            self.rodar(radio, falso)
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
