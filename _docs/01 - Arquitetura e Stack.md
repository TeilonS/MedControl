# Arquitetura e Stack — MedControl

## Stack completo
| Camada | Tecnologia |
|--------|-----------|
| Backend | Python + Flask |
| ORM | SQLAlchemy |
| Banco | PostgreSQL via Supabase |
| Deploy | Render (migrado do Railway) |
| E-mail | Resend |
| Pagamentos | Mercado Pago |
| Frontend | Jinja2 + HTML/CSS vanilla |
| Uptime | UptimeRobot (recomendado para manter Render ativo) |
| Domínio | www.medcontrol.app.br |

## Arquivos principais
```
medcontrol/
├── app.py                          ← lógica principal, rotas, modelos
├── templates/
│   ├── index.html                  ← landing page pública
│   ├── admin/
│   │   └── dashboard.html          ← painel administrativo
│   └── ...
├── static/
│   └── css/
│       └── theme.css               ← variáveis CSS do sistema de temas
├── Procfile                        ← comando de start para Render
└── render.yaml                     ← configuração do Render
```

## Variáveis de ambiente (Render)
```
DATABASE_URL      ← string de conexão Supabase/PostgreSQL
SECRET_KEY        ← chave Flask para sessões
RESEND_API_KEY    ← API key do Resend
RESEND_FROM       ← e-mail remetente
CRON_SECRET       ← segredo para jobs agendados
ADMIN_PASS        ← senha do superadmin
```

## Roles de usuário
| Role | Permissões |
|------|-----------|
| `superadmin` | Controle total do sistema |
| `dono_rede` | Gerencia múltiplas filiais |
| `filial` | Acesso à sua filial apenas |

## Rotas principais
- `/` — landing page
- `/sobre` — página sobre
- `/admin/dashboard` — painel principal
- `/api/busca` — busca AJAX de medicamentos
- `/manutencao` — modo de manutenção
