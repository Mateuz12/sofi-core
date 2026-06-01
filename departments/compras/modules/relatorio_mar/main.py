"""
Launcher GUI - Relatório MAR
Interface gráfica para extração e tratamento dos relatórios.
"""

import sys
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from datetime import datetime

# ─── Configurações ────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    DIRETORIO_PROJETO = Path(sys.executable).resolve().parent
else:
    DIRETORIO_PROJETO = Path(__file__).resolve().parent

ARQUIVO_ENV = DIRETORIO_PROJETO / ".env"
ARQUIVO_ENV_EXEMPLO = DIRETORIO_PROJETO / ".env.example"
PASTA_TEMPLATES = DIRETORIO_PROJETO / "templates"

# ─── Paleta de cores ─────────────────────────────────────────────────────────

COR = {
    "bg":              "#1a1b2e",
    "surface":         "#252640",
    "surface_hover":   "#2f3055",
    "primary":         "#7c3aed",
    "primary_hover":   "#6d28d9",
    "success":         "#22c55e",
    "warning":         "#f59e0b",
    "error":           "#ef4444",
    "text":            "#e2e8f0",
    "text_muted":      "#94a3b8",
    "log_bg":          "#0f1019",
    "log_text":        "#c8d0dc",
    "border":          "#3d3e5c",
}


# ─── Redirecionamento de output para a fila ──────────────────────────────────

class LogRedirector:
    """Redireciona stdout/stderr para uma fila thread-safe."""

    def __init__(self, fila: queue.Queue):
        self.fila = fila

    def write(self, msg: str):
        if msg and msg.strip():
            self.fila.put(msg if msg.endswith("\n") else msg + "\n")

    def flush(self):
        pass


