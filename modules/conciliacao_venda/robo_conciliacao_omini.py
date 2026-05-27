import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

def desmarcar_caixa_laranja(driver, caixa_laranja):
    if not caixa_laranja:
        return

    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", caixa_laranja)
        time.sleep(0.5)
        print("    -> Caixa Laranja desmarcada antes de seguir para o proximo pedido.")
    except Exception as e:
        print(f"    [!] Clique para desmarcar a Caixa Laranja falhou: {str(e)[:50]}...")
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            print("    -> Tentativa extra de limpar selecao enviada com ESC.")
        except Exception as esc_error:
            print(f"    [!] Nao foi possivel limpar a selecao automaticamente: {str(esc_error)[:50]}...")

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
# FASE 1: O CÉREBRO (PANDAS ETL) - APENAS OMINI
# ==========================================
print("1. Lendo o relatório de cartões...")
caminho_relatorio = obter_caminho_relatorio()

df = pd.read_excel(caminho_relatorio, usecols=[
    'NumeroPedido', 'NumeroAutorizacao', 'ValorTitulo', 
    'BandeiraCartao', 'QuantidadeParcelas', 'EntidadeConciliacaoEmissao', 'Titulo', 'PlanoPagamento', 'DataPedido'
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

print("4. Consolidando Parcelamentos e Filtrando Somente OMINI...")
df_consolidado = df_cartoes.groupby(
    ['NumeroPedido', 'NumeroAutorizacao', 'BandeiraCartao'], as_index=False
).agg({
    'ValorMatematico': 'sum',
    'QuantidadeParcelas': 'max',
    'Titulo': 'first',
    'PlanoPagamento': 'first',
    'DataPedido': 'first'
})

def formatar_para_tela(valor):
    try:
        texto = f"R$ {float(valor):,.2f}"
        return texto.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return str(valor)

df_consolidado['ValorTela'] = df_consolidado['ValorMatematico'].apply(formatar_para_tela)

# Filtra APENAS pedidos OMINIChannel
is_omini = df_consolidado['PlanoPagamento'].astype(str).str.strip().str.upper() == 'OMNICHANNEL - CONSUMIDOR FINAL'
pedidos_omini = df_consolidado[is_omini].copy()

print("5. Montando a Fila de Trabalho OMINI...")
fila_total_omini = pedidos_omini.groupby('NumeroPedido').apply(
    lambda x: {
        'transacoes': x[['NumeroAutorizacao', 'ValorTela', 'BandeiraCartao', 'QuantidadeParcelas', 'ValorMatematico', 'Titulo']].to_dict('records'),
        'DataPedido': x['DataPedido'].iloc[0] # Pega a data do primeiro registro desse pedido
    }
).to_dict()

# REMOVIDO CHECKPOINT PARA TESTES
fila_de_trabalho_omini = fila_total_omini.copy()
quantidade_pedidos_omini = len(fila_de_trabalho_omini)

print(f"\n[SUCESSO] Encontrados {quantidade_pedidos_omini} pedidos OMINI para conciliar.")

# ==========================================
# FASE 2: OS MÚSCULOS (SELENIUM RPA)
# ==========================================
if quantidade_pedidos_omini > 0:
    print("\n6. Iniciando Motor do Selenium...")
    
    driver = webdriver.Chrome()
    driver.maximize_window()

    driver.get("https://financasgb.grupoboticario.com.br/") 
    
    input("\n[AÇÃO MANUAL] Faça o login, carregue a tela com as caixas Laranjas e Azuis e aperte ENTER no terminal...")

    print("\n7. Iniciando Conciliação Visual OMINI...")
    
    # Agrupa por Data
    pedidos_omini_por_data = {}
    for p, dados in fila_de_trabalho_omini.items():
        data_raw = pd.to_datetime(dados['DataPedido'], dayfirst=True, errors='coerce')
        data_str = data_raw.strftime('%d/%m/%Y') if pd.notna(data_raw) else 'Sem Data'
        data_sort_key = data_raw if pd.notna(data_raw) else pd.Timestamp.max 
        
        if data_str not in pedidos_omini_por_data:
            pedidos_omini_por_data[data_str] = {'pedidos': {}, 'sort_key': data_sort_key}
        
        if isinstance(pedidos_omini_por_data[data_str], dict) and 'pedidos' in pedidos_omini_por_data[data_str]:
            pedidos_dict: dict = pedidos_omini_por_data[data_str]['pedidos']
            pedidos_dict[p] = dados
            
    # Ordena cronologicamente
    datas_ordenadas = sorted(
        list(pedidos_omini_por_data.keys()), 
        key=lambda d: pedidos_omini_por_data[d].get('sort_key', pd.Timestamp.max) if isinstance(pedidos_omini_por_data[d], dict) else pd.Timestamp.max
    )
    
    for data_atual in datas_ordenadas:
        if isinstance(pedidos_omini_por_data[data_atual], dict) and 'pedidos' in pedidos_omini_por_data[data_atual]:
            pedidos_da_data: dict = pedidos_omini_por_data[data_atual]['pedidos']
            print("\n==========================================")
            print(f"[DATA] INICIANDO PAGAMENTOS OMINI DO DIA: {data_atual}")
            print(f"       Total de pedidos para esta data: {len(pedidos_da_data)}")
            print("==========================================")
            
            input(f"\n[AÇÃO MANUAL] Vá no Finanças GB e filtre os pagamentos (lado direito) e pedidos (lado esquerdo) para a data {data_atual}.\n"
                  "Quando a tela estiver carregada e pronta para essa data, aperte ENTER aqui para o robô começar...")
            
            for pedido, dados_pedido in pedidos_da_data.items():
                transacoes = dados_pedido['transacoes'] if isinstance(dados_pedido, dict) and 'transacoes' in dados_pedido else dados_pedido
                
                try:
                    print(f"\n[+] Iniciando Pedido OMINI: {pedido}")
                    
                    soma_total = sum([t['ValorMatematico'] for t in transacoes])
                    valor_total_str = f"R$ {soma_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    caixa_laranja = None
                    
                    # PASSO B: Caçar a Caixa Laranja (Esquerda - PDV)
                    for t in transacoes:
                        titulo_teste = t['Titulo']
                        xpath_laranja = f"//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV') and not(.//*[contains(., '{valor_total_str}') and contains(., '{titulo_teste}') and contains(., 'PDV')])]"
                        
                        try:
                            elementos = driver.find_elements(By.XPATH, xpath_laranja)
                            if len(elementos) > 0:
                                caixa_laranja = elementos[0] 
                                print(f"    -> Alvo Travado na Esquerda: {valor_total_str} (Documento: {titulo_teste})")
                                
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
                        
                    # PASSO C: Caçar as Azuis (Direita) - LÓGICA DE TESTE OMINI
                    # Aqui usamos um XPATH que ESPECIFICA "NSU" para travar 100% no lado Direito
                    caixa_azul_para_arrastar = None 
                    for transacao in transacoes:
                        aut_azul = str(transacao['NumeroAutorizacao']).strip()
                        valor_azul = str(transacao['ValorTela']).strip()
                        # Variável alternativa: remove zeros à esquerda para flexibilizar a busca
                        # (ex: "042954" vira "42954") pois o portal pode exibir com ou sem o zero
                        aut_azul_sem_zero = aut_azul.lstrip('0') or '0'
                        
                        try:
                            # NOVA ABORDAGEM MATADORA BASEADA NO CÓDIGO FONTE (Modal com divs draggable):
                            # A caixa Azul (Operadora) agora está em uma estrutura modal com div class="draggable"
                            # Usamos o ID estável da modal (conciliacaoModal) + class draggable para identificar a caixa azul
                            # Isso garante imunidade a mudanças estruturais de índices de div ou li
                            # Flex para Código de Autorização: busca TANTO com zeros à esquerda QUANTO sem
                            xpath_infalivel = f"//*[@id='conciliacaoModal']//div[@class='draggable' and .//td[contains(., '{valor_azul}')] and (.//td[contains(., '{aut_azul}')] or .//td[contains(., '{aut_azul_sem_zero}')])]"
                            
                            caixa_azul = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath_infalivel)))
                            print(f"    -> Alvo Travado na Direita: {valor_azul} (Aut: {aut_azul})")
                            
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_azul)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", caixa_azul)
                            caixa_azul_para_arrastar = caixa_azul
                            time.sleep(0.5)
                        except Exception as e:
                            print(f"    [!] Caixa Azul não encontrada: Valor={valor_azul} Aut={aut_azul}.")
                            caixa_azul_para_arrastar = None
                            break
                        
                    # PASSO D: O ARRASTO FÍSICO COM MICRO MOTIONS + MODAL
                    if caixa_azul_para_arrastar:
                        print(f"    -> Realizando o arraste...")
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", caixa_laranja)
                        time.sleep(1)
                        
                        garra = ActionChains(driver)
                        garra.click_and_hold(caixa_azul_para_arrastar)\
                             .pause(0.5)\
                             .move_to_element_with_offset(caixa_laranja, 5, 5)\
                             .pause(1.5)\
                             .release()\
                             .perform()
                             
                        # ========== LÓGICA DO MODAL PARA OMINI ==========
                        try:
                            print("    -> Aguardando modal de justificativa de data (OMINI)...")
                            textarea = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, "//textarea[contains(@placeholder, 'justificativa') or contains(@placeholder, 'Justificativa') or contains(@class, 'justificativa')]"))
                            )
                            textarea.send_keys("OMINICHANEL CARTAO")
                            time.sleep(0.5)
                            
                            btn_conciliar = driver.find_element(By.XPATH, "//button[contains(text(), 'Conciliar') or contains(., 'Conciliar')]")
                            driver.execute_script("arguments[0].click();", btn_conciliar)
                            print("    -> Justificativa preenchida e confirmada.")
                        except Exception as e:
                            print("    [!] Modal de justificativa não apareceu ou ocorreu um erro extra.")
                        # ================================================
                        
                        print("    -> Aguardando Finanças GB processar... (Até 120s)")
                        try:
                            WebDriverWait(driver, 120).until(EC.staleness_of(caixa_laranja))
                            time.sleep(1)
                        except:
                            print("    [!] A caixa Laranja não foi destruída pela tela no prazo máximo ou houve travamento de UI. Seguindo...")
                            time.sleep(3)
                            
                        print(f"    [SUCESSO] Pedido OMINI {pedido} finalizado!")
                    else:
                        print(f"    [!] Faltou alguma caixa azul para o pedido {pedido}. Drag & drop cancelado.")
                        desmarcar_caixa_laranja(driver, caixa_laranja)

                except Exception as e:
                    print(f"    [!] ERRO: {str(e)[:50]}...")
                    continue

    print("\n🚀 FIM DA FILA OMINI!")
    input("Aperte ENTER para fechar o robô...")
    driver.quit()

else:
    print("\nNenhum pedido OMINI encontrado no relatório. Execução terminada.")
