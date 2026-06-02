import pandas as pd
import os
from datetime import datetime

class ETLEngine:
    def __init__(self, data_input=None):
        self.data_input = data_input

    def obter_caminho_relatorio(self):
        base_dir = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI"
        
        print("\n[BUSCA DE ARQUIVO ETL]")
        if self.data_input:
            try:
                data_alvo = datetime.strptime(self.data_input.strip(), "%d/%m/%Y")
                print(f"Buscando relatório para a data especificada: {self.data_input}")
            except Exception as e:
                print("Formato de data inválido. Buscando data de hoje...")
                data_alvo = datetime.now()
        else:
            print("Buscando relatório para a data de HOJE...")
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
            # Retorna None caso não encontre; a seleção manual de arquivo (fallback) 
            # foi removida daqui e repassada ao controller (main.py) ou UI futura.
            return None

    def executar_processamento(self, caminho_relatorio):
        """
        Lê o Excel, limpa os dados, calcula valores e retorna a Fila de Trabalho (dicionário).
        """
        print("1. Lendo o relatório de cartões...")
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

        is_omini = df_consolidado['PlanoPagamento'].astype(str).str.strip().str.upper() == 'OMNICHANNEL - CONSUMIDOR FINAL'
        pedidos_omini = df_consolidado[is_omini].copy()

        print("5. Montando a Fila de Trabalho OMINI...")
        fila_total_omini = pedidos_omini.groupby('NumeroPedido').apply(
            lambda x: {
                'transacoes': x[['NumeroAutorizacao', 'ValorTela', 'BandeiraCartao', 'QuantidadeParcelas', 'ValorMatematico', 'Titulo']].to_dict('records'),
                'DataPedido': x['DataPedido'].iloc[0]
            }
        ).to_dict()

        fila_de_trabalho_omini = fila_total_omini.copy()
        quantidade_pedidos_omini = len(fila_de_trabalho_omini)

        print(f"\n[SUCESSO] Encontrados {quantidade_pedidos_omini} pedidos OMINI para conciliar.")
        
        return fila_de_trabalho_omini, quantidade_pedidos_omini
