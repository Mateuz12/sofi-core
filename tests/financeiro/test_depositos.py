import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
import pytest

import sys

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from departments.financeiro.modules.depositos import script_depositos as sd


def test_normalizar_data_aba_aceita_ponto_e_barra():
    dt1, aba1 = sd.normalizar_data_aba("07.05.2026")
    dt2, aba2 = sd.normalizar_data_aba("07/05/2026")
    assert dt1 == datetime(2026, 5, 7)
    assert aba1 == "07.05.2026"
    assert dt2 == datetime(2026, 5, 7)
    assert aba2 == "07.05.2026"


def test_regras_calculo_credito_padrao_e_911557():
    # Terça-feira 05/05/2026 (weekday == 1)
    terca = datetime(2026, 5, 5)
    # Padrão: Terça -> Quarta (+1 dia = 06/05/2026)
    assert sd.calcular_credito_padrao(terca) == datetime(2026, 5, 6)
    # 911557: Terça -> Sexta (+3 dias = 08/05/2026)
    assert sd.calcular_credito_911557(terca) == datetime(2026, 5, 8)

    # Quinta-feira 07/05/2026 (weekday == 3)
    quinta = datetime(2026, 5, 7)
    # Padrão: Quinta -> Sexta (+1 dia = 08/05/2026)
    assert sd.calcular_credito_padrao(quinta) == datetime(2026, 5, 8)
    # 911557: Quinta -> Segunda (+4 dias = 11/05/2026)
    assert sd.calcular_credito_911557(quinta) == datetime(2026, 5, 11)


def test_controle_duplicidade_sqlite(tmp_path):
    db_file = tmp_path / "test_sofi.db"
    sd.init_depositos_db(db_file)

    dt_dep = datetime(2026, 5, 7)
    dt_cred = datetime(2026, 5, 8)
    chave = sd.gerar_chave_unica(20843, dt_dep, 350.0)
    assert chave == "20843_2026-05-07_350.00"

    # Antes de registrar, não é duplicado
    assert sd.verificar_duplicidade(chave, db_path=db_file) is None

    # Registra sucesso
    sd.registrar_deposito_lancado(
        chave_unica=chave,
        codigo_loja=20843,
        nome_loja="UD SH",
        data_deposito="07.05.2026",
        data_credito="08.05.2026",
        valor=350.0,
        db_path=db_file,
    )

    # Agora deve acusar duplicidade
    reg = sd.verificar_duplicidade(chave, db_path=db_file)
    assert reg is not None
    assert reg["codigo_loja"] == 20843
    assert abs(reg["valor"] - 350.0) < 0.001


def test_executar_bloqueia_duplicidade_e_dry_run_nao_persiste(tmp_path, monkeypatch):
    db_file = tmp_path / "test_sofi.db"
    rel_dir = tmp_path / "relatorios"
    rel_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(sd, "DB_FILE", db_file)
    monkeypatch.setattr(sd, "RELATORIO_DIR", rel_dir)

    # Mock cadastro de lojas e leitura da planilha
    monkeypatch.setattr(
        sd,
        "ler_cadastro_lojas",
        lambda: {
            20843: {
                "nome": "UD SH",
                "conta_origem": "orig_20843",
                "conta_destino": "dest_20843",
                "empresa_id": "emp_20843",
            },
            911557: {
                "nome": "QDB CSH",
                "conta_origem": "orig_911557",
                "conta_destino": "dest_911557",
                "empresa_id": "emp_911557",
            },
        },
    )
    monkeypatch.setattr(
        sd,
        "ler_planilha_rede",
        lambda data_str: [
            {"codigo": 20843, "nome_planilha": "Udi. Shopping", "valor": 400.0},
            {"codigo": 911557, "nome_planilha": "QDB CSH", "valor": 150.5},
        ],
    )

    # 1. Dry-run não chama captura de token nem grava no banco
    exit_code_dry = sd.executar("07.05.2026", is_dry_run=True, forcar_reenvio=False)
    assert exit_code_dry == sd.EXIT_OK
    chave_20843 = sd.gerar_chave_unica(20843, datetime(2026, 5, 7), 400.0)
    assert sd.verificar_duplicidade(chave_20843, db_path=db_file) is None

    # 2. Execução real: envia para a API e grava no banco
    monkeypatch.setattr(sd, "capturar_autenticacao", lambda: ("Bearer token123", "cookie=abc"))
    enviados = []

    def fake_enviar(payload, headers):
        enviados.append(payload)
        return {"status": "SUCESSO", "status_code": 200, "msg": "Ok"}

    monkeypatch.setattr(sd, "enviar_para_api", fake_enviar)
    monkeypatch.setattr(sd.time, "sleep", lambda s: None)

    exit_code_real = sd.executar("07.05.2026", is_dry_run=False, forcar_reenvio=False)
    assert exit_code_real == sd.EXIT_OK
    assert len(enviados) == 2
    assert sd.verificar_duplicidade(chave_20843, db_path=db_file) is not None

    # 3. Segunda execução real para o mesmo dia e valores: deve bloquear ambos por duplicidade sem chamar a API
    enviados.clear()
    exit_code_dup = sd.executar("07.05.2026", is_dry_run=False, forcar_reenvio=False)
    assert exit_code_dup == sd.EXIT_OK
    assert len(enviados) == 0

    # Verifica o último relatório gerado
    relatorios = sorted(rel_dir.glob("relatorio_depositos_*.xlsx"))
    df_ult = pd.read_excel(relatorios[-1])
    assert list(df_ult["Status"]) == ["IGNORADO_DUPLICIDADE", "IGNORADO_DUPLICIDADE"]

    # 4. Com forcar_reenvio=True, deve enviar novamente para a API
    exit_code_force = sd.executar("07.05.2026", is_dry_run=False, forcar_reenvio=True)
    assert exit_code_force == sd.EXIT_OK
    assert len(enviados) == 2


def test_obter_arquivo_rede_usa_ano_da_data_quando_env_ausente(monkeypatch):
    monkeypatch.delenv("DEPOSITOS_PLANILHA_UDI_PATH", raising=False)
    caminho_2027 = sd.obter_arquivo_rede(datetime(2027, 3, 15))
    assert r"\UDI\2027\05-FIN.FECHAMENTO DE CAIXA.CONTROLE DE DEPÓSITO.UDI.2027." in caminho_2027

