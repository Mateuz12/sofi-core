# Motor de Conciliação OMNI v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o Motor de Conciliação OMNI v1 para conciliação automatizada de recebíveis de cartão via API REST no FinançasGB em modo `REPORT_ONLY`, com regras desacopladas (`ReconciliationRule`), isolamento estrito de PIX (`REGRA_NAO_IMPLEMENTADA`), persistência de cursor em SQLite e rate limit com jitter (1 a 6s).

**Architecture:** Abordagem Domain-Driven em camadas desacopladas:
- `auth/`: Sessão Playwright headless, login corporativo e cache de cookies com auto-renovação.
- `client/`: Consumidor HTTP tipado para os endpoints `/List/`, `/GetMovimentosDeVendas/` e `/GetConfirmacaoDoCartao/` com jitter randômico e bloqueio seguro de `POST /Conciliar/` em `REPORT_ONLY`.
- `domain/`: Entidades imutáveis, Enums e Strategy de Regras (`OmniCardRule` e `OmniPixRule`).
- `storage/`: Repositório SQLite em modo WAL gerenciando o cursor histórico de dias e auditoria.
- `engine.py`: Orquestrador determinístico do ciclo de conciliação.
- `reporter.py` & `main.py`: Apresentação segregada em console/logs e conformidade com exit codes do SOFI.

**Tech Stack:** Python 3.14, Requests, Playwright, SQLite3 (WAL), Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-22-motor-conciliacao-omni-v1-design.md`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/docs/superpowers/specs/2026-09-22-motor-conciliacao-omni-v1-design.md)

## Global Constraints
- Python: Compatível com o runtime Python 3.14 corporativo do SOFI no Windows Server.
- Root Resolution: Todo executável deve resolver canonicamente `_ROOT` conforme [`obsidian/00_SYSTEM/conventions.md`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/00_SYSTEM/conventions.md).
- Credenciais: Consumidas via `core.sofi_env.load_sofi_env(department="financeiro")`.
- Modo Seguro v1: Bloqueio estrito de qualquer requisição de mutação a `POST /Conciliar/`.
- Rate Limiting: Delay de `random.uniform(1.0, 6.0)` obrigatório entre chamadas HTTP sequenciais.
- Testes: Executáveis via `python -m pytest tests/financeiro/conciliacao_omni/ -v`.

---

### Task 1: Domain Enums, Models & Base Rule Contract

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/enums.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/models.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/rules/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/rules/base.py`
- Test: `tests/financeiro/conciliacao_omni/test_models.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#5-modelo-de-dados-e-persistencia-sqlite`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#61-regras-de-conciliacao-reconciliationrule`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: Biblioteca padrão (`dataclasses`, `enum`, `abc`, `typing`, `datetime`).
- Produces: `MovementStatus`, `RuleType`, `SaleMovement`, `OmniMovement`, `ProcessingDay`, `MatchingOutcome`, `ReconciliationRule`.

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_models.py
import pytest
from datetime import date
from departments.financeiro.modules.conciliacao_omni.domain.enums import MovementStatus, RuleType
from departments.financeiro.modules.conciliacao_omni.domain.models import SaleMovement, OmniMovement, ProcessingDay

def test_enums_definitions():
    assert MovementStatus.MATCH == "MATCH"
    assert MovementStatus.AGUARDANDO_VENDA == "AGUARDANDO_VENDA"
    assert MovementStatus.AMBIGUO == "AMBIGUO"
    assert MovementStatus.REGRA_NAO_IMPLEMENTADA == "REGRA_NAO_IMPLEMENTADA"
    assert RuleType.OMNI_CARD == "OMNI_CARD"
    assert RuleType.OMNI_PIX == "OMNI_PIX"

def test_sale_movement_parsing():
    raw_sale = {
        "_id": "6a983d8e1f05e388ea506d68",
        "EmpresaId": "669e4cd4180f7231fece4799",
        "Documento": "487063551",
        "Valor": 281.35,
        "Data": "2026-09-01T00:00:00Z",
        "Modalidade": "Débito",
        "Venda": {"CodigoDeAutorizacao": "764498"}
    }
    sale = SaleMovement.from_api_dict(raw_sale)
    assert sale.id == "6a983d8e1f05e388ea506d68"
    assert sale.empresa_id == "669e4cd4180f7231fece4799"
    assert sale.valor == 281.35
    assert sale.codigo_autorizacao == "764498"
    assert sale.data == date(2026, 9, 1)

def test_omni_movement_parsing_card():
    raw_card = {
        "_id": "6aad703b76252df57e05ea2b",
        "MeioDeCaptura": "OMNI",
        "EmpresaId": "5cf577e8955f602ab43d9771",
        "Modalidade": "Crédito Parcelado",
        "Valor": 302.9,
        "Data": "2026-09-16T03:00:00Z",
        "Vendas": [
            {
                "CodigoDeAutorizacao": "0764498",
                "NSU": 379195521,
                "Valor": 302.9
            }
        ]
    }
    mov = OmniMovement.from_api_dict(raw_card)
    assert mov.external_id == "6aad703b76252df57e05ea2b"
    assert mov.empresa_id == "5cf577e8955f602ab43d9771"
    assert mov.valor == 302.9
    assert mov.codigo_autorizacao == "0764498"
    assert mov.normalized_auth == "764498"
    assert mov.is_pix is False
    assert mov.tipo_regra == RuleType.OMNI_CARD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_models.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'departments.financeiro.modules.conciliacao_omni'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/domain/enums.py`:
```python
from enum import Enum

class MovementStatus(str, Enum):
    NOVO = "NOVO"
    AGUARDANDO_VENDA = "AGUARDANDO_VENDA"
    MATCH = "MATCH"
    AMBIGUO = "AMBIGUO"
    SEM_CORRESPONDENCIA = "SEM_CORRESPONDENCIA"
    REGRA_NAO_IMPLEMENTADA = "REGRA_NAO_IMPLEMENTADA"
    CONCILIADO = "CONCILIADO"
    ERRO = "ERRO"

class RuleType(str, Enum):
    OMNI_CARD = "OMNI_CARD"
    OMNI_PIX = "OMNI_PIX"
    OUTROS = "OUTROS"
