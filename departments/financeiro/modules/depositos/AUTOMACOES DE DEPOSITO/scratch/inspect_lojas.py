import pandas as pd

try:
    df = pd.read_excel("lojas.xlsx")
    print("Colunas de lojas.xlsx:", df.columns.tolist())
    print(df.head())
except Exception as e:
    print(f"Erro: {e}")
