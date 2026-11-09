# TrIAgem — Triagem Pré-Consulta Veterinária Assistida por IA (Versão 6.0)

Plataforma SaaS B2B Multi-Tenant para clínicas e hospitais veterinários que transforma o relato leigo do tutor em um **Briefing Clínico Prévio Estruturado** com tradução semiológica descritiva, **Disjuntor de Emergência RN-001 v2.0 (Logística de Resgate GPS, Primeiros Socorros Negativos e Protocolo ABC Anti-Ancoragem)** e **Cronômetro Operacional UTC (RN-003/RN-004)** para comprovação de ROI.

> **Governança Ética CFMV:** O TrIAgem **jamais emite diagnóstico, prognóstico, prescrição ou antídotos**. Toda saída da IA passa por guardrails determinísticos no servidor.

---

## Arquitetura Completa (Backend + Frontend SPA)

- **Backend (`app/`)**: FastAPI + SQLAlchemy 2.0 Async (`asyncpg`) + Alembic (Migrações `001` a `004`) + Google Gemini 2.5 Flash (`google-genai`) + Guardrails Éticos e RBAC Multi-Tenant.
- **Frontend (`frontend/`)**: React 18 + TypeScript + Vite 6 + TailwindCSS 4 + Lucide Icons, estruturado em 5 telas:
  1. **`/login` (`LoginPage.tsx`)**: Login Corporativo JWT + **Modo Demonstração Comercial (1-Click)** (`POST /auth/demo/{papel}`).
  2. **`/t/:token` (`TutorWizardPage.tsx`)**: Wizard Mobile do Tutor em 4 passos + **Disjuntor de Emergência em Tempo Real (RN-001 v2.0)** com Card de Primeiros Socorros Negativos (*"O Que NÃO Fazer Agora em Casa"*), ciência jurídica de risco de morte, aviso *"Estou a Caminho"*, solicitação de *Veículo de Resgate com GPS* e redirecionamento para Hospital Veterinário 24h.
  3. **`/recepcao` (`RecepcaoPage.tsx`)**: Painel Operacional da Recepção com **Alarme Visual Pulsante de Emergência/Resgate GPS**, fila do dia, disparo WhatsApp (`wa.me`) e simulador mobile do tutor.
  4. **`/medico` (`MedicoPage.tsx`)**: Cockpit Clínico do Médico Veterinário com fila priorizada pelo Protocolo de Manchester, **Cronômetro Operacional UTC**, Protocolo ABC Anti-Ancoragem, Segurança Farmacológica (48h), Tradução Semiológica Lado a Lado e Checklist clicável de Exame Físico Presencial.
  5. **`/gestao` (`GestaoPage.tsx`)**: Dashboard Executivo B2B do Gestor (`GET /dashboard/metricas`) com Horas Economizadas, Capacidade Extra de Consultas, Receita Adicional Potencial (R$) e Distribuição de Risco Manchester.

---

## Como Executar o Projeto

### 1. Backend (FastAPI + PostgreSQL)

```bash
# 1. Ative o ambiente virtual e instale as dependências
.\venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure o arquivo .env (copie de .env.example e habilite DEMO_LOGIN_HABILITADO=true para o 1-Click Demo)
copy .env.example .env

# 3. Aplique as migrações (até a 004_protocolo_emergencia_resgate)
alembic upgrade head

# 4. Popule o catálogo de sintomas e o Hospital Veterinário Vida Pet 24h (cenário demo)
python scripts/seed.py --demo --reset-demo

# 5. Inicie o servidor FastAPI na porta 8000
uvicorn main:app --reload --port 8000
```

### 2. Frontend SPA (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Acesse **`http://localhost:5173`** e utilize o card **Modo Demonstração Comercial (1-Click)** ou a barra superior global para alternar instantaneamente entre **Recepção**, **Médica Veterinária (CRMV)** e **Gestor (BI & ROI)**.

---

## Suíte de Testes Automatizados e Build

```bash
# Backend (110 testes automatizados cobrindo RN-001 v2.0, RN-002, RN-003, RN-004 e Migração 004)
pytest -q

# Frontend (TypeScript + Bundle de Produção Vite)
cd frontend && npm run build
```
