from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any, Union

class RetryConfig(BaseModel):
    max_attempts: int = 3
    delay_seconds: int = 120

    @field_validator('max_attempts')
    @classmethod
    def validate_max_attempts(cls, v):
        if v < 1:
            raise ValueError('max_attempts deve ser no mínimo 1.')
        return v

    @field_validator('delay_seconds')
    @classmethod
    def validate_delay_seconds(cls, v):
        if v < 0:
            raise ValueError('delay_seconds não pode ser negativo.')
        return v

class ScheduleConfig(BaseModel):
    type: str = 'cron'
    hour: int
    minute: int
    day_of_week: Optional[str] = None

    @field_validator('hour')
    @classmethod
    def validate_hour(cls, v):
        if not 0 <= v <= 23:
            raise ValueError(f'Hora inválida: {v}. Deve ser entre 0 e 23.')
        return v

    @field_validator('minute')
    @classmethod
    def validate_minute(cls, v):
        if not 0 <= v <= 59:
            raise ValueError(f'Minuto inválido: {v}. Deve ser entre 0 e 59.')
        return v

class JobConfig(BaseModel):
    name: str
    enabled: bool = True
    script: str
    unidade: Optional[str] = None
    schedule: ScheduleConfig
    dias: int = 0
    retry: RetryConfig = RetryConfig()
    depends_on: Optional[str] = None
    condition: Optional[str] = None

    @field_validator('dias')
    @classmethod
    def validate_dias(cls, v):
        if v < 0:
            raise ValueError('dias retroativos não pode ser negativo.')
        return v

class SchedulerSchema(BaseModel):
    enabled: bool = True
    timezone: str = 'America/Sao_Paulo'
    jobs: List[JobConfig]

class NotificationGroup(BaseModel):
    jobs_vinculados: List[str] = []
    emails: List[EmailStr]

class SmtpConfig(BaseModel):
    server_env: str = 'SMTP_SERVER'
    port_env: str = 'SMTP_PORT'
    user_env: str = 'SMTP_USER'
    password_env: str = 'SMTP_PASSWORD'

class NotificacoesSchema(BaseModel):
    smtp: SmtpConfig = SmtpConfig()
    grupos: Dict[str, NotificationGroup]
    enviar_em_sucesso: bool = True
    enviar_em_erro: bool = True

class ParametrosNegocioSchema(BaseModel):
    prazos_pagamento: Dict[str, int]

    @field_validator('prazos_pagamento')
    @classmethod
    def validate_prazos(cls, v):
        for pdv, prazo in v.items():
            if prazo < 0:
                raise ValueError(f'Prazo negativo para PDV {pdv}: {prazo}')
        return v
