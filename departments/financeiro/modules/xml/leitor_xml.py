import os
import sys
import xml.etree.ElementTree as ET
import openpyxl
from openpyxl.styles import Font
from datetime import datetime
import re
from pathlib import Path
from lxml import etree
import zipfile
import win32com.client

# Localiza a raiz do projeto SOFI-core buscando onde existe o pacote 'core'.
# Não usa .env como marcador pois subpastas também possuem .env local.
_ROOT_L = Path(__file__).resolve().parent
while _ROOT_L != _ROOT_L.parent:
    if (_ROOT_L / "core" / "sofi_env.py").exists():
        break
    _ROOT_L = _ROOT_L.parent
if str(_ROOT_L) not in sys.path:
    sys.path.insert(0, str(_ROOT_L))
from core.database.logger import log_execution

# Configuração de dependências no sys.path para execução independente
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))
caminhos_dependencias = [
    DIRETORIO_ATUAL,
    os.path.join(DIRETORIO_PROJETO, 'SOFI-core', 'modules', 'xml'),
    os.path.join(DIRETORIO_PROJETO, "SCRIPTS RELATORIO XML'S")
]
for caminho in caminhos_dependencias:
    if os.path.exists(caminho) and caminho not in sys.path:
        sys.path.append(caminho)


# Configuração de Ambiente
AMBIENTE_SEFAZ = 1 # 1 = Produção, 2 = Homologação

# Filtro: apenas notas emitidas por fornecedores com esta RAIZ de CNPJ serão processadas
# 06147451 é a raiz da Cálamo (abrange todas as filiais)
RAIZ_CNPJ_EMITENTE_FILTRO = '06147451'

# Mapeamento dinâmico dos CNPJs para o nome da loja, PDV, canal e unidade.
# Os dados são lidos dinamicamente de dentro das planilhas de modelo.
def limpar_cnpj(cnpj_val):
    if not cnpj_val:
        return ""
    if isinstance(cnpj_val, float):
        cnpj_val = str(int(cnpj_val))
    return re.sub(r'\D', '', str(cnpj_val)).strip()

def carregar_mapeamento_lojas():
    import xlrd
    
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_modelos = os.path.join(diretorio_atual, 'modelos_xmls')
    
    mapa_completo = {}
    
    # 1. Carrega BH
    caminho_bh = os.path.join(pasta_modelos, 'MODELO BH.xls')
    if os.path.exists(caminho_bh):
        try:
            wb = xlrd.open_workbook(caminho_bh)
            sheet = wb.sheet_by_name('NOMECLATURA LOJAS')
            for r in range(1, sheet.nrows):
                row = sheet.row_values(r)
                if len(row) >= 4:
                    pdv = str(int(float(row[0]))) if isinstance(row[0], (int, float)) else str(row[0]).strip()
                    nomenclatura = str(row[1]).strip()
                    canal = str(row[2]).strip()
                    cnpj = limpar_cnpj(row[3])
                    if cnpj:
                        mapa_completo[cnpj] = {
                            'PDV': pdv,
                            'Nomenclatura': nomenclatura,
                            'Canal': canal,
                            'Unidade': 'BH'
                        }
        except Exception as e:
            print(f"Erro ao carregar nomenclaturas de BH a partir do modelo: {e}")
            
    # 2. Carrega UDI
    caminho_udi = os.path.join(pasta_modelos, 'MODELO UDI.xls')
    if os.path.exists(caminho_udi):
        try:
            wb = xlrd.open_workbook(caminho_udi)
            sheet = wb.sheet_by_name('Nomeclatura Lojas')
            for r in range(1, sheet.nrows):
                row = sheet.row_values(r)
                if len(row) >= 4:
                    pdv = str(int(float(row[0]))) if isinstance(row[0], (int, float)) else str(row[0]).strip()
                    nomenclatura = str(row[1]).strip()
                    canal = str(row[2]).strip()
                    cnpj = limpar_cnpj(row[3])
                    if cnpj:
                        mapa_completo[cnpj] = {
                            'PDV': pdv,
                            'Nomenclatura': nomenclatura,
                            'Canal': canal,
                            'Unidade': 'UDI'
                        }
        except Exception as e:
            print(f"Erro ao carregar nomenclaturas de UDI a partir do modelo: {e}")
            
    return mapa_completo

