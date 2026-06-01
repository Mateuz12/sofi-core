"""
Script para captura automática de Bearer Token e Cookie usando Playwright.
E teste de exclusão de depósito via API conforme endpoint fornecido.
"""

import os
import sys
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

# Carrega o .env global do SOFI
# Carrega o .env global do SOFI + .env.local do departamento
_ROOT = Path(__file__).resolve()
while not (_ROOT / ".env").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

# Configurações de acesso
EMAIL = os.getenv("FINANCAS_UDI_USER")
SENHA = os.getenv("FINANCAS_UDI_PASS")
URL_LOGIN = os.getenv("FINANCAS_URL")

if not all([EMAIL, SENHA, URL_LOGIN]):
    print("ERRO: As variáveis FINANCAS_UDI_USER, FINANCAS_UDI_PASS ou FINANCAS_URL nao foram encontradas no .env.")
    print("Por favor, preencha o arquivo .env com essas credenciais antes de continuar.")
    sys.exit(1)

# Variáveis globais para armazenar os tokens capturados
auth_data = {
    "bearer": None,
    "cookie": None
}

DOMINIO_API = "financasgb.grupoboticario.com.br"

def interceptar_request(request):
    """
    Intercepta TODAS as requisições feitas pelo navegador.
    - Bearer: captura de qualquer requisição que envie Authorization.
    - Cookie: captura especificamente de requisições ao domínio da API de finanças.
    """
    headers = request.headers
    url = request.url
    
    # Busca o Bearer Token em qualquer requisição
    authorization = headers.get("authorization", "")
    if authorization and "bearer" in authorization.lower():
        auth_data["bearer"] = authorization
        print(f"  🔑 [BEARER CAPTURADO] em requisição para: {url[:80]}...")
        
    # Busca o Cookie em requisições para o domínio da API de finanças
    cookie = headers.get("cookie", "")
    if cookie and DOMINIO_API in url:
        auth_data["cookie"] = cookie
        print(f"  🍪 [COOKIE CAPTURADO] em requisição para: {url[:80]}...")


