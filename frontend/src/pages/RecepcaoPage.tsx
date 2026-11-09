import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ambulance,
  CalendarPlus,
  CheckCircle2,
  Clock,
  ExternalLink,
  MapPin,
  MessageCircle,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Siren,
  Smartphone,
  Stethoscope,
  UserCheck,
  X,
  XCircle,
} from 'lucide-react'
import { api } from '../lib/api'
import {
  classes,
  descricaoPet,
  formatarHora,
  formatarTelefone,
  linkTutorLocal,
} from '../lib/format'
import { MANCHESTER } from '../lib/manchester'
import type {
  ConsultaAgendar,
  ConsultaFilaItem,
  MedicoOut,
  PetResumo,
  TutorComPets,
} from '../types'

export function RecepcaoPage() {
  const [fila, setFila] = useState<ConsultaFilaItem[]>([])
  const [medicos, setMedicos] = useState<MedicoOut[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [filtroMedico, setFiltroMedico] = useState<number | ''>('')
  const [filtroStatus, setFiltroStatus] = useState<string>('')

  // Modal de Novo Agendamento
  const [modalAberto, setModalAberto] = useState(false)
  const [buscaTutor, setBuscaTutor] = useState('')
  const [tutoresEncontrados, setTutoresEncontrados] = useState<TutorComPets[]>([])
  const [idMedicoNovo, setIdMedicoNovo] = useState<number>(0)
  const [tutorNome, setTutorNome] = useState('')
  const [tutorTelefone, setTutorTelefone] = useState('')
  const [petNome, setPetNome] = useState('')
  const [petEspecie, setPetEspecie] = useState('Cão')
  const [petRaca, setPetRaca] = useState('Sem raça definida (SRD)')
  const [petSexo, setPetSexo] = useState<'Macho' | 'Fêmea' | 'Não informado'>('Macho')
  const [petIdade, setPetIdade] = useState('3 anos')
  const [petPesoKg, setPetPesoKg] = useState<string>('')
  const [petPorte, setPetPorte] = useState<
    '' | 'Mini' | 'Pequeno' | 'Médio' | 'Grande' | 'Gigante'
  >('Médio')
  const [petStatusReprodutivo, setPetStatusReprodutivo] = useState<'' | 'Castrado' | 'Inteiro'>(
    'Castrado',
  )
  const [salvandoAgendamento, setSalvandoAgendamento] = useState(false)
  const [recemAgendada, setRecemAgendada] = useState<ConsultaFilaItem | null>(null)

  const carregarDados = useCallback(async () => {
    setErro(null)
    try {
      const [listaFila, listaMedicos] = await Promise.all([
        api<ConsultaFilaItem[]>('/consultas/fila', {
          query: {
            id_medico: filtroMedico || undefined,
            status: filtroStatus || undefined,
          },
        }),
        api<MedicoOut[]>('/clinicas/me/medicos'),
      ])
      setFila(listaFila)
      setMedicos(listaMedicos)
      if (listaMedicos.length > 0 && !idMedicoNovo) {
        setIdMedicoNovo(listaMedicos[0].id_medico)
      }
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setCarregando(false)
    }
  }, [filtroMedico, filtroStatus, idMedicoNovo])

  useEffect(() => {
    carregarDados()
    const timer = window.setInterval(carregarDados, 8000)
    return () => window.clearInterval(timer)
  }, [carregarDados])

  // Busca de tutores para autocompletar no modal
  useEffect(() => {
    if (!modalAberto) return
    let ativo = true
    const handle = window.setTimeout(async () => {
      try {
        const res = await api<TutorComPets[]>('/clinicas/me/tutores', {
          query: { q: buscaTutor.trim() },
        })
        if (ativo) setTutoresEncontrados(res)
      } catch {
        // Silencioso
      }
    }, 220)
    return () => {
      ativo = false
      window.clearTimeout(handle)
    }
  }, [modalAberto, buscaTutor])

  // Pacientes com emergência ativa em deslocamento ou solicitação de resgate GPS
  const emergenciasAtivas = useMemo(
    () =>
      fila.filter(
        (c) =>
          (c.status === 'agendada' || c.status === 'em_andamento') &&
          (c.modalidade_emergencia !== null || c.urgencia),
      ),
    [fila],
  )

  function selecionarTutorPet(t: TutorComPets, p?: PetResumo) {
    setTutorNome(t.nome)
    setTutorTelefone(t.telefone)
    if (p) {
      setPetNome(p.nome)
      setPetEspecie(p.especie)
      setPetRaca(p.raca)
      setPetSexo(
        p.sexo === 'Macho' || p.sexo === 'Fêmea' ? p.sexo : 'Não informado',
      )
      setPetIdade(p.idade_texto)
      setPetPesoKg(p.peso_kg != null ? String(p.peso_kg) : '')
      setPetPorte((p.porte as typeof petPorte) ?? '')
      setPetStatusReprodutivo((p.status_reprodutivo as typeof petStatusReprodutivo) ?? '')
    }
  }

  async function handleCriarAgendamento(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    setSalvandoAgendamento(true)
    try {
      const pesoNum = petPesoKg.trim() ? Number(petPesoKg.replace(',', '.')) : null
      const payload: ConsultaAgendar = {
        id_medico: idMedicoNovo || medicos[0]?.id_medico,
        tutor: { nome: tutorNome.trim(), telefone: tutorTelefone.trim() },
        pet: {
          nome: petNome.trim(),
          especie: petEspecie.trim(),
          raca: petRaca.trim() || 'Sem raça definida',
          sexo: petSexo,
          idade_texto: petIdade.trim() || 'Não informada',
          peso_kg: pesoNum && !Number.isNaN(pesoNum) ? pesoNum : null,
          porte: petPorte || null,
          status_reprodutivo: petStatusReprodutivo || null,
        },
      }
      const criada = await api<ConsultaFilaItem>('/consultas', {
        method: 'POST',
        body: payload,
      })
      setRecemAgendada(criada)
      await carregarDados()
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setSalvandoAgendamento(false)
    }
  }

  async function handleRenovarLink(idConsulta: number) {
    try {
      await api<ConsultaFilaItem>(`/consultas/${idConsulta}/novo-link`, { method: 'POST' })
      await carregarDados()
    } catch (err) {
      setErro((err as Error).message)
    }
  }

  async function handleCancelarConsulta(idConsulta: number) {
    try {
      await api(`/consultas/${idConsulta}/cancelar`, { method: 'PATCH' })
      await carregarDados()
    } catch (err) {
      setErro((err as Error).message)
    }
  }

  function abrirModalNovo() {
    setRecemAgendada(null)
    setTutorNome('')
    setTutorTelefone('')
    setPetNome('')
    setPetPesoKg('')
    setBuscaTutor('')
    setModalAberto(true)
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 space-y-6">
      {/* =====================================================================
          TOPO: ALARME VISUAL PULSANTE DE EMERGÊNCIA / RESGATE GPS (RN-001 v2.0)
         ===================================================================== */}
      {emergenciasAtivas.length > 0 && (
        <section className="rounded-3xl border-2 border-red-600 bg-gradient-to-r from-red-950 via-red-900 to-slate-950 text-white p-5 shadow-xl emergency-pulse space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-600 text-white shadow">
                <Siren className="h-6 w-6 animate-bounce" />
              </div>
              <div>
                <span className="text-[11px] font-extrabold uppercase tracking-wider text-red-200">
                  Alarme Operacional de Emergência · Protocolo RN-001 v2.0
                </span>
                <h2 className="text-base sm:text-lg font-extrabold">
                  {emergenciasAtivas.length}{' '}
                  {emergenciasAtivas.length === 1
                    ? 'Paciente Crítico Exige Prioridade Imediata'
                    : 'Pacientes Críticos Exigem Prioridade Imediata'}
                </h2>
              </div>
            </div>
            <span className="rounded-full bg-red-600 px-3 py-1 text-xs font-extrabold uppercase tracking-wider">
              Prioridade Vermelha Manchester
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {emergenciasAtivas.map((item) => {
              const ehResgate = item.modalidade_emergencia === 'RESGATE_SOLICITADO'
              const ehACaminho = item.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO'
              return (
                <div
                  key={item.id_consulta}
                  className="rounded-2xl border border-red-400/40 bg-slate-950/75 p-4 flex flex-col justify-between gap-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="text-sm font-extrabold text-white">
                        {item.pet_nome} ({item.especie} · {item.pet_raca})
                      </span>
                      {ehResgate && (
                        <span className="inline-flex items-center gap-1 rounded-lg bg-amber-400 text-slate-950 px-2.5 py-0.5 text-[11px] font-extrabold">
                          <Ambulance className="h-3.5 w-3.5" />
                          RESGATE GPS SOLICITADO
                        </span>
                      )}
                      {ehACaminho && (
                        <span className="inline-flex items-center gap-1 rounded-lg bg-red-600 text-white px-2.5 py-0.5 text-[11px] font-extrabold">
                          <Siren className="h-3.5 w-3.5" />
                          EMERGÊNCIA A CAMINHO
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-red-100 font-semibold">
                      {ehResgate
                        ? `🚑 Despachar Veículo de Resgate Agora! Localização GPS: ${item.localizacao_gps_tutor ?? ' informada'}`
                        : ehACaminho
                          ? '🚨 Paciente crítico em deslocamento — Preparar Box de Emergência e Oxigênio!'
                          : '⚠️ Triagem com Alerta Crítico de Emergência — Priorizar entrada imediata em consultório!'}
                    </p>

                    <div className="text-[11px] text-slate-300 flex flex-wrap gap-x-3 gap-y-1">
                      <span>Tutor: {item.tutor_nome}</span>
                      <span>Tel: {formatarTelefone(item.tutor_telefone)}</span>
                      <span>Vet: {item.medico.nome}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    {item.maps_url_tutor && (
                      <a
                        href={item.maps_url_tutor}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 px-3 py-1.5 text-xs font-extrabold shadow"
                      >
                        <MapPin className="h-3.5 w-3.5" />
                        <span>Abrir GPS do Tutor no Google Maps</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                    <a
                      href={linkTutorLocal(item.link_triagem)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-xl border border-red-400/50 bg-red-900/50 hover:bg-red-800 px-3 py-1.5 text-xs font-bold text-white"
                    >
                      <Smartphone className="h-3.5 w-3.5" />
                      <span>Ver Celular do Tutor</span>
                    </a>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Cabeçalho Operacional + Filtros + Botão Novo Agendamento */}
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900">
            Painel Operacional da Recepção
          </h1>
          <p className="text-xs text-slate-600">
            Gestão da fila do dia, disparo do link único no WhatsApp e monitoramento de emergências
            em tempo real.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={filtroMedico}
            onChange={(e) => setFiltroMedico(e.target.value ? Number(e.target.value) : '')}
            className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-800"
          >
            <option value="">Todos os veterinários</option>
            {medicos.map((m) => (
              <option key={m.id_medico} value={m.id_medico}>
                {m.nome} ({m.crmv})
              </option>
            ))}
          </select>

          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-800"
          >
            <option value="">Todos os status</option>
            <option value="agendada">Agendadas</option>
            <option value="em_andamento">Em andamento</option>
            <option value="finalizada">Finalizadas</option>
          </select>

          <button
            type="button"
            onClick={carregarDados}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Atualizar</span>
          </button>

          <button
            type="button"
            onClick={abrirModalNovo}
            className="inline-flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-600 px-4 py-2.5 text-xs font-extrabold text-white shadow cursor-pointer"
          >
            <CalendarPlus className="h-4 w-4" />
            <span>Novo Agendamento + Link WhatsApp</span>
          </button>
        </div>
      </section>

      {erro && (
        <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-xs font-semibold text-red-800 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
          <span>{erro}</span>
        </div>
      )}

      {/* Lista / Fila do Dia */}
      <section className="space-y-3">
        {carregando ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
            Carregando fila de atendimento...
          </div>
        ) : fila.length === 0 ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center space-y-3">
            <p className="text-sm font-bold text-slate-700">
              Nenhuma consulta encontrada para os filtros selecionados.
            </p>
            <button
              type="button"
              onClick={abrirModalNovo}
              className="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-2 text-xs font-bold text-white cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              Agendar Primeira Consulta
            </button>
          </div>
        ) : (
          fila.map((item) => {
            const manchester = item.cor_prioridade ? MANCHESTER[item.cor_prioridade] : null
            const urlSimulador = linkTutorLocal(item.link_triagem)
            return (
              <article
                key={item.id_consulta}
                className={classes(
                  'rounded-2xl border bg-white p-4 sm:p-5 shadow-sm transition',
                  item.urgencia && item.status !== 'finalizada'
                    ? 'border-l-8 border-l-red-600 border-red-300 bg-red-50/20'
                    : 'border-slate-200',
                )}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Dados do Pet, Tutor e Veterinário */}
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-extrabold text-slate-900">
                        {item.pet_nome}
                      </span>
                      <span className="rounded-lg bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
                        {descricaoPet({
                          especie: item.especie,
                          raca: item.pet_raca,
                          peso_kg: item.pet_peso_kg,
                          porte: item.pet_porte,
                          status_reprodutivo: item.pet_status_reprodutivo,
                        })}
                      </span>

                      {/* Badge Manchester */}
                      {manchester ? (
                        <span
                          className={classes(
                            'rounded-full px-2.5 py-0.5 text-[11px] font-extrabold uppercase tracking-wider',
                            manchester.fundo,
                          )}
                        >
                          {manchester.cor} · {manchester.rotulo}
                        </span>
                      ) : (
                        <span className="rounded-full bg-amber-100 text-amber-900 px-2.5 py-0.5 text-[11px] font-bold">
                          Triagem Pendente
                        </span>
                      )}

                      {/* Status de Deslocamento / Resgate */}
                      {item.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO' && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-700 text-white px-2.5 py-0.5 text-[11px] font-extrabold">
                          <Siren className="h-3 w-3" />
                          A CAMINHO (Preparar Box)
                        </span>
                      )}
                      {item.modalidade_emergencia === 'RESGATE_SOLICITADO' && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-400 text-slate-950 px-2.5 py-0.5 text-[11px] font-extrabold">
                          <Ambulance className="h-3 w-3" />
                          RESGATE GPS SOLICITADO
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                      <span className="inline-flex items-center gap-1 font-medium text-slate-800">
                        <UserCheck className="h-3.5 w-3.5 text-teal-600" />
                        Tutor: {item.tutor_nome}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Phone className="h-3.5 w-3.5 text-slate-400" />
                        {formatarTelefone(item.tutor_telefone)}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Stethoscope className="h-3.5 w-3.5 text-teal-600" />
                        {item.medico.nome}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        Horário: {formatarHora(item.agendada_para)}
                      </span>
                      <span
                        className={classes(
                          'rounded-md px-2 py-0.5 text-[11px] font-bold uppercase',
                          item.status === 'em_andamento'
                            ? 'bg-teal-100 text-teal-800'
                            : item.status === 'finalizada'
                              ? 'bg-emerald-100 text-emerald-800'
                              : item.status === 'cancelada'
                                ? 'bg-slate-200 text-slate-600'
                                : 'bg-blue-50 text-blue-800',
                        )}
                      >
                        {item.status.replace('_', ' ')}
                      </span>
                    </div>
                  </div>

                  {/* Ações Rápidas da Recepção */}
                  <div className="flex flex-wrap items-center gap-2">
                    {item.maps_url_tutor && (
                      <a
                        href={item.maps_url_tutor}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 px-3 py-2 text-xs font-extrabold shadow-sm"
                      >
                        <MapPin className="h-3.5 w-3.5" />
                        <span>Abrir GPS no Maps</span>
                      </a>
                    )}

                    <a
                      href={item.whatsapp_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-2 text-xs font-bold shadow-sm"
                    >
                      <MessageCircle className="h-3.5 w-3.5" />
                      <span>Enviar Link no WhatsApp</span>
                    </a>

                    <a
                      href={urlSimulador}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-xl border border-teal-600 bg-teal-50 hover:bg-teal-100 text-teal-900 px-3 py-2 text-xs font-bold"
                    >
                      <Smartphone className="h-3.5 w-3.5" />
                      <span>Simular Celular do Tutor</span>
                    </a>

                    {item.status !== 'finalizada' && item.status !== 'cancelada' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleRenovarLink(item.id_consulta)}
                          title="Gerar novo link (invalida o anterior)"
                          className="rounded-xl border border-slate-200 hover:bg-slate-100 px-2.5 py-2 text-xs font-semibold text-slate-600 cursor-pointer"
                        >
                          Novo Link
                        </button>
                        <button
                          type="button"
                          onClick={() => handleCancelarConsulta(item.id_consulta)}
                          title="Cancelar consulta"
                          className="rounded-xl border border-red-200 hover:bg-red-50 px-2.5 py-2 text-xs font-semibold text-red-600 cursor-pointer"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </article>
            )
          })
        )}
      </section>

      {/* =====================================================================
          MODAL ÁGIL DE NOVO AGENDAMENTO (COM BUSCA /clinicas/me/tutores)
         ===================================================================== */}
      {modalAberto && (
        <div className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 my-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  Novo Agendamento Rápido &amp; Link de Pré-Triagem
                </h2>
                <p className="text-xs text-slate-500">
                  Busque um tutor cadastrado na clínica ou preencha os dados para gerar o link do
                  WhatsApp.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModalAberto(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {recemAgendada ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 flex items-start gap-3">
                  <CheckCircle2 className="h-6 w-6 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-xs">
                    <div className="text-sm font-extrabold text-emerald-950">
                      Consulta agendada para {recemAgendada.pet_nome}!
                    </div>
                    <p className="text-emerald-800">
                      Envie agora o link único para <strong>{recemAgendada.tutor_nome}</strong> ou
                      abra o simulador mobile para demonstrar a jornada do tutor.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <a
                    href={recemAgendada.whatsapp_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 hover:bg-emerald-500 py-3.5 px-4 text-xs font-extrabold text-white shadow"
                  >
                    <MessageCircle className="h-4 w-4" />
                    <span>Enviar Link no WhatsApp (wa.me)</span>
                  </a>
                  <a
                    href={linkTutorLocal(recemAgendada.link_triagem)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 rounded-2xl bg-teal-700 hover:bg-teal-600 py-3.5 px-4 text-xs font-extrabold text-white shadow"
                  >
                    <Smartphone className="h-4 w-4" />
                    <span>Simular Celular do Tutor (/t/:token)</span>
                  </a>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setModalAberto(false)}
                    className="rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white cursor-pointer"
                  >
                    Concluir
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCriarAgendamento} className="space-y-4">
                {/* Autocompletar Tutor/Pet Existente */}
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 space-y-2">
                  <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
                    <Search className="h-3.5 w-3.5 text-teal-600" />
                    <span>Buscar Tutor/Pet já cadastrado na clínica (opcional)</span>
                  </label>
                  <input
                    type="text"
                    value={buscaTutor}
                    onChange={(e) => setBuscaTutor(e.target.value)}
                    placeholder="Digite parte do nome ou telefone do tutor..."
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs"
                  />
                  {tutoresEncontrados.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1 max-h-28 overflow-y-auto">
                      {tutoresEncontrados.map((t) =>
                        t.pets.map((p) => (
                          <button
                            key={`${t.telefone}-${p.nome}`}
                            type="button"
                            onClick={() => selecionarTutorPet(t, p)}
                            className="rounded-lg border border-teal-300 bg-white hover:bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-900 cursor-pointer"
                          >
                            {p.nome} ({p.especie}) — {t.nome}
                          </button>
                        )),
                      )}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-1">
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Médico Veterinário
                    </label>
                    <select
                      value={idMedicoNovo}
                      onChange={(e) => setIdMedicoNovo(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    >
                      {medicos.map((m) => (
                        <option key={m.id_medico} value={m.id_medico}>
                          {m.nome}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="sm:col-span-1">
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Nome do Tutor
                    </label>
                    <input
                      type="text"
                      required
                      value={tutorNome}
                      onChange={(e) => setTutorNome(e.target.value)}
                      placeholder="Ex: Carlos Eduardo"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                  <div className="sm:col-span-1">
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      WhatsApp do Tutor (DDD+Número)
                    </label>
                    <input
                      type="text"
                      required
                      value={tutorTelefone}
                      onChange={(e) => setTutorTelefone(e.target.value)}
                      placeholder="Ex: (62) 99999-8888"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Nome do Pet
                    </label>
                    <input
                      type="text"
                      required
                      value={petNome}
                      onChange={(e) => setPetNome(e.target.value)}
                      placeholder="Ex: Thor"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Espécie</label>
                    <select
                      value={petEspecie}
                      onChange={(e) => setPetEspecie(e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    >
                      <option>Cão</option>
                      <option>Gato</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Raça</label>
                    <input
                      type="text"
                      value={petRaca}
                      onChange={(e) => setPetRaca(e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Idade</label>
                    <input
                      type="text"
                      value={petIdade}
                      onChange={(e) => setPetIdade(e.target.value)}
                      placeholder="Ex: 4 anos"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Sexo</label>
                    <select
                      value={petSexo}
                      onChange={(e) => setPetSexo(e.target.value as typeof petSexo)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    >
                      <option>Macho</option>
                      <option>Fêmea</option>
                      <option>Não informado</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Peso (kg)
                    </label>
                    <input
                      type="text"
                      value={petPesoKg}
                      onChange={(e) => setPetPesoKg(e.target.value)}
                      placeholder="Ex: 12.5"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Porte</label>
                    <select
                      value={petPorte}
                      onChange={(e) => setPetPorte(e.target.value as typeof petPorte)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    >
                      <option value="">Não informado</option>
                      <option value="Mini">Mini</option>
                      <option value="Pequeno">Pequeno</option>
                      <option value="Médio">Médio</option>
                      <option value="Grande">Grande</option>
                      <option value="Gigante">Gigante</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Status Reprodutivo
                    </label>
                    <select
                      value={petStatusReprodutivo}
                      onChange={(e) =>
                        setPetStatusReprodutivo(e.target.value as typeof petStatusReprodutivo)
                      }
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
                    >
                      <option value="">Não informado</option>
                      <option value="Castrado">Castrado</option>
                      <option value="Inteiro">Inteiro</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setModalAberto(false)}
                    className="rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={salvandoAgendamento}
                    className="rounded-xl bg-teal-700 hover:bg-teal-600 disabled:opacity-50 px-5 py-2.5 text-xs font-extrabold text-white shadow cursor-pointer"
                  >
                    {salvandoAgendamento ? 'Agendando...' : 'Agendar e Gerar Link Único'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