# Carrega o mapa dinamicamente
LOJAS_MAP_DINAMICO = carregar_mapeamento_lojas()

# Mantém a variável LOJAS_MAP legada para compatibilidade com outros módulos do projeto
LOJAS_MAP = {cnpj: info['Nomenclatura'] for cnpj, info in LOJAS_MAP_DINAMICO.items()}

def eh_emitido_por_calamo(caminho_xml):
    import xml.etree.ElementTree as ET
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        tree = ET.parse(caminho_xml)
        root = tree.getroot()
        infNFe = root.find('.//nfe:infNFe', ns)
        if infNFe is None:
            infNFe = root.find('.//infNFe')
            ns = {'nfe': ''} 
            if infNFe is None: return False
        
        cnpj_emit = infNFe.find('.//nfe:emit/nfe:CNPJ', ns) if ns['nfe'] else infNFe.find('.//emit/CNPJ')
        # A raiz do CNPJ da Cálamo é 06147451
        if cnpj_emit is not None and cnpj_emit.text and cnpj_emit.text.startswith('06147451'):
            return True
        return False
    except Exception:
        return False

def formatar_data(data_str):
    if not data_str:
        return ""
    try:
        data_limpa = data_str.split('T')[0]
        data_obj = datetime.strptime(data_limpa, '%Y-%m-%d')
        return data_obj.strftime('%d/%m/%Y')
    except Exception:
        return data_str

def para_float(valor_str):
    try:
        return float(valor_str)
    except Exception:
        return 0.0

def para_int(valor_str):
    try:
        return int(valor_str)
    except Exception:
        return valor_str

