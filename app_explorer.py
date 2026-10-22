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
DEFAULT_CLIENT_ID = "fe96af16-0c23-44e6-8d0a-57223694b760"
DEFAULT_CLIENT_SECRET = "f7c14c58-f0d0-4947-8423-721548882db7"
APP_VERSION = "1.2.0"
GITHUB_REPO = "Fulviotanure/API-OPEN-FINANCE"

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


def analisar_situacao_consentimento(data):
    """
    Interpreta o recurso de consentimento retornado pela API da Pluggy
    (https://docs.pluggy.ai/pt/reference/consent/consent-retrieve)
    Calcula se o consentimento está Ativo, Expirado ou Revogado,
    além de formatar datas, produtos e permissões concedidas.
    """
    if not isinstance(data, dict):
        return None

    revoked_at = data.get("revokedAt")
    expires_at = data.get("expiresAt")
    created_at = data.get("createdAt")

    revoked_str = formatar_data_hora_br(revoked_at) if revoked_at else None
    expires_str = formatar_data_hora_br(expires_at) if expires_at else None
    created_str = formatar_data_hora_br(created_at) if created_at else "N/A"

    if revoked_at:
        status_key = "REVOKED"
        status_titulo = "REVOGADO"
        cor_status = "#F43F5E"  # Vermelho / Rose moderno
        cor_bg = "#4C0519"
        cor_border = "#881337"
        icone = "●"
        detalhe = f"Consentimento revogado pelo usuário ou instituição em {revoked_str}."
    elif expires_at:
        try:
            clean_exp = str(expires_at).replace('Z', '+00:00')
            clean_exp_val = clean_exp.split('+')[0]
            if '.' in clean_exp_val:
                dt_exp = datetime.strptime(clean_exp_val, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt_exp = datetime.strptime(clean_exp_val, "%Y-%m-%dT%H:%M:%S")

            agora_naive = datetime.utcnow()
            if dt_exp < agora_naive:
                status_key = "EXPIRED"
                status_titulo = "EXPIRADO"
                cor_status = "#F59E0B"  # Âmbar
                cor_bg = "#451A03"
                cor_border = "#78350F"
                icone = "●"
                dias_passados = (agora_naive - dt_exp).days
                detalhe = f"Consentimento expirou em {expires_str} (há {dias_passados} dias)."
            else:
                status_key = "ACTIVE"
                status_titulo = "ATIVO / AUTORIZADO"
                cor_status = "#10B981"  # Verde esmeralda
                cor_bg = "#064E3B"
                cor_border = "#047857"
                icone = "●"
                dias_restantes = (dt_exp - agora_naive).days
                if dias_restantes > 0:
                    detalhe = f"Consentimento ativo e válido até {expires_str} (restam {dias_restantes} dias)."
                else:
                    detalhe = f"Consentimento ativo e válido até {expires_str} (expira hoje)."
        except Exception:
            status_key = "ACTIVE"
            status_titulo = "ATIVO"
            cor_status = "#10B981"
            cor_bg = "#064E3B"
            cor_border = "#047857"
            icone = "●"
            detalhe = f"Consentimento ativo até {expires_str}."
    else:
        status_key = "ACTIVE"
        status_titulo = "ATIVO (INDETERMINADO)"
        cor_status = "#10B981"
        cor_bg = "#064E3B"
        cor_border = "#047857"
        icone = "●"
        detalhe = "Consentimento ativo sem data limite de expiração."

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
        "revoked_str": revoked_str or "Não revogado",
        "id": data.get("id", "N/A"),
        "item_id": data.get("itemId", "N/A"),
        "products": data.get("products", []) or [],
        "permissions": data.get("openFinancePermissionsGranted", []) or []
    }


