import sys
from pathlib import Path
from etl_engine import ETLEngine
from rpa_engine import RPAEngine

# Importa o logger
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from database.logger import log_execution

@log_execution(modulo="Conciliação de Vendas")
def main():
    print("="*60)
    print("  AUTOMAÇÃO OMINI - VERSÃO PLAYWRIGHT (REESCRITA)  ")
    print("="*60)
    print("\nPressione ENTER para rodar com o relatório de HOJE.")
    print("Ou digite uma data especifica (ex: 18/03/2026).")
    data_input = input("Data: ")
    
    # 1. Aciona o Motor ETL
    etl = ETLEngine(data_input=data_input)
    caminho_relatorio = etl.obter_caminho_relatorio()
    
    if not caminho_relatorio:
        # Se não encontrou automático, encerra no fluxo atual
        # A seleção manual de filedialog pode ser conectada na futura interface visual
        print("[!] Arquivo não encontrado. Abortando execução para esta data.")
        sys.exit(1)
        
    try:
        fila_trabalho, qtd_pedidos = etl.executar_processamento(caminho_relatorio)
    except Exception as e:
        print(f"[!] Erro ao processar o arquivo Excel: {e}")
        sys.exit(1)
        
    if qtd_pedidos == 0:
        print("\n[!] Nenhum pedido OMINI encontrado no relatório. Execução terminada.")
        sys.exit(0)
        
    # 2. Aciona o Motor Playwright (RPA)
    print(f"\n-> Iniciando Robô do Navegador para {qtd_pedidos} pedidos...")
    rpa = RPAEngine(headless=False)
    try:
        rpa.executar_conciliacao(fila_trabalho)
    except Exception as e:
        print(f"\n[ERRO FATAL NO NAVEGADOR] Ocorreu um erro na execução: {e}")
        sys.exit(1)
        
    print("\nExecução finalizada com sucesso.")

if __name__ == '__main__':
    main()