def extrair_dados_xml(caminho_xml):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        tree = ET.parse(caminho_xml)
        root = tree.getroot()
        
        infNFe = root.find('.//nfe:infNFe', ns)
        if infNFe is None:
            infNFe = root.find('.//infNFe')
            ns = {'nfe': ''} 
            if infNFe is None: return None

        # Removido filtro de RAIZ_CNPJ_EMITENTE_FILTRO para aceitar todas as notas baixadas
        cnpj_emit = infNFe.find('.//nfe:emit/nfe:CNPJ', ns) if ns['nfe'] else infNFe.find('.//emit/CNPJ')
                
        nosso_pedido = ""
        infCpl = infNFe.find('.//nfe:infAdic/nfe:infCpl', ns) if ns['nfe'] else infNFe.find('.//infAdic/infCpl')
        if infCpl is not None and infCpl.text:
            match = re.search(r'Remessa\.:\s*([^/]+)', infCpl.text)
            if match:
                nosso_pedido = para_int(match.group(1).strip())

        destinatario = ""
        pdv = ""
        canal = ""
        unidade = ""
        nomenclatura = ""
        cnpj_limpo = ""
        
        cnpj_dest = infNFe.find('.//nfe:dest/nfe:CNPJ', ns) if ns['nfe'] else infNFe.find('.//dest/CNPJ')
        nome_dest = infNFe.find('.//nfe:dest/nfe:xNome', ns) if ns['nfe'] else infNFe.find('.//dest/xNome')
        
        if cnpj_dest is not None:
            cnpj_limpo = limpar_cnpj(cnpj_dest.text)
            info_loja = LOJAS_MAP_DINAMICO.get(cnpj_limpo)
            if info_loja:
                destinatario = info_loja['Nomenclatura']
                pdv = info_loja['PDV']
                canal = info_loja['Canal']
                unidade = info_loja['Unidade']
                nomenclatura = info_loja['Nomenclatura']
            else:
                destinatario = f"CNPJ: {cnpj_dest.text} - Nome: {nome_dest.text if nome_dest is not None else ''}"
                # Tentativa de inferir unidade pela raiz do CNPJ caso não esteja mapeada
                if cnpj_limpo.startswith('03982400'):
                    unidade = 'BH'
                elif cnpj_limpo.startswith('20798658'):
                    unidade = 'UDI'
        elif nome_dest is not None:
            destinatario = nome_dest.text

        dt_emissao = ""
        dhEmi = infNFe.find('.//nfe:ide/nfe:dhEmi', ns) if ns['nfe'] else infNFe.find('.//ide/dhEmi')
        if dhEmi is not None: dt_emissao = formatar_data(dhEmi.text)
            
        dt_vencimento = ""
        dVenc = infNFe.find('.//nfe:cobr/nfe:dup/nfe:dVenc', ns) if ns['nfe'] else infNFe.find('.//cobr/dup/dVenc')
        if dVenc is not None: 
            dt_vencimento = formatar_data(dVenc.text)
            
            # Validação e Correção de Data de Vencimento Invertida (Dia/Mês)
            if dt_emissao and dt_vencimento:
                try:
                    obj_emi = datetime.strptime(dt_emissao, '%d/%m/%Y')
                    obj_venc = datetime.strptime(dt_vencimento, '%d/%m/%Y')
                    
                    # Se o vencimento for anterior à emissão, inverte dia e mês
                    if obj_venc < obj_emi:
                        partes = dt_vencimento.split('/')
                        if len(partes) == 3:
                            dia, mes, ano = partes
                            dt_venc_invertida = f"{mes}/{dia}/{ano}"
                            obj_venc_invertido = datetime.strptime(dt_venc_invertida, '%d/%m/%Y')
                            if obj_venc_invertido >= obj_emi:
                                dt_vencimento = dt_venc_invertida
                except Exception:
                    pass

        n_doc = ""
        nNF = infNFe.find('.//nfe:ide/nfe:nNF', ns) if ns['nfe'] else infNFe.find('.//ide/nNF')
        if nNF is not None: n_doc = para_int(nNF.text)
            
        v_prod = 0.0
        vProd = infNFe.find('.//nfe:total/nfe:ICMSTot/nfe:vProd', ns) if ns['nfe'] else infNFe.find('.//total/ICMSTot/vProd')
        if vProd is not None: v_prod = para_float(vProd.text)

        v_doc = 0.0
        vNF = infNFe.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns) if ns['nfe'] else infNFe.find('.//total/ICMSTot/vNF')
        if vNF is not None: v_doc = para_float(vNF.text)

        return {
            'Nº DOC': n_doc,
            'Arquivo_Original': os.path.basename(caminho_xml),
            'CMV': '',
            'TRF': '',
            'REM': '',
            'Nosso Pedido': nosso_pedido,
            'Destinatário': destinatario,
            'Dt. Emissão': dt_emissao,
            'Dt. Vencimento': dt_vencimento,
            'Total Itens/Merc.': v_prod,
            'Total do Documento': v_doc,
            'PDV': pdv,
            'Canal': canal,
            'Unidade': unidade,
            'Nomenclatura': nomenclatura,
            'CNPJ_Dest': cnpj_limpo
        }

    except Exception as e:
        print(f"Erro ao processar {caminho_xml}: {e}")
        return None

def encontrar_primeira_linha_nula(sheet, col_index=1, start_row=4):
    """Procura a primeira linha vazia em uma coluna específica da planilha."""
    for row in range(start_row, sheet.max_row + 2):
        val = sheet.cell(row=row, column=col_index).value
        if val is None or str(val).strip() == "":
            return row
    return sheet.max_row + 1

@log_execution(modulo="XML (Leitor)")
def main():
    print("--- Iniciando Extração de XMLs da SEFAZ (Modo NSU) ---")
    try:
        from extrator_sefaz import loop_extracao
        loop_extracao(LOJAS_MAP, ambiente=AMBIENTE_SEFAZ)
    except Exception as e:
        print(f"Erro na extração automática: {e}")
    print("--- Fim da Extração ---\n")
    
    gerar_relatorio()

