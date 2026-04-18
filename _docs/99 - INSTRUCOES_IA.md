# INSTRUCOES_IA — MedControl

## Quem sou eu
Teilon Santos — desenvolvedor solo do MedControl.
Moro em Vitória da Conquista, BA.
Curso ADS na Uniasselvi (2024–2026), foco em Segurança da Informação.
Stack principal: Python, Flask, PostgreSQL, Linux (Bazzite).
Em transição de farmacêutico para TI — o MedControl é meu projeto principal de portfólio e produto real.

## O que é este projeto
SaaS de gestão de medicamentos para farmácias.
Em produção em www.medcontrol.app.br.
Pagamentos via Mercado Pago ativos.

## Como trabalhar comigo

### Antes de qualquer tarefa
1. Leia `01 - Arquitetura e Stack.md` para entender o projeto
2. Leia `02 - Decisoes e Bugs.md` para não repetir erros já resolvidos
3. Leia `03 - Roadmap.md` para entender prioridades

### Regras inegociáveis de código
- **NUNCA** use cores hardcoded em `style=""` inline — sempre `var(--card-bg)`, `var(--text)`, etc.
- **SEMPRE** confirme a causa no arquivo real antes de diagnosticar
- **SEMPRE** termine entregas de código com:
  ```bash
  git add .
  git commit -m "descrição"
  git push
  ```
- Variáveis de ambiente ficam no Render — nunca hardcode credenciais

### Padrão de resposta
- Responda em português
- Seja direto — mostre o código, não enrole
- Quando resolver um bug, diga qual arquivo foi alterado e o que mudou
- Após resolver bug ou tomar decisão técnica, me lembre de atualizar `02 - Decisoes e Bugs.md`
- Após completar item do roadmap, me lembre de atualizar `03 - Roadmap.md`

### O que NÃO fazer
- Não sugerir trocar o stack (Flask funciona, não muda)
- Não sugerir Railway (migrado para Render — decisão final)
- Não sugerir reativar o scanner de código de barras (tentamos 3 libs, não funciona)
- Não usar cores hardcoded no CSS/HTML

## Contexto de deploy
- Plataforma: Render (free tier)
- Manter UptimeRobot apontando para o app (evita cold start)
- Banco: Supabase PostgreSQL (variável `DATABASE_URL`)
- Após push, Render faz deploy automático via GitHub
