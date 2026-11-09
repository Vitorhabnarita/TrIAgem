import { useCallback, useEffect, useState } from 'react'
import {
  AlertOctagon,
  AlertTriangle,
  Ambulance,
  CheckCircle2,
  CheckSquare,
  ClipboardCheck,
  Clock,
  ExternalLink,
  FileText,
  HeartPulse,
  MapPin,
  Pill,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
  Square,
  StopCircle,
  Stethoscope,
} from 'lucide-react'
import { api } from '../lib/api'
import {
  classes,
  descricaoPet,
  formatarCronometro,
  formatarDataHora,
  formatarHora,
  formatarNumero,
  formatarTelefone,
} from '../lib/format'
import { MANCHESTER } from '../lib/manchester'
import type { Briefing, ConsultaFilaItem, ConsultaFinalizada, ConsultaStatus } from '../types'

const CHECKLIST_EXAME_FISICO_PADRAO = [
  'Coloração de mucosas (róseas, pálidas, ictéricas ou cianóticas)',
  'Tempo de Preenchimento Capilar (TPC ≤ 2s) e grau de hidratação (turgor cutâneo)',
  'Ausculta cardiopulmonar (frequência cardíaca, ritmo, sopros e ruídos respiratórios)',
  'Palpação abdominal (tensão, sensibilidade dolorosa, alças intestinais e repleção vesical)',
  'Temperatura retal, linfonodos palpáveis e escore de condição corporal (ECC)',
]

