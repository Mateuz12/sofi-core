import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.logger import log_execution

@log_execution(modulo="Teste Logger")
def main():
    print("Iniciando o teste do logger.")
    print("Isso deve aparecer no terminal e no banco de dados.")
    for i in range(3):
        print(f"Passo {i+1} completo.")
    print("Teste finalizado com sucesso.")

if __name__ == "__main__":
    main()
