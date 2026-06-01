"""
Script de Build — Relatório MAR
Empacota o projeto em EXE usando PyInstaller.

Pré-requisitos:
  pip install pyinstaller

Uso:
  python build.py
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

# Garante que o console do Windows use UTF-8
if os.name == "nt":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DIRETORIO_PROJETO = Path(__file__).resolve().parent
DIST_DIR = DIRETORIO_PROJETO / "dist"
BUILD_DIR = DIRETORIO_PROJETO / "build"
NOME_APP = "RelatorioMARS"


def encontrar_playwright_driver() -> Path | None:
    """Localiza o diretório do driver do Playwright para bundling."""
    try:
        import playwright
        driver_dir = Path(playwright.__file__).parent / "driver"
        if driver_dir.exists():
            return driver_dir
    except ImportError:
        pass
    return None


def build():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   Build — Relatório MAR                                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Verifica se PyInstaller está instalado
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__} encontrado.")
    except ImportError:
        print("  ✗ PyInstaller não encontrado!")
        print("    Instale com: pip install pyinstaller")
        sys.exit(1)

    # Localiza o driver do Playwright
    playwright_driver = encontrar_playwright_driver()
    if playwright_driver:
        print(f"  ✓ Playwright driver encontrado: {playwright_driver}")
    else:
        print("  ⚠ Playwright driver NÃO encontrado.")
        print("    A extração (extracao_mar) pode não funcionar no EXE.")
        print("    Instale com: pip install playwright")

    print()
    print("  Construindo o EXE...")
    print("  (isso pode levar alguns minutos)")
    print()

    # Monta o comando do PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", NOME_APP,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",

        # Ícone (se existir)
        # "--icon", str(DIRETORIO_PROJETO / "icon.ico"),

        # Hidden imports necessários
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "playwright._impl",
        "--hidden-import", "playwright._impl._driver",
        "--hidden-import", "xlwings",
        "--hidden-import", "xlwings._xlwindows",
        "--hidden-import", "openpyxl",
        "--hidden-import", "openpyxl.utils.cell",
        "--hidden-import", "pandas",
        "--hidden-import", "dotenv",

        # Coleta todo o pacote playwright (inclui o driver node.js)
        "--collect-all", "playwright",
    ]

    # Adiciona o driver do Playwright como dados extras
    if playwright_driver:
        cmd.extend([
            "--add-data", f"{playwright_driver};playwright/driver",
        ])

    # Arquivo principal
    cmd.append(str(DIRETORIO_PROJETO / "main.py"))

    # Adiciona os módulos do projeto como dados (para import funcionar)
    for modulo in ["extracao_mar.py", "tratamento_mar.py"]:
        caminho = DIRETORIO_PROJETO / modulo
        if caminho.exists():
            cmd.extend(["--add-data", f"{caminho};."])

    print(f"  Comando: {' '.join(cmd[:6])} ...")
    print()

    resultado = subprocess.run(cmd, cwd=str(DIRETORIO_PROJETO))

    if resultado.returncode != 0:
        print()
        print("  ✗ ERRO: Build falhou! Verifique os erros acima.")
        sys.exit(1)

    pasta_saida = DIST_DIR / NOME_APP
    print()
    print("=" * 60)
    print(f"  ✓ BUILD CONCLUÍDO!")
    print(f"  Saída: {pasta_saida}")
    print()
    print("  Próximo passo:")
    print("    1. Copie a pasta 'templates/' para dentro de:")
    print(f"       {pasta_saida}")
    print("    2. Copie o '.env.example' para '.env' e configure.")
    print("    3. Ou use o Inno Setup com 'installer.iss' para")
    print("       gerar o instalador .exe")
    print("=" * 60)


if __name__ == "__main__":
    build()