```

Create `departments/financeiro/modules/conciliacao_omni/domain/models.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from .enums import MovementStatus, RuleType

def normalize_auth(code: Optional[str]) -> str:
    if not code:
        return ""
    return str(code).strip().lstrip("0")

@dataclass
class SaleMovement:
    id: str
    empresa_id: str
    valor: float
    data: date
    documento: Optional[str] = None
    codigo_autorizacao: Optional[str] = None
    nsu: Optional[str] = None
    modalidade: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_auth(self) -> str:
        return normalize_auth(self.codigo_autorizacao)

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> "SaleMovement":
        venda_inner = data.get("Venda") or {}
        auth = (
            venda_inner.get("CodigoDeAutorizacao")
            or venda_inner.get("Autorizacao")
            or data.get("CodigoDeAutorizacao")
            or data.get("Autorizacao")
        )
        dt_str = data.get("Data", "")
        dt_val = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date() if dt_str else date.today()

        return cls(
            id=str(data.get("_id") or data.get("Id")),
            empresa_id=str(data.get("EmpresaId", "")),
            valor=round(float(data.get("Valor", 0.0)), 2),
            data=dt_val,
            documento=str(data.get("Documento") or "") if data.get("Documento") else None,
            codigo_autorizacao=str(auth) if auth else None,
            nsu=str(data.get("NSU")) if data.get("NSU") else None,
            modalidade=data.get("Modalidade"),
            raw_payload=data
        )

@dataclass
class OmniMovement:
    external_id: str
    empresa_id: str
    valor: float
    data: date
    meio_captura: str = "OMNI"
    forma_pagamento: str = "CARTAO"
    modalidade: Optional[str] = None
    codigo_autorizacao: Optional[str] = None
    nsu: Optional[str] = None
    tipo_regra: RuleType = RuleType.OMNI_CARD
    status: MovementStatus = MovementStatus.NOVO
    matched_sale_id: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    attempt_count: int = 0
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_auth(self) -> str:
        return normalize_auth(self.codigo_autorizacao)

    @property
    def is_pix(self) -> bool:
        modalidade_upper = (self.modalidade or "").upper()
        forma_upper = (self.forma_pagamento or "").upper()
        return "PIX" in modalidade_upper or "PIX" in forma_upper

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> "OmniMovement":
        vendas = data.get("Vendas") or []
        first_venda = vendas[0] if vendas else {}
        auth = first_venda.get("CodigoDeAutorizacao") or data.get("CodigoDeAutorizacao")
        nsu = first_venda.get("NSU") or data.get("NSU")

        dt_str = data.get("Data", "")
        dt_val = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date() if dt_str else date.today()

        modalidade = data.get("Modalidade") or ""
        is_pix = "PIX" in modalidade.upper()
        tipo_regra = RuleType.OMNI_PIX if is_pix else RuleType.OMNI_CARD

        return cls(
            external_id=str(data.get("_id") or data.get("Id")),
            empresa_id=str(data.get("EmpresaId", "")),
            valor=round(float(data.get("Valor", 0.0)), 2),
            data=dt_val,
            meio_captura=data.get("MeioDeCaptura", "OMNI"),
            forma_pagamento="PIX" if is_pix else "CARTAO",
            modalidade=modalidade,
            codigo_autorizacao=str(auth) if auth else None,
            nsu=str(nsu) if nsu else None,
            tipo_regra=tipo_regra,
            raw_payload=data
        )

@dataclass
class ProcessingDay:
    date: date
    has_pending: bool = False
    has_omni: bool = False
    pending_omni_count: int = 0
    last_checked_at: Optional[datetime] = None
    status: str = "PENDENTE_OMNI"
```

Create `departments/financeiro/modules/conciliacao_omni/domain/rules/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from ..models import OmniMovement, SaleMovement
from ..enums import MovementStatus

@dataclass
class MatchingOutcome:
    status: MovementStatus
    matched_sale_id: Optional[str] = None
    candidate_sale_ids: List[str] = None
    details: str = ""

class ReconciliationRule(ABC):
    @abstractmethod
    def evaluate(self, movement: OmniMovement, sales_pool: List[SaleMovement]) -> MatchingOutcome:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/domain/ tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): domain enums, models and base rule contract"
```

---

### Task 2: Reconciliation Rules Implementation (OmniCardRule & OmniPixRule)

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/domain/rules/omni_card.py`
- Create: `departments/financeiro/modules/conciliacao_omni/domain/rules/omni_pix.py`
- Test: `tests/financeiro/conciliacao_omni/test_omni_card_rule.py`
- Test: `tests/financeiro/conciliacao_omni/test_omni_pix_rule.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#61-regras-de-conciliacao-reconciliationrule`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: `OmniMovement`, `SaleMovement`, `MatchingOutcome`, `MovementStatus`, `ReconciliationRule`.
- Produces: `OmniCardRule`, `OmniPixRule`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/financeiro/conciliacao_omni/test_omni_card_rule.py
from datetime import date
from departments.financeiro.modules.conciliacao_omni.domain.models import OmniMovement, SaleMovement
from departments.financeiro.modules.conciliacao_omni.domain.enums import MovementStatus
from departments.financeiro.modules.conciliacao_omni.domain.rules.omni_card import OmniCardRule

def test_omni_card_rule_single_match():
    card = OmniMovement(
        external_id="card_1",
        empresa_id="emp_10",
        valor=150.00,
        data=date(2026, 9, 10),
        codigo_autorizacao="0012345"
    )
    sales = [
        SaleMovement(id="s1", empresa_id="emp_10", valor=150.00, data=date(2026, 9, 10), codigo_autorizacao="12345"),
        SaleMovement(id="s2", empresa_id="emp_10", valor=200.00, data=date(2026, 9, 10), codigo_autorizacao="99999")
    ]
    rule = OmniCardRule()
    outcome = rule.evaluate(card, sales)

    assert outcome.status == MovementStatus.MATCH
    assert outcome.matched_sale_id == "s1"

