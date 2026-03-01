# MedControl — Sistema de Controle de Validade de Medicamentos

Sistema profissional multi-tenant para controle de validade de medicamentos. Suporta múltiplas redes de farmácias com isolamento de dados por filial, dashboard analítico, geração de relatórios PDF, API REST e arquitetura preparada para integrações externas.

---

## Instalação

```bash
# 1. Clonar e entrar no projeto
git clone <repositorio>
cd validade_med

# 2. Criar ambiente virtual e instalar dependências
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Definir variáveis de ambiente obrigatórias
export SECRET_KEY="sua-chave-secreta-longa-e-aleatoria"
export ADMIN_USER="admin"
export ADMIN_PASS="sua-senha-segura"

# 4. Iniciar o servidor
python app.py

# 5. Acessar no navegador
http://localhost:5000
```

> **Produção (Railway):** configure todas as variáveis via painel de Variables. O app recusa iniciar sem `SECRET_KEY` e `ADMIN_PASS`.

---

## Estrutura do Projeto

```
validade_med/
├── app.py                          # Aplicação principal — rotas, modelos e lógica
├── requirements.txt                # Dependências Python
├── README.md
├── static/
│   └── css/
│       ├── theme.css               # Sistema de temas claro/escuro
│       └── style.css               # Estilos extras
└── templates/
    ├── login.html                  # Autenticação
    ├── index.html                  # Dashboard principal com paginação
    ├── cadastro.html               # Formulário cadastro/edição de medicamentos
    ├── expirado.html               # Tela de assinatura expirada
    ├── alterar_senha.html          # Troca de senha pelo usuário
    ├── planos.html                 # Página de planos e preços
    ├── gerenciar_filiais.html      # Gerenciamento de filiais (dono_rede)
    └── admin/
        ├── dashboard.html          # Painel superadmin — redes e clientes
        ├── rede_form.html          # Formulário nova rede
        ├── rede_detalhe.html       # Detalhe da rede com filiais
        └── confirmar_exclusao.html # Confirmação server-side de exclusão
```

---

## Hierarquia de Acesso

O sistema usa arquitetura **multi-tenant** com três níveis de perfil:

| Perfil | Acesso |
|---|---|
| `superadmin` | Acesso total — gerencia redes, assinaturas, filiais e todos os dados |
| `dono_rede` | Visualiza e edita todas as filiais da sua rede |
| `filial` | Gerencia somente o estoque da própria filial |

---

## Funcionalidades

- **Dashboard** com cards de status, gráfico de perdas (Prejuízo vs. Em estoque) e filtros em tempo real
- **CRUD completo** de medicamentos com validação de todos os campos
- **Classificação automática**: Vencido / Vence em 30 dias / Vence em 60 dias / OK
- **Paginação** — 20 itens por página para performance com grandes volumes
- **Busca** por nome, lote ou código de barras
- **Filtro por filial** disponível para superadmin e dono_rede
- **Relatório PDF** profissional gerado com ReportLab (resumo + tabela completa)
- **API REST** para integração com sistemas externos
- **Feedback** integrado com Telegram (notificação em tempo real)
- **Tema claro/escuro** persistido por usuário no banco de dados
- **Troca de senha** pelo próprio usuário com verificação da senha atual
- **Gerenciamento de assinaturas** com data de expiração, renovação e bloqueio por rede
- **Alertas de renovação** automáticos quando faltam ≤ 10 dias para expirar

---

## API REST

Todos os endpoints exigem autenticação por sessão.

### Listar medicamentos
```
GET /api/v1/medicamentos
GET /api/v1/medicamentos?status=vencido
GET /api/v1/medicamentos?status=alerta_30
GET /api/v1/medicamentos?status=alerta_60
GET /api/v1/medicamentos?status=ok
```

### Buscar por código de barras
```
GET /api/v1/medicamentos/barcode/{codigo}
```

