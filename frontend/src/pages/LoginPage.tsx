import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Lock,
  Mail,
  ShieldAlert,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import { ROTA_POR_PAPEL, useAuth } from '../context/AuthContext'
import type { Papel } from '../types'

const BOTOES_DEMO: {
  papel: Papel
  titulo: string
  subtitulo: string
  destaque: string
  icone: typeof ClipboardList
}[] = [
  {
    papel: 'recepcao',
    titulo: 'Entrar como Recepção',
    subtitulo: 'Painel Operacional · Fila em Tempo Real · Disparo WhatsApp e Alarme de Resgate GPS',
    destaque: 'Ir para /recepcao',
    icone: ClipboardList,
  },
  {
    papel: 'medico',
    titulo: 'Entrar como Médica Veterinária (CRMV)',
    subtitulo: 'Cockpit Clínico · Briefing Semiológico IA · Protocolo ABC e Cronômetro UTC',
    destaque: 'Ir para /medico',
    icone: Stethoscope,
  },
  {
    papel: 'gestor',
    titulo: 'Entrar como Gestor da Clínica (BI & ROI)',
    subtitulo: 'Dashboard Executivo B2B · Horas Economizadas · Receita Potencial e Risco Manchester',
    destaque: 'Ir para /gestao',
    icone: BarChart3,
  },
]

export function LoginPage() {
  const { login, loginDemo, carregando } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [papelAtivo, setPapelAtivo] = useState<Papel | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      const s = await login(email.trim(), senha)
      navigate(ROTA_POR_PAPEL[s.usuario.papel])
    } catch (err) {
      setErro((err as Error).message)
    }
  }

  async function handleDemo(papel: Papel) {
    setErro(null)
    setPapelAtivo(papel)
    try {
      const s = await loginDemo(papel)
      navigate(ROTA_POR_PAPEL[s.usuario.papel])
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setPapelAtivo(null)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-teal-950 text-white flex flex-col justify-between">
      {/* Cabeçalho Institucional */}
      <div className="mx-auto w-full max-w-6xl px-6 pt-8 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-400 to-emerald-600 shadow-lg shadow-teal-900/50">
            <Activity className="h-6 w-6 text-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-extrabold tracking-tight">TrIAgem</span>
              <span className="rounded-full bg-emerald-500/20 border border-emerald-400/30 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                VetTech Enterprise v6.0
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Triagem Pré-Consulta Inteligente · Protocolo Manchester &amp; RN-001 v2.0
            </p>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3.5 py-1.5 text-xs text-slate-300">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>Conformidade Ética CFMV &amp; LGPD</span>
        </div>
      </div>

      {/* Conteúdo Principal: 2 Colunas */}
      <main className="mx-auto w-full max-w-6xl px-6 py-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Coluna Principal: Modo Demonstração Comercial 1-Click */}
        <section className="lg:col-span-7 rounded-3xl border border-teal-500/30 bg-slate-900/90 p-6 sm:p-8 shadow-2xl shadow-teal-950/50">
          <div className="inline-flex items-center gap-2 rounded-full bg-teal-500/15 border border-teal-400/30 px-3 py-1 text-xs font-semibold text-teal-300 mb-4">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Modo Demonstração Comercial (1-Click)</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Hospital Veterinário Vida Pet 24h
          </h1>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Acesse instantaneamente qualquer perfil operacional da clínica demonstrativa sem digitar
            credenciais. Dados reais de fila, emergências RN-001 v2.0 e histórico de ROI pré-carregados.
          </p>

          <div className="mt-6 space-y-3.5">
            {BOTOES_DEMO.map(({ papel, titulo, subtitulo, destaque, icone: Icone }) => {
              const ativo = papelAtivo === papel
              return (
                <button
                  key={papel}
                  type="button"
                  disabled={carregando}
                  onClick={() => handleDemo(papel)}
                  className="group w-full text-left rounded-2xl border border-slate-700/80 bg-slate-800/70 hover:bg-gradient-to-r hover:from-teal-900/60 hover:to-emerald-900/40 hover:border-teal-400/60 p-4 sm:p-5 transition-all shadow-md cursor-pointer disabled:opacity-60"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3.5">
                      <div className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal-500/15 border border-teal-500/30 text-teal-300 group-hover:bg-teal-500 group-hover:text-slate-950 transition-colors">
                        <Icone className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-base font-bold text-white group-hover:text-teal-200 transition-colors">
                          {ativo ? 'Autenticando sessão demo...' : titulo}
                        </div>
                        <p className="mt-1 text-xs text-slate-300 leading-relaxed">{subtitulo}</p>
                      </div>
                    </div>
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-teal-500/20 border border-teal-500/30 px-2.5 py-1 text-xs font-semibold text-teal-200 group-hover:bg-teal-500 group-hover:text-slate-950 transition-colors">
                      {destaque}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </button>
              )
            })}
          </div>

          <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 flex items-start gap-3 text-xs text-slate-400">
            <ShieldAlert className="h-4 w-4 text-teal-400 shrink-0 mt-0.5" />
            <span>
              <strong className="text-slate-200">Governança Clínica:</strong> o TrIAgem organiza a
              anamnese prévia e detecta sinais críticos (RN-001 v2.0), mas jamais emite diagnóstico
              ou prescrição.
            </span>
          </div>
        </section>

        {/* Coluna Lateral: Login JWT Tradicional */}
        <section className="lg:col-span-5 rounded-3xl border border-slate-800 bg-slate-900/75 p-6 sm:p-8 shadow-xl">
          <h2 className="text-lg font-bold text-white">Acesso Corporativo (JWT)</h2>
          <p className="mt-1 text-xs text-slate-400">
            Entre com seu e-mail institucional e senha cadastrados na sua clínica.
          </p>

          {erro && (
            <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-red-500/40 bg-red-950/70 p-3.5 text-xs text-red-200">
              <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <span>{erro}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                E-mail profissional
              </label>
              <div className="relative">
                <Mail className="h-4 w-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="voce@suaclinica.com.br"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/80 pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-teal-400 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Senha
              </label>
              <div className="relative">
                <Lock className="h-4 w-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/80 pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-teal-400 focus:outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={carregando}
              className="w-full rounded-xl bg-teal-600 hover:bg-teal-500 disabled:opacity-60 py-2.5 px-4 text-sm font-bold text-white shadow-lg shadow-teal-950/50 transition cursor-pointer"
            >
              {carregando && !papelAtivo ? 'Entrando...' : 'Entrar com E-mail e Senha'}
            </button>
          </form>
        </section>
      </main>

      <footer className="mx-auto w-full max-w-6xl px-6 py-4 text-center text-xs text-slate-500">
        TrIAgem VetTech · Arquitetura Multi-Tenant (RN-004) · Gemini 2.5 Flash com Guardrails Éticos
      </footer>
    </div>
  )
}
