import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

def obter_caminho_relatorio():
    base_dir = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI"
    
    print("\n[BUSCA DE ARQUIVO]")
    data_input = input("Pressione ENTER para buscar o relatório de HOJE, ou digite a data (ex: 18/03/2026): ").strip()
    
    if data_input:
        try:
            data_alvo = datetime.strptime(data_input, "%d/%m/%Y")
        except Exception as e:
            print("Formato de data inválido. Tentando buscar usando a data de hoje...")
            data_alvo = datetime.now()
    else:
        data_alvo = datetime.now()
        
    ano = data_alvo.strftime("%Y")
    mes_num = data_alvo.strftime("%m")
    dia = data_alvo.strftime("%d")
    
    meses_pt = {
        "01": "01 JANEIRO", "02": "02 FEVEREIRO", "03": "03 MARÇO",
        "04": "04 ABRIL", "05": "05 MAIO", "06": "06 JUNHO",
        "07": "07 JULHO", "08": "08 AGOSTO", "09": "09 SETEMBRO",
        "10": "10 OUTUBRO", "11": "11 NOVEMBRO", "12": "12 DEZEMBRO"
    }
    
    mes_pasta = meses_pt.get(mes_num, "")
    nome_arquivo = f"05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 20844.{data_alvo.strftime('%d-%m-%Y')}.xls"
    
    caminho_automatico = os.path.join(base_dir, ano, mes_pasta, dia, nome_arquivo)
    
    if os.path.exists(caminho_automatico):
        print(f"[+] Sucesso! Relatório encontrado automaticamente:\n    -> {caminho_automatico}\n")
        return caminho_automatico
    else:
        print(f"[-] O relatório não foi encontrado no caminho esperado:\n    -> {caminho_automatico}")
        print("[!] Abrindo janela para você selecionar o arquivo manualmente...")
        
        # Fallback: Janela de seleção manual
        root = tk.Tk()
        root.withdraw() # Oculta a janela principal do tkinter
        root.attributes('-topmost', True) # Traz a janela para frente
        
        caminho_manual = filedialog.askopenfilename(
            title="Selecione o relatório do Fechamento de Caixa",
            filetypes=[("Arquivos Excel", "*.xls *.xlsx")]
        )
        
        root.destroy()
        
        if not caminho_manual:
            print("[X] Nenhum arquivo selecionado. Finalizando o robô.")
            exit()
            
        print(f"[+] Arquivo selecionado manualmente:\n    -> {caminho_manual}\n")
        return caminho_manual

# ==========================================
# FASE 1: O CÉREBRO (PANDAS ETL)
# ==========================================
print("1. Lendo o relatório de cartões...")
caminho_relatorio = obter_caminho_relatorio()

df = pd.read_excel(caminho_relatorio, usecols=[
    'NumeroPedido', 'NumeroAutorizacao', 'ValorTitulo', 
    'BandeiraCartao', 'QuantidadeParcelas', 'EntidadeConciliacaoEmissao', 'Titulo'
])

print("2. Aplicando Filtro de Ruído (Removendo Boletos/Pix)...")
df_cartoes = df[~df['EntidadeConciliacaoEmissao'].astype(str).str.contains('Boleto|Pix', na=False, case=False)].copy()

