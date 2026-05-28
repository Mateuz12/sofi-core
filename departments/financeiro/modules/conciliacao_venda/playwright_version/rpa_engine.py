import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

class RPAEngine:
    def __init__(self, headless=False):
        self.headless = headless

    def executar_conciliacao(self, fila_de_trabalho_omini):
        print("\n6. Iniciando Motor do Playwright...")

        # Agrupa por Data, mantendo a mesma logica do script original
        pedidos_omini_por_data = {}
        for p, dados in fila_de_trabalho_omini.items():
            data_raw = pd.to_datetime(dados['DataPedido'], dayfirst=True, errors='coerce')
            data_str = data_raw.strftime('%d/%m/%Y') if pd.notna(data_raw) else 'Sem Data'
            data_sort_key = data_raw if pd.notna(data_raw) else pd.Timestamp.max 
            
            if data_str not in pedidos_omini_por_data:
                pedidos_omini_por_data[data_str] = {'pedidos': {}, 'sort_key': data_sort_key}
            
            if isinstance(pedidos_omini_por_data[data_str], dict) and 'pedidos' in pedidos_omini_por_data[data_str]:
                pedidos_dict = pedidos_omini_por_data[data_str]['pedidos']
                pedidos_dict[p] = dados
                
        # Ordena cronologicamente
        datas_ordenadas = sorted(
            list(pedidos_omini_por_data.keys()), 
            key=lambda d: pedidos_omini_por_data[d].get('sort_key', pd.Timestamp.max) if isinstance(pedidos_omini_por_data[d], dict) else pd.Timestamp.max
        )

        with sync_playwright() as p:
            # Usamos o Chromium para simular o Google Chrome
            browser = p.chromium.launch(headless=self.headless, args=['--start-maximized'])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()

            page.goto("https://financasgb.grupoboticario.com.br/")

            input("\n[AÇÃO MANUAL] Faça o login, carregue a tela com as caixas Laranjas e Azuis e aperte ENTER no terminal...")
            
            print("\n7. Iniciando Conciliação Visual OMINI...")

            for data_atual in datas_ordenadas:
                if isinstance(pedidos_omini_por_data[data_atual], dict) and 'pedidos' in pedidos_omini_por_data[data_atual]:
                    pedidos_da_data = pedidos_omini_por_data[data_atual]['pedidos']
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
                            
                            caixa_laranja_locator = None
                            
                            # PASSO B: Caçar a Caixa Laranja (Esquerda - PDV)
                            for t in transacoes:
                                titulo_teste = t['Titulo']
                                xpath_laranja = f"//*[contains(text(), '{valor_total_str}') or contains(., '{valor_total_str}')][contains(., '{titulo_teste}')][contains(., 'PDV')]"
                                
                                # Tenta pegar apenas o card raiz para não pegar elementos filhos internos
                                xpath_laranja_completo = f"({xpath_laranja})[1]"
                                
                                try:
                                    locator = page.locator(xpath_laranja_completo)
                                    if locator.count() > 0:
                                        caixa_laranja_locator = locator.first
                                        print(f"    -> Alvo Travado na Esquerda: {valor_total_str} (Documento: {titulo_teste})")
                                        
                                        caixa_laranja_locator.scroll_into_view_if_needed()
                                        # Selecionar a caixa laranja via injeção JavaScript (igual ao Selenium original) para burlar overlaps de tela
                                        caixa_laranja_locator.evaluate("node => node.click()")
                                        print("    -> Caixa Laranja selecionada via JS.")
                                        page.wait_for_timeout(1000) # Micro pausa para animação do site
                                        break 
                                except Exception as e:
                                    continue
                                    
                            if not caixa_laranja_locator:
                                print(f"    [!] Caixa Laranja não encontrada para o pedido {pedido}. Pulando.")
                                continue 
                                
                            # PASSO C: Caçar as Azuis (Direita) - LÓGICA DE TESTE OMINI
                            caixa_azul_para_arrastar_locator = None 
                            for transacao in transacoes:
                                aut_azul = str(transacao['NumeroAutorizacao']).strip()
                                valor_azul = str(transacao['ValorTela']).strip()
                                aut_azul_sem_zero = aut_azul.lstrip('0') or '0'
                                
                                try:
                                    # NOVA ABORDAGEM MATADORA BASEADA NO CÓDIGO FONTE DO SELENIUM
                                    xpath_modal = f"//*[@id='conciliacaoModal']//div[contains(@class, 'draggable') and .//td[contains(., '{valor_azul}')] and (.//td[contains(., '{aut_azul}')] or .//td[contains(., '{aut_azul_sem_zero}')])]"
                                    locator_azul = page.locator(xpath_modal)
                                    
                                    if locator_azul.count() > 0:
                                        caixa_azul_para_arrastar_locator = locator_azul.first
                                        print(f"    -> Alvo Travado na Direita (Modal): {valor_azul} (Aut: {aut_azul})")
                                    else:
                                        # Tenta o XPath alternativo do Selenium
                                        xpath_alt = f"//tr[.//td[contains(@data-bind, 'exibirNSU')] and .//td[contains(., '{valor_azul}')] and .//td[contains(., '{aut_azul}')]]"
                                        locator_azul = page.locator(xpath_alt)
                                        if locator_azul.count() > 0:
                                            caixa_azul_para_arrastar_locator = locator_azul.first
                                            print(f"    -> Alvo Travado na Direita (Tabela): {valor_azul} (Aut: {aut_azul})")
                                        
                                    if caixa_azul_para_arrastar_locator:
                                        caixa_azul_para_arrastar_locator.scroll_into_view_if_needed()
                                        caixa_azul_para_arrastar_locator.evaluate("node => node.click()")
                                        page.wait_for_timeout(1000)
                                        break
                                except Exception as e:
                                    print(f"    [!] Erro ao procurar caixa Azul: Valor={valor_azul} Aut={aut_azul}.")
                                    caixa_azul_para_arrastar_locator = None
                                    break
                                
                            # PASSO D: O ARRASTO FÍSICO
                            if caixa_azul_para_arrastar_locator:
                                print(f"    -> Realizando o arraste (Playwright Drag-and-Drop)...")
                                caixa_laranja_locator.scroll_into_view_if_needed()
                                
                                # Playwright executa drag_to super estável nativamente
                                caixa_azul_para_arrastar_locator.drag_to(caixa_laranja_locator)
                                
                                # ========== LÓGICA DO MODAL PARA OMINI ==========
                                try:
                                    print("    -> Aguardando modal de justificativa de data (OMINI)...")
                                    
                                    # Localiza qualquer textarea contendo justificativa e visível
                                    textarea_locator = page.locator("textarea[placeholder*='justificativa' i], textarea.justificativa").locator("visible=true").first
                                    textarea_locator.wait_for(state="visible", timeout=10000)
                                    textarea_locator.fill("OMINICHANEL CARTAO")
                                    
                                    # Localiza o botão "Conciliar"
                                    btn_conciliar = page.locator("button", has_text="Conciliar").locator("visible=true").first
                                    btn_conciliar.click()
                                    print("    -> Justificativa preenchida e confirmada.")
                                except PlaywrightTimeoutError:
                                    print("    [!] Modal de justificativa não apareceu a tempo ou não foi detectada.")
                                except Exception as e:
                                    print(f"    [!] Erro com o Modal de justificativa: {e}")
                                # ================================================
                                
                                print("    -> Aguardando Finanças GB processar... (Até 120s)")
                                try:
                                    # Aguarda que a caixa laranja desapareça do DOM (concluída)
                                    caixa_laranja_locator.wait_for(state="hidden", timeout=120000)
                                    print(f"    [SUCESSO] Pedido OMINI {pedido} finalizado!")
                                except PlaywrightTimeoutError:
                                    print("    [!] A caixa Laranja não foi destruída pela tela no prazo máximo. Seguindo...")
                                    page.wait_for_timeout(3000)
                                    
                            else:
                                print(f"    [!] Faltou alguma caixa azul para o pedido {pedido}. Drag & drop cancelado.")
                                self.desmarcar_caixa_laranja(page, caixa_laranja_locator)

                        except Exception as e:
                            print(f"    [!] ERRO CRÍTICO NO PEDIDO {pedido}: {str(e)[:50]}...")
                            continue

            print("\n🚀 FIM DA FILA OMINI!")
            input("Aperte ENTER para fechar o navegador...")
            browser.close()

    def desmarcar_caixa_laranja(self, page, locator):
        if not locator:
            return
        try:
            locator.scroll_into_view_if_needed()
            locator.click(timeout=2000)
            print("    -> Caixa Laranja desmarcada antes de seguir para o proximo pedido.")
        except Exception as e:
            print(f"    [!] Clique para desmarcar a Caixa Laranja falhou: {str(e)[:50]}...")
            try:
                page.keyboard.press("Escape")
                print("    -> Tentativa extra de limpar selecao enviada com ESC.")
            except Exception as esc_error:
                print(f"    [!] Nao foi possivel limpar a selecao automaticamente.")
