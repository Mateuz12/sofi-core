"""
run_monitors.py — Orquestrador e inicializador dos Monitores de E-mail VD (UDI + BH).
Inicia ambos os scripts como sub-processos em segundo plano.
"""

import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

script_udi = ROOT / "monitor_emails_vd.py"
script_bh = ROOT / "BH" / "monitor_emails_vd_BH.py"

log_udi_err = ROOT / "monitor_vd_stderr.log"
log_bh_err = ROOT / "BH" / "monitor_vd_stderr.log"

print(f"[Monitores VD] Iniciando Monitor UDI: {script_udi}")
f_udi = open(log_udi_err, "a", encoding="utf-8")
proc_udi = subprocess.Popen(
    [sys.executable, str(script_udi)],
    cwd=str(ROOT),
    stdout=f_udi,
    stderr=f_udi,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)

print(f"[Monitores VD] Iniciando Monitor BH: {script_bh}")
f_bh = open(log_bh_err, "a", encoding="utf-8")
proc_bh = subprocess.Popen(
    [sys.executable, str(script_bh)],
    cwd=str(ROOT / "BH"),
    stdout=f_bh,
    stderr=f_bh,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)

print(f"[Monitores VD] UDI PID: {proc_udi.pid} | BH PID: {proc_bh.pid}")
print("[Monitores VD] Ambos os monitores foram iniciados com sucesso!")
