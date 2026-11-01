import sqlite3
import tempfile
import unittest
from pathlib import Path

from banco import Banco

ESQUEMA_MINUTOS = """
CREATE TABLE rastreados (
    chave TEXT PRIMARY KEY, nome TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
    intervalo_min INTEGER NOT NULL, lat REAL, lon REAL, alt REAL, posicao_em REAL,
    telemetria TEXT, status TEXT, resposta_em REAL, pedido_em REAL,
    proximo_em REAL NOT NULL DEFAULT 0, falhas INTEGER NOT NULL DEFAULT 0
);
INSERT INTO rastreados (chave, nome, intervalo_min) VALUES ('a', 'A', 15), ('b', 'B', 60);
"""

ESQUEMA_SEGUNDOS = """
CREATE TABLE rastreados (
    chave TEXT PRIMARY KEY, nome TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
    intervalo_s INTEGER NOT NULL, cor INTEGER NOT NULL DEFAULT 0, lat REAL, lon REAL, alt REAL,
    posicao_em REAL, telemetria TEXT, status TEXT, resposta_em REAL, pedido_em REAL,
    proximo_em REAL NOT NULL DEFAULT 0, falhas INTEGER NOT NULL DEFAULT 0
);
INSERT INTO rastreados (chave, nome, intervalo_s) VALUES ('x', 'X', 600);
"""


class Migracao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name)

    def abrir(self):
        banco = Banco(self.caminho)
        self.addCleanup(banco.con.close)
        return banco

    def criar_antigo(self, esquema):
        con = sqlite3.connect(self.caminho / "tracker.db")
        con.executescript(esquema)
        con.close()

    def test_minutos_vao_para_o_valor_mais_proximo(self):
        self.criar_antigo(ESQUEMA_MINUTOS)
        self.abrir()
        itens = {i["chave"]: i for i in self.abrir().rastreados()}
        self.assertEqual(itens["a"]["intervalo_s"], 600)
        self.assertEqual(itens["b"]["intervalo_s"], 3600)
        self.assertNotEqual(itens["a"]["cor"], itens["b"]["cor"])
        self.assertNotIn("intervalo_min", itens["a"])

    def test_banco_em_segundos_ganha_colunas_de_tempo(self):
        self.criar_antigo(ESQUEMA_SEGUNDOS)
        item = self.abrir().rastreados()[0]
        self.assertEqual(item["intervalo_s"], 600)
        self.assertIsNone(item["rtt_medio"])

    def test_cor_livre_e_reaproveitada(self):
        banco = self.abrir()
        for chave in "abc":
            banco.adicionar(chave, chave, 600)
        banco.remover("b")
        banco.adicionar("d", "d", 600)
        cores = {i["chave"]: i["cor"] for i in banco.rastreados()}
        self.assertEqual(cores, {"a": 0, "c": 2, "d": 1})


if __name__ == "__main__":
    unittest.main()