### Criar medicamento via API
```
POST /api/v1/medicamentos
Content-Type: application/json

{
  "nome": "Dipirona 500mg",
  "codigo_barras": "7891234567890",
  "lote": "LT-2024-001",
  "data_validade": "2025-12-31",
  "quantidade": 100,
  "preco_unitario": 2.50,
  "codigo_externo": "CONSYS-001",
  "origem_cadastro": "api_consys"
}
```

---

## Segurança

Todas as medidas de segurança já estão implementadas em produção:

| Medida | Status |
|---|---|
| Senhas com hash `scrypt` (werkzeug) | ✅ Ativo |
| `SECRET_KEY` obrigatória via variável de ambiente | ✅ Ativo |
| `ADMIN_PASS` obrigatória via variável de ambiente | ✅ Ativo |
| CSRF protection em todos os formulários POST (Flask-WTF) | ✅ Ativo |
| Rate limiting no login — 10 tentativas/min por IP | ✅ Ativo |
| Session timeout — 30 minutos de inatividade | ✅ Ativo |
| Cookie seguro — `HttpOnly`, `SameSite=Lax`, `Secure` em produção | ✅ Ativo |
| Headers HTTP — `X-Frame-Options`, `CSP`, `HSTS`, `X-Content-Type-Options` | ✅ Ativo |
| Logs de auditoria — login, logout, cadastro, edição e exclusão | ✅ Ativo |
| Isolamento multi-tenant — filial só acessa os próprios dados | ✅ Ativo |
| Confirmação server-side para exclusão permanente de rede | ✅ Ativo |
| Input validation com `try/except` em todos os POSTs | ✅ Ativo |
| Sanitização do código de barras na API | ✅ Ativo |
| `debug=False` controlado por variável de ambiente | ✅ Ativo |

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | ✅ Sim | Chave para assinatura de sessões. Gere com: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASS` | ✅ Sim | Senha do superadmin criada no primeiro boot |
| `DATABASE_URL` | ✅ Em produção | URL do PostgreSQL (Railway/Supabase). SQLite é usado localmente |
| `ADMIN_USER` | Não | Username do superadmin (padrão: `admin`) |
| `TELEGRAM_TOKEN` | Não | Token do bot Telegram para notificações de feedback |
| `TELEGRAM_CHAT_ID` | Não | ID do chat/grupo que receberá os feedbacks |
| `RESET_DB` | Não | Defina como `1` para recriar todas as tabelas (⚠️ apaga os dados) |
| `FLASK_DEBUG` | Não | Defina como `1` para ativar debug (nunca em produção) |

---

## Banco de Dados

- **Local:** SQLite (`medcontrol.db`) criado automaticamente
- **Produção:** PostgreSQL via Supabase ou Railway
- O `db.create_all()` cria as tabelas automaticamente no primeiro boot
- Para adicionar colunas em tabelas existentes, use `ALTER TABLE` diretamente no banco:

```sql
-- Exemplo: adicionar coluna tema (se necessário em migração manual)
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tema VARCHAR(10) DEFAULT 'light';
```

---

## Integrações Futuras

| Sistema | Status | Endpoint planejado |
|---|---|---|
| Consys ERP | Em breve | `POST /api/v1/sync/consys` |
| SNGPC / ANVISA | Em breve | `POST /api/v1/sync/sngpc` |
| Tasy / MV | Em breve | `POST /api/v1/sync/tasy` |
| ANVISA Lookup | Em breve | `GET /api/v1/anvisa/lookup` |

---

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.13 + Flask 3.0 |
| ORM | Flask-SQLAlchemy 3.1 |
| Banco (produção) | PostgreSQL via psycopg3 |
| Banco (local) | SQLite |
| Segurança | Flask-WTF (CSRF), Flask-Limiter, Werkzeug |
| PDF | ReportLab |
| Frontend | Bootstrap 5.3 + Bootstrap Icons + Chart.js |
| Fontes | Syne + DM Sans (Google Fonts) |
| Deploy | Railway (Gunicorn) |
| Banco hospedado | Supabase |
| Notificações | Telegram Bot API |
