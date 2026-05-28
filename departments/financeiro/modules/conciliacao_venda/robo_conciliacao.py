import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time

# ==========================================
# 1. O CÉREBRO: LENDO A PLANILHA
# ==========================================
df_vendas = pd.read_excel(r"C:\Users\luma.dias\Desktop\VENDAS1.xls", decimal=',')

pedido_alvo = 498098062
doc_alvo = "435368362" 

coluna_nsu = 'NSU' # <- Não esqueça de colocar o nome da sua coluna de novo!

# AJUSTE 1: Garante que a NSU seja um texto limpo, sem '.0' no final
lista_nsus = df_vendas[df_vendas['NumeroPedido'] == pedido_alvo][coluna_nsu].dropna().astype(str).str.replace('.0', '', regex=False).tolist()

print(f"Alvo Laranja (Doc): {doc_alvo}")
print(f"Alvos Azuis (NSUs encontradas na planilha): {lista_nsus}")
print("-" * 30)

# ==========================================
# 2. OS OLHOS: ACESSANDO O SISTEMA
# ==========================================
navegador = webdriver.Chrome()
navegador.get("https://financasgb.grupoboticario.com.br/") # <- Recoloque sua URL

input("HUMANO: Faça o login, vá até a tela de Conciliação e aperte ENTER aqui no terminal para eu assumir...")

# ==========================================
# 3. AS MÃOS: SELECIONAR E DEPOIS ARRASTAR
# ==========================================
try:
    caixa_azul_para_arrastar = None

    # 1º PASSO: Clicar para selecionar todas as NSUs juntas
    for nsu in lista_nsus:
        print(f"\n[Selecionando a NSU: {nsu}]")
        
        # Encontra a caixa na tela
        caixa_azul = navegador.find_element(By.XPATH, f"//*[contains(text(), '{nsu}')]")
        
        # O robô dá um clique simples nela para marcá-la no sistema
        caixa_azul.click()
        
        # Guarda essa caixa na memória para ser a nossa "alça" de arrastar depois
        caixa_azul_para_arrastar = caixa_azul
        
        # Uma pausa microscópica só para a página web registrar o clique
        time.sleep(0.5) 
        
    # 2º PASSO: Arrastar o bloco inteiro para a venda
    print(f"\n-> Arrastando o bloco de NSUs para o Doc {doc_alvo}...")
    
    # Acha o destino
    caixa_laranja = navegador.find_element(By.XPATH, f"//*[contains(text(), '{doc_alvo}')]")
    
    # Cria a garra, segura a última caixa azul que clicamos e joga na laranja
    garra = ActionChains(navegador)
    garra.drag_and_drop(caixa_azul_para_arrastar, caixa_laranja).perform()
    
    # Pausa para o sistema processar a junção e fechar a conta
    time.sleep(2) 
        
    print("\nSUCESSO FINAL: Lote conciliado com perfeição!")
    
except Exception as e:
    print(f"\nERRO NA EXECUÇÃO:")
    print(f"O robô falhou na seleção ou no arrasto. Mensagem técnica: {e}")

input("Aperte ENTER para fechar o robô...")
navegador.quit()