def test_omni_card_rule_awaiting_sale():
    card = OmniMovement(
        external_id="card_2",
        empresa_id="emp_10",
        valor=350.00,
        data=date(2026, 9, 10),
        codigo_autorizacao="88888"
    )
    sales = [
        SaleMovement(id="s1", empresa_id="emp_10", valor=150.00, data=date(2026, 9, 10), codigo_autorizacao="12345")
    ]
    rule = OmniCardRule()
    outcome = rule.evaluate(card, sales)

    assert outcome.status == MovementStatus.AGUARDANDO_VENDA
    assert outcome.matched_sale_id is None

def test_omni_card_rule_ambiguous():
    card = OmniMovement(
        external_id="card_3",
        empresa_id="emp_10",
        valor=100.00,
        data=date(2026, 9, 10),
        codigo_autorizacao="777"
    )
    sales = [
        SaleMovement(id="s1", empresa_id="emp_10", valor=100.00, data=date(2026, 9, 10), codigo_autorizacao="0777"),
        SaleMovement(id="s2", empresa_id="emp_10", valor=100.00, data=date(2026, 9, 10), codigo_autorizacao="777")
    ]
    rule = OmniCardRule()
    outcome = rule.evaluate(card, sales)

    assert outcome.status == MovementStatus.AMBIGUO
    assert outcome.matched_sale_id is None
    assert set(outcome.candidate_sale_ids) == {"s1", "s2"}
```

```python
# tests/financeiro/conciliacao_omni/test_omni_pix_rule.py
from datetime import date
from departments.financeiro.modules.conciliacao_omni.domain.models import OmniMovement, SaleMovement
from departments.financeiro.modules.conciliacao_omni.domain.enums import MovementStatus
from departments.financeiro.modules.conciliacao_omni.domain.rules.omni_pix import OmniPixRule

def test_omni_pix_rule_returns_unsupported():
    pix_movement = OmniMovement(
        external_id="pix_1",
        empresa_id="emp_10",
        valor=50.00,
        data=date(2026, 9, 10),
        forma_pagamento="PIX"
    )
    sales = [
        SaleMovement(id="s1", empresa_id="emp_10", valor=50.00, data=date(2026, 9, 10), codigo_autorizacao="PIX123")
    ]
    rule = OmniPixRule()
    outcome = rule.evaluate(pix_movement, sales)

    assert outcome.status == MovementStatus.REGRA_NAO_IMPLEMENTADA
    assert outcome.matched_sale_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_omni_card_rule.py tests/financeiro/conciliacao_omni/test_omni_pix_rule.py -v`  
Expected: FAIL with `ImportError: cannot import name 'OmniCardRule'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/domain/rules/omni_card.py`:
```python
from typing import List
from .base import ReconciliationRule, MatchingOutcome
from ..models import OmniMovement, SaleMovement
from ..enums import MovementStatus

class OmniCardRule(ReconciliationRule):
    """
    Regra v1 para OMNI Cartão:
    Matching: EmpresaId + Valor + CodigoDeAutorizacao (normalizado)
    Resultados:
      - 0 vendas: AGUARDANDO_VENDA
      - 1 venda: MATCH
      - >1 vendas: AMBIGUO
    """
    def evaluate(self, movement: OmniMovement, sales_pool: List[SaleMovement]) -> MatchingOutcome:
        card_auth = movement.normalized_auth
        card_valor = round(movement.valor, 2)
        card_empresa = movement.empresa_id

        matched_sales: List[SaleMovement] = []
        for sale in sales_pool:
            if sale.empresa_id != card_empresa:
                continue
            if round(sale.valor, 2) != card_valor:
                continue
            if sale.normalized_auth and card_auth and sale.normalized_auth == card_auth:
                matched_sales.append(sale)

        count = len(matched_sales)
        if count == 1:
            sale = matched_sales[0]
            return MatchingOutcome(
                status=MovementStatus.MATCH,
                matched_sale_id=sale.id,
                candidate_sale_ids=[sale.id],
                details=f"Correspondência exata encontrada com venda {sale.id}"
            )
        elif count > 1:
            candidate_ids = [s.id for s in matched_sales]
            return MatchingOutcome(
                status=MovementStatus.AMBIGUO,
                matched_sale_id=None,
                candidate_sale_ids=candidate_ids,
                details=f"Ambiguidade: {count} vendas correspondem à mesma chave composta {candidate_ids}"
            )
        else:
            return MatchingOutcome(
                status=MovementStatus.AGUARDANDO_VENDA,
                matched_sale_id=None,
                candidate_sale_ids=[],
                details="Nenhuma venda compatível encontrada na janela até D-1"
            )
```

Create `departments/financeiro/modules/conciliacao_omni/domain/rules/omni_pix.py`:
```python
from typing import List
from .base import ReconciliationRule, MatchingOutcome
from ..models import OmniMovement, SaleMovement
from ..enums import MovementStatus

