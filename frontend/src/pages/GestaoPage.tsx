import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Ambulance,
  BarChart3,
  Clock,
  DollarSign,
  Percent,
  RefreshCw,
  Siren,
  TrendingUp,
  Users,
} from 'lucide-react'
import { api } from '../lib/api'
import { classes, formatarMoeda, formatarNumero } from '../lib/format'
import { MANCHESTER } from '../lib/manchester'
import type { Metricas } from '../types'

export function GestaoPage() {
  const [metricas, setMetricas] = useState<Metricas | null>(null)
  const [diasPeriodo, setDiasPeriodo] = useState<number>(30)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregarMetricas = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const ate = new Date(Date.now() + 24 * 3600 * 1000).toISOString()
      const de = new Date(Date.now() - diasPeriodo * 24 * 3600 * 1000).toISOString()
      const dados = await api<Metricas>('/dashboard/metricas', {
        query: { de, ate },
      })
      setMetricas(dados)
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setCarregando(false)
    }
  }, [diasPeriodo])

  useEffect(() => {
    carregarMetricas()
  }, [carregarMetricas])

  const serieComMovimento =
    metricas?.serie_diaria.filter((d) => d.consultas > 0 || d.minutos_economizados > 0) ?? []
  const maxMinDia = Math.max(
    1,
    ...serieComMovimento.map((d) => d.minutos_economizados),
  )

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 space-y-6">
      {/* Cabeçalho Executivo B2B */}
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-2.5 py-0.5 text-[11px] font-extrabold uppercase tracking-wider text-teal-800">
            <BarChart3 className="h-3.5 w-3.5" />
            Business Intelligence &amp; ROI Auditável (RN-003)
          </span>
          <h1 className="mt-1 text-xl font-extrabold text-slate-900">
            Dashboard Executivo B2B do Gestor
          </h1>
          <p className="text-xs text-slate-600">
            Economia real de tempo aferida por timestamps UTC, capacidade extra de consultas,
            receita adicional potencial e distribuição de risco Manchester.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDiasPeriodo(d)}
              className={classes(
                'rounded-xl px-3 py-2 text-xs font-bold border transition cursor-pointer',
                diasPeriodo === d
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50',
              )}
            >
              Últimos {d} dias
            </button>
          ))}
          <button
            type="button"
            onClick={carregarMetricas}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Atualizar</span>
          </button>
        </div>
      </section>

      {erro && (
        <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-xs font-semibold text-red-800 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
          <span>{erro}</span>
        </div>
      )}

      {carregando || !metricas ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
          Calculando indicadores executivos de ROI...
        </div>
      ) : (
        <>
          {/* 5 CARDS PRINCIPAIS DE KPI E ROI */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-500">
                <span>Horas Economizadas</span>
                <Clock className="h-4 w-4 text-teal-600" />
              </div>
              <div className="text-2xl font-extrabold text-slate-900">
                {formatarNumero(metricas.horas_economizadas, 1)} h
              </div>
              <p className="text-[11px] text-slate-500">
                {formatarNumero(metricas.minutos_economizados, 0)} min totais vs. benchmark de{' '}
                {metricas.benchmark_minutos} min
              </p>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-500">
                <span>Capacidade Extra</span>
                <TrendingUp className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-extrabold text-emerald-700">
                +{formatarNumero(metricas.capacidade_extra_atendimentos, 1)} consultas
              </div>
              <p className="text-[11px] text-slate-500">
                Duração média real:{' '}
                {metricas.duracao_media_minutos != null
                  ? `${formatarNumero(metricas.duracao_media_minutos, 1)} min`
                  : '—'}
              </p>
            </div>

            <div className="rounded-3xl border-2 border-emerald-500 bg-gradient-to-br from-emerald-950 to-teal-950 text-white p-5 shadow-md space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-emerald-300">
                <span>Receita Adicional Potencial</span>
                <DollarSign className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-extrabold text-white">
                {formatarMoeda(metricas.receita_adicional_potencial)}
              </div>
              <p className="text-[11px] text-emerald-200">
                Ticket médio base: {formatarMoeda(metricas.ticket_medio_consulta)} / consulta
              </p>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-500">
                <span>Taxa de Adesão dos Tutores</span>
                <Percent className="h-4 w-4 text-teal-600" />
              </div>
              <div className="text-2xl font-extrabold text-slate-900">
                {formatarNumero(metricas.taxa_adesao_pct, 1)}%
              </div>
              <p className="text-[11px] text-slate-500">
                {metricas.triagens_realizadas} triagens de {metricas.total_agendadas} agendadas
              </p>
            </div>

            <div className="rounded-3xl border border-red-200 bg-red-50/60 p-5 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-red-800">
                <span>Emergências &amp; Resgates</span>
                <Siren className="h-4 w-4 text-red-600" />
              </div>
              <div className="text-2xl font-extrabold text-red-700">
                {metricas.urgencias_detectadas} críticas
              </div>
              <p className="text-[11px] text-red-900 flex items-center gap-2">
                <span>{metricas.emergencias_acionadas} em deslocamento</span> ·
                <span className="inline-flex items-center gap-1 font-bold">
                  <Ambulance className="h-3 w-3" />
                  {metricas.resgates_solicitados} resgates GPS
                </span>
              </p>
            </div>
          </section>

          {/* GRÁFICO DE DISTRIBUIÇÃO DE RISCO MANCHESTER + SÉRIE HISTÓRICA DIÁRIA */}
          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Distribuição de Risco Manchester */}
            <div className="lg:col-span-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div>
                <h2 className="text-base font-extrabold text-slate-900">
                  Distribuição de Risco · Protocolo de Manchester
                </h2>
                <p className="text-xs text-slate-500">
                  Classificação das {metricas.triagens_realizadas} triagens preenchidas no período
                </p>
              </div>

              <div className="space-y-3.5">
                {metricas.distribuicao_risco.map((item) => {
                  const estilo = MANCHESTER[item.cor]
                  return (
                    <div key={item.cor} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span
                            className={classes('h-3 w-3 rounded-full', estilo.ponto)}
                          />
                          <span className="font-extrabold text-slate-800">
                            {estilo.cor} — {estilo.rotulo}
                          </span>
                        </div>
                        <span className="font-bold text-slate-700">
                          {item.quantidade} ({formatarNumero(item.percentual, 1)}%)
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={classes('h-full rounded-full transition-all', estilo.barra)}
                          style={{ width: `${Math.max(item.quantidade > 0 ? 6 : 0, item.percentual)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 text-xs text-slate-600 leading-relaxed">
                <strong>Regra de Governança do ROI:</strong> {metricas.observacao}
              </div>
            </div>

            {/* Série Diária de Consultas e Minutos Economizados */}
            <div className="lg:col-span-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-extrabold text-slate-900">
                    Evolução Diária de Economia de Tempo (UTC)
                  </h2>
                  <p className="text-xs text-slate-500">
                    {metricas.consultas_finalizadas} consultas finalizadas (
                    {metricas.consultas_com_triagem} com Triagem Pré-Consulta)
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-teal-700">
                  <Activity className="h-4 w-4" />
                  <span>Benchmark: {metricas.benchmark_minutos} min/consulta</span>
                </div>
              </div>

              {serieComMovimento.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500">
                  Nenhuma consulta finalizada com economia registrada neste intervalo.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
                  {serieComMovimento
                    .slice()
                    .reverse()
                    .map((dia) => {
                      const pct = Math.min(100, (dia.minutos_economizados / maxMinDia) * 100)
                      return (
                        <div
                          key={dia.dia}
                          className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-bold text-slate-800">{dia.dia}</span>
                            <div className="flex items-center gap-3">
                              <span className="inline-flex items-center gap-1 text-slate-600">
                                <Users className="h-3.5 w-3.5" />
                                {dia.consultas} {dia.consultas === 1 ? 'consulta' : 'consultas'}
                              </span>
                              <span className="font-extrabold text-teal-800">
                                +{formatarNumero(dia.minutos_economizados, 1)} min economizados
                              </span>
                            </div>
                          </div>
                          <div className="h-2.5 w-full rounded-full bg-slate-200 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-teal-600 to-emerald-500"
                              style={{ width: `${Math.max(8, pct)}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
