# 💊 MedControl

> **SaaS de controle de validade de medicamentos para farmácias e redes farmacêuticas.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat&logo=flask)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?style=flat&logo=supabase)](https://supabase.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 📋 Sobre o Projeto

O **MedControl** é um sistema web multi-tenant para controle de validade de medicamentos, voltado para farmácias independentes e redes farmacêuticas. Permite que donos de rede e filiais cadastrem, monitorem e exportem relatórios de medicamentos com alertas automáticos de vencimento.

Acesse em produção: **[medcontrol.app.br](https://medcontrol.app.br)**

---

## ✨ Funcionalidades

- **Dashboard em tempo real** com cards de status (Vencidos, 30 dias, 60 dias, OK)
- **Cadastro de medicamentos** com código de barras (EAN-13), lote, validade, fabricante e preço
- **Alertas automáticos por e-mail** próximos ao vencimento
- **Exportação em PDF** do estoque completo
- **Análise de Perdas** com gráfico de prejuízo por vencimento
- **Multi-tenant**: cada rede tem suas próprias filiais e usuários isolados
- **API REST** para integração com ERPs e sistemas externos (Consys, Tasy, SNGPC)
- **Modo claro/escuro** responsivo, com suporte mobile completo
- **Painel Admin** para gerenciamento de redes, planos e assinaturas

---

## 🏗️ Arquitetura

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Flask 3 |
| ORM | SQLAlchemy |
| Banco de dados | PostgreSQL (Supabase) |
| E-mail | Resend |
| Frontend | Bootstrap 5 + Vanilla JS |
| Fontes | Syne + DM Sans (Google Fonts) |

### Estrutura de Perfis (Multi-tenant)

```
superadmin
└── Gerencia todas as redes e planos

dono_rede
└── Acessa todas as filiais da sua rede

filial
└── Acessa apenas o estoque da própria filial
```

### Estrutura de Pastas

```
medcontrol/
├── app.py                  # Aplicação principal (rotas, models, lógica)
├── requirements.txt
├── static/
│   └── css/
│       └── theme.css       # Variáveis de tema claro/escuro
└── templates/
    ├── index.html          # Dashboard principal
    ├── cadastro.html       # Cadastro de medicamentos
    ├── planos.html         # Planos & Preços
    ├── alterar_senha.html  # Minha Conta
    ├── gerenciar_filiais.html
    └── admin/
        ├── dashboard.html  # Painel superadmin
        ├── rede_detalhe.html
        └── rede_form.html
```

---

## 🚀 Rodando Localmente

### Pré-requisitos

- Python 3.11+
- PostgreSQL (ou conta no [Supabase](https://supabase.com) — plano gratuito funciona)
- Conta no [Resend](https://resend.com) para envio de e-mails (opcional em dev)

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/medcontrol.git
cd medcontrol

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais
```

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/medcontrol
SECRET_KEY=sua_chave_secreta_aqui
RESEND_API_KEY=re_xxxxxxxxxxxx
RESEND_FROM=noreply@medcontrol.app.br
ADMIN_PASS=senha_do_superadmin
CRON_SECRET=chave_para_cron_jobs
```

> ⚠️ **Nunca commite o arquivo `.env`**. Ele já está no `.gitignore`.

### Rodando

```bash
flask run
# Acesse: http://localhost:5000
```

Na primeira execução, as tabelas são criadas automaticamente via `db.create_all()`.

O superadmin padrão é criado com o usuário `admin` e a senha definida em `ADMIN_PASS`.

---

## 🔌 API REST

O MedControl expõe uma API REST para integração com ERPs e sistemas externos (Consys, Tasy, SNGPC, MV, etc.).

### Autenticação

Todas as requisições devem incluir a API Key no header:

```http
X-API-Key: sua_api_key_aqui
```

A API Key é gerada por rede/filial no painel administrativo.

### Base URL

```
https://medcontrol.app.br/api/v1
```

---

### Endpoints

#### `GET /medicamentos`

Lista todos os medicamentos da rede/filial autenticada.

**Resposta:**
```json
[
  {
    "id": 1,
    "nome": "Dipirona Sódica 500mg",
    "codigo_barras": "7891234567890",
    "lote": "LT-2024-001",
    "fabricante": "EMS",
    "data_validade": "2026-06-30",
    "quantidade": 100,
    "preco_unitario": 2.50,
    "status": "ok",
    "filial_id": 3
  }
]
```

---

#### `POST /medicamentos`

Cadastra um novo medicamento via integração externa.

**Body (JSON):**
```json
{
  "nome": "Amoxicilina 500mg",
  "codigo_barras": "7891234500001",
  "lote": "LT-2025-042",
  "fabricante": "Medley",
  "data_validade": "2027-03-15",
  "quantidade": 50,
  "preco_unitario": 8.90,
  "filial_id": 3,
  "origem": "consys",
  "codigo_externo": "CONSYS-00142"
}
```

**Campos obrigatórios:** `nome`, `lote`, `data_validade`, `quantidade`

**Resposta de sucesso (`201 Created`):**
```json
{
  "ok": true,
  "id": 42,
  "message": "Medicamento cadastrado com sucesso"
}
```

**Resposta de erro (`400 Bad Request`):**
```json
{
  "ok": false,
  "error": "Campo 'data_validade' é obrigatório"
}
```

---

#### `PUT /medicamentos/{id}`

Atualiza um medicamento existente.

**Body (JSON):** mesmos campos do `POST` (todos opcionais).

---

#### `DELETE /medicamentos/{id}`

Remove um medicamento.

**Resposta (`200 OK`):**
```json
{ "ok": true, "message": "Medicamento removido" }
```

---

### Status dos Medicamentos

| Valor | Significado |
|-------|-------------|
| `vencido` | Data de validade já passou |
| `30_dias` | Vence em até 30 dias |
| `60_dias` | Vence entre 31 e 60 dias |
| `ok` | Vence em mais de 60 dias |

---

### Exemplo de Integração (curl)

```bash
# Listar medicamentos
curl -H "X-API-Key: sua_chave" \
     https://medcontrol.app.br/api/v1/medicamentos

# Cadastrar medicamento
curl -X POST \
     -H "X-API-Key: sua_chave" \
     -H "Content-Type: application/json" \
     -d '{"nome":"Dipirona 500mg","lote":"LT-001","data_validade":"2027-01-01","quantidade":100}' \
     https://medcontrol.app.br/api/v1/medicamentos
```

### Exemplo de Integração (Python)

```python
import requests

API_KEY = "sua_api_key"
BASE_URL = "https://medcontrol.app.br/api/v1"

headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Cadastrar medicamento
payload = {
    "nome": "Omeprazol 20mg",
    "lote": "LT-2025-099",
    "data_validade": "2027-06-01",
    "quantidade": 200,
    "preco_unitario": 12.00,
    "origem": "consys"
}

response = requests.post(f"{BASE_URL}/medicamentos", json=payload, headers=headers)
print(response.json())
```

---

## 📧 Alertas de Vencimento (Cron Job)

O endpoint `/cron/alertas` deve ser chamado diariamente por um scheduler externo para disparar e-mails de alerta.

```http
POST /cron/alertas
Authorization: Bearer {CRON_SECRET}
```

Você pode usar [cron-job.org](https://cron-job.org) (gratuito) apontando para esse endpoint.

---

## 🔒 Segurança

- Senhas armazenadas com hash `bcrypt`
- Proteção CSRF em todos os formulários (`Flask-WTF`)
- Sessões server-side com `SECRET_KEY`
- Isolamento total entre redes (multi-tenant por `rede_id`)
- Variáveis sensíveis exclusivamente em variáveis de ambiente

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Commit: `git commit -m 'feat: minha feature'`
4. Push: `git push origin feature/minha-feature`
5. Abra um Pull Request

---

## 📄 Licença

Distribuído sob a licença MIT. Veja [`LICENSE`](LICENSE) para mais detalhes.

---

## 📞 Contato & Suporte

- **Site:** [medcontrol.app.br](https://medcontrol.app.br)
- **WhatsApp:** [+55 77 98817-5300](https://wa.me/5577988175300)
- **E-mail:** contato@medcontrol.app.br