def gerar_relatorio():
    """Lê os XMLs da pasta 'xmls_recebidos' e gera a planilha final baseada no modelo."""
    pasta_xml = 'xmls_recebidos'
    if not os.path.exists(pasta_xml):
        os.makedirs(pasta_xml)
        print(f"Pasta '{pasta_xml}' pronta. Nenhum XML para processar.")
        return

    arquivos = [f for f in os.listdir(pasta_xml) if f.lower().endswith('.xml')]
    if not arquivos:
        print("Nenhum arquivo XML encontrado em 'xmls_recebidos' para processar.")
        return

    nome_modelo = "modelo.xlsx"
    if not os.path.exists(nome_modelo):
        print(f"ERRO: Não encontrei o arquivo {nome_modelo} na pasta raiz.")
        return

    print(f"Processando {len(arquivos)} XMLs e inserindo no modelo...")
    try:
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.load_workbook(nome_modelo)
        sheet = wb.active
        
        # Antes de escrever, devemos desmesclar todas as celulas para evitar o erro de MergedCell
        todas_mescladas = list(sheet.merged_cells.ranges)
        for m in todas_mescladas:
            sheet.unmerge_cells(str(m))

        from openpyxl.styles import Font, Alignment
        from openpyxl.styles.borders import Border, Side
        
        linha_atual = encontrar_primeira_linha_nula(sheet, col_index=6, start_row=4)

        todos_dados = []
        for arquivo in arquivos:
            caminho_completo = os.path.join(pasta_xml, arquivo)
            dados = extrair_dados_xml(caminho_completo)
            if dados:
                todos_dados.append(dados)

        ordem_desejada = [
            "20843", "20844", "20845", "20846", "21056", "21057", "21058", "21059", 
            "21060", "21061", "21062", "21207", "21274", "22631", "22844", "23252", 
            "23263", "23264", "23269", "23275", "24417"
        ]

        def get_ordem(d):
            destinatario = str(d.get('Destinatário', ''))
            match = re.search(r'^(\d+)', destinatario)
            if match:
                prefixo = match.group(1)
                if prefixo == "22744": prefixo = "22844"
                if prefixo in ordem_desejada: return ordem_desejada.index(prefixo)
            return 9999

        todos_dados.sort(key=get_ordem)

        fonte_padrao = Font(name='Calibri', size=9, bold=True)
        borda_fina = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)

        for dados in todos_dados:
            for col in range(1, 12):
                c = sheet.cell(row=linha_atual, column=col)
                c.font = fonte_padrao
                c.border = borda_fina
                c.alignment = align_left

            sheet.cell(row=linha_atual, column=1, value=dados['Nº DOC'])
            sheet.cell(row=linha_atual, column=2, value=dados['Nosso Pedido'])
            sheet.cell(row=linha_atual, column=3, value=dados['CMV'])
            sheet.cell(row=linha_atual, column=4, value=dados['TRF'])
            sheet.cell(row=linha_atual, column=5, value=dados['REM'])
            sheet.cell(row=linha_atual, column=6, value=dados['Destinatário'])
            
            c7 = sheet.cell(row=linha_atual, column=7, value=dados['Dt. Emissão'])
            c7.number_format = '@'
            
            c8 = sheet.cell(row=linha_atual, column=8, value=dados['Dt. Vencimento'])
            c8.number_format = '@'
            c8.alignment = align_center
            
            c10 = sheet.cell(row=linha_atual, column=10, value=dados['Total Itens/Merc.'])
            c10.number_format = 'R$ #,##0.00'
            c10.alignment = align_right
            
            c11 = sheet.cell(row=linha_atual, column=11, value=dados['Total do Documento'])
            c11.number_format = 'R$ #,##0.00'
            c11.alignment = align_right
            
            sheet.merge_cells(start_row=linha_atual, start_column=8, end_row=linha_atual, end_column=9)
            linha_atual += 1

        # Restaura as mesclagens antigas que estavam ACIMA da tabela
        for m in todas_mescladas:
            # linha 4 eh onde comecam os dados
            if m.max_row < 4:
                try: sheet.merge_cells(str(m))
                except: pass

        arquivo_saida = "Relatorio_Final_" + datetime.now().strftime("%d-%m-%Y") + ".xlsx"
        wb.save(arquivo_saida)
        print(f"Sucesso! Relatório gerado: {arquivo_saida}")

    except Exception as e:
        print("Erro ao atualizar a planilha:", e)


if __name__ == '__main__':
    main()
