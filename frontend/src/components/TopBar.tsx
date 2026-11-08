import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  Building2,
  ClipboardList,
  LogOut,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import { ROTA_POR_PAPEL, useAuth } from '../context/AuthContext'
import type { Papel } from '../types'

const PERFIS_DEMO: { papel: Papel; rotulo: string; subtitulo: string; icone: typeof ClipboardList }[] = [
  {
    papel: 'recepcao',
    rotulo: 'Recepção',
    subtitulo: 'Fila & WhatsApp',
    icone: ClipboardList,
  },
  {
    papel: 'medico',
    rotulo: 'Médica Veterinária (CRMV)',
    subtitulo: 'Cockpit Clínico',
    icone: Stethoscope,
  },
  {
    papel: 'gestor',
    rotulo: 'Gestor (BI & ROI)',
    subtitulo: 'Dashboard B2B',
    icone: BarChart3,
  },
]

export function TopBar() {
  const { sessao, loginDemo, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [trocando, setTrocando] = useState<Papel | null>(null)
  const [erroDemo, setErroDemo] = useState<string | null>(null)

  if (!sessao) return null

  async function alternarPerfil(papel: Papel) {
    setErroDemo(null)
    if (sessao?.usuario.papel === papel) {
      navigate(ROTA_POR_PAPEL[papel])
      return
    }
    setTrocando(papel)
    try {
      await loginDemo(papel)
      navigate(ROTA_POR_PAPEL[papel])
    } catch (err) {
      setErroDemo((err as Error).message)
    } finally {
      setTrocando(null)
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900 text-white shadow-lg">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        {/* Marca e Clínica */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 shadow-inner">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold tracking-tight text-white">TrIAgem</span>
              <span className="rounded-full bg-teal-500/20 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-teal-300 border border-teal-500/30">
                VetTech v6.0
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-300">
              <Building2 className="h-3.5 w-3.5 text-teal-400" />
              <span className="font-medium">{sessao.clinica.nome_fantasia}</span>
            </div>
          </div>
        </div>

        {/* Alternador Rápido 1-Click para Apresentação à Banca */}
        <div className="flex flex-wrap items-center gap-1.5 rounded-xl bg-slate-800/90 p-1.5 border border-slate-700/80">
          <span className="hidden items-center gap-1 px-2 text-[11px] font-medium uppercase tracking-wider text-teal-300 lg:flex">
            <Sparkles className="h-3.5 w-3.5" />
            1-Click Demo:
          </span>
          {PERFIS_DEMO.map(({ papel, rotulo, icone: Icone }) => {
            const ativo =
              sessao.usuario.papel === papel && location.pathname.startsWith(ROTA_POR_PAPEL[papel])
            const carregandoEste = trocando === papel
            return (
              <button
                key={papel}
                type="button"
                disabled={trocando !== null}
                onClick={() => alternarPerfil(papel)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                  ativo
                    ? 'bg-teal-600 text-white shadow-sm ring-1 ring-teal-400/50'
                    : 'text-slate-300 hover:bg-slate-700/70 hover:text-white'
                }`}
              >
                <Icone className="h-3.5 w-3.5" />
                <span>{carregandoEste ? 'Alternando...' : rotulo}</span>
              </button>
            )
          })}
        </div>

        {/* Usuário Logado e Logout */}
        <div className="flex items-center gap-3">
          <div className="hidden text-right sm:block">
            <div className="flex items-center justify-end gap-1 text-xs font-semibold text-white">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>{sessao.usuario.nome}</span>
            </div>
            <div className="text-[11px] text-slate-400">{sessao.usuario.email}</div>
          </div>
          <button
            type="button"
            onClick={() => {
              logout()
              navigate('/login')
            }}
            title="Encerrar sessão"
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-red-500/50 hover:bg-red-500/10 hover:text-red-300 cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sair</span>
          </button>
        </div>
      </div>

      {erroDemo && (
        <div className="border-t border-red-500/30 bg-red-950/90 px-4 py-1.5 text-center text-xs text-red-200">
          {erroDemo}
        </div>
      )}
    </header>
  )
}
