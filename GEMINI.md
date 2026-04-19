# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projeto
**MedControl** — SaaS de controle de validade de medicamentos para farmácias.
- Produção: www.medcontrol.app.br
- Dev solo: Teilon Santos
- Licença: BSL 1.1 → Apache 2.0 em 01/01/2029

## Rodar localmente

```bash
# Ativar venv
source venv/bin/activate

# Rodar dev
flask run
# http://localhost:5000

# Rodar como produção (gunicorn)
gunicorn app:app --workers 2 --bind 0.0.0.0:5000 --timeout 120
```

`.env` mínimo para dev:
```env
SECRET_KEY=<chave_longa>
DATABASE_URL=sqlite:///instance/medcontrol.db
FLASK_ENV=development
FLASK_DEBUG=1
ADMIN_PASS=<sua_senha>
```

**Não há testes automatizados nem lint configurado** no projeto atualmente.

## Arquitetura

Todo o código da aplicação está em **`app.py`** (arquivo único, ~2200 linhas). Não há blueprints.

### Modelos principais (app.py ~160–308)
- `Rede` — farmácia ou rede de farmácias (multi-tenant root)
- `Usuario` — 3 perfis: `superadmin`, `dono_rede`, `filial`
- `Medicamento` — item com validade, vinculado à `Rede` e filial
- `IntegracaoConsys` — config de ERP externo por rede

### Decoradores de acesso (app.py ~350–430)
- `@login_required` — sessão ativa
- `@assinatura_required` — logado + assinatura ativa + email confirmado + termos aceitos
- `@superadmin_required` — apenas superadmin
- `@api_key_required` — header `X-API-Key` (API REST)

### Grupos de rotas
| Grupo | Prefixo |
|---|---|
| Autenticação | `/login`, `/logout`, `/registrar` |
| Dashboard + CRUD | `/`, `/cadastro`, `/editar/<id>`, `/excluir/<id>` |
| Filiais | `/filiais/*` |
| Pagamentos | `/assinar`, `/webhook/mercadopago`, `/pagamento/*` |
| Email | `/confirmar-email`, `/completar-cadastro` |
| Integração Consys | `/integracoes/consys` |
| API REST | `/api/v1/*` |
| Admin (superadmin) | `/admin/*` |
| Utilitários | `/healthz`, `/relatorio/pdf`, `/sistema/notificacoes` |

### Integrações externas
- **Resend** (`RESEND_API_KEY`) — envio de emails (confirmação e alertas de validade)
- **Mercado Pago** (`MP_ACCESS_TOKEN`) — checkout de assinaturas + webhook
- **Consys ERP** — sincronização de medicamentos via REST (em andamento)
- **Telegram** (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`) — feedback de usuários (opcional)

### Jobs agendados
- `POST /sistema/notificacoes` com header `X-Cron-Secret` — envia emails de alerta de validade
- Configurado via cron-job.org

## Regras inegociáveis

- **NUNCA** cores hardcoded em `style=""` ou CSS — sempre `var(--card-bg)`, `var(--text-primary)`, etc. (definidas em `static/css/theme.css`)
- **NUNCA** hardcode credenciais — sempre variáveis de ambiente
- **SEMPRE** confirme a causa no arquivo real antes de diagnosticar um bug
- **NÃO** sugerir Railway (migrou para Render), não reativar scanner de código de barras
- Responder **em português**, direto ao ponto
- Terminar entregas com: `git add . && git commit -m "msg" && git push`

## Deploy (Render)

Push para GitHub dispara deploy automático. Variáveis necessárias no Render:

```
DATABASE_URL, SECRET_KEY, ADMIN_PASS, RESEND_API_KEY, RESEND_FROM,
CRON_SECRET, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, APP_BASE_URL, FLASK_DEBUG
```

Health check: `GET /healthz` (monitorado pelo UptimeRobot).

## Documentação interna

Leia antes de trabalhar em features ou bugs:
- `_docs/01 - Arquitetura e Stack.md` — stack e rotas
- `_docs/02 - Decisoes e Bugs.md` — decisões tomadas e bugs já resolvidos (atualizar após fixes)
- `_docs/03 - Roadmap.md` — backlog e prioridades (atualizar após entregas)
