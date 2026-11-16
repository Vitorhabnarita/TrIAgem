import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  ClipboardList,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import { BrandLogo } from '../components/BrandLogo'
import { ROTA_POR_PAPEL, useAuth } from '../context/AuthContext'
import type { Papel } from '../types'

const ACESSOS: { papel: Papel; titulo: string; desc: string; icone: typeof ClipboardList; cor: string }[] = [
  {
    papel: 'recepcao',
    titulo: 'Recepção',
    desc: 'Fila do dia, link no WhatsApp e alarme de emergência.',
    icone: ClipboardList,
    cor: 'bg-brand-soft text-brand',
  },
  {
    papel: 'medico',
    titulo: 'Médica Veterinária',
    desc: 'Briefing clínico prévio e cronômetro da consulta (CRMV).',
    icone: Stethoscope,
    cor: 'bg-ai-soft text-ai',
  },
  {
    papel: 'gestor',
    titulo: 'Diretor da Clínica',
    desc: 'BI, horas economizadas e receita adicional potencial.',
    icone: BarChart3,
    cor: 'bg-emerald-50 text-emerald-600',
  },
]

export function LoginPage() {
  const { login, loginDemo, carregando } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [papelAtivo, setPapelAtivo] = useState<Papel | null>(null)

  async function entrar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      const s = await login(email.trim(), senha)
      navigate(ROTA_POR_PAPEL[s.usuario.papel])
    } catch (err) {
      setErro((err as Error).message)
    }
  }

  async function demo(papel: Papel) {
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
    <div className="relative min-h-screen overflow-hidden bg-surface">
      {/* Detalhes suaves do gradiente da marca */}
      <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-brand/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-32 h-[28rem] w-[28rem] rounded-full bg-ai/15 blur-3xl" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl grid-cols-1 items-center gap-10 px-6 py-10 lg:grid-cols-2">
        {/* Login */}
        <section className="fade-up">
          <BrandLogo variant="full" textSize="text-4xl" markSize="h-14 w-14" selo />
          <h1 className="mt-8 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
            A anamnese chega <span className="text-brand-gradient">pronta</span> ao consultório.
          </h1>
          <p className="mt-3 max-w-md text-base text-ink-soft">
            O tutor responde pelo WhatsApp, a IA organiza e o veterinário começa a consulta já sabendo o essencial.
          </p>

          <form onSubmit={entrar} className="card mt-8 max-w-md space-y-4 p-6">
            <h2 className="text-sm font-bold text-ink">Acesso da equipe</h2>
            {erro && (
              <div className="flex items-start gap-2 rounded-xl bg-red-50 p-3 text-xs text-red-700">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {erro}
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">E-mail</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="email" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="voce@suaclinica.com.br"
                  className="input pl-10"
                />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="senha">Senha</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="senha" type="password" required value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  placeholder="••••••••"
                  className="input pl-10"
                />
              </div>
            </div>
            <button type="submit" disabled={carregando} className="btn-primary w-full">
              {carregando && !papelAtivo ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        </section>

        {/* Demo 1-click */}
        <section className="fade-up">
          <div className="card p-6 sm:p-8">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ai-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-ai">
              <Sparkles className="h-3.5 w-3.5" />
              Acesso rápido de demonstração
            </span>
            <h2 className="mt-3 text-xl font-bold text-ink">Conheça o TrIAgem em 1 clique</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Explore a clínica demonstrativa sem digitar senha. Escolha um perfil:
            </p>

            <div className="mt-6 space-y-3">
              {ACESSOS.map(({ papel, titulo, desc, icone: Icone, cor }) => (
                <button
                  key={papel}
                  type="button"
                  disabled={carregando}
                  onClick={() => demo(papel)}
                  className="group flex w-full cursor-pointer items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-brand hover:shadow-md disabled:opacity-60"
                >
                  <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${cor}`}>
                    <Icone className="h-6 w-6" />
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-bold text-ink">
                      {papelAtivo === papel ? 'Entrando…' : titulo}
                    </span>
                    <span className="block text-xs text-ink-soft">{desc}</span>
                  </span>
                  <ArrowRight className="h-5 w-5 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand" />
                </button>
              ))}
            </div>

            <p className="mt-6 flex items-start gap-2 text-xs text-ink-soft">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              O TrIAgem organiza informações e sinaliza emergências. Nunca emite diagnóstico ou prescrição.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