def capturar_autenticacao():
    """
    Realiza o fluxo de navegação passo a passo usando Playwright para capturar os tokens.
    """
    print("Iniciando captura de tokens com Playwright...")
    with sync_playwright() as p:
        # Abrindo o navegador visível para conseguir ver o processo e eventuais captchas
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Inicia a interceptação de REQUESTS para pegar os headers enviados pelo navegador
        page.on("request", interceptar_request)
        
        # 1. Acessa a página de login do portal lida do .env
        url_login = URL_LOGIN
        try:
            page.goto(url_login)
        except Exception as e:
            print(f"Erro ao acessar página de login: {e}")
            print("Por favor, atualize a variável 'url_login' no script.")
        
        print("Preenchendo credenciais...")
        # xpath email: //*[@id="email"]
        page.locator('//*[@id="email"]').fill(EMAIL)
        
        # xpath senha: //*[@id="input-button-icon-right"]
        page.locator('//*[@id="input-button-icon-right"]').fill(SENHA)
        
        print("Aguardando 10 segundos antes de clicar em Entrar para evitar captchas...")
        time.sleep(10)
        
        # xpath botão entrar: //*[@id="login-root"]/div/div/div[2]/div/div/form/button
        print("Clicando em Entrar...")
        page.locator('//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()
        
        # ---------------------------------------------------------------
        # Tratamento da tela "Acesso em Andamento"
        # Após o login, pode aparecer uma página intermediária pedindo
        # para clicar em "Continuar". Precisamos esperar o carregamento
        # e verificar se essa tela apareceu.
        # ---------------------------------------------------------------
        print("Aguardando carregamento pós-login...")
        time.sleep(8)
        
        # Tenta encontrar o botão "Continuar" de várias formas
        botao_continuar_encontrado = False
        seletores_continuar = [
            "button:has-text('Continuar')",
            "button:has-text('continuar')",
            "text='Continuar'",
            "text='continuar'",
            "a:has-text('Continuar')",
            "input[value='Continuar']",
        ]
        
        for seletor in seletores_continuar:
            try:
                elemento = page.locator(seletor).first
                if elemento.is_visible(timeout=3000):
                    elemento.click()
                    botao_continuar_encontrado = True
                    print("✅ Página de 'Acesso em Andamento' detectada. Botão 'Continuar' clicado.")
                    print("Aguardando portal carregar completamente...")
                    try:
                        page.wait_for_load_state("networkidle", timeout=60000)
                    except Exception:
                        pass  # Se der timeout, continua mesmo assim
                    time.sleep(8)  # Espera extra para o portal renderizar
                    break
            except Exception:
                continue
        
        if not botao_continuar_encontrado:
            print("ℹ️ Nenhuma tela de 'Acesso em Andamento' detectada. Seguindo direto.")
        
        # Espera geral para garantir que o portal está pronto
        print("Aguardando portal estabilizar...")
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        time.sleep(5)
        
        # ---------------------------------------------------------------
        # Navegação até Fechamento de Caixa
        # ---------------------------------------------------------------
        print("Aguardando menu lateral carregar...")
        # O sidebar pode começar oculto e aparecer gradualmente.
        # Esperamos ele existir no DOM primeiro, depois o link dentro dele ficar visível.
        page.wait_for_selector('//*[@id="mfe-sidebar-react"]', state="attached", timeout=60000)
        time.sleep(3)
        
        print("Acessando Fechamento de caixa...")
        menu_fc = page.locator('//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[2]/a')
        # Espera até 30s pelo link ficar clicável
        menu_fc.wait_for(state="visible", timeout=30000)
        menu_fc.click()
        
        # Espera a tela de Fechamento de Caixa carregar
        print("Aguardando tela de Fechamento de Caixa carregar...")
        page.wait_for_selector('//*[@id="novo-layout-filtros"]', timeout=30000)
        # Espera o portal estabilizar completamente antes de mexer no dropdown
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        time.sleep(8)  # Espera extra para os componentes Kendo renderizarem
        
        # ---------------------------------------------------------------
        # Selecionar a loja
        # O dropdown é um componente Kendo UI. O clique normal nem sempre
        # abre a lista. Usamos retry com múltiplas estratégias.
        # ---------------------------------------------------------------
        dropdown_aberto = False
        MAX_TENTATIVAS = 3
        
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            print(f"Abrindo lista de lojas... (tentativa {tentativa}/{MAX_TENTATIVAS})")
            
            # Estratégia 1: Clicar no span do filtro (xpath original)
            try:
                btn_lojas = page.locator('//*[@id="novo-layout-filtros"]/div/div[1]/span/span/span')
                btn_lojas.wait_for(state="visible", timeout=10000)
                btn_lojas.click()
                time.sleep(3)
                if page.locator("li:has-text('20843')").first.is_visible(timeout=3000):
                    dropdown_aberto = True
                    break
            except Exception:
                pass
                
            # Estratégia 2: Clicar na seta do dropdown Kendo
            print("  ⚠️ Tentando abrir dropdown pela seta Kendo...")
            try:
                seta = page.locator('//*[@id="novo-layout-filtros"] span.k-select').first
                seta.click()
                time.sleep(3)
                if page.locator("li:has-text('20843')").first.is_visible(timeout=3000):
                    dropdown_aberto = True
                    break
            except Exception:
                pass
                
            # Estratégia 3: Forçar abertura via JavaScript
            print("  ⚠️ Tentando abrir dropdown via JavaScript...")
            try:
                page.evaluate("""
                    () => {
                        const widget = $('[data-role="dropdownlist"]').first().data('kendoDropDownList');
                        if (widget) { widget.open(); }
                        else {
                            const el = document.querySelector('#novo-layout-filtros span.k-input');
                            if (el) el.click();
                        }
                    }
                """)
                time.sleep(3)
                if page.locator("li:has-text('20843')").first.is_visible(timeout=3000):
                    dropdown_aberto = True
                    break
            except Exception:
                pass
            
            # Se não conseguiu, espera mais e tenta de novo
            if tentativa < MAX_TENTATIVAS:
                print(f"  ⏳ Aguardando mais 5s antes da próxima tentativa...")
                time.sleep(5)
                
        if not dropdown_aberto:
            print("  ❌ Não foi possível abrir a lista de lojas.")
            browser.close()
            return None, None
            
        print("  ✅ Lista de lojas aberta!")
        
        # Agora seleciona a loja 20843
        print("Selecionando a loja 20843 - UDI SH...")
        try:
            loja_udi = page.locator("li:has-text('20843')").first
            loja_udi.scroll_into_view_if_needed()
            loja_udi.click()
        except Exception as e:
            print(f"  ❌ Não foi possível selecionar a loja: {e}")
            browser.close()
            return None, None
        
        # Espera o calendário carregar após selecionar a loja
        print("Aguardando calendário carregar...")
        page.wait_for_selector('//*[@id="calendarVendas"]', timeout=30000)
        time.sleep(3)
        
        print("Dando duplo clique em um dia do calendário para gerar os cookies...")
        dia_calendario = page.locator('//*[@id="calendarVendas"]/div/div/table/tbody/tr[2]/td[5]/div/div[2]/div/div')
        dia_calendario.wait_for(state="visible", timeout=15000)
        dia_calendario.dblclick()
        
        # Espera a requisição ObterDepositosDoDia ser disparada
        print("Aguardando requisição ObterDepositosDoDia...")
        time.sleep(5)
        
        # ---------------------------------------------------------------
        # Captura do Cookie via contexto do navegador
        # Os cookies gerenciados pelo browser nem sempre aparecem nos
        # headers interceptados. A forma mais confiável é extrair
        # diretamente do contexto do Playwright.
        # ---------------------------------------------------------------
        print("Extraindo cookies do navegador...")
        todos_cookies = context.cookies()
        
        # Filtra cookies do domínio financasgb
        cookies_financas = [
            c for c in todos_cookies 
            if DOMINIO_API in c.get("domain", "")
        ]
        
        if cookies_financas:
            # Monta a string de cookie no formato "nome=valor; nome2=valor2"
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_financas])
            auth_data["cookie"] = cookie_str
            print(f"  🍪 [COOKIE CAPTURADO] {len(cookies_financas)} cookies do domínio {DOMINIO_API}")
        else:
            # Se não encontrou do domínio específico, pega todos os cookies como fallback
            print("  ⚠️ Nenhum cookie específico do domínio financasgb encontrado.")
            print(f"  ℹ️ Total de cookies no navegador: {len(todos_cookies)}")
            # Mostra os domínios disponíveis para debug
            dominios = set(c.get("domain", "?") for c in todos_cookies)
            print(f"  ℹ️ Domínios encontrados: {dominios}")
            
            # Tenta pegar todos os cookies como string
            if todos_cookies:
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in todos_cookies])
                auth_data["cookie"] = cookie_str
                print(f"  🍪 [COOKIE FALLBACK] Usando {len(todos_cookies)} cookies de todos os domínios")
        
        browser.close()
        
    print("\nNavegação concluída.")
    if auth_data["bearer"] and auth_data["cookie"]:
        print("✅ Bearer e Cookie capturados com sucesso!")
        print(f"   Bearer: {auth_data['bearer'][:30]}...")
        print(f"   Cookie: {auth_data['cookie'][:60]}...")
        return auth_data["bearer"], auth_data["cookie"]
    else:
        capturou = []
        if auth_data["bearer"]: capturou.append("Bearer ✅")
        else: capturou.append("Bearer ❌")
        if auth_data["cookie"]: capturou.append("Cookie ✅")
        else: capturou.append("Cookie ❌")
        print(f"❌ Captura incompleta: {', '.join(capturou)}")
        return None, None