class OmniPixRule(ReconciliationRule):
    """
    Regra v1 para OMNI PIX:
    Isola os pagamentos PIX sem rodar a regra de cartão, registrando o status
    como REGRA_NAO_IMPLEMENTADA.
    """
    def evaluate(self, movement: OmniMovement, sales_pool: List[SaleMovement]) -> MatchingOutcome:
        return MatchingOutcome(
            status=MovementStatus.REGRA_NAO_IMPLEMENTADA,
            matched_sale_id=None,
            candidate_sale_ids=[],
            details="Regra de conciliação para OMNI PIX ainda não implementada na v1"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_omni_card_rule.py tests/financeiro/conciliacao_omni/test_omni_pix_rule.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/domain/rules/ tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement OmniCardRule and OmniPixRule"
```

---

### Task 3: SQLite Repository & Cursor Persistence

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/storage/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/storage/repository.py`
- Test: `tests/financeiro/conciliacao_omni/test_repository.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#52-esquema-ddl`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: `sqlite3`, `OmniMovement`, `SaleMovement`, `ProcessingDay`, `MatchingOutcome`.
- Produces: `OmniRepository` (`save_processing_day`, `get_active_processing_days`, `save_sales_batch`, `save_movements_batch`, `record_matching_result`, `get_unresolved_movements_count`).

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_repository.py
import pytest
from datetime import date
from departments.financeiro.modules.conciliacao_omni.storage.repository import OmniRepository
from departments.financeiro.modules.conciliacao_omni.domain.models import OmniMovement, SaleMovement, ProcessingDay
from departments.financeiro.modules.conciliacao_omni.domain.enums import MovementStatus, RuleType

@pytest.fixture
def repo():
    # Repositório isolado em memória
    r = OmniRepository(db_path=":memory:")
    r.init_db()
    return r

def test_processing_days_cursor(repo):
    pday = ProcessingDay(date=date(2026, 9, 1), has_pending=True, has_omni=True, pending_omni_count=3, status="PENDENTE_OMNI")
    repo.save_processing_day(pday)

    active = repo.get_active_processing_days()
    assert len(active) == 1
    assert active[0].date == date(2026, 9, 1)
    assert active[0].status == "PENDENTE_OMNI"

def test_save_sales_and_movements(repo):
    sale = SaleMovement(id="s1", empresa_id="emp1", valor=100.0, data=date(2026, 9, 1), codigo_autorizacao="123")
    repo.save_sales_batch([sale])
    saved_sales = repo.get_sales_in_range(date(2026, 9, 1), date(2026, 9, 1))
    assert len(saved_sales) == 1
    assert saved_sales[0].id == "s1"

    mov = OmniMovement(
        external_id="m1",
        empresa_id="emp1",
        valor=100.0,
        data=date(2026, 9, 1),
        codigo_autorizacao="123",
        status=MovementStatus.MATCH,
        tipo_regra=RuleType.OMNI_CARD,
        matched_sale_id="s1"
    )
    repo.save_movements_batch([mov])
    movements = repo.get_movements_by_date(date(2026, 9, 1))
    assert len(movements) == 1
    assert movements[0].status == MovementStatus.MATCH
    assert movements[0].matched_sale_id == "s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_repository.py -v`  
Expected: FAIL with `ImportError: cannot import name 'OmniRepository'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/storage/repository.py`:
```python
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional
from ..domain.models import OmniMovement, SaleMovement, ProcessingDay
from ..domain.enums import MovementStatus, RuleType

DDL_SCRIPT = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS processing_days (
    date TEXT PRIMARY KEY,
    has_pending BOOLEAN NOT NULL DEFAULT 0,
    has_omni BOOLEAN NOT NULL DEFAULT 0,
    pending_omni_count INTEGER NOT NULL DEFAULT 0,
    last_checked_at TIMESTAMP,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS omni_movements (
    external_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    empresa_id TEXT NOT NULL,
    valor REAL NOT NULL,
    meio_captura TEXT NOT NULL,
    forma_pagamento TEXT NOT NULL,
    codigo_autorizacao TEXT,
    nsu TEXT,
    tipo_regra TEXT NOT NULL,
    status TEXT NOT NULL,
    matched_sale_id TEXT,
    last_attempt_at TIMESTAMP,
    attempt_count INTEGER DEFAULT 0,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS sales (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    empresa_id TEXT NOT NULL,
    valor REAL NOT NULL,
    documento TEXT,
    codigo_autorizacao TEXT,
    nsu TEXT,
    modalidade TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS matching_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movement_id TEXT NOT NULL,
    sale_id TEXT,
    status TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY(movement_id) REFERENCES omni_movements(external_id)
);

CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'REPORT_ONLY',
    summary_json TEXT
);
"""

class OmniRepository:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None or db_path != ":memory:":
            default_path = Path(__file__).resolve().parent / "omni_conciliacao.db"
            self.db_path = str(default_path)
        else:
            self.db_path = ":memory:"
        self._memory_conn = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:")

    def get_connection(self) -> sqlite3.Connection:
        if self._memory_conn:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        conn.executescript(DDL_SCRIPT)
        conn.commit()

    def save_processing_day(self, pday: ProcessingDay):
        conn = self.get_connection()
        conn.execute(
            """
            INSERT INTO processing_days (date, has_pending, has_omni, pending_omni_count, last_checked_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                has_pending = excluded.has_pending,
                has_omni = excluded.has_omni,
                pending_omni_count = excluded.pending_omni_count,
                last_checked_at = excluded.last_checked_at,
                status = excluded.status
            """,
            (
                pday.date.isoformat(),
                pday.has_pending,
                pday.has_omni,
                pday.pending_omni_count,
                pday.last_checked_at.isoformat() if pday.last_checked_at else datetime.now().isoformat(),
                pday.status
            )
        )
        conn.commit()

    def get_active_processing_days(self) -> List[ProcessingDay]:
        conn = self.get_connection()
        cursor = conn.execute(
            "SELECT date, has_pending, has_omni, pending_omni_count, last_checked_at, status FROM processing_days WHERE status = 'PENDENTE_OMNI' ORDER BY date ASC"
        )
        results = []
        for row in cursor.fetchall():
            dt = date.fromisoformat(row[0])
            chk = datetime.fromisoformat(row[4]) if row[4] else None
            results.append(ProcessingDay(
                date=dt,
                has_pending=bool(row[1]),
                has_omni=bool(row[2]),
                pending_omni_count=int(row[3]),
                last_checked_at=chk,
                status=row[5]
            ))
        return results

    def save_sales_batch(self, sales: List[SaleMovement]):
        conn = self.get_connection()
        records = [
            (
                s.id,
                s.data.isoformat(),
                s.empresa_id,
                s.valor,
                s.documento,
                s.codigo_autorizacao,
                s.nsu,
                s.modalidade,
                json.dumps(s.raw_payload)
            )
            for s in sales
        ]
        conn.executemany(
            """
            INSERT INTO sales (id, date, empresa_id, valor, documento, codigo_autorizacao, nsu, modalidade, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                valor = excluded.valor,
                codigo_autorizacao = excluded.codigo_autorizacao,
                raw_json = excluded.raw_json
            """,
            records
        )
        conn.commit()

    def get_sales_in_range(self, start_date: date, end_date: date) -> List[SaleMovement]:
        conn = self.get_connection()
        cursor = conn.execute(
            "SELECT id, date, empresa_id, valor, documento, codigo_autorizacao, nsu, modalidade, raw_json FROM sales WHERE date >= ? AND date <= ?",
            (start_date.isoformat(), end_date.isoformat())
        )
        sales = []
        for row in cursor.fetchall():
            raw = json.loads(row[8]) if row[8] else {}
            sales.append(SaleMovement(
                id=row[0],
                data=date.fromisoformat(row[1]),
                empresa_id=row[2],
                valor=float(row[3]),
                documento=row[4],
                codigo_autorizacao=row[5],
                nsu=row[6],
                modalidade=row[7],
                raw_payload=raw
            ))
        return sales

    def save_movements_batch(self, movements: List[OmniMovement]):
        conn = self.get_connection()
        now_str = datetime.now().isoformat()
        records = [
            (
                m.external_id,
                m.data.isoformat(),
                m.empresa_id,
                m.valor,
                m.meio_captura,
                m.forma_pagamento,
                m.codigo_autorizacao,
                m.nsu,
                m.tipo_regra.value,
                m.status.value,
                m.matched_sale_id,
                now_str,
                m.attempt_count + 1,
                json.dumps(m.raw_payload)
            )
            for m in movements
        ]
        conn.executemany(
            """
            INSERT INTO omni_movements (
                external_id, date, empresa_id, valor, meio_captura, forma_pagamento,
                codigo_autorizacao, nsu, tipo_regra, status, matched_sale_id,
                last_attempt_at, attempt_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_id) DO UPDATE SET
                status = excluded.status,
                matched_sale_id = excluded.matched_sale_id,
                last_attempt_at = excluded.last_attempt_at,
                attempt_count = omni_movements.attempt_count + 1,
                raw_json = excluded.raw_json
            """,
            records
        )
        conn.commit()

    def get_movements_by_date(self, dt: date) -> List[OmniMovement]:
        conn = self.get_connection()
        cursor = conn.execute(
            "SELECT external_id, date, empresa_id, valor, meio_captura, forma_pagamento, codigo_autorizacao, nsu, tipo_regra, status, matched_sale_id, attempt_count, raw_json FROM omni_movements WHERE date = ?",
            (dt.isoformat(),)
        )
        movements = []
        for row in cursor.fetchall():
            raw = json.loads(row[12]) if row[12] else {}
            movements.append(OmniMovement(
                external_id=row[0],
                data=date.fromisoformat(row[1]),
                empresa_id=row[2],
                valor=float(row[3]),
                meio_captura=row[4],
                forma_pagamento=row[5],
                codigo_autorizacao=row[6],
                nsu=row[7],
                tipo_regra=RuleType(row[8]),
                status=MovementStatus(row[9]),
                matched_sale_id=row[10],
                attempt_count=int(row[11]),
                raw_payload=raw
            ))
        return movements
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_repository.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/storage/ tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement SQLite OmniRepository for cursor and movements"
```

---

### Task 4: Playwright Session Manager & Cookie Cache

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/auth/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/auth/session_manager.py`
- Test: `tests/financeiro/conciliacao_omni/test_session_manager.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#42-fluxo-de-autenticacao-playwright`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: Playwright, `.env` via `core.sofi_env`.
- Produces: `SessionManager` (`get_cookie_header()`, `refresh_session()`, `is_cache_valid()`).

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_session_manager.py
import pytest
import json
import time
from pathlib import Path
from departments.financeiro.modules.conciliacao_omni.auth.session_manager import SessionManager

def test_cache_validity_and_load(tmp_path):
    cache_file = tmp_path / ".session_cookie.json"
    cache_data = {
        "cookie": "ASP.NET_SessionId=xyz123; token=abc",
        "timestamp": time.time()
    }
    cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    sm = SessionManager(cache_path=str(cache_file))
    assert sm.is_cache_valid() is True
    assert sm.get_cookie_header() == "ASP.NET_SessionId=xyz123; token=abc"

def test_cache_expired(tmp_path):
    cache_file = tmp_path / ".session_cookie.json"
    cache_data = {
        "cookie": "expired_cookie",
        "timestamp": time.time() - 8000 # > 2h
    }
    cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    sm = SessionManager(cache_path=str(cache_file), ttl_seconds=7200)
    assert sm.is_cache_valid() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_session_manager.py -v`  
Expected: FAIL with `ImportError: cannot import name 'SessionManager'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/auth/session_manager.py`:
```python
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict

_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and not (_ROOT / ".git").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

DOMINIO_API = "financasgb.grupoboticario.com.br"

class SessionManager:
    def __init__(self, cache_path: Optional[str] = None, ttl_seconds: int = 7200):
        if cache_path:
            self.cache_file = Path(cache_path)
        else:
            self.cache_file = Path(__file__).resolve().parent / ".session_cookie.json"
        self.ttl_seconds = ttl_seconds

    def is_cache_valid(self) -> bool:
        if not self.cache_file.exists():
            return False
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            ts = data.get("timestamp", 0)
            cookie = data.get("cookie", "")
            return bool(cookie and (time.time() - ts < self.ttl_seconds))
        except Exception:
            return False

    def get_cookie_header(self, force_refresh: bool = False) -> str:
        if not force_refresh and self.is_cache_valid():
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return data["cookie"]
        return self.refresh_session()

    def refresh_session(self) -> str:
        cookie_str = self._capture_via_playwright()
        self.cache_file.write_text(
            json.dumps({"cookie": cookie_str, "timestamp": time.time()}),
            encoding="utf-8"
        )
        return cookie_str

    def _capture_via_playwright(self) -> str:
        from playwright.sync_api import sync_playwright

        email = os.getenv("FINANCAS_UDI_USER")
        senha = os.getenv("FINANCAS_UDI_PASS")
        url_login = os.getenv("FINANCAS_URL")
        headless = os.getenv("HEADLESS", "true").lower() == "true"

        if not all([email, senha, url_login]):
            raise ValueError("Credenciais FINANCAS_UDI_USER, FINANCAS_UDI_PASS ou FINANCAS_URL não definidas no .env")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            page.goto(url_login)
            page.locator('//*[@id="email"]').fill(email)
            page.locator('//*[@id="input-button-icon-right"]').fill(senha)
            time.sleep(2)
            page.locator('//*[@id="login-root"]/div/div/div[2]/div/div/form/button').click()

            time.sleep(5)
            # Tratamento botão Continuar
            for sel in ["button:has-text('Continuar')", "text='Continuar'"]:
                if page.locator(sel).first.is_visible(timeout=2000):
                    page.locator(sel).first.click()
                    time.sleep(5)
                    break

            # Navega para o menu de conciliação
            page.wait_for_selector('//*[@id="mfe-sidebar-react"]', state="attached", timeout=30000)
            menu_concilia = page.locator('//*[@id="mfe-sidebar-react"]/div/nav/div[2]/div[3]/a/p')
            menu_concilia.wait_for(state="visible", timeout=30000)
            menu_concilia.click()

            # Clica no checkbox especificado
            checkbox = page.locator('//*[@id="tabstrip-1"]/div[1]/div/label[2]/input')
            checkbox.wait_for(state="attached", timeout=30000)
            checkbox.click(force=True)
            time.sleep(3)

            cookies = context.cookies()
            browser.close()

        cookies_financas = [c for c in cookies if DOMINIO_API in c.get("domain", "")]
        if not cookies_financas:
            cookies_financas = cookies

        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_financas])
        if not cookie_str:
            raise RuntimeError("Não foi possível capturar os cookies de sessão no FinançasGB")
        return cookie_str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_session_manager.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/auth/ tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement SessionManager with cookie caching and playwright auth"