# ─── Aplicação Principal ─────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Relatório MAR — Automação")
        self.root.geometry("780x600")
        self.root.minsize(640, 480)
        self.root.configure(bg=COR["bg"])

        # Tenta definir o ícone (ignora se não existir)
        try:
            ico = DIRETORIO_PROJETO / "icon.ico"
            if ico.exists():
                self.root.iconbitmap(str(ico))
        except Exception:
            pass

        # Estado
        self.log_queue = queue.Queue()
        self.executando = False

        # Redireciona print() para o log da GUI
        self._stdout_original = sys.stdout
        self._stderr_original = sys.stderr
        sys.stdout = LogRedirector(self.log_queue)
        sys.stderr = LogRedirector(self.log_queue)

        # Monta a interface
        self._criar_cabecalho()
        self._criar_status()
        self._criar_botoes()
        self._criar_log()

        # Inicia polling do log e fecha corretamente
        self._poll_log()
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ── Cabeçalho ────────────────────────────────────────────────────────────

    def _criar_cabecalho(self):
        frame = tk.Frame(self.root, bg=COR["surface"], pady=16)
        frame.pack(fill="x")

        tk.Label(
            frame,
            text="Relatório MAR",
            font=("Segoe UI", 20, "bold"),
            fg=COR["text"], bg=COR["surface"],
        ).pack()

        tk.Label(
            frame,
            text="Automação — Portal Extranet Grupo Boticário",
            font=("Segoe UI", 10),
            fg=COR["text_muted"], bg=COR["surface"],
        ).pack()

    # ── Indicadores de status ────────────────────────────────────────────────

    def _criar_status(self):
        self.frame_status = tk.Frame(self.root, bg=COR["bg"], pady=10, padx=20)
        self.frame_status.pack(fill="x")

        self.lbl_env = tk.Label(
            self.frame_status, font=("Segoe UI", 10),
            fg=COR["text_muted"], bg=COR["bg"], anchor="w",
        )
        self.lbl_env.pack(side="left", padx=(0, 24))

        self.lbl_templates = tk.Label(
            self.frame_status, font=("Segoe UI", 10),
            fg=COR["text_muted"], bg=COR["bg"], anchor="w",
        )
        self.lbl_templates.pack(side="left")

        self._atualizar_status()

    def _atualizar_status(self):
        # .env
        env_ok = ARQUIVO_ENV.exists()
        if env_ok:
            self.lbl_env.config(text="● .env configurado", fg=COR["success"])
        else:
            self.lbl_env.config(text="○ .env não encontrado", fg=COR["error"])

        # Templates
        PASTA_TEMPLATES.mkdir(exist_ok=True)
        qtd = len(list(PASTA_TEMPLATES.glob("*_template.xlsx")))
        cor = COR["success"] if qtd > 0 else COR["warning"]
        self.lbl_templates.config(text=f"● {qtd} templates", fg=cor)

    # ── Botões de ação ───────────────────────────────────────────────────────

    def _criar_botoes(self):
        frame = tk.Frame(self.root, bg=COR["bg"], pady=6, padx=20)
        frame.pack(fill="x")

        # Botão principal
        self.btn_tudo = self._botao(
            frame, "▶  Executar Tudo  (Extração + Tratamento)",
            self._run_workflow_completo, primario=True,
        )
        self.btn_tudo.pack(fill="x", pady=(0, 8))

        frame_row = tk.Frame(frame, bg=COR["bg"])
        frame_row.pack(fill="x")

        self.btn_extracao = self._botao(
            frame_row, "📥  Só Extração",
            self._run_extracao,
        )
        self.btn_extracao.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_tratamento = self._botao(
            frame_row, "📊  Só Tratamento",
            self._run_tratamento,
        )
        self.btn_tratamento.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _botao(self, parent, texto, comando, primario=False):
        bg = COR["primary"] if primario else COR["surface"]
        hover = COR["primary_hover"] if primario else COR["surface_hover"]
        fg = COR["text"]
        tamanho = 12 if primario else 10
        peso = "bold" if primario else "normal"

        btn = tk.Button(
            parent, text=texto, command=comando,
            font=("Segoe UI", tamanho, peso),
            fg=fg, bg=bg, activeforeground=fg, activebackground=hover,
            relief="flat", cursor="hand2", pady=10, bd=0,
        )
        btn.bind("<Enter>", lambda e, b=btn, c=hover: b.config(bg=c))
        btn.bind("<Leave>", lambda e, b=btn, c=bg: b.config(bg=c))
        return btn

    def _desabilitar_botoes(self):
        for btn in (self.btn_tudo, self.btn_extracao, self.btn_tratamento):
            btn.config(state="disabled", bg=COR["border"], cursor="arrow")

    def _habilitar_botoes(self):
        self.btn_tudo.config(
            state="normal", bg=COR["primary"], cursor="hand2",
        )
        for btn in (self.btn_extracao, self.btn_tratamento):
            btn.config(state="normal", bg=COR["surface"], cursor="hand2")

    # ── Área de log ──────────────────────────────────────────────────────────

    def _criar_log(self):
        frame = tk.Frame(self.root, bg=COR["bg"], padx=20)
        frame.pack(fill="both", expand=True, pady=(6, 12))

        # Cabeçalho do log
        header = tk.Frame(frame, bg=COR["bg"])
        header.pack(fill="x", pady=(0, 4))

        tk.Label(
            header, text="Log", font=("Segoe UI", 10, "bold"),
            fg=COR["text_muted"], bg=COR["bg"],
        ).pack(side="left")

        btn_limpar = tk.Button(
            header, text="Limpar", command=self._limpar_log,
            font=("Segoe UI", 9), fg=COR["text_muted"], bg=COR["bg"],
            activeforeground=COR["text"], activebackground=COR["bg"],
            relief="flat", cursor="hand2", bd=0,
        )
        btn_limpar.pack(side="right")

        # Caixa de texto com scroll
        container = tk.Frame(frame, bg=COR["border"], bd=1, relief="solid")
        container.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            container,
            font=("Consolas", 10),
            fg=COR["log_text"], bg=COR["log_bg"],
            insertbackground=COR["text"],
            selectbackground=COR["primary"],
            relief="flat", wrap="word",
            padx=10, pady=8,
            state="disabled",
        )

        scrollbar = tk.Scrollbar(
            container, command=self.log_text.yview,
            bg=COR["surface"], troughcolor=COR["log_bg"],
            activebackground=COR["primary"],
        )
        self.log_text.config(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        # Mensagem inicial
        self._log_escrever("Pronto. Selecione uma opção acima para iniciar.\n")

    def _log_escrever(self, texto: str):
        """Escreve diretamente no widget de log (thread principal)."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", texto)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _limpar_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _poll_log(self):
        """Consome a fila de log e escreve no widget (chamado a cada 100ms)."""
        while True:
            try:
                msg = self.log_queue.get_nowait()
                self._log_escrever(msg)
            except queue.Empty:
                break
        self.root.after(100, self._poll_log)

    # ── Execução em thread separada ──────────────────────────────────────────

    def _executar_em_thread(self, funcao, nome: str):
        """Roda uma função em thread separada para não travar a GUI."""
        if self.executando:
            return

        self.executando = True
        self._desabilitar_botoes()
        self._atualizar_status()

        def wrapper():
            agora = datetime.now().strftime("%H:%M:%S")
            print(f"[{agora}] ═══ Iniciando: {nome} ═══")
            try:
                funcao()
            except SystemExit:
                # Scripts usam sys.exit() em erros — não deixa fechar a GUI
                agora = datetime.now().strftime("%H:%M:%S")
                print(f"[{agora}] Processo finalizado (com erros, veja acima).")
            except Exception as e:
                agora = datetime.now().strftime("%H:%M:%S")
                print(f"[{agora}] ERRO: {e}")
            finally:
                agora = datetime.now().strftime("%H:%M:%S")
                print(f"[{agora}] ═══ Finalizado: {nome} ═══\n")
                # Volta para a thread principal para habilitar botões
                self.root.after(0, self._finalizar_execucao)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()

    def _finalizar_execucao(self):
        self.executando = False
        self._habilitar_botoes()
        self._atualizar_status()

    # ── Wrappers de execução ─────────────────────────────────────────────────

    def _run_extracao(self):
        if not ARQUIVO_ENV.exists():
            messagebox.showwarning(
                "Configuração necessária",
                "O arquivo .env não foi encontrado.\n\n"
                "Copie o .env.example para .env e preencha\n"
                "suas credenciais antes de executar a extração.",
            )
            return
        self._executar_em_thread(self._extracao, "Extração")

    def _run_tratamento(self):
        self._executar_em_thread(self._tratamento, "Tratamento")

    def _run_workflow_completo(self):
        if not ARQUIVO_ENV.exists():
            messagebox.showwarning(
                "Configuração necessária",
                "O arquivo .env não foi encontrado.\n\n"
                "Copie o .env.example para .env e preencha\n"
                "suas credenciais antes de executar.",
            )
            return
        self._executar_em_thread(self._workflow_completo, "Workflow Completo")

    @staticmethod
    def _extracao():
        from extracao_mar import executar_extracao
        executar_extracao()

    @staticmethod
    def _tratamento():
        from tratamento_mar import executar_tratamento
        executar_tratamento()

    def _workflow_completo(self):
        print("=" * 50)
        print("  ETAPA 1/2 — EXTRAÇÃO DO RELATÓRIO")
        print("=" * 50)
        self._extracao()

        print()
        print("=" * 50)
        print("  ETAPA 2/2 — TRATAMENTO DOS DADOS")
        print("=" * 50)
        self._tratamento()

        print()
        print("✓ WORKFLOW COMPLETO FINALIZADO!")

    # ── Fechamento ───────────────────────────────────────────────────────────

    def _ao_fechar(self):
        if self.executando:
            if not messagebox.askokcancel(
                "Processo em andamento",
                "Um processo está em execução.\nDeseja fechar mesmo assim?",
            ):
                return

        # Restaura stdout/stderr
        sys.stdout = self._stdout_original
        sys.stderr = self._stderr_original
        self.root.destroy()

    # ── Iniciar ──────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ─── Ponto de entrada ────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        app = App()
        app.run()
    except Exception as e:
        messagebox.showerror(
            "Erro Fatal",
            f"Não foi possível iniciar a aplicação:\n\n{e}",
        )
        sys.exit(1)
