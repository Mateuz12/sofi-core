import os
import sys
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import win32com.client

# Importa o conversor de XMLs para o padrão SEFAZ
try:
    from conversor_xml_sefaz import converter_pasta as _converter_pasta_sefaz
    _CONVERSOR_DISPONIVEL = True
except ImportError:
    _CONVERSOR_DISPONIVEL = False
    print("AVISO: conversor_xml_sefaz.py não encontrado. XMLs não serão convertidas para o padrão SEFAZ.")

# Configura diretórios no sys.path para importações locais e dependências
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
# A pasta principal PROJETO fica dois níveis acima
DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

caminhos_dependencias = [
    DIRETORIO_ATUAL,
    os.path.join(DIRETORIO_PROJETO, 'SOFI-core', 'departments', 'financeiro', 'modules', 'xml'),
]

for caminho in caminhos_dependencias:
    if os.path.exists(caminho) and caminho not in sys.path:
        sys.path.append(caminho)

# Importa as funções do leitor_xml
try:
    from leitor_xml import extrair_dados_xml, limpar_cnpj
except ImportError as e:
    print(f"Erro ao importar dependências do 'leitor_xml.py': {e}")
    sys.exit(1)

try:
    from gerador_relatorio_detalhado import processar_relatorios_detalhados
except ImportError:
    try:
        from departments.financeiro.modules.xml.gerador_relatorio_detalhado import processar_relatorios_detalhados
    except ImportError:
        processar_relatorios_detalhados = None

# Localiza a raiz do projeto SOFI-core buscando onde existe o pacote 'core'.
# Não usa .env como marcador pois subpastas também possuem .env local.
_ROOT = Path(__file__).resolve().parent
while _ROOT != _ROOT.parent:
    if (_ROOT / "core" / "sofi_env.py").exists():
        break
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.database.logger import log_execution

# Mapeamento do número do mês para o nome em português
MESES_MAP = {
    1: "01 - Janeiro", 2: "02 - Fevereiro", 3: "03 - Março", 4: "04 - Abril",
    5: "05 - Maio", 6: "06 - Junho", 7: "07 - Julho", 8: "08 - Agosto",
    9: "09 - Setembro", 10: "10 - Outubro", 11: "11 - Novembro", 12: "12 - Dezembro"
}

MESES_NOME_UPPER = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
    5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
    9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
}

def carregar_regras_prazo():
    """Carrega as regras de prazo de pagamento via ConfigManager (YAML), com fallback para regras_prazo.txt."""
    try:
        from core.config.config_manager import ConfigManager
        prazos_dict = ConfigManager().get_pdv_prazos()
        if prazos_dict:
            regras = {}
            for k, v in prazos_dict.items():
                if k.lower() == "default":
                    regras["DEFAULT"] = int(v)
                else:
                    regras[str(k)] = int(v)
            if "DEFAULT" not in regras:
                regras["DEFAULT"] = 45
            return regras
    except Exception as e:
        print(f"[Aviso] ConfigManager indisponivel em carregar_regras_prazo: {e}")

    caminho = os.path.join(DIRETORIO_ATUAL, 'regras_prazo.txt')
    regras = {'DEFAULT': 45}
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        try:
                            regras[k] = int(v)
                        except ValueError:
                            pass
        except Exception as e:
            print(f"Erro ao carregar regras de prazo: {e}")
    return regras

def obter_ordem_lojas(caminho_modelo, aba_nomenclatura):
    """Carrega dinamicamente a ordem dos PDVs conforme aparecem no modelo."""
    import xlrd
    ordem = []
    if os.path.exists(caminho_modelo):
        try:
            wb = xlrd.open_workbook(caminho_modelo)
            sheet = wb.sheet_by_name(aba_nomenclatura)
            for r in range(1, sheet.nrows):
                val = sheet.cell_value(r, 0)
                pdv = str(int(float(val))) if isinstance(val, (int, float)) else str(val).strip()
                if pdv and pdv not in ordem:
                    ordem.append(pdv)
        except Exception as e:
            print(f"Erro ao obter ordem das lojas do modelo {os.path.basename(caminho_modelo)}: {e}")
    return ordem

def ajustar_larguras_colunas(excel, sheet):
    """Ajusta as larguras das colunas conforme as dimensões exatas especificadas.
    A: 6.29
    B/C/D: 4
    E: 19.71
    F: 10.43
    G/H: 5.43 CADA
    I: 4.71
    J: 6.86
    K: 11.43
    L: 11.57
    """
    larguras = {
        1: 6.29,   # A
        2: 4,      # B (CMV)
        3: 4,      # C (TRF)
        4: 4,      # D (REM)
        5: 19.71,  # E
        6: 11.43,  # F (Dt. Emissão)
        7: 5.43,   # G (Dt. Vencimento)
        8: 5.43,   # H (Dt. Vencimento)
        9: 4.71,   # I (Prazo de Pagamento)
        10: 6.86,  # J (Detalhe do Prazo)
        11: 11.43, # K (Total Itens/Merc)
        12: 11.57, # L (Total do Documento)
    }
    for col_idx, width_val in larguras.items():
        sheet.Columns(col_idx).ColumnWidth = width_val