```

---

### Task 5: HTTP Client with Jitter & Report-Only Guard

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/client/__init__.py`
- Create: `departments/financeiro/modules/conciliacao_omni/client/financas_client.py`
- Test: `tests/financeiro/conciliacao_omni/test_financas_client.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#41-endpoints-do-financasgb-httpsfinancasgbgrupoboticariocombrconciliacaoapi`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#43-rate-limit-e-jitter`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: `requests.Session`, `SessionManager`, `SaleMovement`, `OmniMovement`, `ProcessingDay`.
- Produces: `FinancasClient` (`get_pendencias_list`, `get_movimentos_vendas`, `get_confirmacao_cartao`, `conciliar`).

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_financas_client.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from departments.financeiro.modules.conciliacao_omni.client.financas_client import FinancasClient

@pytest.fixture
def mock_session_manager():
    sm = MagicMock()
    sm.get_cookie_header.return_value = "session_cookie_mock"
    return sm

def test_report_only_guard(mock_session_manager):
    client = FinancasClient(session_manager=mock_session_manager, mode="REPORT_ONLY")
    with pytest.raises(PermissionError, match="bloqueada em modo REPORT_ONLY"):
        client.conciliar(cartoes=["c1"], ids=["s1"])

@patch("time.sleep")
def test_jitter_is_applied(mock_sleep, mock_session_manager):
    client = FinancasClient(session_manager=mock_session_manager)
    client._throttle()
    mock_sleep.assert_called_once()
    sleep_val = mock_sleep.call_args[0][0]
    assert 1.0 <= sleep_val <= 6.0