ERROS_DIAGNOSTICO_MAP = {
    "INVALID_CREDENTIALS": {
        "titulo": "Credenciais Inválidas / Senha Incorreta",
        "explicacao": "As credenciais fornecidas (usuário, senha, agência, conta ou CPF) foram rejeitadas pelo sistema do banco.",
        "acao": "Peça ao cliente para verificar os dados no aplicativo oficial do banco e reconectar a conta pelo Pluggy Connect.",
        "severidade": "alta"
    },
    "INVALID_CREDENTIALS_2FA": {
        "titulo": "Segundo Fator de Autenticação Incorreto",
        "explicacao": "O código do token (MFA / SMS / Token do aplicativo) digitado pelo usuário estava incorreto ou expirou.",
        "acao": "Inicie uma nova tentativa e solicite que o usuário insira o código de token imediatamente após gerá-lo.",
        "severidade": "alta"
    },
    "ACCOUNT_LOCKED": {
        "titulo": "Conta ou Internet Banking Bloqueado",
        "explicacao": "O acesso digital da conta foi bloqueado pelo banco por excesso de tentativas incorretas ou medidas de segurança.",
        "acao": "O cliente deve desbloquear o acesso no aplicativo do banco, caixa eletrônico ou com o gerente antes de tentar novamente.",
        "severidade": "critica"
    },
    "SITE_NOT_AVAILABLE": {
        "titulo": "Instituição Temporariamente Indisponível",
        "explicacao": "Os servidores ou internet banking da instituição financeira estão temporariamente fora do ar ou em manutenção.",
        "acao": "Aguarde a estabilização do banco (geralmente alguns minutos a horas) e solicite uma nova sincronização.",
        "severidade": "media"
    },
    "USER_INPUT_TIMEOUT": {
        "titulo": "Tempo Limite de Interação Esgotado",
        "explicacao": "O tempo para o usuário responder ao desafio de segurança (MFA, token ou confirmação no celular) expirou.",
        "acao": "Inicie uma nova tentativa quando o cliente estiver com o celular desbloqueado pronto para autorizar a conexão.",
        "severidade": "media"
    },
    "ALREADY_LOGGED_IN": {
        "titulo": "Sessão Concorrente Detectada no Banco",
        "explicacao": "O banco detectou que o cliente já está conectado em outro dispositivo (celular ou computador) e bloqueou logins simultâneos.",
        "acao": "Oriente o cliente a fazer logout em todos os dispositivos/aplicativos do banco e aguardar 2 a 3 minutos antes de reconectar.",
        "severidade": "media"
    },
    "CONNECTOR_ERROR": {
        "titulo": "Falha na Comunicação do Conector",
        "explicacao": "O conector da Pluggy encontrou uma instabilidade ao se comunicar com a instituição financeira.",
        "acao": "Tente sincronizar novamente mais tarde. Se persistir, verifique a página de status dos conectores da Pluggy.",
        "severidade": "alta"
    },
    "UNEXPECTED_ERROR": {
        "titulo": "Instabilidade Inesperada no Conector",
        "explicacao": "Ocorreu uma falha inesperada durante a sincronização dos dados com a instituição bancária.",
        "acao": "Tente atualizar o item novamente. Caso o erro persista, consulte a documentação ou o suporte da Pluggy.",
        "severidade": "alta"
    },
    "WAITING_USER_INPUT": {
        "titulo": "Aguardando Interação do Usuário (MFA)",
        "explicacao": "A instituição está aguardando uma confirmação ou dado adicional do usuário (código MFA, aprovação push ou token).",
        "acao": "Abra o widget do Pluggy Connect para que o usuário forneça a validação exigida pela instituição.",
        "severidade": "atencao"
    },
    "OUTDATED": {
        "titulo": "Conexão Desatualizada / Sessão Expirada",
        "explicacao": "A conexão precisa de uma nova autenticação do usuário para voltar a sincronizar os dados bancários.",
        "acao": "Solicite ao usuário que execute o fluxo de reconexão (Pluggy Connect) para renovar as credenciais.",
        "severidade": "atencao"
    },
    "CONSENT_REVOKED": {
        "titulo": "Consentimento Revogado",
        "explicacao": "O consentimento Open Finance foi cancelado pelo titular da conta ou pela instituição bancária.",
        "acao": "É necessário criar uma nova autorização de consentimento para retomar o compartilhamento de dados.",
        "severidade": "critica"
    },
    "CONSENT_EXPIRED": {
        "titulo": "Consentimento Expirado",
        "explicacao": "O prazo máximo de validade do consentimento Open Finance chegou ao fim.",
        "acao": "Solicite que o cliente autorize a renovação do consentimento pelo fluxo do Pluggy Connect.",
        "severidade": "atencao"
    },
    "LOGIN_ERROR": {
        "titulo": "Erro de Autenticação / Login",
        "explicacao": "Não foi possível autenticar junto à instituição com as credenciais ou autorizações fornecidas.",
        "acao": "Peça ao usuário para verificar suas credenciais bancárias e autorizar novamente o acesso.",
        "severidade": "alta"
    }
}

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
        "explicacao": "Não foi possível acessar a conta bancária. As credenciais falharam ou foram revogadas.",
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

    raw_cor = connector.get("primaryColor")
    if isinstance(raw_cor, str) and raw_cor.strip().startswith("#") and len(raw_cor.strip()) in (4, 7, 9):
        banco_cor = raw_cor.strip()
    else:
        banco_cor = "#0284C7"

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

    if isinstance(status_detail, dict) and status_detail:
        for k, v in status_detail.items():
            if isinstance(v, dict):
                p_nome = nomes_prod_pt.get(k, k.capitalize())
                p_is_up = v.get("isUpdated", False)
                p_last = formatar_data_hora_br(v.get("lastUpdatedAt"))
                p_warn = v.get("warnings")
                p_stat_str = "Sincronizado" if p_is_up else "Pendente / Não Atualizado"
                produtos_detalhe.append({
                    "chave": k,
                    "nome": p_nome,
                    "is_updated": p_is_up,
                    "status_str": p_stat_str,
                    "atualizado": p_last,
                    "warnings": p_warn
                })

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
        "erro_mensagem": erro_mensagem,
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
        "contas_vinculadas": contas_processadas
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
        self.after(40, self._processar_fila_ui)

        self.var_data_ini = MascaraDataVar()
        self.var_data_fim = MascaraDataVar()

        self._last_auto_searched_id = None
        self._last_diag_searched_id = None
        self._last_consent_searched_id = None
        self._debounce_timer = None

        self.carregar_config()
        self.configurar_estilos_treeview()
        self.criar_cabecalho()
        self.criar_corpo_principal()
        self.aplicar_mes(self.nav_year, self.nav_month)

        self.after(150, lambda: threading.Thread(target=self.obter_api_key, daemon=True).start())
        self.after(3000, lambda: threading.Thread(target=lambda: self.verificar_atualizacoes(silencioso=True), daemon=True).start())

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
                self.after(40, self._processar_fila_ui)
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
        self.frame_status_badge.pack(side=tk.LEFT, padx=(0, 12), ipady=2)

        self.lbl_header_status = ctk.CTkLabel(
            self.frame_status_badge,
            text="◌ Verificando conexão...",
            font=("Segoe UI", 11, "bold"),
            text_color="#F59E0B"
        )
        self.lbl_header_status.pack(padx=12, pady=2)

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

        self.setup_aba_transacoes()
        self.setup_aba_diagnostico()
        self.setup_aba_consentimento()

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
            width=260,
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

        lbl_empty_titulo = ctk.CTkLabel(
            self.frame_empty_tabela,
            text="Nenhum registro encontrado",
            font=("Segoe UI", 13, "bold"),
            text_color="#E2E8F0"
        )
        lbl_empty_titulo.pack(pady=(0, 2))

        lbl_empty_sub = ctk.CTkLabel(
            self.frame_empty_tabela,
            text="Nenhum registro encontrado, aguardando consulta ou filtros aplicados.",
            font=("Segoe UI", 10),
            text_color="#64748B"
        )
        lbl_empty_sub.pack()

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

        self.btn_consultar_diag = ctk.CTkButton(
            row1,
            text="Consultar Status",
            width=150,
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
        self.lbl_parecer_acao.pack(fill=tk.X, padx=12, pady=(0, 10))

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

        # 2. Card de Parecer & Solução
        self.card_diag_parecer.configure(border_color=info["status_border"])
        self.lbl_parecer_titulo.configure(text=info["resumo_titulo"], text_color=info["status_cor"])
        self.lbl_parecer_desc.configure(text=info["resumo_desc"])
        self.lbl_parecer_acao.configure(text=info["recomendacao"])

        # Detalhes técnicos
        if info["tem_erro"] and (info["erro_codigo"] or info["erro_mensagem"]):
            cod_str = f"Código do Erro: {info['erro_codigo'] or 'N/A'}"
            if info["erro_provider"]:
                cod_str += f" | Provider Code: {info['erro_provider']}"
            self.lbl_parecer_tecnico_cod.configure(text=cod_str)
            self.lbl_parecer_tecnico_msg.configure(text=f"Mensagem da API Pluggy: {info['erro_mensagem'] or 'Sem detalhes'}")
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

                is_up = p.get("is_updated", False)
                cor_p = "#10B981" if is_up else "#F59E0B"
                txt_p = p.get("status_str") or ("✓ Sincronizado" if is_up else "⚠ Pendente")
                badge_p = ctk.CTkFrame(c_right, fg_color="#1E293B", corner_radius=10, border_width=1, border_color=cor_p)
                badge_p.pack(side=tk.LEFT, padx=(0, 10), ipady=1)
                ctk.CTkLabel(badge_p, text=txt_p, font=("Segoe UI", 9, "bold"), text_color=cor_p).pack(padx=8, pady=1)

                if p.get("atualizado") and p.get("atualizado") != "N/A":
                    ctk.CTkLabel(c_right, text=f"Sync: {p['atualizado']}", font=("Segoe UI", 10), text_color="#64748B").pack(side=tk.LEFT)
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
        row1.pack(fill=tk.X, padx=16, pady=14)

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

        # 2. Card de Resumo de Situação e Metadados
        self.card_consent_status = ctk.CTkFrame(self.tab_consentimento, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        self.card_consent_status.pack(fill=tk.X, padx=8, pady=(0, 10))

        # Topo do card: Pill de Status + Título
        row_status_top = ctk.CTkFrame(self.card_consent_status, fg_color="transparent")
        row_status_top.pack(fill=tk.X, padx=16, pady=(12, 6))

        self.frame_pill_consent = ctk.CTkFrame(row_status_top, fg_color="#1E293B", corner_radius=14, border_width=1, border_color="#334155")
        self.frame_pill_consent.pack(side=tk.LEFT, padx=(0, 12), ipady=2)

        self.lbl_pill_consent = ctk.CTkLabel(
            self.frame_pill_consent,
            text="● AGUARDANDO CONSULTA",
            font=("Segoe UI", 11, "bold"),
            text_color="#F59E0B"
        )
        self.lbl_pill_consent.pack(padx=14, pady=2)

        self.lbl_consent_titulo = ctk.CTkLabel(
            row_status_top,
            text="Recurso de Consentimento Open Finance (GET /consents/{id})",
            font=("Segoe UI", 13, "bold"),
            text_color="#FFFFFF"
        )
        self.lbl_consent_titulo.pack(side=tk.LEFT)

        self.lbl_consent_detalhe = ctk.CTkLabel(
            self.card_consent_status,
            text="Informe o Consent ID ou Item ID acima e clique em 'Consultar Situação Atual'.",
            font=("Segoe UI", 11),
            text_color="#94A3B8",
            anchor="w"
        )
        self.lbl_consent_detalhe.pack(fill=tk.X, padx=16, pady=(0, 10))

        # Grid de Detalhes
        grid_info = ctk.CTkFrame(self.card_consent_status, fg_color="#0B0F19", corner_radius=8, border_width=1, border_color="#1F2937")
        grid_info.pack(fill=tk.X, padx=16, pady=(0, 12))
        grid_info.columnconfigure(0, weight=1)
        grid_info.columnconfigure(1, weight=1)

        # Coluna 1: IDs
        c1 = ctk.CTkFrame(grid_info, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="nsew", padx=12, pady=10)

        # Consent ID
        f_cid = ctk.CTkFrame(c1, fg_color="transparent")
        f_cid.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_cid, text="Consent ID:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=90, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_cid = ctk.CTkLabel(f_cid, text="-", font=("Consolas", 11), text_color="#38BDF8", anchor="w")
        self.lbl_val_cid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_copiar_cid = ctk.CTkButton(f_cid, text="Copiar", width=50, height=22, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(self.lbl_val_cid.cget("text"), self.btn_copiar_cid))
        self.btn_copiar_cid.pack(side=tk.RIGHT)

        # Item ID
        f_iid = ctk.CTkFrame(c1, fg_color="transparent")
        f_iid.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_iid, text="Item ID:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=90, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_itemid = ctk.CTkLabel(f_iid, text="-", font=("Consolas", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_itemid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_copiar_iid = ctk.CTkButton(f_iid, text="Copiar", width=50, height=22, font=("Segoe UI", 9), fg_color="#1E293B", hover_color="#334155", command=lambda: self.copiar_para_clipboard(self.lbl_val_itemid.cget("text"), self.btn_copiar_iid))
        self.btn_copiar_iid.pack(side=tk.RIGHT)

        # Coluna 2: Datas
        c2 = ctk.CTkFrame(grid_info, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="nsew", padx=12, pady=10)

        f_d1 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d1.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_d1, text="Criado em:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_created = ctk.CTkLabel(f_d1, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_created.pack(side=tk.LEFT)

        f_d2 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d2.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_d2, text="Expira em:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_expires = ctk.CTkLabel(f_d2, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_expires.pack(side=tk.LEFT)

        f_d3 = ctk.CTkFrame(c2, fg_color="transparent")
        f_d3.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(f_d3, text="Revogado em:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=95, anchor="w").pack(side=tk.LEFT)
        self.lbl_val_revoked = ctk.CTkLabel(f_d3, text="-", font=("Segoe UI", 11), text_color="#E2E8F0", anchor="w")
        self.lbl_val_revoked.pack(side=tk.LEFT)

        # 3. Badges (Produtos & Permissões)
        self.card_consent_badges = ctk.CTkFrame(self.tab_consentimento, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
        self.card_consent_badges.pack(fill=tk.X, padx=8, pady=(0, 10))

        # Produtos
        f_prod = ctk.CTkFrame(self.card_consent_badges, fg_color="transparent")
        f_prod.pack(fill=tk.X, padx=14, pady=(8, 4))
        ctk.CTkLabel(f_prod, text="Produtos Consentidos:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=160, anchor="w").pack(side=tk.LEFT)
        self.frame_chips_products = ctk.CTkFrame(f_prod, fg_color="transparent")
        self.frame_chips_products.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_empty_prod = ctk.CTkLabel(self.frame_chips_products, text="Nenhum produto carregado", font=("Segoe UI", 10, "italic"), text_color="#64748B")
        self.lbl_empty_prod.pack(side=tk.LEFT)

        # Permissões Open Finance
        f_perm = ctk.CTkFrame(self.card_consent_badges, fg_color="transparent")
        f_perm.pack(fill=tk.X, padx=14, pady=(4, 8))
        ctk.CTkLabel(f_perm, text="Permissões Concedidas:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8", width=160, anchor="w").pack(side=tk.LEFT)
        self.frame_chips_permissions = ctk.CTkFrame(f_perm, fg_color="transparent")
        self.frame_chips_permissions.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_empty_perm = ctk.CTkLabel(self.frame_chips_permissions, text="Nenhuma permissão carregada", font=("Segoe UI", 10, "italic"), text_color="#64748B")
        self.lbl_empty_perm.pack(side=tk.LEFT)

        # 4. JSON Viewer
        card_json = ctk.CTkFrame(self.tab_consentimento, fg_color="#07090E", corner_radius=10, border_width=1, border_color="#1F2937")
        card_json.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        bar_json = ctk.CTkFrame(card_json, height=36, fg_color="#0B0F19", corner_radius=8)
        bar_json.pack(fill=tk.X, padx=6, pady=(6, 2))

        ctk.CTkLabel(bar_json, text="JSON da Resposta:", font=("Segoe UI", 11, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=10)

        self.entry_busca_t3 = ctk.CTkEntry(bar_json, placeholder_text="Buscar no JSON...", width=160, height=26, font=("Consolas", 10), border_color="#1F2937")
        self.entry_busca_t3.pack(side=tk.LEFT, padx=(0, 4))
        self.entry_busca_t3.bind("<Return>", lambda e: self.acao_buscar_t3())

        btn_prev_j = ctk.CTkButton(bar_json, text="▲", width=26, height=26, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_anterior_json_t3)
        btn_prev_j.pack(side=tk.LEFT, padx=2)

        btn_next_j = ctk.CTkButton(bar_json, text="▼", width=26, height=26, fg_color="#1E293B", hover_color="#334155", font=("Segoe UI", 10), command=self.localizar_proximo_json_t3)
        btn_next_j.pack(side=tk.LEFT, padx=2)

        self.lbl_busca_status_t3 = ctk.CTkLabel(bar_json, text="", font=("Segoe UI", 10), text_color="#94A3B8")
        self.lbl_busca_status_t3.pack(side=tk.LEFT, padx=6)

        btn_copy_json = ctk.CTkButton(
            bar_json,
            text="Copiar JSON",
            width=90,
            height=26,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 10),
            command=lambda: self.copiar_para_clipboard(self.txt_json_t3.get("1.0", tk.END).strip())
        )
        btn_copy_json.pack(side=tk.RIGHT, padx=6)

        # Text + Scrollbars
        self.scroll_t3_y = ctk.CTkScrollbar(card_json, orientation="vertical", fg_color="#07090E", button_color="#1E293B", button_hover_color="#6366F1", corner_radius=6, width=12)
        self.scroll_t3_x = ctk.CTkScrollbar(card_json, orientation="horizontal", fg_color="#07090E", button_color="#1E293B", button_hover_color="#6366F1", corner_radius=6, height=12)

        self.txt_json_t3 = tk.Text(
            card_json,
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

    def popular_linhas_tabela(self, lista_filtrada=None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        dados = lista_filtrada if lista_filtrada is not None else self.current_transactions
        if not dados:
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

            self.raw_item_data = data

            def atualizar_ui_diag():
                status = data.get("status", "N/A")
                err_obj = data.get("error")
                last_up = formatar_data_hora_br(data.get("updatedAt") or data.get("lastUpdatedAt"))

                if err_obj:
                    code = err_obj.get("code", "ERRO")
                    msg = err_obj.get("message", "Sem detalhes")
                    self.lbl_diag_status.configure(text=f"Falha no Item: {status} [{code}]", text_color="#F43F5E")
                    self.lbl_diag_erro.configure(text=f"Mensagem: {msg} | Última tentativa: {last_up}")
                    self.card_diag_status.configure(border_color="#4C0519")
                else:
                    self.lbl_diag_status.configure(text=f"Status do Item: {status}", text_color="#10B981")
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
            return res.json()

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
        self.frame_pill_consent.configure(fg_color="#0C4A6E", border_color="#0284C7")
        self.lbl_consent_detalhe.configure(
            text="Aguarde o retorno da consulta do recurso de consentimento...",
            text_color="#94A3B8"
        )
        self.card_consent_status.configure(border_color="#0284C7")

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
                self.frame_pill_consent.configure(fg_color="#4C0519", border_color="#881337")
                self.lbl_consent_detalhe.configure(text=str(e), text_color="#F43F5E")
                self.card_consent_status.configure(border_color="#881337")
                messagebox.showerror("Erro ao Consultar Situação", str(e), parent=self)
            self.safe_after(0, on_err)

    def _atualizar_ui_consentimento_tab3(self, data):
        info = analisar_situacao_consentimento(data)
        if not info:
            return

        self.lbl_val_cid.configure(text=info["id"])
        self.lbl_val_itemid.configure(text=info["item_id"])
        self.lbl_val_created.configure(text=info["created_str"])
        self.lbl_val_expires.configure(text=info["expires_str"])
        self.lbl_val_revoked.configure(text=info["revoked_str"])

        self.lbl_pill_consent.configure(text=f"● {info['status_titulo']}", text_color=info["cor_status"])
        self.frame_pill_consent.configure(fg_color=info["cor_bg"], border_color=info["cor_border"])
        self.lbl_consent_detalhe.configure(text=info["detalhe"], text_color=info["cor_status"])
        self.card_consent_status.configure(border_color=info["cor_border"])

        # Renderizar chips de produtos
        for widget in self.frame_chips_products.winfo_children():
            widget.destroy()

        products = info.get("products", [])
        if products:
            for p in products:
                chip = ctk.CTkLabel(
                    self.frame_chips_products,
                    text=f" {p} ",
                    fg_color="#1E293B",
                    corner_radius=6,
                    font=("Segoe UI", 10, "bold"),
                    text_color="#38BDF8"
                )
                chip.pack(side=tk.LEFT, padx=3, pady=2)
        else:
            ctk.CTkLabel(self.frame_chips_products, text="Nenhum produto listado", font=("Segoe UI", 10, "italic"), text_color="#64748B").pack(side=tk.LEFT)

        # Renderizar chips de permissões
        for widget in self.frame_chips_permissions.winfo_children():
            widget.destroy()

        permissions = info.get("permissions", [])
        if permissions:
            for perm in permissions[:8]:
                chip = ctk.CTkLabel(
                    self.frame_chips_permissions,
                    text=f" {perm} ",
                    fg_color="#1E293B",
                    corner_radius=6,
                    font=("Segoe UI", 9),
                    text_color="#A7F3D0"
                )
                chip.pack(side=tk.LEFT, padx=2, pady=2)
            if len(permissions) > 8:
                ctk.CTkLabel(self.frame_chips_permissions, text=f"+{len(permissions)-8} mais", font=("Segoe UI", 9, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=3)
        else:
            ctk.CTkLabel(self.frame_chips_permissions, text="Nenhuma permissão listada", font=("Segoe UI", 10, "italic"), text_color="#64748B").pack(side=tk.LEFT)

        self.renderizar_json_texto(self.txt_json_t3, data)

    def abrir_janela_situacao_consentimento(self, data):
        info = analisar_situacao_consentimento(data)
        if not info:
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Situação Atual do Consentimento - Pluggy Open Finance")
        janela.geometry("760x700")
        janela.minsize(680, 560)
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

        lbl_desc = ctk.CTkLabel(
            card_destaque,
            text=info["detalhe"],
            font=("Segoe UI", 12),
            text_color="#E2E8F0",
            wraplength=680,
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
        ctk.CTkLabel(r3, text=f"Revogado em: {info['revoked_str']}", font=("Segoe UI", 11), text_color="#94A3B8").pack(side=tk.LEFT)

        # 3. Badges de Produtos e Permissões
        if info["products"] or info["permissions"]:
            card_p = ctk.CTkFrame(main_frame, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1F2937")
            card_p.pack(fill=tk.X, pady=(0, 10))

            if info["products"]:
                f_p = ctk.CTkFrame(card_p, fg_color="transparent")
                f_p.pack(fill=tk.X, padx=14, pady=6)
                ctk.CTkLabel(f_p, text="Produtos:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=80, anchor="w").pack(side=tk.LEFT)
                for prod in info["products"]:
                    ctk.CTkLabel(f_p, text=f" {prod} ", fg_color="#1E293B", text_color="#38BDF8", corner_radius=6, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=3)

            if info["permissions"]:
                f_perm = ctk.CTkFrame(card_p, fg_color="transparent")
                f_perm.pack(fill=tk.X, padx=14, pady=(2, 8))
                ctk.CTkLabel(f_perm, text="Permissões:", font=("Segoe UI", 11, "bold"), text_color="#64748B", width=80, anchor="w").pack(side=tk.LEFT)
                for perm in info["permissions"][:6]:
                    ctk.CTkLabel(f_perm, text=f" {perm} ", fg_color="#1E293B", text_color="#A7F3D0", corner_radius=6, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
                if len(info["permissions"]) > 6:
                    ctk.CTkLabel(f_perm, text=f"+{len(info['permissions'])-6}", font=("Segoe UI", 9, "bold"), text_color="#94A3B8").pack(side=tk.LEFT, padx=2)

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
        janela.geometry("540x360")
        janela.transient(self)

        lbl_t = ctk.CTkLabel(janela, text="Credenciais Pluggy Open Finance", font=("Segoe UI", 14, "bold"))
        lbl_t.pack(padx=20, pady=(20, 4), anchor="w")

        lbl_desc = ctk.CTkLabel(janela, text="Suas credenciais são salvas localmente em config.json.", font=("Segoe UI", 11), text_color="#9CA3AF")
        lbl_desc.pack(padx=20, pady=(0, 16), anchor="w")

        lbl_cid = ctk.CTkLabel(janela, text="Client ID:", font=("Segoe UI", 11, "bold"))
        lbl_cid.pack(padx=20, anchor="w")

        entry_cid = ctk.CTkEntry(janela, width=500, height=36, font=("Consolas", 11), border_color="#1F2937")
        entry_cid.insert(0, self.client_id)
        entry_cid.pack(padx=20, pady=(2, 12))

        lbl_sec = ctk.CTkLabel(janela, text="Client Secret:", font=("Segoe UI", 11, "bold"))
        lbl_sec.pack(padx=20, anchor="w")

        entry_sec = ctk.CTkEntry(janela, width=500, height=36, show="•", font=("Consolas", 11), border_color="#1F2937")
        entry_sec.insert(0, self.client_secret)
        entry_sec.pack(padx=20, pady=(2, 20))

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
        btn_salvar.pack(padx=20, pady=8, fill=tk.X)

        # Seção de Versão e Atualização
        sep_update = ctk.CTkFrame(janela, height=1, fg_color="#1F2937")
        sep_update.pack(fill=tk.X, padx=20, pady=(16, 12))

        frame_ver = ctk.CTkFrame(janela, fg_color="transparent")
        frame_ver.pack(fill=tk.X, padx=20, pady=(0, 10))

        lbl_versao = ctk.CTkLabel(frame_ver, text=f"Versão Instalada: v{APP_VERSION}", font=("Segoe UI", 11), text_color="#94A3B8")
        lbl_versao.pack(side=tk.LEFT)

        btn_verif_update = ctk.CTkButton(
            frame_ver,
            text="🔄 Verificar Atualizações",
            width=175,
            height=32,
            fg_color="#1E293B",
            hover_color="#334155",
            font=("Segoe UI", 11, "bold"),
            border_width=1,
            border_color="#334155",
            command=lambda: threading.Thread(target=lambda: self.verificar_atualizacoes(silencioso=False), daemon=True).start()
        )
        btn_verif_update.pack(side=tk.RIGHT)

    def verificar_atualizacoes(self, silencioso=False):
        """Verifica se há novas versões disponíveis no GitHub Releases"""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "PluggyExplorer"}
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                rel = res.json()
                tag_raw = rel.get("tag_name", "")
                tag_clean = tag_raw.lstrip("vV")

                def extrair_versao(v_str):
                    parts = re.findall(r'\d+', v_str)
                    return tuple(int(p) for p in parts) if parts else (0,)

                ver_remota = extrair_versao(tag_clean)
                ver_local = extrair_versao(APP_VERSION)

                if ver_remota > ver_local:
                    assets = rel.get("assets", [])
                    exe_url = None
                    for a in assets:
                        if a.get("name", "").lower().endswith(".exe"):
                            exe_url = a.get("browser_download_url")
                            break
                    corpo_notas = rel.get("body", "Melhorias de desempenho e estabilidade.")
                    html_url = rel.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"

                    def perguntar():
                        msg = (
                            f"Uma nova versão (v{tag_clean}) do Pluggy Explorer está disponível!\n\n"
                            f"Versão atual instalada: v{APP_VERSION}\n"
                            f"Nova versão encontrada: v{tag_clean}\n\n"
                            f"Notas da versão:\n{corpo_notas[:300]}\n\n"
                            f"Deseja atualizar automaticamente agora?"
                        )
                        if messagebox.askyesno("Atualização Encontrada", msg, parent=self):
                            if getattr(sys, 'frozen', False) and exe_url:
                                self.baixar_e_instalar_atualizacao(exe_url, tag_clean)
                            else:
                                webbrowser.open(html_url)

                    self.safe_after(0, perguntar)
                elif not silencioso:
                    self.safe_after(0, lambda: messagebox.showinfo(
                        "Atualizações",
                        f"O Pluggy Explorer já está atualizado!\nVersão instalada: v{APP_VERSION}",
                        parent=self
                    ))
            elif not silencioso:
                self.safe_after(0, lambda: messagebox.showinfo(
                    "Atualizações",
                    f"Versão atual: v{APP_VERSION}.\nNenhuma atualização disponível no momento.",
                    parent=self
                ))
        except Exception as e:
            if not silencioso:
                self.safe_after(0, lambda err=str(e): messagebox.showwarning(
                    "Verificação de Atualização",
                    f"Não foi possível verificar atualizações no momento:\n{err}",
                    parent=self
                ))

    def baixar_e_instalar_atualizacao(self, download_url, versao_tag):
        """Baixa o novo executável e executa a substituição suave"""
        prog_win = ctk.CTkToplevel(self)
        prog_win.title("Baixando Atualização...")
        prog_win.geometry("400x160")
        prog_win.transient(self)
        prog_win.grab_set()

        lbl = ctk.CTkLabel(prog_win, text=f"Baixando nova versão v{versao_tag}...", font=("Segoe UI", 12, "bold"))
        lbl.pack(pady=(20, 10))

        bar = ctk.CTkProgressBar(prog_win, width=320)
        bar.set(0)
        bar.pack(pady=10)

        lbl_status = ctk.CTkLabel(prog_win, text="Iniciando download...", font=("Segoe UI", 10), text_color="#94A3B8")
        lbl_status.pack()

        def worker():
            try:
                exe_path = sys.executable
                exe_dir = os.path.dirname(os.path.abspath(exe_path))
                temp_exe = os.path.join(exe_dir, "PluggyExplorer_new.exe")
                bat_path = os.path.join(exe_dir, "aplicar_update.bat")

                res = requests.get(download_url, stream=True, timeout=60)
                res.raise_for_status()
                total_size = int(res.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_exe, "wb") as f:
                    for chunk in res.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                frac = downloaded / total_size
                                self.safe_after(0, lambda p=frac: bar.set(p))
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                self.safe_after(0, lambda s=f"{mb_down:.1f} MB / {mb_tot:.1f} MB": lbl_status.configure(text=s))

                bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
:loop
del /f /q "{exe_path}" > nul 2>&1
if exist "{exe_path}" (
    timeout /t 1 /nobreak > nul
    goto loop
)
move /y "{temp_exe}" "{exe_path}" > nul
start "" "{exe_path}"
del "%~f0"
exit
"""
                with open(bat_path, "w", encoding="utf-8") as f_bat:
                    f_bat.write(bat_content)

                import subprocess
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
                subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=flags)

                self.safe_after(0, self.destroy)
                sys.exit(0)
            except Exception as e:
                self.safe_after(0, lambda err=str(e): messagebox.showerror(
                    "Erro ao Atualizar",
                    f"Falha durante o download da atualização:\n{err}",
                    parent=self
                ))
                self.safe_after(0, prog_win.destroy)

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = ModernPluggyApp()
    app.mainloop()
