# 🔌 {{NOME_DA_INTEGRACAO}}

## 🎯 Finalidade da Integração

Papel deste portal, API, serviço externo ou protocolo na arquitetura do SOFI.

## 🌐 Detalhes Técnicos

- **Tipo:** Portal Web (Playwright/Selenium) | API REST (requests) | Protocolo Windows COM | Sistema de Arquivos (SMB) | SMTP
- **URL Base / Endpoint:** `https://...`
- **Autenticação:** Credenciais estáticas (Usuário/Senha) | Bearer Token / Sessão dinâmica | Senha de Aplicativo | MAPI Windows
- **Protocolos e Portas:** HTTP/HTTPS (443) | SMTP (587) | SMB (445)

## 📦 Módulos que Utilizam esta Integração

- [[modulo_a]]
- [[modulo_b]]

## 🔄 Mecanismo de Interação

1. Autenticação e handshake inicial
2. Navegação / Chamada de endpoints
3. Extração / Upload de dados
4. Tratamento de sessão e expiração

## 🚨 Resiliência e Falhas Conhecidas

- Padrões de erro comuns (timeouts, alteração de seletores DOM, bloqueio anti-bot, captcha, tela de onboarding)
- Estratégias de bypass ou contorno (stealth scripts, user-agents simulados, retry com delay)

## 🔐 Configuração e Variáveis de Ambiente

- Chaves de configuração no `.env` e `.env.local`

## 🔎 Evidências no Código

- `caminho/arquivo.py`