def carregar_notas_existentes_semana(saida_geral, saida_matheus, unidade):
    """
    Carrega as notas fiscais previamente gravadas nos relatórios da semana
    (saida_geral e saida_matheus), permitindo acumular faturamentos novos sem sobrescrever.
    """
    import xlrd
    notas_existentes = []
    mapa_pedidos = {}

    # 1. Tenta ler os números de pedido da aba 'Notas Fiscais' do relatório do Matheus (se existir)
    if os.path.exists(saida_matheus):
        try:
            wb_m = xlrd.open_workbook(saida_matheus)
            if 'Notas Fiscais' in wb_m.sheet_names():
                sheet_m = wb_m.sheet_by_name('Notas Fiscais')
                start_col = 0 if unidade == "BH" else 5
                for r in range(3, sheet_m.nrows):
                    val_pdv = sheet_m.cell_value(r, start_col)
                    val_nf = sheet_m.cell_value(r, start_col + 3)
                    val_ped = sheet_m.cell_value(r, start_col + 4)
                    
                    if str(val_pdv).strip() != "" and str(val_nf).strip() != "":
                        pdv_s = str(int(val_pdv)) if isinstance(val_pdv, (int, float)) else str(val_pdv).strip()
                        nf_s = str(int(val_nf)) if isinstance(val_nf, (int, float)) else str(val_nf).strip()
                        ped_s = int(val_ped) if isinstance(val_ped, float) and val_ped.is_integer() else val_ped
                        mapa_pedidos[(pdv_s, nf_s)] = ped_s
        except Exception as e:
            print(f"[{unidade}] Aviso ao carregar pedidos do relatório do Matheus: {e}")

    # 2. Lê os registros da aba 'Base' do relatório Geral (se existir)
    if os.path.exists(saida_geral):
        try:
            wb_g = xlrd.open_workbook(saida_geral)
            if 'Base' in wb_g.sheet_names():
                sheet_b = wb_g.sheet_by_name('Base')
                for r in range(1, sheet_b.nrows):
                    val_pdv = sheet_b.cell_value(r, 0)
                    val_ndoc = sheet_b.cell_value(r, 3)

                    if str(val_pdv).strip() == "" and str(val_ndoc).strip() == "":
                        continue

                    pdv_str = str(int(val_pdv)) if isinstance(val_pdv, (int, float)) else str(val_pdv).strip()
                    ndoc_str = str(int(val_ndoc)) if isinstance(val_ndoc, (int, float)) else str(val_ndoc).strip()

                    canal = str(sheet_b.cell_value(r, 5)).strip() if sheet_b.ncols > 5 else 'LOJA'
                    dt_emissao = str(sheet_b.cell_value(r, 7)).strip() if sheet_b.ncols > 7 else ''
                    dt_venc = str(sheet_b.cell_value(r, 8)).strip() if sheet_b.ncols > 8 else ''

                    # Converte formato de data serial do Excel se necessário
                    if isinstance(sheet_b.cell_value(r, 7), float):
                        try:
                            dt_t = xlrd.xldate_as_tuple(sheet_b.cell_value(r, 7), wb_g.datemode)
                            dt_emissao = f"{dt_t[2]:02d}/{dt_t[1]:02d}/{dt_t[0]}"
                        except Exception:
                            pass

                    if isinstance(sheet_b.cell_value(r, 8), float):
                        try:
                            dt_t = xlrd.xldate_as_tuple(sheet_b.cell_value(r, 8), wb_g.datemode)
                            dt_venc = f"{dt_t[2]:02d}/{dt_t[1]:02d}/{dt_t[0]}"
                        except Exception:
                            pass

                    val_tot_itens = sheet_b.cell_value(r, 19) if sheet_b.ncols > 19 else 0.0
                    val_tot_doc = sheet_b.cell_value(r, 23) if sheet_b.ncols > 23 else 0.0

                    try: tot_itens = float(val_tot_itens)
                    except: tot_itens = 0.0

                    try: tot_doc = float(val_tot_doc)
                    except: tot_doc = 0.0

                    ped_val = mapa_pedidos.get((pdv_str, ndoc_str), '')

                    nota = {
                        'Nº DOC': int(ndoc_str) if ndoc_str.isdigit() else ndoc_str,
                        'PDV': int(pdv_str) if pdv_str.isdigit() else pdv_str,
                        'Canal': canal,
                        'Dt. Emissão': dt_emissao,
                        'Dt. Vencimento': dt_venc,
                        'Total Itens/Merc.': tot_itens,
                        'Total do Documento': tot_doc,
                        'Nosso Pedido': ped_val,
                        'Unidade': unidade,
                    }
                    notas_existentes.append(nota)
        except Exception as e:
            print(f"[{unidade}] Aviso ao carregar notas do relatório geral existente: {e}")

    return notas_existentes

