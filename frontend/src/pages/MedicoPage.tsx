import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertOctagon,
  AlertTriangle,
  Ambulance,
  Check,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  ExternalLink,
  HeartPulse,
  MapPin,
  Pill,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
} from 'lucide-react'
import { ManchesterBadge } from '../components/ui'
import { api } from '../lib/api'
import {
  classes,
  formatarCronometro,
  formatarDataHora,
  formatarHora,
  formatarNumero,
  formatarTelefone,
} from '../lib/format'
import { pesoManchester } from '../lib/manchester'
import type { Briefing, ConsultaFilaItem, ConsultaFinalizada, ConsultaStatus } from '../types'

const EXAME_FISICO = [
  'Mucosas (coloração) e TPC',
  'Hidratação (turgor cutâneo)',
  'Ausculta cardiopulmonar',
  'Palpação abdominal e vesical',
  'Temperatura retal',
  'Linfonodos e escore de condição corporal',
]

const AVISO_CFMV =
  'Relatório Clínico Prévio organizado por IA a partir do relato leigo do tutor. Não constitui diagnóstico, prognóstico nem prescrição e não substitui a avaliação clínica presencial do médico veterinário responsável.'

type Filtro = 'todos' | 'prontos' | 'urgencias'

const aberta = (i: ConsultaFilaItem) => i.status === 'agendada' || i.status === 'em_andamento'

/** Checklist persistente por consulta (riscado suave ao marcar). */
function useChecklist(chave: string) {
  const [marcados, setMarcados] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(localStorage.getItem(chave) ?? '{}') as Record<string, boolean>
    } catch {
      return {}
    }
  })
  useEffect(() => {
    try {
      setMarcados(JSON.parse(localStorage.getItem(chave) ?? '{}') as Record<string, boolean>)
    } catch {
      setMarcados({})
    }
  }, [chave])
  const alternar = (id: string) =>
    setMarcados((prev) => {
      const novo = { ...prev, [id]: !prev[id] }
      localStorage.setItem(chave, JSON.stringify(novo))
      return novo
    })
  return { marcados, alternar }
}

