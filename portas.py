"""Lista as portas seriais com o nome informado pelo proprio dispositivo USB."""

import ctypes
import logging
import sys
import uuid

from serial.tools import list_ports

CLASSE_PORTAS = "{4D36E978-E325-11CE-BFC1-08002BE10318}"
CHAVE_NOME_USB = "{540B947E-8B40-45BC-A8A2-6A0B894CBDA2}"
LISTAR_SO_PRESENTES_DA_CLASSE = 0x100 | 0x200

logger = logging.getLogger("tracker")


def compor_nome(produto, interface):
    partes = [nome for nome in (produto, interface) if nome]
    if len(partes) == 2 and partes[0] == partes[1]:
        partes.pop()
    return " - ".join(partes)


def _nomes_windows():
    """Retorna {porta: nome}. Num aparelho composto, o nome do produto fica no dispositivo pai."""
    import winreg

    cfg = ctypes.WinDLL("cfgmgr32")

    class ChavePropriedade(ctypes.Structure):
        _fields_ = [("guid", ctypes.c_ubyte * 16), ("pid", ctypes.c_ulong)]

    chave = ChavePropriedade((ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(CHAVE_NOME_USB).bytes_le), 4)

    def propriedade(no):
        tipo = ctypes.c_ulong()
        buffer = ctypes.create_unicode_buffer(512)
        tamanho = ctypes.c_ulong(ctypes.sizeof(buffer))
        retorno = cfg.CM_Get_DevNode_PropertyW(
            no, ctypes.byref(chave), ctypes.byref(tipo), buffer, ctypes.byref(tamanho), 0
        )
        return buffer.value if retorno == 0 else ""

    tamanho = ctypes.c_ulong()
    if cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(tamanho), CLASSE_PORTAS, LISTAR_SO_PRESENTES_DA_CLASSE):
        return {}
    lista = ctypes.create_unicode_buffer(tamanho.value)
    if cfg.CM_Get_Device_ID_ListW(CLASSE_PORTAS, lista, tamanho, LISTAR_SO_PRESENTES_DA_CLASSE):
        return {}

    nomes = {}
    for instancia in lista[:].split("\0"):
        if not instancia:
            continue
        try:
            caminho = rf"SYSTEM\CurrentControlSet\Enum\{instancia}\Device Parameters"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, caminho) as registro:
                porta = winreg.QueryValueEx(registro, "PortName")[0]
        except OSError:
            continue

        no = ctypes.c_ulong()
        if cfg.CM_Locate_DevNodeW(ctypes.byref(no), instancia, 0):
            continue
        interface = propriedade(no)
        produto = ""
        pai = ctypes.c_ulong()
        if "&MI_" in instancia and cfg.CM_Get_Parent(ctypes.byref(pai), no, 0) == 0:
            produto = propriedade(pai)
        nomes[porta] = compor_nome(produto, interface)
    return nomes


def descrever(porta, nomes_windows):
    """Usa o nome USB. Sem ele, a descricao generica do sistema, sem repetir a porta."""
    nome = nomes_windows.get(porta.device) or compor_nome(porta.product, porta.interface)
    if nome:
        return nome
    descricao = (porta.description or "").replace(f" ({porta.device})", "")
    return "" if descricao in ("n/a", porta.device) else descricao


def listar_portas():
    nomes_windows = {}
    if sys.platform == "win32":
        try:
            nomes_windows = _nomes_windows()
        except Exception:
            logger.exception("Nao foi possivel ler os nomes USB")
    return [
        {"porta": porta.device, "descricao": descrever(porta, nomes_windows)}
        for porta in sorted(list_ports.comports(), key=lambda p: p.device)
    ]
