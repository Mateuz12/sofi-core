"""
run_monitors.py — Orquestrador e Supervisor dos Monitores de E-mail VD (UDI + BH).
Inicia ambos os scripts e mantém a supervisão contínua em segundo plano.
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

def start_udi():
    f_udi = open(log_udi_err, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, str(script_udi)],
        cwd=str(ROOT),
        stdout=f_udi,
        stderr=f_udi,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

def start_bh():
    f_bh = open(log_bh_err, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, str(script_bh)],
        cwd=str(ROOT / "BH"),
        stdout=f_bh,
        stderr=f_bh,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

def main():
    print("[Monitores VD] Iniciando Supervisor de Monitores...")
    proc_udi = start_udi()
    proc_bh = start_bh()
    print(f"[Monitores VD] UDI PID: {proc_udi.pid} | BH PID: {proc_bh.pid}")
    print("[Monitores VD] Ambos os monitores foram iniciados e estão sendo supervisionados!")

    try:
        while True:
            time.sleep(10)
            if proc_udi.poll() is not None:
                print("[Monitores VD] Processo UDI finalizado. Reiniciando...")
                proc_udi = start_udi()
            if proc_bh.poll() is not None:
                print("[Monitores VD] Processo BH finalizado. Reiniciando...")
                proc_bh = start_bh()
    except KeyboardInterrupt:
        print("[Monitores VD] Encerrando supervisor e monitores...")
        proc_udi.terminate()
        proc_bh.terminate()

if __name__ == "__main__":
    main()