def excluir_deposito(bearer, cookie, id_deposito, id_loja):
    """
    Função que consome o endpoint de Excluir Depósito, com o payload sendo o id da loja.
    """
    print(f"\nIniciando exclusão do depósito ID: {id_deposito}")
    
    endpoint_exclusao = f"https://financasgb.grupoboticario.com.br/FechamentoDeCaixaAPI/ExcluirDeposito/?id={id_deposito}"
    
    headers = {
        "Authorization": bearer,
        "Cookie": cookie,
        "Content-Type": "application/json"
    }
    
    # De acordo com as instruções: Com payload: id "id da loja"
    payload = {
        "id": id_loja
    }
    
    try:
        response = requests.post(endpoint_exclusao, json=payload, headers=headers)
        
        if response.status_code in [200, 204]:
            print(f"✅ Depósito {id_deposito} excluído com sucesso (Status: {response.status_code}).")
        else:
            print(f"⚠️ Resposta da API ao tentar excluir (Status: {response.status_code}): {response.text}")
    except Exception as e:
         print(f"❌ Erro ao tentar excluir depósito: {e}")


if __name__ == "__main__":
    print("="*50)
    print("   TESTE DE CAPTURA DE TOKEN E EXCLUSÃO")
    print("="*50)
    
    # 1. Captura manual guiada por código
    bearer, cookie = capturar_autenticacao()
    
    if bearer and cookie:
        # Exemplo de uso do endpoint fornecido na solicitação
        # id_exemplo = "69fde6b3143a0840497c5e00"
        # id_loja_udi = 20843 # (Ou o ID UUID que representa a loja UDI SH na API, caso não seja o número curto)
        
        print("\nPara testar a exclusão de fato, tire o comentário das linhas abaixo no código.")
        # excluir_deposito(bearer, cookie, id_exemplo, id_loja_udi)
        
    print("\nFinalizado.")