function Checklist({
  titulo,
  itens,
  prefixo,
  marcados,
  alternar,
}: {
  titulo: string
  itens: string[]
  prefixo: string
  marcados: Record<string, boolean>
  alternar: (id: string) => void
}) {
  const feitos = itens.filter((_, i) => marcados[`${prefixo}${i}`]).length
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold text-ink">
          <ClipboardCheck className="h-4 w-4 text-brand" />
          {titulo}
        </h3>
        <span className="text-xs font-medium text-ink-soft">{feitos}/{itens.length}</span>
      </div>
      <ul className="space-y-1.5">
        {itens.map((item, i) => {
          const id = `${prefixo}${i}`
          const ok = Boolean(marcados[id])
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => alternar(id)}
                aria-pressed={ok}
                className="flex w-full cursor-pointer items-start gap-3 rounded-xl px-2.5 py-2 text-left transition hover:bg-slate-50"
              >
                <span className={classes('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition', ok ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-300 text-transparent')}>
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
                <span className={classes('text-sm leading-snug transition', ok ? 'text-slate-400 line-through decoration-slate-300' : 'text-slate-700')}>
                  {item}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Chip({ ok, children }: { ok: boolean | null; children: React.ReactNode }) {
  const cor = ok === null ? 'bg-slate-100 text-slate-700 ring-slate-200' : ok ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : 'bg-amber-50 text-amber-800 ring-amber-200'
  return <span className={classes('inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset', cor)}>{children}</span>
}

export function MedicoPage() {
  const [fila, setFila] = useState<ConsultaFilaItem[]>([])
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [idSelecionada, setIdSelecionada] = useState<number | null>(null)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [carregandoFila, setCarregandoFila] = useState(true)
  const [carregandoBriefing, setCarregandoBriefing] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [acao, setAcao] = useState(false)
  const [resumo, setResumo] = useState<ConsultaFinalizada | null>(null)
  const [reprocessando, setReprocessando] = useState(false)
  const [segundos, setSegundos] = useState(0)

  const { marcados, alternar } = useChecklist(`triagem.checklist.${idSelecionada ?? 0}`)

  const carregarFila = useCallback(async () => {
    try {
      const lista = await api<ConsultaFilaItem[]>('/consultas/fila')
      setFila(lista)
      setIdSelecionada((atual) => (atual && lista.some((i) => i.id_consulta === atual) ? atual : (lista[0]?.id_consulta ?? null)))
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setCarregandoFila(false)
    }
  }, [])

  const carregarBriefing = useCallback(async (id: number, silencioso = false) => {
    if (!silencioso) setCarregandoBriefing(true)
    setErro(null)
    try {
      setBriefing(await api<Briefing>(`/triagem/${id}/briefing`))
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      if (!silencioso) setCarregandoBriefing(false)
    }
  }, [])

  useEffect(() => {
    carregarFila()
    const t = window.setInterval(carregarFila, 8000)
    return () => window.clearInterval(t)
  }, [carregarFila])

  useEffect(() => {
    if (idSelecionada) {
      setResumo(null)
      carregarBriefing(idSelecionada)
    } else setBriefing(null)
  }, [idSelecionada, carregarBriefing])

  // Cronômetro UTC
  useEffect(() => {
    if (!briefing?.inicio_consulta) {
      setSegundos(0)
      return
    }
    const ini = new Date(briefing.inicio_consulta).getTime()
    if (briefing.status === 'finalizada' && briefing.fim_consulta) {
      setSegundos(Math.max(0, Math.floor((new Date(briefing.fim_consulta).getTime() - ini) / 1000)))
      return
    }
    const tick = () => setSegundos(Math.max(0, Math.floor((Date.now() - ini) / 1000)))
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [briefing])

  const filaOrdenada = useMemo(() => {
    const peso = (i: ConsultaFilaItem) => (i.cor_prioridade ? pesoManchester(i.cor_prioridade) : i.urgencia ? 0 : 5)
    return [...fila]
      .filter((i) => (filtro === 'urgencias' ? aberta(i) && i.urgencia : filtro === 'prontos' ? aberta(i) && i.status_triagem !== 'pendente' : true))
      .sort((a, b) => {
        if (aberta(a) !== aberta(b)) return aberta(a) ? -1 : 1
        if (Boolean(a.modalidade_emergencia) !== Boolean(b.modalidade_emergencia)) return a.modalidade_emergencia ? -1 : 1
        return peso(a) - peso(b)
      })
  }, [fila, filtro])

  async function iniciar() {
    if (!briefing) return
    setAcao(true)
    setErro(null)
    try {
      await api<ConsultaStatus>(`/consultas/${briefing.id_consulta}/iniciar`, { method: 'PATCH' })
      await Promise.all([carregarFila(), carregarBriefing(briefing.id_consulta, true)])
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setAcao(false)
    }
  }

  async function finalizar() {
    if (!briefing) return
    setAcao(true)
    setErro(null)
    try {
      setResumo(await api<ConsultaFinalizada>(`/consultas/${briefing.id_consulta}/finalizar`, { method: 'PATCH' }))
      await Promise.all([carregarFila(), carregarBriefing(briefing.id_consulta, true)])
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setAcao(false)
    }
  }

  async function reprocessar() {
    if (!briefing) return
    setReprocessando(true)
    try {
      await api(`/triagem/${briefing.id_consulta}/reprocessar-ia`, { method: 'POST' })
      window.setTimeout(() => {
        carregarBriefing(briefing.id_consulta, true)
        carregarFila()
      }, 2000)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setReprocessando(false)
    }
  }

  const bench = briefing?.benchmark_minutos ?? 30
  const economia = Math.max(0, bench - segundos / 60)
  const rel = briefing?.relatorio ?? null
  const form = briefing?.formulario ?? null
  const acessoRua = form?.manejo_preventivo?.match(/Acesso à rua: ([^·]+)/)?.[1]?.trim()

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 pb-24">
      <div className="grid items-start gap-6 lg:grid-cols-12">
        {/* ============ Sidebar compacta ============ */}
        <aside className="card p-3 lg:sticky lg:top-20 lg:col-span-4">
          <div className="flex items-center justify-between px-2 pb-3 pt-1">
            <h1 className="text-sm font-bold text-ink">Pacientes de hoje</h1>
            <button type="button" onClick={carregarFila} title="Atualizar" aria-label="Atualizar" className="cursor-pointer rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-50 hover:text-brand">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          <div className="mb-3 flex rounded-xl bg-slate-100 p-1">
            {(['todos', 'prontos', 'urgencias'] as Filtro[]).map((f) => (
              <button key={f} type="button" onClick={() => setFiltro(f)} className={classes('flex-1 cursor-pointer rounded-lg py-1.5 text-xs font-semibold capitalize transition', filtro === f ? 'bg-white text-ink shadow-sm' : 'text-ink-soft hover:text-ink')}>
                {f === 'urgencias' ? 'Urgências' : f === 'prontos' ? 'Prontos' : 'Todos'}
              </button>
            ))}
          </div>

          {carregandoFila ? (
            <p className="p-6 text-center text-sm text-ink-soft">Carregando…</p>
          ) : filaOrdenada.length === 0 ? (
            <p className="p-6 text-center text-sm text-ink-soft">Nenhum paciente nesta visão.</p>
          ) : (
            <ul className="max-h-[68vh] space-y-1.5 overflow-y-auto pr-0.5">
              {filaOrdenada.map((i) => {
                const sel = i.id_consulta === idSelecionada
                return (
                  <li key={i.id_consulta}>
                    <button
                      type="button"
                      onClick={() => setIdSelecionada(i.id_consulta)}
                      className={classes(
                        'relative w-full cursor-pointer rounded-xl py-3 pl-4 pr-3 text-left transition',
                        sel ? 'bg-brand-soft' : 'hover:bg-slate-50',
                        !aberta(i) && 'opacity-60',
                      )}
                    >
                      {sel && <span className="bg-brand-gradient absolute inset-y-2 left-0 w-1 rounded-full" />}
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-bold text-ink">{i.pet_nome}</span>
                        <ManchesterBadge cor={i.cor_prioridade ?? (i.urgencia ? 'VERMELHO' : null)} />
                      </div>
                      <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-ink-soft">
                        <span className="truncate">{i.especie} · {i.pet_raca}</span>
                        <span className="shrink-0">{formatarHora(i.agendada_para)}</span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
                        {i.modalidade_emergencia && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-red-600 px-1.5 py-0.5 font-bold text-white">
                            {i.modalidade_emergencia === 'RESGATE_SOLICITADO' ? <Ambulance className="h-3 w-3" /> : <Siren className="h-3 w-3" />}
                            {i.modalidade_emergencia === 'RESGATE_SOLICITADO' ? 'Resgate' : 'A caminho'}
                          </span>
                        )}
                        {i.status === 'em_andamento' && <span className="font-semibold text-brand">em consulta</span>}
                        {i.status === 'finalizada' && <span className="font-semibold text-emerald-600">finalizada</span>}
                        {i.status === 'cancelada' && <span className="font-semibold text-slate-500">cancelada</span>}
                        {i.status === 'agendada' && i.status_triagem === 'pendente' && <span className="text-slate-500">aguardando triagem</span>}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </aside>

        {/* ============ Cockpit ============ */}
        <section className="space-y-5 lg:col-span-8">
          {erro && (
            <div className="flex items-center gap-2 rounded-xl bg-red-50 p-3.5 text-sm text-red-700 ring-1 ring-red-200">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {erro}
            </div>
          )}

          {carregandoBriefing || !briefing ? (
            <div className="card p-12 text-center text-sm text-ink-soft">
              {carregandoBriefing ? 'Abrindo briefing clínico…' : 'Selecione um paciente na lista.'}
            </div>
          ) : (
            <>
              {/* Header do paciente + cronômetro */}
              <div className="card sticky top-16 z-20 flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-xl font-extrabold tracking-tight text-ink">{briefing.pet.nome}</h2>
                    <ManchesterBadge cor={rel?.cor_prioridade ?? (briefing.urgencia ? 'VERMELHO' : null)} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Chip ok={null}>{briefing.pet.especie} · {briefing.pet.raca}</Chip>
                    <Chip ok={null}>{briefing.pet.sexo} · {briefing.pet.idade_texto}</Chip>
                    {briefing.pet.peso_kg != null && <Chip ok={null}>{formatarNumero(briefing.pet.peso_kg, 2)} kg</Chip>}
                    {briefing.pet.porte && <Chip ok={null}>Porte {briefing.pet.porte.toLowerCase()}</Chip>}
                    {briefing.pet.status_reprodutivo && <Chip ok={null}>{briefing.pet.status_reprodutivo}</Chip>}
                  </div>
                  <p className="mt-2 text-xs text-ink-soft">
                    Tutor {briefing.tutor.nome} · {formatarTelefone(briefing.tutor.telefone)}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-4 rounded-2xl bg-slate-50 p-3 pr-4 ring-1 ring-slate-200">
                  <div className="flex items-center gap-2.5">
                    <Clock className="h-5 w-5 text-brand" />
                    <div className="leading-tight">
                      <div className="font-mono text-2xl font-extrabold tabular-nums text-ink">{formatarCronometro(segundos)}</div>
                      <div className="text-[11px] text-ink-soft">
                        {briefing.inicio_consulta && briefing.triagem_preenchida
                          ? `economia ~${formatarNumero(economia, 1)} min`
                          : `UTC · benchmark ${bench} min`}
                      </div>
                    </div>
                  </div>
                  {briefing.status === 'agendada' && (
                    <button type="button" disabled={acao} onClick={iniciar} className="btn-primary">
                      <Play className="h-4 w-4" />
                      Iniciar
                    </button>
                  )}
                  {briefing.status === 'em_andamento' && (
                    <button type="button" disabled={acao} onClick={finalizar} className="btn-success">
                      <CheckCircle2 className="h-4 w-4" />
                      Finalizar
                    </button>
                  )}
                  {briefing.status === 'finalizada' && (
                    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-600">
                      <CheckCircle2 className="h-4 w-4" />
                      Finalizada
                    </span>
                  )}
                </div>
              </div>

              {resumo && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-900 ring-1 ring-emerald-200">
                  <span className="font-semibold">{resumo.mensagem}</span>
                  <span className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-bold text-white">+{formatarNumero(resumo.minutos_economizados, 1)} min no ROI</span>
                </div>
              )}

              {/* Emergência + ABC */}
              {(briefing.urgencia || briefing.modalidade_emergencia) && (
                <div className="space-y-4 rounded-2xl bg-red-600 p-5 text-white shadow-lg">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <Siren className="mt-0.5 h-6 w-6 shrink-0" />
                      <div>
                        <h3 className="text-base font-extrabold leading-tight">
                          {briefing.modalidade_emergencia === 'RESGATE_SOLICITADO'
                            ? 'Resgate acionado pelo tutor — GPS registrado'
                            : briefing.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO'
                              ? 'Paciente crítico a caminho — prepare o Box de Emergência'
                              : 'Sinais críticos identificados na triagem'}
                        </h3>
                        <p className="mt-1 text-xs text-red-100">
                          Ciência de risco: <strong>{briefing.ciente_risco_morte ? 'confirmada' : 'não marcada'}</strong>
                          {briefing.alerta_critico_exibido_em && ` · alerta exibido ${formatarDataHora(briefing.alerta_critico_exibido_em)}`}
                        </p>
                      </div>
                    </div>
                    {briefing.maps_url_tutor && (
                      <a href={briefing.maps_url_tutor} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-xs font-bold text-red-700 transition hover:bg-red-50">
                        <MapPin className="h-4 w-4" />
                        Ver localização
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {briefing.protocolo_abc_emergencia.length > 0 && (
                    <div className="rounded-xl bg-white/10 p-4">
                      <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
                        <HeartPulse className="h-4 w-4" />
                        Protocolo anti-ancoragem · Exame ABC
                      </div>
                      <ul className="grid gap-1.5 text-sm md:grid-cols-2">
                        {briefing.protocolo_abc_emergencia.map((p, i) => (
                          <li key={i} className="rounded-lg bg-white/10 px-3 py-2 leading-snug">{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {!briefing.triagem_preenchida || !form ? (
                <div className="card space-y-2 p-8 text-center">
                  <AlertOctagon className="mx-auto h-8 w-8 text-amber-500" />
                  <h3 className="text-sm font-bold text-ink">O tutor ainda não enviou a triagem</h3>
                  <p className="text-sm text-ink-soft">Você pode iniciar a consulta normalmente ou aguardar o preenchimento.</p>
                </div>
              ) : (
                <>
                  {/* 1 · Segurança primeiro */}
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
                      <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-amber-900">
                        <Pill className="h-4 w-4" />
                        Segurança farmacológica · 48h
                      </h3>
                      <p className="text-sm font-semibold text-ink">{form.medicamento_continuo}</p>
                      {rel?.alerta_medicacao_e_bioindicadores && (
                        <p className="mt-2 text-xs leading-relaxed text-amber-900/80">{rel.alerta_medicacao_e_bioindicadores}</p>
                      )}
                      <dl className="mt-3 grid grid-cols-1 gap-1 text-xs text-ink-soft">
                        <div><dt className="inline font-semibold">Urina/fezes:</dt> <dd className="inline">{form.aspecto_urina_fezes}</dd></div>
                        <div><dt className="inline font-semibold">Apetite/peso:</dt> <dd className="inline">{form.alteracao_peso_apetite}</dd></div>
                        <div><dt className="inline font-semibold">Água:</dt> <dd className="inline">{form.ingestao_hidrica}</dd></div>
                      </dl>
                    </div>

                    <div className="card p-5">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-ink">
                        <ShieldCheck className="h-4 w-4 text-brand" />
                        Manejo preventivo
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        <Chip ok={form.vacinacao_em_dia}>Vacinas {form.vacinacao_em_dia ? 'em dia' : 'pendentes'}</Chip>
                        <Chip ok={form.vermifugo_em_dia}>Vermífugo {form.vermifugo_em_dia ? 'em dia' : 'atrasado'}</Chip>
                        {acessoRua && <Chip ok={null}>{acessoRua}</Chip>}
                        <Chip ok={null}>{form.convivio_outros_animais ? 'Convive com outros animais' : 'Sem contactantes'}</Chip>
                      </div>
                      <p className="mt-3 text-xs text-ink-soft">{form.ambiente} · {form.alimentacao}</p>
                    </div>
                  </div>

                  {rel && rel.sinais_alerta_identificados.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {rel.sinais_alerta_identificados.map((s, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-800 ring-1 ring-inset ring-red-200">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* 2 · Resumo IA + tradução */}
                  <div className="card space-y-5 border-ai/30 p-5 ring-1 ring-ai/10">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="flex items-center gap-2 text-sm font-bold text-ai">
                        <Sparkles className="h-4 w-4" />
                        Resumo estruturado · TrIAgem IA
                      </h3>
                      <button type="button" disabled={reprocessando} onClick={reprocessar} className="btn-ghost px-3 py-1.5 text-xs">
                        <RefreshCw className={classes('h-3.5 w-3.5', reprocessando && 'animate-spin')} />
                        {reprocessando ? 'Reprocessando…' : 'Reprocessar'}
                      </button>
                    </div>

                    {rel ? (
                      <>
                        <p className="text-sm leading-relaxed text-ink">{rel.resumo_estruturado}</p>

                        {rel.traducao_semiologica.length > 0 && (
                          <div className="overflow-hidden rounded-xl border border-slate-200">
                            <table className="w-full text-left text-sm">
                              <thead className="bg-ai-soft text-xs font-semibold uppercase tracking-wide text-ai">
                                <tr>
                                  <th className="px-4 py-2.5">O que o tutor relatou</th>
                                  <th className="px-4 py-2.5">Tradução semiológica</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {rel.traducao_semiologica.map((p, i) => (
                                  <tr key={i}>
                                    <td className="px-4 py-3 italic text-ink-soft">“{p.relato_leigo}”</td>
                                    <td className="px-4 py-3 font-semibold text-ink">{p.termo_tecnico_descritivo}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-ink-soft">Cronologia</h4>
                            <p className="text-sm leading-relaxed text-slate-700">{rel.cronologia_evolucao}</p>
                          </div>
                          <div>
                            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-ink-soft">Relato original</h4>
                            <p className="text-sm italic leading-relaxed text-slate-600">“{form.relato_livre_tutor}”</p>
                          </div>
                        </div>
                        {rel.orientacao_preparatoria_consultorio && (
                          <p className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-ink-soft">{rel.orientacao_preparatoria_consultorio}</p>
                        )}
                      </>
                    ) : (
                      <div className="rounded-xl bg-slate-50 p-4 text-sm text-ink-soft">
                        <p className="font-semibold text-ink">Processamento da IA: {briefing.status_ia}</p>
                        <p className="mt-1 italic">“{form.relato_livre_tutor}”</p>
                      </div>
                    )}
                  </div>

                  {/* 3 · Checklists */}
                  <div className="grid gap-4 md:grid-cols-2">
                    {rel && rel.pontos_investigacao.length > 0 && (
                      <Checklist titulo="Pontos de investigação" itens={rel.pontos_investigacao} prefixo="inv" marcados={marcados} alternar={alternar} />
                    )}
                    <Checklist titulo="Exame físico presencial" itens={EXAME_FISICO} prefixo="exa" marcados={marcados} alternar={alternar} />
                  </div>
                </>
              )}
            </>
          )}
        </section>
      </div>

      {/* Rodapé ético CFMV (discreto e fixo) */}
      <footer className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 backdrop-blur">
        <p className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-2 text-[11px] leading-snug text-ink-soft">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-ai" />
          <span><strong className="text-ink">Governança ética CFMV:</strong> {rel?.aviso_governanca_etica ?? AVISO_CFMV}</span>
        </p>
      </footer>
    </main>
  )
}
