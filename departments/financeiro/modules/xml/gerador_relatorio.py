import os
import sys
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import win32com.client

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
    1: "05 - Maio" if 5 == 5 else "01 - Janeiro", # Garante mapeamento correto
    1: "01 - Janeiro", 2: "02 - Fevereiro", 3: "03 - Março", 4: "04 - Abril",
    5: "05 - Maio", 6: "06 - Junho", 7: "07 - Julho", 8: "08 - Agosto",
    9: "09 - Setembro", 10: "10 - Outubro", 11: "11 - Novembro", 12: "12 - Dezembro"
}

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

def processar_relatorio_geral(unidade, notas, caminho_modelo, caminho_saida):
    """Preenche a aba Base e gera a aba Notas Fiscais dinamicamente mantendo formatação e fórmulas do modelo."""
    if not notas:
        print(f"[{unidade}] Nenhuma nota fiscal encontrada. Relatório Geral não gerado.")
        return
        
    print(f"[{unidade}] Iniciando preenchimento do Relatório Geral...")
    
    # Inicializa Excel COM
    excel = win32com.client.Dispatch('Excel.Application')
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
            sheet_nf.Range("A4:J200").UnMerge()
        except Exception as ex:
            print(f"[{unidade}] Aviso ao desmesclar células antigas: {ex}")
                
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
            
            for col in range(1, 11):
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
            
            sheet_nf.Cells(row, 9).Formula = f"=Base!T{row_base}"  # Total Itens
            sheet_nf.Cells(row, 9).NumberFormatLocal = "R$ #.##0,00"
            sheet_nf.Cells(row, 9).HorizontalAlignment = -4152   # xlRight
            
            sheet_nf.Cells(row, 10).Formula = f"=Base!X{row_base}" # Total Documento
            sheet_nf.Cells(row, 10).NumberFormatLocal = "R$ #.##0,00"
            sheet_nf.Cells(row, 10).HorizontalAlignment = -4152   # xlRight
            
            sheet_nf.Range(sheet_nf.Cells(row, 7), sheet_nf.Cells(row, 8)).Merge()
            
        row_nf_last = 4 + num_notas - 1
        
        # 3. Restaura e atualiza a linha de Totais do backup
        row_total = row_nf_last + 1
        if orig_total_row:
            sheet_backup.Rows("1:2").Copy(sheet_nf.Rows(f"{row_total}:{row_total+1}"))
            
            # Conserva e atualiza os intervalos das fórmulas de Totais nativas do Excel
            sheet_nf.Cells(row_total, 9).Formula = f"=SUM(I4:I{row_nf_last})"
            sheet_nf.Cells(row_total, 10).Formula = f"=SUM(J4:J{row_nf_last})"
            sheet_nf.Cells(row_total+1, 10).Formula = f"=J{row_total}/I{row_total}-1"
            
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
            sheet_nf.Cells(r_loja, 6).Formula = '=SUMIFS(Base!X:X, Base!F:F, "LOJA")'
            sheet_nf.Cells(r_loja, 7).Formula = f'=F{r_loja}/E{r_loja}-1'
            
            # VD
            sheet_nf.Cells(r_vd, 5).Formula = '=SUMIFS(Base!T:T, Base!F:F, "VD", Base!D:D, "<700000")'
            sheet_nf.Cells(r_vd, 6).Formula = '=SUMIFS(Base!X:X, Base!F:F, "VD", Base!D:D, "<700000")'
            sheet_nf.Cells(r_vd, 7).Formula = f'=F{r_vd}/E{r_vd}-1'
            
            # VD - EUDORA
            sheet_nf.Cells(r_eudora, 5).Formula = '=SUMIFS(Base!T:T, Base!F:F, "VD", Base!D:D, ">=700000")'
            sheet_nf.Cells(r_eudora, 6).Formula = '=SUMIFS(Base!X:X, Base!F:F, "VD", Base!D:D, ">=700000")'
            sheet_nf.Cells(r_eudora, 7).Formula = f'=F{r_eudora}/E{r_eudora}-1'
            
            # TOTAL
            sheet_nf.Cells(r_tot, 5).Formula = f'=SUM(E{r_loja}:E{r_eudora})'
            sheet_nf.Cells(r_tot, 6).Formula = f'=SUM(F{r_loja}:F{r_eudora})'
            sheet_nf.Cells(r_tot, 7).Formula = f'=F{r_tot}/E{r_tot}-1'
            
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
    
    excel = win32com.client.Dispatch('Excel.Application')
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
    
    if os.path.exists(r"T:\05-FIN\XMLS CÁLAMO"):
        pasta_xml = r"T:\05-FIN\XMLS CÁLAMO\XML BAIXADOS\TEMP_PROCESSAMENTO"
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
    datas_emissao = []
    
    for arquivo in arquivos_xml:
        caminho_completo = os.path.join(pasta_xml, arquivo)
        dados = extrair_dados_xml(caminho_completo)
        if dados:
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
    
    if not notas_bh and not notas_udi:
        print("Nenhuma nota processada dos XMLs. Abortando geração.")
        return
        
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
        
        min_str = segunda_pasta.strftime('%d-%m')
        max_str = domingo_pasta.strftime('%d-%m')
        semana_pasta = f"Semana {min_str} a {max_str}"
    else:
        # Fallback padrão
        ano_pasta = str(datetime.now().year)
        mes_pasta = MESES_MAP.get(datetime.now().month, f"{datetime.now().month:02d} - Outros")
        semana_pasta = f"Semana {datetime.now().strftime('%d-%m')}"
        
    # Caminho final estruturado na rede T:
    base_relatorios = r"T:\05-FIN\XMLS CÁLAMO\RELATÓRIOS COMPLETOS"
    base_xmls_baixados = r"T:\05-FIN\XMLS CÁLAMO\XML BAIXADOS"
    
    # Se a T: não estiver mapeada, usar fallback local
    if not os.path.exists(r"T:\05-FIN\XMLS CÁLAMO"):
        print("AVISO: Drive T:\\05-FIN\\XMLS CÁLAMO não encontrado! Usando pastas locais como fallback.")
        base_relatorios = os.path.join(DIRETORIO_ATUAL, 'Relatórios Cálamo')
        base_xmls_baixados = os.path.join(DIRETORIO_ATUAL, 'XML BAIXADOS')
        
    diretorio_saida = os.path.join(base_relatorios, ano_pasta, mes_pasta, semana_pasta)
    os.makedirs(diretorio_saida, exist_ok=True)
    print(f"Diretório de relatórios criado: {diretorio_saida}")
    
    # Caminhos finais para salvar os 4 arquivos
    saida_geral_bh = os.path.join(diretorio_saida, "Relatorio_Final_Calamo_BH.xls")
    saida_geral_udi = os.path.join(diretorio_saida, "Relatorio_Final_Calamo_UDI.xls")
    saida_matheus_bh = os.path.join(diretorio_saida, "Relatorio_Final_Matheus_BH.xls")
    saida_matheus_udi = os.path.join(diretorio_saida, "Relatorio_Final_Matheus_UDI.xls")
    
    # Modelos de entrada
    caminho_mod_matheus_bh = os.path.join(pasta_modelos, 'MODELO_MATHEUS_BH.xls')
    caminho_mod_matheus_udi = os.path.join(pasta_modelos, 'MODELO_MATHEUS_UDI.xls')
    
    # Executa a geração para cada um dos 4 arquivos de forma robusta
    if notas_bh:
        processar_relatorio_geral('BH', notas_bh, caminho_mod_bh, saida_geral_bh)
        processar_relatorio_matheus('BH', notas_bh, caminho_mod_matheus_bh, saida_matheus_bh)
        
    if notas_udi:
        processar_relatorio_geral('UDI', notas_udi, caminho_mod_udi, saida_geral_udi)
        processar_relatorio_matheus('UDI', notas_udi, caminho_mod_matheus_udi, saida_matheus_udi)
        
    # 5. MOVE OS XMLS PARA A REDE (OU FALLBACK)
    diretorio_xmls_saida = os.path.join(base_xmls_baixados, ano_pasta, mes_pasta, semana_pasta)
    os.makedirs(diretorio_xmls_saida, exist_ok=True)
    xmls_movidos = 0
    try:
        for arquivo in arquivos_xml:
            caminho_origem = os.path.join(pasta_xml, arquivo)
            caminho_destino = os.path.join(diretorio_xmls_saida, arquivo)
            shutil.copy2(caminho_origem, caminho_destino)
            os.remove(caminho_origem)
            xmls_movidos += 1
        print(f"[{xmls_movidos}] XMLs organizados e movidos para:")
        print(f" => {diretorio_xmls_saida}")
    except Exception as e:
        print(f"Erro ao mover arquivos XML: {e}")
        
    print(f"\n=== PROCESSAMENTO CONCLUÍDO COM SUCESSO! ===")
    print(f"Os relatórios Excel foram salvos com sucesso em:")
    print(f" => {diretorio_saida}")

if __name__ == '__main__':
    gerar_relatorio_calamo()

