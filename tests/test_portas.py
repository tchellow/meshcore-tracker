import unittest
from types import SimpleNamespace

from portas import compor_nome, descrever


def porta(device, description="n/a", product=None, interface=None):
    return SimpleNamespace(device=device, description=description, product=product, interface=interface)


class Nomes(unittest.TestCase):
    def test_compor_nome(self):
        self.assertEqual(compor_nome("A", "B"), "A - B")
        self.assertEqual(compor_nome("A", "A"), "A")
        self.assertEqual(compor_nome(None, "B"), "B")
        self.assertEqual(compor_nome(None, None), "")

    def test_linux_usa_os_campos_da_biblioteca(self):
        radio = porta("/dev/ttyACM0", "x", "ProMicro NRF52840", "TinyUSB Serial")
        self.assertEqual(descrever(radio, {}), "ProMicro NRF52840 - TinyUSB Serial")
        self.assertEqual(descrever(porta("/dev/ttyS0"), {}), "")

    def test_windows_prefere_o_nome_usb(self):
        radio = porta("COM9", "Dispositivo Serial USB (COM9)")
        self.assertEqual(descrever(radio, {"COM9": "ProMicro NRF52840"}), "ProMicro NRF52840")

    def test_sem_nome_usb_nao_repete_a_porta(self):
        self.assertEqual(descrever(porta("COM5", "Dispositivo Serial USB (COM5)"), {"COM5": ""}), "Dispositivo Serial USB")


if __name__ == "__main__":
    unittest.main()
