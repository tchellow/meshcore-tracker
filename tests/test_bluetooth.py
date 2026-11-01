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
from radio import ERRO_FIRMWARE_USB, PAREAMENTO_NAO_ATENDIDO, TENTATIVAS_PAREAMENTO, PinNecessario, Radio, RadioErro, endereco_bluetooth, parear


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


class Pareamento(unittest.TestCase):
    def rodar(self, *resultados):
        with mock.patch("radio.PAUSA_TENTATIVAS_PAREAMENTO_S", 0), \
                mock.patch("radio._tentar_parear", mock.AsyncMock(side_effect=resultados)) as tentar:
            self.tentar = tentar
            asyncio.run(parear("AA:BB", "123456"))

    def test_recusa_sem_pedir_o_pin_tenta_de_novo(self):
        self.rodar((False, False), (False, False), (False, False), (True, True))
        self.assertEqual(self.tentar.await_count, 4)

    def test_pin_recusado_para_na_primeira_vez(self):
        with self.assertRaises(RadioErro) as erro:
            self.rodar((False, False), (False, True), (True, True))
        self.assertIn("PIN", str(erro.exception))
        self.assertEqual(self.tentar.await_count, 2)

    def test_desiste_depois_do_limite(self):
        with self.assertRaises(RadioErro) as erro:
            self.rodar(*[(False, False)] * TENTATIVAS_PAREAMENTO)
        self.assertEqual(str(erro.exception), PAREAMENTO_NAO_ATENDIDO)
        self.assertEqual(self.tentar.await_count, TENTATIVAS_PAREAMENTO)


class Usb(unittest.TestCase):
    def erro_ao_abrir(self, falha):
        radio = Radio()
        with mock.patch("radio.MeshCore.create_serial", mock.AsyncMock(side_effect=falha)), \
                self.assertRaises(RadioErro) as erro:
            asyncio.run(radio.conectar("COM9"))
        self.assertIsNone(radio.porta)
        return str(erro.exception)

    def test_acesso_negado_indica_o_firmware(self):
        embrulhado = Exception("could not open port 'COM9': PermissionError(13, 'Acesso negado.', None, 5)")
        for falha in (PermissionError(13, "Acesso negado."), embrulhado):
            self.assertEqual(self.erro_ao_abrir(falha), ERRO_FIRMWARE_USB)

    def test_sem_resposta_indica_o_firmware(self):
        radio = Radio()
        with mock.patch("radio.MeshCore.create_serial", mock.AsyncMock(return_value=None)), \
                self.assertRaises(RadioErro) as erro:
            asyncio.run(radio.conectar("COM9"))
        self.assertEqual(str(erro.exception), ERRO_FIRMWARE_USB)
        for texto in ("Companion USB", "Bluetooth", "Wi-Fi"):
            self.assertIn(texto, ERRO_FIRMWARE_USB)

    def test_outra_falha_mostra_a_porta(self):
        self.assertIn("COM9", self.erro_ao_abrir(OSError("porta inexistente")))