def processar_relatorio_geral(unidade, notas, caminho_modelo, caminho_saida):
    """Preenche a aba Base e gera a aba Notas Fiscais dinamicamente mantendo formatação e fórmulas do modelo."""
    if not notas:
        print(f"[{unidade}] Nenhuma nota fiscal encontrada. Relatório Geral não gerado.")
        return
        
    print(f"[{unidade}] Iniciando preenchimento do Relatório Geral...")
    regras_prazo = carregar_regras_prazo()
    
    # Inicializa Excel COM — DispatchEx sempre cria nova instância isolada,
    # evitando herdar estado corrompido de sessões anteriores.
    excel = win32com.client.DispatchEx('Excel.Application')
    excel.Visible = False
    excel.DisplayAlerts = False
    
    try:
        wb = excel.Workbooks.Open(caminho_modelo)
        
        # 1. Limpa e Preenche a aba 'Base'
        sheet_base = wb.Sheets('Base')
        last_row_base = sheet_base.UsedRange.Rows.Count
        if last_row_base >= 2:
            # Limpa valores antigos, mantendo apenas o cabeçalho (linha 1)
            sheet_base.Rows(f"2:{last_row_base}").ClearContents()
            
        for idx, nota in enumerate(notas):
            row = 2 + idx
            
            # Converte PDV para inteiro se possível para compatibilidade com XLOOKUP/VLOOKUP
            pdv_val = nota.get('PDV', '')
            try: sheet_base.Cells(row, 1).Value = int(pdv_val) if pdv_val else ""
            except: sheet_base.Cells(row, 1).Value = pdv_val
            
            sheet_base.Cells(row, 2).Value = 24  # Código Fornecedor
            sheet_base.Cells(row, 3).Value = 'Cálamo Distrib.de Produtos de '
            
            # Converte Nº DOC para inteiro se possível para compatibilidade com fórmulas
            ndoc_val = nota.get('Nº DOC', '')
            try: sheet_base.Cells(row, 4).Value = int(ndoc_val) if ndoc_val else ""
            except: sheet_base.Cells(row, 4).Value = ndoc_val
            
            sheet_base.Cells(row, 5).Value = 19  # Operação
            sheet_base.Cells(row, 6).Value = nota.get('Canal', '')  # LOJA ou VD para SUMIFS
            sheet_base.Cells(row, 7).Value = 'PENDENTE'
            sheet_base.Cells(row, 8).NumberFormat = "@"
            sheet_base.Cells(row, 8).Value = nota.get('Dt. Emissão', '')
            sheet_base.Cells(row, 9).NumberFormat = "@"
            sheet_base.Cells(row, 9).Value = nota.get('Dt. Vencimento', '')  # Data Vencimento
            sheet_base.Cells(row, 20).Value = nota.get('Total Itens/Merc.', 0.0)
            sheet_base.Cells(row, 20).NumberFormat = "#,##0.00"
            sheet_base.Cells(row, 24).Value = nota.get('Total do Documento', 0.0)
            sheet_base.Cells(row, 24).NumberFormat = "#,##0.00"
            
        # 2. Limpa e Preenche a aba 'Notas Fiscais' dinamicamente
        sheet_nf = wb.Sheets('Notas Fiscais')
        
        # Desmescla as células antigas a partir da linha 4 para evitar erros ao redimensionar/limpar
        try:
            sheet_nf.Range("A4:L200").UnMerge()
        except Exception as ex:
            print(f"[{unidade}] Aviso ao desmesclar células antigas: {ex}")
        
        # Atualiza os cabeçalhos da linha 3 para garantir nomes corretos
        try:
            sheet_nf.Range("A3:L3").UnMerge()
        except Exception:
            pass
        
        # Lê a formatação original do cabeçalho a partir de uma célula existente (A3)
        ref_cell = sheet_nf.Cells(3, 1)
        hdr_bg_color = ref_cell.Interior.Color
        hdr_font_color = ref_cell.Font.Color
        hdr_font_bold = ref_cell.Font.Bold
        hdr_font_name = ref_cell.Font.Name
        hdr_font_size = ref_cell.Font.Size
        
        cabecalhos = {
            1: "N° DOC",
            2: "CMV",
            3: "TRF",
            4: "REM",
            5: "Destinatário",
            6: "Dt. Emissão",
            7: "Dt. Vencimento",
            9: "Prazo de Pagamento",
            11: "Total\nItens/Merc.",
            12: "Total do\nDocumento",
        }

        def formatar_celula_cabecalho(cell):
            cell.Interior.Color = hdr_bg_color
            cell.Font.Color = hdr_font_color
            cell.Font.Bold = hdr_font_bold
            cell.Font.Name = hdr_font_name
            cell.Font.Size = hdr_font_size
            cell.VerticalAlignment = -4108   # xlCenter
            cell.HorizontalAlignment = -4108 # xlCenter
            cell.WrapText = True
            for border_id in [7, 8, 9, 10]:
                cell.Borders(border_id).LineStyle = 1
                cell.Borders(border_id).Weight = 2

        for col_idx, nome in cabecalhos.items():
            cell = sheet_nf.Cells(3, col_idx)
            cell.Value = nome
            formatar_celula_cabecalho(cell)

        # Aplica a mesma formatação na célula H3 (mergeada com G3)
        cell_h3 = sheet_nf.Cells(3, 8)
        formatar_celula_cabecalho(cell_h3)
        # Mescla G3:H3 para "Dt. Vencimento" (mesma estrutura das linhas de dados)
        sheet_nf.Range(sheet_nf.Cells(3, 7), sheet_nf.Cells(3, 8)).Merge()

        # Aplica a mesma formatação na célula J3 (mergeada com I3)
        cell_j3 = sheet_nf.Cells(3, 10)
        formatar_celula_cabecalho(cell_j3)
        # Mescla I3:J3 para "Prazo de Pagamento"
        sheet_nf.Range(sheet_nf.Cells(3, 9), sheet_nf.Cells(3, 10)).Merge()
                
        # Identifica dinamicamente a posição original dos blocos de Totais e Resumos
        orig_resumo_start = None
        orig_resumo_end = None
        orig_total_row = None
        
        for r in range(1, 100):
            val_a = str(sheet_nf.Cells(r, 1).Value).strip()
            val_g = str(sheet_nf.Cells(r, 7).Value).strip()
            if val_a == "RESUMO DE NOTAS POR CANAL/MARCA":
                orig_resumo_start = r
            if orig_resumo_start and not orig_resumo_end:
                if val_a == "TOTAL":
                    orig_resumo_end = r
            if val_g == "TOTAL" and not orig_total_row:
                orig_total_row = r
                
        # Backup temporário no próprio Excel usando aba auxiliar
        sheet_backup = wb.Sheets.Add()
        sheet_backup.Name = "BackupTemp"
        
        # Copia o bloco de Totais
        if orig_total_row:
            sheet_nf.Rows(f"{orig_total_row}:{orig_total_row+1}").Copy(sheet_backup.Rows("1:2"))
            
        # Copia o bloco de Resumo
        if orig_resumo_start and orig_resumo_end:
            num_res_rows = orig_resumo_end - orig_resumo_start + 1
            sheet_nf.Rows(f"{orig_resumo_start}:{orig_resumo_end}").Copy(sheet_backup.Rows(f"5:{4+num_res_rows}"))
            
        # Limpa todas as linhas antigas da tabela de dados a partir da linha 4
        # pois não queremos pular as linhas 4 e 5.
        last_row_nf = sheet_nf.UsedRange.Rows.Count
        if last_row_nf >= 4:
            sheet_nf.Rows(f"4:{last_row_nf}").Delete()
            
        # Cores de preenchimento alternado POR LOJA (PDV):
        # Cor 1: #DDEBF7 = RGB(221, 235, 247) -> BGR 16247773
        # Cor 2: #9BC2E6 = RGB(155, 194, 230) -> BGR 15123099
        cor_loja_1 = 16247773
        cor_loja_2 = 15123099
        
        # Monta mapeamento de cor por loja (PDV)
        pdvs_unicos = []
        for n in notas:
            pdv = str(n.get('PDV', ''))
            if pdv not in pdvs_unicos:
                pdvs_unicos.append(pdv)
        pdv_color_map = {pdv: i % 2 for i, pdv in enumerate(pdvs_unicos)}
        
        # Escreve as notas e suas fórmulas apontando para a aba Base
        num_notas = len(notas)
        for idx in range(num_notas):
            row = 4 + idx
            row_base = 2 + idx
            
            # Altura e estilo padrão da linha — cor alternada por LOJA
            sheet_nf.Rows(row).RowHeight = 25
            pdv_atual = str(notas[idx].get('PDV', ''))
            current_color = cor_loja_1 if pdv_color_map.get(pdv_atual, 0) == 0 else cor_loja_2
            
            for col in range(1, 13):
                cell = sheet_nf.Cells(row, col)
                cell.Font.Name = 'Calibri'
                cell.Font.Size = 9
                cell.Font.Bold = True
                cell.Interior.Color = current_color
                cell.VerticalAlignment = -4108 # xlCenter
                cell.HorizontalAlignment = -4131 # xlLeft
                
                # Aplica bordas finas
                for border_id in [7, 8, 9, 10]: # xlEdgeLeft, xlEdgeTop, xlEdgeBottom, xlEdgeRight
                    cell.Borders(border_id).LineStyle = 1
                    cell.Borders(border_id).Weight = 2
                    
            # Fórmulas e Valores
            sheet_nf.Cells(row, 1).Formula = f"=Base!D{row_base}"  # Nº DOC
            sheet_nf.Cells(row, 1).HorizontalAlignment = -4108
            sheet_nf.Cells(row, 2).Value = ""                      # CMV
            sheet_nf.Cells(row, 3).Value = ""                      # TRF
            sheet_nf.Cells(row, 4).Value = ""                      # REM
            
            # Mapeamento do destinatário (VLOOKUP dinâmico baseado na aba de nomenclaturas)
            aba_nomeclatura = "NOMECLATURA LOJAS" if unidade == "BH" else "Nomeclatura Lojas"
            col_max = "C" if unidade == "BH" else "B"
            sheet_nf.Cells(row, 5).Formula = f"=VLOOKUP(Base!A{row_base},'{aba_nomeclatura}'!A:{col_max},2,0)"
            
            sheet_nf.Cells(row, 6).Formula = f"=Base!H{row_base}"  # Dt. Emissão
            sheet_nf.Cells(row, 6).NumberFormat = "@"
            sheet_nf.Cells(row, 6).HorizontalAlignment = -4108
            
            sheet_nf.Cells(row, 7).Formula = f"=Base!I{row_base}"  # Dt. Vencimento
            sheet_nf.Cells(row, 7).NumberFormat = "@"
            sheet_nf.Cells(row, 7).HorizontalAlignment = -4108
            sheet_nf.Cells(row, 8).Value = ""
            
            # ── Prazo de Pagamento (dias totais e detalhe do prazo) ──────────────────
            _dt_emi_str  = notas[idx].get('Dt. Emissão', '')
            _dt_venc_str = notas[idx].get('Dt. Vencimento', '')
            _prazo_texto = ""
            _prazo_dias_num = None
            if _dt_emi_str and _dt_venc_str:
                try:
                    _obj_emi  = datetime.strptime(_dt_emi_str,  '%d/%m/%Y')
                    _obj_venc = datetime.strptime(_dt_venc_str, '%d/%m/%Y')
                    _prazo_dias = (_obj_venc - _obj_emi).days
                    _prazo_dias_num = _prazo_dias
                    
                    # Carrega dias base usando o PDV da nota (ou DEFAULT do TXT)
                    pdv_atual = str(notas[idx].get('PDV', '')).strip()
                    base_dias = regras_prazo.get(pdv_atual, regras_prazo.get('DEFAULT', 45))
                    
                    _x = max(_prazo_dias - (base_dias + 5), 0)
                    _prazo_texto = f"{base_dias}+5+{_x}"
                except Exception:
                    _prazo_texto = ""
                    _prazo_dias_num = None
            
            # Escreve prazo de pagamento (dias totais) na coluna 9
            if _prazo_dias_num is not None:
                sheet_nf.Cells(row, 9).Value = _prazo_dias_num
            else:
                sheet_nf.Cells(row, 9).Value = ""
            sheet_nf.Cells(row, 9).HorizontalAlignment = -4108  # xlCenter
            
            # Escreve detalhe do prazo de pagamento na coluna 10
            sheet_nf.Cells(row, 10).Value = _prazo_texto
            sheet_nf.Cells(row, 10).HorizontalAlignment = -4108  # xlCenter
            
            sheet_nf.Cells(row, 11).Formula = f"=Base!T{row_base}"  # Total Itens
            sheet_nf.Cells(row, 11).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(row, 11).HorizontalAlignment = -4152   # xlRight
            
            sheet_nf.Cells(row, 12).Formula = f"=Base!X{row_base}" # Total Documento
            sheet_nf.Cells(row, 12).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(row, 12).HorizontalAlignment = -4152   # xlRight
            
            sheet_nf.Range(sheet_nf.Cells(row, 7), sheet_nf.Cells(row, 8)).Merge()
            
        row_nf_last = 4 + num_notas - 1
        
        # 3. Restaura e atualiza a linha de Totais do backup
        row_total = row_nf_last + 1
        if orig_total_row:
            sheet_backup.Rows("1:2").Copy(sheet_nf.Rows(f"{row_total}:{row_total+1}"))
            
            # Limpa todas as colunas novas (9-12) nas linhas de totais para remover
            # fórmulas residuais do backup do modelo antigo (que não tinha "Prazo de Pagamento")
            for rt in [row_total, row_total+1]:
                for ct in range(9, 13):
                    sheet_nf.Cells(rt, ct).ClearContents()
            
            # Reescreve as fórmulas de Totais nas posições corretas (colunas K e L)
            sheet_nf.Cells(row_total, 11).Formula = f"=SUM(K4:K{row_nf_last})"
            sheet_nf.Cells(row_total, 11).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(row_total, 12).Formula = f"=SUM(L4:L{row_nf_last})"
            sheet_nf.Cells(row_total, 12).NumberFormat = '"R$" #,##0.00'
            
            # % ICMS ST — fórmula correta na coluna L (12): Total Documento / Total Itens - 1
            sheet_nf.Cells(row_total+1, 12).Formula = f"=IF(K{row_total}=0, 0, L{row_total}/K{row_total}-1)"
            sheet_nf.Cells(row_total+1, 12).NumberFormat = "0.0%"
            
            # Aplica formatação consistente nas linhas de totais (colunas 9-12)
            # Lê a formatação existente de cada linha (coluna 1) para replicar
            for rt in [row_total, row_total+1]:
                ref_total = sheet_nf.Cells(rt, 1)
                rt_bg = ref_total.Interior.Color
                rt_font_color = ref_total.Font.Color
                for ct in range(9, 13):
                    cell_t = sheet_nf.Cells(rt, ct)
                    cell_t.Interior.Color = rt_bg
                    cell_t.Font.Color = rt_font_color
                    cell_t.Font.Name = 'Calibri'
                    cell_t.Font.Size = 9
                    cell_t.Font.Bold = True
                    for border_id in [7, 8, 9, 10]:
                        cell_t.Borders(border_id).LineStyle = 1
                        cell_t.Borders(border_id).Weight = 2
            
        # 4. Restaura a tabela de Resumo do backup dinamicamente
        row_resumo_start = row_total + 4
        if orig_resumo_start and orig_resumo_end:
            num_res_rows = orig_resumo_end - orig_resumo_start + 1
            sheet_backup.Rows(f"5:{4+num_res_rows}").Copy(sheet_nf.Rows(f"{row_resumo_start}:{row_resumo_start+num_res_rows-1}"))
            
            # Reescreve as fórmulas do resumo usando SUMIFS nativo e compatível com Excel .xls
            # Isso evita que a planilha exiba zeros devido ao XLOOKUP legado que não funciona no formato 97-2003
            r_loja = row_resumo_start + 2
            r_vd = row_resumo_start + 3
            r_eudora = row_resumo_start + 4
            r_tot = row_resumo_start + 5
            
            # LOJA
            sheet_nf.Cells(r_loja, 5).Formula = '=SUMIFS(Base!T:T, Base!F:F, "LOJA")'
            sheet_nf.Cells(r_loja, 5).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_loja, 6).Formula = '=SUMIFS(Base!X:X, Base!F:F, "LOJA")'
            sheet_nf.Cells(r_loja, 6).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_loja, 7).Formula = f'=IF(E{r_loja}=0, 0, F{r_loja}/E{r_loja}-1)'
            sheet_nf.Cells(r_loja, 7).NumberFormat = "0.0%"
            
            # VD (Sem filtro restritivo de Nº DOC, soma todas as notas do canal VD)
            sheet_nf.Cells(r_vd, 5).Formula = '=SUMIFS(Base!T:T, Base!F:F, "VD")'
            sheet_nf.Cells(r_vd, 5).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_vd, 6).Formula = '=SUMIFS(Base!X:X, Base!F:F, "VD")'
            sheet_nf.Cells(r_vd, 6).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_vd, 7).Formula = f'=IF(E{r_vd}=0, 0, F{r_vd}/E{r_vd}-1)'
            sheet_nf.Cells(r_vd, 7).NumberFormat = "0.0%"
            
            # VD - EUDORA (Zerado, sem distinção por canal)
            sheet_nf.Cells(r_eudora, 5).Value = 0
            sheet_nf.Cells(r_eudora, 5).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_eudora, 6).Value = 0
            sheet_nf.Cells(r_eudora, 6).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_eudora, 7).Value = 0
            sheet_nf.Cells(r_eudora, 7).NumberFormat = "0.0%"
            
            # TOTAL
            sheet_nf.Cells(r_tot, 5).Formula = f'=SUM(E{r_loja}:E{r_eudora})'
            sheet_nf.Cells(r_tot, 5).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_tot, 6).Formula = f'=SUM(F{r_loja}:F{r_eudora})'
            sheet_nf.Cells(r_tot, 6).NumberFormat = '"R$" #,##0.00'
            sheet_nf.Cells(r_tot, 7).Formula = f'=IF(E{r_tot}=0, 0, F{r_tot}/E{r_tot}-1)'
            sheet_nf.Cells(r_tot, 7).NumberFormat = "0.0%"
            
        # Centraliza todas as informações da tabela de resumo
        if orig_resumo_start and orig_resumo_end:
            for r_res in range(row_resumo_start, r_tot + 1):
                for c_res in range(1, 11):
                    cell_res = sheet_nf.Cells(r_res, c_res)
                    cell_res.HorizontalAlignment = -4108  # xlCenter
                    cell_res.VerticalAlignment = -4108     # xlCenter
        
        # Remove a aba de backup temporário de forma limpa
        sheet_backup.Delete()
        
        # Atualiza Título Principal na linha 1 — usa semana completa (segunda a domingo)
        datas_emissao = []
        for n in notas:
            dt_emi = n.get('Dt. Emissão')
            if dt_emi:
                try: datas_emissao.append(datetime.strptime(dt_emi, '%d/%m/%Y'))
                except: pass
        if datas_emissao:
            min_date = min(datas_emissao)
            # Calcula segunda-feira da semana e domingo correspondente
            segunda = min_date - timedelta(days=min_date.weekday())
            domingo = segunda + timedelta(days=6)
            min_d = segunda.strftime('%d/%m')
            max_d = domingo.strftime('%d/%m')
            sheet_nf.Cells(1, 1).Value = f"NOTAS FISCAIS X CONTABILIZAÇÃO - SEMANA {min_d} A {max_d} - {unidade}"
            print(f"  [{unidade}] Cabeçalho atualizado: {min_d} a {max_d}")
        else:
            print(f"  [{unidade}] AVISO: Nenhuma data de emissão válida encontrada para atualizar o cabeçalho")
        
        # Estende o merge e formatação das linhas de título (1 e 2) até a coluna L (12)
        # pois o modelo original ia só até J (10) e agora temos duas colunas adicionais
        for row_tit in [1, 2]:
            try:
                sheet_nf.Range(f"A{row_tit}:L{row_tit}").UnMerge()
            except Exception:
                pass
            # Lê a formatação da célula A para replicar na extensão
            ref_tit = sheet_nf.Cells(row_tit, 1)
            tit_bg = ref_tit.Interior.Color
            tit_font_color = ref_tit.Font.Color
            tit_font_bold = ref_tit.Font.Bold
            tit_font_name = ref_tit.Font.Name
            tit_font_size = ref_tit.Font.Size
            # Aplica formatação e mescla toda a faixa A:L
            for ct in range(1, 13):
                cell_tit = sheet_nf.Cells(row_tit, ct)
                cell_tit.Interior.Color = tit_bg
                cell_tit.Font.Color = tit_font_color
                cell_tit.Font.Bold = tit_font_bold
                cell_tit.Font.Name = tit_font_name
                cell_tit.Font.Size = tit_font_size
            sheet_nf.Range(f"A{row_tit}:L{row_tit}").Merge()
            sheet_nf.Range(f"A{row_tit}:L{row_tit}").HorizontalAlignment = -4108  # xlCenter
            
        # Ajusta a largura das colunas do relatório
        ajustar_larguras_colunas(excel, sheet_nf)
        
        # Força o tamanho da fonte da linha 58 para 9
        sheet_nf.Rows(58).Font.Size = 9

        # Salva o arquivo preservando o formato nativo .xls (Excel 97-2003)
        wb.SaveAs(caminho_saida, FileFormat=56)
        wb.Close(True)
        print(f"[{unidade}] Sucesso! Relatório Geral salvo em: {os.path.basename(caminho_saida)}")
        
    except Exception as e:
        print(f"[{unidade}] Erro ao gerar o relatório geral: {e}")
        try: wb.Close(False)
        except: pass
    finally:
        excel.Quit()

