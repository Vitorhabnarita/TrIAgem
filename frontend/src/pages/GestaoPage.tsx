import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ambulance,
  ChevronDown,
  Clock,
  RefreshCw,
  ShieldCheck,
  Siren,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { api } from '../lib/api'
import { classes, formatarMoeda, formatarNumero } from '../lib/format'
import { MANCHESTER } from '../lib/manchester'
import type { Metricas } from '../types'

const PERIODOS = [7, 14, 30]

function dataCurta(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

function Hero({
  icone,
  titulo,
  valor,
  legenda,
  destaque = false,
  tom,
}: {
  icone: React.ReactNode
  titulo: string
  valor: string
  legenda: string
  destaque?: boolean
  tom: string
}) {
  return (
    <div
      className={classes(
        'rounded-2xl p-5',
        destaque ? 'bg-brand-gradient text-white shadow-lg' : 'card',
      )}
    >
      <div className="flex items-center justify-between">
        <span className={classes('text-sm font-medium', destaque ? 'text-white/85' : 'text-ink-soft')}>{titulo}</span>
        <span className={classes('flex h-9 w-9 items-center justify-center rounded-xl', destaque ? 'bg-white/20 text-white' : tom)}>{icone}</span>
      </div>
      <div className={classes('mt-3 text-3xl font-extrabold tracking-tight', destaque ? 'text-white' : 'text-ink')}>{valor}</div>
      <p className={classes('mt-1.5 text-xs leading-relaxed', destaque ? 'text-white/80' : 'text-ink-soft')}>{legenda}</p>
    </div>
  )
}

export function GestaoPage() {
  const [m, setM] = useState<Metricas | null>(null)
  const [dias, setDias] = useState(30)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const ate = new Date(Date.now() + 24 * 3600 * 1000).toISOString()
      const de = new Date(Date.now() - dias * 24 * 3600 * 1000).toISOString()
      setM(await api<Metricas>('/dashboard/metricas', { query: { de, ate } }))
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setCarregando(false)
    }
  }, [dias])

  useEffect(() => {
    carregar()
  }, [carregar])

  const ultimos = useMemo(() => (m ? m.serie_diaria.slice(-14) : []), [m])
  const maxDia = Math.max(1, ...ultimos.map((d) => d.minutos_economizados))
  const totalDiasUteis = ultimos.reduce((s, d) => s + d.consultas, 0)

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-ink">Retorno do TrIAgem</h1>
          <p className="mt-1 text-sm text-ink-soft">Quanto tempo e dinheiro a triagem devolveu à clínica.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-xl bg-slate-100 p-1">
            {PERIODOS.map((d) => (
              <button key={d} type="button" onClick={() => setDias(d)} className={classes('cursor-pointer rounded-lg px-3.5 py-1.5 text-xs font-semibold transition', dias === d ? 'bg-white text-ink shadow-sm' : 'text-ink-soft hover:text-ink')}>
                {d} dias
              </button>
            ))}
          </div>
          <button type="button" onClick={carregar} title="Atualizar" aria-label="Atualizar" className="btn-ghost h-10 w-10 p-0">
            <RefreshCw className={classes('h-4 w-4', carregando && 'animate-spin')} />
          </button>
        </div>
      </div>

      {erro && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 p-3.5 text-sm text-red-700 ring-1 ring-red-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {erro}
        </div>
      )}

      {!m ? (
        <div className="card p-12 text-center text-sm text-ink-soft">{carregando ? 'Calculando indicadores…' : 'Sem dados.'}</div>
      ) : (
        <>
          {/* 1 · Hero cards */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Hero
              destaque tom=""
              icone={<Wallet className="h-5 w-5" />}
              titulo="Receita adicional potencial"
              valor={formatarMoeda(m.receita_adicional_potencial)}
              legenda={`${formatarNumero(m.capacidade_extra_atendimentos, 1)} consultas extras × ticket médio de ${formatarMoeda(m.ticket_medio_consulta)}.`}
            />
            <Hero
              tom="bg-brand-soft text-brand"
              icone={<Clock className="h-5 w-5" />}
              titulo="Horas economizadas"
              valor={`${formatarNumero(m.horas_economizadas, 1)} h`}
              legenda={`${formatarNumero(m.minutos_economizados, 0)} min devolvidos à equipe frente ao benchmark de ${m.benchmark_minutos} min.`}
            />
            <Hero
              tom="bg-ai-soft text-ai"
              icone={<TrendingUp className="h-5 w-5" />}
              titulo="Capacidade extra"
              valor={`+${formatarNumero(m.capacidade_extra_atendimentos, 1)}`}
              legenda="Novas consultas que cabem no tempo economizado."
            />
            <Hero
              tom="bg-emerald-50 text-emerald-600"
              icone={<ShieldCheck className="h-5 w-5" />}
              titulo="Adesão e segurança"
              valor={`${formatarNumero(m.taxa_adesao_pct, 0)}%`}
              legenda={`${m.triagens_realizadas} de ${m.total_agendadas} tutores responderam · ${m.urgencias_detectadas} emergências sinalizadas, ${m.resgates_solicitados} resgates.`}
            />
          </section>

          {/* 2 · Antes vs. Com TrIAgem */}
          <section className="card p-6">
            <h2 className="text-base font-bold text-ink">Tempo por consulta: antes vs. com TrIAgem</h2>
            <div className="mt-5 space-y-4">
              <div>
                <div className="mb-1.5 flex justify-between text-sm">
                  <span className="font-medium text-ink-soft">Consulta tradicional (anamnese no consultório)</span>
                  <span className="font-bold text-ink">{m.benchmark_minutos} min</span>
                </div>
                <div className="h-4 rounded-full bg-slate-100">
                  <div className="h-full w-full rounded-full bg-slate-300" />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex justify-between text-sm">
                  <span className="font-semibold text-brand">Com TrIAgem (média real medida)</span>
                  <span className="font-bold text-brand">
                    {m.duracao_media_minutos != null ? `${formatarNumero(m.duracao_media_minutos, 1)} min` : '—'}
                  </span>
                </div>
                <div className="h-4 rounded-full bg-slate-100">
                  <div
                    className="bg-brand-gradient h-full rounded-full transition-all"
                    style={{ width: `${m.duracao_media_minutos != null ? Math.min(100, (m.duracao_media_minutos / m.benchmark_minutos) * 100) : 0}%` }}
                  />
                </div>
              </div>
            </div>
            {m.duracao_media_minutos != null && (
              <p className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
                <TrendingUp className="h-4 w-4" />
                {formatarNumero(Math.max(0, m.benchmark_minutos - m.duracao_media_minutos), 1)} minutos poupados em cada atendimento
              </p>
            )}
          </section>

          {/* 3 · Gráficos */}
          <section className="grid gap-6 lg:grid-cols-2">
            {/* Manchester */}
            <div className="card p-6">
              <h2 className="text-base font-bold text-ink">Perfil clínico dos atendimentos</h2>
              <p className="mt-0.5 text-xs text-ink-soft">Classificação de risco (Protocolo de Manchester) das {m.triagens_realizadas} triagens.</p>
              <ul className="mt-5 space-y-4">
                {m.distribuicao_risco.map((r) => {
                  const e = MANCHESTER[r.cor]
                  return (
                    <li key={r.cor}>
                      <div className="mb-1.5 flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2 font-medium text-ink">
                          <span className={classes('h-2.5 w-2.5 rounded-full', e.dot)} />
                          {e.rotulo}
                        </span>
                        <span className="text-ink-soft">
                          <strong className="text-ink">{r.quantidade}</strong> · {formatarNumero(r.percentual, 0)}%
                        </span>
                      </div>
                      <div className="h-2.5 rounded-full bg-slate-100">
                        <div className={classes('h-full rounded-full transition-all', e.barra)} style={{ width: `${r.quantidade > 0 ? Math.max(3, r.percentual) : 0}%` }} />
                      </div>
                    </li>
                  )
                })}
              </ul>
              <p className="mt-5 flex items-center gap-2 text-xs text-ink-soft">
                <Siren className="h-4 w-4 text-red-500" />
                {m.emergencias_acionadas} emergências acionadas pelo tutor
                <Ambulance className="ml-2 h-4 w-4 text-amber-500" />
                {m.resgates_solicitados} resgates
              </p>
            </div>

            {/* Evolução diária */}
            <div className="card p-6">
              <h2 className="text-base font-bold text-ink">Minutos economizados por dia</h2>
              <p className="mt-0.5 text-xs text-ink-soft">Últimos 14 dias · {totalDiasUteis} consultas finalizadas.</p>

              <div className="mt-6 flex h-44 items-end gap-1.5" role="img" aria-label="Gráfico de minutos economizados por dia">
                {ultimos.map((d) => {
                  const h = d.minutos_economizados > 0 ? Math.max(6, (d.minutos_economizados / maxDia) * 100) : 0
                  return (
                    <div key={d.dia} className="group relative flex h-full flex-1 flex-col justify-end">
                      <div className="pointer-events-none absolute -top-1 left-1/2 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-ink px-2.5 py-1.5 text-[11px] text-white shadow-lg group-hover:block">
                        <strong>{dataCurta(d.dia)}</strong> · {formatarNumero(d.minutos_economizados, 0)} min · {d.consultas} {d.consultas === 1 ? 'consulta' : 'consultas'}
                      </div>
                      <div className={classes('w-full rounded-t-md transition-all', h > 0 ? 'bg-brand-gradient group-hover:opacity-80' : 'bg-slate-100')} style={{ height: h > 0 ? `${h}%` : '3px' }} />
                    </div>
                  )
                })}
              </div>
              <div className="mt-2 flex gap-1.5 text-[10px] text-slate-400">
                {ultimos.map((d, i) => (
                  <span key={d.dia} className="flex-1 text-center">{i % 2 === 0 ? dataCurta(d.dia) : ''}</span>
                ))}
              </div>

              <details className="group mt-5 border-t border-slate-100 pt-4">
                <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-ink">
                  Ver tabela por dia
                  <ChevronDown className="h-4 w-4 text-slate-400 transition group-open:rotate-180" />
                </summary>
                <table className="mt-3 w-full text-left text-sm">
                  <thead className="text-xs text-ink-soft">
                    <tr><th className="py-1.5 font-medium">Dia</th><th className="py-1.5 font-medium">Consultas</th><th className="py-1.5 text-right font-medium">Min. economizados</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {[...ultimos].reverse().map((d) => (
                      <tr key={d.dia}>
                        <td className="py-1.5 text-ink">{dataCurta(d.dia)}</td>
                        <td className="py-1.5 text-ink-soft">{d.consultas}</td>
                        <td className="py-1.5 text-right font-semibold text-ink">{formatarNumero(d.minutos_economizados, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </div>
          </section>

          <p className="text-center text-xs text-ink-soft">{m.observacao}</p>
        </>
      )}
    </main>
  )
}
