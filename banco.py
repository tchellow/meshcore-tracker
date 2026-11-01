"""Persistencia em SQLite: contatos rastreados, ultima posicao e configuracao."""

import json
import os
import sqlite3
import sys
from pathlib import Path

INTERVALOS_S = (15, 30, 60, 5 * 60, 10 * 60, 30 * 60, 60 * 60, 3 * 60 * 60, 5 * 60 * 60)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS rastreados (
    chave TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    intervalo_s INTEGER NOT NULL,
    cor INTEGER NOT NULL DEFAULT 0,
    lat REAL,
    lon REAL,
    alt REAL,
    posicao_em REAL,
    telemetria TEXT,
    status TEXT,
    resposta_em REAL,
    pedido_em REAL,
    rtt_ultimo REAL,
    rtt_medio REAL,
    proximo_em REAL NOT NULL DEFAULT 0,
    falhas INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS config (
    nome TEXT PRIMARY KEY,
    valor TEXT
);
"""


def pasta_dados():
    """Pasta local do usuario: o banco nao pode ficar na pasta sincronizada do Drive."""
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "MeshcoreTracker"
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "meshcore-tracker"


class Banco:
    def __init__(self, pasta):
        pasta.mkdir(parents=True, exist_ok=True)
        # Criado na linha principal, mas depois usado so pela linha do servidor.
        self.con = sqlite3.connect(pasta / "tracker.db", isolation_level=None, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self._migrar_intervalo_em_minutos()
        self._garantir_colunas_de_tempo()

    def _garantir_colunas_de_tempo(self):
        colunas = [linha["name"] for linha in self.con.execute("PRAGMA table_info(rastreados)")]
        for coluna in ("rtt_ultimo", "rtt_medio"):
            if coluna not in colunas:
                self.con.execute(f"ALTER TABLE rastreados ADD COLUMN {coluna} REAL")

    def _migrar_intervalo_em_minutos(self):
        """Bancos antigos guardam intervalo_min: leva cada contato ao valor mais proximo da lista."""
        colunas = [linha["name"] for linha in self.con.execute("PRAGMA table_info(rastreados)")]
        if "intervalo_min" not in colunas:
            return
        linhas = self.con.execute("SELECT chave, intervalo_min FROM rastreados ORDER BY rowid").fetchall()
        self.con.execute("BEGIN")
        self.con.execute("ALTER TABLE rastreados ADD COLUMN intervalo_s INTEGER NOT NULL DEFAULT 600")
        self.con.execute("ALTER TABLE rastreados ADD COLUMN cor INTEGER NOT NULL DEFAULT 0")
        for cor, linha in enumerate(linhas):
            segundos = min(INTERVALOS_S, key=lambda s: abs(s - linha["intervalo_min"] * 60))
            self.con.execute(
                "UPDATE rastreados SET intervalo_s = ?, cor = ? WHERE chave = ?",
                (segundos, cor, linha["chave"]),
            )
        self.con.execute("ALTER TABLE rastreados DROP COLUMN intervalo_min")
        self.con.execute("COMMIT")

    def config(self, nome):
        linha = self.con.execute("SELECT valor FROM config WHERE nome = ?", (nome,)).fetchone()
        return linha["valor"] if linha else None

    def salvar_config(self, nome, valor):
        self.con.execute(
            "INSERT INTO config (nome, valor) VALUES (?, ?) "
            "ON CONFLICT (nome) DO UPDATE SET valor = excluded.valor",
            (nome, valor),
        )

    def rastreados(self):
        linhas = self.con.execute("SELECT * FROM rastreados ORDER BY nome COLLATE NOCASE").fetchall()
        return [_item(linha) for linha in linhas]

    def adicionar(self, chave, nome, intervalo_s):
        """Cada contato recebe a menor cor livre e a mantem, para nao mudar de cor no mapa."""
        usadas = {linha["cor"] for linha in self.con.execute("SELECT cor FROM rastreados")}
        cor = next(i for i in range(len(usadas) + 1) if i not in usadas)
        self.con.execute(
            "INSERT OR IGNORE INTO rastreados (chave, nome, intervalo_s, cor) VALUES (?, ?, ?, ?)",
            (chave, nome, intervalo_s, cor),
        )

    def remover(self, chave):
        self.con.execute("DELETE FROM rastreados WHERE chave = ?", (chave,))

    def alterar(self, chave, ativo=None, intervalo_s=None):
        """Mudar o agendamento vale a partir de agora, entao o proximo pedido e imediato."""
        if ativo is not None:
            self.con.execute(
                "UPDATE rastreados SET ativo = ?, proximo_em = 0, falhas = 0 WHERE chave = ?",
                (int(ativo), chave),
            )
        if intervalo_s is not None:
            self.con.execute(
                "UPDATE rastreados SET intervalo_s = ?, proximo_em = 0, falhas = 0 WHERE chave = ?",
                (intervalo_s, chave),
            )

    def pedir_agora(self, chave):
        self.con.execute("UPDATE rastreados SET proximo_em = 0, falhas = 0 WHERE chave = ?", (chave,))

    def proximo_pendente(self, agora):
        linha = self.con.execute(
            "SELECT * FROM rastreados WHERE ativo = 1 AND proximo_em <= ? ORDER BY proximo_em LIMIT 1",
            (agora,),
        ).fetchone()
        return _item(linha) if linha else None

    def registrar_tentativa(self, chave, status, agora, proximo_em, falhas):
        self.con.execute(
            "UPDATE rastreados SET status = ?, pedido_em = ?, proximo_em = ?, falhas = ? WHERE chave = ?",
            (status, agora, proximo_em, falhas, chave),
        )

    def registrar_resposta(self, chave, lpp, agora):
        self.con.execute(
            "UPDATE rastreados SET telemetria = ?, resposta_em = ? WHERE chave = ?",
            (json.dumps(lpp, ensure_ascii=False), agora, chave),
        )

    def registrar_medicao(self, chave, rtt, media):
        self.con.execute(
            "UPDATE rastreados SET rtt_ultimo = ?, rtt_medio = ? WHERE chave = ?",
            (rtt, media, chave),
        )

    def descartar_media(self, chave):
        self.con.execute("UPDATE rastreados SET rtt_medio = NULL WHERE chave = ?", (chave,))

    def registrar_posicao(self, chave, posicao, agora):
        self.con.execute(
            "UPDATE rastreados SET lat = ?, lon = ?, alt = ?, posicao_em = ? WHERE chave = ?",
            (posicao["latitude"], posicao["longitude"], posicao.get("altitude"), agora, chave),
        )


def _item(linha):
    item = dict(linha)
    item["ativo"] = bool(item["ativo"])
    item["telemetria"] = json.loads(item["telemetria"]) if item["telemetria"] else []
    return item