def processar_relatorio_matheus(unidade, notas, caminho_modelo, caminho_saida):
    """Gera o relatório específico do Matheus nas colunas adequadas (A-E para BH, F-J para UDI)."""
    if not notas:
        print(f"[{unidade}] Nenhuma nota encontrada para o Matheus. Relatório não gerado.")
        return
        
    print(f"[{unidade}] Iniciando preenchimento do Relatório do Matheus...")
    
    # DispatchEx sempre cria nova instância isolada do Excel
    excel = win32com.client.DispatchEx('Excel.Application')
    excel.Visible = False
    excel.DisplayAlerts = False
    
    try:
        wb = excel.Workbooks.Open(caminho_modelo)
        
        # 1. Limpa e Preenche a aba 'Base'
        sheet_base = wb.Sheets('Base')
        last_row_base = sheet_base.UsedRange.Rows.Count
        if last_row_base >= 2:
            sheet_base.Rows(f"2:{last_row_base}").ClearContents()
            
        for idx, nota in enumerate(notas):
            row = 2 + idx
            
            # Converte PDV para inteiro se possível
            pdv_val = nota.get('PDV', '')
            try: sheet_base.Cells(row, 1).Value = int(pdv_val) if pdv_val else ""
            except: sheet_base.Cells(row, 1).Value = pdv_val
            
            sheet_base.Cells(row, 2).Value = 24
            sheet_base.Cells(row, 3).Value = 'Cálamo Distrib.de Produtos de '
            
            # Converte Nº DOC para inteiro se possível
            ndoc_val = nota.get('Nº DOC', '')
            try: sheet_base.Cells(row, 4).Value = int(ndoc_val) if ndoc_val else ""
            except: sheet_base.Cells(row, 4).Value = ndoc_val
            
            sheet_base.Cells(row, 5).Value = 19
            sheet_base.Cells(row, 6).Value = nota.get('Canal', '')
            sheet_base.Cells(row, 7).Value = 'PENDENTE'
            sheet_base.Cells(row, 8).NumberFormat = "@"
            sheet_base.Cells(row, 8).Value = nota.get('Dt. Emissão', '')
            sheet_base.Cells(row, 9).NumberFormat = "@"
            sheet_base.Cells(row, 9).Value = nota.get('Dt. Vencimento', '')  # Data Vencimento
            sheet_base.Cells(row, 20).Value = nota.get('Total Itens/Merc.', 0.0)
            sheet_base.Cells(row, 20).NumberFormat = "#,##0.00"
            sheet_base.Cells(row, 24).Value = nota.get('Total do Documento', 0.0)
            sheet_base.Cells(row, 24).NumberFormat = "#,##0.00"
            
        # 2. Limpa e Preenche a aba 'Notas Fiscais' do Matheus
        sheet_nf = wb.Sheets('Notas Fiscais')
        
        # Deleta as linhas de dados excedentes a partir da linha 4
        last_row_nf = sheet_nf.UsedRange.Rows.Count
        if last_row_nf >= 4:
            sheet_nf.Rows(f"4:{last_row_nf}").Delete()
            
        # Escreve os registros nas colunas correspondentes (visíveis)
        # BH usa colunas de A a E (1 a 5). UDI usa colunas de F a J (6 a 10).
        start_col = 1 if unidade == "BH" else 6
        end_col = 5 if unidade == "BH" else 10
        
        # Cores de preenchimento alternado POR LOJA (PDV):
        # Cor 1: #DDEBF7 = RGB(221, 235, 247) -> BGR 16247773
        # Cor 2: #9BC2E6 = RGB(155, 194, 230) -> BGR 15123099
        cor_loja_1 = 16247773
        cor_loja_2 = 15123099
        
        # Monta mapeamento de cor por loja (PDV)
        pdvs_unicos = []
        for n in notas:
            pdv = str(n.get('PDV', ''))
            if pdv not in pdvs_unicos:
                pdvs_unicos.append(pdv)
        pdv_color_map = {pdv: i % 2 for i, pdv in enumerate(pdvs_unicos)}
        
        for idx, nota in enumerate(notas):
            row = 4 + idx
            row_base = 2 + idx
            
            sheet_nf.Rows(row).RowHeight = 25
            pdv_atual = str(nota.get('PDV', ''))
            current_color = cor_loja_1 if pdv_color_map.get(pdv_atual, 0) == 0 else cor_loja_2
            
            # Formata todas as células da nova linha
            for col in range(start_col, end_col + 1):
                cell = sheet_nf.Cells(row, col)
                cell.Font.Name = 'Calibri'
                cell.Font.Size = 9
                cell.Font.Bold = True
                cell.Font.Color = 0 # Força a cor do texto para preto padrão
                cell.Interior.Color = current_color
                cell.VerticalAlignment = -4108 # xlCenter
                
                # Borda fina
                for border_id in [7, 8, 9, 10]:
                    cell.Borders(border_id).LineStyle = 1
                    cell.Borders(border_id).Weight = 2
            
            aba_nomenclatura = "NOMECLATURA LOJAS" if unidade == "BH" else "Nomeclatura Lojas"
            col_max = "C" if unidade == "BH" else "B"
            
            # Preenche as fórmulas corretas
            if unidade == "BH":
                sheet_nf.Cells(row, 1).Formula = f"=Base!A{row_base}"  # PDV
                sheet_nf.Cells(row, 1).HorizontalAlignment = -4108
                
                sheet_nf.Cells(row, 2).Formula = f"=VLOOKUP(Base!A{row_base},'{aba_nomenclatura}'!A:{col_max},2,0)" # Nome
                
                sheet_nf.Cells(row, 3).Formula = f"=Base!H{row_base}"  # Dt. Emissão
                sheet_nf.Cells(row, 3).NumberFormat = "@"
                sheet_nf.Cells(row, 3).HorizontalAlignment = -4108
                
                sheet_nf.Cells(row, 4).Formula = f"=Base!D{row_base}"  # Nº NF
                sheet_nf.Cells(row, 4).HorizontalAlignment = -4108
                
                # Converte Nosso Pedido para inteiro se possível
                pedido_val = nota.get('Nosso Pedido', '')
                try: sheet_nf.Cells(row, 5).Value = int(pedido_val) if pedido_val else ""
                except: sheet_nf.Cells(row, 5).Value = pedido_val
                sheet_nf.Cells(row, 5).HorizontalAlignment = -4108
            else:
                sheet_nf.Cells(row, 6).Formula = f"=Base!A{row_base}"  # PDV
                sheet_nf.Cells(row, 6).HorizontalAlignment = -4108
                
                sheet_nf.Cells(row, 7).Formula = f"=VLOOKUP(Base!A{row_base},'{aba_nomenclatura}'!A:{col_max},2,0)" # Nome
                
                sheet_nf.Cells(row, 8).Formula = f"=Base!H{row_base}"  # Dt. Emissão
                sheet_nf.Cells(row, 8).NumberFormat = "@"
                sheet_nf.Cells(row, 8).HorizontalAlignment = -4108
                
                sheet_nf.Cells(row, 9).Formula = f"=Base!D{row_base}"  # Nº NF
                sheet_nf.Cells(row, 9).HorizontalAlignment = -4108
                
                # Converte Nosso Pedido para inteiro se possível
                pedido_val = nota.get('Nosso Pedido', '')
                try: sheet_nf.Cells(row, 10).Value = int(pedido_val) if pedido_val else ""
                except: sheet_nf.Cells(row, 10).Value = pedido_val
                sheet_nf.Cells(row, 10).HorizontalAlignment = -4108
                
        # Atualiza o Título na linha 1 — usa semana completa (segunda a domingo)
        datas_emissao = []
        for n in notas:
            dt_emi = n.get('Dt. Emissão')
            if dt_emi:
                try: datas_emissao.append(datetime.strptime(dt_emi, '%d/%m/%Y'))
                except: pass
        if datas_emissao:
            min_date = min(datas_emissao)
            # Calcula segunda-feira da semana e domingo correspondente
            segunda = min_date - timedelta(days=min_date.weekday())
            domingo = segunda + timedelta(days=6)
            min_d = segunda.strftime('%d/%m')
            max_d = domingo.strftime('%d/%m')
            col_tit = 1 if unidade == "BH" else 6
            sheet_nf.Cells(1, col_tit).Value = f"NOTAS FISCAIS FATURADAS - SEMANA {min_d} A {max_d} - {unidade}"
            print(f"  [{unidade}/Matheus] Cabeçalho atualizado: {min_d} a {max_d}")
        else:
            print(f"  [{unidade}/Matheus] AVISO: Nenhuma data de emissão válida encontrada para atualizar o cabeçalho")
            
        # Salva o arquivo do Matheus
        wb.SaveAs(caminho_saida, FileFormat=56)
        wb.Close(True)
        print(f"[{unidade}] Sucesso! Relatório do Matheus salvo em: {os.path.basename(caminho_saida)}")
        
    except Exception as e:
        print(f"[{unidade}] Erro ao gerar o relatório do Matheus: {e}")
        try: wb.Close(False)
        except: pass
    finally:
        excel.Quit()