export function MedicoPage() {
  const [fila, setFila] = useState<ConsultaFilaItem[]>([])
  const [idSelecionada, setIdSelecionada] = useState<number | null>(null)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [carregandoFila, setCarregandoFila] = useState(true)
  const [carregandoBriefing, setCarregandoBriefing] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [acaoCronometro, setAcaoCronometro] = useState(false)
  const [resumoFinalizacao, setResumoFinalizacao] = useState<ConsultaFinalizada | null>(null)
  const [reprocessandoIA, setReprocessandoIA] = useState(false)

  // Cronômetro ao vivo (segundos desde inicio_consulta UTC)
  const [segundosDecorridos, setSegundosDecorridos] = useState<number>(0)

  // Checklist clicável de Exame Físico Presencial (escopado por id_consulta)
  const [exameMarcado, setExameMarcado] = useState<Record<string, boolean>>({})

  const carregarFila = useCallback(async () => {
    try {
      const lista = await api<ConsultaFilaItem[]>('/consultas/fila')
      setFila(lista)
      setIdSelecionada((atual) => {
        if (atual && lista.some((i) => i.id_consulta === atual)) return atual
        return lista[0]?.id_consulta ?? null
      })
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setCarregandoFila(false)
    }
  }, [])

  const carregarBriefing = useCallback(async (idConsulta: number, silencioso = false) => {
    if (!silencioso) setCarregandoBriefing(true)
    setErro(null)
    try {
      const b = await api<Briefing>(`/triagem/${idConsulta}/briefing`)
      setBriefing(b)
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      if (!silencioso) setCarregandoBriefing(false)
    }
  }, [])

  useEffect(() => {
    carregarFila()
    const timer = window.setInterval(carregarFila, 8000)
    return () => window.clearInterval(timer)
  }, [carregarFila])

  useEffect(() => {
    if (idSelecionada) {
      setResumoFinalizacao(null)
      carregarBriefing(idSelecionada)
    } else {
      setBriefing(null)
    }
  }, [idSelecionada, carregarBriefing])

  // Atualiza cronômetro UTC a cada segundo quando em_andamento
  useEffect(() => {
    if (!briefing || !briefing.inicio_consulta) {
      setSegundosDecorridos(0)
      return
    }
    const iniMs = new Date(briefing.inicio_consulta).getTime()
    if (briefing.status === 'finalizada' && briefing.fim_consulta) {
      const fimMs = new Date(briefing.fim_consulta).getTime()
      setSegundosDecorridos(Math.max(0, Math.floor((fimMs - iniMs) / 1000)))
      return
    }
    const tick = () => {
      setSegundosDecorridos(Math.max(0, Math.floor((Date.now() - iniMs) / 1000)))
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [briefing])

  async function handleIniciarConsulta() {
    if (!briefing) return
    setAcaoCronometro(true)
    setErro(null)
    try {
      await api<ConsultaStatus>(`/consultas/${briefing.id_consulta}/iniciar`, {
        method: 'PATCH',
      })
      await Promise.all([carregarFila(), carregarBriefing(briefing.id_consulta, true)])
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setAcaoCronometro(false)
    }
  }

  async function handleFinalizarConsulta() {
    if (!briefing) return
    setAcaoCronometro(true)
    setErro(null)
    try {
      const res = await api<ConsultaFinalizada>(`/consultas/${briefing.id_consulta}/finalizar`, {
        method: 'PATCH',
      })
      setResumoFinalizacao(res)
      await Promise.all([carregarFila(), carregarBriefing(briefing.id_consulta, true)])
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setAcaoCronometro(false)
    }
  }

  async function handleReprocessarIA() {
    if (!briefing) return
    setReprocessandoIA(true)
    setErro(null)
    try {
      await api(`/triagem/${briefing.id_consulta}/reprocessar-ia`, { method: 'POST' })
      window.setTimeout(() => {
        carregarBriefing(briefing.id_consulta, true)
        carregarFila()
      }, 2000)
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setReprocessandoIA(false)
    }
  }

  function alternarItemExame(idx: number) {
    if (!briefing) return
    const chave = `${briefing.id_consulta}:${idx}`
    setExameMarcado((prev) => ({ ...prev, [chave]: !prev[chave] }))
  }

  const benchmarkMin = briefing?.benchmark_minutos ?? 30
  const minutosAtuais = segundosDecorridos / 60
  const minutosEconomizadosAoVivo = Math.max(0, benchmarkMin - minutosAtuais)
  const manchesterAtual = briefing?.relatorio?.cor_prioridade
    ? MANCHESTER[briefing.relatorio.cor_prioridade]
    : briefing?.urgencia
      ? MANCHESTER.VERMELHO
      : null

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 pb-20">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* =====================================================================
            COLUNA LATERAL ESQUERDA: FILA PRIORIZADA MANCHESTER (VERMELHO NO TOPO)
           ===================================================================== */}
        <aside className="lg:col-span-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5 text-teal-600" />
              <div>
                <h1 className="text-sm font-extrabold text-slate-900">
                  Fila Priorizada Manchester
                </h1>
                <p className="text-[11px] text-slate-500">
                  Emergências RN-001 sempre no topo
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={carregarFila}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50 cursor-pointer"
              title="Atualizar fila"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>

          {carregandoFila ? (
            <div className="p-6 text-center text-xs text-slate-500">Carregando fila clínica...</div>
          ) : fila.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              Nenhum paciente na fila para este médico.
            </div>
          ) : (
            <div className="space-y-2 max-h-[72vh] overflow-y-auto pr-1">
              {fila.map((item) => {
                const selecionado = item.id_consulta === idSelecionada
                const m = item.cor_prioridade
                  ? MANCHESTER[item.cor_prioridade]
                  : item.urgencia
                    ? MANCHESTER.VERMELHO
                    : null
                return (
                  <button
                    key={item.id_consulta}
                    type="button"
                    onClick={() => setIdSelecionada(item.id_consulta)}
                    className={classes(
                      'w-full text-left rounded-2xl border p-3.5 transition cursor-pointer',
                      selecionado
                        ? 'border-teal-600 bg-teal-50/70 ring-2 ring-teal-500/30 shadow-sm'
                        : item.urgencia && item.status !== 'finalizada'
                          ? 'border-red-300 bg-red-50/40 hover:bg-red-50/70'
                          : 'border-slate-200 bg-white hover:bg-slate-50',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-extrabold text-slate-900">
                            {item.pet_nome}
                          </span>
                          <span className="text-xs text-slate-500">
                            ({item.especie} · {item.pet_raca})
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Tutor: {item.tutor_nome} · {formatarHora(item.agendada_para)}
                        </div>
                      </div>
                      {m ? (
                        <span
                          className={classes(
                            'shrink-0 rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase',
                            m.fundo,
                          )}
                        >
                          {m.cor}
                        </span>
                      ) : (
                        <span className="shrink-0 rounded-full bg-slate-200 text-slate-700 px-2 py-0.5 text-[10px] font-bold">
                          Sem Triagem
                        </span>
                      )}
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {item.modalidade_emergencia === 'RESGATE_SOLICITADO' && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-400 text-slate-950 px-2 py-0.5 text-[10px] font-extrabold">
                          <Ambulance className="h-3 w-3" />
                          RESGATE GPS
                        </span>
                      )}
                      {item.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO' && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-red-600 text-white px-2 py-0.5 text-[10px] font-extrabold">
                          <Siren className="h-3 w-3" />A CAMINHO
                        </span>
                      )}
                      <span
                        className={classes(
                          'rounded-md px-2 py-0.5 text-[10px] font-bold uppercase',
                          item.status === 'em_andamento'
                            ? 'bg-teal-600 text-white'
                            : item.status === 'finalizada'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-slate-100 text-slate-700',
                        )}
                      >
                        {item.status.replace('_', ' ')}
                      </span>
                      {item.duracao_minutos != null && (
                        <span className="text-[10px] font-semibold text-emerald-700">
                          {formatarNumero(item.duracao_minutos, 1)} min (eco:{' '}
                          {formatarNumero(item.minutos_economizados ?? 0, 1)}m)
                        </span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </aside>

        {/* =====================================================================
            COLUNA PRINCIPAL DIREITA: COCKPIT DO MÉDICO VETERINÁRIO
           ===================================================================== */}
        <section className="lg:col-span-8 space-y-5">
          {erro && (
            <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-xs font-semibold text-red-800 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
              <span>{erro}</span>
            </div>
          )}

          {carregandoBriefing || !briefing ? (
            <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
              {carregandoBriefing
                ? 'Carregando Briefing Clínico Prévio...'
                : 'Selecione um paciente na fila ao lado para abrir o Cockpit Clínico.'}
            </div>
          ) : (
            <>
              {/* CABEÇALHO DO PACIENTE + CRONÔMETRO OPERACIONAL UTC (RN-004) */}
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-extrabold text-slate-900">
                        {briefing.pet.nome}
                      </h2>
                      <span className="rounded-lg bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
                        {descricaoPet(briefing.pet)} · {briefing.pet.sexo} ·{' '}
                        {briefing.pet.idade_texto}
                      </span>
                      {manchesterAtual && (
                        <span
                          className={classes(
                            'rounded-full px-3 py-0.5 text-xs font-extrabold uppercase tracking-wider',
                            manchesterAtual.fundo,
                          )}
                        >
                          {manchesterAtual.cor} · {manchesterAtual.rotulo}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-600">
                      Tutor: <strong>{briefing.tutor.nome}</strong> (
                      {formatarTelefone(briefing.tutor.telefone)}) · Veterinário responsável:{' '}
                      <strong>{briefing.medico.nome}</strong>
                    </p>
                  </div>

                  {/* Painel do Cronômetro Operacional UTC */}
                  <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-slate-900 text-white p-3.5">
                    <div className="flex items-center gap-2">
                      <Clock className="h-5 w-5 text-teal-400" />
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Cronômetro UTC (Benchmark {benchmarkMin}m)
                        </div>
                        <div className="flex items-baseline gap-2">
                          <span className="font-mono text-lg font-extrabold text-white">
                            {formatarCronometro(segundosDecorridos)}
                          </span>
                          {briefing.inicio_consulta && briefing.triagem_preenchida && (
                            <span className="text-[11px] font-bold text-emerald-400">
                              Economia: ~{formatarNumero(minutosEconomizadosAoVivo, 1)} min
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {briefing.status === 'agendada' && (
                      <button
                        type="button"
                        disabled={acaoCronometro}
                        onClick={handleIniciarConsulta}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-teal-500 hover:bg-teal-400 disabled:opacity-50 px-4 py-2 text-xs font-extrabold text-slate-950 shadow cursor-pointer"
                      >
                        <Play className="h-4 w-4" />
                        <span>Iniciar Consulta</span>
                      </button>
                    )}

                    {briefing.status === 'em_andamento' && (
                      <button
                        type="button"
                        disabled={acaoCronometro}
                        onClick={handleFinalizarConsulta}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 px-4 py-2 text-xs font-extrabold text-slate-950 shadow cursor-pointer"
                      >
                        <StopCircle className="h-4 w-4" />
                        <span>Finalizar Consulta</span>
                      </button>
                    )}

                    {briefing.status === 'finalizada' && (
                      <span className="inline-flex items-center gap-1 rounded-xl bg-emerald-500/20 border border-emerald-400/40 px-3 py-1.5 text-xs font-bold text-emerald-300">
                        <CheckCircle2 className="h-4 w-4" />
                        Finalizada
                      </span>
                    )}
                  </div>
                </div>

                {resumoFinalizacao && (
                  <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-3.5 text-xs text-emerald-950 flex items-center justify-between gap-2">
                    <span className="font-bold">{resumoFinalizacao.mensagem}</span>
                    <span className="rounded-lg bg-emerald-600 text-white px-2.5 py-1 font-extrabold">
                      +{formatarNumero(resumoFinalizacao.minutos_economizados, 1)} min no ROI
                    </span>
                  </div>
                )}
              </div>

              {/* =====================================================================
                  ALERTA DE EMERGÊNCIA / DESLOCAMENTO / RESGATE + PROTOCOLO ANTI-ANCORAGEM (ABC)
                 ===================================================================== */}
              {(briefing.urgencia || briefing.modalidade_emergencia) && (
                <div className="rounded-3xl border-2 border-red-600 bg-gradient-to-br from-red-950 via-slate-950 to-slate-900 text-white p-5 shadow-xl space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-red-600 text-white shadow">
                        <Siren className="h-6 w-6" />
                      </div>
                      <div>
                        <span className="inline-block rounded-full bg-red-500/30 border border-red-400/40 px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-red-200">
                          Alerta de Emergência RN-001 v2.0
                        </span>
                        <h3 className="mt-1 text-base font-extrabold">
                          {briefing.modalidade_emergencia === 'RESGATE_SOLICITADO'
                            ? '🚑 Veículo de Resgate Acionado pelo Tutor (GPS Registrado)'
                            : briefing.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO'
                              ? '🚨 Paciente Crítico em Deslocamento — Preparar Box de Emergência e Oxigênio'
                              : '⚠️ Sinais Críticos de Emergência Identificados na Pré-Triagem'}
                        </h3>
                        <div className="mt-1 text-xs text-red-200 flex flex-wrap gap-x-4 gap-y-1">
                          <span>
                            Ciência jurídica de risco de morte:{' '}
                            <strong>{briefing.ciente_risco_morte ? 'Confirmada pelo tutor' : 'Não marcada'}</strong>
                          </span>
                          {briefing.alerta_critico_exibido_em && (
                            <span>
                              Alerta exibido em: {formatarDataHora(briefing.alerta_critico_exibido_em)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {briefing.maps_url_tutor && (
                      <a
                        href={briefing.maps_url_tutor}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 px-3.5 py-2 text-xs font-extrabold shadow"
                      >
                        <MapPin className="h-4 w-4" />
                        <span>Ver Localização GPS ({briefing.localizacao_gps_tutor})</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>

                  {/* Protocolo de Descarte Diferencial Anti-Ancoragem (ABC de Emergência) */}
                  {briefing.protocolo_abc_emergencia.length > 0 && (
                    <div className="rounded-2xl border border-red-400/30 bg-slate-900/90 p-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-300">
                        <HeartPulse className="h-4 w-4 text-amber-400" />
                        <span>
                          Protocolo de Descarte Diferencial Anti-Ancoragem · Exame ABC de Emergência
                        </span>
                      </div>
                      <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-100">
                        {briefing.protocolo_abc_emergencia.map((item, idx) => (
                          <li
                            key={idx}
                            className="rounded-xl border border-slate-800 bg-slate-950/70 p-2.5 leading-snug"
                          >
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Sem Triagem Preenchida */}
              {!briefing.triagem_preenchida || !briefing.formulario ? (
                <div className="rounded-3xl border border-amber-300 bg-amber-50 p-6 text-center space-y-2">
                  <AlertOctagon className="h-8 w-8 text-amber-600 mx-auto" />
                  <h3 className="text-sm font-extrabold text-amber-950">
                    O tutor ainda não enviou o formulário completo da Triagem Pré-Consulta
                  </h3>
                  <p className="text-xs text-amber-800">
                    Você ainda pode iniciar o cronômetro da consulta ou aguardar o preenchimento pelo
                    link enviado no WhatsApp.
                  </p>
                </div>
              ) : (
                <>
                  {/* CARD DE SEGURANÇA FARMACOLÓGICA (48H), BIOINDICADORES E MANEJO PREVENTIVO */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-3xl border-2 border-amber-300 bg-amber-50/70 p-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-900">
                        <Pill className="h-4 w-4 text-amber-700" />
                        <span>Segurança Farmacológica (Últimas 48h) &amp; Bioindicadores</span>
                      </div>
                      <div className="rounded-xl bg-white border border-amber-200 p-3 text-xs space-y-1">
                        <div className="font-bold text-slate-900">
                          Medicação informada: {briefing.formulario.medicamento_continuo}
                        </div>
                        <div className="text-slate-600">
                          Urina/Fezes: {briefing.formulario.aspecto_urina_fezes}
                        </div>
                        <div className="text-slate-600">
                          Apetite/Peso: {briefing.formulario.alteracao_peso_apetite}
                        </div>
                        <div className="text-slate-600">
                          Ingestão hídrica: {briefing.formulario.ingestao_hidrica}
                        </div>
                      </div>
                      {briefing.relatorio?.alerta_medicacao_e_bioindicadores && (
                        <p className="text-xs text-amber-950 font-medium leading-relaxed">
                          {briefing.relatorio.alerta_medicacao_e_bioindicadores}
                        </p>
                      )}
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                      <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-teal-800">
                        <ShieldCheck className="h-4 w-4 text-teal-600" />
                        <span>Manejo Preventivo &amp; Ambiente</span>
                      </div>
                      <div className="text-xs text-slate-700 space-y-1.5">
                        <div className="flex flex-wrap gap-1.5">
                          <span
                            className={classes(
                              'rounded-md px-2 py-0.5 text-[11px] font-bold',
                              briefing.formulario.vacinacao_em_dia
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-red-100 text-red-800',
                            )}
                          >
                            Vacinação: {briefing.formulario.vacinacao_em_dia ? 'Em dia' : 'Atrasada/Incompleta'}
                          </span>
                          <span
                            className={classes(
                              'rounded-md px-2 py-0.5 text-[11px] font-bold',
                              briefing.formulario.vermifugo_em_dia
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800',
                            )}
                          >
                            Vermífugo: {briefing.formulario.vermifugo_em_dia ? 'Em dia' : 'Atrasado'}
                          </span>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                            Contactantes: {briefing.formulario.convivio_outros_animais ? 'Sim' : 'Não'}
                          </span>
                        </div>
                        <p>
                          <strong>Ambiente:</strong> {briefing.formulario.ambiente} ·{' '}
                          <strong>Alimentação:</strong> {briefing.formulario.alimentacao}
                        </p>
                        {briefing.formulario.manejo_preventivo && (
                          <p className="rounded-xl bg-slate-50 border border-slate-200 p-2.5 text-[11px] text-slate-600 leading-relaxed">
                            {briefing.formulario.manejo_preventivo}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* SÍNTESE SEMIOLÓGICA DA IA + BOTÃO REPROCESSAR */}
                  <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-teal-600" />
                        <div>
                          <h3 className="text-sm font-extrabold text-slate-900">
                            Briefing Clínico Prévio · Síntese Semiológica Descritiva
                          </h3>
                          <p className="text-[11px] text-slate-500">
                            Evolução informada: {briefing.formulario.tempo_evolucao} · Modelo:{' '}
                            {briefing.relatorio?.modelo_utilizado ?? briefing.status_ia ?? 'pendente'}
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        disabled={reprocessandoIA}
                        onClick={handleReprocessarIA}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-700 cursor-pointer"
                      >
                        <RefreshCw
                          className={classes('h-3.5 w-3.5', reprocessandoIA && 'animate-spin')}
                        />
                        <span>{reprocessandoIA ? 'Reprocessando...' : 'Reprocessar IA'}</span>
                      </button>
                    </div>

                    {briefing.relatorio ? (
                      <>
                        <p className="text-sm text-slate-800 leading-relaxed font-medium">
                          {briefing.relatorio.resumo_estruturado}
                        </p>

                        {/* Sinais de Alerta (Red Flags) */}
                        {briefing.relatorio.sinais_alerta_identificados.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {briefing.relatorio.sinais_alerta_identificados.map((sinal, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 rounded-lg bg-red-100 border border-red-300 px-2.5 py-1 text-xs font-bold text-red-900"
                              >
                                <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
                                {sinal}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* TABELA: TRADUÇÃO SEMIOLÓGICA LADO A LADO */}
                        {briefing.relatorio.traducao_semiologica.length > 0 && (
                          <div className="overflow-hidden rounded-2xl border border-slate-200">
                            <div className="bg-slate-900 text-white px-4 py-2 text-xs font-extrabold uppercase tracking-wider flex items-center gap-2">
                              <FileText className="h-3.5 w-3.5 text-teal-400" />
                              <span>Tradução Semiológica Lado a Lado (Leigo → Técnico Descritivo)</span>
                            </div>
                            <table className="w-full text-left text-xs">
                              <thead className="bg-slate-100 text-slate-700 border-b border-slate-200">
                                <tr>
                                  <th className="py-2.5 px-4 font-bold w-1/2">
                                    Relato Leigo do Tutor (`relato_leigo`)
                                  </th>
                                  <th className="py-2.5 px-4 font-bold w-1/2">
                                    Termo Semiológico Descritivo (`termo_tecnico_descritivo`)
                                  </th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-200">
                                {briefing.relatorio.traducao_semiologica.map((par, i) => (
                                  <tr key={i} className="hover:bg-slate-50">
                                    <td className="py-2.5 px-4 italic text-slate-600">
                                      &ldquo;{par.relato_leigo}&rdquo;
                                    </td>
                                    <td className="py-2.5 px-4 font-bold text-teal-900">
                                      {par.termo_tecnico_descritivo}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Cronologia e Pontos de Investigação */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-1.5">
                            <div className="text-xs font-extrabold uppercase tracking-wider text-slate-700">
                              Cronologia de Evolução
                            </div>
                            <p className="text-xs text-slate-700 leading-relaxed">
                              {briefing.relatorio.cronologia_evolucao}
                            </p>
                            <div className="pt-2 border-t border-slate-200 mt-2">
                              <div className="text-[11px] font-bold text-slate-500">
                                Relato original do tutor:
                              </div>
                              <p className="text-xs italic text-slate-700 mt-0.5">
                                &ldquo;{briefing.formulario.relato_livre_tutor}&rdquo;
                              </p>
                            </div>
                          </div>

                          <div className="rounded-2xl border border-teal-200 bg-teal-50/50 p-4 space-y-2">
                            <div className="text-xs font-extrabold uppercase tracking-wider text-teal-900">
                              Pontos de Investigação Inicial Presencial
                            </div>
                            <ul className="list-disc list-inside space-y-1 text-xs text-teal-950 font-medium">
                              {briefing.relatorio.pontos_investigacao.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                            <p className="pt-1 text-[11px] text-teal-800">
                              {briefing.relatorio.orientacao_preparatoria_consultorio}
                            </p>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
                        <p className="font-bold text-slate-800">
                          Status do processamento de IA: {briefing.status_ia}
                        </p>
                        <p className="mt-1">
                          Relato bruto do tutor: &ldquo;{briefing.formulario.relato_livre_tutor}
                          &rdquo;
                        </p>
                      </div>
                    )}
                  </div>

                  {/* CHECKLIST CLICÁVEL DE EXAME FÍSICO PRESENCIAL */}
                  <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
                    <div className="flex items-center gap-2">
                      <ClipboardCheck className="h-5 w-5 text-teal-600" />
                      <div>
                        <h3 className="text-sm font-extrabold text-slate-900">
                          Checklist Clicável de Exame Físico Presencial (Anti-Ancoragem)
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          Inspeção física obrigatória em consultório para evitar viés de ancoragem
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-2">
                      {CHECKLIST_EXAME_FISICO_PADRAO.map((item, idx) => {
                        const chave = `${briefing.id_consulta}:${idx}`
                        const marcado = Boolean(exameMarcado[chave])
                        return (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => alternarItemExame(idx)}
                            className={classes(
                              'flex items-center gap-3 rounded-xl border p-3 text-left text-xs transition cursor-pointer',
                              marcado
                                ? 'border-emerald-500 bg-emerald-50 text-emerald-950 font-bold'
                                : 'border-slate-200 bg-slate-50/70 text-slate-800 hover:bg-slate-100',
                            )}
                          >
                            {marcado ? (
                              <CheckSquare className="h-4 w-4 text-emerald-600 shrink-0" />
                            ) : (
                              <Square className="h-4 w-4 text-slate-400 shrink-0" />
                            )}
                            <span>{item}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}

              {/* RODAPÉ FIXO DE GOVERNANÇA ÉTICA CFMV */}
              <footer className="rounded-2xl border border-slate-300 bg-slate-900 text-slate-200 p-4 flex items-start gap-3 text-xs shadow">
                <ShieldAlert className="h-5 w-5 text-teal-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-extrabold text-white uppercase tracking-wider text-[11px]">
                    Declaração de Governança Ética CFMV
                  </div>
                  <p className="mt-0.5 text-slate-300 leading-relaxed">
                    {briefing.relatorio?.aviso_governanca_etica ??
                      'Este documento é um Relatório Clínico Prévio de Triagem Pré-Consulta, elaborado a partir de relato leigo do tutor e organizado por inteligência artificial. Não constitui diagnóstico, prognóstico nem prescrição, e não substitui a avaliação clínica presencial e o julgamento do médico veterinário responsável.'}
                  </p>
                </div>
              </footer>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
