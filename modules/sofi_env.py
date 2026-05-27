"""
SOFI — Carregamento centralizado do .env global.

Uso em qualquer script dentro de /modules:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # aponta para /modules
    from sofi_env import load_sofi_env
    load_sofi_env()
"""
from pathlib import Path
from dotenv import load_dotenv


def _find_project_root() -> Path:
    """Sobe a árvore de diretórios procurando o .env na raiz do projeto."""
    current = Path(__file__).resolve().parent  # modules/
    for _ in range(10):
        candidate = current / ".env"
        if candidate.exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Não encontrei o .env global do SOFI. "
        "Certifique-se de que .env existe na raiz do projeto (sofi-core/.env)."
    )


def load_sofi_env(override: bool = True) -> Path:
    """Carrega o .env global do SOFI na raiz do projeto.

    Args:
        override: Se True (padrão), sobrescreve variáveis já definidas no ambiente.

    Returns:
        Path do arquivo .env encontrado e carregado.
    """
    root = _find_project_root()
    env_path = root / ".env"
    load_dotenv(env_path, override=override)
    return env_path