class Conexao(unittest.TestCase):
    def setUp(self):
        pausa = mock.patch("radio.PAUSA_TENTATIVAS_BLUETOOTH_S", 0)
        pausa.start()
        self.addCleanup(pausa.stop)
        consulta = mock.patch("radio.precisa_parear", mock.AsyncMock(return_value=False))
        self.precisa_parear = consulta.start()
        self.addCleanup(consulta.stop)
        pareamento = mock.patch("radio.parear", mock.AsyncMock())
        self.parear = pareamento.start()
        self.addCleanup(pareamento.stop)

    def novo_mc(self, **resposta):
        """Radio falso cuja conexao devolve ou levanta o que for pedido."""
        return mock.MagicMock(
            is_connected=True,
            connect=mock.AsyncMock(**resposta),
            disconnect=mock.AsyncMock(),
        )

    def mc_que_conecta(self):
        falso = self.novo_mc(return_value=object())
        contatos = mock.MagicMock(payload={"c": {}})
        contatos.type = None
        falso.commands.get_contacts = mock.AsyncMock(return_value=contatos)
        return falso

    def rodar(self, radio, *instancias, pin=None):
        self.clientes = []

        def nova_conexao(**_):
            conexao = mock.MagicMock()
            conexao.client.disconnect = mock.AsyncMock()
            self.clientes.append(conexao.client)
            return conexao

        async def conectar():
            with mock.patch("radio.MeshCore", side_effect=list(instancias)), \
                    mock.patch("radio.BLEConnection", side_effect=nova_conexao):
                await radio.conectar("ble:AA:BB", pin)

        asyncio.run(conectar())

    def test_sem_pareamento_e_sem_pin_nao_tenta_conectar(self):
        self.precisa_parear.return_value = True
        radio = Radio()
        with self.assertRaises(PinNecessario):
            self.rodar(radio)
        self.assertEqual(self.clientes, [])
        self.parear.assert_not_awaited()
        self.assertIsNone(radio.porta)

    def test_com_o_pin_pareia_e_conecta(self):
        self.precisa_parear.return_value = True
        radio = Radio()
        self.rodar(radio, self.mc_que_conecta(), pin="123456")
        self.parear.assert_awaited_once_with("AA:BB", "123456")
        self.assertEqual(radio.porta, "ble:AA:BB")

    def test_pareamento_recusado_nao_conecta(self):
        self.precisa_parear.return_value = True
        self.parear.side_effect = RadioErro("O rádio recusou o pareamento. Confira o PIN.")
        radio = Radio()
        with self.assertRaises(RadioErro) as erro:
            self.rodar(radio, pin="000000")
        self.assertIn("PIN", str(erro.exception))
        self.assertEqual(self.clientes, [])
        self.assertIsNone(radio.porta)

    def test_ja_pareado_ignora_o_pin(self):
        radio = Radio()
        self.rodar(radio, self.mc_que_conecta(), pin="123456")
        self.parear.assert_not_awaited()
        self.assertEqual(radio.porta, "ble:AA:BB")

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
        falso = self.mc_que_conecta()
        self.rodar(radio, self.novo_mc(side_effect=OSError("Insufficient Authentication")), falso)
        self.assertEqual(len(self.clientes), 2)
        self.clientes[0].disconnect.assert_awaited_once()
        self.clientes[1].disconnect.assert_not_awaited()
        self.assertEqual(radio.porta, "ble:AA:BB")
        self.assertIsNone(radio.erro)
        self.assertTrue(radio.conectado)

    def mc_com_leitura(self, leitura):
        """Radio falso em que `leitura` recebe a funcao que avisa a chegada de um contato."""
        falso = self.novo_mc(return_value=object())

        async def get_contacts(**_):
            return await leitura(falso.subscribe.call_args.args[1])

        falso.commands.get_contacts = get_contacts
        return falso

    def test_lista_longa_passa_do_silencio_sem_falhar(self):
        async def leitura(chegou):
            for _ in range(10):
                await asyncio.sleep(0.02)
                chegou(None)
            return mock.MagicMock(type=None, payload={"c": {}})

        radio = Radio()
        with mock.patch("radio.SILENCIO_CONTATOS_S", 0.1):
            self.rodar(radio, self.mc_com_leitura(leitura))
        self.assertEqual(radio.contatos, {"c": {}})
        self.assertEqual(radio.porta, "ble:AA:BB")

    def test_silencio_na_lista_fecha_a_conexao(self):
        async def leitura(chegou):
            chegou(None)
            await asyncio.sleep(30)

        radio = Radio()
        falso = self.mc_com_leitura(leitura)
        with mock.patch("radio.SILENCIO_CONTATOS_S", 0.05), self.assertRaises(RadioErro):
            self.rodar(radio, falso)
        falso.disconnect.assert_awaited_once()
        falso.unsubscribe.assert_called_once()
        self.assertIsNone(radio.porta)
        self.assertIn("contatos", radio.erro)

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