print("3. Preparando dados para fusão (Matemática Pura)...")
df_cartoes['NumeroAutorizacao'] = df_cartoes['NumeroAutorizacao'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
df_cartoes['BandeiraCartao'] = df_cartoes['BandeiraCartao'].astype(str).str.strip()
df_cartoes['Titulo'] = df_cartoes['Titulo'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

def converter_para_float(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    v_str = str(valor).strip().replace('.', '').replace(',', '.')
    try: return float(v_str)
    except ValueError: return 0.0

df_cartoes['ValorMatematico'] = df_cartoes['ValorTitulo'].apply(converter_para_float)
df_cartoes['QuantidadeParcelas'] = pd.to_numeric(df_cartoes['QuantidadeParcelas'], errors='coerce').fillna(1)

print("4. Consolidando Parcelamentos (O Cérebro fundindo as linhas)...")
df_consolidado = df_cartoes.groupby(
    ['NumeroPedido', 'NumeroAutorizacao', 'BandeiraCartao'], as_index=False
).agg({
    'ValorMatematico': 'sum',
    'QuantidadeParcelas': 'max',
    'Titulo': 'first'
})

print("5. Formatando Valores para o Robô (Padrão Tela)...")
def formatar_para_tela(valor):
    try:
        texto = f"R$ {float(valor):,.2f}"
        return texto.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return str(valor)

df_consolidado['ValorTela'] = df_consolidado['ValorMatematico'].apply(formatar_para_tela)

print("6. Filtrando apenas pedidos complexos POS (1 para N)...")
pedidos_complexos = df_consolidado[df_consolidado.duplicated(subset=['NumeroPedido'], keep=False)].copy()

print("7. Montando a Fila de Trabalho para o Robô...")
fila_total = pedidos_complexos.groupby('NumeroPedido').apply(
    lambda x: x[['NumeroAutorizacao', 'ValorTela', 'BandeiraCartao', 'QuantidadeParcelas', 'ValorMatematico', 'Titulo']].to_dict('records')
).to_dict()

arquivo_checkpoint = "pedidos_conciliados.txt"
pedidos_ja_feitos = set()
if os.path.exists(arquivo_checkpoint):
    with open(arquivo_checkpoint, "r") as f:
        pedidos_ja_feitos = set(line.strip() for line in f if line.strip())
    print(f"    -> [CHECKPOINT] Recuperando sessão... {len(pedidos_ja_feitos)} pedidos já conciliados.")

fila_de_trabalho = {p: t for p, t in fila_total.items() if str(p) not in pedidos_ja_feitos}

quantidade_pedidos = len(fila_de_trabalho)
print(f"\n✅ SUCESSO! Encontrados {quantidade_pedidos} pedidos complexos para conciliar.")

# ==========================================
# FASE 2: OS MÚSCULOS (SELENIUM RPA)
# ==========================================
if quantidade_pedidos > 0:
    print("\n8. Iniciando Motor do Selenium...")
    
    driver = webdriver.Chrome()
    driver.maximize_window()

    # AVISO: Coloque o link exato da página de login do Finanças GB aqui se diferente
    driver.get("https://financasgb.grupoboticario.com.br/") 
    
    input("\n[AÇÃO MANUAL] Faça o login, carregue a tela com as caixas Laranjas e Azuis e aperte ENTER no terminal...")

    print("\n9. Iniciando Conciliação Visual...")

    for pedido, transacoes in fila_de_trabalho.items():
        try:
            print(f"\n[+] Iniciando Pedido: {pedido}")
            
            soma_total = sum([t['ValorMatematico'] for t in transacoes])
            valor_total_str = f"R$ {soma_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            caixa_laranja = None
            
            # PASSO B: Caçar e SELECIONAR a Caixa Laranja (Lado Esquerdo - PDV)
            for t in transacoes:
                aut_teste = t['NumeroAutorizacao']
                titulo_teste = t['Titulo']
                
                # XPath Laranja: Agora exige obrigatoriamente Titulo + Valor + a palavra 'PDV' (Ignorando se a Autorização da subtransação se repete)
                xpath_laranja = f"//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV') and not(.//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV')])]"
                
                try:
                    elementos = driver.find_elements(By.XPATH, xpath_laranja)
                    if len(elementos) > 0:
                        caixa_laranja = elementos[0] 
                        print(f"    -> Alvo Travado na Esquerda: {valor_total_str} (Documento: {titulo_teste})")
                        
                        # Rola a tela até exibir a caixa laranja e forçar marcação por JavaScript (Evita ElementNotInteractable)
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", caixa_laranja)
                        print("    -> Caixa Laranja selecionada via JS.")
                        time.sleep(1)
                        break 
                except:
                    continue
                    
            if not caixa_laranja:
                print(f"    [!] Caixa Laranja não encontrada para o pedido {pedido}. Pulando.")
                continue 
                
            # PASSO C: SELECIONAR AS AZUIS (Lado Direito - Modal Draggable)
            caixa_azul_para_arrastar = None 
            for transacao in transacoes:
                aut_azul = transacao['NumeroAutorizacao']
                valor_azul = transacao['ValorTela']
                # Variável alternativa: remove zeros à esquerda para flexibilizar a busca
                # (ex: "042954" vira "42954") pois o portal pode exibir com ou sem o zero
                aut_azul_sem_zero = str(aut_azul).lstrip('0') or '0'
                
                # Nova busca: utiliza a modal ID estável + div draggable para garantir seleção correta
                # Flex para Código de Autorização: busca TANTO com zeros à esquerda QUANTO sem
                xpath_azul = f"//*[@id='conciliacaoModal']//div[@class='draggable' and .//td[contains(., '{valor_azul}')] and (.//td[contains(., '{aut_azul}')] or .//td[contains(., '{aut_azul_sem_zero}')])]"
                
                caixa_azul = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_azul)))
                print(f"    -> Selecionando Azul: {valor_azul} (Aut: {aut_azul})")
                
                # Rolar scroll por JS para ter 100% de visibilidade e em seguida, executar clique via script
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_azul)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", caixa_azul)
                caixa_azul_para_arrastar = caixa_azul
                time.sleep(0.5)
                
            # PASSO D: O ARRASTO FÍSICO COM MICRO MOTIONS (DRAG AND DROP REFINADO)
            if caixa_azul_para_arrastar:
                print(f"    -> Realizando o arraste...")
                # Garante que a laranja está visível antes de soltar
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
                time.sleep(1)
                
                garra = ActionChains(driver)
                # Clica na última caixa azul "âncora", pausa levemente, movimenta em direção à laranja com offset, pausa para acender o 'dropzone' verde e libera o clique
                garra.click_and_hold(caixa_azul_para_arrastar)\
                     .pause(0.5)\
                     .move_to_element_with_offset(caixa_laranja, 5, 5)\
                     .pause(1.5)\
                     .release()\
                     .perform()
                
                print("    -> Aguardando Finanças GB processar... (Até 120s)")
                try:
                    # Espera Dinâmica: Trava o fluxo até o elemento caixa_laranja deixar de existir na página (staleness)
                    # Significa que o "loading/refresh" do site encerrou e removeu as caixas conciliadas da tela visível
                    WebDriverWait(driver, 120).until(EC.staleness_of(caixa_laranja))
                    time.sleep(1) # Extra de respiro após DOM estabilizar
                except:
                    print("    [!] A caixa Laranja não foi destruída pela tela no prazo máximo ou houve travamento de UI. Seguindo...")
                    time.sleep(3)
                
                # Checkpoint: Grava a prova de vida no HD
                with open(arquivo_checkpoint, "a") as f:
                    f.write(f"{pedido}\n")
                
                print(f"    ✅ Pedido {pedido} finalizado e salvo no checkpoint!")

        except Exception as e:
            print(f"    [!] ERRO: {str(e)[:50]}...")
            continue

    print("\n🚀 FIM DA FILA!")
    input("Aperte ENTER para fechar o robô...")
    driver.quit()

else:
    print("\nNenhum pedido complexo encontrado no relatório. Execução terminada.")
