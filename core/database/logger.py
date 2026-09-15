import sys
import sqlite3
import traceback
import getpass
from pathlib import Path
from datetime import datetime
import functools

# Encontra a raiz do projeto e adiciona ao sys.path
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env()

import os
db_path = os.getenv("LOG_DB_PATH", "core/database/sofi.db")
DB_FILE = _ROOT / db_path

def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        # Modo WAL suporta leituras simultâneas sem bloquear escritas (ideal para Streamlit)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modulo TEXT,
                status TEXT,
                mensagem TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuration_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT NOT NULL,
                dominio TEXT NOT NULL,
                chave TEXT NOT NULL,
                valor_anterior TEXT,
                valor_novo TEXT
            )
        """)

init_db()

class DBStreamCatcher:
    """ Intercepta sys.stdout/stderr para gravar no terminal e no banco SQLite. """
    def __init__(self, original_stream, log_id):
        self.original_stream = original_stream
        self.log_id = log_id

    def write(self, text):
        # 1. Print no terminal original (com fallback seguro para Windows cp1252)
        try:
            self.original_stream.write(text)
        except UnicodeEncodeError:
            # Substitui caracteres incompatíveis com o encoding do terminal
            self.original_stream.write(text.encode('ascii', errors='replace').decode('ascii'))
        self.original_stream.flush()
        
        # 2. Append no banco
        if text:
            try:
                with sqlite3.connect(DB_FILE, timeout=10.0) as conn:
                    # Concatena o texto ao final da mensagem (se null, trata como vazio)
                    conn.execute("""
                        UPDATE execution_logs
                        SET mensagem = COALESCE(mensagem, '') || ?
                        WHERE id = ?
                    """, (text, self.log_id))
            except Exception as e:
                # Se falhar no banco, loga no original apenas
                self.original_stream.write(f"\n[Logger DB Error]: {e}\n")

    def flush(self):
        self.original_stream.flush()

def log_execution(modulo="Geral"):
    """
    Decorator para envelopar a função main() de cada script.
    Registra inicio, captura os prints (via sys.stdout/stderr) e finaliza com SUCESSO/ERRO.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            usuario = getpass.getuser()
            
            # Insere INICIADO no banco e pega o ID
            with sqlite3.connect(DB_FILE, timeout=10.0) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO execution_logs (modulo, status, mensagem, usuario)
                    VALUES (?, ?, ?, ?)
                """, (modulo, "INICIADO", "", usuario))
                log_id = cursor.lastrowid
            
            # Captura stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = DBStreamCatcher(old_stdout, log_id)
            sys.stderr = DBStreamCatcher(old_stderr, log_id)
            
            status_final = "ERRO"
            try:
                result = func(*args, **kwargs)
                status_final = "SUCESSO"
                return result
            except Exception as e:
                # Em caso de erro, printa o traceback (que será capturado pelo sys.stderr)
                traceback.print_exc()
                raise
            finally:
                # Restaura saídas
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                
                # Atualiza status final
                try:
                    with sqlite3.connect(DB_FILE, timeout=10.0) as conn:
                        conn.execute("""
                            UPDATE execution_logs
                            SET status = ?
                            WHERE id = ?
                        """, (status_final, log_id))
                except Exception as e:
                    print(f"\n[Logger DB Error on close]: {e}\n")

        return wrapper
    return decorator
