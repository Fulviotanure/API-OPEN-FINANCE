import json
import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import requests

# ==========================================
# CREDENCIAIS OCULTAS (FIXAS NO CÓDIGO)
# ==========================================
CLIENT_ID = ""
CLIENT_SECRET = ""
BASE_URL = "https://api.pluggy.ai"


class PluggyApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Pluggy API Explorer & Diagnostics")
        self.root.geometry("1050x830")
        self.root.minsize(900, 650)

        self.api_key = None
        self.contas_map = {}

        # Variáveis de Navegação de Busca - Aba 1
        self.matches_t1 = []
        self.current_match_t1 = -1

        # Variáveis de Navegação de Busca - Aba 2
        self.matches_t2 = []
        self.current_match_t2 = -1

        # ----------------------------------------------------
        # ESTILO E TEMAS (Dark Theme - Fundo Preto/Escuro)
        # ----------------------------------------------------
        self.bg_dark = "#0B0E14"
        self.card_bg = "#12171F"
        self.border_color = "#232A35"
        self.text_light = "#E6EDE3"
        self.accent_pink = "#FF3366"
        self.accent_hover = "#E02B55"
        self.json_bg = "#05070A"
        self.entry_bg = "#1A202C"

        self.root.configure(bg=self.bg_dark)

        style = ttk.Style()
        style.theme_use("clam")

        # Styles
        style.configure("TFrame", background=self.bg_dark)
        style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        style.configure("TLabelframe", background=self.card_bg, foreground="#8B949E", bordercolor=self.border_color)
        style.configure("TLabelframe.Label", background=self.card_bg, foreground="#58A6FF", font=("Segoe UI", 10, "bold"))
        
        style.configure("TLabel", background=self.card_bg, foreground=self.text_light, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=self.bg_dark, foreground="#FFFFFF", font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel", background=self.card_bg, foreground="#FFD700", font=("Segoe UI", 10, "bold"))

        style.configure("TEntry", fieldbackground=self.entry_bg, foreground="#FFFFFF", bordercolor=self.border_color, insertcolor="#FFFFFF")
        
        # Estilo do Combobox
        style.configure("TCombobox", fieldbackground=self.entry_bg, background=self.card_bg, foreground="#FFFFFF", bordercolor=self.border_color, arrowcolor="#FFFFFF")
        style.map("TCombobox", 
                  fieldbackground=[("readonly", self.entry_bg), ("focus", self.entry_bg)],
                  foreground=[("readonly", "#FFFFFF"), ("focus", "#FFFFFF")],
                  selectbackground=[("readonly", "#2D3748")],
                  selectforeground=[("readonly", "#FFFFFF")])

        self.root.option_add("*TCombobox*Listbox.background", self.entry_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", "#FFFFFF")
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.accent_pink)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

        # Estilo das Abas (Notebook)
        style.configure("TNotebook", background=self.bg_dark, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.card_bg, foreground="#8B949E", padding=[15, 8], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", 
                  background=[("selected", self.accent_pink), ("active", "#2D3748")],
                  foreground=[("selected", "#FFFFFF"), ("active", "#FFFFFF")])

        # Botões
        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), background=self.accent_pink, foreground="#FFFFFF", borderwidth=0, focuscolor="none")
        style.map("Action.TButton", background=[("active", self.accent_hover), ("pressed", self.accent_hover)])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), background=self.entry_bg, foreground=self.text_light, bordercolor=self.border_color)
        style.map("Secondary.TButton", background=[("active", "#2D3748")])

        # Container Principal
        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Cabeçalho com Botão de Chave Manual
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        header_label = ttk.Label(header_frame, text="⚡ Pluggy API Explorer & Diagnostics", style="Header.TLabel")
        header_label.pack(side=tk.LEFT)

        btn_key = ttk.Button(header_frame, text="🔑 Renovar API Key", style="Secondary.TButton", command=self.acao_renovar_key_manual)
        btn_key.pack(side=tk.RIGHT)

        self.lbl_key_status = ttk.Label(header_frame, text="API Key: Não gerada", font=("Segoe UI", 8), foreground="#8B949E", background=self.bg_dark)
        self.lbl_key_status.pack(side=tk.RIGHT, padx=10)

        # Estrutura de Abas
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Criar as abas
        self.tab1 = ttk.Frame(self.notebook, padding="10")
        self.tab2 = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.tab1, text="  💳 Explorer de Transações  ")
        self.notebook.add(self.tab2, text="  🚨 Diagnóstico de Item (Erros)  ")

        # Construir conteúdo das abas
        self._setup_tab1()
        self._setup_tab2()

        # Shortcuts
        self.root.bind("<Control-f>", lambda e: self.focar_busca())
        self.root.bind("<Control-F>", lambda e: self.focar_busca())

    # ==========================================
    # GERENCIAMENTO DE API KEY (COM REUSO E AUTO-REFRESH)
    # ==========================================
    def obter_api_key(self, force_refresh=False):
        """Obtém uma chave existente ou solicita uma nova apenas se necessário"""
        if self.api_key and not force_refresh:
            return True

        url = f"{BASE_URL}/auth"
        payload = {"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET}
        headers = {"accept": "application/json", "content-type": "application/json"}

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            res.raise_for_status()
            self.api_key = res.json().get("apiKey")
            
            def atualizar_status_key():
                self.lbl_key_status.config(text="API Key: Ativa ✅", foreground="#3FB950")
            self.root.after(0, atualizar_status_key)
            
            return True
        except Exception as e:
            self.api_key = None
            def falha_key():
                self.lbl_key_status.config(text="API Key: Falhou ❌", foreground="#FF6B6B")
                messagebox.showerror("Erro de Autenticação", f"Falha ao gerar API Key:\n{str(e)}")
            self.root.after(0, falha_key)
            return False

    def acao_renovar_key_manual(self):
        def worker():
            if self.obter_api_key(force_refresh=True):
                self.root.after(0, lambda: messagebox.showinfo("Sucesso", "API Key renovada com sucesso!"))
        threading.Thread(target=worker, daemon=True).start()

    # ==========================================
    # ABA 1: EXPLORER DE TRANSAÇÕES
    # ==========================================
    def _setup_tab1(self):
        controls_frame = ttk.LabelFrame(self.tab1, text=" Parâmetros de Requisição ", padding="12")
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls_frame, text="Item ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_item_id_t1 = ttk.Entry(controls_frame, width=38)
        self.entry_item_id_t1.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.btn_buscar_contas = ttk.Button(controls_frame, text="1. Buscar Contas", style="Action.TButton", command=self.acao_buscar_contas)
        self.btn_buscar_contas.grid(row=0, column=2, padx=10, pady=5, sticky=tk.W)

        ttk.Label(controls_frame, text="Conta:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.combo_contas = ttk.Combobox(controls_frame, width=55, state="readonly")
        self.combo_contas.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(controls_frame, text="Data Inicial (AAAA-MM-DD):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_date_from = ttk.Entry(controls_frame, width=18)
        self.entry_date_from.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        date_to_frame = ttk.Frame(controls_frame, style="Card.TFrame")
        date_to_frame.grid(row=2, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(date_to_frame, text="Data Final:").pack(side=tk.LEFT, padx=(5, 5))
        self.entry_date_to = ttk.Entry(date_to_frame, width=15)
        self.entry_date_to.pack(side=tk.LEFT)

        self.btn_buscar_transacoes = ttk.Button(controls_frame, text="2. Ver Transações", style="Action.TButton", command=self.acao_buscar_transacoes)
        self.btn_buscar_transacoes.grid(row=3, column=0, columnspan=3, pady=(10, 5), sticky=tk.EW)

        # Output JSON Tab 1
        frame_output = ttk.LabelFrame(self.tab1, text=" Resposta da API (JSON) ", padding="10")
        frame_output.pack(fill=tk.BOTH, expand=True)

        search_frame = ttk.Frame(frame_output, style="Card.TFrame")
        search_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(search_frame, text="🔍 Buscar (Ctrl+F):").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_search_t1 = ttk.Entry(search_frame, width=25)
        self.entry_search_t1.pack(side=tk.LEFT, padx=5)
        self.entry_search_t1.bind("<Return>", lambda e: self.localizar_proximo_t1())

        ttk.Button(search_frame, text="Buscar", style="Secondary.TButton", command=self.executar_busca_t1).pack(side=tk.LEFT, padx=2)
        
        self.btn_prev_t1 = ttk.Button(search_frame, text="▲ Anterior", style="Secondary.TButton", command=self.localizar_anterior_t1, state="disabled")
        self.btn_prev_t1.pack(side=tk.LEFT, padx=(10, 2))

        self.btn_next_t1 = ttk.Button(search_frame, text="▼ Próximo", style="Secondary.TButton", command=self.localizar_proximo_t1, state="disabled")
        self.btn_next_t1.pack(side=tk.LEFT, padx=2)

        self.lbl_status_t1 = ttk.Label(search_frame, text="", foreground="#8B949E")
        self.lbl_status_t1.pack(side=tk.LEFT, padx=10)

        self.txt_output_t1 = self._criar_text_area(frame_output)

    # ==========================================
    # ABA 2: DIAGNÓSTICO DE ITEM
    # ==========================================
    def _setup_tab2(self):
        controls_frame = ttk.LabelFrame(self.tab2, text=" Consultar Status do Item / Erros ", padding="12")
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls_frame, text="Item ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_item_id_t2 = ttk.Entry(controls_frame, width=45)
        self.entry_item_id_t2.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.btn_diagnosticar = ttk.Button(controls_frame, text="🔍 Consultar Status do Item", style="Action.TButton", command=self.acao_diagnosticar_item)
        self.btn_diagnosticar.grid(row=0, column=2, padx=10, pady=5, sticky=tk.W)

        # Painel Rápido de Resumo do Erro
        summary_frame = ttk.Frame(controls_frame, style="Card.TFrame")
        summary_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))

        self.lbl_item_status = ttk.Label(summary_frame, text="Status: -", style="Status.TLabel")
        self.lbl_item_status.pack(anchor=tk.W, padx=10, pady=2)

        self.lbl_item_error = ttk.Label(summary_frame, text="Erro Detalhado: -", foreground="#FF6B6B", font=("Segoe UI", 9, "bold"))
        self.lbl_item_error.pack(anchor=tk.W, padx=10, pady=2)

        # Output JSON Tab 2
        frame_output = ttk.LabelFrame(self.tab2, text=" Resposta Completa do Item (JSON) ", padding="10")
        frame_output.pack(fill=tk.BOTH, expand=True)

        search_frame = ttk.Frame(frame_output, style="Card.TFrame")
        search_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(search_frame, text="🔍 Buscar (Ctrl+F):").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_search_t2 = ttk.Entry(search_frame, width=25)
        self.entry_search_t2.pack(side=tk.LEFT, padx=5)
        self.entry_search_t2.bind("<Return>", lambda e: self.localizar_proximo_t2())

        ttk.Button(search_frame, text="Buscar", style="Secondary.TButton", command=self.executar_busca_t2).pack(side=tk.LEFT, padx=2)

        self.btn_prev_t2 = ttk.Button(search_frame, text="▲ Anterior", style="Secondary.TButton", command=self.localizar_anterior_t2, state="disabled")
        self.btn_prev_t2.pack(side=tk.LEFT, padx=(10, 2))

        self.btn_next_t2 = ttk.Button(search_frame, text="▼ Próximo", style="Secondary.TButton", command=self.localizar_proximo_t2, state="disabled")
        self.btn_next_t2.pack(side=tk.LEFT, padx=2)

        self.lbl_status_t2 = ttk.Label(search_frame, text="", foreground="#8B949E")
        self.lbl_status_t2.pack(side=tk.LEFT, padx=10)

        self.txt_output_t2 = self._criar_text_area(frame_output)

    # ----------------------------------------------------
    # AUXILIARES DE COMPONENTES
    # ----------------------------------------------------
    def _criar_text_area(self, parent):
        txt_container = ttk.Frame(parent, style="Card.TFrame")
        txt_container.pack(fill=tk.BOTH, expand=True)

        txt = tk.Text(
            txt_container, wrap=tk.NONE, font=("Consolas", 10), bg=self.json_bg,
            fg="#D4D4D4", insertbackground="#FFFFFF", selectbackground="#264F78",
            selectforeground="#FFFFFF", bd=1, relief="solid"
        )
        
        scroll_y = ttk.Scrollbar(txt_container, orient=tk.VERTICAL, command=txt.yview)
        scroll_x = ttk.Scrollbar(txt_container, orient=tk.HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(fill=tk.BOTH, expand=True)

        txt.tag_configure("key", foreground="#9CDCFE")
        txt.tag_configure("string", foreground="#CE9178")
        txt.tag_configure("number", foreground="#B5CEA8")
        txt.tag_configure("boolean", foreground="#569CD6")
        txt.tag_configure("highlight", background="#4A3B00", foreground="#FFFFFF")
        txt.tag_configure("current_highlight", background="#FF9900", foreground="#000000")

        return txt

    def focar_busca(self):
        tab_ativa = self.notebook.index("current")
        if tab_ativa == 0:
            self.entry_search_t1.focus_set()
            self.entry_search_t1.selection_range(0, tk.END)
        else:
            self.entry_search_t2.focus_set()
            self.entry_search_t2.selection_range(0, tk.END)

    # ----------------------------------------------------
    # LÓGICA DA ABA 1 (CONTAS E TRANSAÇÕES)
    # ----------------------------------------------------
    def acao_buscar_contas(self):
        item_id = self.entry_item_id_t1.get().strip()
        if not item_id:
            messagebox.showwarning("Aviso", "Por favor, insira o Item ID.")
            return

        self.txt_output_t1.delete("1.0", tk.END)
        self.txt_output_t1.insert(tk.END, "⏳ Buscando contas...")
        threading.Thread(target=self._worker_buscar_contas, args=(item_id,), daemon=True).start()

    def _worker_buscar_contas(self, item_id, retry=True):
        if not self.obter_api_key():
            return

        url = f"{BASE_URL}/accounts"
        params = {"itemId": item_id}
        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=20)
            
            # Se der 401 (token expirado), tenta renovar uma vez automaticamente
            if res.status_code == 401 and retry:
                if self.obter_api_key(force_refresh=True):
                    self._worker_buscar_contas(item_id, retry=False)
                return

            res.raise_for_status()
            data = res.json()

            results = data.get("results", [])
            combo_values = []
            contas_temp = {}

            for acc in results:
                acc_id = acc.get("id")
                acc_name = acc.get("name") or acc.get("number") or acc.get("type", "Conta")
                label = f"{acc_name} - ({acc_id})"
                contas_temp[label] = acc_id
                combo_values.append(label)

            def atualizar_ui():
                self.contas_map = contas_temp
                self.combo_contas["values"] = combo_values
                if combo_values:
                    self.combo_contas.current(0)
                self.exibir_json_otimizado(self.txt_output_t1, data, 1)

            self.root.after(0, atualizar_ui)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao buscar contas:\n{str(e)}"))

    def acao_buscar_transacoes(self):
        selecionado = self.combo_contas.get()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma conta na lista.")
            return

        account_id = self.contas_map.get(selecionado)
        date_from = self.entry_date_from.get().strip()
        date_to = self.entry_date_to.get().strip()

        self.txt_output_t1.delete("1.0", tk.END)
        self.txt_output_t1.insert(tk.END, "⏳ Carregando transações da API...")
        threading.Thread(target=self._worker_buscar_transacoes, args=(account_id, date_from, date_to), daemon=True).start()

    def _worker_buscar_transacoes(self, account_id, date_from, date_to, retry=True):
        url = f"{BASE_URL}/v2/transactions"
        params = {"accountId": account_id}
        if date_from: params["dateFrom"] = date_from
        if date_to: params["dateTo"] = date_to

        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=25)

            if res.status_code == 401 and retry:
                if self.obter_api_key(force_refresh=True):
                    self._worker_buscar_transacoes(account_id, date_from, date_to, retry=False)
                return

            res.raise_for_status()
            data = res.json()
            self.root.after(0, lambda: self.exibir_json_otimizado(self.txt_output_t1, data, 1))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao buscar transações:\n{str(e)}"))

    # ----------------------------------------------------
    # LÓGICA DA ABA 2 (DIAGNÓSTICO DE ITEM)
    # ----------------------------------------------------
    def acao_diagnosticar_item(self):
        item_id = self.entry_item_id_t2.get().strip()
        if not item_id:
            messagebox.showwarning("Aviso", "Por favor, insira o Item ID para diagnóstico.")
            return

        self.lbl_item_status.config(text="Status: Consultando API...")
        self.lbl_item_error.config(text="Erro Detalhado: -")
        self.txt_output_t2.delete("1.0", tk.END)
        self.txt_output_t2.insert(tk.END, "⏳ Consultando dados do Item...")

        threading.Thread(target=self._worker_diagnosticar_item, args=(item_id,), daemon=True).start()

    def _worker_diagnosticar_item(self, item_id, retry=True):
        if not self.obter_api_key():
            return

        url = f"{BASE_URL}/items/{item_id}"
        headers = {"accept": "application/json", "X-API-KEY": self.api_key}

        try:
            res = requests.get(url, headers=headers, timeout=20)

            if res.status_code == 401 and retry:
                if self.obter_api_key(force_refresh=True):
                    self._worker_diagnosticar_item(item_id, retry=False)
                return

            data = res.json()

            def atualizar_ui_diag():
                status = data.get("status", "N/A")
                error_obj = data.get("error")
                
                if error_obj:
                    err_code = error_obj.get("code", "DESCONHECIDO")
                    err_msg = error_obj.get("message", "Sem mensagem")
                    err_text = f"🚨 [{err_code}] {err_msg}"
                else:
                    err_text = "✅ Nenhum erro reportado no item."

                self.lbl_item_status.config(text=f"Status do Item: {status}")
                self.lbl_item_error.config(text=f"Resultado: {err_text}")
                
                self.exibir_json_otimizado(self.txt_output_t2, data, 2)

            self.root.after(0, atualizar_ui_diag)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro no Diagnóstico", f"Falha na requisição:\n{str(e)}"))

    # ----------------------------------------------------
    # COLORÇÃO E RENDERIZAÇÃO
    # ----------------------------------------------------
    def exibir_json_otimizado(self, txt_widget, data, aba):
        txt_widget.delete("1.0", tk.END)
        if aba == 1: self.limpar_busca_t1()
        else: self.limpar_busca_t2()

        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        txt_widget.insert(tk.END, json_str)

        lines = json_str.splitlines()

        regex_key = re.compile(r'^\s*("([^"\\]|\\.)*")\s*:')
        regex_string = re.compile(r':\s*("([^"\\]|\\.)*")')
        regex_number = re.compile(r':\s*(-?\d+(\.\d+)?([eE][+-]?\d+)?)')
        regex_bool = re.compile(r':\s*(true|false|null)')

        def colorir_lote(inicio_linha):
            fim_linha = min(inicio_linha + 200, len(lines))

            for line_num in range(inicio_linha, fim_linha):
                line = lines[line_num]
                idx = line_num + 1

                m_key = regex_key.search(line)
                if m_key: txt_widget.tag_add("key", f"{idx}.{m_key.span(1)[0]}", f"{idx}.{m_key.span(1)[1]}")

                m_str = regex_string.search(line)
                if m_str: txt_widget.tag_add("string", f"{idx}.{m_str.span(1)[0]}", f"{idx}.{m_str.span(1)[1]}")

                m_num = regex_number.search(line)
                if m_num: txt_widget.tag_add("number", f"{idx}.{m_num.span(1)[0]}", f"{idx}.{m_num.span(1)[1]}")

                m_bool = regex_bool.search(line)
                if m_bool: txt_widget.tag_add("boolean", f"{idx}.{m_bool.span(1)[0]}", f"{idx}.{m_bool.span(1)[1]}")

            if fim_linha < len(lines):
                self.root.after(10, lambda: colorir_lote(fim_linha))

        colorir_lote(0)

    # ----------------------------------------------------
    # NAVEGAÇÃO DE BUSCA - ABA 1
    # ----------------------------------------------------
    def limpar_busca_t1(self):
        self.txt_output_t1.tag_remove("highlight", "1.0", tk.END)
        self.txt_output_t1.tag_remove("current_highlight", "1.0", tk.END)
        self.matches_t1.clear()
        self.current_match_t1 = -1
        self.lbl_status_t1.config(text="")
        self.btn_prev_t1.config(state="disabled")
        self.btn_next_t1.config(state="disabled")

    def executar_busca_t1(self):
        self.limpar_busca_t1()
        query = self.entry_search_t1.get().strip()
        if not query: return

        pos = "1.0"
        while True:
            pos = self.txt_output_t1.search(query, pos, stopindex=tk.END, nocase=True)
            if not pos: break
            end_pos = f"{pos} + {len(query)} chars"
            self.matches_t1.append((pos, end_pos))
            self.txt_output_t1.tag_add("highlight", pos, end_pos)
            pos = end_pos

        if self.matches_t1:
            self.current_match_t1 = 0
            self.btn_prev_t1.config(state="normal")
            self.btn_next_t1.config(state="normal")
            self.atualizar_foco_t1()
        else:
            self.lbl_status_t1.config(text="Nenhum resultado")

    def localizar_proximo_t1(self):
        if not self.matches_t1: self.executar_busca_t1(); return
        self.current_match_t1 = (self.current_match_t1 + 1) % len(self.matches_t1)
        self.atualizar_foco_t1()

    def localizar_anterior_t1(self):
        if not self.matches_t1: return
        self.current_match_t1 = (self.current_match_t1 - 1) % len(self.matches_t1)
        self.atualizar_foco_t1()

    def atualizar_foco_t1(self):
        self.txt_output_t1.tag_remove("current_highlight", "1.0", tk.END)
        pos_start, pos_end = self.matches_t1[self.current_match_t1]
        self.txt_output_t1.tag_add("current_highlight", pos_start, pos_end)
        self.txt_output_t1.see(pos_start)
        self.lbl_status_t1.config(text=f"{self.current_match_t1 + 1} de {len(self.matches_t1)} ocorrência(s)")

    # ----------------------------------------------------
    # NAVEGAÇÃO DE BUSCA - ABA 2
    # ----------------------------------------------------
    def limpar_busca_t2(self):
        self.txt_output_t2.tag_remove("highlight", "1.0", tk.END)
        self.txt_output_t2.tag_remove("current_highlight", "1.0", tk.END)
        self.matches_t2.clear()
        self.current_match_t2 = -1
        self.lbl_status_t2.config(text="")
        self.btn_prev_t2.config(state="disabled")
        self.btn_next_t2.config(state="disabled")

    def executar_busca_t2(self):
        self.limpar_busca_t2()
        query = self.entry_search_t2.get().strip()
        if not query: return

        pos = "1.0"
        while True:
            pos = self.txt_output_t2.search(query, pos, stopindex=tk.END, nocase=True)
            if not pos: break
            end_pos = f"{pos} + {len(query)} chars"
            self.matches_t2.append((pos, end_pos))
            self.txt_output_t2.tag_add("highlight", pos, end_pos)
            pos = end_pos

        if self.matches_t2:
            self.current_match_t2 = 0
            self.btn_prev_t2.config(state="normal")
            self.btn_next_t2.config(state="normal")
            self.atualizar_foco_t2()
        else:
            self.lbl_status_t2.config(text="Nenhum resultado")

    def localizar_proximo_t2(self):
        if not self.matches_t2: self.executar_busca_t2(); return
        self.current_match_t2 = (self.current_match_t2 + 1) % len(self.matches_t2)
        self.atualizar_foco_t2()

    def localizar_anterior_t2(self):
        if not self.matches_t2: return
        self.current_match_t2 = (self.current_match_t2 - 1) % len(self.matches_t2)
        self.atualizar_foco_t2()

    def atualizar_foco_t2(self):
        self.txt_output_t2.tag_remove("current_highlight", "1.0", tk.END)
        pos_start, pos_end = self.matches_t2[self.current_match_t2]
        self.txt_output_t2.tag_add("current_highlight", pos_start, pos_end)
        self.txt_output_t2.see(pos_start)
        self.lbl_status_t2.config(text=f"{self.current_match_t2 + 1} de {len(self.matches_t2)} ocorrência(s)")


if __name__ == "__main__":
    root = tk.Tk()
    app = PluggyApp(root)
    root.mainloop()