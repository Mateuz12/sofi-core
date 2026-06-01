import pandas as pd

file_path = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\CONTROLE DE DEPÓSITO\UDI\2026\05-FIN.FECHAMENTO DE CAIXA.CONTROLE DE DEPÓSITO.UDI.2026.PLANILHA DE ACOMPANHAMENTO DE DEPÓSITOS LOJAS - VD.xlsx"

try:
    xl = pd.ExcelFile(file_path)
    df = xl.parse(xl.sheet_names[0], header=None, nrows=10)
    
    with open("scratch/inspect_output.txt", "w", encoding="utf-8") as f:
        for i, row in df.iterrows():
            f.write(f"Linha {i}: {row.tolist()}\n")
except Exception as e:
    print(f"Erro: {e}")
