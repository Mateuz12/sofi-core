import os
from portal_uploader import PortalUploader

def debug_upload():
    # Caminhos dos arquivos do dia 15 identificados na pasta
    base_path = r"\\srv-dc01\File Server\05-FIN\FECHAMENTO DE CAIXA\IMPORTAÇÃO FINANÇAS GB\UDI\2026\04 ABRIL\15"
    
    files = [
        os.path.join(base_path, "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 20844.15-04-2026.xls"),
        os.path.join(base_path, "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 23275.15-04-2026.xls"),
        os.path.join(base_path, "05-FIN.FECHAMENTO DE CAIXA.IMPORTAÇÃO FINANÇAS GB.UDI.2.1 FECHAMENTO DE CAIXA VD 24417.15-04-2026.xls"),
    ]

    print("--- DEBUG UPLOAD DIA 15 ---")
    print(f"Arquivos para upload: {len(files)}")
    for f in files:
        if os.path.exists(f):
            print(f"  [OK] Encontrado: {os.path.basename(f)}")
        else:
            print(f"  [ERRO] Não encontrado: {f}")
            return

    print("\nIniciando PortalUploader...")
    # Forçamos HEADLESS=False no código para este debug se quiser ver, 
    # mas o uploader já lê do .env. 
    # Vou garantir que use HEADLESS=False se não estiver definido para debug visual.
    os.environ["HEADLESS"] = "False" 
    
    uploader = PortalUploader()
    success = uploader.upload_files(files)
    
    if success:
        print("\n[SUCESSO] O processo de upload foi concluído.")
    else:
        print("\n[FALHA] Falha no processo. Verifique os logs e o print de erro salvo.")

if __name__ == "__main__":
    debug_upload()
