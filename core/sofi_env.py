"""
SOFI — Carregamento centralizado do .env global + .env.local por departamento.

Uso em qualquer script dentro de /departments/<dept>/modules/:
    import sys
    from pathlib import Path

    _ROOT = Path(__file__).resolve()
    while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
        _ROOT = _ROOT.parent
    sys.path.insert(0, str(_ROOT))

    from core.sofi_env import load_sofi_env
    load_sofi_env(department="financeiro")   # carrega .env + .env.local do dept
"""
from pathlib import Path
from dotenv import load_dotenv


def _find_project_root() -> Path:
    """Sobe a árvore de diretórios procurando o .env na raiz do projeto."""
    current = Path(__file__).resolve().parent.parent  # core/ -> raiz
    for _ in range(10):
        candidate = current / ".env"
        if candidate.exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Não encontrei o .env global do SOFI. "
        "Certifique-se de que .env existe na raiz do projeto (sofi-core/.env)."
    )


def load_sofi_env(department: str = None, override: bool = True) -> Path:
    """Carrega o .env global do SOFI e, opcionalmente, o .env.local do departamento.

    Args:
        department: Nome do departamento (ex: "financeiro", "rh", "compras").
                    Se informado, carrega também departments/<dept>/.env.local
                    por cima do .env central (override=True).
        override:   Se True (padrão), sobrescreve variáveis já definidas no ambiente.

    Returns:
        Path do .env central encontrado e carregado.
    """
    root = _find_project_root()

    # 1. Carrega o .env central (credenciais compartilhadas entre departamentos)
    env_path = root / ".env"
    load_dotenv(env_path, override=override)

    # 2. Carrega o .env.local do departamento por cima (credenciais exclusivas)
    if department:
        local_env = root / "departments" / department / ".env.local"
        if local_env.exists():
            load_dotenv(local_env, override=True)

    return env_path