@log_execution(modulo="XML (Gerador de Relatório)")
def gerar_relatorio_calamo():
    """Função principal que orquestra a leitura do XML, classificação e geração dos 4 relatórios."""
    print("=== INICIANDO PROCESSAMENTO DOS RELATÓRIOS DA CÁLAMO ===")
    
    if os.path.exists(r"T:\13-Publica\XMLS CÁLAMO"):
        pasta_xml = r"T:\13-Publica\XMLS CÁLAMO\XML BAIXADOS\TEMP_PROCESSAMENTO"
    else:
        pasta_xml = os.path.join(DIRETORIO_ATUAL, 'xmls_meudanfe')
        
    pasta_modelos = os.path.join(DIRETORIO_ATUAL, 'modelos_xmls')
    
    if not os.path.exists(pasta_xml):
        print(f"AVISO: A pasta '{pasta_xml}' não existe.")
        print("Isso geralmente significa que nenhum XML foi baixado nesta sessão ainda.")
        print("Tente 'Executar todo o processo' primeiro.")
        return
        
    arquivos_xml = [f for f in os.listdir(pasta_xml) if f.lower().endswith('.xml')]
    if not arquivos_xml:
        print(f"Nenhum arquivo XML encontrado em '{pasta_xml}'.")
        return
        
    print(f"Lendo {len(arquivos_xml)} arquivos XML...")
    
    notas_bh = []
    notas_udi = []
    notas_ignoradas = 0
    notas_sem_vencimento = 0
    datas_emissao = []
    
    for arquivo in arquivos_xml:
        caminho_completo = os.path.join(pasta_xml, arquivo)
        dados = extrair_dados_xml(caminho_completo)
        if dados:
            # ── Filtro: ignora notas sem data de vencimento ──
            dt_venc = (dados.get('Dt. Vencimento') or '').strip()
            if not dt_venc:
                ndoc = dados.get('Nº DOC', '?')
                pdv = dados.get('PDV', '?')
                print(f"  [IGNORADA] Nota {ndoc} (PDV {pdv}) sem data de vencimento — não será incluída nos relatórios.")
                notas_sem_vencimento += 1
                continue

            unidade = dados.get('Unidade')
            dt_emi = dados.get('Dt. Emissão')
            
            # Armazena datas válidas para calcular o período da semana
            if dt_emi:
                try:
                    data_obj = datetime.strptime(dt_emi, '%d/%m/%Y')
                    datas_emissao.append(data_obj)
                except:
                    pass
                    
            if unidade == 'BH':
                notas_bh.append(dados)
            elif unidade == 'UDI':
                notas_udi.append(dados)
            else:
                print(f"Diagnóstico: Nota {dados.get('Nº DOC')} com destinatário '{dados.get('Destinatário')}' não está mapeada em BH nem em UDI.")
                
    print(f"Notas lidas com sucesso: BH={len(notas_bh)}, UDI={len(notas_udi)} (Total processado: {len(arquivos_xml)})")
    if notas_sem_vencimento:
        print(f"  ⚠️  {notas_sem_vencimento} nota(s) ignorada(s) por não possuírem data de vencimento.")
    
    if not notas_bh and not notas_udi:
        print("Nenhuma nota processada dos XMLs. Abortando geração.")
        return 0
        
    # Carrega dinamicamente a ordem desejada das lojas baseada nas planilhas
    caminho_mod_bh = os.path.join(pasta_modelos, 'MODELO BH.xls')
    caminho_mod_udi = os.path.join(pasta_modelos, 'MODELO UDI.xls')
    
    ordem_bh = obter_ordem_lojas(caminho_mod_bh, 'NOMECLATURA LOJAS')
    ordem_udi = obter_ordem_lojas(caminho_mod_udi, 'Nomeclatura Lojas')
    
    # Ordena as notas conforme a ordem física dos PDVs nas planilhas
    def ordenar_bh(n):
        pdv = str(n.get('PDV', ''))
        return ordem_bh.index(pdv) if pdv in ordem_bh else 9999
        
    def ordenar_udi(n):
        pdv = str(n.get('PDV', ''))
        return ordem_udi.index(pdv) if pdv in ordem_udi else 9999
        
    notas_bh.sort(key=ordenar_bh)
    notas_udi.sort(key=ordenar_udi)
    
    # 4. Determina Ano, Mês e a Semana para criar a estrutura organizada de pastas
    if datas_emissao:
        min_date_obj = min(datas_emissao)
        # Calcula segunda-feira da semana e domingo correspondente
        segunda_pasta = min_date_obj - timedelta(days=min_date_obj.weekday())
        domingo_pasta = segunda_pasta + timedelta(days=6)
        
        ano_pasta = str(segunda_pasta.year)
        mes_pasta = MESES_MAP.get(segunda_pasta.month, f"{segunda_pasta.month:02d} - Outros")
        mes_upper = MESES_NOME_UPPER.get(segunda_pasta.month, "OUTROS")
        
        min_str = segunda_pasta.strftime('%d-%m')
        max_str = domingo_pasta.strftime('%d-%m')
        semana_pasta = f"Semana {min_str} a {max_str}"
    else:
        # Fallback padrão
        ano_pasta = str(datetime.now().year)
        mes_pasta = MESES_MAP.get(datetime.now().month, f"{datetime.now().month:02d} - Outros")
        mes_upper = MESES_NOME_UPPER.get(datetime.now().month, "OUTROS")
        semana_pasta = f"Semana {datetime.now().strftime('%d-%m')}"
        
    # Caminho final estruturado na rede T:
    base_relatorios = r"T:\13-Publica\XMLS CÁLAMO\RELATÓRIOS COMPLETOS"
    base_xmls_baixados = r"T:\13-Publica\XMLS CÁLAMO\XML BAIXADOS"
    
    # Se a T: não estiver mapeada, usar fallback local
    if not os.path.exists(r"T:\13-Publica\XMLS CÁLAMO"):
        print("AVISO: Drive T:\\13-Publica\\XMLS CÁLAMO não encontrado! Usando pastas locais como fallback.")
        base_relatorios = os.path.join(DIRETORIO_ATUAL, 'Relatórios Cálamo')
        base_xmls_baixados = os.path.join(DIRETORIO_ATUAL, 'XML BAIXADOS')
        
    diretorio_saida = os.path.join(base_relatorios, ano_pasta, mes_pasta, semana_pasta)
    os.makedirs(diretorio_saida, exist_ok=True)
    print(f"Diretório de relatórios criado: {diretorio_saida}")
    
    # Caminhos finais para salvar os 4 arquivos (novo padrão de nomeação)
    saida_geral_bh = os.path.join(diretorio_saida, f"13.PUB.NOTAS FISCAIS FATURADAS & CONTABILIZAÇÃO-{ano_pasta}-{mes_upper}-{semana_pasta} BH.xls")
    saida_geral_udi = os.path.join(diretorio_saida, f"13.PUB.NOTAS FISCAIS FATURADAS & CONTABILIZAÇÃO-{ano_pasta}-{mes_upper}-{semana_pasta} UDI.xls")
    saida_matheus_bh = os.path.join(diretorio_saida, f"13.PUB.NOTAS FISCAIS FATURADAS & NOSSO PEDIDO-{ano_pasta}-{mes_upper}-{semana_pasta} BH.xls")
    saida_matheus_udi = os.path.join(diretorio_saida, f"13.PUB.NOTAS FISCAIS FATURADAS & NOSSO PEDIDO-{ano_pasta}-{mes_upper}-{semana_pasta} UDI.xls")
    
    # Modelos de entrada
    caminho_mod_matheus_bh = os.path.join(pasta_modelos, 'MODELO_MATHEUS_BH.xls')
    caminho_mod_matheus_udi = os.path.join(pasta_modelos, 'MODELO_MATHEUS_UDI.xls')
    
    # Carrega notas previamente existentes na semana (se os relatórios já existirem)
    existentes_bh = carregar_notas_existentes_semana(saida_geral_bh, saida_matheus_bh, 'BH')
    existentes_udi = carregar_notas_existentes_semana(saida_geral_udi, saida_matheus_udi, 'UDI')

    # Mescla notas existentes com novas notas (desduplicando por PDV + Nº DOC)
    chaves_bh = set()
    notas_bh_combinadas = []
    for n in (existentes_bh + notas_bh):
        k = (str(n.get('PDV', '')).strip(), str(n.get('Nº DOC', '')).strip())
        if k not in chaves_bh:
            chaves_bh.add(k)
            notas_bh_combinadas.append(n)

    chaves_udi = set()
    notas_udi_combinadas = []
    for n in (existentes_udi + notas_udi):
        k = (str(n.get('PDV', '')).strip(), str(n.get('Nº DOC', '')).strip())
        if k not in chaves_udi:
            chaves_udi.add(k)
            notas_udi_combinadas.append(n)

    # Reordena as notas combinadas conforme a ordem física dos PDVs nas planilhas
    notas_bh_combinadas.sort(key=ordenar_bh)
    notas_udi_combinadas.sort(key=ordenar_udi)

    # Executa a geração para cada um dos 4 arquivos com os dados acumulados da semana
    if notas_bh_combinadas:
        processar_relatorio_geral('BH', notas_bh_combinadas, caminho_mod_bh, saida_geral_bh)
        processar_relatorio_matheus('BH', notas_bh_combinadas, caminho_mod_matheus_bh, saida_matheus_bh)
        
    if notas_udi_combinadas:
        processar_relatorio_geral('UDI', notas_udi_combinadas, caminho_mod_udi, saida_geral_udi)
        processar_relatorio_matheus('UDI', notas_udi_combinadas, caminho_mod_matheus_udi, saida_matheus_udi)
        
    # 4.1. GERAÇÃO DOS RELATÓRIOS DETALHADOS POR PDV (VD CAPTAÇÃO: 20844 E 13793)
    if processar_relatorios_detalhados and arquivos_xml:
        base_detalhados = r"T:\13-Publica\XMLS CÁLAMO\RELATÓRIOS DETALHADOS"
        if not os.path.exists(r"T:\13-Publica\XMLS CÁLAMO"):
            base_detalhados = os.path.join(DIRETORIO_ATUAL, 'Relatórios Cálamo Detalhado')

        caminhos_xmls_processamento = [os.path.join(pasta_xml, arq) for arq in arquivos_xml]
        try:
            print("\n--- Iniciando Geração dos Relatórios Detalhados por PDV (VD Captação) ---")
            processar_relatorios_detalhados(
                lista_arquivos_xml=caminhos_xmls_processamento,
                diretorio_base_saida=base_detalhados,
                ano_pasta=ano_pasta,
                mes_pasta=mes_pasta,
                semana_pasta=semana_pasta,
                pdvs_alvo=['20844', '13793']
            )
        except Exception as e_det:
            print(f"Aviso: Erro ao gerar relatórios detalhados por PDV: {e_det}")

    # 5. ORGANIZA E SALVA OS XMLS POR PDV
    diretorio_xmls_saida = os.path.join(base_xmls_baixados, ano_pasta, mes_pasta, semana_pasta)
    os.makedirs(diretorio_xmls_saida, exist_ok=True)
    xmls_movidos = 0
    
    # Monta mapeamento: nome_arquivo_original -> dados da nota (PDV + Nº DOC)
    mapa_arquivo_nota = {}
    for nota in (notas_bh + notas_udi):
        arq_original = nota.get('Arquivo_Original', '')
        if arq_original:
            mapa_arquivo_nota[arq_original] = nota
    
    try:
        for arquivo in arquivos_xml:
            caminho_origem = os.path.join(pasta_xml, arquivo)
            nota = mapa_arquivo_nota.get(arquivo)
            
            if nota:
                pdv  = str(nota.get('PDV', '')).strip()
                ndoc = str(nota.get('Nº DOC', '')).strip()
            else:
                pdv  = ''
                ndoc = ''
            
            # Define subpasta: apenas o número do PDV, ou pasta especial se não mapeado
            subpasta = pdv if pdv else 'PDV_SEM_IDENTIFICACAO'
            pasta_pdv = os.path.join(diretorio_xmls_saida, subpasta)
            os.makedirs(pasta_pdv, exist_ok=True)
            
            # Renomeia para PDV_NºDOC.xml; se não houver dados mantém o nome original
            if pdv and ndoc:
                novo_nome = f"{pdv}_{ndoc}.xml"
            else:
                novo_nome = arquivo
            
            caminho_destino = os.path.join(pasta_pdv, novo_nome)
            shutil.copy2(caminho_origem, caminho_destino)
            os.remove(caminho_origem)
            xmls_movidos += 1
        print(f"[{xmls_movidos}] XMLs organizados por PDV e salvos em:")
        print(f" => {diretorio_xmls_saida}")
        
        # Converte as XMLs recém-organizadas para o padrão SEFAZ
        if _CONVERSOR_DISPONIVEL and xmls_movidos > 0:
            print("\n--- Iniciando conversão para o padrão SEFAZ ---")
            _converter_pasta_sefaz(
                diretorio_xmls_saida,
                fazer_backup=False,
                apenas_meudanfe=True,
            )
    except Exception as e:
        print(f"Erro ao organizar arquivos XML: {e}")
        
    print(f"\n=== PROCESSAMENTO CONCLUÍDO COM SUCESSO! ===")
    print(f"Os relatórios Excel foram salvos com sucesso em:")
    print(f" => {diretorio_saida}")
    return len(notas_bh) + len(notas_udi)

if __name__ == '__main__':
    gerar_relatorio_calamo()

