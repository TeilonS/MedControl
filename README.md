# 💊 MedControl — Sistema de Controle de Validade de Medicamentos

Sistema profissional de gerenciamento de validade de medicamentos com suporte a leitura de código de barras, dashboard analítico, geração de PDF e arquitetura aberta para integrações com sistemas externos (Consys, SNGPC, Tasy, etc.).

## 🚀 Instalação Rápida

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Iniciar o servidor
python app.py

# 3. Acessar no navegador
http://localhost:5000

# Login padrão: admin / admin123
```

## 📁 Estrutura do Projeto

```
validade_med/
├── app.py                  # Aplicação principal, rotas e lógica
├── requirements.txt        # Dependências Python
├── README.md
├── static/
│   ├── css/
│   │   └── style.css       # Estilos customizados extras (opcional)
│   └── js/
│       └── charts.js       # Lógica Chart.js (opcional separar)
└── templates/
    ├── login.html          # Tela de autenticação
    ├── index.html          # Dashboard principal com gráficos
    └── cadastro.html       # Formulário de cadastro/edição com scanner
```

## 🔌 API REST para Integrações

### Listar medicamentos
```
GET  /api/v1/medicamentos
GET  /api/v1/medicamentos?status=vencido
```

### Buscar por código de barras
```
GET  /api/v1/medicamentos/barcode/{codigo}
```

### Criar via API (para sistemas como Consys)
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

## 📊 Funcionalidades

- ✅ **CRUD completo** de medicamentos
- ✅ **Dashboard** com cards de status e alertas visuais
- ✅ **Código de barras** — leitura via câmera (QuaggaJS) ou leitor USB
- ✅ **Classificação automática**: Vencido / 30 dias / 60 dias / OK
- ✅ **Gráfico de perdas** (Chart.js) — valor vencido vs. em estoque
- ✅ **Relatório PDF** gerado com ReportLab
- ✅ **Busca** por nome, lote ou código de barras
- ✅ **API REST** documentada para integração externa
- ✅ **Autenticação** por sessão
- ✅ Campos preparados para **Consys, SNGPC, Tasy, MV**

## 🔮 Integrações Futuras

| Sistema    | Status    | Endpoint sugerido           |
|------------|-----------|-----------------------------|
| Consys ERP | Em breve  | `POST /api/v1/sync/consys`  |
| SNGPC      | Em breve  | `POST /api/v1/sync/sngpc`   |
| Tasy / MV  | Em breve  | `POST /api/v1/sync/tasy`    |
| ANVISA     | Em breve  | `GET  /api/v1/anvisa/lookup`|

## 🔐 Segurança (Produção)

- Troque `SECRET_KEY` por uma string aleatória via variável de ambiente
- Implemente hashing de senha com `bcrypt`
- Use HTTPS (reverse proxy Nginx + Gunicorn)
- Configure autenticação de API com JWT ou API Keys para endpoints `/api/v1/`
