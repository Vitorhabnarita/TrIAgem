import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Check,
  ChevronDown,
  ClipboardList,
  LogOut,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import { ROTA_POR_PAPEL, useAuth } from '../context/AuthContext'
import { classes } from '../lib/format'
import type { Papel } from '../types'
import { BrandLogo } from './BrandLogo'
import { ClinicAvatar } from './ui'

const PERFIS: { papel: Papel; rotulo: string; sub: string; icone: typeof ClipboardList }[] = [
  { papel: 'recepcao', rotulo: 'Recepção', sub: 'Fila e WhatsApp', icone: ClipboardList },
  { papel: 'medico', rotulo: 'Médica Veterinária', sub: 'Cockpit clínico (CRMV)', icone: Stethoscope },
  { papel: 'gestor', rotulo: 'Diretor · BI & ROI', sub: 'Painel executivo', icone: BarChart3 },
]

export function TopBar() {
  const { sessao, loginDemo, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [aberto, setAberto] = useState(false)
  const [trocando, setTrocando] = useState<Papel | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const raiz = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function fora(e: MouseEvent) {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAberto(false)
    }
    document.addEventListener('mousedown', fora)
    return () => document.removeEventListener('mousedown', fora)
  }, [])

  useEffect(() => setAberto(false), [location.pathname])

  if (!sessao) return null
  const atual = PERFIS.find((p) => p.papel === sessao.usuario.papel) ?? PERFIS[0]
  const IconeAtual = atual.icone

  async function alternar(papel: Papel) {
    setErro(null)
    if (papel === sessao?.usuario.papel) {
      navigate(ROTA_POR_PAPEL[papel])
      setAberto(false)
      return
    }
    setTrocando(papel)
    try {
      await loginDemo(papel)
      navigate(ROTA_POR_PAPEL[papel])
      setAberto(false)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setTrocando(null)
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        <div className="flex min-w-0 items-center gap-4">
          <BrandLogo variant="full" textSize="text-xl" markSize="h-9 w-9" />
          <span className="hidden h-6 w-px bg-slate-200 sm:block" />
          {/* Co-branding interno: clínica ativa */}
          <div className="hidden min-w-0 items-center gap-2.5 sm:flex">
            <ClinicAvatar nome={sessao.clinica.nome_fantasia} className="h-8 w-8 rounded-xl text-[11px]" />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold text-ink">{sessao.clinica.nome_fantasia}</div>
              <div className="flex items-center gap-1.5 text-[11px] text-ink-soft">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Clínica ativa
              </div>
            </div>
          </div>
        </div>

        <div ref={raiz} className="relative">
          <button
            type="button"
            onClick={() => setAberto((v) => !v)}
            aria-expanded={aberto}
            className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200 bg-white py-1.5 pl-2 pr-3 text-left transition hover:bg-slate-50"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
              <IconeAtual className="h-4 w-4" />
            </span>
            <span className="hidden leading-tight sm:block">
              <span className="block text-sm font-semibold text-ink">{atual.rotulo}</span>
              <span className="block max-w-40 truncate text-[11px] text-ink-soft">{sessao.usuario.nome}</span>
            </span>
            <ChevronDown className={classes('h-4 w-4 text-slate-400 transition', aberto && 'rotate-180')} />
          </button>

          {aberto && (
            <div className="fade-up absolute right-0 mt-2 w-72 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
              <div className="flex items-center gap-1.5 bg-ai-soft px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-ai">
                <Sparkles className="h-3.5 w-3.5" />
                Alternar perfil (demonstração)
              </div>
              <ul className="p-1.5">
                {PERFIS.map(({ papel, rotulo, sub, icone: Icone }) => {
                  const ativo = papel === sessao.usuario.papel
                  return (
                    <li key={papel}>
                      <button
                        type="button"
                        disabled={trocando !== null}
                        onClick={() => alternar(papel)}
                        className={classes(
                          'flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-slate-50',
                          ativo && 'bg-brand-soft',
                        )}
                      >
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-brand ring-1 ring-slate-200">
                          <Icone className="h-4 w-4" />
                        </span>
                        <span className="flex-1 leading-tight">
                          <span className="block text-sm font-semibold text-ink">
                            {trocando === papel ? 'Alternando…' : rotulo}
                          </span>
                          <span className="block text-[11px] text-ink-soft">{sub}</span>
                        </span>
                        {ativo && <Check className="h-4 w-4 text-brand" />}
                      </button>
                    </li>
                  )
                })}
              </ul>
              {erro && <p className="border-t border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700">{erro}</p>}
              <button
                type="button"
                onClick={() => {
                  logout()
                  navigate('/login')
                }}
                className="flex w-full cursor-pointer items-center gap-2 border-t border-slate-100 px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-red-600"
              >
                <LogOut className="h-4 w-4" />
                Encerrar sessão
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
