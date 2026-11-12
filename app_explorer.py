import os
import sys
import io
import json
import re
import tempfile
import base64
import threading
import queue
import calendar
from datetime import datetime, timedelta
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import customtkinter as ctk
from PIL import Image

try:
    from icon_b64 import ICON_PNG_B64, ICON_ICO_B64
except ImportError:
    ICON_PNG_B64 = ""
    ICON_ICO_B64 = ""

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def obter_diretorios_busca():
    """Retorna lista de diretórios onde o arquivo de configuração pode estar localizado"""
    dirs = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        dirs.append(exe_dir)
    if '__file__' in globals():
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.getcwd())
    dirs.append(os.path.abspath('..'))
    dirs.append(os.path.abspath('../..'))

    vistos = set()
    dirs_unicos = []
    for d in dirs:
        if d and os.path.isdir(d) and d not in vistos:
            vistos.add(d)
            dirs_unicos.append(d)
    return dirs_unicos


def localizar_arquivo_config():
    """Localiza config.json ou .env se existir"""
    for d in obter_diretorios_busca():
        c_json = os.path.join(d, 'config.json')
        if os.path.exists(c_json):
            return c_json
        c_env = os.path.join(d, '.env')
        if os.path.exists(c_env):
            return c_env
    return None


CONFIG_FILE = "config.json"
PLUGGY_BASE_URL = "https://api.pluggy.ai"
PLUGGY_STATUS_BASE_URL = "https://status.pluggy.ai"
DEFAULT_CLIENT_ID = "fe96af16-0c23-44e6-8d0a-57223694b760"
DEFAULT_CLIENT_SECRET = "f7c14c58-f0d0-4947-8423-721548882db7"
APP_VERSION = "1.4.0"
GITHUB_REPO = "Fulviotanure/API-OPEN-FINANCE"


def normalizar_cor_hex(raw_cor, fallback="#6366F1"):
    """
    Normaliza cores hexadecimais retornadas pela API (com ou sem prefixo #).
    Exemplo: '009ee3' -> '#009ee3'. Evita TclError no Tkinter.
    """
    if not raw_cor or not isinstance(raw_cor, str):
        return fallback
    clean = raw_cor.strip()
    if not clean:
        return fallback
    if not clean.startswith("#"):
        clean = "#" + clean
    if re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", clean):
        return clean
    return fallback


# Cache em memória para requisições de status da infraestrutura Pluggy
_STATUS_CACHE = {
    "summary": {"data": None, "ts": 0},
    "connectors": {"data": None, "ts": 0},
    "full": {"data": None, "ts": 0}
}
_STATUS_CACHE_TTL = 45  # 45 segundos de cache


def obter_status_summary(force_refresh=False):
    """Consulta https://status.pluggy.ai/api/summary com cache"""
    agora = datetime.now().timestamp()
    cached = _STATUS_CACHE["summary"]
    if not force_refresh and cached["data"] and (agora - cached["ts"] < _STATUS_CACHE_TTL):
        return cached["data"]
    try:
        url = f"{PLUGGY_STATUS_BASE_URL}/api/summary"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            data = res.json()
            _STATUS_CACHE["summary"] = {"data": data, "ts": agora}
            return data
    except Exception as e:
        print("Erro ao buscar status summary:", e)
    return cached["data"] or {"status": "unknown", "labels": {"pt": "Status Indisponível"}, "openIncidents": 0}


def obter_status_conectores_incidentes(force_refresh=False):
    """Consulta https://status.pluggy.ai/api/connectors-incidents com cache"""
    agora = datetime.now().timestamp()
    cached = _STATUS_CACHE["connectors"]
    if not force_refresh and cached["data"] and (agora - cached["ts"] < _STATUS_CACHE_TTL):
        return cached["data"]
    try:
        url = f"{PLUGGY_STATUS_BASE_URL}/api/connectors-incidents"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            _STATUS_CACHE["connectors"] = {"data": data, "ts": agora}
            return data
    except Exception as e:
        print("Erro ao buscar incidentes de conectores:", e)
    return cached["data"] or {"connectors": {}}


def obter_status_completo_pluggy(force_refresh=False):
    """Consulta https://status.pluggy.ai/api/status com cache"""
    agora = datetime.now().timestamp()
    cached = _STATUS_CACHE["full"]
    if not force_refresh and cached["data"] and (agora - cached["ts"] < _STATUS_CACHE_TTL):
        return cached["data"]
    try:
        url = f"{PLUGGY_STATUS_BASE_URL}/api/status"
        res = requests.get(url, timeout=12)
        if res.status_code == 200:
            data = res.json()
            _STATUS_CACHE["full"] = {"data": data, "ts": agora}
            return data
    except Exception as e:
        print("Erro ao buscar status completo:", e)
    return cached["data"] or {"components": [], "incidents": []}


def buscar_incidentes_para_conector(connector_id, connector_name=""):
    """
    Retorna lista de incidentes ativos para um determinado connector_id ou nome
    """
    if not connector_id and not connector_name:
        return []

    data_con = obter_status_conectores_incidentes()
    connectors_map = data_con.get("connectors", {}) if isinstance(data_con, dict) else {}

    c_id_str = str(connector_id).strip()
    if c_id_str in connectors_map:
        return connectors_map[c_id_str]

    # Se não achou pelo ID exato, tenta por nome nas propriedades dos incidentes
    if connector_name and len(connector_name.strip()) > 3:
        nome_clean = connector_name.strip().lower()
        achados = []
        for cid, inc_list in connectors_map.items():
            for inc in inc_list:
                titulo = (inc.get("title") or "").lower()
                if nome_clean in titulo:
                    achados.append(inc)
        if achados:
            return achados

    return []

EMPTY_STATE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAADQElEQVR4nO3dvW4TQRiF4QniTkiLSEdDHSG"
    "lkQ3QuUyFHEsEpYocpI1FldIdN5AmEkpNQweiDdcCsoQla+P1Hzv+zsx5nwZQko3t7/Xs2rsWKQEAAAAAA"
    "AAAAACo00ESMRjePKbCTSfnh6kw4QHUMPiSQ3gW+ctrHH5p9+tA5UF6uL+bpsIdn5wOSlsJQlaAGoe/7H"
    "6UsBKE7gJqGn6p92fvASw+K0p7sDa1eL/UV4HwFQCxCMAcAZgjAHMEYI4AzBGAOQIwRwDmCMAcAZh7ngow"
    "urh8k0Q011ffUkXkVwCl4SvenuoDQF4EYE4+ALV9biN2eywOAmt70JXIrwDIiwDMEYA5AjBHAOYIwBwBmC"
    "MAc0W8EaR0Aqap7E0p+RVAafiKt6f6AJAXAZiTD0Btn9uI3R6Lg8DaHnQl8isA8iIAcwRgjgDMEYA5AjBH"
    "AOYIwFwRbwTlPAHTmL/JJL8C5D77Nqrs7F51ASAvAjAnfwww20erHQOMLi4/rfueHz9//U4FkA9A6UBttM"
    "Hg545evXxRQghFBFDS4JeFcPvl65+zd2/D/3ueZQgg0+DbZhHM/lQLgQB2HP7H4fvvXV8bTz6/7vqa2mpA"
    "AFsMf9XQu75vWQxKEfAysOfhb/pz811CNFaANcPfdfDLttFeDRRWAlaAFfoYfs7t9YEAMhzxbyN6V0AAe3"
    "62qq0CBJCePvtzD6m9/chVgADM2QcwCtr3t0WtAvYBRI2jVY4FCMAcAZgjAHMEYI4AzBGAOQLY4mKOEn/P"
    "OvYBNNdXH5KAqNPC9gG4I4D0dBXIvTy3tx95UQgBdMgVgcq+f44Ago8FuCRM2LjnZ6vas3+GFWDNKjAb2v"
    "8Oro9tVBPAdHJ+OP/78cnpIBWyKxjvOMB1Pxd9TWDI0edgePO4+O+H+7tpMvlkkNqxQNjLjxoi6FtEBKEf"
    "SmhHoOro30e9+xruqmV/3xGEfz6tlAh2DaFroCoRhAdQawhnGwxRIQKZAFzdBkfA+wDBVg15Hy8RCcA8Ag"
    "Iwj4AAzCMgAPMICMA8AgIwj4AAzCMgAPMICMA8AgIwj4AAzCMggEoi2PXEEQEUqD3s6EvLEST6glIAAAAA"
    "AAAAACI+wuzKFLtiFwi6gAAAABJRU5ErkJggg=="
)

MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MESES_NOMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

CATALOGO_CONECTORES_PLUGGY = [
    (976, '6P Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (977, '6P Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (804, '99Pay', 'PERSONAL_BANK', True, 'ef294b', True),
    (620, 'Ágora Investimentos', 'INVESTMENT', True, '296fa7', False),
    (781, 'Ágora Investimentos Empresas', 'BUSINESS_BANK', True, '296fa7', False),
    (970, 'Apex', 'PERSONAL_BANK', True, 'ef294b', True),
    (971, 'Apex Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (883, 'ASA', 'PERSONAL_BANK', True, '2b56c0', False),
    (884, 'ASA Empresas', 'BUSINESS_BANK', True, '2b56c0', False),
    (969, 'Atlanta', 'PERSONAL_BANK', True, 'ef294b', False),
    (230, 'Avenue', 'INVESTMENT', False, '#000000', False),
    (974, 'Axiis Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (975, 'Axiis Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (805, 'Azimut', 'PERSONAL_BANK', True, 'ef294b', True),
    (652, 'Banco Bmg', 'PERSONAL_BANK', True, 'fa6300', True),
    (666, 'Banco Bmg Empresas', 'BUSINESS_BANK', True, 'fa6300', True),
    (817, 'Banco BRB', 'PERSONAL_BANK', True, '003D7C', True),
    (818, 'Banco BRB Empresas', 'BUSINESS_BANK', True, '003D7C', True),
    (653, 'Banco Digio', 'PERSONAL_BANK', True, 'ff6776', True),
    (611, 'Banco do Brasil', 'PERSONAL_BANK', True, '1194F6', True),
    (662, 'Banco do Brasil Empresas', 'BUSINESS_BANK', True, '1194F6', True),
    (217, 'Banco do Brasil Empresas', 'BUSINESS_BANK', False, '1194F6', False),
    (279, 'Banco do Brasil Previdência', 'PERSONAL_BANK', False, '1194F6', False),
    (671, 'Banco do Nordeste do Brasil', 'PERSONAL_BANK', True, 'A6193C', True),
    (672, 'Banco do Nordeste do Brasil Empresas', 'BUSINESS_BANK', True, 'A6193C', True),
    (741, 'Banco Guanabara', 'PERSONAL_BANK', True, 'ef294b', True),
    (855, 'Banco Guanabara Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (680, 'Banco Master', 'PERSONAL_BANK', True, '031C2D', True),
    (742, 'Banco Mercantil', 'PERSONAL_BANK', True, 'ef294b', True),
    (819, 'Banco Mercantil Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (657, 'Banco PAN', 'PERSONAL_BANK', True, '02afff', True),
    (714, 'Banco Sofisa', 'PERSONAL_BANK', True, '004e46', True),
    (715, 'Banco Sofisa Empresas', 'BUSINESS_BANK', True, '004e46', True),
    (659, 'Banrisul', 'PERSONAL_BANK', True, '0B45E4', True),
    (660, 'Banrisul Empresas', 'BUSINESS_BANK', True, '0B45E4', True),
    (260, 'Banrisul Empresas', 'BUSINESS_BANK', False, '#0C45E5', False),
    (967, 'BPO Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (968, 'BPO Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (775, 'Bradescard', 'PERSONAL_BANK', True, 'ef294b', False),
    (603, 'Bradesco', 'PERSONAL_BANK', True, 'e5173f', True),
    (209, 'Bradesco Empresas', 'BUSINESS_BANK', False, 'e5173f', False),
    (609, 'Bradesco Empresas', 'BUSINESS_BANK', True, 'e5173f', True),
    (675, 'BTGPactual', 'PERSONAL_BANK', True, '66768f', True),
    (214, 'BTGPactual', 'INVESTMENT', False, '66768F', False),
    (655, 'BTGPactual Empresas', 'BUSINESS_BANK', True, '66768f', True),
    (614, 'BTGPactual Investimentos', 'INVESTMENT', True, '66768f', False),
    (779, 'BTGPactual Investimentos Empresas', 'BUSINESS_BANK', True, '66768f', False),
    (718, 'BV - Corporate', 'BUSINESS_BANK', True, '223AD2', True),
    (716, 'BV - Pessoa Física - APP', 'PERSONAL_BANK', True, '223AD2', True),
    (717, 'BV - Pessoa Física - Web', 'PERSONAL_BANK', True, '223AD2', False),
    (719, 'BV - Private', 'PERSONAL_BANK', True, '223AD2', True),
    (626, 'C6 Bank', 'PERSONAL_BANK', True, 'FFE45C', True),
    (726, 'C6 Bank Empresas', 'BUSINESS_BANK', True, 'FFE45C', True),
    (990, 'CAIXA - clientes sem conta', 'PERSONAL_BANK', True, '296fa7', False),
    (991, 'CAIXA - clientes sem conta Empresas', 'BUSINESS_BANK', True, '296fa7', False),
    (619, 'Caixa Econômica Federal', 'PERSONAL_BANK', True, '296fa7', True),
    (616, 'Caixa Econômica Federal Empresas', 'BUSINESS_BANK', True, '296fa7', True),
    (246, 'Caixa Previdência', 'INVESTMENT', False, '296fa7', False),
    (783, 'Caixa Tem', 'PERSONAL_BANK', True, '296fa7', False),
    (821, 'Cartão Atacadão', 'PERSONAL_BANK', True, 'ef294b', False),
    (822, 'Cartão Carrefour', 'PERSONAL_BANK', True, 'ef294b', False),
    (820, "Cartão Sam's Club", 'PERSONAL_BANK', True, 'ef294b', False),
    (982, 'CEAPE BANK', 'PERSONAL_BANK', True, 'ef294b', False),
    (983, 'Celcoin Baas', 'PERSONAL_BANK', True, 'ef294b', False),
    (747, 'Cielo', 'BUSINESS_BANK', True, 'ef294b', True),
    (710, 'Citi Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (623, 'Clear Corretora', 'INVESTMENT', True, '0500F5', False),
    (966, 'Concept', 'PERSONAL_BANK', True, 'ef294b', False),
    (880, 'Conta Bemol', 'PERSONAL_BANK', True, 'ef294b', True),
    (965, 'Conta Universal', 'PERSONAL_BANK', True, 'ef294b', True),
    (250, 'Cora', 'BUSINESS_BANK', False, 'f51b81', False),
    (964, 'CRB Money', 'PERSONAL_BANK', True, 'ef294b', True),
    (750, 'Crefisa', 'PERSONAL_BANK', True, '23b9e2', True),
    (860, 'Crefisa Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (963, 'Dezbrazil', 'PERSONAL_BANK', True, 'ef294b', False),
    (962, 'DMX', 'PERSONAL_BANK', True, 'ef294b', False),
    (961, 'Ease Bankly', 'PERSONAL_BANK', True, 'ef294b', False),
    (239, 'Efí Bank', 'BUSINESS_BANK', False, 'fb6910', False),
    (959, 'Ella Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (960, 'Ella Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (957, 'EMCASH', 'PERSONAL_BANK', True, 'ef294b', False),
    (958, 'EMCASH Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (271, 'EQI', 'INVESTMENT', False, 'DB671F', False),
    (802, 'EQI', 'INVESTMENT', True, '03ff60', False),
    (956, 'ESBank', 'PERSONAL_BANK', True, 'ef294b', True),
    (290, 'Ethereum networks', 'PERSONAL_BANK', False, '8faef2', False),
    (955, 'Exclusive', 'PERSONAL_BANK', True, 'ef294b', False),
    (954, 'Fixxbank', 'PERSONAL_BANK', True, 'ef294b', False),
    (953, 'Genius', 'PERSONAL_BANK', True, 'ef294b', False),
    (952, 'Giffty', 'PERSONAL_BANK', True, 'ef294b', False),
    (951, 'Gift Premium', 'PERSONAL_BANK', True, 'ef294b', False),
    (950, 'Glorya', 'PERSONAL_BANK', True, 'ef294b', False),
    (949, 'GoalBox', 'PERSONAL_BANK', True, 'ef294b', False),
    (948, 'Gold Pass', 'PERSONAL_BANK', True, 'ef294b', False),
    (980, 'GS3', 'PERSONAL_BANK', True, 'ef294b', False),
    (981, 'GS3 Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (946, 'HausBank', 'PERSONAL_BANK', True, 'ef294b', True),
    (944, 'Health Cash', 'PERSONAL_BANK', True, 'ef294b', True),
    (945, 'Health Cash Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (978, 'Hiperbanco', 'PERSONAL_BANK', True, 'ef294b', True),
    (979, 'Hiperbanco Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (947, 'H+ plus', 'PERSONAL_BANK', True, 'ef294b', False),
    (943, 'Hyak Bank', 'PERSONAL_BANK', True, 'ef294b', False),
    (942, 'Ibanx', 'PERSONAL_BANK', True, 'ef294b', False),
    (941, 'iHold', 'PERSONAL_BANK', True, 'ef294b', True),
    (940, 'IlevaCard', 'PERSONAL_BANK', True, 'ef294b', False),
    (972, 'Imobi Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (973, 'Imobi Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (939, 'Incentivale', 'PERSONAL_BANK', True, 'ef294b', False),
    (777, 'InfinitePay', 'PERSONAL_BANK', True, 'ef294b', True),
    (778, 'InfinitePay Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (938, 'Inova', 'PERSONAL_BANK', True, 'ef294b', False),
    (215, 'Inter', 'PERSONAL_BANK', False, '#fb6910', False),
    (823, 'Inter', 'PERSONAL_BANK', True, 'fb6910', False),
    (225, 'Inter Empresas', 'BUSINESS_BANK', False, 'fb6910', False),
    (824, 'Inter Empresas', 'BUSINESS_BANK', True, 'fb6910', False),
    (673, 'Investimentos BB', 'INVESTMENT', True, 'ef294b', False),
    (677, 'Íon', 'INVESTMENT', True, '0a1b1e', True),
    (601, 'Itaú', 'PERSONAL_BANK', True, 'EC7000', True),
    (794, 'Itaú BBA', 'BUSINESS_BANK', True, 'EC7000', False),
    (618, 'Itaú Empresas', 'BUSINESS_BANK', True, '0F1941', True),
    (218, 'Itaú Empresas', 'BUSINESS_BANK', False, '0F1941', False),
    (786, 'Itaú Emps', 'BUSINESS_BANK', True, '1130FF', True),
    (937, 'JoyCard', 'PERSONAL_BANK', True, 'ef294b', False),
    (936, 'Lemon', 'PERSONAL_BANK', True, 'ef294b', False),
    (934, 'Lothus', 'PERSONAL_BANK', True, 'ef294b', True),
    (935, 'Lothus Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (932, 'Mais Todos', 'PERSONAL_BANK', True, 'ef294b', False),
    (933, 'Mais Todos Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (931, 'Mark Up', 'PERSONAL_BANK', True, 'ef294b', False),
    (929, 'Meirelles', 'PERSONAL_BANK', True, 'ef294b', True),
    (930, 'Meirelles Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (720, 'Méliuz', 'PERSONAL_BANK', True, 'ef294b', False),
    (282, 'Mercado Bitcoin', 'INVESTMENT', False, 'ef4723', False),
    (206, 'Mercado Pago', 'PERSONAL_BANK', False, '009ee3', False),
    (606, 'Mercado Pago', 'PERSONAL_BANK', True, '009ee3', True),
    (665, 'Mercado Pago Empresas', 'BUSINESS_BANK', True, '009ee3', True),
    (200, 'MeuPluggy', 'PERSONAL_BANK', False, 'ef294b', False),
    (928, 'Meu Premio', 'PERSONAL_BANK', True, 'ef294b', False),
    (927, 'Meu Premio 360', 'PERSONAL_BANK', True, 'ef294b', False),
    (688, 'Midway', 'PERSONAL_BANK', True, 'ef294b', True),
    (795, 'Monte Bravo', 'INVESTMENT', True, 'ef294b', True),
    (926, 'Moovi', 'PERSONAL_BANK', True, 'ef294b', False),
    (925, 'MOTTU', 'PERSONAL_BANK', True, 'ef294b', False),
    (924, 'Multipremium', 'PERSONAL_BANK', True, 'ef294b', False),
    (793, 'Necton', 'PERSONAL_BANK', True, 'ef294b', False),
    (280, 'Necton', 'INVESTMENT', False, '0000FF', False),
    (689, 'Neon', 'PERSONAL_BANK', True, 'ef294b', True),
    (656, 'Next', 'PERSONAL_BANK', True, '03ff60', True),
    (801, 'Next Empresas', 'BUSINESS_BANK', True, '03ff60', True),
    (922, 'Nitybank', 'PERSONAL_BANK', True, 'ef294b', True),
    (923, 'Nitybank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (612, 'Nubank', 'PERSONAL_BANK', True, '8a0fbe', True),
    (664, 'Nubank Empresas', 'BUSINESS_BANK', True, '8a0fbe', True),
    (921, 'Omnion', 'PERSONAL_BANK', True, 'ef294b', False),
    (920, 'Onn Marketing', 'PERSONAL_BANK', True, 'ef294b', False),
    (918, 'Ovni', 'PERSONAL_BANK', True, 'ef294b', True),
    (919, 'Ovni Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (917, 'P2x', 'PERSONAL_BANK', True, 'ef294b', False),
    (692, 'PagBank', 'PERSONAL_BANK', True, '1BB99A', True),
    (816, 'PagBank Empresas', 'BUSINESS_BANK', True, '1BB99A', True),
    (814, 'Pague Veloz Serasa', 'PERSONAL_BANK', True, 'FE8502', True),
    (815, 'Pague Veloz Serasa Empresas', 'BUSINESS_BANK', True, 'FE8502', True),
    (916, 'PayCard', 'PERSONAL_BANK', True, 'ef294b', False),
    (651, 'PicPay', 'PERSONAL_BANK', True, '238662', True),
    (713, 'PicPay Negócios', 'BUSINESS_BANK', True, 'ef294b', True),
    (765, "Player's Bank", 'PERSONAL_BANK', True, 'ef294b', True),
    (915, 'Pocket', 'PERSONAL_BANK', True, 'ef294b', False),
    (800, 'Porto Bank', 'PERSONAL_BANK', True, '2b56c0', True),
    (882, 'Porto Bank Empresas', 'BUSINESS_BANK', True, '2b56c0', True),
    (914, 'POWPAY', 'PERSONAL_BANK', True, 'ef294b', True),
    (913, 'Prix', 'PERSONAL_BANK', True, 'ef294b', False),
    (912, 'Pulse', 'PERSONAL_BANK', True, 'ef294b', False),
    (694, 'QI SCD', 'PERSONAL_BANK', True, 'ef294b', True),
    (864, 'QI SCD Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (910, 'Rapidium Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (911, 'Rapidium Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (767, 'RecargaPay', 'PERSONAL_BANK', True, 'ef294b', True),
    (768, 'RecargaPay Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (696, 'Rede Celcoin', 'PERSONAL_BANK', True, 'ef294b', True),
    (811, 'Rede Celcoin Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (909, 'RelacionaMais', 'PERSONAL_BANK', True, 'ef294b', False),
    (907, 'Resolve Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (908, 'Resolve Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (905, 'Rhiza Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (906, 'Rhiza Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (605, 'Rico Investimentos', 'INVESTMENT', True, 'ff5200', True),
    (629, 'Safra', 'PERSONAL_BANK', True, '00003C', True),
    (697, 'Safra Empresas', 'BUSINESS_BANK', True, '00003C', True),
    (711, 'Safra Financeira', 'PERSONAL_BANK', True, 'ef294b', False),
    (712, 'Safra Financeira Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (608, 'Santander', 'PERSONAL_BANK', True, 'cc0000', True),
    (812, 'Santander Corretora', 'INVESTMENT', True, 'EC0000', False),
    (813, 'Santander Corretora Empresas', 'INVESTMENT', True, 'EC0000', False),
    (621, 'Santander Empresas', 'BUSINESS_BANK', True, 'cc0000', True),
    (221, 'Santander Empresas', 'BUSINESS_BANK', False, 'cc0000', False),
    (903, 'SEMEC BANK', 'PERSONAL_BANK', True, 'ef294b', False),
    (904, 'SEMEC BANK Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (658, 'Sicoob', 'PERSONAL_BANK', True, '00AE9D', True),
    (628, 'Sicoob Empresas', 'BUSINESS_BANK', True, '00AE9D', True),
    (661, 'Sicredi', 'PERSONAL_BANK', True, '3FA110', True),
    (627, 'Sicredi Empresas', 'BUSINESS_BANK', True, '3FA110', True),
    (901, 'Simpbank', 'PERSONAL_BANK', True, 'ef294b', True),
    (902, 'Simpbank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (900, 'Smart', 'PERSONAL_BANK', True, 'ef294b', False),
    (898, 'Snob Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (899, 'Snob Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (897, 'Spin', 'PERSONAL_BANK', True, 'ef294b', False),
    (787, 'Stone Pagamentos', 'PERSONAL_BANK', True, '00A868', True),
    (788, 'Stone Pagamentos Empresas', 'BUSINESS_BANK', True, '00A868', True),
    (896, 'Suppero', 'PERSONAL_BANK', True, 'ef294b', False),
    (895, 'Tokpay', 'PERSONAL_BANK', True, 'ef294b', False),
    (796, 'Toro Investimentos', 'INVESTMENT', True, 'ef294b', False),
    (797, 'Toro Investimentos Empresas', 'BUSINESS_BANK', True, 'ef294b', False),
    (674, 'Uber Conta by Digio', 'PERSONAL_BANK', True, 'ef294b', True),
    (663, 'Unicred', 'PERSONAL_BANK', True, '1e5c49', True),
    (670, 'Unicred Empresas', 'BUSINESS_BANK', True, '1e5c49', True),
    (894, 'Unique', 'PERSONAL_BANK', True, 'ef294b', False),
    (892, 'Uze', 'PERSONAL_BANK', True, 'ef294b', True),
    (893, 'Uze Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (291, 'Wise', 'PERSONAL_BANK', False, '9fe870', False),
    (890, 'Won Bank', 'PERSONAL_BANK', True, 'ef294b', True),
    (891, 'Won Bank Empresas', 'BUSINESS_BANK', True, 'ef294b', True),
    (676, 'Woop', 'PERSONAL_BANK', True, '00EE62', True),
    (602, 'XP Banking', 'PERSONAL_BANK', True, '111111', True),
    (702, 'XP Banking Empresas', 'BUSINESS_BANK', True, '111111', True),
    (202, 'XP Investimentos', 'INVESTMENT', False, '111111', False),
]

APELIDOS_BANCOS = {
    "bb": "Banco do Brasil",
    "bancodobrasil": "Banco do Brasil",
    "itau": "Itaú",
    "itaú": "Itaú",
    "bradesco": "Bradesco",
    "santander": "Santander",
    "nubank": "Nubank",
    "nu": "Nubank",
    "inter": "Inter",
    "bancointer": "Inter",
    "caixa": "Caixa Econômica Federal",
    "cef": "Caixa Econômica Federal",
    "caixaeconomica": "Caixa Econômica Federal",
    "c6": "C6 Bank",
    "c6bank": "C6 Bank",
    "mercadopago": "Mercado Pago",
    "mp": "Mercado Pago",
    "btg": "BTGPactual",
    "btgpactual": "BTGPactual",
    "xp": "XP Investimentos",
    "xpinvestimentos": "XP Investimentos",
    "sicoob": "Sicoob",
    "sicredi": "Sicredi",
    "neon": "Neon",
    "safra": "Safra",
    "cresol": "Cresol",
    "banrisul": "Banrisul",
    "pan": "Banco PAN",
    "bancopan": "Banco PAN",
    "bmg": "Banco Bmg",
    "sofisa": "Banco Sofisa",
    "daycoval": "Banco Daycoval",
    "pagbank": "PagBank",
    "pagseguro": "PagBank",
    "picpay": "PicPay",
    "wise": "Wise",
    "avenue": "Avenue",
    "original": "Banco Original"
}

def normalizar_texto_busca(s):
    """Remove acentos, espaços e caracteres especiais para busca insensível."""
    if not s:
        return ""
    import unicodedata, re
    nfkd = unicodedata.normalize("NFKD", str(s))
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r"[^a-zA-Z0-9]", "", sem_acento).lower()

def buscar_conector_por_termo(termo_ou_id):
    """Localiza o conector no catálogo da Pluggy por ID, apelido ou nome aproximado."""
    if not termo_ou_id:
        return None
    termo_str = str(termo_ou_id).strip()

    # 1. Busca por ID numérico exato
    if termo_str.isdigit():
        target_id = int(termo_str)
        for c in CATALOGO_CONECTORES_PLUGGY:
            if c[0] == target_id:
                return c

    clean = normalizar_texto_busca(termo_str)

    # 2. Resolução de apelido
    if clean in APELIDOS_BANCOS:
        nome_apelido = APELIDOS_BANCOS[clean]
        clean_apelido = normalizar_texto_busca(nome_apelido)
        for c in CATALOGO_CONECTORES_PLUGGY:
            if normalizar_texto_busca(c[1]) == clean_apelido:
                return c
        clean = clean_apelido

    # 3. Nome exato normalizado
    for c in CATALOGO_CONECTORES_PLUGGY:
        if normalizar_texto_busca(c[1]) == clean:
            return c

    # 4. Início de nome (prefixo)
    for c in CATALOGO_CONECTORES_PLUGGY:
        if normalizar_texto_busca(c[1]).startswith(clean):
            return c

    # 5. Substring
    for c in CATALOGO_CONECTORES_PLUGGY:
        if clean in normalizar_texto_busca(c[1]):
            return c

    return None

def obter_detalhes_historico_instituicao(termo_ou_id):
    """
    Retorna estrutura completa de histórico transacional da instituição:
    - nome: nome oficial
    - id: connector_id (se identificado)
    - texto_campo: '(banco)-(quantos ) meses' (ex: 'Itaú - 12 meses')
    - meses_retornados: '12 meses'
    - meses_esperados: '12 meses (1 ano completo)'
    - dias_iniciais: 365
    - atualizacoes_recentes: 'Últimos 7 dias (frequente de 1 a 6 dias)'
    - lancamentos_futuros: 'Até 90 dias futuros (PENDING)' ou 'Apenas transações passadas'
    - tipo_conexao: 'Open Finance Regulado (BACEN)' ou 'Conexão Direta'
    - explicacao_faq: texto oficial com links
    - motivos_retorno_menor: lista explicativa
    """
    c = buscar_conector_por_termo(termo_ou_id)
    if c:
        cid = c[0]
        nome = c[1]
        tipo = c[2]
        is_of = c[3]
        cor = normalizar_cor_hex(c[4], fallback="#0284C7")
        sched = c[5]
    else:
        cid = None
        nome = str(termo_ou_id).strip() if termo_ou_id else "Instituição"
        tipo = "PERSONAL_BANK"
        is_of = True
        cor = "#0284C7"
        sched = False

    nome_clean = normalizar_texto_busca(nome)

    # Regra dos meses
    if cid == 202 or "xpinvest" in nome_clean:
        meses_rotulo = "12 meses"
        meses_detalhe = "12 meses para contas bancárias/cartões e até 48 meses (4 anos) para notas de corretagem/investimentos"
        meses_esperados = "12 meses (contas/cartões) / até 48 meses (investimentos)"
        tipo_conexao = "Conexão Direta Homologada (Scraping/Web)"
    elif is_of:
        meses_rotulo = "12 meses"
        meses_detalhe = "Até 12 meses (365 dias) de histórico inicial retroativo"
        meses_esperados = "12 meses completos (Resolução Conjunta BCB nº 1 / Open Finance)"
        tipo_conexao = "Open Finance Regulado (Banco Central do Brasil)"
    else:
        meses_rotulo = "12 meses"
        meses_detalhe = "Até 12 meses de histórico inicial retroativo"
        meses_esperados = "12 meses (limite padrão da API Pluggy)"
        tipo_conexao = "Conexão Direta Homologada"

    # Lançamentos futuros
    if cid in (601, 618) or "itau" in nome_clean:
        lancamentos_futuros = "Até 90 dias futuros (status PENDING - boletos, débitos e Pix agendados)"
    elif cid in (626, 726) or "c6" in nome_clean:
        lancamentos_futuros = "Até 90 dias futuros (status PENDING - pagamentos agendados)"
    else:
        lancamentos_futuros = "Não aplicável (apenas transações passadas/consolidadas)"

    texto_campo = f"{nome} - {meses_rotulo}"

    return {
        "id": cid,
        "nome": nome,
        "tipo": tipo,
        "is_open_finance": is_of,
        "cor": cor,
        "supports_scheduled": sched,
        "texto_campo": texto_campo,
        "meses_rotulo": meses_rotulo,
        "meses_detalhe": meses_detalhe,
        "meses_esperados": meses_esperados,
        "dias_iniciais": 365,
        "atualizacoes_recentes": "Últimos 7 dias (frequente de 1 a 6 dias)",
        "lancamentos_futuros": lancamentos_futuros,
        "tipo_conexao": tipo_conexao,
        "motivos_retorno_menor": [
            ("Conta recente", "Se a conta bancária foi aberta há menos de 12 meses, o banco só possui dados a partir da data de abertura."),
            ("Sem movimentações", "Períodos em que o cliente não realizou nenhuma movimentação não geram registros de transação na API."),
            ("Faturas de cartão", "Transações de cartão de crédito só são disponibilizadas após o fechamento ou vencimento das faturas correspondentes."),
            ("Instabilidade do banco", "Alguns servidores bancários sofrem lentidão ou timeout ao buscar datas muito antigas; nesses casos, a Pluggy sincroniza o período que respondeu com sucesso.")
        ]
    }


# =============================================================================
# OTIMIZAÇÃO DE RENDERIZAÇÃO E MOVIMENTAÇÃO DE JANELA (WINDOWS & HIGH-DPI)
# =============================================================================
if sys.platform.startswith("win"):
    try:
        import ctypes
        # Ativa conscientização de DPI nativa do sistema (PROCESS_SYSTEM_DPI_AWARE = 1).
        # Permite que telas de alta resolução (125%, 150%, 4K) renderizem fontes e componentes
        # com nitidez total, enquanto a movimentação e arrasto da janela ficam a cargo da GPU (DWM).
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Desativa o rastreador de DPI automático do CustomTkinter, que interceptava o arrasto da
# janela, alternava a transparência para '-alpha 0.15' e reconstruía todos os canvas em loop,
# gerando o efeito de janela 'pesada', atraso de 1.5s na nova posição e distorções visuais.
ctk.deactivate_automatic_dpi_awareness()

try:
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
    # Neutraliza a checagem contínua (check_dpi_scaling) que pausava o loop de eventos por 1500ms
    ScalingTracker.check_dpi_scaling = lambda *args, **kwargs: None
except Exception:
    pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MonthPickerPopover:
    """Seleção flutuante moderna para escolha rápida de mês e ano"""
    def __init__(self, master, button, on_select_callback):
        self.master = master
        self.button = button
        self.on_select_callback = on_select_callback
        self.popover = None
        self.current_year = datetime.now().year
        self.selected_month = datetime.now().month

    def toggle(self):
        if self.popover and self.popover.winfo_exists():
            self.fechar()
            return
        self.abrir()

    def abrir(self):
        if self.popover and self.popover.winfo_exists():
            self.popover.destroy()

        self.popover = ctk.CTkToplevel(self.master)
        self.popover.overrideredirect(True)
        self.popover.configure(fg_color="#0B0F19")

        self.master.update_idletasks()
        bx = self.button.winfo_rootx()
        by = self.button.winfo_rooty() + self.button.winfo_height() + 4

        width = 250
        height = 210
        self.popover.geometry(f"{width}x{height}+{bx}+{by}")

        container = ctk.CTkFrame(
            self.popover,
            fg_color="#0F172A",
            border_width=2,
            border_color="#0284C7",
            corner_radius=10
        )
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Cabeçalho de Navegação de Ano
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill=tk.X, padx=10, pady=(8, 4))

        btn_prev_y = ctk.CTkButton(
            header,
            text="◀",
            width=28,
            height=26,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10, "bold"),
            command=self.ano_anterior
        )
        btn_prev_y.pack(side=tk.LEFT)

        self.lbl_year = ctk.CTkLabel(
            header,
            text=str(self.current_year),
            font=("Segoe UI", 14, "bold"),
            text_color="#38BDF8"
        )
        self.lbl_year.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_next_y = ctk.CTkButton(
            header,
            text="▶",
            width=28,
            height=26,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10, "bold"),
            command=self.proximo_ano
        )
        btn_next_y.pack(side=tk.RIGHT)

        # Grade de Meses (4 colunas x 3 linhas)
        self.grid_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))

        self._montar_meses()

        self.popover.bind("<Escape>", lambda e: self.fechar())
        self.popover.focus_set()
        self.popover.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event):
        def check():
            if not self.popover or not self.popover.winfo_exists():
                return
            try:
                focused = self.popover.focus_get()
                if not focused or not str(focused).startswith(str(self.popover)):
                    self.fechar()
            except Exception:
                pass
        self.popover.after(150, check)

    def fechar(self):
        if self.popover and self.popover.winfo_exists():
            self.popover.destroy()
            self.popover = None

    def ano_anterior(self):
        self.current_year -= 1
        self.lbl_year.configure(text=str(self.current_year))
        self._montar_meses()

    def proximo_ano(self):
        self.current_year += 1
        self.lbl_year.configure(text=str(self.current_year))
        self._montar_meses()

    def _montar_meses(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        for i in range(12):
            mes_num = i + 1
            abrev = MESES_ABREV[i]
            row = i // 4
            col = i % 4

            is_selected = (self.selected_month == mes_num and self.current_year == datetime.now().year)
            bg = "#0284C7" if is_selected else "#1E293B"
            hover = "#0369A1" if is_selected else "#334155"

            btn = ctk.CTkButton(
                self.grid_frame,
                text=abrev,
                width=52,
                height=32,
                fg_color=bg,
                hover_color=hover,
                font=("Segoe UI", 10, "bold" if is_selected else "normal"),
                command=lambda m=mes_num: self.selecionar_mes(m)
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

        for c in range(4):
            self.grid_frame.columnconfigure(c, weight=1)
        for r in range(3):
            self.grid_frame.rowconfigure(r, weight=1)

    def selecionar_mes(self, mes_num):
        self.selected_month = mes_num
        self.fechar()
        if self.on_select_callback:
            self.on_select_callback(self.current_year, mes_num)


class MascaraDataVar(tk.StringVar):
    """
    StringVar reativa com máscara de data brasileira (DD/MM/AAAA) corrigida.
    Garante que as barras sejam inseridas sem fazer o cursor pular para trás
    do próximo número ou prender a digitação, suportando edição e BackSpace.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._entry_widget = None
        self._is_formatting = False

    def vincular_entry(self, entry_widget):
        self._entry_widget = entry_widget
        inner = getattr(entry_widget, '_entry', entry_widget)
        inner.bind("<KeyPress>", self._ao_pressionar_tecla, add="+")
        inner.bind("<KeyRelease>", self._ao_soltar_tecla, add="+")
        inner.bind("<<Paste>>", self._ao_colar, add="+")

    def _ao_pressionar_tecla(self, event):
        inner = getattr(self._entry_widget, '_entry', self._entry_widget)

        # Permitir atalhos (Ctrl+C, Ctrl+V, Ctrl+A, Ctrl+Z, etc.)
        if event.state & 4:
            return

        # Teclas de navegação comuns
        if event.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Tab', 'Escape'):
            return

        # BackSpace inteligente
        if event.keysym == 'BackSpace':
            try:
                if inner.select_present():
                    return
                pos = inner.index(tk.INSERT)
                val = inner.get()
                # Se o cursor estiver logo após uma barra '/', apaga a barra e o número anterior
                if pos > 0 and pos <= len(val):
                    if val[pos - 1] == '/':
                        inner.delete(pos - 2, pos)
                        self._reformatar(offset=-1)
                        return "break"
            except Exception:
                pass
            return

        # Delete inteligente
        if event.keysym == 'Delete':
            try:
                if inner.select_present():
                    return
                pos = inner.index(tk.INSERT)
                val = inner.get()
                if pos < len(val) and val[pos] == '/':
                    inner.delete(pos, pos + 2)
                    self._reformatar()
                    return "break"
            except Exception:
                pass
            return

        char = event.char
        if not char:
            return

        # Se o usuário digitou uma barra manualmente
        if char == '/':
            pos = inner.index(tk.INSERT)
            val = inner.get()
            if pos < len(val) and val[pos] == '/':
                inner.icursor(pos + 1)
                return "break"
            elif pos in (2, 5):
                return "break"

        # Apenas dígitos numéricos são aceitos
        if not char.isdigit():
            return "break"

        # Se já tiver 8 dígitos e não houver seleção de texto, bloqueia
        digits = [c for c in inner.get() if c.isdigit()]
        if len(digits) >= 8 and not inner.select_present():
            return "break"

    def _ao_soltar_tecla(self, event):
        if event.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Tab', 'Escape', 'BackSpace', 'Delete'):
            return
        if event.state & 4:
            return
        self._reformatar()

    def _ao_colar(self, event):
        if self._entry_widget:
            inner = getattr(self._entry_widget, '_entry', self._entry_widget)
            inner.after(10, self._reformatar)

    def _reformatar(self, offset=0):
        if self._is_formatting or not self._entry_widget:
            return
        self._is_formatting = True
        try:
            inner = getattr(self._entry_widget, '_entry', self._entry_widget)
            raw = inner.get()
            pos = inner.index(tk.INSERT)

            # Conta a quantidade de dígitos que existiam antes do cursor
            digits_before = sum(1 for c in raw[:pos] if c.isdigit()) + offset
            if digits_before < 0:
                digits_before = 0

            # Extrai apenas dígitos (máximo 8: DDMMAAAA)
            digits = [c for c in raw if c.isdigit()][:8]

            formatted = ""
            for i, d in enumerate(digits):
                if i in (2, 4):
                    formatted += "/"
                formatted += d

            # Se digitou o 2º ou 4º dígito na posição correta, adiciona a barra
            if len(digits) == 2 and pos == 2:
                formatted += "/"
            elif len(digits) == 4 and pos in (4, 5):
                formatted += "/"

            if raw != formatted:
                inner.delete(0, tk.END)
                inner.insert(0, formatted)
                super().set(formatted)

                # Calcular a posição correta do cursor para que nunca pule para trás
                target_pos = 0
                counted = 0
                for idx, c in enumerate(formatted):
                    if c.isdigit():
                        counted += 1
                    if counted >= digits_before:
                        target_pos = idx + 1
                        break
                else:
                    target_pos = len(formatted)

                # Pula a barra para que o cursor fique na frente e não atrás
                if target_pos < len(formatted) and formatted[target_pos] == '/':
                    target_pos += 1
                elif target_pos == 2 and len(formatted) > 2 and formatted[2] == '/':
                    target_pos = 3
                elif target_pos == 5 and len(formatted) > 5 and formatted[5] == '/':
                    target_pos = 6

                inner.icursor(target_pos)
            else:
                super().set(raw)
        finally:
            self._is_formatting = False

    def set(self, value):
        super().set(value)
        if self._entry_widget:
            try:
                inner = getattr(self._entry_widget, '_entry', self._entry_widget)
                if inner.get() != str(value):
                    inner.delete(0, tk.END)
                    inner.insert(0, str(value))
            except Exception:
                pass


def formatar_data_br(date_str):
    """Converte datas ISO (YYYY-MM-DD ou com timestamp) para DD/MM/AAAA"""
    if not date_str:
        return ""
    try:
        clean = str(date_str).strip().split('T')[0]
        parts = clean.split('-')
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return clean
    except Exception:
        return str(date_str)


def formatar_data_hora_br(dt_str):
    """Converte ISO timestamp para DD/MM/AAAA HH:mm:ss"""
    if not dt_str:
        return ""
    try:
        clean = str(dt_str).replace('Z', '').split('.')[0]
        if 'T' in clean:
            d_part, t_part = clean.split('T')
            d_br = formatar_data_br(d_part)
            return f"{d_br} {t_part}"
        return clean
    except Exception:
        return str(dt_str)


def converter_br_para_iso(date_str):
    """Converte qualquer formato de data brasileiro para YYYY-MM-DD"""
    if not date_str:
        return ""
    clean = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', clean):
        return clean
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$', clean)
    if m:
        dia, mes, ano = m.groups()
        return f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
    digits = ''.join([c for c in clean if c.isdigit()])
    if len(digits) == 8:
        return f"{digits[4:8]}-{digits[2:4]}-{digits[0:2]}"
    return clean


def formatar_moeda_br(valor):
    """Formata valor numérico para R$ 1.250,50 de forma segura"""
    if valor is None:
        return "R$ 0,00"
    try:
        if isinstance(valor, str):
            valor = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        num = float(valor)
        negativo = num < 0
        num_abs = abs(num)
        formatado = f"{num_abs:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        prefixo = "-R$ " if negativo else "R$ "
        return f"{prefixo}{formatado}"
    except Exception:
        return f"R$ {valor}"


OPEN_FINANCE_PRODUCTS_DICT = {
    "ACCOUNTS": {
        "nome": "Contas Bancárias",
        "icone": "🏦",
        "desc": "Saldos em conta corrente/poupança, agência, conta e limites contratados"
    },
    "CREDIT_CARDS": {
        "nome": "Cartões de Crédito",
        "icone": "💳",
        "desc": "Faturas abertas e fechadas, limites totais/disponíveis e compras parceladas"
    },
    "TRANSACTIONS": {
        "nome": "Extratos e Movimentações",
        "icone": "📊",
        "desc": "Histórico detalhado de movimentações bancárias, transferências TED e PIX"
    },
    "INVESTMENTS": {
        "nome": "Investimentos",
        "icone": "📈",
        "desc": "Posições em renda fixa, títulos, fundos de investimento, ações e tesouro"
    },
    "LOANS": {
        "nome": "Empréstimos e Financiamentos",
        "icone": "📑",
        "desc": "Contratos de crédito, parcelas a vencer, taxas contratadas e saldos devedores"
    },
    "PAYMENT_DATA": {
        "nome": "Dados de Pagamentos",
        "icone": "💸",
        "desc": "Histórico de autorizações e liquidações de pagamentos"
    },
    "PAYMENTS": {
        "nome": "Iniciação de Pagamentos",
        "icone": "💸",
        "desc": "Autorização para iniciação e movimentação de pagamentos"
    },
    "IDENTITY": {
        "nome": "Dados Cadastrais",
        "icone": "👤",
        "desc": "Identificação e qualificação cadastral do titular da conta (PF ou PJ)"
    },
    "CUSTOMERS": {
        "nome": "Cadastro de Clientes",
        "icone": "👤",
        "desc": "Informações cadastrais e relacionamento formal com a instituição"
    },
    "BENEFITS": {
        "nome": "Benefícios e Recompensas",
        "icone": "🎁",
        "desc": "Programas de pontos, milhas e benefícios vinculados aos produtos"
    }
}

OPEN_FINANCE_PERMISSIONS_DICT = {
    # Contas & Saldos
    "ACCOUNTS_READ": {
        "categoria": "Contas & Saldos",
        "icone_cat": "🏦",
        "nome": "Identificação de Contas",
        "desc": "Permite visualizar tipo de conta, agência e número de conta."
    },
    "ACCOUNTS_BALANCES_READ": {
        "categoria": "Contas & Saldos",
        "icone_cat": "🏦",
        "nome": "Consulta de Saldos Bancários",
        "desc": "Permite visualizar saldo disponível, bloqueado e limite de cheque especial."
    },
    "ACCOUNTS_TRANSACTIONS_READ": {
        "categoria": "Contas & Saldos",
        "icone_cat": "🏦",
        "nome": "Histórico de Transações e Extrato",
        "desc": "Permite acessar histórico de movimentações, recebimentos, TED e PIX."
    },
    "ACCOUNTS_OVERDRAFT_LIMITS_READ": {
        "categoria": "Contas & Saldos",
        "icone_cat": "🏦",
        "nome": "Limites de Cheque Especial",
        "desc": "Permite consultar limites contratados de cheque especial."
    },
    # Cartões de Crédito
    "CREDIT_CARDS_ACCOUNTS_READ": {
        "categoria": "Cartões de Crédito",
        "icone_cat": "💳",
        "nome": "Identificação de Cartões",
        "desc": "Permite listar contas de cartão de crédito e bandeiras ativas."
    },
    "CREDIT_CARDS_ACCOUNTS_BILLS_READ": {
        "categoria": "Cartões de Crédito",
        "icone_cat": "💳",
        "nome": "Faturas e Vencimentos",
        "desc": "Permite consultar faturas abertas, fechadas, vencimentos e valores mínimos."
    },
    "CREDIT_CARDS_ACCOUNTS_TRANSACTIONS_READ": {
        "categoria": "Cartões de Crédito",
        "icone_cat": "💳",
        "nome": "Lançamentos e Compras no Cartão",
        "desc": "Permite consultar compras na fatura, parcelamentos e lançamentos futuros."
    },
    "CREDIT_CARDS_ACCOUNTS_LIMITS_READ": {
        "categoria": "Cartões de Crédito",
        "icone_cat": "💳",
        "nome": "Limites de Crédito do Cartão",
        "desc": "Permite verificar limite total contratado e limite disponível para compras."
    },
    # Cadastro PF & PJ
    "CUSTOMERS_PERSONAL_IDENTIFICATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "👤",
        "nome": "Identificação Pessoal (PF)",
        "desc": "Permite consultar nome completo, CPF, documento de identificação e filiação."
    },
    "CUSTOMERS_PERSONAL_QUALIFICATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "👤",
        "nome": "Qualificação Cadastral (PF)",
        "desc": "Permite consultar profissão informada, faixa de renda e patrimônio."
    },
    "CUSTOMERS_PERSONAL_FINANCIAL_RELATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "👤",
        "nome": "Relacionamento Financeiro (PF)",
        "desc": "Permite verificar data de abertura da conta e produtos contratados."
    },
    "CUSTOMERS_BUSINESS_IDENTIFICATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "🏢",
        "nome": "Identificação Empresarial (PJ)",
        "desc": "Permite consultar razão social, CNPJ, nome fantasia e representantes legais."
    },
    "CUSTOMERS_BUSINESS_QUALIFICATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "🏢",
        "nome": "Qualificação Empresarial (PJ)",
        "desc": "Permite consultar faturamento informado e ramo de atividade econômica."
    },
    "CUSTOMERS_BUSINESS_FINANCIAL_RELATIONS_READ": {
        "categoria": "Identificação e Cadastro",
        "icone_cat": "🏢",
        "nome": "Relacionamento Institucional (PJ)",
        "desc": "Permite verificar histórico de relacionamento empresarial com o banco."
    },
    # Investimentos
    "INVESTMENTS_READ": {
        "categoria": "Investimentos",
        "icone_cat": "📈",
        "nome": "Portfólio de Ativos e Fundos",
        "desc": "Permite listar ativos, títulos de renda fixa, fundos e posições em custódia."
    },
    "INVESTMENTS_BALANCES_READ": {
        "categoria": "Investimentos",
        "icone_cat": "📈",
        "nome": "Saldos e Posições Atualizadas",
        "desc": "Permite consultar valores aplicados, posições brutas e valores líquidos."
    },
    "INVESTMENTS_TRANSACTIONS_READ": {
        "categoria": "Investimentos",
        "icone_cat": "📈",
        "nome": "Movimentações de Aplicações",
        "desc": "Permite consultar histórico de aportes, resgates e rendimentos creditados."
    },
    # Operações de Crédito
    "LOANS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Contratos de Empréstimo",
        "desc": "Permite listar empréstimos ativos, prazos contratados e modalidades."
    },
    "LOANS_WARRANTIES_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Garantias Vinculadas ao Crédito",
        "desc": "Permite consultar garantias vinculadas às operações de crédito."
    },
    "LOANS_SCHEDULED_INSTALMENTS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Cronograma de Parcelas de Empréstimo",
        "desc": "Permite consultar parcelas futuras, datas de vencimento e valores."
    },
    "LOANS_PAYMENTS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Pagamentos e Amortizações",
        "desc": "Permite verificar parcelas de empréstimo quitadas ou amortizadas."
    },
    "FINANCINGS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Contratos de Financiamento",
        "desc": "Permite listar financiamentos imobiliários, veiculares e de bens."
    },
    "FINANCINGS_SCHEDULED_INSTALMENTS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Parcelas de Financiamentos",
        "desc": "Permite consultar cronograma de parcelas e amortizações futuras."
    },
    "FINANCINGS_PAYMENTS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Histórico de Financiamento Pago",
        "desc": "Permite verificar parcelas de financiamento já liquidadas."
    },
    "UNARRANGED_ACCOUNTS_OVERDRAFT_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Adiantamento a Depositante",
        "desc": "Permite consultar operações emergenciais de crédito em conta."
    },
    "INVOICE_FINANCINGS_READ": {
        "categoria": "Crédito e Financiamentos",
        "icone_cat": "📑",
        "nome": "Antecipação de Recebíveis",
        "desc": "Permite consultar operações de desconto de duplicatas e recebíveis."
    }
}


def analisar_situacao_consentimento(data):
    """
    Interpreta o recurso de consentimento retornado pela API da Pluggy
    (https://docs.pluggy.ai/pt/reference/consent/consent-retrieve)
    Calcula se o consentimento está Ativo, Expirado ou Desconectado,
    além de formatar datas, produtos e permissões concedidas.
    """
    if not isinstance(data, dict):
        return None

    revoked_at = data.get("revokedAt")
    expires_at = data.get("expiresAt")
    created_at = data.get("createdAt")
    raw_status = str(data.get("status") or "").upper().strip()

    revoked_str = formatar_data_hora_br(revoked_at) if revoked_at else None
    expires_str = formatar_data_hora_br(expires_at) if expires_at else None
    created_str = formatar_data_hora_br(created_at) if created_at else "N/A"

    # Datas parseadas
    dt_created = None
    if created_at:
        try:
            clean_c = str(created_at).replace('Z', '+00:00').split('+')[0]
            if '.' in clean_c:
                dt_created = datetime.strptime(clean_c, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt_created = datetime.strptime(clean_c, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            dt_created = None

    dt_exp = None
    if expires_at:
        try:
            clean_exp = str(expires_at).replace('Z', '+00:00').split('+')[0]
            if '.' in clean_exp:
                dt_exp = datetime.strptime(clean_exp, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt_exp = datetime.strptime(clean_exp, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            dt_exp = None

    agora_naive = datetime.utcnow()
    dias_restantes = None
    dias_passados = None
    pct_validade = 1.0

    if dt_exp and dt_created:
        total_seg = max(1.0, (dt_exp - dt_created).total_seconds())
        passado_seg = max(0.0, (agora_naive - dt_created).total_seconds())
        pct_validade = min(1.0, max(0.0, passado_seg / total_seg))
    elif dt_exp:
        if dt_exp > agora_naive:
            d_rest = (dt_exp - agora_naive).days
            pct_validade = min(1.0, max(0.0, 1.0 - (d_rest / 365.0)))
        else:
            pct_validade = 1.0

    if revoked_at or raw_status == "REVOKED":
        status_key = "REVOKED"
        status_titulo = "DESCONECTADO"
        cor_status = "#F43F5E"  # Rose / Vermelho
        cor_bg = "#4C0519"
        cor_border = "#881337"
        icone = "●"
        detalhe = f"Conta desconectada pelo usuário ou pela instituição em {revoked_str or 'data informada'}."
        msg_prazo = f"Desconectado em {revoked_str}" if revoked_str else "Conta Desconectada"
        severidade_prazo = "desconectado"
        pct_validade = 1.0
        recomendacao_titulo = "Conta Desconectada"
        recomendacao_texto = "O titular da conta ou o banco desconectou esta autorização. O compartilhamento foi encerrado permanentemente. Para retomar a sincronização e voltar a receber transações, solicite a reconexão pelo botão abaixo."
        tipo_acao = "desconectado"
    elif raw_status == "WAITING_AUTHORISATION":
        status_key = "WAITING_AUTHORISATION"
        status_titulo = "AGUARDANDO AUTORIZAÇÃO"
        cor_status = "#38BDF8"  # Azul celeste
        cor_bg = "#0C4A6E"
        cor_border = "#0284C7"
        icone = "●"
        detalhe = "O fluxo de consentimento foi iniciado, mas o titular ainda não concluiu a autorização no aplicativo do banco."
        msg_prazo = "Aguardando confirmação no app do banco"
        severidade_prazo = "pendente"
        pct_validade = 0.0
        recomendacao_titulo = "Autorização Pendente"
        recomendacao_texto = "Oriente o cliente a abrir o aplicativo oficial da instituição financeira e aprovar o compartilhamento de dados do Open Finance."
        tipo_acao = "aguardando"
    elif expires_at:
        if dt_exp and dt_exp < agora_naive:
            status_key = "EXPIRED"
            status_titulo = "EXPIRADO"
            cor_status = "#F59E0B"  # Âmbar
            cor_bg = "#451A03"
            cor_border = "#78350F"
            icone = "●"
            dias_passados = (agora_naive - dt_exp).days
            detalhe = f"Consentimento expirou em {expires_str} (há {dias_passados} dias)."
            msg_prazo = f"Expirou há {dias_passados} dias ({expires_str})"
            severidade_prazo = "expirado"
            pct_validade = 1.0
            recomendacao_titulo = "Renovação de Consentimento Necessária"
            recomendacao_texto = "O prazo máximo de 1 ano do consentimento regulatório expirou. Para reativar o fluxo e continuar recebendo extratos e saldos sem perder o histórico, solicite ao cliente a renovação pelo Pluggy Connect."
            tipo_acao = "expirado"
        else:
            status_key = "ACTIVE"
            status_titulo = "ATIVO / AUTORIZADO"
            cor_status = "#10B981"  # Verde esmeralda
            cor_bg = "#064E3B"
            cor_border = "#047857"
            icone = "●"
            if dt_exp:
                dias_restantes = max(0, (dt_exp - agora_naive).days)
                if dias_restantes > 0:
                    detalhe = f"Consentimento ativo e válido até {expires_str} (restam {dias_restantes} dias)."
                    msg_prazo = f"Restam {dias_restantes} dias de validade (até {expires_str})"
                    severidade_prazo = "alerta" if dias_restantes <= 30 else "excelente"
                else:
                    detalhe = f"Consentimento ativo e válido até {expires_str} (expira hoje)."
                    msg_prazo = f"Expira hoje ({expires_str})"
                    severidade_prazo = "alerta"
            else:
                detalhe = f"Consentimento ativo até {expires_str}."
                msg_prazo = f"Válido até {expires_str}"
                severidade_prazo = "excelente"
            recomendacao_titulo = "Consentimento Saudável e Vigente"
            recomendacao_texto = "A autorização Open Finance está em plena conformidade com as regras do Banco Central. Todas as sincronizações de dados e transações operam regularmente sem nenhuma ação necessária."
            tipo_acao = "ativo"
    else:
        status_key = "ACTIVE"
        status_titulo = "ATIVO (INDETERMINADO)"
        cor_status = "#10B981"
        cor_bg = "#064E3B"
        cor_border = "#047857"
        icone = "●"
        detalhe = "Consentimento ativo sem data limite de expiração estipulada."
        msg_prazo = "Vigência Contínua / Sem Data Limite"
        severidade_prazo = "excelente"
        pct_validade = 1.0
        recomendacao_titulo = "Consentimento Ativo e Vigente"
        recomendacao_texto = "A autorização Open Finance está em plena conformidade com as regras do Banco Central. Todas as sincronizações de dados e transações operam regularmente sem nenhuma ação necessária."
        tipo_acao = "ativo"

    # Enriquecimento de Produtos (com inferência caso o objeto consentimento não traga array explícito)
    raw_prods = list(data.get("products", []) or [])
    if not raw_prods and isinstance(data.get("connector"), dict):
        raw_prods = list(data["connector"].get("products", []) or [])
    if not raw_prods:
        perms = data.get("openFinancePermissionsGranted", []) or []
        for p in perms:
            p_up = str(p).upper()
            if "ACCOUNT" in p_up and "ACCOUNTS" not in raw_prods:
                raw_prods.append("ACCOUNTS")
            if "TRANSACTION" in p_up and "TRANSACTIONS" not in raw_prods:
                raw_prods.append("TRANSACTIONS")
            if "CREDIT_CARD" in p_up and "CREDIT_CARDS" not in raw_prods:
                raw_prods.append("CREDIT_CARDS")
            if "PAYMENT" in p_up and "PAYMENT_INITIATION" not in raw_prods:
                raw_prods.append("PAYMENT_INITIATION")
            if "INVESTMENT" in p_up and "INVESTMENTS" not in raw_prods:
                raw_prods.append("INVESTMENTS")
            if "LOAN" in p_up and "LOANS" not in raw_prods:
                raw_prods.append("LOANS")

    # Fallback seguro: instituições financeiras autorizadas possuem no mínimo contas e transações ativas
    if not raw_prods and (data.get("connector") or data.get("status") == "ACTIVE"):
        raw_prods = ["ACCOUNTS", "TRANSACTIONS"]

    products_enriched = []
    for p in raw_prods:
        pkey = str(p).upper().strip()
        pinfo = OPEN_FINANCE_PRODUCTS_DICT.get(pkey, {
            "nome": pkey.replace("_", " ").title(),
            "icone": "📦",
            "desc": "Recursos bancários autorizados para compartilhamento via Open Finance"
        })
        products_enriched.append({
            "key": pkey,
            "nome": pinfo["nome"],
            "icone": pinfo["icone"],
            "desc": pinfo["desc"]
        })

    # Enriquecimento de Permissões
    raw_perms = data.get("openFinancePermissionsGranted", []) or []
    permissions_enriched = []
    permissions_by_category = {}
    for perm in raw_perms:
        perm_key = str(perm).strip()
        perm_info = OPEN_FINANCE_PERMISSIONS_DICT.get(perm_key, {
            "categoria": "Outras Permissões",
            "icone_cat": "🛡️",
            "nome": perm_key.replace("_", " ").title(),
            "desc": "Escopo regulatório de acesso a dados Open Finance."
        })
        p_obj = {
            "key": perm_key,
            "categoria": perm_info.get("categoria", "Geral"),
            "icone_cat": perm_info.get("icone_cat", "🛡️"),
            "nome": perm_info.get("nome", perm_key),
            "desc": perm_info.get("desc", "")
        }
        permissions_enriched.append(p_obj)
        cat = p_obj["categoria"]
        if cat not in permissions_by_category:
            permissions_by_category[cat] = []
        permissions_by_category[cat].append(p_obj)

    # Conector / Instituição se disponível
    connector = data.get("connector") or {}
    banco_nome = connector.get("name") or None
    banco_id = str(connector.get("id")) if connector.get("id") is not None else None
    banco_cor = normalizar_cor_hex(connector.get("primaryColor"), fallback="#6366F1")
    raw_tipo = connector.get("type") or ""
    tipo_map = {
        "PERSONAL_BANK": "Banco - Pessoa Física",
        "BUSINESS_BANK": "Banco - Pessoa Jurídica",
        "INVESTMENT": "Corretora / Investimentos",
        "INVOICE": "Emissor de Cartão / Faturas",
        "OTHER": "Conector Pluggy"
    }
    banco_tipo = tipo_map.get(raw_tipo, raw_tipo or "Instituição Financeira")

    cid_val = str(data.get("id") or data.get("consentId") or data.get("_searched_consent_id") or "").strip()
    item_val = str(data.get("itemId") or data.get("item_id") or data.get("_searched_item_id") or "").strip()
    if not cid_val or cid_val in ("N/A", "None", "-"):
        cid_val = str(data.get("_searched_id") or "N/A")
    if not item_val or item_val in ("N/A", "None", "-"):
        item_val = str(data.get("_searched_item_id") or "N/A")

    return {
        "status_key": status_key,
        "status_titulo": status_titulo,
        "icone": icone,
        "cor_status": cor_status,
        "cor_bg": cor_bg,
        "cor_border": cor_border,
        "detalhe": detalhe,
        "created_str": created_str,
        "expires_str": expires_str or "Sem expiração",
        "revoked_str": revoked_str or "Não desconectado",
        "id": cid_val,
        "item_id": item_val,
        "products": raw_prods,
        "permissions": raw_perms,
        # Campos Enriquecidos
        "dias_restantes": dias_restantes,
        "dias_passados": dias_passados,
        "pct_validade": pct_validade,
        "msg_prazo": msg_prazo,
        "severidade_prazo": severidade_prazo,
        "products_enriched": products_enriched,
        "permissions_enriched": permissions_enriched,
        "permissions_by_category": permissions_by_category,
        "banco_nome": banco_nome,
        "banco_id": banco_id,
        "banco_cor": banco_cor,
        "banco_tipo": banco_tipo,
        "recomendacao_titulo": recomendacao_titulo,
        "recomendacao_texto": recomendacao_texto,
        "tipo_acao": tipo_acao,
        "all_consents_count": data.get("_all_consents_count")
    }


ERROS_DIAGNOSTICO_MAP = {
    "INVALID_CREDENTIALS": {
        "titulo": "Credenciais Rejeitadas pelo Banco",
        "explicacao": "As informações de acesso (usuário, senha, agência ou CPF) não foram reconhecidas pelo aplicativo da instituição financeira.",
        "acao": "Oriente o cliente a conferir os dados no aplicativo oficial do banco e tentar novamente pelo botão de reconexão.",
        "severidade": "alta"
    },
    "INVALID_CREDENTIALS_2FA": {
        "titulo": "Código de Token / 2FA Incorreto ou Expirado",
        "explicacao": "O código temporário de segurança (SMS, token do app ou push) digitado pelo usuário expirou ou continha divergência.",
        "acao": "Ao gerar um novo código no app do banco, digite-o de imediato para evitar a expiração do tempo limite.",
        "severidade": "alta"
    },
    "ACCOUNT_LOCKED": {
        "titulo": "Acesso Preventivamente Bloqueado no Banco",
        "explicacao": "O internet banking foi temporariamente bloqueado pela instituição financeira por medidas de segurança ou tentativas incorretas.",
        "acao": "O titular da conta deve efetuar o desbloqueio no aplicativo ou canais de atendimento do próprio banco antes de tentar reconectar.",
        "severidade": "critica"
    },
    "SITE_NOT_AVAILABLE": {
        "titulo": "Instituição Bancária em Oscilação Temporária",
        "explicacao": "O sistema ou aplicativo do próprio banco está passando por uma oscilação técnica momentânea ou manutenção programada.",
        "acao": "Fique tranquilo: esta é uma oscilação no servidor do banco. Aguarde alguns minutos para que o serviço seja restabelecido.",
        "severidade": "media"
    },
    "USER_INPUT_TIMEOUT": {
        "titulo": "Tempo de Confirmação no Celular Esgotado",
        "explicacao": "O tempo para confirmar a notificação no celular ou digitar o token de segurança expirou.",
        "acao": "Ao reconectar, certifique-se de estar com o celular em mãos para aprovar a autorização de imediato.",
        "severidade": "media"
    },
    "ALREADY_LOGGED_IN": {
        "titulo": "Sessão Aberta em Outro Aparelho",
        "explicacao": "O banco identificou que o cliente já está conectado em outro celular ou computador e bloqueou acessos simultâneos.",
        "acao": "Basta fechar o aplicativo do banco em outros dispositivos, aguardar cerca de 2 minutos e tentar a sincronização novamente.",
        "severidade": "media"
    },
    "CONNECTOR_ERROR": {
        "titulo": "Oscilação Temporária de Comunicação com o Banco",
        "explicacao": "Houve uma instabilidade pontual na troca de informações com a instituição financeira.",
        "acao": "Não se preocupe: aguarde alguns instantes e solicite uma nova sincronização. Não é necessário recadastrar a conta.",
        "severidade": "alta"
    },
    "UNEXPECTED_ERROR": {
        "titulo": "Instabilidade Momentânea na Resposta do Banco",
        "explicacao": "O banco demorou para responder ou enviou uma resposta fora do padrão esperado pelo Open Finance.",
        "acao": "Aguarde alguns instantes e tente atualizar novamente. A maioria dessas oscilações se normaliza rapidamente.",
        "severidade": "alta"
    },
    "WAITING_USER_INPUT": {
        "titulo": "Aguardando Confirmação do Usuário (Token / MFA)",
        "explicacao": "A instituição bancária enviou uma solicitação de segurança (código SMS, aprovação no app ou token).",
        "acao": "Abra o fluxo de conexão para que o usuário aprove a autorização no aplicativo.",
        "severidade": "atencao"
    },
    "OUTDATED": {
        "titulo": "Sessão Bancária Expirada / Reconexão Necessária",
        "explicacao": "A autorização temporária de acesso do banco expirou e precisa ser renovada pelo titular.",
        "acao": "Solicite ao cliente que confirme o acesso pelo Pluggy Connect para reativar as sincronizações.",
        "severidade": "atencao"
    },
    "CONSENT_REVOKED": {
        "titulo": "Compartilhamento Cancelado no Banco",
        "explicacao": "O consentimento Open Finance foi cancelado no aplicativo do banco pelo titular da conta.",
        "acao": "Para voltar a receber as movimentações, oriente o titular a criar uma nova autorização de conexão.",
        "severidade": "critica"
    },
    "CONSENT_EXPIRED": {
        "titulo": "Prazo de Compartilhamento Concluído",
        "explicacao": "O prazo regulatório do consentimento Open Finance chegou ao fim.",
        "acao": "Basta abrir o fluxo de conexão para renovar a autorização por mais um período.",
        "severidade": "atencao"
    },
    "LOGIN_ERROR": {
        "titulo": "Divergência de Autenticação no Banco",
        "explicacao": "Não foi possível concluir a validação junto à instituição financeira com os dados informados.",
        "acao": "Verifique se as credenciais bancárias e autorizações no app do banco estão atualizadas e tente reconectar.",
        "severidade": "alta"
    },
    "USER_AUTHORIZATION_REVOKED": {
        "titulo": "Conta Desconectada pelo Usuário",
        "explicacao": "O titular da conta desconectou o acesso ou cancelou as permissões do Open Finance diretamente no aplicativo do banco.",
        "acao": "Para voltar a receber as transações e extratos, utilize o botão 'Reconectar Item' para que o cliente realize uma nova autenticação.",
        "severidade": "critica"
    },
    "USER_AUTHORIZATION_NOT_GRANTED": {
        "titulo": "Autorização Não Concedida",
        "explicacao": "O titular da conta iniciou o fluxo mas não confirmou o compartilhamento no aplicativo do banco.",
        "acao": "Oriente o cliente a concluir todas as etapas de autorização no aplicativo da instituição bancária.",
        "severidade": "alta"
    },
    "USER_AUTHORIZATION_EXPIRED": {
        "titulo": "Autorização do Usuário Expirada",
        "explicacao": "O tempo concedido para autorização expirou antes da conclusão da autenticação.",
        "acao": "Inicie uma nova tentativa de conexão com o banco pelo Pluggy Connect.",
        "severidade": "alta"
    },
    "RATE_LIMIT_EXCEEDED": {
        "titulo": "Limite de Requisições Atingido",
        "explicacao": "Foram feitas muitas tentativas de sincronização em um curto intervalo de tempo.",
        "acao": "Aguarde cerca de 2 a 5 minutos antes de solicitar uma nova sincronização.",
        "severidade": "media"
    },
    "ITEM_QUOTA_EXCEEDED": {
        "titulo": "Limite de Conexões da Conta Atingido",
        "explicacao": "O limite de itens e conexões contratadas na assinatura da Pluggy foi atingido.",
        "acao": "Acesse o painel da Pluggy para verificar o plano contratado ou desconectar itens antigos.",
        "severidade": "alta"
    }
}


MAPA_CODIGOS_TRADUCAO = {
    "USER_AUTHORIZATION_REVOKED": "Autorização Desconectada pelo Usuário",
    "USER_AUTHORIZATION_NOT_GRANTED": "Autorização Não Concedida",
    "USER_AUTHORIZATION_EXPIRED": "Autorização Expirada",
    "LOGIN_ERROR": "Falha de Autenticação no Banco",
    "OUTDATED": "Sessão Bancária Expirada",
    "INVALID_CREDENTIALS": "Credenciais Rejeitadas pelo Banco",
    "INVALID_CREDENTIALS_2FA": "Token / 2FA Incorreto ou Expirado",
    "ACCOUNT_LOCKED": "Acesso Bloqueado no Banco",
    "SITE_NOT_AVAILABLE": "Banco em Oscilação Temporária",
    "USER_INPUT_TIMEOUT": "Tempo de Confirmação Esgotado",
    "ALREADY_LOGGED_IN": "Sessão Aberta em Outro Aparelho",
    "CONNECTOR_ERROR": "Oscilação no Conector Bancário",
    "UNEXPECTED_ERROR": "Instabilidade na Resposta do Banco",
    "WAITING_USER_INPUT": "Aguardando Confirmação no Celular",
    "CONSENT_REVOKED": "Compartilhamento Desconectado",
    "CONSENT_EXPIRED": "Consentimento Expirado",
    "RATE_LIMIT_EXCEEDED": "Limite de Tentativas Excedido",
    "ITEM_QUOTA_EXCEEDED": "Limite de Conexões Atingido",
    "UNSUPPORTED_PRODUCT": "Produto Não Suportado pelo Banco",
    "UPDATED": "Atualizado com Sucesso",
    "UPDATING": "Sincronização em Andamento",
    "WAITING_USER_ACTION": "Aguardando Ação do Usuário"
}


def traduzir_codigo_erro_pluggy(raw_code):
    """Traduz códigos técnicos da API Pluggy para títulos em português compreensíveis."""
    if not raw_code:
        return "Erro Não Especificado"
    c_clean = str(raw_code).strip()
    if c_clean in MAPA_CODIGOS_TRADUCAO:
        return MAPA_CODIGOS_TRADUCAO[c_clean]
    if "REVOKED" in c_clean:
        return "Desconectado pelo Usuário"
    if "EXPIRED" in c_clean:
        return "Autorização Expirada"
    if "TIMEOUT" in c_clean:
        return "Tempo Limite Esgotado"
    if "CREDENTIAL" in c_clean:
        return "Credenciais Incorretas"
    if "LOCKED" in c_clean:
        return "Acesso Bloqueado no Banco"
    return c_clean.replace("_", " ").title()


MAPA_MENSAGENS_TRADUCAO = {
    "The user revoked the necessary permissions for their account.": "O usuário desconectou ou cancelou as permissões de acesso da conta no aplicativo do banco.",
    "The user has not granted the necessary permissions for their account.": "O usuário não concedeu as permissões necessárias no aplicativo do banco.",
    "The credentials provided are invalid.": "As informações de acesso digitadas foram recusadas pelo banco.",
    "Invalid credentials.": "Credenciais de acesso incorretas ou rejeitadas pelo aplicativo do banco.",
    "Invalid credentials": "Credenciais de acesso incorretas ou rejeitadas pelo aplicativo do banco.",
    "Site not available.": "O sistema ou aplicativo do banco está passando por oscilação momentânea.",
    "Site not available": "O sistema ou aplicativo do banco está passando por oscilação momentânea.",
    "Already logged in.": "O banco identificou que o usuário já está conectado em outro aparelho.",
    "Already logged in": "O banco identificou que o usuário já está conectado em outro aparelho.",
    "User input timeout.": "O tempo para aprovar a autorização ou digitar o token no celular esgotou.",
    "User input timeout": "O tempo para aprovar a autorização ou digitar o token no celular esgotou.",
    "Connector error.": "Oscilação temporária na comunicação entre a Pluggy e a instituição bancária.",
    "Connector error": "Oscilação temporária na comunicação entre a Pluggy e a instituição bancária.",
    "Unexpected error.": "O banco demorou para responder ou enviou uma resposta fora do padrão esperado.",
    "Unexpected error": "O banco demorou para responder ou enviou uma resposta fora do padrão esperado.",
    "Account is locked.": "Acesso preventivamente bloqueado pela instituição financeira por segurança.",
    "Account is locked": "Acesso preventivamente bloqueado pela instituição financeira por segurança.",
    "Rate limit exceeded.": "Muitas tentativas realizadas em curto intervalo. Aguarde alguns instantes."
}


def traduzir_mensagem_erro_pluggy(raw_msg):
    """Traduz mensagens em inglês da API Pluggy para explicações em português claro."""
    if not raw_msg:
        return "Nenhum detalhe adicional fornecido pela instituição."
    m_clean = str(raw_msg).strip()
    if m_clean in MAPA_MENSAGENS_TRADUCAO:
        return MAPA_MENSAGENS_TRADUCAO[m_clean]
    m_lower = m_clean.lower()
    if "user revoked the necessary permissions" in m_lower or "permissions for their account" in m_lower:
        return "O titular desconectou ou cancelou as permissões de acesso da conta no aplicativo do banco."
    if "not granted the necessary permissions" in m_lower:
        return "O cliente não concluiu a autorização de permissões no aplicativo do banco."
    if "invalid credentials" in m_lower:
        return "Credenciais de acesso (senha, usuário ou chave) rejeitadas pelo banco."
    if "already logged in" in m_lower:
        return "Sessão já aberta em outro dispositivo no internet banking."
    if "site not available" in m_lower or "connector error" in m_lower:
        return "Instabilidade ou manutenção momentânea no servidor da instituição bancária."
    if "user input timeout" in m_lower or "timed out" in m_lower:
        return "Tempo para confirmação no celular ou digitação do token esgotado."
    if "account is locked" in m_lower or "account locked" in m_lower:
        return "Acesso bloqueado temporariamente pelo aplicativo do próprio banco."
    return m_clean

STATUS_ITEM_MAP = {
    "UPDATED": {
        "label": "ATUALIZADO (SAUDÁVEL)",
        "cor": "#10B981",
        "bg": "#064E3B",
        "border": "#047857",
        "icone": "✓",
        "resumo": "Conexão Íntegra e Saudável",
        "explicacao": "Os dados foram sincronizados com sucesso e estão atualizados junto à instituição.",
        "acao": "Nenhuma intervenção necessária. Os dados estão disponíveis e atualizados para consulta."
    },
    "UPDATING": {
        "label": "SINCRONIZANDO...",
        "cor": "#38BDF8",
        "bg": "#0C4A6E",
        "border": "#0284C7",
        "icone": "⟳",
        "resumo": "Atualização em Andamento",
        "explicacao": "A Pluggy está se comunicando com a instituição e coletando os dados mais recentes.",
        "acao": "Aguarde o término da sincronização (geralmente leva de 30 a 90 segundos)."
    },
    "WAITING_USER_INPUT": {
        "label": "AGUARDANDO USUÁRIO (MFA)",
        "cor": "#F59E0B",
        "bg": "#451A03",
        "border": "#78350F",
        "icone": "⚠",
        "resumo": "Interação de Segurança Pendente",
        "explicacao": "A instituição bancária enviou um desafio de segurança (MFA, SMS, push ou token).",
        "acao": "O usuário precisa preencher o token no widget do Pluggy Connect para liberar o acesso."
    },
    "LOGIN_ERROR": {
        "label": "FALHA DE AUTENTICAÇÃO",
        "cor": "#F43F5E",
        "bg": "#4C0519",
        "border": "#881337",
        "icone": "✗",
        "resumo": "Erro no Login Bancário",
        "explicacao": "Não foi possível acessar a conta bancária. As credenciais falharam ou a conta foi desconectada.",
        "acao": "Solicite ao cliente para verificar os dados e reconectar através do Pluggy Connect."
    },
    "OUTDATED": {
        "label": "DESATUALIZADO (REQUER LOGIN)",
        "cor": "#FB923C",
        "bg": "#431407",
        "border": "#9A3412",
        "icone": "⚠",
        "resumo": "Reconexão Necessária",
        "explicacao": "A sessão bancária expirou ou a instituição exigiu renovação de credenciais.",
        "acao": "Inicie o fluxo de reconexão do Pluggy Connect para restabelecer a coleta automática."
    },
    "WAITING_USER_ACTION": {
        "label": "AÇÃO NO APP BANCÁRIO PENDENTE",
        "cor": "#F59E0B",
        "bg": "#451A03",
        "border": "#78350F",
        "icone": "📱",
        "resumo": "Aprovação no App Bancário Pendente",
        "explicacao": "O banco enviou uma notificação push ou pede confirmação no app oficial.",
        "acao": "Oriente o cliente a abrir o aplicativo do banco no smartphone e autorizar o acesso."
    }
}


def analisar_diagnostico_item(data):
    """
    Analisa os dados de um Item retornado pela API da Pluggy (GET /items/{id})
    ou dados de consentimento, estruturando parecer amigável, recomendações
    de resolução, métricas do conector e status de produtos.
    """
    if not isinstance(data, dict):
        return None

    # Verifica se os dados representam um Consentimento
    is_consent = "openFinancePermissionsGranted" in data or ("products" in data and "connector" not in data)
    if is_consent:
        c_info = analisar_situacao_consentimento(data)
        if not c_info:
            return None
        return {
            "tipo_dado": "consent",
            "status_raw": c_info["status_key"],
            "status_label": f"CONSENTIMENTO {c_info['status_titulo']}",
            "status_cor": c_info["cor_status"],
            "status_bg": c_info["cor_bg"],
            "status_border": c_info["cor_border"],
            "status_icone": c_info["icone"],
            "exec_status": c_info["status_titulo"],
            "resumo_titulo": f"Consentimento Open Finance {c_info['status_titulo']}",
            "resumo_desc": c_info["detalhe"],
            "recomendacao": "Acesse a aba 'Situação do Consentimento' para gerenciar permissões e renovação." if c_info["status_key"] != "ACTIVE" else "Consentimento ativo e válido para consumo de dados da instituição.",
            "tem_erro": c_info["status_key"] != "ACTIVE",
            "erro_codigo": None if c_info["status_key"] == "ACTIVE" else c_info["status_key"],
            "erro_mensagem": None,
            "erro_provider": None,
            "banco_nome": "Open Finance Regulatório",
            "banco_cor": "#6366F1",
            "banco_tipo": "Consentimento Compartilhado",
            "banco_id": "-",
            "banco_url": None,
            "created_str": c_info["created_str"],
            "updated_str": c_info["expires_str"],
            "item_id": data.get("itemId") or "-",
            "consent_id": data.get("id") or "-",
            "client_user_id": data.get("clientUserId") or "-",
            "tentativas_falhas": 0,
            "webhook_url": data.get("webhookUrl") or "-",
            "produtos_detalhe": [
                {"nome": p, "status_str": "Concedido", "is_updated": c_info["status_key"] == "ACTIVE", "atualizado": c_info["expires_str"]}
                for p in c_info["products"]
            ]
        }

    # Item Pluggy padrão
    raw_status = (data.get("status") or "UNKNOWN").upper()
    exec_status = (data.get("executionStatus") or "UNKNOWN").upper()
    err_obj = data.get("error") if isinstance(data.get("error"), dict) else None

    status_info = STATUS_ITEM_MAP.get(raw_status, {
        "label": raw_status,
        "cor": "#94A3B8",
        "bg": "#1E293B",
        "border": "#334155",
        "icone": "●",
        "resumo": f"Status do Item: {raw_status}",
        "explicacao": "Status reportado pela API da Pluggy.",
        "acao": "Verifique os detalhes retornados no JSON para mais informações."
    })

    erro_codigo = None
    erro_mensagem = None
    erro_provider = None
    tem_erro = False
    erro_meta = None

    if err_obj:
        tem_erro = True
        erro_codigo = err_obj.get("code") or "ERRO"
        erro_mensagem = err_obj.get("message") or "Sem detalhes adicionais"
        erro_provider = err_obj.get("providerCode")
        erro_meta = ERROS_DIAGNOSTICO_MAP.get(erro_codigo)
    elif raw_status in ("LOGIN_ERROR", "OUTDATED"):
        tem_erro = True
        erro_codigo = raw_status
        erro_meta = ERROS_DIAGNOSTICO_MAP.get(raw_status)

    if tem_erro and erro_meta:
        resumo_titulo = erro_meta["titulo"]
        resumo_desc = erro_meta["explicacao"]
        recomendacao = erro_meta["acao"]
        status_cor = "#F43F5E" if erro_meta.get("severidade") in ("alta", "critica") else "#F59E0B"
        status_bg = "#4C0519" if erro_meta.get("severidade") in ("alta", "critica") else "#451A03"
        status_border = "#881337" if erro_meta.get("severidade") in ("alta", "critica") else "#78350F"
    elif tem_erro:
        resumo_titulo = f"Falha na Conexão [{erro_codigo}]"
        resumo_desc = erro_mensagem or "Ocorreu uma falha no processo de conexão com a instituição bancária."
        recomendacao = "Verifique as credenciais da conta ou solicite nova autenticação ao usuário."
        status_cor = "#F43F5E"
        status_bg = "#4C0519"
        status_border = "#881337"
    else:
        resumo_titulo = status_info["resumo"]
        resumo_desc = status_info["explicacao"]
        recomendacao = status_info["acao"]
        status_cor = status_info["cor"]
        status_bg = status_info["bg"]
        status_border = status_info["border"]

    connector = data.get("connector") or {}
    banco_nome = connector.get("name") or "Instituição Financeira"
    banco_id = str(connector.get("id")) if connector.get("id") is not None else "-"

    banco_cor = normalizar_cor_hex(connector.get("primaryColor"), fallback="#0284C7")

    raw_tipo = connector.get("type") or ""
    tipo_map = {
        "PERSONAL_BANK": "Banco - Pessoa Física",
        "BUSINESS_BANK": "Banco - Pessoa Jurídica",
        "INVESTMENT": "Corretora / Investimentos",
        "PAYMENT_PROCESSOR": "Processador de Pagamentos",
        "INVOICE": "Faturas / Telecom / Concessionária"
    }
    banco_tipo = tipo_map.get(raw_tipo, raw_tipo or "Instituição Bancária")
    banco_url = connector.get("institutionUrl")

    created_str = formatar_data_hora_br(data.get("createdAt"))
    updated_str = formatar_data_hora_br(data.get("updatedAt") or data.get("lastUpdatedAt"))
    failed_attempts = data.get("consecutiveFailedLoginAttempts", 0)

    # Detalhes de contas bancárias vinculadas ao item
    contas_raw = data.get("_contas_vinculadas") or data.get("accounts") or []
    contas_processadas = []
    subtipos_pt = {
        "CHECKING_ACCOUNT": "Conta Corrente",
        "SAVINGS_ACCOUNT": "Conta Poupança",
        "CREDIT_CARD": "Cartão de Crédito",
        "INVESTMENT_ACCOUNT": "Investimentos",
        "SALARY_ACCOUNT": "Conta Salário",
        "LOAN": "Empréstimo / Financiamento"
    }

    if isinstance(contas_raw, list):
        for acc in contas_raw:
            if isinstance(acc, dict):
                a_name = acc.get("name") or acc.get("marketingName") or "Conta Bancária"
                a_sub = acc.get("subtype") or acc.get("type") or "BANK"
                a_sub_pt = subtipos_pt.get(a_sub, a_sub)
                a_num = acc.get("number") or "-"
                a_agency = acc.get("agency") or (acc.get("bankData") or {}).get("agencyNumber") or "-"
                a_owner = acc.get("owner") or "-"
                a_balance = acc.get("balance")
                a_bal_str = formatar_moeda_br(a_balance) if a_balance is not None else "Não informado"
                contas_processadas.append({
                    "id": acc.get("id"),
                    "nome": a_name,
                    "tipo": a_sub_pt,
                    "numero": a_num,
                    "agencia": a_agency,
                    "titular": a_owner,
                    "saldo_str": a_bal_str,
                    "saldo_num": a_balance
                })

    # Detalhes de produtos (statusDetail)
    status_detail = data.get("statusDetail") or {}
    produtos_detalhe = []
    nomes_prod_pt = {
        "accounts": "Contas Bancárias",
        "transactions": "Transações / Extrato",
        "investments": "Investimentos",
        "identity": "Identidade e Titularidade",
        "paymentData": "Dados de Pagamento",
        "creditCards": "Cartões de Crédito"
    }

    item_desconectado = ("REVOKED" in str(erro_codigo or "").upper() or 
                         "REVOKED" in str(raw_status or "").upper() or 
                         "REVOKED" in str(erro_mensagem or "").upper())
    item_em_falha = tem_erro or raw_status in ("LOGIN_ERROR", "OUTDATED", "REVOKED")

    if isinstance(status_detail, dict) and status_detail:
        for k, v in status_detail.items():
            if isinstance(v, dict):
                p_nome = nomes_prod_pt.get(k, k.capitalize())
                p_is_up_raw = v.get("isUpdated", False)
                p_last = formatar_data_hora_br(v.get("lastUpdatedAt"))
                p_warn = v.get("warnings")

                # Se o Item está desconectado ou em falha de login, a sincronização não está ativa
                if item_desconectado:
                    p_tipo = "desconectado"
                    p_is_up = False
                    p_stat_str = "✕ Desconectado"
                    p_atualizado = f"Último sync: {p_last} (Interrompido)" if p_last and p_last != "N/A" else "Sincronização Interrompida"
                elif item_em_falha:
                    p_tipo = "erro"
                    p_is_up = False
                    p_stat_str = "⚠ Interrompido"
                    p_atualizado = f"Último sync: {p_last} (Requer Login)" if p_last and p_last != "N/A" else "Aguardando Reconexão"
                elif raw_status == "UPDATING":
                    p_tipo = "atualizando"
                    p_is_up = False
                    p_stat_str = "⟳ Sincronizando..."
                    p_atualizado = f"Sync anterior: {p_last}" if p_last and p_last != "N/A" else "Sincronizando..."
                else:
                    p_tipo = "ok" if p_is_up_raw else "pendente"
                    p_is_up = p_is_up_raw
                    p_stat_str = "✓ Sincronizado" if p_is_up else "⚠ Pendente"
                    p_atualizado = f"Sync: {p_last}" if p_last and p_last != "N/A" else "Sincronizado"

                produtos_detalhe.append({
                    "chave": k,
                    "nome": p_nome,
                    "tipo_status": p_tipo,
                    "is_updated": p_is_up,
                    "status_str": p_stat_str,
                    "atualizado": p_atualizado,
                    "data_raw": p_last,
                    "warnings": p_warn
                })

    # Verificação de incidentes oficiais em status.pluggy.ai
    incidentes_con = data.get("_incidentes_conector") or []
    if not incidentes_con and banco_id != "-":
        incidentes_con = buscar_incidentes_para_conector(banco_id, banco_nome)

    if incidentes_con:
        inc_tit = incidentes_con[0].get("title", "")
        if "🚨 ALERTA OPEN FINANCE:" not in recomendacao:
            recomendacao += f"\n\n🚨 ALERTA OPEN FINANCE: A instituição {banco_nome} está com incidente oficial registrado no status.pluggy.ai ('{inc_tit}'). Falhas ou transações ausentes podem decorrer desta instabilidade no banco transmissor."

    return {
        "tipo_dado": "item",
        "status_raw": raw_status,
        "status_label": status_info["label"],
        "status_cor": status_cor,
        "status_bg": status_bg,
        "status_border": status_border,
        "status_icone": status_info["icone"],
        "exec_status": exec_status,
        "resumo_titulo": resumo_titulo,
        "resumo_desc": resumo_desc,
        "recomendacao": recomendacao,
        "tem_erro": tem_erro,
        "erro_codigo": erro_codigo,
        "erro_codigo_traduzido": traduzir_codigo_erro_pluggy(erro_codigo),
        "erro_mensagem": erro_mensagem,
        "erro_mensagem_traduzida": traduzir_mensagem_erro_pluggy(erro_mensagem),
        "erro_provider": erro_provider,
        "banco_nome": banco_nome,
        "banco_cor": banco_cor,
        "banco_tipo": banco_tipo,
        "banco_id": banco_id,
        "banco_url": banco_url,
        "created_str": created_str,
        "updated_str": updated_str,
        "item_id": data.get("id") or "-",
        "consent_id": data.get("consentId") or "-",
        "client_user_id": data.get("clientUserId") or "-",
        "tentativas_falhas": failed_attempts,
        "webhook_url": data.get("webhookUrl") or "-",
        "produtos_detalhe": produtos_detalhe,
        "contas_vinculadas": contas_processadas,
        "incidentes_conector": incidentes_con
    }


class ModernPluggyApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Pluggy Open Finance Explorer & Diagnostics")
        self.geometry("1200x860")
        self.minsize(980, 720)

        tk.Tk.report_callback_exception = self._reportar_excecao_global
        self.definir_icone_janela()

        self.client_id = DEFAULT_CLIENT_ID
        self.client_secret = DEFAULT_CLIENT_SECRET
        self.api_key = None
        self.contas_map = {}
        self.raw_transactions_data = None
        self.current_transactions = []
        self.all_columns = ['date', 'description', 'amount', 'type', 'category', 'status', 'currencyCode', 'balance', 'id']
        self.visible_columns = ['date', 'description', 'amount', 'type', 'category', 'status']
        self.sort_column = 'date'
        self.sort_descending = True
        self.raw_item_data = None
        self.raw_consent_data = None
        self.item_diag_info = None

        self.json_matches_t1 = []
        self.json_current_match_t1 = -1
        self.json_matches_t2 = []
        self.json_current_match_t2 = -1
        self.json_matches_t3 = []
        self.json_current_match_t3 = -1

        # Navegação de Mês
        agora = datetime.now()
        self.nav_year = agora.year
        self.nav_month = agora.month

        # Fila Thread-Safe de UI
        self._ui_queue = queue.Queue()
        self.after(50, self._processar_fila_ui)

        self.var_data_ini = MascaraDataVar()
        self.var_data_fim = MascaraDataVar()

        self._last_auto_searched_id = None
        self._last_diag_searched_id = None
        self._last_consent_searched_id = None
        self._debounce_timer = None

        # Estado de Monitoramento de Status da Rede (status.pluggy.ai)
        self.raw_status_summary = None
        self.raw_connectors_incidents = {}
        self.raw_full_status = None
        self._filtro_status_texto = ""
        self._filtro_status_severidade = "Todos"
        self._status_debounce_timer = None
        self._status_last_loaded_time = None
        self._instituicao_ativa_info = None

        # Estado do Sistema de Atualizações Automáticas em Segundo Plano
        self._is_updating = False
        self._update_download_progress = 0.0
        self.lbl_update_modal_status = None
        self.btn_modal_verif_update = None

        self.carregar_config()
        self.configurar_estilos_treeview()
        self.criar_cabecalho()
        self.criar_corpo_principal()
        self.aplicar_mes(self.nav_year, self.nav_month)

        self.after(150, lambda: threading.Thread(target=self.obter_api_key, daemon=True).start())
        self.after(800, lambda: threading.Thread(target=self.carregar_status_rede, kwargs={"silencioso": True}, daemon=True).start())
        # Checagem de pós-atualização (notifica se acabou de reiniciar atualizado)
        self.after(600, self._verificar_pos_atualizacao)
        # Verificação automática de atualizações em segundo plano
        self.after(3500, self.iniciar_verificacao_automatica_atualizacoes)

    def _processar_fila_ui(self):
        try:
            while not self._ui_queue.empty():
                func = self._ui_queue.get_nowait()
                try:
                    func()
                except Exception as e:
                    print("Erro ao executar callback na UI:", e)
        finally:
            try:
                self.after(50, self._processar_fila_ui)
            except Exception:
                pass

    def _reportar_excecao_global(self, exc_type, exc_val, exc_tb):
        """Evita que qualquer erro interno passe despercebido"""
        import traceback
        err_msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        print("Erro não tratado:\n" + err_msg)
        self.exibir_alerta("Erro interno", "Consulte o console se necessário.", cor="#F43F5E")

    def definir_icone_janela(self):
        """Define o ícone da janela usando os bytes incorporados ou arquivo temp"""
        if ICON_ICO_B64:
            try:
                temp_ico = os.path.join(tempfile.gettempdir(), 'pluggy_explorer_app_icon.ico')
                with open(temp_ico, 'wb') as f:
                    f.write(base64.b64decode(ICON_ICO_B64))
                self.iconbitmap(temp_ico)
                return
            except Exception:
                pass
        if ICON_PNG_B64:
            try:
                img_data = base64.b64decode(ICON_PNG_B64)
                photo = tk.PhotoImage(data=img_data)
                self.wm_iconphoto(True, photo)
            except Exception:
                pass

    def obter_logo_image(self, size=(34, 34)):
        """Obtém a imagem do logotipo diretamente da memória (Base64)"""
        if ICON_PNG_B64:
            try:
                img_data = base64.b64decode(ICON_PNG_B64)
                pil_img = Image.open(io.BytesIO(img_data))
                return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            except Exception:
                pass
        return None

    def obter_empty_state_image(self, size=(54, 54)):
        """Obtém o ícone de empty state em alta definição a partir de Base64"""
        if EMPTY_STATE_PNG_B64:
            try:
                img_data = base64.b64decode(EMPTY_STATE_PNG_B64)
                pil_img = Image.open(io.BytesIO(img_data))
                return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            except Exception:
                pass
        return None

    def carregar_config(self):
        """Carrega credenciais em segundo plano a partir de config.json ou embutidas"""
        env_id = os.environ.get("PLUGGY_CLIENT_ID") or os.environ.get("CLIENT_ID")
        env_sec = os.environ.get("PLUGGY_CLIENT_SECRET") or os.environ.get("CLIENT_SECRET")
        if env_id:
            self.client_id = env_id.strip()
        if env_sec:
            self.client_secret = env_sec.strip()

        config_path = localizar_arquivo_config()
        if config_path and config_path.endswith('.json'):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cid = data.get('client_id') or data.get('clientId')
                    sec = data.get('client_secret') or data.get('clientSecret')
                    if cid:
                        self.client_id = str(cid).strip()
                    if sec:
                        self.client_secret = str(sec).strip()
            except Exception as e:
                print("Aviso ao carregar credenciais: ", e)

    def salvar_config(self, c_id, c_secret):
        try:
            self.client_id = c_id.strip()
            self.client_secret = c_secret.strip()
            self.api_key = None
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"client_id": self.client_id, "client_secret": self.client_secret}, f, indent=2)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar config.json: {e}", parent=self)

    def safe_after(self, delay, func):
        if delay == 0:
            self._ui_queue.put(func)
        else:
            try:
                self.after(delay, lambda: self._ui_queue.put(func))
            except Exception:
                pass

    def obter_api_key(self, force_refresh=False):
        if self.api_key and not force_refresh:
            return True
        if not self.client_id or not self.client_secret:
            self.safe_after(0, lambda: self.atualizar_status_chave("Credenciais não configuradas", "#F59E0B"))
            return False

        self.safe_after(0, lambda: self.atualizar_status_chave("Conectando à Pluggy...", "#38BDF8"))
        url = f"{PLUGGY_BASE_URL}/auth"
        payload = {"clientId": self.client_id, "clientSecret": self.client_secret}
        headers = {"accept": "application/json", "content-type": "application/json"}

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                self.api_key = res.json().get("apiKey")
                self.safe_after(0, lambda: self.atualizar_status_chave("API Key: Ativa", "#10B981"))
                return True
            else:
                self.safe_after(0, lambda: self.atualizar_status_chave("Falha de Autenticação", "#F43F5E"))
                return False
        except Exception:
            self.safe_after(0, lambda: self.atualizar_status_chave("Sem conexão com Pluggy", "#F43F5E"))
            return False

    def atualizar_status_chave(self, texto, cor):
        if "Ativa" in texto:
            bg_pill = "#064E3B"
            border_pill = "#059669"
            dot = "• "
            cor = "#34D399"
        elif "Conectando" in texto:
            bg_pill = "#0C4A6E"
            border_pill = "#0284C7"
            dot = "◌ "
        else:
            bg_pill = "#4C0519" if ("Falha" in texto or "Sem conexão" in texto) else "#1E293B"
            border_pill = "#F43F5E" if ("Falha" in texto or "Sem conexão" in texto) else "#F59E0B"
            dot = "▲ "

        self.frame_status_badge.configure(fg_color=bg_pill, border_color=border_pill)
        self.lbl_header_status.configure(text=f"{dot}{texto}", text_color=cor)

    def renovar_key_manual(self):
        def worker():
            sucesso = self.obter_api_key(force_refresh=True)
            if sucesso:
                self.safe_after(0, lambda: messagebox.showinfo("Sucesso", "API Key da Pluggy renovada com sucesso!", parent=self))
            else:
                self.safe_after(0, lambda: messagebox.showerror("Erro", "Não foi possível gerar a API Key. Verifique suas credenciais.", parent=self))
        threading.Thread(target=worker, daemon=True).start()

    def obter_connect_token(self, item_id=None, retry=True):
        """
        Gera um Connect Token seguro (accessToken) via POST https://api.pluggy.ai/connect_token.
        Se item_id for fornecido, gera token para atualização/reconexão/MFA do item existente.
        Caso contrário, gera token para uma nova conexão bancária.
        """
        if not self.obter_api_key():
            raise Exception("Não foi possível autenticar na API Pluggy. Verifique suas credenciais.")

        url = f"{PLUGGY_BASE_URL}/connect_token"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-KEY": self.api_key
        }
        payload = {}
        if item_id:
            c_id = str(item_id).strip().strip("'\"")
            if c_id:
                payload["itemId"] = c_id

        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 401 and retry:
            if self.obter_api_key(force_refresh=True):
                return self.obter_connect_token(item_id=item_id, retry=False)

        if res.status_code not in (200, 201):
            try:
                err_data = res.json()
                msg = err_data.get("message") or err_data.get("error") or str(err_data)
            except Exception:
                msg = res.text
            raise Exception(f"Falha ao gerar Connect Token (HTTP {res.status_code}): {msg}")

        data = res.json()
        token = data.get("accessToken")
        if not token:
            raise Exception("A resposta da API Pluggy não retornou um accessToken válido.")
        return token

    def gerar_html_connect_widget(self, access_token, item_id=None):
        """
        Gera uma página HTML moderna e independente com o Pluggy Connect Widget v2.11.0,
        abrindo imediatamente o fluxo oficial de conexão / reconexão no navegador padrão.
        """
        mode_title = f"Reconexão de Item: {item_id}" if item_id else "Nova Conexão Bancária"
        mode_badge = "Reconexão / MFA" if item_id else "Nova Conexão"
        badge_class = "badge-warning" if item_id else "badge-primary"
        target_info = f"<div class='info-row'><span class='info-label'>Item Alvo:</span><span class='info-val'>{item_id}</span></div>" if item_id else ""
        js_item_id = f'"{item_id}"' if item_id else "null"

        html_template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pluggy Connect • Open Finance Explorer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.pluggy.ai/pluggy-connect/v2.11.0/pluggy-connect.js"></script>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: #07090E;
      color: #F1F5F9;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      line-height: 1.5;
    }
    .card-wrap {
      width: 100%;
      max-width: 620px;
      background: #0F172A;
      border: 1px solid #1E293B;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.04);
    }
    .header-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }
    .logo-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 700;
      color: #38BDF8;
      background: rgba(2, 132, 199, 0.12);
      border: 1px solid rgba(2, 132, 199, 0.3);
      padding: 6px 14px;
      border-radius: 9999px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-primary {
      background: rgba(2, 132, 199, 0.15);
      border: 1px solid #0284C7;
      color: #38BDF8;
    }
    .badge-warning {
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid #F59E0B;
      color: #FBBF24;
    }
    .badge-success {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid #10B981;
      color: #34D399;
    }
    h1 {
      font-size: 22px;
      font-weight: 700;
      color: #FFFFFF;
      margin-bottom: 6px;
    }
    p.desc {
      font-size: 13px;
      color: #94A3B8;
      margin-bottom: 20px;
    }
    .info-table {
      background: #111827;
      border: 1px solid #1F2937;
      border-radius: 12px;
      padding: 14px 16px;
      margin-bottom: 20px;
    }
    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      font-size: 12px;
      border-bottom: 1px solid #1F2937;
    }
    .info-row:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }
    .info-label {
      color: #64748B;
      font-weight: 500;
    }
    .info-val {
      color: #E2E8F0;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-weight: 600;
      font-size: 11px;
      word-break: break-all;
    }
    .btn-launch {
      width: 100%;
      background: #0284C7;
      color: #FFFFFF;
      border: none;
      padding: 13px 20px;
      font-size: 14px;
      font-weight: 600;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
    }
    .btn-launch:hover {
      background: #0369A1;
      transform: translateY(-1px);
    }
    .log-container {
      margin-top: 20px;
      background: #07090E;
      border: 1px solid #1F2937;
      border-radius: 10px;
      padding: 12px 14px;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 11px;
      color: #94A3B8;
      max-height: 140px;
      overflow-y: auto;
    }
    .log-entry {
      padding: 2px 0;
      display: flex;
      gap: 8px;
    }
    .log-ts {
      color: #475569;
    }
    .success-box {
      display: none;
      margin-top: 18px;
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid #059669;
      border-radius: 12px;
      padding: 16px;
      text-align: center;
    }
    .success-box h3 {
      color: #34D399;
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .success-box p {
      font-size: 13px;
      color: #CBD5E1;
      margin-bottom: 12px;
    }
    .btn-copy-id {
      background: #10B981;
      color: #07090E;
      border: none;
      padding: 8px 16px;
      font-weight: 700;
      font-size: 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    .btn-copy-id:hover {
      background: #34D399;
    }
  </style>
</head>
<body>

  <div class="card-wrap">
    <div class="header-bar">
      <div class="logo-badge">⚡ Pluggy Connect</div>
      <span class="badge {{BADGE_CLASS}}">{{MODE_BADGE}}</span>
    </div>

    <h1>{{MODE_TITLE}}</h1>
    <p class="desc">A janela segura de autenticação bancária está sendo aberta. Siga as instruções do banco para concluir a conexão.</p>

    <div class="info-table">
      {{TARGET_INFO}}
      <div class="info-row">
        <span class="info-label">Connect Token:</span>
        <span class="info-val">{{TOKEN_SNIPPET}}...</span>
      </div>
      <div class="info-row">
        <span class="info-label">Validade:</span>
        <span class="info-val" style="color: #34D399;">30 minutos</span>
      </div>
      <div class="info-row">
        <span class="info-label">Ambiente:</span>
        <span class="info-val">Open Finance Brasil (com Sandbox Ativo)</span>
      </div>
    </div>

    <button id="btn-reabrir" class="btn-launch" onclick="abrirWidget()">
      <span>🚀 Reabrir Modal de Conexão</span>
    </button>

    <div id="success-box" class="success-box">
      <h3>🎉 Conexão Concluída com Sucesso!</h3>
      <p>As credenciais foram validadas pelo banco. O item já está registrado na Pluggy.</p>
      <div style="margin-bottom: 12px;">
        <span style="font-size: 11px; color: #94A3B8;">Item ID Gerado/Atualizado:</span><br>
        <strong id="created-item-id" style="font-family: monospace; color: #38BDF8; font-size: 13px;">-</strong>
      </div>
      <button class="btn-copy-id" onclick="copiarItemId()">📋 Copiar Item ID</button>
      <p style="font-size: 11px; color: #94A3B8; margin-top: 10px;">Você já pode retornar ao Open Finance Explorer e clicar em <strong>Recarregar Diagnóstico</strong> ou <strong>Buscar Contas</strong>.</p>
    </div>

    <div class="log-container" id="log-box">
      <div class="log-entry"><span class="log-ts">[Log]</span><span>Aguardando inicialização do SDK...</span></div>
    </div>
  </div>

  <script>
    const CONNECT_TOKEN = "{{ACCESS_TOKEN}}";
    const TARGET_ITEM_ID = {{JS_ITEM_ID}};
    let pluggyWidget = null;
    let createdItemId = TARGET_ITEM_ID || '';

    function log(msg, color) {
      const box = document.getElementById('log-box');
      const row = document.createElement('div');
      row.className = 'log-entry';
      const ts = new Date().toLocaleTimeString();
      row.innerHTML = `<span class="log-ts">[${ts}]</span> <span style="color: ${color || '#94A3B8'}">${msg}</span>`;
      box.appendChild(row);
      box.scrollTop = box.scrollHeight;
    }

    function copiarItemId() {
      if (createdItemId) {
        navigator.clipboard.writeText(createdItemId);
        alert('Item ID copiado para a Área de Transferência!');
      }
    }

    function abrirWidget() {
      try {
        if (typeof PluggyConnect === 'undefined') {
          log('Biblioteca PluggyConnect ainda não carregou da CDN. Aguarde...', '#F59E0B');
          setTimeout(abrirWidget, 500);
          return;
        }

        log('Inicializando Pluggy Connect v2.11.0...', '#38BDF8');

        const opts = {
          connectToken: CONNECT_TOKEN,
          includeSandbox: true,
          onSuccess: (data) => {
            log('🎉 Sucesso! Conexão autenticada pelo banco.', '#34D399');
            console.log('Pluggy Connect onSuccess:', data);
            const id = data?.item?.id || (typeof data?.item === 'string' ? data.item : '') || TARGET_ITEM_ID || '';
            createdItemId = id;
            document.getElementById('created-item-id').innerText = id || '(Identificador registrado)';
            document.getElementById('success-box').style.display = 'block';
          },
          onError: (err) => {
            const errStr = err?.message || JSON.stringify(err);
            log('⚠️ Erro na autenticação: ' + errStr, '#F43F5E');
            console.error('Pluggy Connect onError:', err);
          },
          onClose: () => {
            log('Modal do conector fechado pelo usuário.', '#94A3B8');
          },
          onEvent: (evt) => {
            const evName = evt?.event || evt?.type || JSON.stringify(evt);
            log('Evento: ' + evName, '#60A5FA');
          }
        };

        if (TARGET_ITEM_ID) {
          opts.updateItem = TARGET_ITEM_ID;
        }

        pluggyWidget = new PluggyConnect(opts);
        pluggyWidget.init();
        log('Modal do Pluggy Connect aberto com sucesso!', '#34D399');
      } catch (e) {
        log('Erro ao inicializar widget: ' + e.message, '#F43F5E');
        console.error(e);
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      setTimeout(abrirWidget, 350);
    });
  </script>
</body>
</html>"""

        token_snippet = access_token[:24] if access_token else ""
        content = (
            html_template
            .replace("{{BADGE_CLASS}}", badge_class)
            .replace("{{MODE_BADGE}}", mode_badge)
            .replace("{{MODE_TITLE}}", mode_title)
            .replace("{{TARGET_INFO}}", target_info)
            .replace("{{TOKEN_SNIPPET}}", token_snippet)
            .replace("{{ACCESS_TOKEN}}", access_token)
            .replace("{{JS_ITEM_ID}}", js_item_id)
        )

        tmp_dir = tempfile.gettempdir()
        file_path = os.path.join(tmp_dir, f"pluggy_connect_{int(datetime.now().timestamp())}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def abrir_fluxo_connect_widget(self, item_id=None):
        """
        Executa o fluxo completo do Connect Widget:
        1. Consulta POST /connect_token na Pluggy
        2. Gera HTML local e abre no navegador padrão
        3. Exibe modal com detalhes, cópia de token e atalhos no app
        """
        def worker():
            try:
                self.safe_after(0, lambda: self.atualizar_status_chave("Gerando Connect Token...", "#38BDF8"))
                token = self.obter_connect_token(item_id=item_id)
                html_path = self.gerar_html_connect_widget(token, item_id=item_id)

                # Abre no navegador padrão do sistema operacional
                webbrowser.open(f"file:///{os.path.abspath(html_path).replace(chr(92), '/')}")

                self.safe_after(0, lambda: self.atualizar_status_chave("API Key: Ativa", "#10B981"))
                self.safe_after(0, lambda: self.abrir_modal_connect_token(token, item_id=item_id, html_path=html_path))
            except Exception as e:
                self.safe_after(0, lambda: self.atualizar_status_chave("API Key: Ativa", "#10B981"))
                self.safe_after(0, lambda: messagebox.showerror(
                    "Erro no Pluggy Connect",
                    f"Não foi possível iniciar o Pluggy Connect:\n\n{e}",
                    parent=self
                ))

        threading.Thread(target=worker, daemon=True).start()

    def abrir_modal_connect_token(self, access_token, item_id=None, html_path=None):
        """Abre modal elegante no app com o Connect Token e ações rápidas"""
        win = ctk.CTkToplevel(self)
        win.title("Pluggy Connect • Open Finance")
        win.configure(fg_color="#0B0F19")
        win.resizable(False, False)

        w, h = 580, 460
        self.update_idletasks()
        rx = self.winfo_rootx() + (self.winfo_width() - w) // 2
        ry = self.winfo_rooty() + (self.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{max(50, rx)}+{max(50, ry)}")
        win.transient(self)

        header = ctk.CTkFrame(win, height=60, corner_radius=0, fg_color="#0F172A")
        header.pack(fill=tk.X)

        accent = ctk.CTkFrame(win, height=2, corner_radius=0, fg_color="#059669")
        accent.pack(fill=tk.X)

        head_inner = ctk.CTkFrame(header, fg_color="transparent")
        head_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            head_inner,
            text="⚡ Pluggy Connect Iniciado",
            font=("Segoe UI", 16, "bold"),
            text_color="#FFFFFF"
        ).pack(side=tk.LEFT)

        badge_frame = ctk.CTkFrame(head_inner, fg_color="#064E3B", corner_radius=12, border_width=1, border_color="#059669")
        badge_frame.pack(side=tk.RIGHT)
        ctk.CTkLabel(badge_frame, text="● Aberto no Navegador", font=("Segoe UI", 10, "bold"), text_color="#34D399").pack(padx=10, pady=2)

        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        sub_txt = (
            f"O widget Pluggy Connect foi aberto no seu navegador padrão para atualizar e resolver pendências (MFA / Senha) do item informado."
            if item_id else
            "O widget Pluggy Connect foi aberto no seu navegador padrão para conectar uma nova instituição bancária com segurança."
        )
        ctk.CTkLabel(content, text=sub_txt, font=("Segoe UI", 12), text_color="#94A3B8", wraplength=530, justify="left").pack(anchor="w", pady=(0, 14))

        card_info = ctk.CTkFrame(content, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
        card_info.pack(fill=tk.X, pady=(0, 14))

        if item_id:
            row_id = ctk.CTkFrame(card_info, fg_color="transparent")
            row_id.pack(fill=tk.X, padx=14, pady=(10, 6))
            ctk.CTkLabel(row_id, text="Item Alvo:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=75, anchor="w").pack(side=tk.LEFT)
            ctk.CTkLabel(row_id, text=item_id, font=("Consolas", 11, "bold"), text_color="#38BDF8").pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_tok = ctk.CTkFrame(card_info, fg_color="transparent")
        row_tok.pack(fill=tk.X, padx=14, pady=(6 if item_id else 10, 10))

        ctk.CTkLabel(row_tok, text="Token:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=75, anchor="w").pack(side=tk.LEFT)
        entry_tok = ctk.CTkEntry(row_tok, height=32, font=("Consolas", 10), border_color="#1F2937")
        entry_tok.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        entry_tok.insert(0, access_token)
        entry_tok.configure(state="readonly")

        btn_copy_tok = ctk.CTkButton(
            row_tok,
            text="Copiar Token",
            width=100,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.copiar_para_clipboard(access_token, btn_copy_tok)
        )
        btn_copy_tok.pack(side=tk.RIGHT)

        row_val = ctk.CTkFrame(card_info, fg_color="transparent")
        row_val.pack(fill=tk.X, padx=14, pady=(0, 10))
        ctk.CTkLabel(row_val, text="⏱️ Validade do Token: 30 minutos a partir da emissão", font=("Segoe UI", 10), text_color="#10B981").pack(anchor="w")

        # Botões de Ação
        btn_reopen = ctk.CTkButton(
            content,
            text="🌐 Reabrir Página do Conector no Navegador",
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=lambda: webbrowser.open(f"file:///{os.path.abspath(html_path).replace(chr(92), '/')}") if html_path else None
        )
        btn_reopen.pack(fill=tk.X, pady=(0, 8))

        row_bottom = ctk.CTkFrame(content, fg_color="transparent")
        row_bottom.pack(fill=tk.X, pady=(4, 0))

        if item_id:
            def _recarregar():
                win.destroy()
                self.tabview.set("Diagnóstico de Item (Erros)")
                self.entry_diag_item_id.delete(0, tk.END)
                self.entry_diag_item_id.insert(0, item_id)
                self.acao_diagnosticar_item()

            btn_reload_diag = ctk.CTkButton(
                row_bottom,
                text="🔄 Recarregar Diagnóstico do Item",
                height=36,
                fg_color="#059669",
                hover_color="#047857",
                font=("Segoe UI", 11, "bold"),
                command=_recarregar
            )
            btn_reload_diag.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_close = ctk.CTkButton(
            row_bottom,
            text="Fechar Janela",
            width=110,
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=win.destroy
        )
        btn_close.pack(side=tk.RIGHT if item_id else tk.TOP, fill=tk.NONE if item_id else tk.X)

    def configurar_estilos_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Remove completamente a Treeview.field e Treeheading.border que geravam a linha/borda branca nativa
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        style.layout("Treeview.Heading", [
            ('Treeheading.cell', {'sticky': 'nswe'}),
            ('Treeheading.padding', {'sticky': 'nswe', 'children': [
                ('Treeheading.image', {'side': 'right', 'sticky': ''}),
                ('Treeheading.text', {'sticky': 'we'})
            ]})
        ])
        
        style.configure(
            "Treeview",
            background="#111827",
            foreground="#F3F4F6",
            fieldbackground="#111827",
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            bordercolor="#111827",
            lightcolor="#111827",
            darkcolor="#111827"
        )
        style.map("Treeview", background=[("selected", "#0369A1")], foreground=[("selected", "#FFFFFF")])
        style.configure(
            "Treeview.Heading",
            background="#1E293B",
            foreground="#94A3B8",
            relief="flat",
            borderwidth=0,
            bordercolor="#1E293B",
            lightcolor="#1E293B",
            darkcolor="#1E293B",
            font=("Segoe UI", 10, "bold"),
            padding=(8, 8)
        )
        style.map("Treeview.Heading", background=[("active", "#334155")], foreground=[("active", "#38BDF8")])

    def criar_cabecalho(self):
        header_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header_container.pack(fill=tk.X, side=tk.TOP)

        header = ctk.CTkFrame(header_container, height=62, corner_radius=0, fg_color="#0F172A")
        header.pack(fill=tk.X)

        # Linha decorativa de acento inferior
        accent_line = ctk.CTkFrame(header_container, height=2, corner_radius=0, fg_color="#0284C7")
        accent_line.pack(fill=tk.X)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side=tk.LEFT, padx=20, pady=10)

        logo_img = self.obter_logo_image((34, 34))
        if logo_img:
            lbl_icon = ctk.CTkLabel(title_frame, text="", image=logo_img)
            lbl_icon.pack(side=tk.LEFT, padx=(0, 10))

        lbl_title = ctk.CTkLabel(title_frame, text="Open Finance Explorer", font=("Segoe UI", 16, "bold"), text_color="#FFFFFF")
        lbl_title.pack(side=tk.LEFT)

        lbl_sub = ctk.CTkLabel(title_frame, text="Pluggy API Diagnostics", font=("Segoe UI", 11), text_color="#64748B")
        lbl_sub.pack(side=tk.LEFT, padx=(8, 0))

        actions_frame = ctk.CTkFrame(header, fg_color="transparent")
        actions_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        # Status badge com efeito de pílula
        self.frame_status_badge = ctk.CTkFrame(actions_frame, fg_color="#1E293B", corner_radius=14, border_width=1, border_color="#334155")
        self.frame_status_badge.pack(side=tk.LEFT, padx=(0, 8), ipady=2)

        self.lbl_header_status = ctk.CTkLabel(
            self.frame_status_badge,
            text="◌ Verificando conexão...",
            font=("Segoe UI", 11, "bold"),
            text_color="#F59E0B"
        )
        self.lbl_header_status.pack(padx=12, pady=2)

        # Badge de Rede mantido sem exibição no cabeçalho (conforme solicitação do usuário)
        # O status detalhado de instabilidades é concentrado na aba 'Status dos Bancos & Conectores'
        self.frame_rede_badge = None
        self.lbl_rede_status = None

        self.btn_conectar_widget = ctk.CTkButton(
            actions_frame,
            text="⚡ Conectar Conta",
            width=128,
            height=32,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 11, "bold"),
            command=lambda: self.abrir_fluxo_connect_widget(item_id=None)
        )
        self.btn_conectar_widget.pack(side=tk.LEFT, padx=4)

        btn_renew = ctk.CTkButton(
            actions_frame,
            text="Renovar Key",
            width=115,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=self.renovar_key_manual
        )
        btn_renew.pack(side=tk.LEFT, padx=4)

        btn_settings = ctk.CTkButton(
            actions_frame,
            text="Credenciais",
            width=115,
            height=32,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=self.abrir_janela_credenciais
        )
        btn_settings.pack(side=tk.LEFT, padx=4)

        btn_docs = ctk.CTkButton(
            actions_frame,
            text="📖 Docs Pluggy",
            width=115,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt")
        )
        btn_docs.pack(side=tk.LEFT, padx=4)

    def criar_corpo_principal(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="#0B0F19",
            segmented_button_fg_color="#1E293B",
            segmented_button_selected_color="#0284C7",
            segmented_button_selected_hover_color="#0369A1"
        )
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 16))

        self.tab_transacoes = self.tabview.add("Explorer de Transações")
        self.tab_diagnostico = self.tabview.add("Diagnóstico de Item (Erros)")
        self.tab_consentimento = self.tabview.add("Situação do Consentimento")
        self.tab_status_bancos = self.tabview.add("Status dos Bancos & Conectores")
        self.tab_docs_recursos = self.tabview.add("Docs & Novos Recursos")

        self.setup_aba_transacoes()
        self.setup_aba_diagnostico()
        self.setup_aba_consentimento()
        self.setup_aba_status_bancos()
        self.setup_aba_docs_recursos()

    def setup_aba_transacoes(self):
        # 1. Painel de Filtros Organizado Conforme Imagem:
        # Card 1: Container arredondado com borda sutil
        card_filtros = ctk.CTkFrame(self.tab_transacoes, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_filtros.pack(fill=tk.X, padx=8, pady=(4, 10))

        # ----------------------------------------------------
        # LINHA 1 (SUPERIOR): ITEM ID + BOTÃO BUSCAR CONTAS E CONTA
        # ----------------------------------------------------
        row1 = ctk.CTkFrame(card_filtros, fg_color="transparent")
        row1.pack(fill=tk.X, padx=16, pady=(12, 6))
        row1.columnconfigure(0, weight=3)
        row1.columnconfigure(1, weight=2)

        # Coluna Esquerda: Item ID com campo amplo e botão 1. Buscar Contas logo ao lado
        col_item = ctk.CTkFrame(row1, fg_color="transparent")
        col_item.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        lbl_item = ctk.CTkLabel(col_item, text="Item ID:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8")
        lbl_item.pack(anchor="w", pady=(0, 4))

        frame_item_ctrl = ctk.CTkFrame(col_item, fg_color="transparent")
        frame_item_ctrl.pack(fill=tk.X)

        self.entry_item_id = ctk.CTkEntry(
            frame_item_ctrl,
            placeholder_text="Cole o Item ID aqui (ex: e7c2394d-e9c5-4ad9-9069-7c85...) ou Account ID",
            height=38,
            font=("Consolas", 11),
            border_color="#1F2937",
            fg_color="#162032"
        )
        self.entry_item_id.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.entry_item_id.bind("<Return>", lambda e: self.acao_buscar_contas())

        # Vínculos automáticos para sincronização e pesquisa imediata ao colar ou digitar
        self.entry_item_id.bind("<Control-v>", self._ao_colar_item_id)
        self.entry_item_id.bind("<Control-V>", self._ao_colar_item_id)
        self.entry_item_id.bind("<<Paste>>", self._ao_colar_item_id)
        self.entry_item_id.bind("<KeyRelease>", self._ao_mudar_item_id_debounce)
        self._criar_menu_contexto_entry(self.entry_item_id)

        self.btn_buscar_contas = ctk.CTkButton(
            frame_item_ctrl,
            text="1. Buscar Contas",
            width=150,
            height=38,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            corner_radius=8,
            command=self.acao_buscar_contas
        )
        self.btn_buscar_contas.pack(side=tk.RIGHT)

        # Coluna Direita: Conta
        col_conta = ctk.CTkFrame(row1, fg_color="transparent")
        col_conta.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        lbl_conta = ctk.CTkLabel(col_conta, text="Conta:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8")
        lbl_conta.pack(anchor="w", pady=(0, 4))

        self.combo_contas = ctk.CTkComboBox(
            col_conta,
            values=["Informe o Item ID e clique em '1. Buscar Contas'"],
            height=38,
            font=("Segoe UI", 11),
            state="readonly",
            border_color="#1F2937",
            fg_color="#162032"
        )
        self.combo_contas.pack(fill=tk.X)

        # ----------------------------------------------------
        # LINHA 2: DATA, NAVEGAÇÃO DE MESES E BOTÃO 2. VER TRANSAÇÕES
        # ----------------------------------------------------
        row2 = ctk.CTkFrame(card_filtros, fg_color="transparent")
        row2.pack(fill=tk.X, padx=16, pady=(4, 12))

        # Sub-bloco 1: Data Início
        blk_ini = ctk.CTkFrame(row2, fg_color="transparent")
        blk_ini.pack(side=tk.LEFT, padx=(0, 8))

        lbl_dini = ctk.CTkLabel(blk_ini, text="Data Início:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8")
        lbl_dini.pack(anchor="w", pady=(0, 4))

        self.entry_data_ini = ctk.CTkEntry(
            blk_ini,
            textvariable=self.var_data_ini,
            placeholder_text="DD/MM/AAAA",
            width=105,
            height=36,
            font=("Consolas", 11),
            border_color="#1F2937",
            fg_color="#162032"
        )
        self.entry_data_ini.pack()
        self.entry_data_ini.bind("<Return>", lambda e: self.acao_buscar_transacoes())
        self.var_data_ini.vincular_entry(self.entry_data_ini)

        # Sub-bloco 2: Data Fim
        blk_fim = ctk.CTkFrame(row2, fg_color="transparent")
        blk_fim.pack(side=tk.LEFT, padx=(0, 14))

        lbl_dfim = ctk.CTkLabel(blk_fim, text="Data Fim:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8")
        lbl_dfim.pack(anchor="w", pady=(0, 4))

        self.entry_data_fim = ctk.CTkEntry(
            blk_fim,
            textvariable=self.var_data_fim,
            placeholder_text="DD/MM/AAAA",
            width=105,
            height=36,
            font=("Consolas", 11),
            border_color="#1F2937",
            fg_color="#162032"
        )
        self.entry_data_fim.pack()
        self.entry_data_fim.bind("<Return>", lambda e: self.acao_buscar_transacoes())
        self.var_data_fim.vincular_entry(self.entry_data_fim)

        # Sub-bloco 3: Atalhos e Seleção de Meses
        blk_meses = ctk.CTkFrame(row2, fg_color="transparent")
        blk_meses.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_meses = ctk.CTkLabel(blk_meses, text="Atalhos e Seleção de Meses:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8")
        lbl_meses.pack(anchor="w", pady=(0, 4))

        frame_btns_meses = ctk.CTkFrame(blk_meses, fg_color="transparent")
        frame_btns_meses.pack(anchor="w")

        btn_todo_hist = ctk.CTkButton(
            frame_btns_meses,
            text="Todo Histórico",
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=self.acao_todo_historico
        )
        btn_todo_hist.pack(side=tk.LEFT, padx=(0, 4))

        btn_mes_ant = ctk.CTkButton(
            frame_btns_meses,
            text="◀ Mês Anterior",
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=self.acao_mes_anterior
        )
        btn_mes_ant.pack(side=tk.LEFT, padx=4)

        self.btn_mes_atual = ctk.CTkButton(
            frame_btns_meses,
            text="Mês Atual",
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=self.acao_mes_atual
        )
        self.btn_mes_atual.pack(side=tk.LEFT, padx=4)

        btn_prox_mes = ctk.CTkButton(
            frame_btns_meses,
            text="Próximo Mês ▶",
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=self.acao_proximo_mes
        )
        btn_prox_mes.pack(side=tk.LEFT, padx=4)

        self.btn_picker_mes = ctk.CTkButton(
            frame_btns_meses,
            text="Selecionar Mês ▾",
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155"
        )
        self.btn_picker_mes.pack(side=tk.LEFT, padx=4)

        self.month_picker = MonthPickerPopover(self, self.btn_picker_mes, self.aplicar_mes)
        self.btn_picker_mes.configure(command=self.month_picker.toggle)

        # Sub-bloco 4 (Direita): 2. Ver Transações
        blk_ver_trans = ctk.CTkFrame(row2, fg_color="transparent")
        blk_ver_trans.pack(side=tk.RIGHT, anchor="s")

        self.btn_ver_transacoes = ctk.CTkButton(
            blk_ver_trans,
            text="2. Ver Transações",
            width=190,
            height=38,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            command=self.acao_buscar_transacoes
        )
        self.btn_ver_transacoes.pack(side=tk.RIGHT)

        # Banner compacto de status / alertas (oculto por padrão ou slim)
        self.banner_status = ctk.CTkFrame(self.tab_transacoes, fg_color="#1E293B", corner_radius=8, height=0)
        self.lbl_status_msg = ctk.CTkLabel(
            self.banner_status,
            text="",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )

        # ----------------------------------------------------
        # 2. GRID DE KPIS MODERNOS CONFORME IMAGEM (4 CARDS)
        # ----------------------------------------------------
        self.frame_kpis = ctk.CTkFrame(self.tab_transacoes, fg_color="transparent")
        self.frame_kpis.pack(fill=tk.X, padx=8, pady=(0, 10))

        for c in range(4):
            self.frame_kpis.columnconfigure(c, weight=1)

        # Card 1: Total de Registros
        card_total = ctk.CTkFrame(self.frame_kpis, fg_color="#0F172A", corner_radius=10, border_width=1, border_color="#1E293B")
        card_total.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        top_c1 = ctk.CTkFrame(card_total, fg_color="transparent")
        top_c1.pack(fill=tk.X, padx=14, pady=(10, 2))
        ctk.CTkLabel(top_c1, text="TOTAL DE REGISTROS", font=("Segoe UI", 9, "bold"), text_color="#94A3B8").pack(side=tk.LEFT)
        ctk.CTkLabel(top_c1, text="📊", font=("Segoe UI", 11), text_color="#64748B").pack(side=tk.RIGHT)
        self.lbl_kpi_total = ctk.CTkLabel(card_total, text="0", font=("Segoe UI", 22, "bold"), text_color="#F8FAFC")
        self.lbl_kpi_total.pack(anchor="w", padx=14, pady=(0, 10))

        # Card 2: Entradas (Créditos)
        card_ent = ctk.CTkFrame(self.frame_kpis, fg_color="#0A1D16", corner_radius=10, border_width=1, border_color="#059669")
        card_ent.grid(row=0, column=1, padx=4, sticky="nsew")
        top_c2 = ctk.CTkFrame(card_ent, fg_color="transparent")
        top_c2.pack(fill=tk.X, padx=14, pady=(10, 2))
        ctk.CTkLabel(top_c2, text="▲ ENTRADAS (CRÉDITOS)", font=("Segoe UI", 9, "bold"), text_color="#10B981").pack(side=tk.LEFT)
        ctk.CTkLabel(top_c2, text="↗", font=("Segoe UI", 12, "bold"), text_color="#10B981").pack(side=tk.RIGHT)
        self.lbl_kpi_entradas = ctk.CTkLabel(card_ent, text="R$ 0,00", font=("Segoe UI", 22, "bold"), text_color="#34D399")
        self.lbl_kpi_entradas.pack(anchor="w", padx=14, pady=(0, 10))

        # Card 3: Saídas (Débitos)
        card_sai = ctk.CTkFrame(self.frame_kpis, fg_color="#1F0D14", corner_radius=10, border_width=1, border_color="#E11D48")
        card_sai.grid(row=0, column=2, padx=4, sticky="nsew")
        top_c3 = ctk.CTkFrame(card_sai, fg_color="transparent")
        top_c3.pack(fill=tk.X, padx=14, pady=(10, 2))
        ctk.CTkLabel(top_c3, text="▼ SAÍDAS (DÉBITOS)", font=("Segoe UI", 9, "bold"), text_color="#F43F5E").pack(side=tk.LEFT)
        ctk.CTkLabel(top_c3, text="↗", font=("Segoe UI", 12, "bold"), text_color="#F43F5E").pack(side=tk.RIGHT)
        self.lbl_kpi_saidas = ctk.CTkLabel(card_sai, text="R$ 0,00", font=("Segoe UI", 22, "bold"), text_color="#FB7185")
        self.lbl_kpi_saidas.pack(anchor="w", padx=14, pady=(0, 10))

        # Card 4: Saldo Líquido
        card_saldo = ctk.CTkFrame(self.frame_kpis, fg_color="#0A1828", corner_radius=10, border_width=1, border_color="#0284C7")
        card_saldo.grid(row=0, column=3, padx=(6, 0), sticky="nsew")
        top_c4 = ctk.CTkFrame(card_saldo, fg_color="transparent")
        top_c4.pack(fill=tk.X, padx=14, pady=(10, 2))
        ctk.CTkLabel(top_c4, text="SALDO LÍQUIDO", font=("Segoe UI", 9, "bold"), text_color="#38BDF8").pack(side=tk.LEFT)
        ctk.CTkLabel(top_c4, text="💳", font=("Segoe UI", 11), text_color="#38BDF8").pack(side=tk.RIGHT)
        self.lbl_kpi_saldo = ctk.CTkLabel(card_saldo, text="R$ 0,00", font=("Segoe UI", 22, "bold"), text_color="#38BDF8")
        self.lbl_kpi_saldo.pack(anchor="w", padx=14, pady=(0, 10))

        # ----------------------------------------------------
        # 3. BARRA DE CONTROLES DA TABELA / JSON
        # ----------------------------------------------------
        bar_view = ctk.CTkFrame(self.tab_transacoes, fg_color="transparent")
        bar_view.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.seg_view_mode = ctk.CTkSegmentedButton(
            bar_view,
            values=["Tabela Interativa", "Código Puro (JSON)"],
            selected_color="#0284C7",
            selected_hover_color="#0369A1",
            command=self.alternar_modo_visualizacao
        )
        self.seg_view_mode.set("Tabela Interativa")
        self.seg_view_mode.pack(side=tk.LEFT, padx=(0, 8))

        frame_busca_t1 = ctk.CTkFrame(bar_view, fg_color="transparent")
        frame_busca_t1.pack(side=tk.LEFT, padx=4)

        self.entry_busca_t1 = ctk.CTkEntry(
            frame_busca_t1,
            placeholder_text="Filtrar registros ou JSON...",
            width=200,
            height=32,
            font=("Segoe UI", 11),
            border_color="#1F2937",
            fg_color="#162032"
        )
        self.entry_busca_t1.pack(side=tk.LEFT)
        self.entry_busca_t1.bind("<KeyRelease>", lambda e: self.acao_buscar_t1())
        self.entry_busca_t1.bind("<Return>", lambda e: self.localizar_proximo_json_t1())

        lbl_lupa = ctk.CTkLabel(frame_busca_t1, text="🔍", font=("Segoe UI", 10), text_color="#64748B")
        lbl_lupa.pack(side=tk.LEFT, padx=(4, 0))

        # ----------------------------------------------------
        # 3.1 CAMPO DE CONSULTA DA INSTITUIÇÃO & PRAZO DE HISTÓRICO
        # Formato solicitado: (banco)-(quantos ) meses
        # ----------------------------------------------------
        self.frame_banco_prazo = ctk.CTkFrame(
            bar_view,
            fg_color="#0B132B",
            corner_radius=8,
            border_width=1,
            border_color="#1E293B"
        )
        self.frame_banco_prazo.pack(side=tk.LEFT, padx=(8, 4))

        lbl_banco_ico = ctk.CTkLabel(
            self.frame_banco_prazo,
            text="🏦",
            font=("Segoe UI", 12)
        )
        lbl_banco_ico.pack(side=tk.LEFT, padx=(8, 4))

        self.entry_banco_meses = ctk.CTkEntry(
            self.frame_banco_prazo,
            placeholder_text="(banco)-(quantos ) meses",
            width=190,
            height=30,
            font=("Segoe UI", 11, "bold"),
            border_width=0,
            fg_color="transparent",
            text_color="#38BDF8"
        )
        self.entry_banco_meses.pack(side=tk.LEFT, padx=(0, 4))
        self.entry_banco_meses.bind("<Return>", lambda e: self.consultar_instituicao_digitada())

        self.btn_consultar_inst_meses = ctk.CTkButton(
            self.frame_banco_prazo,
            text="🔍 Consultar",
            width=90,
            height=26,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10, "bold"),
            border_width=1,
            border_color="#334155",
            corner_radius=6,
            command=self.abrir_modal_consulta_instituicao
        )
        self.btn_consultar_inst_meses.pack(side=tk.LEFT, padx=3)

        self.btn_info_inst_meses = ctk.CTkButton(
            self.frame_banco_prazo,
            text="ℹ️",
            width=26,
            height=26,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11, "bold"),
            border_width=1,
            border_color="#334155",
            corner_radius=6,
            command=self.abrir_detalhes_historico_atual
        )
        self.btn_info_inst_meses.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_prev_json_t1 = ctk.CTkButton(bar_view, text="▲", width=30, height=32, fg_color="#1E293B", hover_color="#334155", command=self.localizar_anterior_json_t1)
        self.btn_next_json_t1 = ctk.CTkButton(bar_view, text="▼", width=30, height=32, fg_color="#1E293B", hover_color="#334155", command=self.localizar_proximo_json_t1)
        self.lbl_busca_status_t1 = ctk.CTkLabel(bar_view, text="", font=("Segoe UI", 10), text_color="#9CA3AF")

        self.btn_colunas = ctk.CTkButton(
            bar_view,
            text="Colunas",
            width=95,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            command=self.abrir_gerenciador_colunas
        )
        self.btn_colunas.pack(side=tk.RIGHT, padx=4)

        self.btn_exportar = ctk.CTkButton(
            bar_view,
            text="Exportar CSV",
            width=110,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color="#334155",
            command=self.exportar_csv_transacoes
        )
        self.btn_exportar.pack(side=tk.RIGHT, padx=4)

        # ----------------------------------------------------
        # 4. CONTAINER DE DADOS (TABELA E JSON)
        # ----------------------------------------------------
        self.container_dados = ctk.CTkFrame(self.tab_transacoes, fg_color="transparent")
        self.container_dados.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        # Frame da Tabela sem borda branca (borda sutil dark #1F2937)
        self.frame_tabela = ctk.CTkFrame(self.container_dados, fg_color="#111827", corner_radius=8, border_width=1, border_color="#1F2937")
        self.frame_tabela.pack(fill=tk.BOTH, expand=True)

        # Empty State estilizado dentro da tabela conforme imagem
        self.frame_empty_tabela = ctk.CTkFrame(self.frame_tabela, fg_color="#111827", corner_radius=0)
        self.frame_empty_tabela.place(relx=0.5, rely=0.55, anchor="center")

        img_empty = self.obter_empty_state_image((54, 54))
        if img_empty:
            lbl_empty_icon = ctk.CTkLabel(self.frame_empty_tabela, text="", image=img_empty)
            lbl_empty_icon.pack(pady=(0, 8))
        else:
            lbl_empty_icon = ctk.CTkLabel(self.frame_empty_tabela, text="📄🔍", font=("Segoe UI", 36), text_color="#64748B")
            lbl_empty_icon.pack(pady=(0, 8))

        self.lbl_empty_titulo = ctk.CTkLabel(
            self.frame_empty_tabela,
            text="Nenhum registro encontrado",
            font=("Segoe UI", 13, "bold"),
            text_color="#E2E8F0"
        )
        self.lbl_empty_titulo.pack(pady=(0, 2))

        self.lbl_empty_sub = ctk.CTkLabel(
            self.frame_empty_tabela,
            text="Nenhum registro encontrado, aguardando consulta ou filtros aplicados.",
            font=("Segoe UI", 10),
            text_color="#64748B"
        )
        self.lbl_empty_sub.pack()

        self.scroll_tree_y = ctk.CTkScrollbar(
            self.frame_tabela,
            orientation="vertical",
            fg_color="#111827",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            width=12
        )
        self.scroll_tree_x = ctk.CTkScrollbar(
            self.frame_tabela,
            orientation="horizontal",
            fg_color="#111827",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            height=12
        )

        colunas_iniciais = ('date', 'description', 'amount', 'type', 'category', 'status')
        self.tree = ttk.Treeview(
            self.frame_tabela,
            columns=colunas_iniciais,
            show='headings',
            selectmode='browse',
            yscrollcommand=self.scroll_tree_y.set,
            xscrollcommand=self.scroll_tree_x.set
        )
        self.scroll_tree_y.configure(command=self.tree.yview)
        self.scroll_tree_x.configure(command=self.tree.xview)

        self.scroll_tree_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(1, 2), pady=2)
        self.scroll_tree_x.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(1, 2))
        self.tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.tree.tag_configure('credito', foreground='#10B981')
        self.tree.tag_configure('debito', foreground='#F43F5E')
        self.tree.tag_configure('padrao', foreground='#F3F4F6')
        self.tree.tag_configure('linha_par', background='#111827')
        self.tree.tag_configure('linha_impar', background='#0D131F')
        self.tree.bind("<Double-1>", self.ao_clicar_duas_vezes_linha)

        self.atualizar_colunas_treeview()

        # Frame JSON com CTkScrollbar nas cores do tema
        self.frame_json = ctk.CTkFrame(self.container_dados, fg_color="#07090E", corner_radius=8, border_width=1, border_color="#1F2937")

        self.scroll_json_y = ctk.CTkScrollbar(
            self.frame_json,
            orientation="vertical",
            fg_color="#07090E",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            width=12
        )
        self.scroll_json_x = ctk.CTkScrollbar(
            self.frame_json,
            orientation="horizontal",
            fg_color="#07090E",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            height=12
        )

        self.txt_json_t1 = tk.Text(
            self.frame_json,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#07090E",
            fg="#D4D4D4",
            insertbackground="#FFFFFF",
            selectbackground="#264F78",
            selectforeground="#FFFFFF",
            bd=0,
            yscrollcommand=self.scroll_json_y.set,
            xscrollcommand=self.scroll_json_x.set
        )
        self.scroll_json_y.configure(command=self.txt_json_t1.yview)
        self.scroll_json_x.configure(command=self.txt_json_t1.xview)

        self.scroll_json_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 2), pady=2)
        self.scroll_json_x.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(2, 2))
        self.txt_json_t1.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.txt_json_t1.tag_configure("key", foreground="#9CDCFE")
        self.txt_json_t1.tag_configure("string", foreground="#CE9178")
        self.txt_json_t1.tag_configure("number", foreground="#B5CEA8")
        self.txt_json_t1.tag_configure("boolean", foreground="#569CD6")
        self.txt_json_t1.tag_configure("highlight", background="#4A3B00", foreground="#FFFFFF")
        self.txt_json_t1.tag_configure("current_highlight", background="#FF9900", foreground="#000000")

    def exibir_alerta(self, titulo, mensagem, cor="#1E293B"):
        """Exibe uma mensagem no banner de status da janela"""
        texto_completo = f"{titulo}: {mensagem}" if mensagem else titulo
        cor_texto = "#FFFFFF" if cor != "#1E293B" else "#94A3B8"
        if hasattr(self, 'lbl_status_msg'):
            self.lbl_status_msg.configure(text=texto_completo, text_color=cor_texto)
        if hasattr(self, 'banner_status') and cor != "#1E293B":
            self.banner_status.configure(fg_color=cor)
            try:
                self.banner_status.pack(fill=tk.X, padx=8, pady=(0, 6), before=self.frame_kpis)
                self.lbl_status_msg.pack(side=tk.LEFT, padx=12, pady=4)
                self.after(5000, lambda: self.banner_status.pack_forget())
            except Exception:
                pass

    def setup_aba_diagnostico(self):
        # 1. Painel Superior de Controles e Busca
        card_diag_ctrl = ctk.CTkFrame(self.tab_diagnostico, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_diag_ctrl.pack(fill=tk.X, padx=8, pady=(8, 10))

        row1 = ctk.CTkFrame(card_diag_ctrl, fg_color="transparent")
        row1.pack(fill=tk.X, padx=16, pady=12)

        lbl = ctk.CTkLabel(row1, text="Item ID:", font=("Segoe UI", 12, "bold"), text_color="#E2E8F0", width=65, anchor="w")
        lbl.pack(side=tk.LEFT)

        self.entry_diag_item_id = ctk.CTkEntry(
            row1,
            placeholder_text="Informe o Item ID para diagnóstico completo e análise de integridade...",
            height=36,
            font=("Consolas", 11),
            border_color="#1F2937"
        )
        self.entry_diag_item_id.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 12))
        self.entry_diag_item_id.bind("<Return>", lambda e: self.acao_diagnosticar_item())

        self.btn_reconectar_diag = ctk.CTkButton(
            row1,
            text="⚡ Reconectar Item",
            width=145,
            height=36,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 12, "bold"),
            command=self.acao_reconectar_item_diag
        )
        self.btn_reconectar_diag.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_consultar_diag = ctk.CTkButton(
            row1,
            text="Consultar Status",
            width=145,
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 12, "bold"),
            command=self.acao_diagnosticar_item
        )
        self.btn_consultar_diag.pack(side=tk.RIGHT)

        # Barra compacta de status rápido
        self.card_diag_status = ctk.CTkFrame(card_diag_ctrl, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        self.card_diag_status.pack(fill=tk.X, padx=16, pady=(0, 10))

        self.lbl_diag_status = ctk.CTkLabel(self.card_diag_status, text="Status: Aguardando consulta...", font=("Segoe UI", 13, "bold"), text_color="#F59E0B")
        self.lbl_diag_status.pack(anchor="w", padx=14, pady=(8, 2))

        self.lbl_diag_erro = ctk.CTkLabel(self.card_diag_status, text="Detalhes: Nenhum item consultado ainda.", font=("Segoe UI", 11), text_color="#E2E8F0")
        self.lbl_diag_erro.pack(anchor="w", padx=14, pady=(2, 8))

        # 2. Barra de Alternância de Modo (Visual Amigável vs Código JSON)
        bar_diag_switcher = ctk.CTkFrame(self.tab_diagnostico, fg_color="transparent")
        bar_diag_switcher.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.seg_modo_diag = ctk.CTkSegmentedButton(
            bar_diag_switcher,
            values=["Visual Amigável", "Código Puro (JSON)"],
            selected_color="#0284C7",
            selected_hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=self.alternar_modo_diagnostico
        )
        self.seg_modo_diag.set("Visual Amigável")
        self.seg_modo_diag.pack(side=tk.LEFT)

        # Toolbar Contextual do Modo Visual (Ações Rápidas)
        self.tools_diag_visual = ctk.CTkFrame(bar_diag_switcher, fg_color="transparent")
        self.tools_diag_visual.pack(side=tk.RIGHT)

        self.btn_copiar_relatorio_diag = ctk.CTkButton(
            self.tools_diag_visual,
            text="📋 Copiar Parecer",
            width=135,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.copiar_relatorio_diagnostico
        )
        self.btn_copiar_relatorio_diag.pack(side=tk.RIGHT, padx=(4, 0))

        # Toolbar Contextual do Modo Código (Busca e Cópia do JSON)
        self.tools_diag_json = ctk.CTkFrame(bar_diag_switcher, fg_color="transparent")

        self.btn_copiar_json_t2 = ctk.CTkButton(
            self.tools_diag_json,
            text="Copiar JSON",
            width=95,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10),
            command=lambda: self.copiar_para_clipboard(self.txt_json_t2.get("1.0", tk.END).strip(), self.btn_copiar_json_t2)
        )
        self.btn_copiar_json_t2.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_next_j2 = ctk.CTkButton(self.tools_diag_json, text="▼", width=26, height=32, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_proximo_json_t2)
        self.btn_next_j2.pack(side=tk.RIGHT, padx=2)

        self.btn_prev_j2 = ctk.CTkButton(self.tools_diag_json, text="▲", width=26, height=32, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_anterior_json_t2)
        self.btn_prev_j2.pack(side=tk.RIGHT, padx=2)

        self.lbl_busca_status_t2 = ctk.CTkLabel(self.tools_diag_json, text="", font=("Segoe UI", 10), text_color="#94A3B8")
        self.lbl_busca_status_t2.pack(side=tk.RIGHT, padx=4)

        self.entry_busca_t2 = ctk.CTkEntry(
            self.tools_diag_json,
            placeholder_text="Buscar no JSON...",
            width=170,
            height=32,
            font=("Consolas", 10),
            border_color="#1F2937"
        )
        self.entry_busca_t2.pack(side=tk.RIGHT, padx=4)
        self.entry_busca_t2.bind("<Return>", lambda e: self.acao_buscar_t2())
        self.entry_busca_t2.bind("<KeyRelease>", lambda e: self.acao_buscar_t2())

        # 3. Contêiner de Dados Central
        self.container_diag_conteudo = ctk.CTkFrame(self.tab_diagnostico, fg_color="transparent")
        self.container_diag_conteudo.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # A) Visão Amigável (Scrollable)
        self.scroll_diag_visual = ctk.CTkScrollableFrame(
            self.container_diag_conteudo,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_diag_visual.pack(fill=tk.BOTH, expand=True)

        # Placeholder / Empty State (inicial)
        self.frame_diag_empty = ctk.CTkFrame(self.scroll_diag_visual, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.frame_diag_empty.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        ctk.CTkLabel(
            self.frame_diag_empty,
            text="🩺",
            font=("Segoe UI", 42)
        ).pack(pady=(36, 10))

        ctk.CTkLabel(
            self.frame_diag_empty,
            text="Diagnóstico Inteligente de Integridade e Erros",
            font=("Segoe UI", 18, "bold"),
            text_color="#FFFFFF"
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            self.frame_diag_empty,
            text="Analise a integridade de conexões Open Finance, detecte causas de falhas\nde login ou MFA e consulte pareceres técnicos com recomendações claras.",
            font=("Segoe UI", 12),
            text_color="#94A3B8",
            justify="center"
        ).pack(pady=(0, 24), padx=20)

        # Passos instrutivos no empty state
        box_inst = ctk.CTkFrame(self.frame_diag_empty, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        box_inst.pack(padx=30, pady=(0, 36), fill=tk.X)

        itens_inst = [
            ("1", "Informe o Item ID no campo superior", "Cole o identificador retornado na criação da conexão ou na aba de transações."),
            ("2", "Clique em 'Consultar Status'", "O sistema consultará o status do conector bancário, mapeará eventuais falhas e sugerirá ações."),
            ("3", "Alterne entre Visão Visual e Código JSON", "Use o botão seletor acima para alternar em tempo real entre o parecer amigável e o JSON puro.")
        ]
        for num, tit, desc in itens_inst:
            row_i = ctk.CTkFrame(box_inst, fg_color="transparent")
            row_i.pack(fill=tk.X, padx=16, pady=10)
            badge_n = ctk.CTkFrame(row_i, width=28, height=28, fg_color="#0284C7", corner_radius=14)
            badge_n.pack(side=tk.LEFT, padx=(0, 12))
            badge_n.pack_propagate(False)
            ctk.CTkLabel(badge_n, text=num, font=("Segoe UI", 12, "bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")
            f_txt = ctk.CTkFrame(row_i, fg_color="transparent")
            f_txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ctk.CTkLabel(f_txt, text=tit, font=("Segoe UI", 12, "bold"), text_color="#E2E8F0", anchor="w").pack(anchor="w")
            ctk.CTkLabel(f_txt, text=desc, font=("Segoe UI", 11), text_color="#94A3B8", anchor="w").pack(anchor="w")

        # Frame de Diagnóstico Ativo (inicialmente pack_forget)
        self.frame_diag_ativo = ctk.CTkFrame(self.scroll_diag_visual, fg_color="transparent")

        # --- Card 1: Banner de Status Hero & Conector ---
        self.card_diag_hero = ctk.CTkFrame(self.frame_diag_ativo, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        self.card_diag_hero.pack(fill=tk.X, pady=(0, 10))

        row_hero_top = ctk.CTkFrame(self.card_diag_hero, fg_color="transparent")
        row_hero_top.pack(fill=tk.X, padx=16, pady=(14, 8))

        # Pill Status
        self.frame_pill_diag_status = ctk.CTkFrame(row_hero_top, fg_color="#1E293B", corner_radius=14, border_width=1, border_color="#334155")
        self.frame_pill_diag_status.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
        self.lbl_pill_diag_status = ctk.CTkLabel(self.frame_pill_diag_status, text="● AGUARDANDO", font=("Segoe UI", 11, "bold"), text_color="#F59E0B")
        self.lbl_pill_diag_status.pack(padx=14, pady=2)

        # Pill Execution Status
        self.frame_pill_diag_exec = ctk.CTkFrame(row_hero_top, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1F2937")
        self.frame_pill_diag_exec.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
        self.lbl_pill_diag_exec = ctk.CTkLabel(self.frame_pill_diag_exec, text="EXECUÇÃO: -", font=("Segoe UI", 10, "bold"), text_color="#94A3B8")
        self.lbl_pill_diag_exec.pack(padx=12, pady=2)

        # Pill Falhas (aparece se houver tentativas falhas > 0)
        self.frame_pill_diag_falhas = ctk.CTkFrame(row_hero_top, fg_color="#4C0519", corner_radius=14, border_width=1, border_color="#881337")
        self.lbl_pill_diag_falhas = ctk.CTkLabel(self.frame_pill_diag_falhas, text="⚠️ 0 Falhas", font=("Segoe UI", 10, "bold"), text_color="#F43F5E")
        self.lbl_pill_diag_falhas.pack(padx=12, pady=2)

        # Linha inferior do Hero: Dados do Banco / Conector
        row_hero_bot = ctk.CTkFrame(self.card_diag_hero, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1F2937")
        row_hero_bot.pack(fill=tk.X, padx=16, pady=(0, 14))

        col_banco = ctk.CTkFrame(row_hero_bot, fg_color="transparent")
        col_banco.pack(side=tk.LEFT, padx=14, pady=10, fill=tk.X, expand=True)

        row_banco_tit = ctk.CTkFrame(col_banco, fg_color="transparent")
        row_banco_tit.pack(fill=tk.X)

        self.bar_banco_cor = ctk.CTkFrame(row_banco_tit, width=5, height=22, fg_color="#0284C7", corner_radius=2)
        self.bar_banco_cor.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_diag_banco_nome = ctk.CTkLabel(row_banco_tit, text="Instituição Financeira", font=("Segoe UI", 15, "bold"), text_color="#FFFFFF")
        self.lbl_diag_banco_nome.pack(side=tk.LEFT)

        self.lbl_diag_banco_detalhes = ctk.CTkLabel(col_banco, text="Conector # - • Tipo não informado", font=("Segoe UI", 11), text_color="#94A3B8", anchor="w")
        self.lbl_diag_banco_detalhes.pack(anchor="w", padx=(13, 0), pady=(2, 0))

        col_datas = ctk.CTkFrame(row_hero_bot, fg_color="transparent")
        col_datas.pack(side=tk.RIGHT, padx=14, pady=10)

        self.lbl_diag_sync_time = ctk.CTkLabel(col_datas, text="Último Sync: -", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="e")
        self.lbl_diag_sync_time.pack(anchor="e")

        self.lbl_diag_created_time = ctk.CTkLabel(col_datas, text="Criado em: -", font=("Segoe UI", 10), text_color="#64748B", anchor="e")
        self.lbl_diag_created_time.pack(anchor="e", pady=(2, 0))

        # --- Card Amigável de Comunicado de Banco / Incidente (status.pluggy.ai) ---
        self.card_diag_incidente_alerta = ctk.CTkFrame(
            self.frame_diag_ativo,
            fg_color="#0F172A",
            corner_radius=12,
            border_width=1,
            border_color="#1E293B"
        )
        # Inicialmente não empacotado (exibido apenas se houver comunicados ativos na instituição)

        row_inc_top = ctk.CTkFrame(self.card_diag_incidente_alerta, fg_color="transparent")
        row_inc_top.pack(fill=tk.X, padx=16, pady=(12, 6))

        self.lbl_inc_header_tag = ctk.CTkLabel(
            row_inc_top,
            text="ℹ️ COMUNICADO DO PROVEDOR BANCÁRIO",
            font=("Segoe UI", 11, "bold"),
            text_color="#38BDF8"
        )
        self.lbl_inc_header_tag.pack(side=tk.LEFT)

        self.frame_inc_severity_badge = ctk.CTkFrame(row_inc_top, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#F59E0B")
        self.frame_inc_severity_badge.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_inc_severity = ctk.CTkLabel(
            self.frame_inc_severity_badge,
            text="Oscilação Temporária",
            font=("Segoe UI", 9, "bold"),
            text_color="#F59E0B"
        )
        self.lbl_inc_severity.pack(padx=8, pady=2)

        self.btn_inc_ver_web = ctk.CTkButton(
            row_inc_top,
            text="Acompanhar no status.pluggy.ai ↗",
            width=200,
            height=28,
            font=("Segoe UI", 10, "bold"),
            fg_color="#1E293B",
            hover_color="#334155"
        )
        self.btn_inc_ver_web.pack(side=tk.RIGHT)

        self.lbl_inc_titulo = ctk.CTkLabel(
            self.card_diag_incidente_alerta,
            text="Oscilação informada pela instituição financeira",
            font=("Segoe UI", 13, "bold"),
            text_color="#F8FAFC",
            anchor="w"
        )
        self.lbl_inc_titulo.pack(fill=tk.X, padx=16, pady=(4, 2))

        self.lbl_inc_detalhes = ctk.CTkLabel(
            self.card_diag_incidente_alerta,
            text="Acompanhamento técnico em andamento pelo provedor bancário.",
            font=("Segoe UI", 11),
            text_color="#94A3B8",
            wraplength=880,
            justify="left",
            anchor="w"
        )
        self.lbl_inc_detalhes.pack(fill=tk.X, padx=16, pady=(0, 6))

        box_dica_amigavel = ctk.CTkFrame(self.card_diag_incidente_alerta, fg_color="#111827", corner_radius=8, border_width=1, border_color="#1E293B")
        box_dica_amigavel.pack(fill=tk.X, padx=16, pady=(0, 12))

        self.lbl_inc_aviso = ctk.CTkLabel(
            box_dica_amigavel,
            text="💡 Suas credenciais e dados permanecem 100% seguros. Esta oscilação ocorre no próprio provedor bancário e afeta apenas o tempo de sincronização. Não é necessário refazer o login ou desconectar a conta agora.",
            font=("Segoe UI", 11),
            text_color="#CBD5E1",
            wraplength=880,
            justify="left",
            anchor="w"
        )
        self.lbl_inc_aviso.pack(fill=tk.X, padx=12, pady=10)

        # --- Card 2: Parecer do Diagnóstico & Solução Recomendada ---
        self.card_diag_parecer = ctk.CTkFrame(self.frame_diag_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_diag_parecer.pack(fill=tk.X, pady=(0, 10))

        row_par_top = ctk.CTkFrame(self.card_diag_parecer, fg_color="transparent")
        row_par_top.pack(fill=tk.X, padx=16, pady=(12, 4))
        ctk.CTkLabel(row_par_top, text="📋 PARECER TÉCNICO & ORIENTAÇÃO DE RESOLUÇÃO", font=("Segoe UI", 11, "bold"), text_color="#94A3B8").pack(side=tk.LEFT)

        self.lbl_parecer_titulo = ctk.CTkLabel(self.card_diag_parecer, text="Diagnóstico", font=("Segoe UI", 15, "bold"), text_color="#FFFFFF", anchor="w")
        self.lbl_parecer_titulo.pack(fill=tk.X, padx=16, pady=(4, 2))

        self.lbl_parecer_desc = ctk.CTkLabel(self.card_diag_parecer, text="Descrição detalhada do diagnóstico.", font=("Segoe UI", 12), text_color="#CBD5E1", wraplength=900, justify="left", anchor="w")
        self.lbl_parecer_desc.pack(fill=tk.X, padx=16, pady=(2, 10))

        # Box de Ação Recomendada
        self.box_parecer_acao = ctk.CTkFrame(self.card_diag_parecer, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
        self.box_parecer_acao.pack(fill=tk.X, padx=16, pady=(0, 12))

        lbl_acao_tag = ctk.CTkLabel(self.box_parecer_acao, text="👉 O que fazer (Ação Recomendada):", font=("Segoe UI", 11, "bold"), text_color="#38BDF8", anchor="w")
        lbl_acao_tag.pack(fill=tk.X, padx=12, pady=(10, 2))

        self.lbl_parecer_acao = ctk.CTkLabel(self.box_parecer_acao, text="Ação recomendada.", font=("Segoe UI", 11), text_color="#E2E8F0", wraplength=880, justify="left", anchor="w")
        self.lbl_parecer_acao.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.btn_box_reconnect = ctk.CTkButton(
            self.box_parecer_acao,
            text="⚡ Abrir Pluggy Connect para Reconectar / Atualizar este Item",
            height=34,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 11, "bold"),
            command=self.acao_reconectar_item_diag
        )
        self.btn_box_reconnect.pack(fill=tk.X, padx=12, pady=(0, 10))

        # Box de Detalhes Técnicos
        self.box_parecer_tecnico = ctk.CTkFrame(self.card_diag_parecer, fg_color="#07090E", corner_radius=8, border_width=1, border_color="#1F2937")
        self.lbl_parecer_tecnico_cod = ctk.CTkLabel(self.box_parecer_tecnico, text="Código: -", font=("Consolas", 11, "bold"), text_color="#F43F5E", anchor="w")
        self.lbl_parecer_tecnico_cod.pack(fill=tk.X, padx=12, pady=(8, 2))
        self.lbl_parecer_tecnico_msg = ctk.CTkLabel(self.box_parecer_tecnico, text="Mensagem da API: -", font=("Consolas", 10), text_color="#94A3B8", wraplength=880, justify="left", anchor="w")
        self.lbl_parecer_tecnico_msg.pack(fill=tk.X, padx=12, pady=(0, 8))

        # --- Card 3: Instituição & Contas Bancárias Vinculadas ---
        self.card_diag_contas = ctk.CTkFrame(self.frame_diag_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_diag_contas.pack(fill=tk.X, pady=(0, 10))

        row_c_top = ctk.CTkFrame(self.card_diag_contas, fg_color="transparent")
        row_c_top.pack(fill=tk.X, padx=16, pady=(12, 4))
        ctk.CTkLabel(row_c_top, text="🏦 INSTITUIÇÃO & CONTAS BANCÁRIAS VINCULADAS", font=("Segoe UI", 11, "bold"), text_color="#94A3B8").pack(side=tk.LEFT)

        self.lbl_contas_banco_info = ctk.CTkLabel(
            self.card_diag_contas,
            text="Instituição Financeira",
            font=("Segoe UI", 12, "bold"),
            text_color="#FFFFFF",
            anchor="w"
        )
        self.lbl_contas_banco_info.pack(fill=tk.X, padx=16, pady=(2, 6))

        self.frame_lista_contas_diag = ctk.CTkFrame(self.card_diag_contas, fg_color="transparent")
        self.frame_lista_contas_diag.pack(fill=tk.X, padx=16, pady=(0, 12))

        # --- Card 4: Status por Produto / Recurso (statusDetail) ---
        self.card_diag_produtos = ctk.CTkFrame(self.frame_diag_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_diag_produtos.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(self.card_diag_produtos, text="📦 STATUS POR PRODUTO BANCÁRIO (statusDetail)", font=("Segoe UI", 11, "bold"), text_color="#94A3B8").pack(anchor="w", padx=16, pady=(12, 6))

        self.frame_chips_diag_produtos = ctk.CTkFrame(self.card_diag_produtos, fg_color="transparent")
        self.frame_chips_diag_produtos.pack(fill=tk.X, padx=16, pady=(0, 12))

        # --- Card 5: Rodapé com Ações Rápidas ---
        card_rodape = ctk.CTkFrame(self.frame_diag_ativo, fg_color="transparent")
        card_rodape.pack(fill=tk.X, pady=(4, 16))

        self.btn_rod_reconnect = ctk.CTkButton(
            card_rodape,
            text="⚡ Reconectar via Widget",
            height=36,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 11, "bold"),
            command=self.acao_reconectar_item_diag
        )
        self.btn_rod_reconnect.pack(side=tk.LEFT, padx=(0, 8))

        btn_rod_parecer = ctk.CTkButton(
            card_rodape,
            text="📋 Copiar Parecer Formatado",
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11, "bold"),
            command=self.copiar_relatorio_diagnostico
        )
        btn_rod_parecer.pack(side=tk.LEFT, padx=(0, 8))

        btn_rod_code = ctk.CTkButton(
            card_rodape,
            text="</> Ver Payload JSON (Código)",
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=lambda: self.seg_modo_diag.set("Código Puro (JSON)") or self.alternar_modo_diagnostico("Código Puro (JSON)")
        )
        btn_rod_code.pack(side=tk.LEFT)

        # B) Frame de Código Puro (JSON) (inicialmente oculto)
        self.card_diag_json = ctk.CTkFrame(
            self.container_diag_conteudo,
            fg_color="#07090E",
            corner_radius=10,
            border_width=1,
            border_color="#1F2937"
        )

        self.scroll_diag_y = ctk.CTkScrollbar(
            self.card_diag_json,
            orientation="vertical",
            fg_color="#07090E",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            width=12
        )
        self.scroll_diag_x = ctk.CTkScrollbar(
            self.card_diag_json,
            orientation="horizontal",
            fg_color="#07090E",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            height=12
        )

        self.txt_json_t2 = tk.Text(
            self.card_diag_json,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#07090E",
            fg="#D4D4D4",
            insertbackground="#FFFFFF",
            selectbackground="#264F78",
            selectforeground="#FFFFFF",
            bd=0,
            yscrollcommand=self.scroll_diag_y.set,
            xscrollcommand=self.scroll_diag_x.set
        )
        self.scroll_diag_y.configure(command=self.txt_json_t2.yview)
        self.scroll_diag_x.configure(command=self.txt_json_t2.xview)

        self.scroll_diag_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 2), pady=2)
        self.scroll_diag_x.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(2, 2))
        self.txt_json_t2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.txt_json_t2.tag_configure("key", foreground="#9CDCFE")
        self.txt_json_t2.tag_configure("string", foreground="#CE9178")
        self.txt_json_t2.tag_configure("number", foreground="#B5CEA8")
        self.txt_json_t2.tag_configure("boolean", foreground="#569CD6")
        self.txt_json_t2.tag_configure("highlight", background="#4B5563", foreground="#FFFFFF")
        self.txt_json_t2.tag_configure("current_highlight", background="#F59E0B", foreground="#000000")

    def alternar_modo_diagnostico(self, modo=None):
        """Alterna a exibição entre a Visão Visual Amigável e o Código Puro (JSON)"""
        if modo is None:
            modo = self.seg_modo_diag.get()
        if "Visual" in modo:
            self.card_diag_json.pack_forget()
            self.tools_diag_json.pack_forget()
            self.tools_diag_visual.pack(side=tk.RIGHT)
            self.scroll_diag_visual.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t2()
        else:
            self.scroll_diag_visual.pack_forget()
            self.tools_diag_visual.pack_forget()
            self.tools_diag_json.pack(side=tk.RIGHT)
            self.card_diag_json.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t2()

    def atualizar_ui_diagnostico_visual(self, data):
        """Atualiza a visão amigável de diagnóstico a partir dos dados do item ou consentimento"""
        info = analisar_diagnostico_item(data)
        if not info:
            return

        self.item_diag_info = info

        # Oculta empty state e exibe frame de dados ativos
        self.frame_diag_empty.pack_forget()
        self.frame_diag_ativo.pack(fill=tk.BOTH, expand=True)

        # 1. Hero Card
        self.card_diag_hero.configure(border_color=info["status_border"])
        self.frame_pill_diag_status.configure(fg_color=info["status_bg"], border_color=info["status_border"])
        self.lbl_pill_diag_status.configure(
            text=f"{info['status_icone']} {info['status_label']}",
            text_color=info["status_cor"]
        )

        exec_text = f"EXECUÇÃO: {info['exec_status']}"
        exec_cor = "#10B981" if info['exec_status'] == "SUCCESS" else ("#F43F5E" if info['exec_status'] == "ERROR" else "#94A3B8")
        self.lbl_pill_diag_exec.configure(text=exec_text, text_color=exec_cor)

        if info["tentativas_falhas"] > 0:
            self.lbl_pill_diag_falhas.configure(text=f"⚠️ {info['tentativas_falhas']} Falhas de Login")
            self.frame_pill_diag_falhas.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
        else:
            self.frame_pill_diag_falhas.pack_forget()

        # Conector / Instituição
        self.bar_banco_cor.configure(fg_color=info["banco_cor"])
        self.lbl_diag_banco_nome.configure(text=f"🏦 {info['banco_nome']}")
        detalhes_con = f"Conector #{info['banco_id']} • {info['banco_tipo']}"
        self.lbl_diag_banco_detalhes.configure(text=detalhes_con)

        self.lbl_diag_sync_time.configure(text=f"Última Sincronização: {info['updated_str']}")
        self.lbl_diag_created_time.configure(text=f"Criado em: {info['created_str']}")

        # Alerta de Incidente no Conector do Banco (status.pluggy.ai)
        incidentes_con = info.get("incidentes_conector") or []
        if incidentes_con:
            primeiro_inc = incidentes_con[0]
            tit_inc = primeiro_inc.get("title") or "Oscilação temporária informada pela instituição financeira"
            sev_inc = str(primeiro_inc.get("severity") or "DEGRADED").upper()
            state_inc = str(primeiro_inc.get("state") or "INVESTIGATING").upper()
            started_inc = formatar_data_hora_br(primeiro_inc.get("startedAt") or primeiro_inc.get("started_at"))
            url_inc = primeiro_inc.get("url") or (f"https://status.pluggy.ai/incident/{primeiro_inc.get('id')}" if primeiro_inc.get('id') else "https://status.pluggy.ai")

            estados_map = {
                "INVESTIGATING": "Equipe técnica acompanhando",
                "IDENTIFIED": "Causa identificada pelo banco",
                "MONITORING": "Fase final de normalização",
                "SCHEDULED": "Janela de manutenção programada",
                "UPDATE": "Atualizado recentemente",
                "RESOLVED": "Normalizado"
            }
            state_friendly = estados_map.get(state_inc, state_inc.title())

            if "OUTAGE" in sev_inc or "MAJOR" in sev_inc:
                cor_inc = "#FB7185"
                border_inc = "#881337"
                label_sev = "● Instabilidade Temporária"
            elif "MAINTENANCE" in sev_inc:
                cor_inc = "#38BDF8"
                border_inc = "#0284C7"
                label_sev = "● Manutenção Programada"
            else:
                cor_inc = "#F59E0B"
                border_inc = "#78350F"
                label_sev = "● Oscilação Temporária"

            self.card_diag_incidente_alerta.configure(border_color=border_inc)
            self.frame_inc_severity_badge.configure(border_color=cor_inc)
            self.lbl_inc_severity.configure(text=label_sev, text_color=cor_inc)
            self.lbl_inc_header_tag.configure(text_color="#38BDF8")
            self.lbl_inc_titulo.configure(text=f"🏦 {tit_inc}")

            txt_detalhes = f"Situação: {state_friendly}  •  Registrado em: {started_inc}"
            if len(incidentes_con) > 1:
                txt_detalhes += f"  •  (+{len(incidentes_con)-1} outro comunicado desta instituição)"
            self.lbl_inc_detalhes.configure(text=txt_detalhes)

            self.btn_inc_ver_web.configure(command=lambda u=url_inc: webbrowser.open(u))
            self.card_diag_incidente_alerta.pack(fill=tk.X, pady=(0, 10), before=self.card_diag_parecer)
        else:
            self.card_diag_incidente_alerta.pack_forget()

        # 2. Card de Parecer & Solução
        self.card_diag_parecer.configure(border_color=info["status_border"])
        self.lbl_parecer_titulo.configure(text=info["resumo_titulo"], text_color=info["status_cor"])
        self.lbl_parecer_desc.configure(text=info["resumo_desc"])
        self.lbl_parecer_acao.configure(text=info["recomendacao"])

        # Detalhes técnicos
        if info["tem_erro"] and (info["erro_codigo"] or info["erro_mensagem"]):
            cod_raw = info.get("erro_codigo") or "N/A"
            cod_trad = info.get("erro_codigo_traduzido") or traduzir_codigo_erro_pluggy(cod_raw)
            cod_str = f"Código do Erro: {cod_raw}"
            if cod_trad and cod_trad != cod_raw:
                cod_str += f" ({cod_trad})"
            if info.get("erro_provider"):
                cod_str += f" | Provider Code: {info['erro_provider']}"
            self.lbl_parecer_tecnico_cod.configure(text=cod_str)

            msg_raw = info.get("erro_mensagem") or "Sem detalhes"
            msg_trad = info.get("erro_mensagem_traduzida") or traduzir_mensagem_erro_pluggy(msg_raw)
            self.lbl_parecer_tecnico_msg.configure(text=f"Mensagem da API Pluggy: {msg_trad} (Original: \"{msg_raw}\")" if msg_trad != msg_raw else f"Mensagem da API Pluggy: {msg_raw}")
            self.box_parecer_tecnico.pack(fill=tk.X, padx=16, pady=(0, 12))
        else:
            self.box_parecer_tecnico.pack_forget()

        # 3. Informações Bancárias & Contas Vinculadas
        banco_desc = f"Instituição: {info['banco_nome']} • Conector #{info['banco_id']} ({info['banco_tipo']})"
        self.lbl_contas_banco_info.configure(text=banco_desc)

        for w in self.frame_lista_contas_diag.winfo_children():
            w.destroy()

        contas = info.get("contas_vinculadas") or []
        if contas:
            for acc in contas:
                acc_card = ctk.CTkFrame(
                    self.frame_lista_contas_diag,
                    fg_color="#0B0F19",
                    corner_radius=10,
                    border_width=1,
                    border_color="#1E293B"
                )
                acc_card.pack(fill=tk.X, pady=4)

                # Linha Superior da Conta: Nome, Tipo e Saldo
                row_acc_top = ctk.CTkFrame(acc_card, fg_color="transparent")
                row_acc_top.pack(fill=tk.X, padx=14, pady=(10, 4))

                col_left = ctk.CTkFrame(row_acc_top, fg_color="transparent")
                col_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

                nome_conta = acc.get("nome") or "Conta Bancária"
                ctk.CTkLabel(
                    col_left,
                    text=f"💳 {nome_conta}",
                    font=("Segoe UI", 13, "bold"),
                    text_color="#FFFFFF"
                ).pack(side=tk.LEFT)

                tipo_conta = acc.get("tipo") or "Conta"
                badge_tipo = ctk.CTkFrame(col_left, fg_color="#1E293B", corner_radius=6, border_width=1, border_color="#334155")
                badge_tipo.pack(side=tk.LEFT, padx=(10, 0))
                ctk.CTkLabel(
                    badge_tipo,
                    text=tipo_conta,
                    font=("Segoe UI", 9, "bold"),
                    text_color="#38BDF8"
                ).pack(padx=8, pady=2)

                col_right = ctk.CTkFrame(row_acc_top, fg_color="transparent")
                col_right.pack(side=tk.RIGHT)

                saldo_str = acc.get("saldo_str", "Não informado")
                saldo_num = acc.get("saldo_num")
                saldo_cor = "#10B981" if saldo_num is not None and saldo_num >= 0 else ("#F43F5E" if saldo_num is not None else "#94A3B8")
                ctk.CTkLabel(
                    col_right,
                    text=f"Saldo: {saldo_str}",
                    font=("Segoe UI", 12, "bold"),
                    text_color=saldo_cor
                ).pack(side=tk.RIGHT)

                # Linha Inferior da Conta: Agência, Conta, Titular e Ação de Cópia
                row_acc_bot = ctk.CTkFrame(acc_card, fg_color="transparent")
                row_acc_bot.pack(fill=tk.X, padx=14, pady=(2, 10))

                detalhes = []
                if acc.get("agencia") and acc.get("agencia") != "-":
                    detalhes.append(f"Agência: {acc['agencia']}")
                if acc.get("numero") and acc.get("numero") != "-":
                    detalhes.append(f"Conta: {acc['numero']}")
                if acc.get("titular") and acc.get("titular") != "-":
                    detalhes.append(f"Titular: {acc['titular']}")
                if acc.get("id"):
                    detalhes.append(f"ID: {acc['id']}")

                txt_sub = "  •  ".join(detalhes) if detalhes else "Dados adicionais não informados pelo conector."

                ctk.CTkLabel(
                    row_acc_bot,
                    text=txt_sub,
                    font=("Segoe UI", 10),
                    text_color="#94A3B8",
                    anchor="w"
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)

                def _copiar_acc(a=acc, b_nome=info['banco_nome']):
                    txt = (
                        f"Banco: {b_nome}\n"
                        f"Nome da Conta: {a.get('nome')}\n"
                        f"Tipo: {a.get('tipo')}\n"
                        f"Agência: {a.get('agencia')}\n"
                        f"Número da Conta: {a.get('numero')}\n"
                        f"Titular: {a.get('titular')}\n"
                        f"Saldo: {a.get('saldo_str')}\n"
                        f"ID da Conta: {a.get('id')}"
                    )
                    self.copiar_para_clipboard(txt)

                btn_copiar = ctk.CTkButton(
                    row_acc_bot,
                    text="Copiar Dados",
                    width=90,
                    height=24,
                    fg_color="#1E293B",
                    hover_color="#334155",
                    font=("Segoe UI", 9),
                    command=_copiar_acc
                )
                btn_copiar.pack(side=tk.RIGHT)
        else:
            box_vazio = ctk.CTkFrame(self.frame_lista_contas_diag, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            box_vazio.pack(fill=tk.X, pady=4)
            ctk.CTkLabel(
                box_vazio,
                text="ℹ️ Nenhuma conta bancária sincronizada localizada para este Item.",
                font=("Segoe UI", 11, "bold"),
                text_color="#94A3B8"
            ).pack(anchor="w", padx=14, pady=(8, 2))
            ctk.CTkLabel(
                box_vazio,
                text="Caso a conexão tenha falhado antes da sincronização ou ainda esteja em processamento, as contas serão exibidas assim que a instituição finalizar a leitura.",
                font=("Segoe UI", 10),
                text_color="#64748B"
            ).pack(anchor="w", padx=14, pady=(0, 8))

        # 4. Produtos (statusDetail)
        for w in self.frame_chips_diag_produtos.winfo_children():
            w.destroy()

        prods = info.get("produtos_detalhe") or []
        if prods:
            self.card_diag_produtos.pack(fill=tk.X, pady=(0, 10))
            for p in prods:
                chip = ctk.CTkFrame(self.frame_chips_diag_produtos, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
                chip.pack(fill=tk.X, pady=3)

                c_left = ctk.CTkFrame(chip, fg_color="transparent")
                c_left.pack(side=tk.LEFT, padx=12, pady=8)

                p_nome = p.get("nome", "")
                icone_p = "💳" if "conta" in p_nome.lower() else ("📊" if "transa" in p_nome.lower() else ("📈" if "invest" in p_nome.lower() else "👤"))
                ctk.CTkLabel(c_left, text=f"{icone_p} {p_nome}", font=("Segoe UI", 11, "bold"), text_color="#E2E8F0").pack(side=tk.LEFT)

                c_right = ctk.CTkFrame(chip, fg_color="transparent")
                c_right.pack(side=tk.RIGHT, padx=12, pady=8)

                tipo_st = p.get("tipo_status", "ok" if p.get("is_updated") else "pendente")
                if tipo_st == "desconectado":
                    cor_p = "#FB7185"
                    bg_badge = "#4C0519"
                    border_badge = "#881337"
                    txt_p = p.get("status_str") or "✕ Desconectado"
                    cor_data = "#FB7185"
                elif tipo_st == "erro":
                    cor_p = "#F59E0B"
                    bg_badge = "#451A03"
                    border_badge = "#78350F"
                    txt_p = p.get("status_str") or "⚠ Interrompido"
                    cor_data = "#F59E0B"
                elif tipo_st == "atualizando":
                    cor_p = "#38BDF8"
                    bg_badge = "#0C4A6E"
                    border_badge = "#0284C7"
                    txt_p = p.get("status_str") or "⟳ Sincronizando..."
                    cor_data = "#38BDF8"
                else:
                    if p.get("is_updated", False):
                        cor_p = "#10B981"
                        bg_badge = "#064E3B"
                        border_badge = "#047857"
                        txt_p = p.get("status_str") or "✓ Sincronizado"
                        cor_data = "#64748B"
                    else:
                        cor_p = "#F59E0B"
                        bg_badge = "#451A03"
                        border_badge = "#78350F"
                        txt_p = p.get("status_str") or "⚠ Pendente"
                        cor_data = "#64748B"

                badge_p = ctk.CTkFrame(c_right, fg_color=bg_badge, corner_radius=10, border_width=1, border_color=border_badge)
                badge_p.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
                ctk.CTkLabel(badge_p, text=txt_p, font=("Segoe UI", 9, "bold"), text_color=cor_p).pack(padx=8, pady=1)

                if p.get("atualizado") and p.get("atualizado") != "N/A":
                    ctk.CTkLabel(c_right, text=str(p["atualizado"]), font=("Segoe UI", 10), text_color=cor_data).pack(side=tk.LEFT)
        else:
            self.card_diag_produtos.pack_forget()

    def exibir_loading_diagnostico_visual(self):
        """Atualiza a visão para indicar que uma consulta está em processamento"""
        self.frame_diag_empty.pack_forget()
        self.frame_diag_ativo.pack(fill=tk.BOTH, expand=True)
        self.card_diag_hero.configure(border_color="#0284C7")
        self.frame_pill_diag_status.configure(fg_color="#0C4A6E", border_color="#0284C7")
        self.lbl_pill_diag_status.configure(text="⟳ CONSULTANDO API PLUGGY...", text_color="#38BDF8")
        self.lbl_pill_diag_exec.configure(text="EXECUÇÃO: EM ANDAMENTO", text_color="#38BDF8")
        self.frame_pill_diag_falhas.pack_forget()
        self.lbl_diag_banco_nome.configure(text="Consultando dados do Item...")
        self.lbl_diag_banco_detalhes.configure(text="Aguardando retorno da API Open Finance...")
        self.lbl_parecer_titulo.configure(text="Realizando Diagnóstico...", text_color="#38BDF8")
        self.lbl_parecer_desc.configure(text="Coletando logs de sincronização, detalhes do conector bancário e histórico de erros...")
        self.lbl_parecer_acao.configure(text="Aguarde alguns instantes enquanto os dados são processados.")
        self.box_parecer_tecnico.pack_forget()
        self.lbl_contas_banco_info.configure(text="Consultando contas vinculadas na API...")
        for w in self.frame_lista_contas_diag.winfo_children():
            w.destroy()
        self.card_diag_produtos.pack_forget()

    def exibir_erro_diagnostico_visual(self, erro_msg):
        """Atualiza a visão para apresentar falha na requisição de diagnóstico"""
        self.frame_diag_empty.pack_forget()
        self.frame_diag_ativo.pack(fill=tk.BOTH, expand=True)
        self.card_diag_hero.configure(border_color="#881337")
        self.frame_pill_diag_status.configure(fg_color="#4C0519", border_color="#881337")
        self.lbl_pill_diag_status.configure(text="✗ FALHA NA REQUISIÇÃO", text_color="#F43F5E")
        self.lbl_pill_diag_exec.configure(text="EXECUÇÃO: FALHA", text_color="#F43F5E")
        self.frame_pill_diag_falhas.pack_forget()
        self.lbl_diag_banco_nome.configure(text="Erro ao Consultar Item")
        self.lbl_diag_banco_detalhes.configure(text="A requisição à API retornou um erro.")
        self.lbl_parecer_titulo.configure(text="Falha na Consulta do Item", text_color="#F43F5E")
        self.lbl_parecer_desc.configure(text=f"Não foi possível obter os dados do Item ID informado na Pluggy: {erro_msg}")
        self.lbl_parecer_acao.configure(text="Verifique se o Item ID digitado está correto, se a API Key é válida e se há conexão com a internet.")
        self.lbl_parecer_tecnico_cod.configure(text="Erro de Comunicação / API")
        self.lbl_parecer_tecnico_msg.configure(text=str(erro_msg))
        self.box_parecer_tecnico.pack(fill=tk.X, padx=16, pady=(0, 12))
        self.lbl_contas_banco_info.configure(text="Informações indisponíveis devido a erro na consulta.")
        for w in self.frame_lista_contas_diag.winfo_children():
            w.destroy()
        self.card_diag_produtos.pack_forget()

    def copiar_relatorio_diagnostico(self):
        """Gera um relatório formatado em texto com os dados do diagnóstico e copia para a área de transferência"""
        info = getattr(self, 'item_diag_info', None)
        if not info and getattr(self, 'raw_item_data', None):
            info = analisar_diagnostico_item(self.raw_item_data)
        if not info:
            messagebox.showinfo("Aviso", "Nenhum diagnóstico realizado para copiar.", parent=self)
            return

        linhas = [
            "===========================================================",
            "  RELATÓRIO DE DIAGNÓSTICO OPEN FINANCE (PLUGGY)",
            "===========================================================",
            f"Status do Item: {info['status_label']}",
            f"Execução: {info['exec_status']}",
            f"Instituição: {info['banco_nome']} (Conector #{info['banco_id']})",
            f"Tipo: {info['banco_tipo']}",
            f"Última Sincronização: {info['updated_str']}",
            f"Criado em: {info['created_str']}",
            "",
            "PARECER TÉCNICO:",
            f"• {info['resumo_titulo']}",
            f"• {info['resumo_desc']}",
            "",
            "AÇÃO RECOMENDADA / SOLUÇÃO:",
            f"• {info['recomendacao']}",
        ]

        if info.get("tem_erro") and (info.get("erro_codigo") or info.get("erro_mensagem")):
            linhas.extend([
                "",
                "DETALHES TÉCNICOS DA API:",
                f"• Código: {info.get('erro_codigo') or 'N/A'}",
                f"• Provider Code: {info.get('erro_provider') or 'N/A'}",
                f"• Mensagem: {info.get('erro_mensagem') or 'N/A'}"
            ])

        contas = info.get("contas_vinculadas") or []
        if contas:
            linhas.append("")
            linhas.append(f"CONTAS BANCÁRIAS VINCULADAS ({len(contas)}):")
            for c in contas:
                linhas.append(f"• {c.get('nome')} ({c.get('tipo')}) - Agência: {c.get('agencia')} | Conta: {c.get('numero')} | Titular: {c.get('titular')} | Saldo: {c.get('saldo_str')}")

        inc_list = info.get("incidentes_conector") or []
        if inc_list:
            linhas.append("")
            linhas.append("🚨 ALERTA DE INCIDENTE OFICIAL NA INSTITUIÇÃO (status.pluggy.ai):")
            for inc in inc_list:
                linhas.append(f"• Incidente: {inc.get('title')}")
                linhas.append(f"  Severidade: {inc.get('severity')} | Estado: {inc.get('state')} | Início: {formatar_data_hora_br(inc.get('startedAt'))}")
                linhas.append(f"  Link Oficial: {inc.get('url') or 'https://status.pluggy.ai'}")

        linhas.extend([
            "",
            "METADADOS DA CONEXÃO:",
            f"• Item ID: {info['item_id']}",
            f"• Tentativas de Login Falhas: {info['tentativas_falhas']}",
            "==========================================================="
        ])

        texto = "\n".join(linhas)
        self.copiar_para_clipboard(texto, getattr(self, 'btn_copiar_relatorio_diag', None))

    def acao_abrir_consent_da_diag(self):
        """Leva diretamente para a Aba 3 de Situação do Consentimento usando o Consent ID ou Item ID"""
        info = getattr(self, 'item_diag_info', None)
        consent_id = None
        item_id = self.entry_diag_item_id.get().strip().strip("'\"")
        if info:
            cid = info.get("consent_id")
            if cid and cid != "-":
                consent_id = cid
            else:
                iid = info.get("item_id")
                if iid and iid != "-":
                    consent_id = iid
        id_final = consent_id or item_id
        if not id_final or id_final == "-":
            messagebox.showwarning("Aviso", "Nenhum Consent ID ou Item ID informado.", parent=self)
            return

        self.entry_consent_id.delete(0, tk.END)
        self.entry_consent_id.insert(0, id_final)
        self.tabview.set("Situação do Consentimento")
        self.acao_consultar_situacao_tab3()

    def acao_buscar_t2(self):
        """Dispara busca textual no JSON da aba de diagnóstico"""
        query = self.entry_busca_t2.get().strip()
        self.executar_busca_json_t2(query)

    def executar_busca_json_t2(self, query=None):
        """Localiza ocorrências no JSON da Aba 2 e destaca"""
        if query is None:
            query = self.entry_busca_t2.get().strip()
        self.txt_json_t2.tag_remove("highlight", "1.0", tk.END)
        self.txt_json_t2.tag_remove("current_highlight", "1.0", tk.END)
        self.json_matches_t2.clear()
        self.json_current_match_t2 = -1
        self.lbl_busca_status_t2.configure(text="")

        if not query:
            return

        pos = "1.0"
        while True:
            pos = self.txt_json_t2.search(query, pos, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(query)}c"
            self.txt_json_t2.tag_add("highlight", pos, end_pos)
            self.json_matches_t2.append((pos, end_pos))
            pos = end_pos

        if self.json_matches_t2:
            self.localizar_proximo_json_t2()
        else:
            self.lbl_busca_status_t2.configure(text="Não encontrado")

    def localizar_proximo_json_t2(self):
        """Move o foco para a próxima correspondência no JSON da Aba 2"""
        if not self.json_matches_t2:
            self.executar_busca_json_t2()
            return
        self.json_current_match_t2 = (self.json_current_match_t2 + 1) % len(self.json_matches_t2)
        self.atualizar_foco_json_t2()

    def localizar_anterior_json_t2(self):
        """Move o foco para a correspondência anterior no JSON da Aba 2"""
        if not self.json_matches_t2:
            return
        self.json_current_match_t2 = (self.json_current_match_t2 - 1) % len(self.json_matches_t2)
        self.atualizar_foco_json_t2()

    def atualizar_foco_json_t2(self):
        """Atualiza o realce e rolagem para o resultado ativo de busca na Aba 2"""
        if not self.json_matches_t2 or self.json_current_match_t2 < 0:
            return
        self.txt_json_t2.tag_remove("current_highlight", "1.0", tk.END)
        start, end = self.json_matches_t2[self.json_current_match_t2]
        self.txt_json_t2.tag_add("current_highlight", start, end)
        self.txt_json_t2.see(start)
        self.lbl_busca_status_t2.configure(text=f"{self.json_current_match_t2 + 1} de {len(self.json_matches_t2)}")

    def setup_aba_consentimento(self):
        # 1. Controles Superiores
        card_ctrl = ctk.CTkFrame(self.tab_consentimento, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_ctrl.pack(fill=tk.X, padx=8, pady=(8, 10))

        row1 = ctk.CTkFrame(card_ctrl, fg_color="transparent")
        row1.pack(fill=tk.X, padx=16, pady=12)

        lbl = ctk.CTkLabel(row1, text="Consent ou Item ID:", font=("Segoe UI", 12, "bold"), text_color="#E2E8F0", anchor="w")
        lbl.pack(side=tk.LEFT, padx=(0, 8))

        self.entry_consent_id = ctk.CTkEntry(
            row1,
            placeholder_text="Informe o Consent ID ou Item ID para consultar a situação atual...",
            height=36,
            font=("Consolas", 11),
            border_color="#1F2937"
        )
        self.entry_consent_id.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_consent_id.bind("<Return>", lambda e: self.acao_consultar_situacao_tab3())

        self.btn_consultar_consent_t3 = ctk.CTkButton(
            row1,
            text="Consultar Situação Atual",
            width=190,
            height=36,
            fg_color="#6366F1",
            hover_color="#4F46E5",
            font=("Segoe UI", 12, "bold"),
            command=self.acao_consultar_situacao_tab3
        )
        self.btn_consultar_consent_t3.pack(side=tk.LEFT, padx=(0, 8))

        btn_doc = ctk.CTkButton(
            row1,
            text="Documentação ↗",
            width=120,
            height=36,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt/reference/consent/consent-retrieve")
        )
        btn_doc.pack(side=tk.LEFT)

        # 2. Barra de Alternância de Modo (Visual Amigável vs Código JSON)
        bar_consent_switcher = ctk.CTkFrame(self.tab_consentimento, fg_color="transparent")
        bar_consent_switcher.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.seg_modo_consent = ctk.CTkSegmentedButton(
            bar_consent_switcher,
            values=["Visual Amigável", "Código Puro (JSON)"],
            selected_color="#6366F1",
            selected_hover_color="#4F46E5",
            font=("Segoe UI", 11, "bold"),
            command=self.alternar_modo_consentimento
        )
        self.seg_modo_consent.set("Visual Amigável")
        self.seg_modo_consent.pack(side=tk.LEFT)

        # Toolbar Contextual do Modo Visual
        self.tools_consent_visual = ctk.CTkFrame(bar_consent_switcher, fg_color="transparent")
        self.tools_consent_visual.pack(side=tk.RIGHT)

        self.btn_copiar_resumo_consent = ctk.CTkButton(
            self.tools_consent_visual,
            text="📋 Copiar Resumo",
            width=130,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.copiar_relatorio_consentimento
        )
        self.btn_copiar_resumo_consent.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_ir_diagnostico = ctk.CTkButton(
            self.tools_consent_visual,
            text="🩺 Ver Diagnóstico",
            width=130,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.acao_ir_para_diagnostico_do_consent
        )
        self.btn_ir_diagnostico.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_ir_transacoes = ctk.CTkButton(
            self.tools_consent_visual,
            text="🔍 Ver Transações",
            width=130,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.acao_ir_para_transacoes_do_consent
        )
        self.btn_ir_transacoes.pack(side=tk.RIGHT)

        # Toolbar Contextual do Modo JSON
        self.tools_consent_json = ctk.CTkFrame(bar_consent_switcher, fg_color="transparent")

        self.btn_copiar_json_t3 = ctk.CTkButton(
            self.tools_consent_json,
            text="Copiar JSON",
            width=95,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10),
            command=lambda: self.copiar_para_clipboard(self.txt_json_t3.get("1.0", tk.END).strip(), self.btn_copiar_json_t3)
        )
        self.btn_copiar_json_t3.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_next_j3 = ctk.CTkButton(self.tools_consent_json, text="▼", width=26, height=32, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_proximo_json_t3)
        self.btn_next_j3.pack(side=tk.RIGHT, padx=2)

        self.btn_prev_j3 = ctk.CTkButton(self.tools_consent_json, text="▲", width=26, height=32, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_anterior_json_t3)
        self.btn_prev_j3.pack(side=tk.RIGHT, padx=2)

        self.lbl_busca_status_t3 = ctk.CTkLabel(self.tools_consent_json, text="", font=("Segoe UI", 10), text_color="#94A3B8")
        self.lbl_busca_status_t3.pack(side=tk.RIGHT, padx=4)

        self.entry_busca_t3 = ctk.CTkEntry(
            self.tools_consent_json,
            placeholder_text="Buscar no JSON...",
            width=170,
            height=32,
            font=("Consolas", 10),
            border_color="#1F2937"
        )
        self.entry_busca_t3.pack(side=tk.RIGHT, padx=4)
        self.entry_busca_t3.bind("<Return>", lambda e: self.acao_buscar_t3())
        self.entry_busca_t3.bind("<KeyRelease>", lambda e: self.acao_buscar_t3())

        # 3. Contêiner de Dados Central
        self.container_consent_conteudo = ctk.CTkFrame(self.tab_consentimento, fg_color="transparent")
        self.container_consent_conteudo.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # A) Visão Amigável (Scrollable)
        self.scroll_consent_visual = ctk.CTkScrollableFrame(
            self.container_consent_conteudo,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_consent_visual.pack(fill=tk.BOTH, expand=True)

        # Placeholder / Empty State (inicial)
        self.frame_consent_empty = ctk.CTkFrame(self.scroll_consent_visual, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.frame_consent_empty.pack(fill=tk.BOTH, expand=True, padx=4, pady=12)

        ctk.CTkLabel(
            self.frame_consent_empty,
            text="🔐",
            font=("Segoe UI", 42)
        ).pack(pady=(36, 10))

        ctk.CTkLabel(
            self.frame_consent_empty,
            text="Consulta e Gestão de Consentimento Open Finance",
            font=("Segoe UI", 18, "bold"),
            text_color="#FFFFFF"
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            self.frame_consent_empty,
            text="Monitore a validade regulatória (12 meses), rastreie identificadores de autorização\ne audite produtos e permissões concedidas pelo titular da conta bancária.",
            font=("Segoe UI", 12),
            text_color="#94A3B8",
            justify="center"
        ).pack(pady=(0, 24), padx=20)

        # Passos instrutivos no empty state
        box_inst = ctk.CTkFrame(self.frame_consent_empty, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        box_inst.pack(padx=30, pady=(0, 36), fill=tk.X)

        itens_inst = [
            ("1", "Informe o Consent ID ou Item ID", "Cole o UUID retornado na criação da autorização ou o Item ID associado à instituição financeira."),
            ("2", "Validação de Vigência e Prazos", "O sistema verifica a situação atual (Ativo, Expirado ou Desconectado) e calcula o cronômetro de dias restantes."),
            ("3", "Auditoria Amigável de Dados Autorizados", "Examine com clareza os produtos concedidos (contas, faturas, extratos, investimentos) e permissões técnicas traduzidas.")
        ]
        for num, tit, desc in itens_inst:
            row_i = ctk.CTkFrame(box_inst, fg_color="transparent")
            row_i.pack(fill=tk.X, padx=16, pady=10)
            badge_n = ctk.CTkFrame(row_i, width=28, height=28, fg_color="#6366F1", corner_radius=14)
            badge_n.pack(side=tk.LEFT, padx=(0, 12))
            badge_n.pack_propagate(False)
            ctk.CTkLabel(badge_n, text=num, font=("Segoe UI", 12, "bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")
            f_txt = ctk.CTkFrame(row_i, fg_color="transparent")
            f_txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ctk.CTkLabel(f_txt, text=tit, font=("Segoe UI", 12, "bold"), text_color="#E2E8F0", anchor="w").pack(anchor="w")
            ctk.CTkLabel(f_txt, text=desc, font=("Segoe UI", 11), text_color="#94A3B8", anchor="w").pack(anchor="w")

        # Frame de Consentimento Ativo (inicialmente pack_forget)
        self.frame_consent_ativo = ctk.CTkFrame(self.scroll_consent_visual, fg_color="transparent")

        # --- Card 1: Banner Hero de Status, Instituição & Validade ---
        self.card_consent_hero = ctk.CTkFrame(self.frame_consent_ativo, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        self.card_consent_hero.pack(fill=tk.X, pady=(0, 10))

        # Topo: Pill de Status + Tags
        row_hero_top = ctk.CTkFrame(self.card_consent_hero, fg_color="transparent")
        row_hero_top.pack(fill=tk.X, padx=16, pady=(14, 8))

        self.frame_pill_consent = ctk.CTkFrame(row_hero_top, fg_color="#1E293B", corner_radius=14, border_width=1, border_color="#334155")
        self.frame_pill_consent.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
        self.lbl_pill_consent = ctk.CTkLabel(self.frame_pill_consent, text="● AGUARDANDO CONSULTA", font=("Segoe UI", 11, "bold"), text_color="#F59E0B")
        self.lbl_pill_consent.pack(padx=14, pady=2)

        self.frame_tag_regulatoria = ctk.CTkFrame(row_hero_top, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1F2937")
        self.frame_tag_regulatoria.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
        self.lbl_tag_regulatoria = ctk.CTkLabel(self.frame_tag_regulatoria, text="Open Finance Brasil • Resolução BCB nº 1", font=("Segoe UI", 10, "bold"), text_color="#94A3B8")
        self.lbl_tag_regulatoria.pack(padx=12, pady=2)

        self.lbl_consent_id_badge = ctk.CTkLabel(row_hero_top, text="", font=("Consolas", 10), text_color="#64748B")
        self.lbl_consent_id_badge.pack(side=tk.RIGHT)

        # Linha da Instituição Financeira / Conector
        self.row_banco_consent = ctk.CTkFrame(self.card_consent_hero, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1F2937")
        self.row_banco_consent.pack(fill=tk.X, padx=16, pady=(0, 10))

        col_banco = ctk.CTkFrame(self.row_banco_consent, fg_color="transparent")
        col_banco.pack(side=tk.LEFT, padx=14, pady=10, fill=tk.X, expand=True)

        row_banco_tit = ctk.CTkFrame(col_banco, fg_color="transparent")
        row_banco_tit.pack(fill=tk.X)

        self.bar_banco_consent_cor = ctk.CTkFrame(row_banco_tit, width=5, height=22, fg_color="#6366F1", corner_radius=2)
        self.bar_banco_consent_cor.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_consent_banco_nome = ctk.CTkLabel(row_banco_tit, text="Instituição Financeira", font=("Segoe UI", 15, "bold"), text_color="#FFFFFF")
        self.lbl_consent_banco_nome.pack(side=tk.LEFT)

        self.lbl_consent_banco_detalhes = ctk.CTkLabel(col_banco, text="Conector Open Finance • Conexão Monitorada", font=("Segoe UI", 11), text_color="#94A3B8", anchor="w")
        self.lbl_consent_banco_detalhes.pack(anchor="w", padx=(13, 0), pady=(2, 0))

        # Detalhe do Consentimento
        self.lbl_consent_detalhe = ctk.CTkLabel(
            self.card_consent_hero,
            text="Informe o Consent ID ou Item ID acima e clique em 'Consultar Situação Atual'.",
            font=("Segoe UI", 12),
            text_color="#E2E8F0",
            anchor="w",
            wraplength=850,
            justify="left"
        )
        self.lbl_consent_detalhe.pack(fill=tk.X, padx=16, pady=(0, 12))

        # Painel de Validade e Linha do Tempo
        self.box_validade_timeline = ctk.CTkFrame(self.card_consent_hero, fg_color="#07090E", corner_radius=10, border_width=1, border_color="#1F2937")
        self.box_validade_timeline.pack(fill=tk.X, padx=16, pady=(0, 14))

        row_time_top = ctk.CTkFrame(self.box_validade_timeline, fg_color="transparent")
        row_time_top.pack(fill=tk.X, padx=14, pady=(10, 4))

        self.lbl_metric_prazo = ctk.CTkLabel(
            row_time_top,
            text="⏱️ Vigência e Prazo de Validade",
            font=("Segoe UI", 12, "bold"),
            text_color="#10B981"
        )
        self.lbl_metric_prazo.pack(side=tk.LEFT)

        self.lbl_range_datas = ctk.CTkLabel(
            row_time_top,
            text="",
            font=("Segoe UI", 10),
            text_color="#94A3B8"
        )
        self.lbl_range_datas.pack(side=tk.RIGHT)

        # Barra de Progresso do Consentimento
        self.progresso_validade = ctk.CTkProgressBar(
            self.box_validade_timeline,
            height=8,
            corner_radius=4,
            fg_color="#1E293B",
            progress_color="#10B981"
        )
        self.progresso_validade.pack(fill=tk.X, padx=14, pady=(4, 6))
        self.progresso_validade.set(1.0)

        self.lbl_nota_regulatoria = ctk.CTkLabel(
            self.box_validade_timeline,
            text="Norma BACEN: Os consentimentos Open Finance possuem validade máxima de até 12 meses, renováveis pelo cliente.",
            font=("Segoe UI", 10),
            text_color="#64748B",
            anchor="w"
        )
        self.lbl_nota_regulatoria.pack(anchor="w", padx=14, pady=(0, 8))

        # Retrocompatibilidade
        self.card_consent_status = self.card_consent_hero

        # --- Card 2: Identificadores e Rastreabilidade ---
        card_dados = ctk.CTkFrame(self.frame_consent_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_dados.pack(fill=tk.X, pady=(0, 10))

        head_d = ctk.CTkFrame(card_dados, fg_color="transparent")
        head_d.pack(fill=tk.X, padx=16, pady=(12, 6))
        ctk.CTkLabel(head_d, text="Identificadores e Rastreabilidade do Consentimento", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF").pack(side=tk.LEFT)

        grid_info = ctk.CTkFrame(card_dados, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        grid_info.pack(fill=tk.X, padx=16, pady=(0, 14))
        grid_info.columnconfigure(0, weight=1)
        grid_info.columnconfigure(1, weight=1)

        # Coluna 1: IDs
        c1 = ctk.CTkFrame(grid_info, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="nsew", padx=14, pady=12)

        # Consent ID
        f_cid = ctk.CTkFrame(c1, fg_color="transparent")
        f_cid.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_cid, text="Consent ID:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_cid = ctk.CTkLabel(f_cid, text="-", font=("Consolas", 11), text_color="#38BDF8", anchor="w")
        self.lbl_val_cid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_copiar_cid = ctk.CTkButton(f_cid, text="Copiar", width=55, height=24, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(self.lbl_val_cid.cget("text"), self.btn_copiar_cid))
        self.btn_copiar_cid.pack(side=tk.RIGHT)

        # Item ID
        f_iid = ctk.CTkFrame(c1, fg_color="transparent")
        f_iid.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_iid, text="Item ID:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_itemid = ctk.CTkLabel(f_iid, text="-", font=("Consolas", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_itemid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_copiar_iid = ctk.CTkButton(f_iid, text="Copiar", width=55, height=24, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(self.lbl_val_itemid.cget("text"), self.btn_copiar_iid))
        self.btn_copiar_iid.pack(side=tk.RIGHT)

        # Histórico de Consentimentos (se houver)
        f_hist = ctk.CTkFrame(c1, fg_color="transparent")
        f_hist.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_hist, text="Relação Item:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_historico = ctk.CTkLabel(f_hist, text="Consentimento direto", font=("Segoe UI", 11), text_color="#94A3B8", anchor="w")
        self.lbl_val_historico.pack(side=tk.LEFT)

        # Coluna 2: Datas
        c2 = ctk.CTkFrame(grid_info, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="nsew", padx=14, pady=12)

        f_d1 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d1.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_d1, text="Criado em:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=105, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_created = ctk.CTkLabel(f_d1, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_created.pack(side=tk.LEFT)

        f_d2 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d2.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_d2, text="Expira em:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=105, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_expires = ctk.CTkLabel(f_d2, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_expires.pack(side=tk.LEFT)

        f_d3 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d3.pack(fill=tk.X, pady=3)
        ctk.CTkLabel(f_d3, text="Desconectado em:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=125, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_revoked = ctk.CTkLabel(f_d3, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_revoked.pack(side=tk.LEFT)

        # --- Card 3: Produtos Financeiros Compartilhados ---
        self.card_produtos_section = ctk.CTkFrame(self.frame_consent_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_produtos_section.pack(fill=tk.X, pady=(0, 10))

        head_p = ctk.CTkFrame(self.card_produtos_section, fg_color="transparent")
        head_p.pack(fill=tk.X, padx=16, pady=(12, 4))
        self.lbl_tit_produtos = ctk.CTkLabel(head_p, text="Produtos Financeiros Consentidos (0)", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF")
        self.lbl_tit_produtos.pack(side=tk.LEFT)

        self.lbl_subtit_produtos = ctk.CTkLabel(
            self.card_produtos_section,
            text="Dados e recursos que o cliente autorizou a sincronizar a partir da instituição bancária:",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        self.lbl_subtit_produtos.pack(anchor="w", padx=16, pady=(0, 10))

        self.container_produtos_cards = ctk.CTkFrame(self.card_produtos_section, fg_color="transparent")
        self.container_produtos_cards.pack(fill=tk.X, padx=16, pady=(0, 14))

        # Retrocompatibilidade
        self.frame_chips_products = self.container_produtos_cards

        # --- Card 4: Permissões Regulatórias Open Finance ---
        self.card_permissoes_section = ctk.CTkFrame(self.frame_consent_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_permissoes_section.pack(fill=tk.X, pady=(0, 10))

        head_perm = ctk.CTkFrame(self.card_permissoes_section, fg_color="transparent")
        head_perm.pack(fill=tk.X, padx=16, pady=(12, 4))
        self.lbl_tit_permissoes = ctk.CTkLabel(head_perm, text="Permissões Regulatórias Concedidas (0)", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF")
        self.lbl_tit_permissoes.pack(side=tk.LEFT)

        self.lbl_subtit_permissoes = ctk.CTkLabel(
            self.card_permissoes_section,
            text="Escopos técnicos autorizados pelo titular da conta conforme as diretrizes do Banco Central do Brasil:",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        self.lbl_subtit_permissoes.pack(anchor="w", padx=16, pady=(0, 10))

        self.container_permissoes_agrupadas = ctk.CTkFrame(self.card_permissoes_section, fg_color="transparent")
        self.container_permissoes_agrupadas.pack(fill=tk.X, padx=16, pady=(0, 14))

        # Retrocompatibilidade
        self.frame_chips_permissions = self.container_permissoes_agrupadas

        # --- Card 5: Parecer e Plano de Ação Recomendado ---
        self.card_consent_parecer = ctk.CTkFrame(self.frame_consent_ativo, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        self.card_consent_parecer.pack(fill=tk.X, pady=(0, 10))

        head_rec = ctk.CTkFrame(self.card_consent_parecer, fg_color="transparent")
        head_rec.pack(fill=tk.X, padx=16, pady=(12, 6))
        ctk.CTkLabel(head_rec, text="💡 Parecer e Próximos Passos Recomendados", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF").pack(side=tk.LEFT)

        self.box_rec_conteudo = ctk.CTkFrame(self.card_consent_parecer, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        self.box_rec_conteudo.pack(fill=tk.X, padx=16, pady=(0, 12))

        self.lbl_rec_titulo = ctk.CTkLabel(
            self.box_rec_conteudo,
            text="Situação do Consentimento",
            font=("Segoe UI", 12, "bold"),
            text_color="#10B981",
            anchor="w"
        )
        self.lbl_rec_titulo.pack(fill=tk.X, padx=14, pady=(10, 4))

        self.lbl_rec_texto = ctk.CTkLabel(
            self.box_rec_conteudo,
            text="Aguardando retorno da consulta...",
            font=("Segoe UI", 11),
            text_color="#E2E8F0",
            wraplength=850,
            justify="left",
            anchor="w"
        )
        self.lbl_rec_texto.pack(fill=tk.X, padx=14, pady=(0, 12))

        # Barra de Ações Rápidas no Rodapé
        self.bar_acoes_consent = ctk.CTkFrame(self.card_consent_parecer, fg_color="transparent")
        self.bar_acoes_consent.pack(fill=tk.X, padx=16, pady=(0, 14))

        self.btn_acao_reconectar = ctk.CTkButton(
            self.bar_acoes_consent,
            text="⚡ Reconectar via Pluggy Connect",
            height=34,
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 11, "bold"),
            command=self.acao_reconectar_consentimento
        )

        self.btn_acao_copiar_msg_cliente = ctk.CTkButton(
            self.bar_acoes_consent,
            text="📋 Copiar Mensagem para o Cliente",
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.copiar_orientacao_cliente_consentimento
        )

        self.btn_acao_ver_transacoes = ctk.CTkButton(
            self.bar_acoes_consent,
            text="🔍 Ver Transações deste Item",
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.acao_ir_para_transacoes_do_consent
        )
        self.btn_acao_ver_transacoes.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_acao_ver_diag = ctk.CTkButton(
            self.bar_acoes_consent,
            text="🩺 Diagnóstico Completo do Item",
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=self.acao_ir_para_diagnostico_do_consent
        )
        self.btn_acao_ver_diag.pack(side=tk.LEFT)

        # B) Visão Código Puro / JSON (inicialmente pack_forget)
        self.card_consent_json = ctk.CTkFrame(self.container_consent_conteudo, fg_color="#07090E", corner_radius=10, border_width=1, border_color="#1F2937")

        # Text + Scrollbars
        self.scroll_t3_y = ctk.CTkScrollbar(self.card_consent_json, orientation="vertical", fg_color="#07090E", button_color="#1E293B", button_hover_color="#6366F1", corner_radius=6, width=12)
        self.scroll_t3_x = ctk.CTkScrollbar(self.card_consent_json, orientation="horizontal", fg_color="#07090E", button_color="#1E293B", button_hover_color="#6366F1", corner_radius=6, height=12)

        self.txt_json_t3 = tk.Text(
            self.card_consent_json,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#07090E",
            fg="#D4D4D4",
            insertbackground="#FFFFFF",
            selectbackground="#264F78",
            selectforeground="#FFFFFF",
            bd=0,
            yscrollcommand=self.scroll_t3_y.set,
            xscrollcommand=self.scroll_t3_x.set
        )
        self.scroll_t3_y.configure(command=self.txt_json_t3.yview)
        self.scroll_t3_x.configure(command=self.txt_json_t3.xview)

        self.scroll_t3_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 2), pady=2)
        self.scroll_t3_x.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(2, 2))
        self.txt_json_t3.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.txt_json_t3.tag_configure("key", foreground="#9CDCFE")
        self.txt_json_t3.tag_configure("string", foreground="#CE9178")
        self.txt_json_t3.tag_configure("number", foreground="#B5CEA8")
        self.txt_json_t3.tag_configure("boolean", foreground="#569CD6")
        self.txt_json_t3.tag_configure("highlight", background="#4B5563", foreground="#FFFFFF")
        self.txt_json_t3.tag_configure("current_highlight", background="#F59E0B", foreground="#000000")

    # ==========================================
    # ABA 4: STATUS DOS BANCOS E CONECTORES (status.pluggy.ai)
    # ==========================================
    def setup_aba_status_bancos(self):
        """Monta a aba de monitoramento ao vivo de incidentes e estabilidade da rede Open Finance"""
        # 1. Painel Superior: Banner de Status Geral & Ações Rápidas
        card_ctrl_status = ctk.CTkFrame(self.tab_status_bancos, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_ctrl_status.pack(fill=tk.X, padx=8, pady=(8, 10))

        row_top = ctk.CTkFrame(card_ctrl_status, fg_color="transparent")
        row_top.pack(fill=tk.X, padx=16, pady=12)

        col_info = ctk.CTkFrame(row_top, fg_color="transparent")
        col_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkLabel(
            col_info,
            text="Status dos Bancos & Conectores Open Finance",
            font=("Segoe UI", 16, "bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w")

        self.lbl_status_sub = ctk.CTkLabel(
            col_info,
            text="Monitoramento oficial de incidentes e estabilidade da rede via status.pluggy.ai",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        self.lbl_status_sub.pack(anchor="w", pady=(2, 0))

        col_actions = ctk.CTkFrame(row_top, fg_color="transparent")
        col_actions.pack(side=tk.RIGHT)

        self.frame_pill_global_status = ctk.CTkFrame(col_actions, fg_color="#1E293B", corner_radius=14, border_width=1, border_color="#334155")
        self.frame_pill_global_status.pack(side=tk.LEFT, padx=(0, 10), ipady=2)

        self.lbl_status_global_pill = ctk.CTkLabel(
            self.frame_pill_global_status,
            text="● CONSULTANDO REDE...",
            font=("Segoe UI", 11, "bold"),
            text_color="#38BDF8"
        )
        self.lbl_status_global_pill.pack(padx=14, pady=2)

        self.btn_recarregar_status = ctk.CTkButton(
            col_actions,
            text="🔄 Atualizar Status",
            width=135,
            height=32,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=lambda: threading.Thread(target=self.carregar_status_rede, kwargs={"force_refresh": True}, daemon=True).start()
        )
        self.btn_recarregar_status.pack(side=tk.LEFT, padx=4)

        btn_abrir_status_web = ctk.CTkButton(
            col_actions,
            text="status.pluggy.ai ↗",
            width=130,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=lambda: webbrowser.open("https://status.pluggy.ai")
        )
        btn_abrir_status_web.pack(side=tk.LEFT, padx=4)

        # 2. Barra de Serviços Centrais Pluggy
        self.card_componentes_pluggy = ctk.CTkFrame(card_ctrl_status, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1E293B")
        self.card_componentes_pluggy.pack(fill=tk.X, padx=16, pady=(0, 12))

        lbl_comp_tit = ctk.CTkLabel(
            self.card_componentes_pluggy,
            text="SERVIÇOS DA PLATAFORMA PLUGGY:",
            font=("Segoe UI", 10, "bold"),
            text_color="#64748B"
        )
        lbl_comp_tit.pack(anchor="w", padx=12, pady=(8, 4))

        self.frame_comp_grid = ctk.CTkFrame(self.card_componentes_pluggy, fg_color="transparent")
        self.frame_comp_grid.pack(fill=tk.X, padx=12, pady=(0, 8))

        # 3. Barra de Filtros e Busca
        card_filtros_status = ctk.CTkFrame(self.tab_status_bancos, fg_color="transparent")
        card_filtros_status.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry_busca_status = ctk.CTkEntry(
            card_filtros_status,
            placeholder_text="Filtrar por nome do banco ou conector (ex: Itaú, Bradesco, Inter, Nubank, XP, Sicredi)...",
            height=36,
            font=("Segoe UI", 11),
            border_color="#1F2937"
        )
        self.entry_busca_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_busca_status.bind("<KeyRelease>", self._ao_digitar_busca_status)

        self.seg_filtro_severidade = ctk.CTkSegmentedButton(
            card_filtros_status,
            values=["Todos", "Degradado", "Parcial / Outage", "Manutenções"],
            selected_color="#0284C7",
            selected_hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=self._ao_mudar_filtro_severidade
        )
        self.seg_filtro_severidade.set("Todos")
        self.seg_filtro_severidade.pack(side=tk.RIGHT)

        row_count = ctk.CTkFrame(self.tab_status_bancos, fg_color="transparent")
        row_count.pack(fill=tk.X, padx=12, pady=(0, 6))

        self.lbl_contagem_status = ctk.CTkLabel(
            row_count,
            text="Carregando incidentes dos conectores...",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        self.lbl_contagem_status.pack(side=tk.LEFT)

        self.lbl_status_ultima_hora = ctk.CTkLabel(
            row_count,
            text="",
            font=("Segoe UI", 10),
            text_color="#64748B"
        )
        self.lbl_status_ultima_hora.pack(side=tk.RIGHT)

        # 4. Lista Scrollable de Cards de Incidentes
        self.scroll_status_incidentes = ctk.CTkScrollableFrame(
            self.tab_status_bancos,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_status_incidentes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _ao_digitar_busca_status(self, event=None):
        """Aplica debounce na busca por texto da aba de status"""
        if self._status_debounce_timer:
            self.after_cancel(self._status_debounce_timer)
        self._status_debounce_timer = self.after(250, self.renderizar_lista_incidentes_status)

    def _ao_mudar_filtro_severidade(self, valor):
        self._filtro_status_severidade = valor
        self.renderizar_lista_incidentes_status()

    def carregar_status_rede(self, force_refresh=False, silencioso=False):
        """Worker em segundo plano para consultar status.pluggy.ai"""
        if hasattr(self, 'btn_recarregar_status'):
            self.safe_after(0, lambda: self.btn_recarregar_status.configure(text="Atualizando...", state="disabled"))

        try:
            summary = obter_status_summary(force_refresh=force_refresh)
            con_inc = obter_status_conectores_incidentes(force_refresh=force_refresh)
            full_stat = obter_status_completo_pluggy(force_refresh=force_refresh)

            self.safe_after(0, lambda: self._processar_retorno_status_rede(summary, con_inc, full_stat))
        except Exception as e:
            print("Erro ao carregar status da rede:", e)
            if hasattr(self, 'btn_recarregar_status'):
                self.safe_after(0, lambda: self.btn_recarregar_status.configure(text="🔄 Atualizar Status", state="normal"))

    def _processar_retorno_status_rede(self, summary, con_inc, full_stat):
        """Atualiza a UI da aba de status e o badge do cabeçalho com os dados obtidos"""
        if hasattr(self, 'btn_recarregar_status'):
            self.btn_recarregar_status.configure(text="🔄 Atualizar Status", state="normal")

        self.raw_status_summary = summary
        self.raw_connectors_incidents = con_inc
        self.raw_full_status = full_stat
        self._status_last_loaded_time = datetime.now()

        # 1. Atualizar Badge no Header Geral
        status_code = (summary.get("status") or "op").lower()
        open_cnt = summary.get("openIncidents", 0)
        label_pt = (summary.get("labels") or {}).get("pt", "Operacional")

        if status_code == "op" or open_cnt == 0:
            cor_status = "#10B981"
            bg_status = "#064E3B"
            border_status = "#047857"
            txt_header = "● Rede: 100% Operacional"
            txt_pill = "● TODOS OS SISTEMAS OPERACIONAIS"
        elif status_code in ("pt", "dg"):
            cor_status = "#F59E0B"
            bg_status = "#451A03"
            border_status = "#78350F"
            txt_header = f"● Rede: {open_cnt} instabilidade(s)"
            txt_pill = f"● {label_pt.upper()} ({open_cnt} INCIDENTES)"
        else:
            cor_status = "#F43F5E"
            bg_status = "#4C0519"
            border_status = "#881337"
            txt_header = f"● Rede: Instabilidade Geral ({open_cnt})"
            txt_pill = f"● {label_pt.upper()} ({open_cnt} INCIDENTES)"

        if hasattr(self, 'lbl_rede_status') and self.lbl_rede_status:
            self.lbl_rede_status.configure(text=txt_header, text_color=cor_status)
        if hasattr(self, 'frame_rede_badge') and self.frame_rede_badge:
            self.frame_rede_badge.configure(fg_color=bg_status, border_color=border_status)

        if hasattr(self, 'lbl_status_global_pill'):
            self.lbl_status_global_pill.configure(text=txt_pill, text_color=cor_status)
            self.frame_pill_global_status.configure(fg_color=bg_status, border_color=border_status)

        # 2. Renderizar Componentes Centrais
        comp_list = (full_stat.get("components") or []) if isinstance(full_stat, dict) else []
        self.renderizar_componentes_servicos(comp_list)

        # 3. Renderizar Lista de Incidentes Filtrados
        self.renderizar_lista_incidentes_status()

    def renderizar_componentes_servicos(self, componentes):
        """Renderiza badges horizontais dos serviços da infraestrutura Pluggy"""
        if not hasattr(self, 'frame_comp_grid'):
            return

        for w in self.frame_comp_grid.winfo_children():
            w.destroy()

        if not componentes:
            componentes = [
                {"name": "API", "status": "operational"},
                {"name": "Webhooks", "status": "operational"},
                {"name": "Connect Widget", "status": "operational"},
                {"name": "Iniciação de Pagamentos", "status": "operational"},
                {"name": "PIX Automático", "status": "operational"},
                {"name": "Smart Transfers", "status": "operational"}
            ]

        for comp in componentes:
            nome = comp.get("name") or comp.get("key", "Serviço")
            stat = str(comp.get("status") or "operational").lower()

            is_op = stat == "operational"
            cor_dot = "#10B981" if is_op else ("#F59E0B" if stat == "degraded" else "#F43F5E")
            stat_lbl = "Operacional" if is_op else ("Degradado" if stat == "degraded" else "Instabilidade")

            box = ctk.CTkFrame(self.frame_comp_grid, fg_color="#111827", corner_radius=6, border_width=1, border_color="#1F2937")
            box.pack(side=tk.LEFT, padx=3, pady=2)

            ctk.CTkLabel(
                box,
                text=f"● {nome}: {stat_lbl}",
                font=("Segoe UI", 9, "bold"),
                text_color=cor_dot
            ).pack(padx=8, pady=3)

    def renderizar_lista_incidentes_status(self):
        """Filtra e renderiza os cards de incidentes na área scrollable"""
        if not hasattr(self, 'scroll_status_incidentes'):
            return

        for w in self.scroll_status_incidentes.winfo_children():
            w.destroy()

        query = self.entry_busca_status.get().strip().lower() if hasattr(self, 'entry_busca_status') else ""
        filtro_sev = self.seg_filtro_severidade.get() if hasattr(self, 'seg_filtro_severidade') else "Todos"

        lista_final = []
        ids_vistos = set()

        # 1. Incidentes por conector da rota /api/connectors-incidents
        con_dict = (self.raw_connectors_incidents or {}).get("connectors", {}) if isinstance(self.raw_connectors_incidents, dict) else {}
        for cid, inc_list in con_dict.items():
            for inc in inc_list:
                inc_id = inc.get("id")
                if inc_id and inc_id in ids_vistos:
                    continue
                if inc_id:
                    ids_vistos.add(inc_id)

                item = dict(inc)
                item["connector_id"] = cid
                item["origem"] = "conector"
                lista_final.append(item)

        # 2. Incidentes/manutenções adicionais da rota /api/status
        full_inc_list = (self.raw_full_status or {}).get("incidents", []) if isinstance(self.raw_full_status, dict) else []
        for inc in full_inc_list:
            inc_id = inc.get("id")
            if inc_id and inc_id in ids_vistos:
                continue
            if inc.get("state") == "resolved":
                continue
            if inc_id:
                ids_vistos.add(inc_id)

            item = dict(inc)
            item["connector_id"] = str(inc.get("pluggy_id") or "")
            item["origem"] = "full"
            lista_final.append(item)

        total_encontrados = len(lista_final)

        filtrados = []
        for item in lista_final:
            sev = str(item.get("severity") or "").upper()
            kind = str(item.get("kind") or "").lower()

            if filtro_sev == "Degradado" and "DEGRADED" not in sev:
                continue
            if filtro_sev == "Parcial / Outage" and ("OUTAGE" not in sev and "MAJOR" not in sev):
                continue
            if filtro_sev == "Manutenções" and ("MAINTENANCE" not in sev and kind != "maintenance"):
                continue

            if query:
                titulo = str(item.get("title") or "").lower()
                desc = str(item.get("description") or "").lower()
                cid = str(item.get("connector_id") or "").lower()
                b_name = str(item.get("institution_name") or "").lower()
                if query not in titulo and query not in desc and query not in cid and query not in b_name:
                    continue

            filtrados.append(item)

        if hasattr(self, 'lbl_contagem_status'):
            self.lbl_contagem_status.configure(
                text=f"Exibindo {len(filtrados)} de {total_encontrados} ocorrência(s) ativa(s)"
            )
        if hasattr(self, 'lbl_status_ultima_hora') and self._status_last_loaded_time:
            self.lbl_status_ultima_hora.configure(
                text=f"Última verificação: {self._status_last_loaded_time.strftime('%H:%M:%S')}"
            )

        if not filtrados:
            card_empty = ctk.CTkFrame(self.scroll_status_incidentes, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
            card_empty.pack(fill=tk.BOTH, expand=True, padx=20, pady=30)

            ctk.CTkLabel(card_empty, text="✓", font=("Segoe UI", 38, "bold"), text_color="#10B981").pack(pady=(28, 6))
            ctk.CTkLabel(
                card_empty,
                text="Nenhum Incidente Localizado",
                font=("Segoe UI", 16, "bold"),
                text_color="#FFFFFF"
            ).pack(pady=(0, 4))
            msg_sub = "Todos os conectores bancários estão operando normalmente." if not query and filtro_sev == "Todos" else "Nenhuma ocorrência encontrada para os filtros aplicados."
            ctk.CTkLabel(card_empty, text=msg_sub, font=("Segoe UI", 12), text_color="#94A3B8").pack(pady=(0, 28))
            return

        for inc in filtrados:
            sev = str(inc.get("severity") or "DEGRADED").upper()
            state = str(inc.get("state") or "INVESTIGATING").upper()
            kind = str(inc.get("kind") or "incident").lower()
            cid = inc.get("connector_id") or "-"

            if "MAINTENANCE" in sev or kind == "maintenance":
                cor_sev = "#38BDF8"
                label_sev = "Manutenção Programada"
            elif "OUTAGE" in sev or "MAJOR" in sev:
                cor_sev = "#FB7185"
                label_sev = "Instabilidade Temporária"
            else:
                cor_sev = "#F59E0B"
                label_sev = "Oscilação Temporária"

            estados_map = {
                "INVESTIGATING": "Equipe técnica acompanhando",
                "IDENTIFIED": "Solução em andamento",
                "MONITORING": "Fase final de normalização",
                "SCHEDULED": "Janela programada",
                "UPDATE": "Atualizado recentemente",
                "RESOLVED": "Normalizado"
            }
            state_lbl = estados_map.get(state, state.title())

            card = ctk.CTkFrame(
                self.scroll_status_incidentes,
                fg_color="#111827",
                corner_radius=10,
                border_width=1,
                border_color="#1F2937"
            )
            card.pack(fill=tk.X, pady=4)

            r_top = ctk.CTkFrame(card, fg_color="transparent")
            r_top.pack(fill=tk.X, padx=14, pady=(10, 4))

            inst_nome = inc.get("institution_name")
            if not inst_nome:
                tit_raw = inc.get("title") or ""
                for sep in (" — ", " - ", " | "):
                    if sep in tit_raw:
                        inst_nome = tit_raw.split(sep)[0]
                        break
            if not inst_nome:
                inst_nome = f"Conector #{cid}" if cid != "-" else "Instituição Financeira"

            lbl_banco = ctk.CTkLabel(
                r_top,
                text=f"🏦 {inst_nome}",
                font=("Segoe UI", 13, "bold"),
                text_color="#FFFFFF"
            )
            lbl_banco.pack(side=tk.LEFT)

            if cid != "-":
                chip_cid = ctk.CTkFrame(r_top, fg_color="#1E293B", corner_radius=6, border_width=1, border_color="#334155")
                chip_cid.pack(side=tk.LEFT, padx=(8, 0))
                ctk.CTkLabel(chip_cid, text=f"#{cid}", font=("Consolas", 9, "bold"), text_color="#38BDF8").pack(padx=6, pady=1)

            chip_state = ctk.CTkFrame(r_top, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
            chip_state.pack(side=tk.RIGHT, padx=(6, 0))
            ctk.CTkLabel(chip_state, text=state_lbl, font=("Segoe UI", 9, "bold"), text_color="#CBD5E1").pack(padx=8, pady=2)

            chip_sev = ctk.CTkFrame(r_top, fg_color="#1E293B", corner_radius=10, border_width=1, border_color=cor_sev)
            chip_sev.pack(side=tk.RIGHT, padx=(6, 0))
            ctk.CTkLabel(chip_sev, text=f"● {label_sev}", font=("Segoe UI", 9, "bold"), text_color=cor_sev).pack(padx=8, pady=2)

            tit_inc = inc.get("title") or "Oscilação temporária no conector bancário"
            lbl_tit = ctk.CTkLabel(
                card,
                text=tit_inc,
                font=("Segoe UI", 12, "bold"),
                text_color="#F8FAFC",
                wraplength=920,
                justify="left",
                anchor="w"
            )
            lbl_tit.pack(fill=tk.X, padx=14, pady=(2, 4))

            desc_inc = inc.get("description")
            if desc_inc and len(desc_inc.strip()) > 5:
                lbl_desc = ctk.CTkLabel(
                    card,
                    text=desc_inc.strip(),
                    font=("Segoe UI", 11),
                    text_color="#CBD5E1",
                    wraplength=920,
                    justify="left",
                    anchor="w"
                )
                lbl_desc.pack(fill=tk.X, padx=14, pady=(0, 4))

            r_bot = ctk.CTkFrame(card, fg_color="transparent")
            r_bot.pack(fill=tk.X, padx=14, pady=(4, 10))

            started_at = formatar_data_hora_br(inc.get("startedAt") or inc.get("started_at"))
            sub_info = f"Início: {started_at}  •  💡 Sincronizações deste conector podem levar alguns instantes a mais."

            ctk.CTkLabel(
                r_bot,
                text=sub_info,
                font=("Segoe UI", 10),
                text_color="#94A3B8"
            ).pack(side=tk.LEFT)

            url_inc = inc.get("url") or (f"https://status.pluggy.ai/incident/{inc.get('id')}" if inc.get("id") else "https://status.pluggy.ai")
            btn_web = ctk.CTkButton(
                r_bot,
                text="Acompanhar Status Oficial ↗",
                width=195,
                height=28,
                fg_color="#1E293B",
                hover_color="#334155",
                font=("Segoe UI", 10, "bold"),
                command=lambda u=url_inc: webbrowser.open(u)
            )
            btn_web.pack(side=tk.RIGHT)

    # =========================================================================
    # ABA: DOCUMENTAÇÃO OFICIAL DA PLUGGY, ATUALIZAÇÕES & RECURSOS
    # =========================================================================
    def setup_aba_docs_recursos(self):
        """Monta a aba com link para documentação oficial, acompanhamento de novos conectores e recursos da Pluggy"""
        scroll = ctk.CTkScrollableFrame(self.tab_docs_recursos, fg_color="transparent")
        scroll.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 1. Card Banner Superior: Documentação Oficial
        card_header = ctk.CTkFrame(scroll, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_header.pack(fill=tk.X, pady=(0, 12))

        row_h = ctk.CTkFrame(card_header, fg_color="transparent")
        row_h.pack(fill=tk.X, padx=18, pady=16)

        col_h_info = ctk.CTkFrame(row_h, fg_color="transparent")
        col_h_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkLabel(
            col_h_info,
            text="Documentação Oficial Pluggy (Brasil) & Novos Recursos",
            font=("Segoe UI", 16, "bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_h_info,
            text="Consulte a referência técnica oficial em português para acompanhar o suporte a novos bancos, APIs e atualizações da plataforma Open Finance.",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        ).pack(anchor="w", pady=(3, 0))

        col_h_btn = ctk.CTkFrame(row_h, fg_color="transparent")
        col_h_btn.pack(side=tk.RIGHT, padx=(10, 0))

        btn_open_portal = ctk.CTkButton(
            col_h_btn,
            text="🌐 Acessar docs.pluggy.ai/pt ↗",
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt")
        )
        btn_open_portal.pack(side=tk.RIGHT)

        # 2. Card: Verificador de Novos Conectores na API em Tempo Real
        card_checker = ctk.CTkFrame(scroll, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_checker.pack(fill=tk.X, pady=(0, 12))

        pad_ch = ctk.CTkFrame(card_checker, fg_color="transparent")
        pad_ch.pack(fill=tk.X, padx=18, pady=16)

        ctk.CTkLabel(
            pad_ch,
            text="🔍 Verificar Disponibilidade de Conectores na API em Tempo Real",
            font=("Segoe UI", 13, "bold"),
            text_color="#F8FAFC"
        ).pack(anchor="w")

        ctk.CTkLabel(
            pad_ch,
            text="Consulte se uma instituição (como Cresol, cooperativas ou bancos digitais) já possui conector disponível para agregação na API da Pluggy:",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        ).pack(anchor="w", pady=(2, 10))

        row_search = ctk.CTkFrame(pad_ch, fg_color="transparent")
        row_search.pack(fill=tk.X, pady=(0, 8))

        self.entry_check_connector = ctk.CTkEntry(
            row_search,
            placeholder_text="Digite o nome da instituição (ex: Cresol, Nubank, Sicredi, Inter...)",
            height=36,
            font=("Segoe UI", 11),
            border_color="#1F2937"
        )
        self.entry_check_connector.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.entry_check_connector.insert(0, "Cresol")
        self.entry_check_connector.bind("<Return>", lambda e: self.verificar_conector_api())

        self.btn_checar_conector = ctk.CTkButton(
            row_search,
            text="🔍 Consultar na API",
            height=36,
            width=150,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            command=self.verificar_conector_api
        )
        self.btn_checar_conector.pack(side=tk.LEFT, padx=(0, 8))

        btn_ver_todos = ctk.CTkButton(
            row_search,
            text="📋 Ver Lista Oficial no Portal ↗",
            height=36,
            width=210,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            border_width=1,
            border_color="#334155",
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt/reference/connectors/connectors-list")
        )
        btn_ver_todos.pack(side=tk.LEFT)

        # Container onde é exibido o resultado da consulta
        self.frame_resultado_conector = ctk.CTkFrame(pad_ch, fg_color="transparent")
        self.frame_resultado_conector.pack(fill=tk.X, pady=(4, 0))

        # 3. Card: Seções e Guias da Documentação Oficial
        card_guias = ctk.CTkFrame(scroll, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_guias.pack(fill=tk.X, pady=(0, 12))

        pad_g = ctk.CTkFrame(card_guias, fg_color="transparent")
        pad_g.pack(fill=tk.X, padx=18, pady=16)

        ctk.CTkLabel(
            pad_g,
            text="📚 Guias & Tópicos da Documentação Pluggy",
            font=("Segoe UI", 13, "bold"),
            text_color="#F8FAFC"
        ).pack(anchor="w", pady=(0, 10))

        guias = [
            (
                "Documentação Geral & Primeiros Passos",
                "Visão geral dos recursos, conceitos de Items, Accounts, Transactions e Identity.",
                "https://docs.pluggy.ai/pt",
                "🌐 Acessar Portal Geral"
            ),
            (
                "Conectores Homologados & Parâmetros de Login",
                "Consulte os requisitos específicos de autenticação e credenciais de cada instituição bancária.",
                "https://docs.pluggy.ai/pt/reference/connectors/connectors-list",
                "🏦 Ver Conectores"
            ),
            (
                "Iniciação de Pagamentos (Pix Open Finance)",
                "Documentação para pagamentos instantâneos, transferências Pix e bancos suportados (incluindo Cresol Empresas).",
                "https://docs.pluggy.ai/pt/reference/payments",
                "💳 Ver Pagamentos"
            ),
            (
                "Situação e Renovação de Consentimento",
                "Regras e endpoints para consultar expiração e renovar consentimentos de usuários finais.",
                "https://docs.pluggy.ai/pt/reference/consent/consent-retrieve",
                "🔐 Ver Consentimentos"
            ),
            (
                "Status da Rede & Incidentes em Tempo Real",
                "Página oficial de saúde operacional dos conectores e componentes da Pluggy.",
                "https://status.pluggy.ai",
                "⚡ Ver status.pluggy.ai"
            )
        ]

        for tit, desc, url, btn_txt in guias:
            row_guia = ctk.CTkFrame(pad_g, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            row_guia.pack(fill=tk.X, pady=4)

            inner_g = ctk.CTkFrame(row_guia, fg_color="transparent")
            inner_g.pack(fill=tk.X, padx=14, pady=10)

            col_gtxt = ctk.CTkFrame(inner_g, fg_color="transparent")
            col_gtxt.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ctk.CTkLabel(
                col_gtxt,
                text=tit,
                font=("Segoe UI", 11, "bold"),
                text_color="#38BDF8"
            ).pack(anchor="w")

            ctk.CTkLabel(
                col_gtxt,
                text=desc,
                font=("Segoe UI", 10),
                text_color="#94A3B8"
            ).pack(anchor="w", pady=(1, 0))

            btn_g = ctk.CTkButton(
                inner_g,
                text=f"{btn_txt} ↗",
                width=180,
                height=30,
                fg_color="#1E293B",
                hover_color="#334155",
                font=("Segoe UI", 10, "bold"),
                border_width=1,
                border_color="#334155",
                command=lambda u=url: webbrowser.open(u)
            )
            btn_g.pack(side=tk.RIGHT, padx=(10, 0))

        # 4. Card: Versão do Pluggy Explorer & Atualizações do Software
        card_app_ver = ctk.CTkFrame(scroll, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card_app_ver.pack(fill=tk.X, pady=(0, 6))

        pad_av = ctk.CTkFrame(card_app_ver, fg_color="transparent")
        pad_av.pack(fill=tk.X, padx=18, pady=14)

        row_av = ctk.CTkFrame(pad_av, fg_color="transparent")
        row_av.pack(fill=tk.X)

        col_av_info = ctk.CTkFrame(row_av, fg_color="transparent")
        col_av_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkLabel(
            col_av_info,
            text=f"Pluggy Explorer  v{APP_VERSION}",
            font=("Segoe UI", 12, "bold"),
            text_color="#F8FAFC"
        ).pack(anchor="w")

        self.lbl_docs_update_status = ctk.CTkLabel(
            col_av_info,
            text="Verificação contínua de atualizações no GitHub ativa",
            font=("Segoe UI", 10),
            text_color="#10B981"
        )
        self.lbl_docs_update_status.pack(anchor="w", pady=(2, 0))

        btn_chk_app = ctk.CTkButton(
            row_av,
            text="🔄 Verificar Atualizações do App",
            height=32,
            width=210,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10, "bold"),
            border_width=1,
            border_color="#334155",
            command=self.acao_clique_verificar_atualizacao
        )
        btn_chk_app.pack(side=tk.RIGHT)

    def definir_instituicao_e_prazo(self, nome_ou_id, silencioso=False):
        """
        Atualiza o campo na barra de ferramentas formatado exatamente como:
        (banco)-(quantos ) meses  -> Exemplo: 'Itaú - 12 meses'
        """
        if not hasattr(self, 'entry_banco_meses'):
            return
        info = obter_detalhes_historico_instituicao(nome_ou_id)
        self._instituicao_ativa_info = info
        self.entry_banco_meses.delete(0, tk.END)
        self.entry_banco_meses.insert(0, info["texto_campo"])
        if not silencioso:
            self.exibir_alerta(
                "Instituição Identificada",
                f"{info['nome']}: retorna até {info['meses_rotulo']} de histórico transacional.",
                cor="#0284C7"
            )

    def consultar_instituicao_digitada(self):
        """Ao teclar Enter no campo (banco)-(quantos ) meses, busca a instituição e exibe o modal de detalhes"""
        texto = self.entry_banco_meses.get().strip()
        if " - " in texto:
            termo = texto.split(" - ")[0].strip()
        else:
            termo = texto
        if not termo:
            self.abrir_modal_consulta_instituicao()
            return
        self.definir_instituicao_e_prazo(termo)
        self.abrir_modal_consulta_instituicao(banco_inicial=termo)

    def abrir_detalhes_historico_atual(self):
        """Abre os detalhes da instituição que já está no campo ou abre busca se estiver vazio"""
        texto = self.entry_banco_meses.get().strip()
        if " - " in texto:
            termo = texto.split(" - ")[0].strip()
        else:
            termo = texto
        self.abrir_modal_consulta_instituicao(banco_inicial=termo if termo else None)

    def abrir_modal_consulta_instituicao(self, banco_inicial=None):
        """
        Janela modal avançada para consulta de instituições financeiras, mostrando
        quantos meses cada banco retorna de dados e quantos deveria retornar.
        """
        janela = ctk.CTkToplevel(self)
        janela.title("Consulta de Instituição & Prazos de Retorno de Dados - Pluggy Open Finance")
        janela.geometry("860x720")
        janela.minsize(780, 580)
        janela.transient(self)
        janela.grab_set()

        try:
            rx = self.winfo_rootx() + (self.winfo_width() // 2) - 430
            ry = self.winfo_rooty() + (self.winfo_height() // 2) - 360
            janela.geometry(f"860x720+{max(50, rx)}+{max(50, ry)}")
        except Exception:
            pass

        bar_top = ctk.CTkFrame(janela, height=5, fg_color="#0284C7")
        bar_top.pack(fill=tk.X)

        header = ctk.CTkFrame(janela, fg_color="#0F172A", corner_radius=0)
        header.pack(fill=tk.X, padx=0, pady=0)

        inner_h = ctk.CTkFrame(header, fg_color="transparent")
        inner_h.pack(fill=tk.X, padx=22, pady=16)

        lbl_tit = ctk.CTkLabel(
            inner_h,
            text="🏦 Consulta de Instituições & Prazo de Histórico de Dados",
            font=("Segoe UI", 16, "bold"),
            text_color="#F8FAFC"
        )
        lbl_tit.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            inner_h,
            text="Verifique quantos meses de dados transacionais cada instituição financeira disponibiliza e quantos deveria retornar segundo o Open Finance Brasil (BACEN) e a Pluggy.",
            font=("Segoe UI", 11),
            text_color="#94A3B8",
            wraplength=800,
            justify="left"
        )
        lbl_sub.pack(anchor="w", pady=(3, 0))

        bar_search = ctk.CTkFrame(janela, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
        bar_search.pack(fill=tk.X, padx=20, pady=(14, 10))

        pad_bs = ctk.CTkFrame(bar_search, fg_color="transparent")
        pad_bs.pack(fill=tk.X, padx=14, pady=12)

        row_in = ctk.CTkFrame(pad_bs, fg_color="transparent")
        row_in.pack(fill=tk.X)

        entry_busca = ctk.CTkEntry(
            row_in,
            placeholder_text="Digite o nome do banco ou conector (ex: Itaú, Nubank, Bradesco, Inter, C6, Caixa, Santander, Cresol...)",
            height=38,
            font=("Segoe UI", 12),
            border_color="#334155",
            fg_color="#0B0F19"
        )
        entry_busca.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        btn_limpar = ctk.CTkButton(
            row_in,
            text="Limpar",
            width=75,
            height=38,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            command=lambda: (entry_busca.delete(0, tk.END), renderizar_resultado("Itaú"))
        )
        btn_limpar.pack(side=tk.RIGHT)

        frame_pills = ctk.CTkFrame(pad_bs, fg_color="transparent")
        frame_pills.pack(fill=tk.X, pady=(10, 0))

        ctk.CTkLabel(
            frame_pills,
            text="Bancos Populares:",
            font=("Segoe UI", 10, "bold"),
            text_color="#64748B"
        ).pack(side=tk.LEFT, padx=(0, 6))

        pills_container = ctk.CTkFrame(frame_pills, fg_color="transparent")
        pills_container.pack(side=tk.LEFT, fill=tk.X, expand=True)

        top_pills = [
            "Itaú", "Nubank", "Bradesco", "Banco do Brasil", "Santander",
            "Inter", "Caixa", "C6 Bank", "Mercado Pago", "BTGPactual", "Sicoob", "XP"
        ]

        scroll_res = ctk.CTkScrollableFrame(janela, fg_color="transparent")
        scroll_res.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 14))

        frame_conteudo_resultado = ctk.CTkFrame(scroll_res, fg_color="transparent")
        frame_conteudo_resultado.pack(fill=tk.X)

        def aplicar_no_campo(texto_formatado, nome_banco):
            self.entry_banco_meses.delete(0, tk.END)
            self.entry_banco_meses.insert(0, texto_formatado)
            self._instituicao_ativa_info = obter_detalhes_historico_instituicao(nome_banco)
            self.exibir_alerta("Campo Atualizado", f"Instituição definida: {texto_formatado}", cor="#10B981")
            janela.destroy()

        def renderizar_resultado(termo):
            for w in frame_conteudo_resultado.winfo_children():
                w.destroy()

            info = obter_detalhes_historico_instituicao(termo)

            card_res = ctk.CTkFrame(frame_conteudo_resultado, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
            card_res.pack(fill=tk.X, pady=(0, 12))

            pad_cr = ctk.CTkFrame(card_res, fg_color="transparent")
            pad_cr.pack(fill=tk.X, padx=18, pady=16)

            row_header_card = ctk.CTkFrame(pad_cr, fg_color="transparent")
            row_header_card.pack(fill=tk.X, pady=(0, 10))

            badge_id = f"#{info['id']}" if info['id'] else "Homologado"
            lbl_banco_tit = ctk.CTkLabel(
                row_header_card,
                text=f"🏛️ {info['nome']} ({badge_id})",
                font=("Segoe UI", 15, "bold"),
                text_color="#F8FAFC"
            )
            lbl_banco_tit.pack(side=tk.LEFT)

            badge_of = ctk.CTkLabel(
                row_header_card,
                text="● Open Finance Regulado" if info['is_open_finance'] else "● Conexão Direta",
                font=("Segoe UI", 10, "bold"),
                text_color="#10B981" if info['is_open_finance'] else "#38BDF8",
                fg_color="#064E3B" if info['is_open_finance'] else "#0C4A6E",
                corner_radius=6,
                padx=8,
                pady=2
            )
            badge_of.pack(side=tk.RIGHT)

            banner_meses = ctk.CTkFrame(pad_cr, fg_color="#0B132B", corner_radius=8, border_width=1, border_color="#1E293B")
            banner_meses.pack(fill=tk.X, pady=(0, 14))

            pad_bm = ctk.CTkFrame(banner_meses, fg_color="transparent")
            pad_bm.pack(fill=tk.X, padx=16, pady=12)

            col_b1 = ctk.CTkFrame(pad_bm, fg_color="transparent")
            col_b1.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ctk.CTkLabel(
                col_b1,
                text="QUANTOS MESES RETORNA DE DADOS:",
                font=("Segoe UI", 10, "bold"),
                text_color="#94A3B8"
            ).pack(anchor="w")

            ctk.CTkLabel(
                col_b1,
                text=f"📅 {info['meses_rotulo']} de histórico",
                font=("Segoe UI", 16, "bold"),
                text_color="#38BDF8"
            ).pack(anchor="w", pady=(1, 0))

            col_b2 = ctk.CTkFrame(pad_bm, fg_color="transparent")
            col_b2.pack(side=tk.RIGHT)

            btn_aplicar = ctk.CTkButton(
                col_b2,
                text=f"✓ Aplicar no Campo: {info['texto_campo']}",
                font=("Segoe UI", 11, "bold"),
                height=34,
                fg_color="#0284C7",
                hover_color="#0369A1",
                corner_radius=8,
                command=lambda t=info['texto_campo'], n=info['nome']: aplicar_no_campo(t, n)
            )
            btn_aplicar.pack()

            grid_cards = ctk.CTkFrame(pad_cr, fg_color="transparent")
            grid_cards.pack(fill=tk.X, pady=(0, 12))
            grid_cards.columnconfigure(0, weight=1)
            grid_cards.columnconfigure(1, weight=1)

            c1 = ctk.CTkFrame(grid_cards, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
            p_c1 = ctk.CTkFrame(c1, fg_color="transparent")
            p_c1.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
            ctk.CTkLabel(p_c1, text="⚖️ QUANTOS DEVERIA RETORNAR:", font=("Segoe UI", 10, "bold"), text_color="#F59E0B").pack(anchor="w")
            ctk.CTkLabel(p_c1, text=info['meses_esperados'], font=("Segoe UI", 12, "bold"), text_color="#F8FAFC").pack(anchor="w", pady=(2, 2))
            ctk.CTkLabel(p_c1, text="Obrigatório pela Resolução Conjunta BACEN nº 1 para contas à vista, poupança e cartões de crédito na 1ª conexão.", font=("Segoe UI", 9), text_color="#94A3B8", wraplength=350, justify="left").pack(anchor="w")

            c2 = ctk.CTkFrame(grid_cards, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            c2.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
            p_c2 = ctk.CTkFrame(c2, fg_color="transparent")
            p_c2.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
            ctk.CTkLabel(p_c2, text="🔄 ATUALIZAÇÕES ROTINEIRAS:", font=("Segoe UI", 10, "bold"), text_color="#10B981").pack(anchor="w")
            ctk.CTkLabel(p_c2, text=info['atualizacoes_recentes'], font=("Segoe UI", 12, "bold"), text_color="#F8FAFC").pack(anchor="w", pady=(2, 2))
            ctk.CTkLabel(p_c2, text="Atualizações diárias puxam os últimos 7 dias de transações para refletir novas compras e transferências sem sobrecarregar a rede.", font=("Segoe UI", 9), text_color="#94A3B8", wraplength=350, justify="left").pack(anchor="w")

            c3 = ctk.CTkFrame(grid_cards, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            c3.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
            p_c3 = ctk.CTkFrame(c3, fg_color="transparent")
            p_c3.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
            ctk.CTkLabel(p_c3, text="⏳ LANÇAMENTOS FUTUROS:", font=("Segoe UI", 10, "bold"), text_color="#A855F7").pack(anchor="w")
            ctk.CTkLabel(p_c3, text=info['lancamentos_futuros'], font=("Segoe UI", 11, "bold"), text_color="#F8FAFC", wraplength=350, justify="left").pack(anchor="w", pady=(2, 2))

            c4 = ctk.CTkFrame(grid_cards, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
            c4.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
            p_c4 = ctk.CTkFrame(c4, fg_color="transparent")
            p_c4.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
            ctk.CTkLabel(p_c4, text="🛡️ TIPO DE CONEXÃO:", font=("Segoe UI", 10, "bold"), text_color="#38BDF8").pack(anchor="w")
            ctk.CTkLabel(p_c4, text=info['tipo_conexao'], font=("Segoe UI", 11, "bold"), text_color="#F8FAFC").pack(anchor="w", pady=(2, 2))
            ctk.CTkLabel(p_c4, text="Conexão direta segura com consentimento gerido via OAuth2 do banco.", font=("Segoe UI", 9), text_color="#94A3B8").pack(anchor="w")

            card_motivos = ctk.CTkFrame(pad_cr, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#1E293B")
            card_motivos.pack(fill=tk.X, pady=(12, 0))

            pad_mot = ctk.CTkFrame(card_motivos, fg_color="transparent")
            pad_mot.pack(fill=tk.X, padx=14, pady=12)

            ctk.CTkLabel(
                pad_mot,
                text="💡 Por que uma conta pode retornar menos do que 12 meses na prática?",
                font=("Segoe UI", 11, "bold"),
                text_color="#F8FAFC"
            ).pack(anchor="w", pady=(0, 6))

            for tit_m, desc_m in info["motivos_retorno_menor"]:
                row_m = ctk.CTkFrame(pad_mot, fg_color="transparent")
                row_m.pack(fill=tk.X, pady=2)
                ctk.CTkLabel(row_m, text=f"• {tit_m}:", font=("Segoe UI", 10, "bold"), text_color="#38BDF8").pack(side=tk.LEFT, padx=(0, 6))
                ctk.CTkLabel(row_m, text=desc_m, font=("Segoe UI", 10), text_color="#94A3B8", wraplength=660, justify="left").pack(side=tk.LEFT)

            row_links = ctk.CTkFrame(pad_cr, fg_color="transparent")
            row_links.pack(fill=tk.X, pady=(14, 0))

            ctk.CTkButton(
                row_links,
                text="🌐 FAQ Oficial Pluggy ↗",
                height=30,
                width=170,
                fg_color="#1E293B",
                hover_color="#334155",
                font=("Segoe UI", 10, "bold"),
                border_width=1,
                border_color="#334155",
                command=lambda: webbrowser.open("https://docs.pluggy.ai/en/docs/get-started/faq")
            ).pack(side=tk.LEFT, padx=(0, 8))

            ctk.CTkButton(
                row_links,
                text="📖 Regras de Transações Pluggy ↗",
                height=30,
                width=220,
                fg_color="#1E293B",
                hover_color="#334155",
                font=("Segoe UI", 10, "bold"),
                border_width=1,
                border_color="#334155",
                command=lambda: webbrowser.open("https://docs.pluggy.ai/docs/transactions")
            ).pack(side=tk.LEFT)

        for p_nome in top_pills:
            btn_p = ctk.CTkButton(
                pills_container,
                text=p_nome,
                height=24,
                width=65,
                fg_color="#1E293B",
                hover_color="#334155",
                font=("Segoe UI", 10),
                corner_radius=12,
                command=lambda n=p_nome: (entry_busca.delete(0, tk.END), entry_busca.insert(0, n), renderizar_resultado(n))
            )
            btn_p.pack(side=tk.LEFT, padx=3)

        entry_busca.bind("<KeyRelease>", lambda e: renderizar_resultado(entry_busca.get()))
        entry_busca.bind("<Return>", lambda e: renderizar_resultado(entry_busca.get()))

        banco_start = banco_inicial or "Itaú"
        entry_busca.insert(0, banco_start)
        renderizar_resultado(banco_start)

    def verificar_conector_api(self):
        """Consulta em tempo real na API da Pluggy se o conector digitado já está disponível"""
        termo = self.entry_check_connector.get().strip()
        if not termo:
            messagebox.showwarning("Aviso", "Digite o nome da instituição para consultar.", parent=self)
            return

        self.btn_checar_conector.configure(text="Consultando...", state="disabled")
        for widget in self.frame_resultado_conector.winfo_children():
            widget.destroy()

        lbl_carregando = ctk.CTkLabel(
            self.frame_resultado_conector,
            text=f"◌ Consultando a API Pluggy para '{termo}'...",
            font=("Segoe UI", 11),
            text_color="#38BDF8"
        )
        lbl_carregando.pack(anchor="w", pady=6)

        def worker():
            try:
                if not self.obter_api_key():
                    self.safe_after(0, lambda: self._exibir_resultado_conector(termo, erro="Não foi possível autenticar na API Pluggy. Verifique suas credenciais no botão 'Credenciais'."))
                    return

                url = f"{PLUGGY_BASE_URL}/connectors"
                params = {"name": termo, "pageSize": 50}
                headers = {"accept": "application/json", "X-API-KEY": self.api_key}
                res = requests.get(url, params=params, headers=headers, timeout=15)

                if res.status_code == 401:
                    if self.obter_api_key(force_refresh=True):
                        headers["X-API-KEY"] = self.api_key
                        res = requests.get(url, params=params, headers=headers, timeout=15)

                if res.status_code == 200:
                    data = res.json()
                    resultados = data.get("results", [])
                    self.safe_after(0, lambda: self._exibir_resultado_conector(termo, resultados=resultados))
                else:
                    self.safe_after(0, lambda: self._exibir_resultado_conector(termo, erro=f"Erro na resposta da API (Status {res.status_code}): {res.text}"))
            except Exception as e:
                self.safe_after(0, lambda: self._exibir_resultado_conector(termo, erro=f"Erro de comunicação: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    def _exibir_resultado_conector(self, termo, resultados=None, erro=None):
        """Exibe o resultado da consulta do conector no card dedicado"""
        self.btn_checar_conector.configure(text="🔍 Consultar na API", state="normal")
        for widget in self.frame_resultado_conector.winfo_children():
            widget.destroy()

        if erro:
            card_err = ctk.CTkFrame(self.frame_resultado_conector, fg_color="#4C0519", corner_radius=8, border_width=1, border_color="#F43F5E")
            card_err.pack(fill=tk.X, pady=6)
            ctk.CTkLabel(card_err, text=f"❌ {erro}", font=("Segoe UI", 11), text_color="#FECDD3", wraplength=850, justify="left").pack(padx=14, pady=10, anchor="w")
            return

        if not resultados:
            card_empty = ctk.CTkFrame(self.frame_resultado_conector, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155")
            card_empty.pack(fill=tk.X, pady=6)
            inner_e = ctk.CTkFrame(card_empty, fg_color="transparent")
            inner_e.pack(fill=tk.X, padx=14, pady=12)

            ctk.CTkLabel(
                inner_e,
                text=f"● Instituição '{termo}' não encontrada no catálogo de agregação/leitura de contas da Pluggy no momento.",
                font=("Segoe UI", 11, "bold"),
                text_color="#F59E0B"
            ).pack(anchor="w")

            ctk.CTkLabel(
                inner_e,
                text="Isso indica que a instituição ainda não possui conector homologado para leitura de dados (extratos/saldos).\n"
                     "Nota: Algumas instituições (como a Cresol) podem estar disponíveis apenas para Iniciação de Pagamentos (ITP/Pix).\n"
                     "Você pode acompanhar atualizações de suporte e novos lançamentos na documentação oficial.",
                font=("Segoe UI", 10),
                text_color="#94A3B8",
                justify="left"
            ).pack(anchor="w", pady=(4, 8))

            row_e_btns = ctk.CTkFrame(inner_e, fg_color="transparent")
            row_e_btns.pack(fill=tk.X)

            ctk.CTkButton(
                row_e_btns,
                text="📖 Ver Documentação Oficial da Pluggy (docs.pluggy.ai/pt) ↗",
                height=28,
                fg_color="#0284C7",
                hover_color="#0369A1",
                font=("Segoe UI", 10, "bold"),
                command=lambda: webbrowser.open("https://docs.pluggy.ai/pt")
            ).pack(side=tk.LEFT, padx=(0, 8))

            ctk.CTkButton(
                row_e_btns,
                text="⚡ Checar Status em status.pluggy.ai ↗",
                height=28,
                fg_color="#334155",
                hover_color="#475569",
                font=("Segoe UI", 10),
                command=lambda: webbrowser.open("https://status.pluggy.ai")
            ).pack(side=tk.LEFT)
            return

        # Encontrados resultados
        card_res = ctk.CTkFrame(self.frame_resultado_conector, fg_color="#064E3B", corner_radius=8, border_width=1, border_color="#059669")
        card_res.pack(fill=tk.X, pady=6)
        inner_r = ctk.CTkFrame(card_res, fg_color="transparent")
        inner_r.pack(fill=tk.X, padx=14, pady=10)

        ctk.CTkLabel(
            inner_r,
            text=f"✓ Encontrado(s) {len(resultados)} conector(es) correspondente(s) a '{termo}':",
            font=("Segoe UI", 11, "bold"),
            text_color="#34D399"
        ).pack(anchor="w", pady=(0, 6))

        for con in resultados:
            c_id = con.get("id")
            c_nome = con.get("name")
            c_tipo = con.get("type", "Desconhecido")
            c_oauth = "Sim (OAuth)" if con.get("oauth") else "Credenciais Diretas"
            c_pais = con.get("country", "BR")

            row_c = ctk.CTkFrame(inner_r, fg_color="#0B0F19", corner_radius=6, border_width=1, border_color="#047857")
            row_c.pack(fill=tk.X, pady=3)
            r_c_in = ctk.CTkFrame(row_c, fg_color="transparent")
            r_c_in.pack(fill=tk.X, padx=10, pady=6)

            ctk.CTkLabel(
                r_c_in,
                text=f"ID {c_id}  •  {c_nome}",
                font=("Segoe UI", 11, "bold"),
                text_color="#FFFFFF"
            ).pack(side=tk.LEFT)

            ctk.CTkLabel(
                r_c_in,
                text=f"Tipo: {c_tipo}  |  País: {c_pais}  |  Autenticação: {c_oauth}",
                font=("Segoe UI", 10),
                text_color="#94A3B8"
            ).pack(side=tk.LEFT, padx=(16, 0))

            btn_copiar_id = ctk.CTkButton(
                r_c_in,
                text=f"Copiar ID {c_id}",
                width=110,
                height=26,
                fg_color="#0284C7",
                hover_color="#0369A1",
                font=("Segoe UI", 10, "bold"),
                command=lambda cid=c_id, b=None: None
            )
            btn_copiar_id.configure(command=lambda cid=c_id, b=btn_copiar_id: self.copiar_para_clipboard(str(cid), b))
            btn_copiar_id.pack(side=tk.RIGHT)

    # ==========================================
    # LÓGICA DE ATALHOS E NAVEGAÇÃO DE DATA
    # ==========================================
    def aplicar_mes(self, year, month):
        self.nav_year = year
        self.nav_month = month
        last_day = calendar.monthrange(year, month)[1]
        d_ini = f"01/{month:02d}/{year}"
        d_fim = f"{last_day:02d}/{month:02d}/{year}"
        self.var_data_ini.set(d_ini)
        self.var_data_fim.set(d_fim)

        mes_nome = MESES_NOMES[month - 1]
        abrev = MESES_ABREV[month - 1]
        self.btn_picker_mes.configure(text=f"{abrev}/{year} ▾")
        self.exibir_alerta("Filtro de Mês Aplicado", f"{mes_nome} de {year} ({d_ini} a {d_fim})", cor="#1E293B")

    def acao_mes_anterior(self):
        if self.nav_month == 1:
            self.nav_month = 12
            self.nav_year -= 1
        else:
            self.nav_month -= 1
        self.aplicar_mes(self.nav_year, self.nav_month)

    def acao_proximo_mes(self):
        if self.nav_month == 12:
            self.nav_month = 1
            self.nav_year += 1
        else:
            self.nav_month += 1
        self.aplicar_mes(self.nav_year, self.nav_month)

    def acao_mes_atual(self):
        agora = datetime.now()
        self.aplicar_mes(agora.year, agora.month)

    def acao_todo_historico(self):
        self.var_data_ini.set("")
        self.var_data_fim.set("")
        self.btn_picker_mes.configure(text="Selecionar Mês ▾")
        self.exibir_alerta("Filtro de data limpo", "A consulta trará todas as transações disponíveis da conta.", cor="#1E293B")

    def alternar_modo_visualizacao(self, valor):
        if "Tabela" in valor:
            self.frame_json.pack_forget()
            self.btn_prev_json_t1.pack_forget()
            self.btn_next_json_t1.pack_forget()
            self.lbl_busca_status_t1.pack_forget()
            self.frame_tabela.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t1()
            if not self.current_transactions and hasattr(self, 'frame_empty_tabela'):
                self.frame_empty_tabela.place(relx=0.5, rely=0.55, anchor="center")
        else:
            if hasattr(self, 'frame_empty_tabela'):
                self.frame_empty_tabela.place_forget()
            self.frame_tabela.pack_forget()
            self.btn_prev_json_t1.pack(side=tk.LEFT, padx=2)
            self.btn_next_json_t1.pack(side=tk.LEFT, padx=2)
            self.lbl_busca_status_t1.pack(side=tk.LEFT, padx=6)
            self.frame_json.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t1()

    # ==========================================
    # SINCRONIZAÇÃO ENTRE ABAS E PESQUISA AUTOMÁTICA
    # ==========================================
    def _criar_menu_contexto_entry(self, entry_widget):
        menu = tk.Menu(entry_widget, tearoff=0, bg="#1E293B", fg="#F8FAFC", activebackground="#0284C7", activeforeground="#FFFFFF", bd=0)
        menu.add_command(label="Copiar", command=lambda: entry_widget.event_generate("<<Copy>>"))
        def colar_e_processar():
            entry_widget.event_generate("<<Paste>>")
            self.after(50, self._processar_sincronizacao_item_id)
        menu.add_command(label="Colar e Pesquisar em Todas as Abas", command=colar_e_processar)
        menu.add_command(label="Limpar", command=lambda: entry_widget.delete(0, tk.END))

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        entry_widget.bind("<Button-3>", popup)

    def _ao_colar_item_id(self, event=None):
        """Disparado quando o usuário cola algo no campo de Item ID"""
        self.after(50, self._processar_sincronizacao_item_id)

    def _ao_mudar_item_id_debounce(self, event=None):
        """Detecta digitação ou preenchimento de UUID completo com debounce"""
        if hasattr(self, '_debounce_timer') and self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(350, self._verificar_auto_pesquisa_item_id)

    def _verificar_auto_pesquisa_item_id(self):
        val = self.entry_item_id.get().strip().strip("'\"")
        if len(val) >= 30 and getattr(self, '_last_auto_searched_id', None) != val:
            self._processar_sincronizacao_item_id()

    def _processar_sincronizacao_item_id(self):
        raw_val = self.entry_item_id.get().strip()
        clean_val = re.sub(r'^(?:item_?id\s*[:=]\s*|account_?id\s*[:=]\s*)', '', raw_val, flags=re.IGNORECASE).strip("'\" \t\r\n")
        if clean_val != raw_val:
            self.entry_item_id.delete(0, tk.END)
            self.entry_item_id.insert(0, clean_val)

        if len(clean_val) >= 8:
            self.sincronizar_e_pesquisar_tudo(clean_val)

    def sincronizar_e_pesquisar_tudo(self, item_id):
        """Sincroniza o ID colado para todas as abas e dispara as pesquisas em paralelo"""
        if not item_id:
            return
        if getattr(self, '_last_auto_searched_id', None) == item_id:
            return
        self._last_auto_searched_id = item_id

        # 1. Atualizar e disparar pesquisa na Aba 2 (Diagnóstico de Item)
        if hasattr(self, 'entry_diag_item_id'):
            self.entry_diag_item_id.delete(0, tk.END)
            self.entry_diag_item_id.insert(0, item_id)
            self._last_diag_searched_id = item_id
            try:
                self.acao_diagnosticar_item()
            except Exception as e:
                print("Erro ao disparar diagnóstico automático:", e)

        # 2. Atualizar e disparar pesquisa na Aba 3 (Situação do Consentimento)
        if hasattr(self, 'entry_consent_id'):
            self.entry_consent_id.delete(0, tk.END)
            self.entry_consent_id.insert(0, item_id)
            self._last_consent_searched_id = item_id
            try:
                self.acao_consultar_situacao_tab3()
            except Exception as e:
                print("Erro ao disparar consulta de consentimento automática:", e)

        # 3. Disparar busca de contas na Aba 1 (Explorer de Transações)
        try:
            self.acao_buscar_contas()
        except Exception as e:
            print("Erro ao disparar busca de contas automática:", e)

    def acao_buscar_contas(self):
        item_id = self.entry_item_id.get().strip().strip("'\"")
        if not item_id:
            self.exibir_alerta("Aviso", "Por favor, insira o Item ID ou Conta ID para buscar.", cor="#F59E0B")
            messagebox.showwarning("Aviso", "Por favor, insira o Item ID.", parent=self)
            return

        # Limpa imediatamente a tabela, KPIs e JSON da pesquisa anterior
        self.limpar_tabela_transacoes(
            titulo="Buscando contas do Item...",
            mensagem=f"Consultando contas vinculadas ao Item ID {item_id[:16]}... Aguarde."
        )

        # Sincroniza e garante pesquisa nas outras abas
        if hasattr(self, 'entry_diag_item_id'):
            if self.entry_diag_item_id.get().strip() != item_id:
                self.entry_diag_item_id.delete(0, tk.END)
                self.entry_diag_item_id.insert(0, item_id)
            if getattr(self, '_last_diag_searched_id', None) != item_id:
                self._last_diag_searched_id = item_id
                try:
                    self.acao_diagnosticar_item()
                except Exception:
                    pass

        if hasattr(self, 'entry_consent_id'):
            if self.entry_consent_id.get().strip() != item_id:
                self.entry_consent_id.delete(0, tk.END)
                self.entry_consent_id.insert(0, item_id)
            if getattr(self, '_last_consent_searched_id', None) != item_id:
                self._last_consent_searched_id = item_id
                try:
                    self.acao_consultar_situacao_tab3()
                except Exception:
                    pass

        self.btn_buscar_contas.configure(text="Buscando...", state="disabled")
        self.exibir_alerta("Conectando", f"Buscando contas para o item {item_id[:16]}...", cor="#0284C7")
        threading.Thread(target=self._worker_buscar_contas, args=(item_id,), daemon=True).start()

    def _worker_buscar_contas(self, item_id, retry=True):
        if not self.obter_api_key():
            self.safe_after(0, lambda: self.btn_buscar_contas.configure(text="1. Buscar Contas", state="normal"))
            self.safe_after(0, lambda: self.exibir_alerta("Falha de Autenticação", "Não foi possível validar as credenciais da Pluggy.", cor="#F43F5E"))
            self.safe_after(0, lambda: messagebox.showerror("Erro de Autenticação", "Não foi possível autenticar com a Pluggy. Verifique suas credenciais em Credenciais.", parent=self))
            return

        url = f"{PLUGGY_BASE_URL}/accounts"
        params = {"itemId": item_id}
        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=25)
            if res.status_code == 401 and retry:
                if self.obter_api_key(force_refresh=True):
                    self._worker_buscar_contas(item_id, retry=False)
                return

            if res.status_code != 200:
                try:
                    err_json = res.json()
                    err_msg = err_json.get("message") or err_json.get("error") or str(err_json)
                except Exception:
                    err_msg = res.text
                raise Exception(f"HTTP {res.status_code}: {err_msg}")

            data = res.json()
            results = data.get("results", [])

            # Auto-identifica o banco do Item e preenche o campo (banco)-(quantos ) meses
            try:
                url_it = f"{PLUGGY_BASE_URL}/items/{item_id}"
                res_it = requests.get(url_it, headers=headers, timeout=5)
                if res_it.status_code == 200:
                    it_json = res_it.json()
                    b_nome = (it_json.get("connector") or {}).get("name")
                    if b_nome:
                        self.safe_after(0, lambda n=b_nome: self.definir_instituicao_e_prazo(n, silencioso=True))
            except Exception:
                pass
            contas_temp = {}
            combo_values = []

            for acc in results:
                acc_id = acc.get("id")
                acc_name = acc.get("name") or acc.get("number") or acc.get("type", "Conta")
                saldo = acc.get("balance")
                saldo_str = f" [Saldo: {formatar_moeda_br(saldo)}]" if saldo is not None else ""
                label = f"{acc_name}{saldo_str} - ({acc_id})"
                contas_temp[label] = acc_id
                combo_values.append(label)

            def atualizar_ui():
                self.contas_map = contas_temp
                self.btn_buscar_contas.configure(text="1. Buscar Contas", state="normal")
                self.renderizar_json_texto(self.txt_json_t1, data)
                self.combo_contas.configure(values=combo_values)

                # Preenche também na aba de diagnóstico
                self.entry_diag_item_id.delete(0, tk.END)
                self.entry_diag_item_id.insert(0, item_id)

                if combo_values:
                    self.combo_contas.set(combo_values[0])
                    self.exibir_alerta("Contas Localizadas", f"{len(combo_values)} conta(s) encontrada(s). Clique em '2. Ver Transações'.", cor="#10B981")
                else:
                    self.combo_contas.set("Nenhuma conta encontrada")
                    self.exibir_alerta("Nenhuma Conta", "Este Item ID não possui contas vinculadas ativas.", cor="#F59E0B")
                    messagebox.showinfo("Aviso", "Nenhuma conta vinculada foi encontrada para este Item ID.", parent=self)

            self.safe_after(0, atualizar_ui)

        except Exception as e:
            err_msg = str(e)
            self.safe_after(0, lambda: self.btn_buscar_contas.configure(text="1. Buscar Contas", state="normal"))
            self.safe_after(0, lambda m=err_msg: self.exibir_alerta("Erro ao buscar contas", m, cor="#F43F5E"))
            self.safe_after(0, lambda m=err_msg: messagebox.showerror("Erro ao buscar contas", f"A API da Pluggy retornou um erro:\n\n{m}", parent=self))

    def acao_buscar_transacoes(self):
        selecionado = self.combo_contas.get()
        account_id = self.contas_map.get(selecionado)

        # Se não há conta selecionada pelo dropdown, verifica se o usuário digitou uma conta diretamente
        if not account_id:
            m = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', selecionado)
            if m:
                account_id = m.group(1)

        # Se ainda não encontrou conta mas tem Item ID digitado, auto-localiza a conta!
        if not account_id:
            item_id_raw = self.entry_item_id.get().strip().strip("'\"")
            if item_id_raw:
                self.limpar_tabela_transacoes(
                    titulo="Localizando contas...",
                    mensagem="Buscando contas vinculadas para iniciar a consulta de transações..."
                )
                self.btn_ver_transacoes.configure(text="Localizando...", state="disabled")
                self.exibir_alerta("Auto-localização", "Buscando contas vinculadas ao Item informado...", cor="#0284C7")

                def worker_autochain():
                    if not self.obter_api_key():
                        self.safe_after(0, lambda: self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal"))
                        self.safe_after(0, lambda: self.exibir_alerta("Autenticação Falhou", "Verifique suas credenciais em Credenciais", cor="#F43F5E"))
                        self.safe_after(0, lambda: messagebox.showerror("Autenticação", "Não foi possível validar suas credenciais da Pluggy.", parent=self))
                        return
                    try:
                        url_acc = f"{PLUGGY_BASE_URL}/accounts"
                        headers = {"accept": "application/json", "X-API-KEY": self.api_key}
                        res_acc = requests.get(url_acc, headers=headers, params={"itemId": item_id_raw}, timeout=20)
                        if res_acc.status_code == 200:
                            results = res_acc.json().get("results", [])
                            if results:
                                contas_temp = {}
                                combo_vals = []
                                for acc in results:
                                    a_id = acc.get("id")
                                    a_name = acc.get("name") or acc.get("number") or acc.get("type", "Conta")
                                    saldo = acc.get("balance")
                                    saldo_str = f" [Saldo: {formatar_moeda_br(saldo)}]" if saldo is not None else ""
                                    label = f"{a_name}{saldo_str} - ({a_id})"
                                    contas_temp[label] = a_id
                                    combo_vals.append(label)
                                self.contas_map = contas_temp
                                self.safe_after(0, lambda: self.combo_contas.configure(values=combo_vals))
                                self.safe_after(0, lambda: self.combo_contas.set(combo_vals[0]))
                                first_acc_id = results[0].get("id")
                                d_from = converter_br_para_iso(self.var_data_ini.get())
                                d_to = converter_br_para_iso(self.var_data_fim.get())
                                self._worker_buscar_transacoes(first_acc_id, d_from, d_to)
                                return
                    except Exception as e:
                        err_msg = str(e)
                        self.safe_after(0, lambda: self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal"))
                        self.safe_after(0, lambda m=err_msg: self.exibir_alerta("Falha na busca", m, cor="#F43F5E"))
                        self.safe_after(0, lambda m=err_msg: messagebox.showerror("Erro ao buscar", f"Erro: {m}", parent=self))
                        return
                    self.safe_after(0, lambda: self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal"))
                    self.safe_after(0, lambda: self.exibir_alerta("Aviso", "Nenhuma conta vinculada encontrada.", cor="#F59E0B"))
                    self.safe_after(0, lambda: messagebox.showwarning("Aviso", "Por favor, informe o Item ID e clique em '1. Buscar Contas'.", parent=self))

                threading.Thread(target=worker_autochain, daemon=True).start()
                return

            self.exibir_alerta("Aviso", "Por favor, insira o Item ID e selecione uma conta.", cor="#F59E0B")
            messagebox.showwarning("Aviso", "Por favor, informe o Item ID e clique em '1. Buscar Contas'.", parent=self)
            return

        date_from_iso = converter_br_para_iso(self.var_data_ini.get())
        date_to_iso = converter_br_para_iso(self.var_data_fim.get())

        # Limpa imediatamente os registros, KPIs e JSON da busca anterior
        self.limpar_tabela_transacoes(
            titulo="Consultando transações...",
            mensagem="Baixando lançamentos e calculando saldos para a conta selecionada..."
        )

        self.btn_ver_transacoes.configure(text="Carregando...", state="disabled")
        self.exibir_alerta("Consultando Transações", "Consultando transações na Pluggy API...", cor="#0284C7")
        threading.Thread(target=self._worker_buscar_transacoes, args=(account_id, date_from_iso, date_to_iso), daemon=True).start()

    def _worker_buscar_transacoes(self, account_id, date_from, date_to, retry=True):
        if not self.obter_api_key():
            self.safe_after(0, lambda: self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal"))
            self.safe_after(0, lambda: self.exibir_alerta("Falha de Autenticação", "Não foi possível validar API Key.", cor="#F43F5E"))
            self.safe_after(0, lambda: messagebox.showerror("Autenticação", "Não foi possível validar a chave de API da Pluggy.", parent=self))
            return

        todas_transacoes = []
        next_url = f"{PLUGGY_BASE_URL}/v2/transactions"
        next_params = {"accountId": account_id}
        if date_from:
            next_params["dateFrom"] = date_from
        if date_to:
            next_params["dateTo"] = date_to

        headers = {"accept": "application/json", "X-API-KEY": self.api_key}
        pagina = 1
        seen_next = set()
        ultimo_json = None
        max_paginas = 200  # Limite de segurança (até 100.000 lançamentos)

        try:
            while pagina <= max_paginas:
                if pagina > 1:
                    total_acumulado = len(todas_transacoes)
                    def _atualizar_progresso_ui(n=total_acumulado, p=pagina):
                        self.btn_ver_transacoes.configure(text=f"Buscando ({n})...")
                        self.exibir_alerta("Consultando Transações", f"Página {p} - {n} transações baixadas...", cor="#0284C7")
                    self.safe_after(0, _atualizar_progresso_ui)

                res = requests.get(next_url, headers=headers, params=next_params, timeout=30)
                if res.status_code == 401 and retry:
                    if self.obter_api_key(force_refresh=True):
                        headers["X-API-KEY"] = self.api_key
                        res = requests.get(next_url, headers=headers, params=next_params, timeout=30)
                    else:
                        raise Exception("Sessão expirada e não foi possível renovar a chave de API.")

                if res.status_code != 200:
                    try:
                        err_json = res.json()
                        err_msg = err_json.get("message") or err_json.get("error") or str(err_json)
                    except Exception:
                        err_msg = res.text
                    raise Exception(f"HTTP {res.status_code}: {err_msg}")

                data = res.json()
                if ultimo_json is None:
                    ultimo_json = data

                batch = data.get("results", [])
                if isinstance(batch, list) and batch:
                    todas_transacoes.extend(batch)
                else:
                    break

                # 1. Paginação padrão Pluggy v2 (cursor no campo 'next')
                next_val = data.get("next")
                if next_val and isinstance(next_val, str) and next_val.strip():
                    next_clean = next_val.strip()
                    if next_clean in seen_next:
                        break
                    seen_next.add(next_clean)

                    if next_clean.startswith("http://") or next_clean.startswith("https://"):
                        next_url = next_clean
                        next_params = None
                    elif next_clean.startswith("/"):
                        next_url = f"{PLUGGY_BASE_URL}{next_clean}"
                        next_params = None
                    elif next_clean.startswith("?"):
                        next_url = f"{PLUGGY_BASE_URL}/v2/transactions{next_clean}"
                        next_params = None
                    elif "=" in next_clean:
                        next_url = f"{PLUGGY_BASE_URL}/v2/transactions?{next_clean}"
                        next_params = None
                    else:
                        next_url = f"{PLUGGY_BASE_URL}/v2/transactions"
                        next_params = {"accountId": account_id, "after": next_clean}
                        if date_from:
                            next_params["dateFrom"] = date_from
                        if date_to:
                            next_params["dateTo"] = date_to

                    pagina += 1
                    continue

                # 2. Fallback: Paginação numérica ('page' e 'totalPages')
                page_curr = data.get("page")
                total_pages = data.get("totalPages")
                if isinstance(page_curr, int) and isinstance(total_pages, int) and page_curr < total_pages:
                    pagina = page_curr + 1
                    next_url = f"{PLUGGY_BASE_URL}/v2/transactions"
                    next_params = {"accountId": account_id, "page": pagina}
                    if date_from:
                        next_params["dateFrom"] = date_from
                    if date_to:
                        next_params["dateTo"] = date_to
                    continue

                # Sem mais páginas
                break

            # Atualiza objeto raw com todos os registros acumulados
            if ultimo_json is not None:
                self.raw_transactions_data = dict(ultimo_json)
                self.raw_transactions_data["results"] = todas_transacoes
                self.raw_transactions_data["total"] = len(todas_transacoes)
            else:
                self.raw_transactions_data = {"results": todas_transacoes, "total": len(todas_transacoes)}

            self.current_transactions = todas_transacoes
            self.safe_after(0, self._processar_e_renderizar_transacoes)

        except Exception as e:
            err_msg = str(e)
            self.safe_after(0, lambda: self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal"))
            self.safe_after(0, lambda m=err_msg: self.exibir_alerta("Falha na Requisição", m, cor="#F43F5E"))
            self.safe_after(0, lambda m=err_msg: messagebox.showerror("Erro ao buscar transações", f"A Pluggy retornou um erro:\n\n{m}", parent=self))

    def _processar_e_renderizar_transacoes(self):
        self.btn_ver_transacoes.configure(text="2. Ver Transações", state="normal")
        self.renderizar_json_texto(self.txt_json_t1, self.raw_transactions_data)

        if not self.current_transactions:
            self.exibir_alerta(
                "0 transações encontradas",
                "A API respondeu com sucesso (HTTP 200), mas não há registros neste período. Dica: Clique em 'Todo Histórico' para remover filtros.",
                cor="#D97706"
            )
            self.atualizar_kpis()
            self.popular_linhas_tabela()
            messagebox.showinfo(
                "Nenhuma Transação Encontrada",
                "A consulta foi realizada com sucesso na Pluggy, mas esta conta não possui transações registradas no período informado.",
                parent=self
            )
            return

        self.exibir_alerta("Transações Carregadas", f"{len(self.current_transactions)} transação(ões) carregada(s) com sucesso.", cor="#10B981")

        # Detecta dinamicamente colunas extras
        colunas_detectadas = set()
        for t in self.current_transactions:
            if isinstance(t, dict):
                colunas_detectadas.update(t.keys())

        core_cols = ['date', 'description', 'amount', 'type', 'category', 'status']
        extra_cols = ['currencyCode', 'balance', 'id']
        todas = core_cols + [c for c in extra_cols if c in colunas_detectadas]
        for c in sorted(colunas_detectadas):
            if c not in todas:
                todas.append(c)

        self.all_columns = todas
        self.visible_columns = [c for c in core_cols if c in todas]

        self.atualizar_colunas_treeview()
        self.atualizar_kpis()
        self.popular_linhas_tabela()

    def atualizar_colunas_treeview(self):
        rotulos_amigaveis = {
            'date': 'Data (DD/MM/AAAA)',
            'description': 'Descrição',
            'amount': 'Valor (R$)',
            'type': 'Tipo',
            'category': 'Categoria',
            'status': 'Status',
            'currencyCode': 'Moeda',
            'balance': 'Saldo',
            'id': 'ID da Transação',
            'paymentData': 'Dados de Pagamento',
            'createdAt': 'Criado Em',
            'updatedAt': 'Atualizado Em'
        }

        self.tree["columns"] = self.visible_columns
        for col in self.visible_columns:
            rotulo = rotulos_amigaveis.get(col, col.replace('_', ' ').title())
            self.tree.heading(col, text=rotulo, command=lambda c=col: self.ordenar_tabela(c))

            if col in ('date', 'type', 'status', 'currencyCode'):
                self.tree.column(col, width=120, minwidth=90, anchor='center')
            elif col in ('amount', 'balance'):
                self.tree.column(col, width=130, minwidth=100, anchor='e')
            elif col == 'description':
                self.tree.column(col, width=280, minwidth=150, anchor='w')
            else:
                self.tree.column(col, width=160, minwidth=90, anchor='w')

    def limpar_tabela_transacoes(self, titulo="Consultando novos dados...", mensagem="Aguarde, conectando à API Pluggy..."):
        """Limpa imediatamente a tabela de transações, KPIs e JSON da aba 1 para não reter dados da pesquisa anterior."""
        self.current_transactions = []
        self.raw_transactions_data = {}

        if hasattr(self, 'tree'):
            for item in self.tree.get_children():
                self.tree.delete(item)

        if hasattr(self, 'lbl_kpi_total'):
            self.lbl_kpi_total.configure(text="0")
        if hasattr(self, 'lbl_kpi_entradas'):
            self.lbl_kpi_entradas.configure(text="R$ 0,00")
        if hasattr(self, 'lbl_kpi_saidas'):
            self.lbl_kpi_saidas.configure(text="R$ 0,00")
        if hasattr(self, 'lbl_kpi_saldo'):
            self.lbl_kpi_saldo.configure(text="R$ 0,00")

        if hasattr(self, 'txt_json_t1'):
            self.txt_json_t1.delete("1.0", tk.END)

        if hasattr(self, 'lbl_empty_titulo'):
            self.lbl_empty_titulo.configure(text=titulo)
        if hasattr(self, 'lbl_empty_sub'):
            self.lbl_empty_sub.configure(text=mensagem)
        if hasattr(self, 'frame_empty_tabela'):
            self.frame_empty_tabela.place(relx=0.5, rely=0.55, anchor="center")

    def popular_linhas_tabela(self, lista_filtrada=None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        dados = lista_filtrada if lista_filtrada is not None else self.current_transactions
        if not dados:
            if hasattr(self, 'lbl_empty_titulo'):
                if lista_filtrada is not None:
                    self.lbl_empty_titulo.configure(text="Nenhum registro encontrado para a busca")
                    self.lbl_empty_sub.configure(text="Nenhuma transação corresponde ao filtro digitado.")
                else:
                    self.lbl_empty_titulo.configure(text="Nenhum registro encontrado")
                    self.lbl_empty_sub.configure(text="Nenhum registro encontrado para este período ou filtros aplicados.")
            if hasattr(self, 'frame_empty_tabela'):
                self.frame_empty_tabela.place(relx=0.5, rely=0.55, anchor="center")
        else:
            if hasattr(self, 'frame_empty_tabela'):
                self.frame_empty_tabela.place_forget()

        for i, t in enumerate(dados):
            if not isinstance(t, dict):
                continue
            valores_linha = []
            for col in self.visible_columns:
                val = t.get(col)
                if col == 'date':
                    val_str = formatar_data_br(val)
                elif col in ('createdAt', 'updatedAt'):
                    val_str = formatar_data_hora_br(val)
                elif col in ('amount', 'balance'):
                    val_str = formatar_moeda_br(val)
                elif isinstance(val, (dict, list)):
                    val_str = json.dumps(val, ensure_ascii=False)
                elif val is None:
                    val_str = "-"
                else:
                    val_str = str(val)
                valores_linha.append(val_str)

            tipo = str(t.get('type', '')).upper()
            tag = 'padrao'
            val_raw = t.get('amount', 0)
            try:
                valor_num = float(str(val_raw).replace(',', '.'))
            except Exception:
                valor_num = 0

            if tipo == 'CREDIT' or valor_num > 0:
                tag = 'credito'
            elif tipo == 'DEBIT' or valor_num < 0:
                tag = 'debito'

            tag_par_impar = 'linha_par' if i % 2 == 0 else 'linha_impar'
            self.tree.insert("", tk.END, values=valores_linha, tags=(tag, tag_par_impar))

    def atualizar_kpis(self):
        total = len(self.current_transactions)
        total_cred = 0.0
        total_deb = 0.0

        for t in self.current_transactions:
            if not isinstance(t, dict):
                continue
            val_raw = t.get('amount', 0)
            try:
                val = float(str(val_raw).replace(',', '.'))
            except Exception:
                val = 0.0
            tipo = str(t.get('type', '')).upper()
            if tipo == 'CREDIT' or val > 0:
                total_cred += abs(val)
            else:
                total_deb += abs(val)

        saldo = total_cred - total_deb
        self.lbl_kpi_total.configure(text=f"{total}")
        self.lbl_kpi_entradas.configure(text=formatar_moeda_br(total_cred))
        self.lbl_kpi_saidas.configure(text=formatar_moeda_br(total_deb))
        self.lbl_kpi_saldo.configure(text=formatar_moeda_br(saldo))

    def ordenar_tabela(self, coluna):
        if self.sort_column == coluna:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = coluna
            self.sort_descending = False

        def get_val(item):
            v = item.get(coluna, '')
            if coluna in ('amount', 'balance'):
                try:
                    return float(str(v).replace(',', '.'))
                except Exception:
                    return 0.0
            return str(v).lower()

        self.current_transactions.sort(key=get_val, reverse=self.sort_descending)
        self.popular_linhas_tabela()

    def ao_clicar_duas_vezes_linha(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return
        index = self.tree.index(item_id)
        if index < len(self.current_transactions):
            reg = self.current_transactions[index]
            self.abrir_detalhes_registro(reg)

    def abrir_detalhes_registro(self, reg):
        janela = ctk.CTkToplevel(self)
        janela.title("Detalhes da Transação")
        janela.geometry("660x560")
        janela.transient(self)

        container = ctk.CTkFrame(janela, fg_color="#0B0F19", corner_radius=10, border_width=1, border_color="#1F2937")
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        modal_scroll = ctk.CTkScrollbar(
            container,
            orientation="vertical",
            fg_color="#0B0F19",
            button_color="#1E293B",
            button_hover_color="#0284C7",
            corner_radius=6,
            width=12
        )

        txt = tk.Text(
            container,
            bg="#0B0F19",
            fg="#E2E8F0",
            font=("Consolas", 10),
            padx=12,
            pady=12,
            wrap=tk.WORD,
            bd=0,
            yscrollcommand=modal_scroll.set
        )
        modal_scroll.configure(command=txt.yview)

        modal_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2), pady=2)
        txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        linhas = [
            f"TRANSAÇÃO: {reg.get('description', 'Sem descrição')}",
            "============================================================",
            f"Data: {formatar_data_br(reg.get('date'))}",
            f"Valor: {formatar_moeda_br(reg.get('amount'))}",
            f"Tipo: {reg.get('type', '-')}",
            f"Categoria: {reg.get('category', '-')}",
            f"Status: {reg.get('status', '-')}",
            f"ID: {reg.get('id', '-')}",
            "\nTODAS AS PROPRIEDADES (JSON):",
            json.dumps(reg, indent=2, ensure_ascii=False)
        ]
        txt.insert(tk.END, "\n".join(linhas))
        txt.configure(state='disabled')

    def acao_buscar_t1(self):
        query = self.entry_busca_t1.get().strip().lower()
        modo = self.seg_view_mode.get()

        if "Tabela" in modo:
            if not query:
                self.popular_linhas_tabela()
                return
            filtrados = []
            for t in self.current_transactions:
                match = any(query in str(v).lower() for v in t.values())
                if match:
                    filtrados.append(t)
            self.popular_linhas_tabela(filtrados)
        else:
            self.executar_busca_json_t1(query)

    def executar_busca_json_t1(self, query=None):
        if query is None:
            query = self.entry_busca_t1.get().strip()
        self.txt_json_t1.tag_remove("highlight", "1.0", tk.END)
        self.txt_json_t1.tag_remove("current_highlight", "1.0", tk.END)
        self.json_matches_t1.clear()
        self.json_current_match_t1 = -1
        self.lbl_busca_status_t1.configure(text="")

        if not query:
            return

        pos = "1.0"
        while True:
            pos = self.txt_json_t1.search(query, pos, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end_pos = f"{pos} + {len(query)} chars"
            self.json_matches_t1.append((pos, end_pos))
            self.txt_json_t1.tag_add("highlight", pos, end_pos)
            pos = end_pos

        if self.json_matches_t1:
            self.json_current_match_t1 = 0
            self.atualizar_foco_json_t1()
        else:
            self.lbl_busca_status_t1.configure(text="0 ocorrências")

    def localizar_proximo_json_t1(self):
        if not self.json_matches_t1:
            self.executar_busca_json_t1()
            return
        self.json_current_match_t1 = (self.json_current_match_t1 + 1) % len(self.json_matches_t1)
        self.atualizar_foco_json_t1()

    def localizar_anterior_json_t1(self):
        if not self.json_matches_t1:
            return
        self.json_current_match_t1 = (self.json_current_match_t1 - 1) % len(self.json_matches_t1)
        self.atualizar_foco_json_t1()

    def atualizar_foco_json_t1(self):
        self.txt_json_t1.tag_remove("current_highlight", "1.0", tk.END)
        start, end = self.json_matches_t1[self.json_current_match_t1]
        self.txt_json_t1.tag_add("current_highlight", start, end)
        self.txt_json_t1.see(start)
        self.lbl_busca_status_t1.configure(text=f"{self.json_current_match_t1 + 1} de {len(self.json_matches_t1)}")

    def abrir_gerenciador_colunas(self):
        if not self.all_columns:
            messagebox.showinfo("Aviso", "Carregue as transações primeiro para que as colunas sejam detectadas.", parent=self)
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Gerenciar Colunas")
        janela.geometry("450x520")
        janela.transient(self)

        lbl = ctk.CTkLabel(janela, text="Selecione as colunas para exibir na tabela:", font=("Segoe UI", 12, "bold"))
        lbl.pack(padx=16, pady=(16, 8), anchor="w")

        scroll_frame = ctk.CTkScrollableFrame(janela, width=400, height=360)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        vars_map = {}
        for col in self.all_columns:
            var = tk.BooleanVar(value=(col in self.visible_columns))
            vars_map[col] = var
            cb = ctk.CTkCheckBox(scroll_frame, text=col, variable=var)
            cb.pack(anchor="w", padx=16, pady=4)

        def aplicar():
            novas = [c for c, v in vars_map.items() if v.get()]
            if not novas:
                messagebox.showwarning("Aviso", "Selecione pelo menos uma coluna.", parent=janela)
                return
            self.visible_columns = novas
            self.atualizar_colunas_treeview()
            self.popular_linhas_tabela()
            janela.destroy()

        btn_aplicar = ctk.CTkButton(janela, text="Salvar e Aplicar Colunas", fg_color="#0284C7", hover_color="#0369A1", command=aplicar)
        btn_aplicar.pack(padx=16, pady=(8, 16))

    def exportar_csv_transacoes(self):
        if not self.current_transactions:
            messagebox.showinfo("Aviso", "Nenhum dado para exportar.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Planilha CSV", "*.csv")],
            initialfile=f"transacoes_pluggy_{datetime.now().strftime('%Y%m%d')}.csv",
            parent=self
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write(';'.join(self.visible_columns) + '\n')
                for t in self.current_transactions:
                    linha = []
                    for c in self.visible_columns:
                        v = t.get(c, '')
                        if c == 'date':
                            v = formatar_data_br(v)
                        elif c in ('amount', 'balance'):
                            v = str(v).replace('.', ',')
                        elif isinstance(v, (dict, list)):
                            v = json.dumps(v, ensure_ascii=False)
                        v_str = str(v).replace('"', '""')
                        linha.append(f'"{v_str}"')
                    f.write(';'.join(linha) + '\n')

            messagebox.showinfo("Sucesso", "Arquivo CSV exportado com sucesso!", parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao exportar", f"Falha ao salvar CSV: {e}", parent=self)

    def acao_reconectar_item_diag(self):
        """Dispara o fluxo de reconexão / MFA do item atual via Pluggy Connect Widget"""
        item_id = self.entry_diag_item_id.get().strip().strip("'\"")
        if not item_id and hasattr(self, "raw_item_data") and self.raw_item_data:
            item_id = self.raw_item_data.get("id") or ""
        if not item_id and hasattr(self, "entry_item_id"):
            item_id = self.entry_item_id.get().strip().strip("'\"")
            if item_id:
                self.entry_diag_item_id.delete(0, tk.END)
                self.entry_diag_item_id.insert(0, item_id)

        if not item_id:
            messagebox.showwarning(
                "Item ID Necessário",
                "Por favor, informe ou consulte o Item ID antes de solicitar a reconexão.",
                parent=self
            )
            return
        self.abrir_fluxo_connect_widget(item_id=item_id)

    def acao_diagnosticar_item(self):
        item_id = self.entry_diag_item_id.get().strip().strip("'\"")
        if not item_id:
            messagebox.showwarning("Aviso", "Insira o Item ID para diagnóstico.", parent=self)
            return

        self.lbl_diag_status.configure(text="Status: Consultando API Pluggy...", text_color="#38BDF8")
        self.lbl_diag_erro.configure(text="Aguarde o retorno da conexão...")
        self.card_diag_status.configure(border_color="#0284C7")
        self.btn_consultar_diag.configure(state="disabled")
        self.exibir_loading_diagnostico_visual()
        threading.Thread(target=self._worker_diagnosticar_item, args=(item_id,), daemon=True).start()

    def _worker_diagnosticar_item(self, item_id, retry=True):
        if not self.obter_api_key():
            self.safe_after(0, lambda: self.btn_consultar_diag.configure(state="normal"))
            return

        url = f"{PLUGGY_BASE_URL}/items/{item_id}"
        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 401 and retry:
                if self.obter_api_key(force_refresh=True):
                    self._worker_diagnosticar_item(item_id, retry=False)
                return

            if res.status_code != 200:
                try:
                    err_json = res.json()
                    err_msg = err_json.get("message") or err_json.get("error") or str(err_json)
                except Exception:
                    err_msg = res.text
                raise Exception(f"HTTP {res.status_code}: {err_msg}")

            data = res.json()

            # Busca automaticamente as contas bancárias associadas ao Item na Pluggy
            try:
                url_acc = f"{PLUGGY_BASE_URL}/accounts"
                res_acc = requests.get(url_acc, headers=headers, params={"itemId": item_id}, timeout=15)
                if res_acc.status_code == 200:
                    acc_json = res_acc.json()
                    data["_contas_vinculadas"] = acc_json.get("results", [])
            except Exception:
                pass

            # Checagem ao vivo de incidentes do banco no status.pluggy.ai
            try:
                con_id = (data.get("connector") or {}).get("id")
                con_nome = (data.get("connector") or {}).get("name") or ""
                if con_nome:
                    self.safe_after(0, lambda n=con_nome: self.definir_instituicao_e_prazo(n, silencioso=True))
                if con_id:
                    data["_incidentes_conector"] = buscar_incidentes_para_conector(con_id, con_nome)
            except Exception as e:
                print("Erro ao buscar incidentes do conector para o diagnóstico:", e)

            self.raw_item_data = data

            def atualizar_ui_diag():
                status = data.get("status", "N/A")
                err_obj = data.get("error")
                last_up = formatar_data_hora_br(data.get("updatedAt") or data.get("lastUpdatedAt"))

                if err_obj:
                    code = err_obj.get("code", "ERRO")
                    msg = err_obj.get("message", "Sem detalhes")
                    code_trad = traduzir_codigo_erro_pluggy(code)
                    msg_trad = traduzir_mensagem_erro_pluggy(msg)
                    status_trad = traduzir_codigo_erro_pluggy(status)

                    self.lbl_diag_status.configure(
                        text=f"Falha no Item: {status_trad} [{code}]",
                        text_color="#F43F5E"
                    )
                    self.lbl_diag_erro.configure(
                        text=f"Motivo: {msg_trad} | Última tentativa: {last_up}"
                    )
                    self.card_diag_status.configure(border_color="#4C0519")
                elif status in ("LOGIN_ERROR", "OUTDATED", "REVOKED"):
                    status_trad = traduzir_codigo_erro_pluggy(status)
                    self.lbl_diag_status.configure(
                        text=f"Atenção no Item: {status_trad}",
                        text_color="#F59E0B"
                    )
                    self.lbl_diag_erro.configure(
                        text=f"Requer intervenção ou nova autenticação. Última atualização: {last_up}"
                    )
                    self.card_diag_status.configure(border_color="#78350F")
                else:
                    status_trad = traduzir_codigo_erro_pluggy(status)
                    label_status = f"Status do Item: {status_trad}" if status_trad != status else f"Status do Item: {status}"
                    self.lbl_diag_status.configure(text=label_status, text_color="#10B981")
                    self.lbl_diag_erro.configure(text=f"Nenhum erro reportado. Última atualização: {last_up}")
                    self.card_diag_status.configure(border_color="#064E3B")

                self.renderizar_json_texto(self.txt_json_t2, data)
                self.atualizar_ui_diagnostico_visual(data)
                self.btn_consultar_diag.configure(state="normal")

            self.safe_after(0, atualizar_ui_diag)

        except Exception as e:
            self.safe_after(0, lambda: self.btn_consultar_diag.configure(state="normal"))
            self.safe_after(0, lambda: self.lbl_diag_status.configure(text="Erro na consulta do item", text_color="#F43F5E"))
            self.safe_after(0, lambda: self.lbl_diag_erro.configure(text=str(e)))
            self.safe_after(0, lambda: self.card_diag_status.configure(border_color="#4C0519"))
            self.safe_after(0, lambda: self.exibir_erro_diagnostico_visual(str(e)))

    def renderizar_json_texto(self, txt_widget, data):
        txt_widget.delete("1.0", tk.END)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        txt_widget.insert(tk.END, json_str)

        lines = json_str.splitlines()
        regex_key = re.compile(r'^\s*("([^"\\]|\\.)*")\s*:')
        regex_string = re.compile(r':\s*("([^"\\]|\\.)*")')
        regex_number = re.compile(r':\s*(-?\d+(\.\d+)?([eE][+-]?\d+)?)')
        regex_bool = re.compile(r':\s*(true|false|null)')

        for line_num, line in enumerate(lines[:400]):
            idx = line_num + 1

            m_key = regex_key.search(line)
            if m_key:
                txt_widget.tag_add("key", f"{idx}.{m_key.span(1)[0]}", f"{idx}.{m_key.span(1)[1]}")

            m_str = regex_string.search(line)
            if m_str:
                txt_widget.tag_add("string", f"{idx}.{m_str.span(1)[0]}", f"{idx}.{m_str.span(1)[1]}")

            m_num = regex_number.search(line)
            if m_num:
                txt_widget.tag_add("number", f"{idx}.{m_num.span(1)[0]}", f"{idx}.{m_num.span(1)[1]}")

            m_bool = regex_bool.search(line)
            if m_bool:
                txt_widget.tag_add("boolean", f"{idx}.{m_bool.span(1)[0]}", f"{idx}.{m_bool.span(1)[1]}")

    def copiar_para_clipboard(self, texto, feedback_widget=None):
        try:
            self.clipboard_clear()
            self.clipboard_append(str(texto))
            self.update()
            if feedback_widget:
                txt_original = feedback_widget.cget("text")
                feedback_widget.configure(text="Copiado! ✓")
                self.after(1400, lambda: feedback_widget.configure(text=txt_original))
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível copiar: {e}", parent=self)

    def consultar_consentimento_api(self, id_busca, retry=True):
        """
        Recupera o recurso de consentimento da Pluggy conforme:
        https://docs.pluggy.ai/pt/reference/consent/consent-retrieve
        1. Tenta GET /consents/{id_busca} (pelo Consent ID)
        2. Se retornar 404/400 (por ter recebido um Item ID em vez de Consent ID),
           tenta recuperar a lista por itemId: GET /consents?itemId={id_busca}
        """
        if not self.obter_api_key():
            raise Exception("Não foi possível autenticar na API Pluggy.")

        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        # 1. Tentar diretamente GET /consents/{id}
        url_direct = f"{PLUGGY_BASE_URL}/consents/{id_busca}"
        try:
            res = requests.get(url_direct, headers=headers, timeout=20)
        except Exception as e:
            raise Exception(f"Falha na conexão com a Pluggy: {e}")

        if res.status_code == 401 and retry:
            if self.obter_api_key(force_refresh=True):
                return self.consultar_consentimento_api(id_busca, retry=False)
            raise Exception("Chave de API expirada ou inválida.")

        if res.status_code == 200:
            ret = res.json()
            ret["_searched_id"] = id_busca
            self._enriquecer_consentimento_com_item(ret, headers, id_busca=id_busca)
            return ret

        # 2. Se for 404 ou 400, pode ser um Item ID. Tentar GET /consents?itemId={id_busca}
        url_list = f"{PLUGGY_BASE_URL}/consents"
        try:
            res_list = requests.get(url_list, headers=headers, params={"itemId": id_busca}, timeout=20)
        except Exception as e:
            raise Exception(f"Falha na conexão ao buscar consentimentos do item: {e}")

        if res_list.status_code == 401 and retry:
            if self.obter_api_key(force_refresh=True):
                return self.consultar_consentimento_api(id_busca, retry=False)
            raise Exception("Chave de API expirada ou inválida.")

        if res_list.status_code == 200:
            data_list = res_list.json()
            results = data_list.get("results", [])
            if results:
                # Ordena por createdAt decrescente para retornar o consentimento mais recente
                try:
                    results.sort(key=lambda x: str(x.get("createdAt", "")), reverse=True)
                except Exception:
                    pass
                ret = results[0]
                ret["_all_consents_count"] = len(results)
                ret["_searched_item_id"] = id_busca
                self._enriquecer_consentimento_com_item(ret, headers, id_busca=id_busca)
                return ret
            else:
                raise Exception(f"Nenhum consentimento ativo ou histórico associado ao Item ID '{id_busca}'.")

        # Se falhou em ambos:
        try:
            err_json = res.json()
            err_msg = err_json.get("message") or err_json.get("codeDescription") or str(err_json)
        except Exception:
            err_msg = res.text or f"HTTP {res.status_code}"

        raise Exception(f"Consentimento não localizado para '{id_busca}': {err_msg}")

    def _enriquecer_consentimento_com_item(self, ret, headers, id_busca=None):
        """Tenta obter metadados da instituição/conector a partir do itemId vinculado"""
        if not isinstance(ret, dict):
            return
        item_id = ret.get("itemId") or ret.get("item_id")
        if not item_id and id_busca:
            item_id = id_busca
            ret["itemId"] = id_busca

        if item_id:
            try:
                url_item = f"{PLUGGY_BASE_URL}/items/{item_id}"
                r = requests.get(url_item, headers=headers, timeout=6)
                if r.status_code == 200:
                    item_json = r.json()
                    if not ret.get("itemId") and item_json.get("id"):
                        ret["itemId"] = item_json["id"]
                    if not ret.get("connector") and item_json.get("connector"):
                        ret["connector"] = item_json["connector"]
                    if not ret.get("item_status") and item_json.get("status"):
                        ret["item_status"] = item_json["status"]
                    if not ret.get("products"):
                        if item_json.get("products"):
                            ret["products"] = item_json["products"]
                        elif item_json.get("connector", {}).get("products"):
                            ret["products"] = item_json["connector"]["products"]
            except Exception:
                pass

        con = ret.get("connector")
        if isinstance(con, dict):
            if not ret.get("products") and con.get("products"):
                ret["products"] = con.get("products")
        elif ret.get("connectorId"):
            try:
                url_con = f"{PLUGGY_BASE_URL}/connectors/{ret['connectorId']}"
                rc = requests.get(url_con, headers=headers, timeout=5)
                if rc.status_code == 200:
                    cjson = rc.json()
                    ret["connector"] = cjson
                    if not ret.get("products") and cjson.get("products"):
                        ret["products"] = cjson.get("products")
            except Exception:
                pass

    def acao_ver_situacao_consent_tab1(self):
        id_item = self.entry_item_id.get().strip().strip("'\"")
        if not id_item:
            messagebox.showwarning(
                "Aviso",
                "Por favor, insira o Item ID no campo acima para verificar a situação atual do consentimento.",
                parent=self
            )
            return

        if hasattr(self, 'btn_situacao_consent_t1'):
            self.btn_situacao_consent_t1.configure(text="Consultando...", state="disabled")

        def worker():
            try:
                data = self.consultar_consentimento_api(id_item)
                self.raw_consent_data = data
                info = analisar_situacao_consentimento(data)
                if info:
                    c_name = info.get("connector_name") or (data.get("connector") or {}).get("name") or data.get("institutionName")
                    if c_name:
                        self.definir_instituicao_e_prazo(c_name, silencioso=True)

                def atualizar():
                    if hasattr(self, 'btn_situacao_consent_t1'):
                        self.btn_situacao_consent_t1.configure(text="Situação Atual", state="normal")
                    self.lbl_status_msg.configure(
                        text=f"Situação do Consentimento: {info['status_titulo']} | Expira: {info['expires_str']}",
                        text_color=info['cor_status']
                    )
                    # Preenche também na Aba 3
                    self.entry_consent_id.delete(0, tk.END)
                    self.entry_consent_id.insert(0, data.get("id") or id_item)
                    self._atualizar_ui_consentimento_tab3(data)
                    # Abre janela modal destacada com todas as informações
                    self.abrir_janela_situacao_consentimento(data)

                self.safe_after(0, atualizar)
            except Exception as e:
                def on_err():
                    if hasattr(self, 'btn_situacao_consent_t1'):
                        self.btn_situacao_consent_t1.configure(text="Situação Atual", state="normal")
                    messagebox.showerror("Erro ao Consultar Situação", str(e), parent=self)
                self.safe_after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def acao_ver_situacao_consent_tab2(self):
        id_busca = self.entry_diag_item_id.get().strip().strip("'\"")
        if not id_busca:
            id_busca = self.entry_item_id.get().strip().strip("'\"")
        if id_busca:
            self.entry_consent_id.delete(0, tk.END)
            self.entry_consent_id.insert(0, id_busca)
        self.tabview.set("Situação do Consentimento")
        if id_busca:
            self.acao_consultar_situacao_tab3()

    def alternar_modo_consentimento(self, modo=None):
        """Alterna a exibição entre a Visão Amigável e o Código Puro (JSON) da Situação do Consentimento"""
        if modo is None:
            modo = self.seg_modo_consent.get()
        if "Visual" in modo:
            self.card_consent_json.pack_forget()
            self.tools_consent_json.pack_forget()
            self.tools_consent_visual.pack(side=tk.RIGHT)
            self.scroll_consent_visual.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t3()
        else:
            self.scroll_consent_visual.pack_forget()
            self.tools_consent_visual.pack_forget()
            self.tools_consent_json.pack(side=tk.RIGHT)
            self.card_consent_json.pack(fill=tk.BOTH, expand=True)
            self.acao_buscar_t3()

    def copiar_relatorio_consentimento(self):
        """Copia relatório amigável da situação do consentimento para a área de transferência"""
        info = getattr(self, "consent_info", None)
        if not info:
            messagebox.showinfo("Aviso", "Consulte um consentimento antes de copiar o resumo.", parent=self)
            return

        banco = info.get("banco_nome") or "Instituição Financeira"
        con_id = info.get("banco_id") or "-"
        prods = [f"• {p['nome']} ({p['desc']})" for p in info.get("products_enriched", [])]
        prods_txt = "\n".join(prods) if prods else "• Nenhum produto listado"

        perms = [f"• {p['key']}: {p['nome']} - {p['desc']}" for p in info.get("permissions_enriched", [])]
        perms_txt = "\n".join(perms) if perms else "• Nenhuma permissão listada"

        relatorio = (
            f"==========================================================\n"
            f"SITUAÇÃO DO CONSENTIMENTO OPEN FINANCE - PLUGGY EXPLORER\n"
            f"==========================================================\n"
            f"Instituição: {banco} (Conector #{con_id})\n"
            f"Status: {info['status_titulo']}\n"
            f"Validade / Prazos: {info['msg_prazo']}\n"
            f"Consent ID: {info['id']}\n"
            f"Item ID: {info['item_id']}\n"
            f"Data de Criação: {info['created_str']}\n"
            f"Data de Expiração: {info['expires_str']}\n"
            f"Data de Desconexão: {info['revoked_str']}\n\n"
            f"PRODUTOS CONSENTIDOS ({len(info.get('products_enriched', []))}):\n"
            f"{prods_txt}\n\n"
            f"PERMISSÕES REGULATÓRIAS ({len(info.get('permissions_enriched', []))}):\n"
            f"{perms_txt}\n\n"
            f"PARECER E AÇÃO:\n"
            f"{info['recomendacao_titulo']}\n"
            f"{info['recomendacao_texto']}\n"
            f"=========================================================="
        )
        self.copiar_para_clipboard(relatorio, self.btn_copiar_resumo_consent)

    def copiar_orientacao_cliente_consentimento(self):
        """Gera e copia mensagem pronta para orientar o cliente sobre renovação ou reconexão"""
        info = getattr(self, "consent_info", None)
        banco = (info.get("banco_nome") if info else None) or "sua instituição bancária"
        item_id = (info.get("item_id") if info else None) or ""
        msg = (
            f"Olá!\n\n"
            f"Identificamos que a autorização de compartilhamento via Open Finance da sua conta no {banco} "
            f"precisa de renovação para que suas movimentações continuem sendo atualizadas automaticamente.\n\n"
            f"Conforme determinação do Banco Central, os consentimentos têm prazo de validade e necessitam "
            f"de renovação periódica pelo titular.\n\n"
            f"Por favor, acesse nosso aplicativo para autorizar a renovação em poucos segundos de forma 100% segura.\n\n"
            f"(Identificador da conexão: {item_id})"
        )
        self.copiar_para_clipboard(msg, self.btn_acao_copiar_msg_cliente)

    def acao_ir_para_transacoes_do_consent(self):
        """Navega para a aba de transações carregando o item ID deste consentimento"""
        item_id = self.lbl_val_itemid.cget("text").strip()
        if not item_id or item_id in ("-", "N/A"):
            item_id = self.entry_consent_id.get().strip().strip("'\"")
        if not item_id or item_id in ("-", "N/A"):
            messagebox.showwarning("Aviso", "Item ID não disponível.", parent=self)
            return
        self.entry_item_id.delete(0, tk.END)
        self.entry_item_id.insert(0, item_id)
        self.tabview.set("Explorer de Transações")
        self.acao_buscar_contas()

    def acao_ir_para_diagnostico_do_consent(self):
        """Navega para a aba de diagnóstico carregando o item ID deste consentimento"""
        item_id = self.lbl_val_itemid.cget("text").strip()
        if not item_id or item_id in ("-", "N/A"):
            item_id = self.entry_consent_id.get().strip().strip("'\"")
        if not item_id or item_id in ("-", "N/A"):
            messagebox.showwarning("Aviso", "Item ID não disponível.", parent=self)
            return
        self.entry_diag_item_id.delete(0, tk.END)
        self.entry_diag_item_id.insert(0, item_id)
        self.tabview.set("Diagnóstico de Item (Erros)")
        self.acao_diagnosticar_item()

    def acao_reconectar_consentimento(self):
        """Abre o fluxo de reconexão do item via Pluggy Connect Widget"""
        item_id = self.lbl_val_itemid.cget("text").strip()
        if not item_id or item_id in ("-", "N/A"):
            item_id = self.entry_consent_id.get().strip().strip("'\"")
        if not item_id or item_id in ("-", "N/A"):
            messagebox.showwarning("Aviso", "Nenhum Item ID disponível para reconectar.", parent=self)
            return
        self.abrir_fluxo_connect_widget(item_id=item_id)

    def acao_consultar_situacao_tab3(self):
        id_busca = self.entry_consent_id.get().strip().strip("'\"")
        if not id_busca:
            id_busca = self.entry_item_id.get().strip().strip("'\"") or self.entry_diag_item_id.get().strip().strip("'\"")
            if id_busca:
                self.entry_consent_id.delete(0, tk.END)
                self.entry_consent_id.insert(0, id_busca)

        if not id_busca:
            messagebox.showwarning(
                "Aviso",
                "Informe o Consent ID ou Item ID para consultar a situação atual.",
                parent=self
            )
            return

        self.btn_consultar_consent_t3.configure(text="Consultando...", state="disabled")
        self.lbl_pill_consent.configure(text="● CONSULTANDO API...", text_color="#38BDF8")
        if hasattr(self, 'frame_pill_consent'):
            self.frame_pill_consent.configure(fg_color="#0C4A6E", border_color="#0284C7")
        self.lbl_consent_detalhe.configure(
            text="Aguarde o retorno da consulta do recurso de consentimento...",
            text_color="#94A3B8"
        )
        if hasattr(self, 'card_consent_hero'):
            self.card_consent_hero.configure(border_color="#0284C7")

        threading.Thread(target=self._worker_consultar_consentimento_tab3, args=(id_busca,), daemon=True).start()

    def _worker_consultar_consentimento_tab3(self, id_busca):
        try:
            data = self.consultar_consentimento_api(id_busca)
            self.raw_consent_data = data

            def atualizar():
                self.btn_consultar_consent_t3.configure(text="Consultar Situação Atual", state="normal")
                self._atualizar_ui_consentimento_tab3(data)

            self.safe_after(0, atualizar)
        except Exception as e:
            def on_err():
                self.btn_consultar_consent_t3.configure(text="Consultar Situação Atual", state="normal")
                self.lbl_pill_consent.configure(text="● ERRO", text_color="#F43F5E")
                if hasattr(self, 'frame_pill_consent'):
                    self.frame_pill_consent.configure(fg_color="#4C0519", border_color="#881337")
                self.lbl_consent_detalhe.configure(text=str(e), text_color="#F43F5E")
                if hasattr(self, 'card_consent_hero'):
                    self.card_consent_hero.configure(border_color="#881337")
                messagebox.showerror("Erro ao Consultar Situação", str(e), parent=self)
            self.safe_after(0, on_err)

    def _atualizar_ui_consentimento_tab3(self, data):
        info = analisar_situacao_consentimento(data)
        if not info:
            return

        c_name = info.get("connector_name") or (data.get("connector") or {}).get("name") or data.get("institutionName")
        if c_name:
            self.definir_instituicao_e_prazo(c_name, silencioso=True)

        self.consent_info = info

        # 1. Esconder empty state e exibir frame ativo
        self.frame_consent_empty.pack_forget()
        self.frame_consent_ativo.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 2. Status Pill e Header
        self.lbl_pill_consent.configure(text=f"● {info['status_titulo']}", text_color=info["cor_status"])
        self.frame_pill_consent.configure(fg_color=info["cor_bg"], border_color=info["cor_border"])
        self.lbl_consent_detalhe.configure(text=info["detalhe"], text_color="#E2E8F0")
        self.card_consent_hero.configure(border_color=info["cor_border"])

        # Tag de ID
        cid_str = info["id"]
        if cid_str and cid_str != "N/A":
            self.lbl_consent_id_badge.configure(text=f"Consent: {cid_str[:12]}...")
        else:
            self.lbl_consent_id_badge.configure(text="")

        # Instituição Financeira / Conector
        if info.get("banco_nome"):
            self.lbl_consent_banco_nome.configure(text=info["banco_nome"])
            banco_cor = normalizar_cor_hex(info.get("banco_cor"), fallback="#6366F1")
            try:
                self.bar_banco_consent_cor.configure(fg_color=banco_cor)
            except Exception:
                self.bar_banco_consent_cor.configure(fg_color="#6366F1")
            con_id_txt = f"Conector # {info['banco_id']}" if info.get('banco_id') and str(info['banco_id']) not in ("None", "-") else "Conector Open Finance"
            banco_tipo_txt = info.get('banco_tipo') or "Instituição Financeira"
            self.lbl_consent_banco_detalhes.configure(text=f"{con_id_txt} • {banco_tipo_txt} • Conexão Monitorada")
            self.row_banco_consent.pack(fill=tk.X, padx=16, pady=(0, 10))
        else:
            self.lbl_consent_banco_nome.configure(text="Instituição Financeira Open Finance")
            self.lbl_consent_banco_detalhes.configure(text="Conexão Bancária Pluggy • GET /consents/{id}")
            self.bar_banco_consent_cor.configure(fg_color="#6366F1")

        # Timeline e Linha do Tempo
        cor_prazo = normalizar_cor_hex(info.get("cor_status"), fallback="#10B981")
        msg_prazo = info.get("msg_prazo") or "Vigência Contínua / Sem Data Limite"
        self.lbl_metric_prazo.configure(
            text=f"⏱️ {msg_prazo}",
            text_color=cor_prazo
        )

        st_key = info.get("status_key")
        if st_key == "REVOKED":
            self.lbl_range_datas.configure(
                text=f"Autorizado em: {info.get('created_str', '-')}   ➔   Desconectado em: {info.get('revoked_str', '-')} (Encerrado)"
            )
            pct = 1.0
        elif st_key == "EXPIRED":
            self.lbl_range_datas.configure(
                text=f"Autorizado em: {info.get('created_str', '-')}   ➔   Expirou em: {info.get('expires_str', '-')} (Prazo Esgotado)"
            )
            pct = 1.0
        elif st_key == "WAITING_AUTHORISATION":
            self.lbl_range_datas.configure(
                text=f"Criado em: {info.get('created_str', '-')}   ➔   Aguardando autorização no app do banco"
            )
            pct = 0.0
        elif not info.get("expires_str") or info.get("expires_str") in ("Sem expiração", "None", "-"):
            self.lbl_range_datas.configure(
                text=f"Autorizado em: {info.get('created_str') or '-'}   ➔   Vigência: Contínua / Indeterminada"
            )
            pct = 1.0
        else:
            self.lbl_range_datas.configure(
                text=f"Autorizado em: {info['created_str']}   ➔   Expira em: {info['expires_str']}"
            )
            pct = info.get("pct_validade", 1.0)

        try:
            self.progresso_validade.configure(progress_color=cor_prazo)
            self.progresso_validade.set(pct)
        except Exception:
            pass

        # 3. Identificadores e Datas
        cid_val = info.get("id") or data.get("id") or data.get("consentId") or ""
        item_val = info.get("item_id") or data.get("itemId") or data.get("item_id") or ""
        entry_txt = self.entry_consent_id.get().strip().strip("'\"") if hasattr(self, 'entry_consent_id') else ""

        if (not cid_val or cid_val in ("-", "N/A", "None")) and entry_txt:
            cid_val = entry_txt
        if (not item_val or item_val in ("-", "N/A", "None")):
            if entry_txt and entry_txt != cid_val:
                item_val = entry_txt
            elif hasattr(self, 'entry_item_id') and self.entry_item_id.get().strip():
                item_val = self.entry_item_id.get().strip()

        self.lbl_val_cid.configure(text=cid_val if cid_val and cid_val not in ("None", "N/A") else "-")
        self.lbl_val_itemid.configure(text=item_val if item_val and item_val not in ("None", "N/A") else "-")
        self.lbl_val_created.configure(text=info.get("created_str") or "-")
        self.lbl_val_expires.configure(text=info.get("expires_str") or "Sem expiração")
        self.lbl_val_revoked.configure(text=info.get("revoked_str") or "Não desconectado")

        all_count = info.get("all_consents_count")
        if all_count and all_count > 1:
            self.lbl_val_historico.configure(
                text=f"Mais recente de {all_count} consentimentos vinculados a este Item",
                text_color="#38BDF8"
            )
        else:
            self.lbl_val_historico.configure(
                text="Consentimento único / direto da conexão",
                text_color="#94A3B8"
            )

        # 4. Produtos Financeiros
        for w in self.container_produtos_cards.winfo_children():
            w.destroy()

        prods_enr = info.get("products_enriched", [])
        if st_key == "REVOKED":
            self.lbl_tit_produtos.configure(text=f"Produtos com Compartilhamento Desconectado ({len(prods_enr)})")
            if hasattr(self, 'lbl_subtit_produtos'):
                self.lbl_subtit_produtos.configure(
                    text="Estes recursos faziam parte do consentimento, mas o compartilhamento de dados foi cancelado definitivamente devido à desconexão:"
                )
            badge_bg = "#4C0519"
            badge_border = "#881337"
            badge_txt = "✕ Desconectado"
            badge_cor = "#FB7185"
            nome_cor = "#94A3B8"
        elif st_key == "EXPIRED":
            self.lbl_tit_produtos.configure(text=f"Produtos com Consentimento Expirado ({len(prods_enr)})")
            if hasattr(self, 'lbl_subtit_produtos'):
                self.lbl_subtit_produtos.configure(
                    text="O prazo de vigência de 12 meses expirou. Os recursos estão suspensos até nova autorização:"
                )
            badge_bg = "#451A03"
            badge_border = "#78350F"
            badge_txt = "⚠️ Expirado"
            badge_cor = "#F59E0B"
            nome_cor = "#94A3B8"
        elif st_key == "WAITING_AUTHORISATION":
            self.lbl_tit_produtos.configure(text=f"Produtos Aguardando Aprovação ({len(prods_enr)})")
            if hasattr(self, 'lbl_subtit_produtos'):
                self.lbl_subtit_produtos.configure(
                    text="Recursos solicitados que aguardam aprovação do cliente no aplicativo do banco:"
                )
            badge_bg = "#0C4A6E"
            badge_border = "#0284C7"
            badge_txt = "⏳ Pendente"
            badge_cor = "#38BDF8"
            nome_cor = "#E2E8F0"
        else:
            self.lbl_tit_produtos.configure(text=f"Produtos Financeiros Consentidos ({len(prods_enr)})")
            if hasattr(self, 'lbl_subtit_produtos'):
                self.lbl_subtit_produtos.configure(
                    text="Dados e recursos que o cliente autorizou a sincronizar a partir da instituição bancária:"
                )
            badge_bg = "#064E3B"
            badge_border = "#047857"
            badge_txt = "✓ Autorizado"
            badge_cor = "#10B981"
            nome_cor = "#FFFFFF"

        if prods_enr:
            for p in prods_enr:
                card_p = ctk.CTkFrame(self.container_produtos_cards, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
                card_p.pack(fill=tk.X, pady=3)

                r_p = ctk.CTkFrame(card_p, fg_color="transparent")
                r_p.pack(fill=tk.X, padx=12, pady=8)

                # Ícone do produto
                ctk.CTkLabel(r_p, text=p["icone"], font=("Segoe UI", 16)).pack(side=tk.LEFT, padx=(0, 10))

                col_t = ctk.CTkFrame(r_p, fg_color="transparent")
                col_t.pack(side=tk.LEFT, fill=tk.X, expand=True)

                ctk.CTkLabel(col_t, text=p["nome"], font=("Segoe UI", 11, "bold"), text_color=nome_cor, anchor="w").pack(anchor="w")
                ctk.CTkLabel(col_t, text=p["desc"], font=("Segoe UI", 10), text_color="#64748B" if st_key in ("REVOKED", "EXPIRED") else "#94A3B8", anchor="w").pack(anchor="w")

                badge = ctk.CTkFrame(r_p, fg_color=badge_bg, corner_radius=10, border_width=1, border_color=badge_border)
                badge.pack(side=tk.RIGHT, padx=4)
                ctk.CTkLabel(badge, text=badge_txt, font=("Segoe UI", 9, "bold"), text_color=badge_cor).pack(padx=8, pady=2)
        else:
            txt_vazio = "Nenhum produto listado nesta conta desconectada." if st_key == "REVOKED" else "Nenhum produto listado neste consentimento."
            ctk.CTkLabel(self.container_produtos_cards, text=txt_vazio, font=("Segoe UI", 11, "italic"), text_color="#64748B").pack(anchor="w", padx=6, pady=4)

        # 5. Permissões Agrupadas por Categoria
        for w in self.container_permissoes_agrupadas.winfo_children():
            w.destroy()

        perms_enr = info.get("permissions_enriched", [])
        perms_by_cat = info.get("permissions_by_category", {})
        if st_key == "REVOKED":
            self.lbl_tit_permissoes.configure(text=f"Permissões Regulatórias Desconectadas ({len(perms_enr)})")
            if hasattr(self, 'lbl_subtit_permissoes'):
                self.lbl_subtit_permissoes.configure(
                    text="Escopos técnicos que haviam sido autorizados no Open Finance, atualmente cancelados devido à desconexão:"
                )
            cor_code_txt = "#FCA5A5"
        elif st_key == "EXPIRED":
            self.lbl_tit_permissoes.configure(text=f"Permissões Regulatórias Expiradas ({len(perms_enr)})")
            if hasattr(self, 'lbl_subtit_permissoes'):
                self.lbl_subtit_permissoes.configure(
                    text="Escopos técnicos cuja validade expirou, pendentes de renovação pelo cliente:"
                )
            cor_code_txt = "#FCD34D"
        elif st_key == "WAITING_AUTHORISATION":
            self.lbl_tit_permissoes.configure(text=f"Permissões Regulatórias Solicitadas ({len(perms_enr)})")
            if hasattr(self, 'lbl_subtit_permissoes'):
                self.lbl_subtit_permissoes.configure(
                    text="Escopos técnicos solicitados para aprovação do titular no banco transmissor:"
                )
            cor_code_txt = "#93C5FD"
        else:
            self.lbl_tit_permissoes.configure(text=f"Permissões Regulatórias Concedidas ({len(perms_enr)})")
            if hasattr(self, 'lbl_subtit_permissoes'):
                self.lbl_subtit_permissoes.configure(
                    text="Escopos técnicos autorizados pelo titular da conta conforme as diretrizes do Banco Central do Brasil:"
                )
            cor_code_txt = "#A7F3D0"

        if perms_by_cat:
            for cat_nome, perm_list in perms_by_cat.items():
                cat_box = ctk.CTkFrame(self.container_permissoes_agrupadas, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1E293B")
                cat_box.pack(fill=tk.X, pady=4)

                cat_header = ctk.CTkFrame(cat_box, fg_color="transparent")
                cat_header.pack(fill=tk.X, padx=12, pady=(8, 4))

                icone_cat = perm_list[0].get("icone_cat", "🛡️") if perm_list else "🛡️"
                cor_cat_tit = "#38BDF8" if st_key == "ACTIVE" else ("#FB7185" if st_key == "REVOKED" else "#F59E0B")
                ctk.CTkLabel(cat_header, text=f"{icone_cat} {cat_nome}", font=("Segoe UI", 11, "bold"), text_color=cor_cat_tit).pack(side=tk.LEFT)
                ctk.CTkLabel(cat_header, text=f"{len(perm_list)} permissões", font=("Segoe UI", 9), text_color="#64748B").pack(side=tk.RIGHT)

                for perm in perm_list:
                    r_perm = ctk.CTkFrame(cat_box, fg_color="transparent")
                    r_perm.pack(fill=tk.X, padx=12, pady=3)

                    # Pill com o código técnico
                    b_code = ctk.CTkFrame(r_perm, fg_color="#1E293B", corner_radius=6)
                    b_code.pack(side=tk.LEFT, padx=(0, 8))
                    ctk.CTkLabel(b_code, text=f" {perm['key']} ", font=("Consolas", 9), text_color=cor_code_txt).pack(padx=4, pady=2)

                    f_ptxt = ctk.CTkFrame(r_perm, fg_color="transparent")
                    f_ptxt.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    ctk.CTkLabel(f_ptxt, text=f"{perm['nome']}: {perm['desc']}", font=("Segoe UI", 10), text_color="#E2E8F0" if st_key == "ACTIVE" else "#94A3B8", anchor="w").pack(anchor="w")

                # Espaço inferior da categoria
                ctk.CTkFrame(cat_box, height=4, fg_color="transparent").pack()
        else:
            ctk.CTkLabel(self.container_permissoes_agrupadas, text="Nenhuma permissão regulatória listada no registro retornado.", font=("Segoe UI", 11, "italic"), text_color="#64748B").pack(anchor="w", padx=6, pady=4)

        # 6. Parecer e Recomendações
        self.lbl_rec_titulo.configure(text=info["recomendacao_titulo"], text_color=info["cor_status"])
        self.lbl_rec_texto.configure(text=info["recomendacao_texto"])

        # Ajusta botões contextuais do parecer
        self.btn_acao_reconectar.pack_forget()
        self.btn_acao_copiar_msg_cliente.pack_forget()

        if info["tipo_acao"] in ("expirado", "revogado", "desconectado", "aguardando"):
            self.btn_acao_reconectar.pack(side=tk.LEFT, padx=(0, 8))
            self.btn_acao_copiar_msg_cliente.pack(side=tk.LEFT, padx=(0, 8))

        # 7. Renderizar JSON puro na visualização alternativa
        self.renderizar_json_texto(self.txt_json_t3, data)

    def abrir_janela_situacao_consentimento(self, data):
        info = analisar_situacao_consentimento(data)
        if not info:
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Situação Atual do Consentimento - Pluggy Open Finance")
        janela.geometry("780x720")
        janela.minsize(700, 580)
        janela.transient(self)

        # Header
        header = ctk.CTkFrame(janela, fg_color="#0F172A", height=54, corner_radius=0)
        header.pack(fill=tk.X)

        lbl_h = ctk.CTkLabel(header, text="Situação Atual do Consentimento", font=("Segoe UI", 15, "bold"), text_color="#FFFFFF")
        lbl_h.pack(side=tk.LEFT, padx=16, pady=12)

        lbl_sub = ctk.CTkLabel(header, text="(GET /consents/{id})", font=("Consolas", 11), text_color="#64748B")
        lbl_sub.pack(side=tk.LEFT)

        btn_doc = ctk.CTkButton(
            header,
            text="Docs Pluggy ↗",
            width=105,
            height=28,
            font=("Segoe UI", 10),
            fg_color="#1E293B",
            hover_color="#334155",
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt/reference/consent/consent-retrieve")
        )
        btn_doc.pack(side=tk.RIGHT, padx=16)

        # Container Principal
        main_frame = ctk.CTkFrame(janela, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # 1. Card de Situação em Destaque
        card_destaque = ctk.CTkFrame(main_frame, fg_color=info["cor_bg"], corner_radius=12, border_width=1, border_color=info["cor_border"])
        card_destaque.pack(fill=tk.X, pady=(0, 10))

        row_top = ctk.CTkFrame(card_destaque, fg_color="transparent")
        row_top.pack(fill=tk.X, padx=16, pady=(12, 6))

        pill = ctk.CTkLabel(
            row_top,
            text=f" {info['icone']}  {info['status_titulo']} ",
            font=("Segoe UI", 13, "bold"),
            text_color=info["cor_status"],
            fg_color="#0B0F19",
            corner_radius=12
        )
        pill.pack(side=tk.LEFT)

        lbl_prazo_top = ctk.CTkLabel(
            row_top,
            text=f"⏱️ {info['msg_prazo']}",
            font=("Segoe UI", 11, "bold"),
            text_color=info["cor_status"]
        )
        lbl_prazo_top.pack(side=tk.RIGHT)

        lbl_desc = ctk.CTkLabel(
            card_destaque,
            text=info["detalhe"],
            font=("Segoe UI", 12),
            text_color="#E2E8F0",
            wraplength=700,
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=16, pady=(0, 12))

        # 2. Informações Gerais (IDs e Prazos)
        card_dados = ctk.CTkFrame(main_frame, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
        card_dados.pack(fill=tk.X, pady=(0, 10))

        f_ids = ctk.CTkFrame(card_dados, fg_color="transparent")
        f_ids.pack(fill=tk.X, padx=14, pady=10)

        # Consent ID
        r1 = ctk.CTkFrame(f_ids, fg_color="transparent")
        r1.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(r1, text="Consent ID:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=95, anchor="w").pack(side=tk.LEFT)
        lbl_cid = ctk.CTkLabel(r1, text=info["id"], font=("Consolas", 11), text_color="#38BDF8", anchor="w")
        lbl_cid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        btn_c1 = ctk.CTkButton(r1, text="Copiar", width=55, height=22, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(info["id"], btn_c1))
        btn_c1.pack(side=tk.RIGHT)

        # Item ID
        r2 = ctk.CTkFrame(f_ids, fg_color="transparent")
        r2.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(r2, text="Item ID:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=95, anchor="w").pack(side=tk.LEFT)
        lbl_iid = ctk.CTkLabel(r2, text=info["item_id"], font=("Consolas", 11), text_color="#E2E8F0", anchor="w")
        lbl_iid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        btn_c2 = ctk.CTkButton(r2, text="Copiar", width=55, height=22, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(info["item_id"], btn_c2))
        btn_c2.pack(side=tk.RIGHT)

        # Datas
        r3 = ctk.CTkFrame(f_ids, fg_color="transparent")
        r3.pack(fill=tk.X, pady=(6, 2))
        ctk.CTkLabel(r3, text=f"Criado em: {info['created_str']}", font=("Segoe UI", 11), text_color="#94A3B8").pack(side=tk.LEFT, padx=(0, 20))
        ctk.CTkLabel(r3, text=f"Expira em: {info['expires_str']}", font=("Segoe UI", 11), text_color="#94A3B8").pack(side=tk.LEFT, padx=(0, 20))
        ctk.CTkLabel(r3, text=f"Desconectado em: {info['revoked_str']}", font=("Segoe UI", 11), text_color="#94A3B8").pack(side=tk.LEFT)

        # 3. Badges de Produtos e Permissões Enriquecidos
        prods_enr = info.get("products_enriched", [])
        perms_enr = info.get("permissions_enriched", [])
        st_key = info.get("status_key")
        if prods_enr or perms_enr:
            card_p = ctk.CTkFrame(main_frame, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
            card_p.pack(fill=tk.X, pady=(0, 10))

            if prods_enr:
                f_p = ctk.CTkFrame(card_p, fg_color="transparent")
                f_p.pack(fill=tk.X, padx=14, pady=6)
                txt_lbl_p = "Produtos:" if st_key == "ACTIVE" else ("Produtos Desconectados:" if st_key == "REVOKED" else "Produtos Expirados:")
                ctk.CTkLabel(f_p, text=txt_lbl_p, font=("Segoe UI", 11, "bold"), text_color="#64748B", width=145, anchor="w").pack(side=tk.LEFT)
                cor_tag_p = "#38BDF8" if st_key == "ACTIVE" else ("#FB7185" if st_key == "REVOKED" else "#F59E0B")
                for prod in prods_enr:
                    ctk.CTkLabel(f_p, text=f" {prod['icone']} {prod['nome']} ", fg_color="#1E293B", text_color=cor_tag_p, corner_radius=6, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=3)

            if perms_enr:
                f_perm = ctk.CTkFrame(card_p, fg_color="transparent")
                f_perm.pack(fill=tk.X, padx=14, pady=(2, 8))
                txt_lbl_perm = "Permissões:" if st_key == "ACTIVE" else ("Permissões Desconectadas:" if st_key == "REVOKED" else "Permissões Expiradas:")
                ctk.CTkLabel(f_perm, text=txt_lbl_perm, font=("Segoe UI", 11, "bold"), text_color="#64748B", width=145, anchor="w").pack(side=tk.LEFT)
                cor_tag_perm = "#A7F3D0" if st_key == "ACTIVE" else ("#FCA5A5" if st_key == "REVOKED" else "#FCD34D")
                for perm in perms_enr[:6]:
                    ctk.CTkLabel(f_perm, text=f" {perm['nome']} ", fg_color="#1E293B", text_color=cor_tag_perm, corner_radius=6, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
                if len(perms_enr) > 6:
                    ctk.CTkLabel(f_perm, text=f"+{len(perms_enr)-6} mais", font=("Segoe UI", 9, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=2)

        # 4. JSON Bruto com Scroll
        card_j = ctk.CTkFrame(main_frame, fg_color="#07090E", corner_radius=10, border_width=1, border_color="#1F2937")
        card_j.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        bar_j = ctk.CTkFrame(card_j, height=32, fg_color="#0B0F19", corner_radius=6)
        bar_j.pack(fill=tk.X, padx=4, pady=(4, 2))
        ctk.CTkLabel(bar_j, text="JSON da Resposta (Pluggy):", font=("Segoe UI", 10, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=8)

        btn_cp_j = ctk.CTkButton(
            bar_j,
            text="Copiar JSON",
            width=80,
            height=22,
            font=("Segoe UI", 9),
            fg_color="#1E293B",
            hover_color="#334155",
            command=lambda: self.copiar_para_clipboard(json.dumps(data, indent=2, ensure_ascii=False), btn_cp_j)
        )
        btn_cp_j.pack(side=tk.RIGHT, padx=6)

        scroll_m_y = ctk.CTkScrollbar(card_j, orientation="vertical", fg_color="#07090E", button_color="#1E293B", width=12)
        txt_modal = tk.Text(card_j, wrap=tk.NONE, font=("Consolas", 10), bg="#07090E", fg="#D4D4D4", bd=0, yscrollcommand=scroll_m_y.set)
        scroll_m_y.configure(command=txt_modal.yview)
        scroll_m_y.pack(side=tk.RIGHT, fill=tk.Y, padx=2, pady=2)
        txt_modal.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        txt_modal.tag_configure("key", foreground="#9CDCFE")
        txt_modal.tag_configure("string", foreground="#CE9178")
        txt_modal.tag_configure("number", foreground="#B5CEA8")
        txt_modal.tag_configure("boolean", foreground="#569CD6")
        self.renderizar_json_texto(txt_modal, data)
        txt_modal.configure(state="disabled")

        # Botão Fechar
        btn_fechar = ctk.CTkButton(
            main_frame,
            text="Fechar",
            width=120,
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11, "bold"),
            command=janela.destroy
        )
        btn_fechar.pack(anchor="e", pady=(4, 0))

    def acao_buscar_t3(self):
        query = self.entry_busca_t3.get().strip()
        self.executar_busca_json_t3(query)

    def executar_busca_json_t3(self, query=None):
        if query is None:
            query = self.entry_busca_t3.get().strip()
        self.txt_json_t3.tag_remove("highlight", "1.0", tk.END)
        self.txt_json_t3.tag_remove("current_highlight", "1.0", tk.END)
        self.json_matches_t3.clear()
        self.json_current_match_t3 = -1
        self.lbl_busca_status_t3.configure(text="")

        if not query:
            return

        pos = "1.0"
        while True:
            pos = self.txt_json_t3.search(query, pos, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end_pos = f"{pos} + {len(query)} chars"
            self.json_matches_t3.append((pos, end_pos))
            self.txt_json_t3.tag_add("highlight", pos, end_pos)
            pos = end_pos

        if self.json_matches_t3:
            self.json_current_match_t3 = 0
            self.atualizar_foco_json_t3()
        else:
            self.lbl_busca_status_t3.configure(text="0 ocorrências")

    def localizar_proximo_json_t3(self):
        if not self.json_matches_t3:
            self.executar_busca_json_t3()
            return
        self.json_current_match_t3 = (self.json_current_match_t3 + 1) % len(self.json_matches_t3)
        self.atualizar_foco_json_t3()

    def localizar_anterior_json_t3(self):
        if not self.json_matches_t3:
            return
        self.json_current_match_t3 = (self.json_current_match_t3 - 1) % len(self.json_matches_t3)
        self.atualizar_foco_json_t3()

    def atualizar_foco_json_t3(self):
        self.txt_json_t3.tag_remove("current_highlight", "1.0", tk.END)
        start, end = self.json_matches_t3[self.json_current_match_t3]
        self.txt_json_t3.tag_add("current_highlight", start, end)
        self.txt_json_t3.see(start)
        self.lbl_busca_status_t3.configure(text=f"{self.json_current_match_t3 + 1} de {len(self.json_matches_t3)}")

    def abrir_janela_credenciais(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Configurações da API Pluggy")
        janela.geometry("560x440")
        janela.minsize(540, 420)
        janela.transient(self)

        # Centralizar sobre a janela principal
        try:
            janela.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 280
            y = self.winfo_y() + (self.winfo_height() // 2) - 220
            janela.geometry(f"+{max(40, x)}+{max(40, y)}")
        except Exception:
            pass

        lbl_t = ctk.CTkLabel(janela, text="Credenciais Pluggy Open Finance", font=("Segoe UI", 14, "bold"))
        lbl_t.pack(padx=20, pady=(18, 4), anchor="w")

        lbl_desc = ctk.CTkLabel(janela, text="Suas credenciais são salvas localmente em config.json.", font=("Segoe UI", 11), text_color="#9CA3AF")
        lbl_desc.pack(padx=20, pady=(0, 14), anchor="w")

        lbl_cid = ctk.CTkLabel(janela, text="Client ID:", font=("Segoe UI", 11, "bold"))
        lbl_cid.pack(padx=20, anchor="w")

        entry_cid = ctk.CTkEntry(janela, width=520, height=36, font=("Consolas", 11), border_color="#1F2937")
        entry_cid.insert(0, self.client_id)
        entry_cid.pack(padx=20, pady=(2, 10))

        lbl_sec = ctk.CTkLabel(janela, text="Client Secret:", font=("Segoe UI", 11, "bold"))
        lbl_sec.pack(padx=20, anchor="w")

        entry_sec = ctk.CTkEntry(janela, width=520, height=36, show="•", font=("Consolas", 11), border_color="#1F2937")
        entry_sec.insert(0, self.client_secret)
        entry_sec.pack(padx=20, pady=(2, 16))

        def salvar_e_testar():
            cid = entry_cid.get().strip()
            sec = entry_sec.get().strip()
            if not cid or not sec:
                messagebox.showwarning("Aviso", "Preencha Client ID e Client Secret.", parent=janela)
                return

            self.salvar_config(cid, sec)
            btn_salvar.configure(text="Testando conexão...", state="disabled")

            def worker_test():
                sucesso = self.obter_api_key(force_refresh=True)
                if sucesso:
                    self.safe_after(0, lambda: messagebox.showinfo("Sucesso", "Credenciais salvas e conexão com a Pluggy testada com sucesso!", parent=janela))
                    self.safe_after(0, janela.destroy)
                else:
                    self.safe_after(0, lambda: btn_salvar.configure(text="Salvar e Testar Conexão", state="normal"))
                    self.safe_after(0, lambda: messagebox.showerror("Erro de Autenticação", "As credenciais foram salvas, mas a autenticação com a Pluggy falhou.", parent=janela))

            threading.Thread(target=worker_test, daemon=True).start()

        btn_salvar = ctk.CTkButton(
            janela,
            text="Salvar e Testar Conexão",
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 12, "bold"),
            height=38,
            command=salvar_e_testar
        )
        btn_salvar.pack(padx=20, pady=(0, 14), fill=tk.X)

        # Seção de Versão e Atualização (Card dedicado e estilizado)
        card_update = ctk.CTkFrame(janela, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
        card_update.pack(fill=tk.X, padx=20, pady=(0, 10))

        card_update_inner = ctk.CTkFrame(card_update, fg_color="transparent")
        card_update_inner.pack(fill=tk.X, padx=14, pady=12)

        info_box = ctk.CTkFrame(card_update_inner, fg_color="transparent")
        info_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lbl_versao = ctk.CTkLabel(
            info_box,
            text=f"Pluggy Explorer  v{APP_VERSION}",
            font=("Segoe UI", 12, "bold"),
            text_color="#F8FAFC",
            anchor="w"
        )
        lbl_versao.pack(anchor="w")

        status_texto = "⬇ Atualização sendo baixada em segundo plano..." if self._is_updating else "● Verificação automática em segundo plano ativa"
        status_cor = "#38BDF8" if self._is_updating else "#10B981"
        self.lbl_update_modal_status = ctk.CTkLabel(
            info_box,
            text=status_texto,
            font=("Segoe UI", 10),
            text_color=status_cor,
            anchor="w"
        )
        self.lbl_update_modal_status.pack(anchor="w", pady=(2, 0))

        self.btn_modal_verif_update = ctk.CTkButton(
            card_update_inner,
            text="🔄 Verificar Atualizações",
            width=180,
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11, "bold"),
            border_width=1,
            border_color="#334155",
            command=lambda: self.acao_clique_verificar_atualizacao(janela_origem=janela)
        )
        self.btn_modal_verif_update.pack(side=tk.RIGHT, padx=(10, 0))

        btn_modal_docs = ctk.CTkButton(
            janela,
            text="📖 Documentação Oficial Pluggy (docs.pluggy.ai/pt) ↗",
            fg_color="transparent",
            hover_color="#1E293B",
            text_color="#38BDF8",
            font=("Segoe UI", 11),
            height=28,
            command=lambda: webbrowser.open("https://docs.pluggy.ai/pt")
        )
        btn_modal_docs.pack(padx=20, pady=(0, 12))

    # =========================================================================
    # SISTEMA DE ATUALIZAÇÕES AUTOMÁTICAS EM SEGUNDO PLANO E REINICIALIZAÇÃO
    # =========================================================================

    def _obter_caminho_arquivo_marcador_update(self):
        """Retorna o caminho seguro para o marcador de atualização pós-restart"""
        for d in obter_diretorios_busca():
            if os.path.isdir(d):
                return os.path.join(d, "_update_success.json")
        return os.path.join(os.getcwd(), "_update_success.json")

    def _verificar_pos_atualizacao(self):
        """
        Executado logo após a inicialização da aplicação para verificar se o
        executável acabou de ser reiniciado após uma atualização bem-sucedida.
        """
        just_updated = "--just-updated" in sys.argv
        if just_updated:
            sys.argv = [arg for arg in sys.argv if arg != "--just-updated"]

        marker_path = self._obter_caminho_arquivo_marcador_update()
        info_update = None
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r", encoding="utf-8") as f:
                    info_update = json.load(f)
                os.remove(marker_path)
            except Exception as e:
                print("Aviso ao ler/remover marcador de update:", e)

        if just_updated or info_update:
            versao_antiga = info_update.get("versao_anterior", "") if info_update else ""
            self.after(400, lambda: self._mostrar_modal_pos_atualizacao_sucesso(versao_antiga))

    def _mostrar_modal_pos_atualizacao_sucesso(self, versao_anterior=""):
        """Exibe modal comemorativo informando que o app foi atualizado com sucesso"""
        win = ctk.CTkToplevel(self)
        win.title("Pluggy Explorer - Atualizado!")
        win.geometry("500x290")
        win.minsize(460, 270)
        win.transient(self)
        win.grab_set()

        try:
            win.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 250
            y = self.winfo_y() + (self.winfo_height() // 2) - 145
            win.geometry(f"+{max(40, x)}+{max(40, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(win, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        lbl_badge = ctk.CTkLabel(
            card,
            text="🎉 Atualização Concluída com Sucesso!",
            font=("Segoe UI", 15, "bold"),
            text_color="#10B981"
        )
        lbl_badge.pack(pady=(20, 6))

        txt_v = f"Versão anterior: v{versao_anterior}  ➔  Versão atual: v{APP_VERSION}" if versao_anterior else f"Você agora está utilizando a versão mais recente: v{APP_VERSION}"
        lbl_v = ctk.CTkLabel(
            card,
            text=txt_v,
            font=("Segoe UI", 12, "bold"),
            text_color="#F8FAFC"
        )
        lbl_v.pack(pady=(0, 10))

        lbl_det = ctk.CTkLabel(
            card,
            text="O Pluggy Explorer foi reiniciado automaticamente e todas as novas melhorias,\notimizações de diagnóstico e novidades da API Open Finance\nestão ativas e prontas para uso.",
            font=("Segoe UI", 11),
            text_color="#94A3B8",
            justify="center"
        )
        lbl_det.pack(pady=(0, 18))

        btn_ok = ctk.CTkButton(
            card,
            text="🚀 Continuar Explorando",
            fg_color="#059669",
            hover_color="#047857",
            font=("Segoe UI", 12, "bold"),
            height=38,
            width=210,
            command=win.destroy
        )
        btn_ok.pack(pady=(0, 10))

        self.exibir_alerta("Atualização Concluída", f"Pluggy Explorer atualizado com sucesso para v{APP_VERSION}!", cor="#059669")

    def _extrair_tupla_versao(self, v_str):
        """Converte strings como 'v1.4.0' ou '1.5.0-beta' em tuplas de inteiros para comparação confiável"""
        if not v_str:
            return (0,)
        parts = re.findall(r'\d+', str(v_str))
        return tuple(int(p) for p in parts) if parts else (0,)

    def _buscar_dados_release_github(self):
        """
        Consulta a API do GitHub Releases com tolerância a falhas.
        Tenta /releases/latest e, se retornar 404, faz fallback para a lista geral /releases.
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PluggyExplorer"
        }
        url_latest = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            res = requests.get(url_latest, headers=headers, timeout=8)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print("Aviso: Falha ao consultar /releases/latest:", e)

        # Fallback para lista de releases
        try:
            url_all = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
            res_all = requests.get(url_all, headers=headers, timeout=8)
            if res_all.status_code == 200:
                releases = res_all.json()
                if isinstance(releases, list) and len(releases) > 0:
                    return releases[0]
        except Exception as e:
            print("Aviso: Falha ao consultar /releases:", e)

        return None

    def iniciar_verificacao_automatica_atualizacoes(self):
        """Inicia verificação automática em segundo plano sem travar a interface"""
        threading.Thread(target=self._worker_verificacao_automatica, daemon=True).start()

    def _worker_verificacao_automatica(self):
        """Worker silencioso de verificação periódica / de inicialização"""
        if self._is_updating:
            return

        try:
            rel = self._buscar_dados_release_github()
            if not rel:
                return

            tag_raw = rel.get("tag_name", "")
            tag_clean = tag_raw.lstrip("vV").strip()
            ver_remota = self._extrair_tupla_versao(tag_clean)
            ver_local = self._extrair_tupla_versao(APP_VERSION)

            if ver_remota > ver_local:
                assets = rel.get("assets", [])
                exe_url = None
                for a in assets:
                    if a.get("name", "").lower().endswith(".exe"):
                        exe_url = a.get("browser_download_url")
                        break

                is_frozen = getattr(sys, 'frozen', False)
                if is_frozen and exe_url:
                    # Executável compilado: inicia download em segundo plano automaticamente!
                    self._iniciar_download_segundo_plano(exe_url, tag_clean, automatico=True)
                elif not is_frozen:
                    # Modo de desenvolvimento (script Python): apenas alerta no banner
                    self.safe_after(0, lambda: self.exibir_alerta(
                        "Nova Versão Disponível",
                        f"v{tag_clean} disponível no GitHub (Modo Python/Dev).",
                        cor="#0284C7"
                    ))
        except Exception as e:
            print("Erro silencioso na checagem de atualizações:", e)

    def acao_clique_verificar_atualizacao(self, janela_origem=None):
        """Manipula o clique manual no botão 'Verificar Atualizações' com feedback visual claro"""
        if self._is_updating:
            messagebox.showinfo(
                "Atualização em Andamento",
                "Uma atualização já está sendo baixada em segundo plano.\nVocê será notificado assim que o download for concluído.",
                parent=janela_origem or self
            )
            return

        if self.btn_modal_verif_update:
            self.btn_modal_verif_update.configure(text="🔄 Verificando...", state="disabled")

        def worker():
            try:
                rel = self._buscar_dados_release_github()
                self.safe_after(0, lambda: self._restaurar_botao_update())

                if not rel:
                    self.safe_after(0, lambda: messagebox.showinfo(
                        "Atualizações",
                        f"O Pluggy Explorer já está atualizado!\nVersão instalada: v{APP_VERSION}\n\nNenhuma versão superior foi encontrada no servidor.",
                        parent=janela_origem or self
                    ))
                    return

                tag_raw = rel.get("tag_name", "")
                tag_clean = tag_raw.lstrip("vV").strip()
                ver_remota = self._extrair_tupla_versao(tag_clean)
                ver_local = self._extrair_tupla_versao(APP_VERSION)

                if ver_remota > ver_local:
                    assets = rel.get("assets", [])
                    exe_url = None
                    for a in assets:
                        if a.get("name", "").lower().endswith(".exe"):
                            exe_url = a.get("browser_download_url")
                            break

                    corpo_notas = rel.get("body", "Melhorias de desempenho e correções gerais.")
                    html_url = rel.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"

                    def perguntar():
                        msg = (
                            f"Uma nova versão (v{tag_clean}) do Pluggy Explorer está disponível!\n\n"
                            f"• Versão instalada: v{APP_VERSION}\n"
                            f"• Nova versão: v{tag_clean}\n\n"
                            f"Notas da versão:\n{corpo_notas[:280]}\n\n"
                            f"Deseja iniciar o download em segundo plano agora?"
                        )
                        if messagebox.askyesno("Nova Atualização Encontrada", msg, parent=janela_origem or self):
                            if getattr(sys, 'frozen', False) and exe_url:
                                self._iniciar_download_segundo_plano(exe_url, tag_clean, automatico=False, janela_origem=janela_origem)
                            else:
                                webbrowser.open(html_url)

                    self.safe_after(0, perguntar)
                else:
                    self.safe_after(0, lambda: messagebox.showinfo(
                        "Atualizações",
                        f"O Pluggy Explorer já está na versão mais recente!\n\nVersão instalada: v{APP_VERSION}",
                        parent=janela_origem or self
                    ))
            except Exception as e:
                self.safe_after(0, lambda: self._restaurar_botao_update())
                self.safe_after(0, lambda err=str(e): messagebox.showwarning(
                    "Verificação de Atualização",
                    f"Não foi possível verificar atualizações no momento:\n{err}",
                    parent=janela_origem or self
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _restaurar_botao_update(self):
        """Restaura o estado do botão de verificação"""
        if self.btn_modal_verif_update:
            try:
                self.btn_modal_verif_update.configure(text="🔄 Verificar Atualizações", state="normal")
            except Exception:
                pass

    def _iniciar_download_segundo_plano(self, download_url, tag_clean, automatico=False, janela_origem=None):
        """Executa o download do novo binário em segundo plano sem travar a interface"""
        if self._is_updating:
            return

        self._is_updating = True

        # Feedback na UI
        if self.lbl_update_modal_status:
            try:
                self.lbl_update_modal_status.configure(
                    text=f"⬇ Baixando atualização v{tag_clean} em segundo plano...",
                    text_color="#38BDF8"
                )
            except Exception:
                pass

        self.safe_after(0, lambda: self.exibir_alerta(
            "Atualização em Andamento",
            f"Baixando versão v{tag_clean} em segundo plano...",
            cor="#0284C7"
        ))

        def worker():
            try:
                exe_path = sys.executable
                exe_dir = os.path.dirname(os.path.abspath(exe_path))
                temp_exe = os.path.join(exe_dir, "PluggyExplorer_new.exe")

                res = requests.get(download_url, stream=True, timeout=90)
                res.raise_for_status()
                total_size = int(res.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_exe, "wb") as f:
                    for chunk in res.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and self.lbl_update_modal_status:
                                perc = (downloaded / total_size) * 100
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                texto_prog = f"⬇ Baixando v{tag_clean}: {perc:.0f}% ({mb_down:.1f}/{mb_tot:.1f} MB)"
                                self.safe_after(0, lambda s=texto_prog: self._atualizar_texto_status_modal(s))

                if os.path.exists(temp_exe) and os.path.getsize(temp_exe) > 50000:
                    self._is_updating = False
                    self.safe_after(0, lambda: self._preparar_reinicio_com_contagem(temp_exe, exe_path, tag_clean))
                else:
                    raise Exception("O arquivo baixado está incompleto ou corrompido.")

            except Exception as e:
                self._is_updating = False
                print("Erro durante o download da atualização:", e)
                if self.lbl_update_modal_status:
                    self.safe_after(0, lambda: self._atualizar_texto_status_modal("⚠️ Falha ao baixar atualização", cor="#F43F5E"))
                if not automatico:
                    self.safe_after(0, lambda err=str(e): messagebox.showerror(
                        "Erro de Download",
                        f"Não foi possível concluir o download da nova versão:\n{err}",
                        parent=janela_origem or self
                    ))

        threading.Thread(target=worker, daemon=True).start()

    def _atualizar_texto_status_modal(self, texto, cor="#38BDF8"):
        """Atualiza seguramente o texto de status de atualização no modal"""
        if self.lbl_update_modal_status:
            try:
                self.lbl_update_modal_status.configure(text=texto, text_color=cor)
            except Exception:
                pass

    def _preparar_reinicio_com_contagem(self, temp_exe, exe_path, tag_clean):
        """
        Exibe janela com contagem regressiva de 5 segundos informando que o download
        foi concluído e que o aplicativo será reiniciado sozinho para aplicar a atualização.
        """
        reboot_win = ctk.CTkToplevel(self)
        reboot_win.title("Atualização Pronta - Reiniciando")
        reboot_win.geometry("480x260")
        reboot_win.minsize(460, 240)
        reboot_win.transient(self)
        reboot_win.grab_set()

        try:
            reboot_win.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 240
            y = self.winfo_y() + (self.winfo_height() // 2) - 130
            reboot_win.geometry(f"+{max(40, x)}+{max(40, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(reboot_win, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1F2937")
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        lbl_top = ctk.CTkLabel(
            card,
            text=f"⚡ Atualização v{tag_clean} Pronta!",
            font=("Segoe UI", 15, "bold"),
            text_color="#38BDF8"
        )
        lbl_top.pack(pady=(16, 6))

        lbl_msg = ctk.CTkLabel(
            card,
            text="O download em segundo plano foi concluído com sucesso.\nO aplicativo será reiniciado sozinho para aplicar a atualização.",
            font=("Segoe UI", 11),
            text_color="#E2E8F0",
            justify="center"
        )
        lbl_msg.pack(pady=(0, 12))

        progress_bar = ctk.CTkProgressBar(card, width=360, height=8, progress_color="#0284C7", fg_color="#1E293B")
        progress_bar.set(1.0)
        progress_bar.pack(pady=(0, 8))

        lbl_countdown = ctk.CTkLabel(card, text="Reiniciando em 5 segundos...", font=("Segoe UI", 11, "bold"), text_color="#F59E0B")
        lbl_countdown.pack(pady=(0, 14))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack()

        timer_ref = {"cancelado": False, "segundos": 5}

        def reiniciar_agora():
            timer_ref["cancelado"] = True
            try:
                reboot_win.destroy()
            except Exception:
                pass
            self._executar_substituicao_e_reiniciar(temp_exe, exe_path, tag_clean)

        def adiar():
            timer_ref["cancelado"] = True
            try:
                reboot_win.destroy()
            except Exception:
                pass
            self.exibir_alerta("Atualização Pronta", "A atualização será aplicada na próxima reinicialização.", cor="#F59E0B")

        btn_reiniciar = ctk.CTkButton(
            btn_row,
            text="⚡ Reiniciar Agora",
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=("Segoe UI", 11, "bold"),
            height=34,
            width=140,
            command=reiniciar_agora
        )
        btn_reiniciar.pack(side=tk.LEFT, padx=8)

        btn_adiar = ctk.CTkButton(
            btn_row,
            text="Adiar",
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11),
            height=34,
            width=100,
            command=adiar
        )
        btn_adiar.pack(side=tk.LEFT, padx=8)

        def tick():
            if timer_ref["cancelado"]:
                return
            timer_ref["segundos"] -= 1
            if timer_ref["segundos"] <= 0:
                reiniciar_agora()
            else:
                lbl_countdown.configure(text=f"Reiniciando em {timer_ref['segundos']} segundos...")
                progress_bar.set(timer_ref["segundos"] / 5.0)
                self.after(1000, tick)

        self.after(1000, tick)

    def _executar_substituicao_e_reiniciar(self, temp_exe, exe_path, tag_clean):
        """
        Grava o marcador de pós-atualização, cria o script de substituição atômica .bat
        e reinicia a aplicação com o novo executável atualizado.
        """
        import subprocess

        # 1. Gravar marcador json para identificação no relançamento
        marker_path = self._obter_caminho_arquivo_marcador_update()
        try:
            with open(marker_path, "w", encoding="utf-8") as f_mark:
                json.dump({
                    "versao_anterior": APP_VERSION,
                    "nova_versao": tag_clean,
                    "timestamp": datetime.now().isoformat()
                }, f_mark, indent=2)
        except Exception as e:
            print("Aviso ao salvar marcador de update:", e)

        # 2. Criar script .bat para aguardar liberação do processo e substituir arquivo
        exe_dir = os.path.dirname(os.path.abspath(exe_path))
        bat_path = os.path.join(exe_dir, "aplicar_update.bat")
        current_pid = os.getpid()

        bat_content = f"""@echo off
chcp 65001 > nul
timeout /t 1 /nobreak > nul
:loop
taskkill /F /PID {current_pid} > nul 2>&1
del /f /q "{exe_path}" > nul 2>&1
if exist "{exe_path}" (
    timeout /t 1 /nobreak > nul
    goto loop
)
move /y "{temp_exe}" "{exe_path}" > nul
start "" "{exe_path}" --just-updated
del "%~f0"
exit
"""
        with open(bat_path, "w", encoding="utf-8") as f_bat:
            f_bat.write(bat_content)

        # 3. Executar o .bat sem janela e encerrar o processo atual
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=flags)

        self.destroy()
        sys.exit(0)

    def verificar_atualizacoes(self, silencioso=False):
        """Método de compatibilidade com chamadas anteriores"""
        if silencioso:
            self.iniciar_verificacao_automatica_atualizacoes()
        else:
            self.acao_clique_verificar_atualizacao()

    def baixar_e_instalar_atualizacao(self, download_url, versao_tag):
        """Método de compatibilidade com chamadas diretas anteriores"""
        self._iniciar_download_segundo_plano(download_url, versao_tag, automatico=False)


if __name__ == "__main__":
    app = ModernPluggyApp()
    app.mainloop()