def test_get_pendencias_list_parsing(mock_session_manager):
    client = FinancasClient(session_manager=mock_session_manager)
    fake_response = {
        "Result": [
            {"Data": "2026-09-01T00:00:00Z", "MovimentosPendentes": 2, "TodosRegistrosConciliados": False},
            {"Data": "2026-09-03T00:00:00Z", "TodosRegistrosConciliados": True}
        ],
        "Ok": True
    }
    with patch.object(client.session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response
        mock_get.return_value = mock_resp

        pdays = client.get_pendencias_list(data_ref=date(2026, 9, 22))
        assert len(pdays) == 2
        assert pdays[0].has_pending is True
        assert pdays[0].pending_omni_count == 2
        assert pdays[1].has_pending is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_financas_client.py -v`  
Expected: FAIL with `ImportError: cannot import name 'FinancasClient'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/client/financas_client.py`:
```python
import time
import random
import requests
from datetime import date
from typing import List, Dict, Any, Optional
from ..domain.models import SaleMovement, OmniMovement, ProcessingDay

BASE_URL = "https://financasgb.grupoboticario.com.br/ConciliacaoAPI"

class FinancasClient:
    def __init__(self, session_manager=None, mode: str = "REPORT_ONLY"):
        self.session_manager = session_manager
        self.mode = mode.upper()
        self.session = requests.Session()

    def _throttle(self):
        delay = random.uniform(1.0, 6.0)
        time.sleep(delay)

    def _get_headers(self) -> Dict[str, str]:
        cookie = self.session_manager.get_cookie_header() if self.session_manager else ""
        return {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    def get_pendencias_list(self, data_ref: date, empresas_ids: str = "") -> List[ProcessingDay]:
        self._throttle()
        url = f"{BASE_URL}/List/"
        params = {
            "data": f"{data_ref.isoformat()}T16:48:18.728Z",
            "empresasIds": empresas_ids,
            "firstDisplay": "true"
        }
        res = self.session.get(url, params=params, headers=self._get_headers(), timeout=30)
        res.raise_for_status()
        data = res.json()

        days = []
        for item in data.get("Result") or []:
            dt_str = item.get("Data", "")[:10]
            dt = date.fromisoformat(dt_str)
            pendentes = int(item.get("MovimentosPendentes") or 0)
            total_conciliado = bool(item.get("TodosRegistrosConciliados", False))
            has_pending = pendentes > 0 or not total_conciliado

            days.append(ProcessingDay(
                date=dt,
                has_pending=has_pending,
                has_omni=has_pending,
                pending_omni_count=pendentes,
                status="PENDENTE_OMNI" if has_pending else "CONCILIADO"
            ))
        return days

    def get_movimentos_vendas(self, de: date, ate: date, empresas_ids: str = "") -> List[SaleMovement]:
        self._throttle()
        url = f"{BASE_URL}/GetMovimentosDeVendas/"
        params = {
            "de": f"{de.isoformat()}T03:00:00.000Z",
            "ate": f"{ate.isoformat()}T03:00:00.000Z",
            "empresasIds": empresas_ids
        }
        res = self.session.get(url, params=params, headers=self._get_headers(), timeout=30)
        res.raise_for_status()
        data = res.json()

        return [SaleMovement.from_api_dict(item) for item in data.get("Result") or []]

    def get_confirmacao_cartao(self, data_ref: date, empresas_ids: str = "") -> List[OmniMovement]:
        self._throttle()
        url = f"{BASE_URL}/GetConfirmacaoDoCartao/"
        params = {
            "data": f"{data_ref.isoformat()}T03:00:00.000Z",
            "conciliado": "false",
            "empresasIds": empresas_ids,
            "exibirMovimentosDeAjustes": "false"
        }
        res = self.session.get(url, params=params, headers=self._get_headers(), timeout=30)
        res.raise_for_status()
        data = res.json()

        movements = []
        for item in data.get("Result") or []:
            mov = OmniMovement.from_api_dict(item)
            if mov.meio_captura == "OMNI":
                movements.append(mov)
        return movements

    def conciliar(self, cartoes: List[str], ids: List[str], justificativa: Optional[str] = None):
        if self.mode == "REPORT_ONLY":
            raise PermissionError("Ação de conciliação (POST /Conciliar/) bloqueada em modo REPORT_ONLY.")
        raise NotImplementedError("POST /Conciliar/ não ativado na versão 1.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_financas_client.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/client/ tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement FinancasClient with jitter and report-only guard"
```

---

### Task 6: Orchestration Engine (OmniReconciliationEngine)

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/engine.py`
- Test: `tests/financeiro/conciliacao_omni/test_engine.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#62-ciclo-de-orquestracao-enginepy`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)

**Interfaces:**
- Consumes: `FinancasClient`, `OmniRepository`, `OmniCardRule`, `OmniPixRule`.
- Produces: `OmniReconciliationEngine` (`run_reconciliation_cycle(ref_date)`).

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_engine.py
import pytest
from unittest.mock import MagicMock
from datetime import date
from departments.financeiro.modules.conciliacao_omni.engine import OmniReconciliationEngine
from departments.financeiro.modules.conciliacao_omni.storage.repository import OmniRepository
from departments.financeiro.modules.conciliacao_omni.domain.models import ProcessingDay, SaleMovement, OmniMovement
from departments.financeiro.modules.conciliacao_omni.domain.enums import MovementStatus, RuleType

@pytest.fixture
def repo():
    r = OmniRepository(db_path=":memory:")
    r.init_db()
    return r

def test_engine_reconciliation_cycle(repo):
    client = MagicMock()
    # Dia 1 com pendência, Dia 2 sem pendência
    client.get_pendencias_list.return_value = [
        ProcessingDay(date=date(2026, 9, 1), has_pending=True, status="PENDENTE_OMNI"),
        ProcessingDay(date=date(2026, 9, 2), has_pending=False, status="CONCILIADO")
    ]
    # Vendas de 01 a 21
    client.get_movimentos_vendas.return_value = [
        SaleMovement(id="s1", empresa_id="emp1", valor=100.0, data=date(2026, 9, 1), codigo_autorizacao="AUTH100")
    ]
    # Movimentos do dia 01: 1 Cartão (match) e 1 PIX
    client.get_confirmacao_cartao.return_value = [
        OmniMovement(external_id="m_card", empresa_id="emp1", valor=100.0, data=date(2026, 9, 1), codigo_autorizacao="AUTH100", forma_pagamento="CARTAO", tipo_regra=RuleType.OMNI_CARD),
        OmniMovement(external_id="m_pix", empresa_id="emp1", valor=50.0, data=date(2026, 9, 1), forma_pagamento="PIX", tipo_regra=RuleType.OMNI_PIX)
    ]

    engine = OmniReconciliationEngine(client=client, repository=repo)
    summary = engine.run_reconciliation_cycle(ref_date=date(2026, 9, 22))

    assert summary["days_processed"] == 1
    assert summary["matches"] == 1
    assert summary["unsupported_pix"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_engine.py -v`  
Expected: FAIL with `ImportError: cannot import name 'OmniReconciliationEngine'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/engine.py`:
```python
from datetime import date, timedelta
from typing import Dict, Any, List
from .client.financas_client import FinancasClient
from .storage.repository import OmniRepository
from .domain.rules.omni_card import OmniCardRule
from .domain.rules.omni_pix import OmniPixRule
from .domain.enums import MovementStatus, RuleType
from .domain.models import OmniMovement, SaleMovement

class OmniReconciliationEngine:
    def __init__(self, client: FinancasClient, repository: OmniRepository):
        self.client = client
        self.repo = repository
        self.card_rule = OmniCardRule()
        self.pix_rule = OmniPixRule()

    def run_reconciliation_cycle(self, ref_date: Optional[date] = None) -> Dict[str, Any]:
        today = ref_date or date.today()
        d_minus_one = today - timedelta(days=1)
        start_of_month = date(today.year, today.month, 1)

        # 1. Descoberta de Pendências (/List/)
        pendencias_dias = self.client.get_pendencias_list(data_ref=today)
        for pday in pendencias_dias:
            self.repo.save_processing_day(pday)

        # 2. Coleta de Vendas (01 até D-1)
        sales_pool: List[SaleMovement] = self.client.get_movimentos_vendas(de=start_of_month, ate=d_minus_one)
        self.repo.save_sales_batch(sales_pool)

        # 3. Processamento dos dias ativos no cursor (até D-1)
        active_days = [d for d in self.repo.get_active_processing_days() if d.date <= d_minus_one]

        total_matches = 0
        total_waiting_sale = 0
        total_ambiguous = 0
        total_pix_unsupported = 0

        for day in active_days:
            movements = self.client.get_confirmacao_cartao(data_ref=day.date)
            for mov in movements:
                if mov.is_pix or mov.tipo_regra == RuleType.OMNI_PIX:
                    outcome = self.pix_rule.evaluate(mov, sales_pool)
                    total_pix_unsupported += 1
                else:
                    outcome = self.card_rule.evaluate(mov, sales_pool)
                    if outcome.status == MovementStatus.MATCH:
                        total_matches += 1
                    elif outcome.status == MovementStatus.AGUARDANDO_VENDA:
                        total_waiting_sale += 1
                    elif outcome.status == MovementStatus.AMBIGUO:
                        total_ambiguous += 1

                mov.status = outcome.status
                mov.matched_sale_id = outcome.matched_sale_id

            self.repo.save_movements_batch(movements)

        return {
            "ref_date": today.isoformat(),
            "window_sales": f"{start_of_month.isoformat()} a {d_minus_one.isoformat()}",
            "days_processed": len(active_days),
            "matches": total_matches,
            "waiting_sale": total_waiting_sale,
            "ambiguous": total_ambiguous,
            "unsupported_pix": total_pix_unsupported
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_engine.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/engine.py tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement OmniReconciliationEngine orchestration loop"
```

---

### Task 7: Operational Reporter & CLI Entrypoint

**Files:**
- Create: `departments/financeiro/modules/conciliacao_omni/reporter.py`
- Create: `departments/financeiro/modules/conciliacao_omni/main.py`
- Test: `tests/financeiro/conciliacao_omni/test_reporter.py`

**Architecture Reference:**
- [`obsidian/01_DOMAINS/modulo_conciliacao_omni.md#7-formato-do-relatorio-e-exit-codes`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/01_DOMAINS/modulo_conciliacao_omni.md)
- [`obsidian/00_SYSTEM/conventions.md#13-registro-de-logs-e-auditoria-log_execution`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/00_SYSTEM/conventions.md)
- [`obsidian/00_SYSTEM/conventions.md#14-padrao-de-exit-codes-para-jobs-do-scheduler`](file:///C:/Users/Mateus%20Henrique/Documents/GitHub/sofi-core/obsidian/00_SYSTEM/conventions.md)

**Interfaces:**
- Consumes: `OmniRepository`, `summary_dict`.
- Produces: `OmniReporter.generate_text_report()`, CLI `main()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/financeiro/conciliacao_omni/test_reporter.py
from departments.financeiro.modules.conciliacao_omni.reporter import OmniReporter

def test_reporter_formatting():
    summary = {
        "ref_date": "2026-09-22",
        "window_sales": "2026-09-01 a 2026-09-21",
        "days_processed": 5,
        "matches": 176,
        "waiting_sale": 18,
        "ambiguous": 6,
        "unsupported_pix": 24
    }
    report_text = OmniReporter.generate_text_report(summary)
    assert "MOTOR DE CONCILIAÇÃO OMNI v1" in report_text
    assert "REPORT_ONLY" in report_text
    assert "MATCH (Correspondência Exata):   176" in report_text
    assert "REGRA NÃO IMPLEMENTADA:           24" in report_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_reporter.py -v`  
Expected: FAIL with `ImportError: cannot import name 'OmniReporter'`

- [ ] **Step 3: Write minimal implementation**

Create `departments/financeiro/modules/conciliacao_omni/reporter.py`:
```python
from typing import Dict, Any

class OmniReporter:
    @staticmethod
    def generate_text_report(summary: Dict[str, Any]) -> str:
        lines = [
            "=" * 80,
            "SOFI - MOTOR DE CONCILIAÇÃO OMNI v1 (MODO REPORT_ONLY)",
            f"Referência: {summary.get('ref_date')} | Janela Vendas: {summary.get('window_sales')}",
            "=" * 80,
            "",
            "[RESUMO CONSOLIDADO DO PERÍODO]",
            "-" * 80,
            f"Dias com OMNI Ativos Processados: {summary.get('days_processed', 0)}",
            "",
            "OMNI CARTÃO:",
            f"  MATCH (Correspondência Exata):   {summary.get('matches', 0)}",
            f"  AGUARDANDO VENDA:                 {summary.get('waiting_sale', 0)}",
            f"  AMBÍGUO (Múltiplas Vendas):        {summary.get('ambiguous', 0)}",
            "",
            "OMNI PIX:",
            f"  REGRA NÃO IMPLEMENTADA:           {summary.get('unsupported_pix', 0)}",
            "=" * 80
        ]
        return "\n".join(lines)
```

Create `departments/financeiro/modules/conciliacao_omni/main.py`:
```python
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve()
while not (_ROOT / "core").exists() and not (_ROOT / ".git").exists() and _ROOT != _ROOT.parent:
    _ROOT = _ROOT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sofi_env import load_sofi_env
load_sofi_env(department="financeiro")

from core.database.logger import log_execution
from departments.financeiro.modules.conciliacao_omni.auth.session_manager import SessionManager
from departments.financeiro.modules.conciliacao_omni.client.financas_client import FinancasClient
from departments.financeiro.modules.conciliacao_omni.storage.repository import OmniRepository
from departments.financeiro.modules.conciliacao_omni.engine import OmniReconciliationEngine
from departments.financeiro.modules.conciliacao_omni.reporter import OmniReporter

EXIT_OK = 0
EXIT_RETRYABLE = 1
EXIT_PERMANENT = 2
EXIT_SEM_FATURAMENTO = 3

@log_execution(modulo="ConciliacaoOMNI")
def run():
    session_mgr = SessionManager()
    client = FinancasClient(session_manager=session_mgr, mode="REPORT_ONLY")
    repo = OmniRepository()
    repo.init_db()

    engine = OmniReconciliationEngine(client=client, repository=repo)
    summary = engine.run_reconciliation_cycle()

    report_text = OmniReporter.generate_text_report(summary)
    print(report_text)

    if summary.get("days_processed", 0) == 0:
        return EXIT_SEM_FATURAMENTO
    return EXIT_OK

if __name__ == "__main__":
    try:
        exit_code = run()
        sys.exit(exit_code or EXIT_OK)
    except TimeoutError:
        sys.exit(EXIT_RETRYABLE)
    except Exception as err:
        print(f"Erro fatal: {err}", file=sys.stderr)
        sys.exit(EXIT_PERMANENT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/financeiro/conciliacao_omni/test_reporter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add departments/financeiro/modules/conciliacao_omni/reporter.py departments/financeiro/modules/conciliacao_omni/main.py tests/financeiro/conciliacao_omni/
git commit -m "feat(conciliacao_omni): implement OmniReporter and CLI main entrypoint"
```
