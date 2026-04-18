# Decisões Técnicas e Bugs Resolvidos

## Regras críticas de CSS — LEIA ANTES DE MEXER NO FRONTEND

### ⚠️ Regra absoluta: nunca use cores hardcoded
Inline `style=""` com cores fixas quebram o light mode.

**ERRADO:**
```html
<div style="background: rgba(15,23,42,0.8)">
<div style="color: #1e293b">
```

**CORRETO — sempre use variáveis CSS:**
```css
var(--card-bg)
var(--input-bg)
var(--card-border)
var(--text)
var(--muted)
```

Essas variáveis estão definidas em `static/css/theme.css` e funcionam em dark e light mode.

---

## Decisões técnicas registradas

| Data | Decisão | Motivo |
|------|---------|--------|
| 2024 | Migração Railway → Render | Custo e estabilidade |
| 2024 | Usar Resend para e-mail | Simples, confiável, boa API |
| 2024 | Mercado Pago para pagamentos | Mercado BR, integração direta |
| 2024 | Remover scanner de código de barras | Tentativas com ZXing, zbar-wasm e html5-qrcode falharam — funcionalidade removida |
| 2024 | Depoimentos adiados | Aguardando clientes reais para usar feedbacks reais |
| 2024 | UptimeRobot | Manter Render free tier ativo (sem cold start) |
| 2024 | Exportação Excel | Suporte a relatórios .xlsx com openpyxl |
| 2024 | Centralização de Gráficos | Uso de charts.js para gerenciar múltiplos gráficos no dashboard |

---

## Bugs resolvidos

| Bug | Causa | Solução |
|-----|-------|---------|
| CSRF token inválido | Token não estava sendo gerado/enviado corretamente | Corrigido no formulário |
| Dark/light mode quebrado | Cores hardcoded em `style=""` inline | Substituído por `var(--...)` |
| AJAX busca não funcionava | Rota `/api/busca` não estava retornando JSON correto | Corrigido em `app.py` |
| Erro Jinja2 syntax | Template com sintaxe incorreta | Corrigido nos templates |
| Foreign key constraint ao deletar rede | Filiais vinculadas impediam deleção | Deletar filiais antes da rede |
| Rows da tabela admin não clicáveis | Faltava evento de click nas `<tr>` | Adicionado onclick no dashboard |
| IntegracaoConsys definition order | Definida após inicialização do DB | Movida para seção de modelos no app.py |

---

## Funcionalidades implementadas
- ✅ Modo de manutenção
- ✅ Termos de Uso e Política de Privacidade (modal com checkbox obrigatório)
- ✅ Rota `/sobre`
- ✅ Rows clicáveis na tabela admin
- ✅ Integração Mercado Pago
- ✅ Landing page com pricing e CTAs WhatsApp
- ✅ Sistema de roles (superadmin, dono_rede, filial)
- ✅ Busca AJAX via `/api/busca`
- ✅ Migração Railway → Render com `render.yaml` e `Procfile`
