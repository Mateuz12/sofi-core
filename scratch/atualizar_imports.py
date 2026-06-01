"""
Script para atualizar imports de sofi_env e database.logger em todos os scripts
migrados para a nova estrutura de departments/.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scratch/ -> raiz do projeto

# Novo bloco de importação padrão
NOVO_IMPORT_SOFI_ENV = """\
# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="{dept}")
"""

NOVO_IMPORT_LOGGER = """\
# Importa o logger
_ROOT_L = Path(__file__).resolve()
while not (_ROOT_L / ".env").exists() and _ROOT_L != _ROOT_L.parent:
    _ROOT_L = _ROOT_L.parent
if str(_ROOT_L) not in sys.path:
    sys.path.insert(0, str(_ROOT_L))
from core.database.logger import log_execution
"""

# Padrões antigos a remover/substituir
PATTERNS_SOFI_ENV = [
    # sys.path.insert(0, ...) + from sofi_env import ...
    r"sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)*\)\)\s*\nfrom sofi_env import load_sofi_env\s*\nload_sofi_env\(\)",
    # Variações sem load_dotenv call
    r"sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)*\)\)\s*\nfrom sofi_env import load_sofi_env",
]

PATTERNS_LOGGER = [
    # Comentário + sys.path.insert + from database.logger import
    r"# Importa o logger\s*\nsys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)*\)\)\s*\nfrom database\.logger import log_execution",
    # Sem comentário
    r"sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)*\)\)\s*\nfrom database\.logger import log_execution",
    # ROOT_DIR patterns
    r"ROOT_DIR\s*=\s*Path\(__file__\)\.resolve\(\)(?:\.parent)+\s*\nsys\.path\.insert\(0,\s*str\(ROOT_DIR\)\)\s*\nfrom database\.logger import log_execution",
]


def atualizar_arquivo(caminho: Path, dept: str):
    """Lê o arquivo, substitui os imports antigos e salva."""
    conteudo = caminho.read_text(encoding="utf-8")
    original = conteudo

    # 1) Substituir bloco sofi_env
    for pat in PATTERNS_SOFI_ENV:
        novo = NOVO_IMPORT_SOFI_ENV.format(dept=dept)
        conteudo, n = re.subn(pat, novo.strip(), conteudo, flags=re.MULTILINE)
        if n:
            print(f"  [sofi_env] {caminho.name}: {n} substituição(ões)")
            break

    # 2) Substituir bloco logger
    for pat in PATTERNS_LOGGER:
        novo = NOVO_IMPORT_LOGGER.strip()
        conteudo, n = re.subn(pat, novo, conteudo, flags=re.MULTILINE)
        if n:
            print(f"  [logger]   {caminho.name}: {n} substituição(ões)")
            break

    if conteudo != original:
        caminho.write_text(conteudo, encoding="utf-8")
        print(f"  [OK] {caminho.relative_to(ROOT)} atualizado.")
    else:
        print(f"  [MANUAL] {caminho.relative_to(ROOT)} - nenhum padrao reconhecido. Verificar manualmente.")


# ─── MAPA: arquivo → departamento ────────────────────────────────────────────
ARQUIVOS = {
    "financeiro": [
        "departments/financeiro/modules/xml/debug_meudanfe.py",
        "departments/financeiro/modules/xml/gerador_relatorio.py",
        "departments/financeiro/modules/xml/leitor_xml.py",
        "departments/financeiro/modules/extranet/extranet_reports.py",
        "departments/financeiro/modules/extranet/extranet_reports_UDI.py",
        "departments/financeiro/modules/extranet/extranet_bh_pordata.py",
        "departments/financeiro/modules/extranet/extranet_UDI_pordata copy.py",
        "departments/financeiro/modules/retaguarda/extrator_portal.py",
        "departments/financeiro/modules/retaguarda/extrator_portal_udi por data.py",
        "departments/financeiro/modules/retaguarda/debug_bh.py",
        "departments/financeiro/modules/retaguarda/debug_financas.py",
        "departments/financeiro/modules/retaguarda/BH/extrator_portal_bh.py",
        "departments/financeiro/modules/retaguarda/BH/extrator_portal_bh_pordata.py",
        "departments/financeiro/modules/depositos/AUTOMACOES DE DEPOSITO/capturar_token.py",
        "departments/financeiro/modules/depositos/AUTOMACOES DE DEPOSITO/mvp_deposito_21061.py",
        "departments/financeiro/modules/depositos/AUTOMACOES DE DEPOSITO/script_depositos.py",
        "departments/financeiro/modules/emails_vd/portal_uploader.py",
        "departments/financeiro/modules/conciliacao_venda/playwright_version/main.py",
    ],
}

if __name__ == "__main__":
    print("=" * 60)
    print("SOFI — Atualizador de imports")
    print("=" * 60)
    for dept, arquivos in ARQUIVOS.items():
        print(f"\n[Departamento: {dept}]")
        for rel in arquivos:
            caminho = ROOT / rel
            if caminho.exists():
                atualizar_arquivo(caminho, dept)
            else:
                print(f"  [NAO ENCONTRADO] {rel}")
    print("\nConcluído!")
