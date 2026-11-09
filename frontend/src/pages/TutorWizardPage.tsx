import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Ambulance,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  HeartPulse,
  MapPin,
  MessageCircle,
  Navigation,
  Pill,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
} from 'lucide-react'
import { api } from '../lib/api'
import { assinatura, avaliarGatilhos, ROTULO_CATEGORIA } from '../lib/emergencia'
import { classes, descricaoPet } from '../lib/format'
import type {
  AcionarEmergenciaIn,
  AcionarEmergenciaOut,
  ModalidadeEmergencia,
  ResultadoTutor,
  SintomaPublico,
  TriagemContexto,
  TriagemSubmissao,
  TriagemSubmissaoOut,
} from '../types'

export function TutorWizardPage() {
  const { token = '' } = useParams<{ token: string }>()

  const [ctx, setCtx] = useState<TriagemContexto | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erroFatal, setErroFatal] = useState<string | null>(null)

  // Controle de passos: 1=Termo LGPD, 2=Manejo Preventivo, 3=Sintomas & Medicações, 4=Relato & Envio, 5=Concluído
  const [passo, setPasso] = useState<1 | 2 | 3 | 4 | 5>(1)

  // Passo 1
  const [aceiteTermo, setAceiteTermo] = useState(false)

  // Passo 2 — Manejo Preventivo Veterinário
  const [ambiente, setAmbiente] = useState('Apartamento')
  const [alimentacao, setAlimentacao] = useState('Ração seca super premium')
  const [vacinaPolivalente, setVacinaPolivalente] = useState('Em dia (V8/V10 ou V4/V5)')
  const [vacinaAntirrabica, setVacinaAntirrabica] = useState('Em dia')
  const [vermifugoStatus, setVermifugoStatus] = useState('Em dia (últimos 3 a 6 meses)')
  const [ectoparasitas, setEctoparasitas] = useState('Em dia (antipulgas/carrapatos)')
  const [acessoRua, setAcessoRua] = useState('Sem acesso à rua (domiciliado)')
  const [contactantes, setContactantes] = useState('Nenhum outro animal na casa')

  // Passo 3 — Sintomas, Medicação (RN-002/RN-003) e Bioindicadores
  const [sintomasMarcados, setSintomasMarcados] = useState<Set<number>>(new Set())
  const [medicamentoContinuo, setMedicamentoContinuo] = useState('')
  const [aspectoUrinaFezes, setAspectoUrinaFezes] = useState('Urina e fezes normais')
  const [alteracaoPesoApetite, setAlteracaoPesoApetite] = useState('Apetite e peso normais')
  const [ingestaoHidrica, setIngestaoHidrica] = useState('Bebe água normalmente')

  // Passo 4 — Relato livre e evolução
  const [tempoEvolucao, setTempoEvolucao] = useState('Há cerca de 24 horas')
  const [relatoLivre, setRelatoLivre] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erroForm, setErroForm] = useState<string | null>(null)

  // Passo 5 — Resultado pós-submissão
  const [submissaoOut, setSubmissaoOut] = useState<TriagemSubmissaoOut | null>(null)
  const [resultadoIA, setResultadoIA] = useState<ResultadoTutor | null>(null)

  // Disjuntor RN-001 v2.0 (Modal Vermelho de Intercepção Imediata)
  const [modalEmergenciaAberto, setModalEmergenciaAberto] = useState(false)
  const [alertaExibidoEm, setAlertaExibidoEm] = useState<string | null>(null)
  const [cienteRiscoMorte, setCienteRiscoMorte] = useState(false)
  const [enderecoManual, setEnderecoManual] = useState('')
  const [capturandoGps, setCapturandoGps] = useState(false)
  const [acionandoModalidade, setAcionandoModalidade] = useState<ModalidadeEmergencia | null>(null)
  const [emergenciaRegistrada, setEmergenciaRegistrada] = useState<AcionarEmergenciaOut | null>(null)
  const [erroEmergencia, setErroEmergencia] = useState<string | null>(null)
  const ultimaAssinaturaRef = useRef<string>('')

  // Carrega contexto inicial do link
  useEffect(() => {
    let cancelado = false
    async function carregar() {
      setCarregando(true)
      setErroFatal(null)
      try {
        const dados = await api<TriagemContexto>(`/publico/triagem/${token}`, { auth: false })
        if (cancelado) return
        setCtx(dados)
        if (dados.estado === 'preenchida') {
          setPasso(5)
        }
      } catch (err) {
        if (!cancelado) setErroFatal((err as Error).message)
      } finally {
        if (!cancelado) setCarregando(false)
      }
    }
    if (token) carregar()
    return () => {
      cancelado = true
    }
  }, [token])

  // Avalia gatilhos determinísticos em tempo real (sintomas de urgência + palavras críticas no relato)
  const gatilhos = useMemo(() => {
    if (!ctx) return { categorias: [], motivos: [], ativo: false }
    return avaliarGatilhos(
      ctx.sintomas,
      sintomasMarcados,
      relatoLivre,
      ctx.emergencia.gatilhos_texto,
    )
  }, [ctx, sintomasMarcados, relatoLivre])

  // Abre automaticamente o Modal de Intercepção sempre que uma nova categoria crítica surgir
  useEffect(() => {
    const sig = assinatura(gatilhos)
    if (gatilhos.ativo && sig !== ultimaAssinaturaRef.current) {
      ultimaAssinaturaRef.current = sig
      if (!alertaExibidoEm) {
        setAlertaExibidoEm(new Date().toISOString())
      }
      setModalEmergenciaAberto(true)
    } else if (!gatilhos.ativo) {
      ultimaAssinaturaRef.current = ''
    }
  }, [gatilhos, alertaExibidoEm])

  // Polling do resultado da IA quando no passo 5
  useEffect(() => {
    if (passo !== 5 || !token) return
    let ativo = true
    let timer: number | undefined

    async function consultarResultado() {
      try {
        const res = await api<ResultadoTutor>(`/publico/triagem/${token}/resultado`, {
          auth: false,
        })
        if (!ativo) return
        setResultadoIA(res)
        if (res.status_ia === 'pendente') {
          timer = window.setTimeout(consultarResultado, 2500)
        }
      } catch {
        // Ignora silenciosamente se ainda não processou
      }
    }
    consultarResultado()
    return () => {
      ativo = false
      if (timer) window.clearTimeout(timer)
    }
  }, [passo, token])

  // Agrupamento de sintomas por categoria anatômica (Emergência no topo)
  const sintomasPorCategoria = useMemo(() => {
    if (!ctx) return []
    const mapa = new Map<string, SintomaPublico[]>()
    for (const s of ctx.sintomas) {
      const lista = mapa.get(s.categoria) ?? []
      lista.push(s)
      mapa.set(s.categoria, lista)
    }
    const entradas = Array.from(mapa.entries())
    entradas.sort(([a], [b]) => {
      if (a === 'Emergência') return -1
      if (b === 'Emergência') return 1
      return a.localeCompare(b, 'pt-BR')
    })
    return entradas
  }, [ctx])

  function alternarSintoma(id: number) {
    setSintomasMarcados((prev) => {
      const novo = new Set(prev)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  function capturarGeolocalizacao(): Promise<string | null> {
    return new Promise((resolve) => {
      if (!('geolocation' in navigator)) {
        resolve(null)
        return
      }
      setCapturandoGps(true)
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCapturandoGps(false)
          const coords = `${pos.coords.latitude.toFixed(6)},${pos.coords.longitude.toFixed(6)}`
          setEnderecoManual(coords)
          resolve(coords)
        },
        () => {
          setCapturandoGps(false)
          resolve(null)
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 },
      )
    })
  }

  async function acionarEmergenciaAgora(modalidade: ModalidadeEmergencia) {
    if (!ctx) return
    setErroEmergencia(null)

    if (!cienteRiscoMorte) {
      setErroEmergencia(
        'Por favor, marque a confirmação de ciência de risco imediato antes de acionar a equipe.',
      )
      return
    }

    let loc = enderecoManual.trim() || null
    if (modalidade === 'RESGATE_SOLICITADO' && !loc) {
      loc = await capturarGeolocalizacao()
      if (!loc || loc.length < 5) {
        setErroEmergencia(
          'Não foi possível obter seu GPS automaticamente. Digite seu endereço ou localização no campo abaixo para enviar o veículo de resgate.',
        )
        return
      }
    }

    setAcionandoModalidade(modalidade)
    try {
      const payload: AcionarEmergenciaIn = {
        modalidade,
        localizacao_gps_tutor: loc,
        ciente_risco_morte: cienteRiscoMorte,
        alerta_critico_exibido_em: alertaExibidoEm ?? new Date().toISOString(),
        categorias_emergencia: gatilhos.categorias.length ? gatilhos.categorias : ['GERAL'],
      }
      const res = await api<AcionarEmergenciaOut>(
        `/publico/triagem/${token}/acionar-emergencia`,
        {
          method: 'POST',
          body: payload,
          auth: false,
        },
      )
      setEmergenciaRegistrada(res)

      if (modalidade === 'RESGATE_SOLICITADO' && res.whatsapp_resgate_url) {
        window.open(res.whatsapp_resgate_url, '_blank', 'noopener,noreferrer')
      }
    } catch (err) {
      setErroEmergencia((err as Error).message)
    } finally {
      setAcionandoModalidade(null)
    }
  }

  async function handleSubmeterTriagem(e: React.FormEvent) {
    e.preventDefault()
    if (!ctx) return
    setErroForm(null)

    if (medicamentoContinuo.trim().length < 2) {
      setErroForm('Informe os medicamentos em uso ou clique em "Nenhum medicamento".')
      setPasso(3)
      return
    }
    if (relatoLivre.trim().length < 10) {
      setErroForm('Descreva com mais detalhes o que está acontecendo (mínimo de 10 caracteres).')
      return
    }

    const vacinacaoEmDia =
      vacinaPolivalente.startsWith('Em dia') && vacinaAntirrabica.startsWith('Em dia')
    const vermifugoEmDia = vermifugoStatus.startsWith('Em dia')
    const convivioOutros = !contactantes.startsWith('Nenhum')
    const manejoPreventivo = [
      `Polivalente (${ctx.pet.especie === 'Gato' ? 'V4/V5' : 'V8/V10'}): ${vacinaPolivalente}`,
      `Antirrábica: ${vacinaAntirrabica}`,
      `Vermífugo: ${vermifugoStatus}`,
      `Ectoparasitas: ${ectoparasitas}`,
      `Acesso à rua: ${acessoRua}`,
      `Contactantes: ${contactantes}`,
    ].join(' · ')

    const payload: TriagemSubmissao = {
      aceite_termo: aceiteTermo,
      ambiente,
      alimentacao,
      vacinacao_em_dia: vacinacaoEmDia,
      vermifugo_em_dia: vermifugoEmDia,
      convivio_outros_animais: convivioOutros,
      manejo_preventivo: manejoPreventivo,
      medicamento_continuo: medicamentoContinuo.trim(),
      aspecto_urina_fezes: aspectoUrinaFezes.trim(),
      alteracao_peso_apetite: alteracaoPesoApetite.trim(),
      ingestao_hidrica: ingestaoHidrica.trim(),
      tempo_evolucao: tempoEvolucao.trim(),
      relato_livre_tutor: relatoLivre.trim(),
      sintoma_ids: Array.from(sintomasMarcados),
      ciente_risco_morte: cienteRiscoMorte,
      alerta_critico_exibido_em: alertaExibidoEm,
      modalidade_emergencia: emergenciaRegistrada?.modalidade_emergencia ?? null,
      localizacao_gps_tutor:
        emergenciaRegistrada?.localizacao_gps_tutor ?? (enderecoManual.trim() || null),
    }

    setEnviando(true)
    try {
      const resp = await api<TriagemSubmissaoOut>(`/publico/triagem/${token}`, {
        method: 'POST',
        body: payload,
        auth: false,
      })
      setSubmissaoOut(resp)
      setPasso(5)
    } catch (err) {
      setErroForm((err as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="h-12 w-12 rounded-2xl bg-teal-500/20 border border-teal-400/40 flex items-center justify-center animate-pulse">
            <Activity className="h-6 w-6 text-teal-300" />
          </div>
          <p className="text-sm font-medium text-slate-300">
            Carregando Triagem Pré-Consulta segura...
          </p>
        </div>
      </div>
    )
  }

  if (erroFatal || !ctx) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
        <div className="max-w-md w-full rounded-3xl border border-red-500/40 bg-slate-900 p-6 text-center space-y-4">
          <AlertOctagon className="h-12 w-12 text-red-400 mx-auto" />
          <h1 className="text-lg font-bold">Link indisponível</h1>
          <p className="text-xs text-slate-300 leading-relaxed">
            {erroFatal ?? 'Não foi possível localizar esta Triagem Pré-Consulta.'}
          </p>
          <a
            href="https://www.google.com/maps/search/Hospital+Veterinario+24h/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 w-full rounded-xl bg-red-600 hover:bg-red-500 px-4 py-3 text-xs font-bold text-white transition"
          >
            <MapPin className="h-4 w-4" />
            Buscar Hospital Veterinário 24h no Google Maps
          </a>
        </div>
      </div>
    )
  }

  if (ctx.estado === 'cancelada' || ctx.estado === 'expirada') {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
        <div className="max-w-md w-full rounded-3xl border border-amber-500/40 bg-slate-900 p-6 text-center space-y-4">
          <AlertTriangle className="h-12 w-12 text-amber-400 mx-auto" />
          <h1 className="text-lg font-bold">
            {ctx.estado === 'cancelada' ? 'Consulta cancelada' : 'Link de triagem expirado'}
          </h1>
          <p className="text-xs text-slate-300 leading-relaxed">
            Solicite um novo link à recepção de <strong>{ctx.clinica_nome}</strong>. Em caso de
            emergência, dirija-se imediatamente ao pronto-socorro veterinário.
          </p>
          <a
            href={ctx.emergencia.url_hospital_24h}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 w-full rounded-xl bg-red-600 hover:bg-red-500 px-4 py-3 text-xs font-bold text-white transition"
          >
            <MapPin className="h-4 w-4" />
            Buscar Hospital Veterinário 24h Mais Próximo
          </a>
        </div>
      </div>
    )
  }

  const clinicaFechadaAgora =
    !ctx.emergencia.atendimento_24h && !ctx.emergencia.clinica_aberta_agora
  const categoriasAtivas = gatilhos.categorias.length ? gatilhos.categorias : ['GERAL']

  return (
    <div className="min-h-screen bg-slate-100 pb-16">
      {/* Cabeçalho Mobile VetTech */}
      <header className="bg-gradient-to-r from-slate-900 via-teal-950 to-slate-900 text-white px-4 py-4 shadow-md">
        <div className="mx-auto max-w-xl flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500 text-slate-950 font-extrabold shadow">
              <HeartPulse className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-semibold text-teal-300 uppercase tracking-wider">
                {ctx.clinica_nome}
              </div>
              <h1 className="text-base font-extrabold tracking-tight">
                Triagem Pré-Consulta · {ctx.pet.nome}
              </h1>
              <p className="text-[11px] text-slate-300">{descricaoPet(ctx.pet)}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              if (!alertaExibidoEm) setAlertaExibidoEm(new Date().toISOString())
              setModalEmergenciaAberto(true)
            }}
            className="shrink-0 flex items-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-500 px-3 py-2 text-xs font-extrabold text-white shadow-lg cursor-pointer emergency-pulse"
          >
            <Siren className="h-4 w-4" />
            <span>Emergência</span>
          </button>
        </div>
      </header>

      {/* Banner Persistente se Emergência Já Acionada ou Gatilho Ativo */}
      {(gatilhos.ativo || emergenciaRegistrada || ctx.modalidade_emergencia) && (
        <div className="bg-red-700 text-white px-4 py-3 shadow-md">
          <div className="mx-auto max-w-xl flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-bold">
              <Siren className="h-4 w-4 shrink-0 animate-bounce" />
              <span>
                {emergenciaRegistrada?.modalidade_emergencia === 'RESGATE_SOLICITADO' ||
                ctx.modalidade_emergencia === 'RESGATE_SOLICITADO'
                  ? '🚑 VEÍCULO DE RESGATE SOLICITADO — Equipe de plantão acionada!'
                  : emergenciaRegistrada?.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO' ||
                      ctx.modalidade_emergencia === 'EMERGENCIA_A_CAMINHO'
                    ? '🚨 EMERGÊNCIA EM DESLOCAMENTO — Box de Emergência avisado!'
                    : `⚠️ Sinais críticos detectados (${gatilhos.motivos.length}) — Atenção imediata!`}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setModalEmergenciaAberto(true)}
              className="rounded-lg bg-white text-red-800 px-2.5 py-1 text-xs font-extrabold shadow cursor-pointer"
            >
              Abrir Painel de Emergência
            </button>
          </div>
        </div>
      )}

      {/* Barra de Progresso dos 4 Passos */}
      {passo < 5 && (
        <div className="mx-auto max-w-xl px-4 pt-4">
          <div className="grid grid-cols-4 gap-2">
            {[
              { n: 1, t: '1. Termo LGPD' },
              { n: 2, t: '2. Preventivo' },
              { n: 3, t: '3. Sintomas' },
              { n: 4, t: '4. Relato' },
            ].map((item) => (
              <div
                key={item.n}
                className={classes(
                  'rounded-xl px-2 py-1.5 text-center text-[11px] font-bold border transition',
                  passo === item.n
                    ? 'bg-teal-700 text-white border-teal-700 shadow-sm'
                    : passo > item.n
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                      : 'bg-white text-slate-400 border-slate-200',
                )}
              >
                {item.t}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conteúdo Principal do Wizard */}
      <main className="mx-auto max-w-xl px-4 pt-4">
        {erroForm && (
          <div className="mb-4 rounded-2xl border border-red-300 bg-red-50 p-3.5 text-xs font-medium text-red-800 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
            <span>{erroForm}</span>
          </div>
        )}

        {/* PASSO 1 — TERMO LGPD E RESPONSABILIDADE DE EMERGÊNCIA */}
        {passo === 1 && (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-5">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700 border border-teal-200">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-extrabold text-slate-900">
                  Olá, {ctx.tutor_primeiro_nome}! Vamos preparar o atendimento de {ctx.pet.nome}
                </h2>
                <p className="mt-0.5 text-xs text-slate-600">
                  Leva menos de 2 minutos e permite que o médico veterinário receba o Briefing
                  Clínico Prévio antes mesmo de vocês entrarem no consultório.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-red-200 bg-red-50/80 p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-extrabold text-red-800 uppercase tracking-wide">
                <AlertOctagon className="h-4 w-4 text-red-600" />
                <span>Aviso Importante de Emergência (RN-001 v2.0)</span>
              </div>
              <p className="text-xs text-red-900 leading-relaxed">
                Se <strong>{ctx.pet.nome}</strong> estiver com falta de ar, língua roxa, convulsão,
                sangramento intenso, atropelamento ou suspeita de envenenamento,{' '}
                <strong>não aguarde</strong>: clique no botão vermelho <strong>Emergência</strong>{' '}
                no topo para acionar o Box de Emergência ou solicitar o veículo de resgate.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 leading-relaxed">
              <p className="font-semibold text-slate-900 mb-1">
                Termo de Ciência e Consentimento LGPD (Lei 13.709/2018):
              </p>
              <p>{ctx.texto_termo}</p>
            </div>

            <label className="flex items-start gap-3 rounded-2xl border border-teal-200 bg-teal-50/50 p-3.5 cursor-pointer">
              <input
                type="checkbox"
                checked={aceiteTermo}
                onChange={(e) => setAceiteTermo(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
              />
              <span className="text-xs font-semibold text-slate-800">
                Li e aceito o termo de consentimento LGPD e compreendo que esta pré-triagem não
                substitui atendimento emergencial imediato.
              </span>
            </label>

            <button
              type="button"
              disabled={!aceiteTermo}
              onClick={() => setPasso(2)}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-teal-700 hover:bg-teal-600 disabled:opacity-40 py-3.5 px-4 text-sm font-extrabold text-white shadow-md transition cursor-pointer"
            >
              <span>Continuar para Manejo Preventivo</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </section>
        )}

        {/* PASSO 2 — MANEJO PREVENTIVO VETERINÁRIO */}
        {passo === 2 && (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <div>
              <h2 className="text-base font-extrabold text-slate-900">
                Passo 2 · Manejo Preventivo e Ambiente
              </h2>
              <p className="text-xs text-slate-600">
                Informações sobre vacinas, vermífugo, controle de pulgas/carrapatos e rotina de{' '}
                <strong>{ctx.pet.nome}</strong>.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Vacina Polivalente ({ctx.pet.especie === 'Gato' ? 'V4 / V5' : 'V8 / V10'})
                </label>
                <select
                  value={vacinaPolivalente}
                  onChange={(e) => setVacinaPolivalente(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-xs font-medium text-slate-900"
                >
                  <option>Em dia (V8/V10 ou V4/V5)</option>
                  <option>Atrasada há mais de 1 ano</option>
                  <option>Filhote em esquema vacinal incompleto</option>
                  <option>Nunca vacinado / Não sei informar</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Vacina Antirrábica
                </label>
                <select
                  value={vacinaAntirrabica}
                  onChange={(e) => setVacinaAntirrabica(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-xs font-medium text-slate-900"
                >
                  <option>Em dia</option>
                  <option>Atrasada</option>
                  <option>Ainda não tomou / Não sei</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Vermifugação</label>
                <select
                  value={vermifugoStatus}
                  onChange={(e) => setVermifugoStatus(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-xs font-medium text-slate-900"
                >
                  <option>Em dia (últimos 3 a 6 meses)</option>
                  <option>Atrasado (mais de 6 meses)</option>
                  <option>Nunca tomou / Não lembro</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Controle de Ectoparasitas (Pulgas/Carrapatos)
                </label>
                <select
                  value={ectoparasitas}
                  onChange={(e) => setEctoparasitas(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-xs font-medium text-slate-900"
                >
                  <option>Em dia (antipulgas/carrapatos)</option>
                  <option>Atrasado / Sem proteção recente</option>
                  <option>Presença visível de pulgas ou carrapatos hoje</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Ambiente onde vive
                </label>
                <input
                  type="text"
                  value={ambiente}
                  onChange={(e) => setAmbiente(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                  placeholder="Ex: Apartamento telado, Casa com quintal"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Acesso à rua</label>
                <select
                  value={acessoRua}
                  onChange={(e) => setAcessoRua(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-xs font-medium text-slate-900"
                >
                  <option>Sem acesso à rua (domiciliado)</option>
                  <option>Passeios na guia com supervisão</option>
                  <option>Acesso livre à rua / quintal aberto</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Convívio com outros animais (Contactantes)
              </label>
              <input
                type="text"
                value={contactantes}
                onChange={(e) => setContactantes(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                placeholder="Ex: Nenhum outro animal / Convive com 2 cães saudáveis"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Alimentação habitual
              </label>
              <input
                type="text"
                value={alimentacao}
                onChange={(e) => setAlimentacao(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                placeholder="Ex: Ração seca super premium, sachê úmido, alimentação natural"
              />
            </div>

            <div className="flex items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={() => setPasso(1)}
                className="flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Voltar</span>
              </button>
              <button
                type="button"
                onClick={() => setPasso(3)}
                className="flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-600 px-5 py-2.5 text-xs font-extrabold text-white shadow cursor-pointer"
              >
                <span>Avançar para Sintomas</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* PASSO 3 — CHECKLIST DE SINTOMAS + MEDICAÇÕES 48H (RN-003) + BIOINDICADORES */}
        {passo === 3 && (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-5">
            <div>
              <h2 className="text-base font-extrabold text-slate-900">
                Passo 3 · Checklist de Sinais e Segurança Farmacológica
              </h2>
              <p className="text-xs text-slate-600">
                Marque os sinais observados em <strong>{ctx.pet.nome}</strong>. Sinais críticos
                acionam automaticamente o protocolo de emergência.
              </p>
            </div>

            <div className="space-y-4">
              {sintomasPorCategoria.map(([categoria, lista]) => {
                const ehEmergencia = categoria === 'Emergência'
                return (
                  <div
                    key={categoria}
                    className={classes(
                      'rounded-2xl border p-3.5',
                      ehEmergencia
                        ? 'border-red-300 bg-red-50/60'
                        : 'border-slate-200 bg-slate-50/60',
                    )}
                  >
                    <div className="flex items-center justify-between mb-2.5">
                      <span
                        className={classes(
                          'text-xs font-extrabold uppercase tracking-wider flex items-center gap-1.5',
                          ehEmergencia ? 'text-red-800' : 'text-slate-700',
                        )}
                      >
                        {ehEmergencia && <Siren className="h-4 w-4 text-red-600" />}
                        {ehEmergencia
                          ? 'Sinais Críticos de Emergência (RN-001 v2.0)'
                          : categoria}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 gap-2">
                      {lista.map((s) => {
                        const marcado = sintomasMarcados.has(s.id_sintoma)
                        return (
                          <label
                            key={s.id_sintoma}
                            className={classes(
                              'flex items-start gap-2.5 rounded-xl border p-2.5 text-xs cursor-pointer transition',
                              marcado
                                ? s.alerta_urgencia
                                  ? 'border-red-600 bg-red-600 text-white font-bold shadow-sm'
                                  : 'border-teal-600 bg-teal-50 text-teal-950 font-semibold'
                                : 'border-slate-200 bg-white text-slate-800 hover:border-slate-300',
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={marcado}
                              onChange={() => alternarSintoma(s.id_sintoma)}
                              className="mt-0.5 h-4 w-4 rounded"
                            />
                            <span className="leading-snug">{s.nome_sintoma}</span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Campo Obrigatório RN-002 / RN-003: Medicações Contínuas / Últimas 48h */}
            <div className="rounded-2xl border-2 border-amber-300 bg-amber-50/70 p-4 space-y-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <label className="flex items-center gap-1.5 text-xs font-extrabold text-amber-950">
                  <Pill className="h-4 w-4 text-amber-700" />
                  <span>
                    Medicações Contínuas ou Administradas nas Últimas 48h (Obrigatório)
                  </span>
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setMedicamentoContinuo(
                      'Nenhum medicamento contínuo; nada administrado nas últimas 48h',
                    )
                  }
                  className="rounded-lg bg-amber-200/80 hover:bg-amber-300 px-2.5 py-1 text-[11px] font-bold text-amber-950 cursor-pointer"
                >
                  Preencher: &quot;Nenhum medicamento&quot;
                </button>
              </div>
              <input
                type="text"
                required
                value={medicamentoContinuo}
                onChange={(e) => setMedicamentoContinuo(e.target.value)}
                placeholder="Informe nome, dose e horário de qualquer remédio dado em casa (ou clique em Nenhum)"
                className="w-full rounded-xl border border-amber-400 bg-white px-3 py-2.5 text-xs text-slate-900"
              />
            </div>

            {/* Bioindicadores */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Urina e Fezes
                </label>
                <input
                  type="text"
                  value={aspectoUrinaFezes}
                  onChange={(e) => setAspectoUrinaFezes(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Apetite e Peso
                </label>
                <input
                  type="text"
                  value={alteracaoPesoApetite}
                  onChange={(e) => setAlteracaoPesoApetite(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Ingestão de Água
                </label>
                <input
                  type="text"
                  value={ingestaoHidrica}
                  onChange={(e) => setIngestaoHidrica(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900"
                />
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={() => setPasso(2)}
                className="flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Voltar</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (medicamentoContinuo.trim().length < 2) {
                    setErroForm(
                      'Por segurança farmacológica, informe as medicações das últimas 48h ou clique em "Nenhum medicamento".',
                    )
                    return
                  }
                  setErroForm(null)
                  setPasso(4)
                }}
                className="flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-600 px-5 py-2.5 text-xs font-extrabold text-white shadow cursor-pointer"
              >
                <span>Avançar para Relato Livre</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* PASSO 4 — RELATO LIVRE COM DETECÇÃO DE PALAVRAS CRÍTICAS E SUBMISSÃO */}
        {passo === 4 && (
          <form
            onSubmit={handleSubmeterTriagem}
            className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-4"
          >
            <div>
              <h2 className="text-base font-extrabold text-slate-900">
                Passo 4 · Conte com suas palavras o que está acontecendo
              </h2>
              <p className="text-xs text-slate-600">
                Descreva quando começou, como evoluiu e qualquer detalhe que possa ajudar o
                veterinário.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Há quanto tempo começou? (Tempo de evolução)
              </label>
              <input
                type="text"
                required
                value={tempoEvolucao}
                onChange={(e) => setTempoEvolucao(e.target.value)}
                placeholder="Ex: Começou há 2 horas / Desde ontem à noite / Há 3 dias"
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-xs text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Relato livre do tutor (mínimo 10 caracteres)
              </label>
              <textarea
                rows={5}
                required
                value={relatoLivre}
                onChange={(e) => setRelatoLivre(e.target.value)}
                placeholder="Ex: Ele vomitou espuma amarela duas vezes hoje cedo, está mais quietinho e recusou a ração..."
                className="w-full rounded-2xl border border-slate-300 p-3 text-xs text-slate-900 leading-relaxed"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                Dica: caso digite termos de risco imediato (como &quot;veneno&quot;,
                &quot;chumbinho&quot;, &quot;atropelado&quot;, &quot;sangrando muito&quot;,
                &quot;convulsão&quot;, &quot;não respira&quot; ou &quot;língua roxa&quot;), o
                painel de emergência será aberto automaticamente.
              </p>
            </div>

            <div className="flex items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={() => setPasso(3)}
                className="flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Voltar</span>
              </button>
              <button
                type="submit"
                disabled={enviando}
                className="flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-6 py-3 text-xs font-extrabold text-white shadow-lg cursor-pointer"
              >
                <Sparkles className="h-4 w-4" />
                <span>{enviando ? 'Enviando Triagem...' : 'Enviar Triagem Pré-Consulta'}</span>
              </button>
            </div>
          </form>
        )}

        {/* PASSO 5 — CONFIRMAÇÃO E ALERTA DE SEGURANÇA AO TUTOR */}
        {passo === 5 && (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-5">
            <div className="flex items-start gap-3">
              <div
                className={classes(
                  'flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl',
                  submissaoOut?.urgencia_detectada || resultadoIA?.urgencia_detectada
                    ? 'bg-red-100 text-red-700'
                    : 'bg-emerald-100 text-emerald-700',
                )}
              >
                {submissaoOut?.urgencia_detectada || resultadoIA?.urgencia_detectada ? (
                  <Siren className="h-6 w-6" />
                ) : (
                  <CheckCircle2 className="h-6 w-6" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  Triagem Pré-Consulta Recebida!
                </h2>
                <p className="text-xs text-slate-600">
                  O médico veterinário de <strong>{ctx.clinica_nome}</strong> já recebeu os dados
                  de <strong>{ctx.pet.nome}</strong>.
                </p>
              </div>
            </div>

            {/* Orientação de Segurança ao Tutor */}
            <div
              className={classes(
                'rounded-2xl border p-4 space-y-2',
                submissaoOut?.urgencia_detectada || resultadoIA?.urgencia_detectada
                  ? 'border-red-300 bg-red-50 text-red-950'
                  : 'border-teal-200 bg-teal-50/70 text-teal-950',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-extrabold uppercase tracking-wider">
                  Orientação de Segurança ao Tutor
                </span>
                {resultadoIA?.status_ia === 'pendente' && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-700">
                    <Clock className="h-3.5 w-3.5 animate-spin" />
                    Organizando briefing...
                  </span>
                )}
              </div>
              <p className="text-xs leading-relaxed font-medium">
                {resultadoIA?.alerta_seguranca_tutor ??
                  submissaoOut?.mensagem_para_tutor ??
                  'Aguarde ser chamado para o atendimento. Não administre medicamentos por conta própria.'}
              </p>
            </div>

            {/* Primeiros Socorros Negativos pós-submissão (quando houver urgência) */}
            {Object.keys(
              resultadoIA?.primeiros_socorros_negativos ??
                submissaoOut?.primeiros_socorros_negativos ??
                {},
            ).length > 0 && (
              <div className="rounded-2xl border-2 border-red-500 bg-red-950 text-white p-4 space-y-2.5">
                <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-red-200">
                  <ShieldAlert className="h-4 w-4 text-red-400" />
                  <span>⚠️ O QUE NÃO FAZER AGORA EM CASA</span>
                </div>
                {Object.entries(
                  resultadoIA?.primeiros_socorros_negativos ??
                    submissaoOut?.primeiros_socorros_negativos ??
                    {},
                ).map(([cat, texto]) => (
                  <div key={cat} className="rounded-xl bg-red-900/70 border border-red-700 p-3">
                    <div className="text-[11px] font-bold text-red-200 uppercase">
                      {ROTULO_CATEGORIA[cat] ?? cat}
                    </div>
                    <p className="mt-0.5 text-xs text-white leading-relaxed">{texto}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                onClick={() => setModalEmergenciaAberto(true)}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 px-4 py-3 text-xs font-extrabold text-white shadow cursor-pointer"
              >
                <Siren className="h-4 w-4" />
                <span>Acionar Emergência / Resgate GPS</span>
              </button>
              <a
                href={ctx.emergencia.rota_clinica.google_maps}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 px-4 py-3 text-xs font-bold text-slate-800"
              >
                <Navigation className="h-4 w-4 text-teal-700" />
                <span>Rota no Google Maps</span>
              </a>
            </div>
          </section>
        )}
      </main>

      {/* =====================================================================
          MODAL / PAINEL VERMELHO DE INTERCEPÇÃO IMEDIATA (DISJUNTOR RN-001 v2.0)
         ===================================================================== */}
      {modalEmergenciaAberto && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="w-full max-w-lg rounded-3xl border-2 border-red-500 bg-gradient-to-b from-red-950 via-slate-950 to-slate-950 text-white p-5 sm:p-6 shadow-2xl space-y-4 my-auto">
            {/* Cabeçalho do Disjuntor */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-red-600 text-white shadow-lg emergency-pulse">
                  <Siren className="h-6 w-6" />
                </div>
                <div>
                  <span className="inline-block rounded-full bg-red-500/30 border border-red-400/40 px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-red-200">
                    Disjuntor de Emergência RN-001 v2.0
                  </span>
                  <h2 className="mt-1 text-lg font-extrabold text-white leading-tight">
                    Sinais de Risco Imediato à Vida Detectados!
                  </h2>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalEmergenciaAberto(false)}
                className="rounded-lg border border-red-500/40 bg-red-950/60 px-2.5 py-1 text-xs font-bold text-red-200 hover:bg-red-900 cursor-pointer"
              >
                Fechar
              </button>
            </div>

            {/* Motivos que dispararam o disjuntor */}
            {gatilhos.motivos.length > 0 && (
              <div className="rounded-2xl border border-red-500/40 bg-red-950/60 p-3 text-xs">
                <div className="font-bold text-red-200 mb-1">Gatilhos identificados:</div>
                <ul className="list-disc list-inside space-y-0.5 text-red-100">
                  {gatilhos.motivos.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* a) Card de Primeiros Socorros Negativos ("⚠️ O QUE NÃO FAZER AGORA EM CASA") */}
            <div className="rounded-2xl border-2 border-amber-400 bg-amber-950/80 p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-300">
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                <span>⚠️ O QUE NÃO FAZER AGORA EM CASA</span>
              </div>
              {categoriasAtivas.map((cat) => {
                const instrucao =
                  ctx.emergencia.primeiros_socorros_negativos[cat] ??
                  ctx.emergencia.primeiros_socorros_negativos.GERAL
                return (
                  <div
                    key={cat}
                    className="rounded-xl bg-slate-950/80 border border-amber-500/30 p-3 space-y-1"
                  >
                    <div className="text-[11px] font-extrabold uppercase text-amber-300">
                      {ROTULO_CATEGORIA[cat] ?? cat}
                    </div>
                    <p className="text-xs text-amber-50 leading-relaxed font-medium">
                      {instrucao}
                    </p>
                  </div>
                )
              })}
            </div>

            {/* b) Checkbox de ciência de risco de morte imediato (auditoria jurídica) */}
            <label className="flex items-start gap-3 rounded-2xl border border-red-400/50 bg-red-900/40 p-3.5 cursor-pointer">
              <input
                type="checkbox"
                checked={cienteRiscoMorte}
                onChange={(e) => {
                  setCienteRiscoMorte(e.target.checked)
                  setErroEmergencia(null)
                }}
                className="mt-0.5 h-4 w-4 rounded border-red-300 text-red-600"
              />
              <span className="text-xs font-bold text-red-100 leading-snug">
                Estou ciente de que os sinais relatados indicam risco imediato de morte para{' '}
                <strong>{ctx.pet.nome}</strong> e que o atendimento presencial não pode esperar.
              </span>
            </label>

            {erroEmergencia && (
              <div className="rounded-xl border border-red-400 bg-red-950 p-3 text-xs font-bold text-red-200">
                {erroEmergencia}
              </div>
            )}

            {/* Confirmação quando a emergência já foi registrada no servidor */}
            {emergenciaRegistrada && (
              <div className="rounded-2xl border border-emerald-400 bg-emerald-950/90 p-3.5 space-y-2 text-xs">
                <div className="font-extrabold text-emerald-200 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <span>{emergenciaRegistrada.mensagem_para_tutor}</span>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  <a
                    href={emergenciaRegistrada.rota_clinica.google_maps}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-white text-slate-900 px-3 py-1.5 font-extrabold"
                  >
                    <Navigation className="h-3.5 w-3.5 text-teal-700" />
                    Abrir Rota no Google Maps
                  </a>
                  <a
                    href={emergenciaRegistrada.rota_clinica.waze}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500 text-white px-3 py-1.5 font-extrabold"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Abrir no Waze
                  </a>
                  {emergenciaRegistrada.whatsapp_resgate_url && (
                    <a
                      href={emergenciaRegistrada.whatsapp_resgate_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 text-slate-950 px-3 py-1.5 font-extrabold"
                    >
                      <MessageCircle className="h-3.5 w-3.5" />
                      Enviar Localização no WhatsApp do Plantão
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* c) Botão 1: ESTOU A CAMINHO */}
            <button
              type="button"
              disabled={acionandoModalidade !== null}
              onClick={() => acionarEmergenciaAgora('EMERGENCIA_A_CAMINHO')}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-red-600 hover:bg-red-500 disabled:opacity-50 py-3.5 px-4 text-xs sm:text-sm font-extrabold text-white shadow-lg cursor-pointer transition"
            >
              <Siren className="h-5 w-5 shrink-0" />
              <span>
                {acionandoModalidade === 'EMERGENCIA_A_CAMINHO'
                  ? 'Avisando Equipe de Emergência...'
                  : '🚨 ESTOU A CAMINHO! Avisar Equipe de Emergência Agora'}
              </span>
            </button>

            {/* d) Botão 2: SOLICITAR VEÍCULO DE RESGATE DA CLÍNICA (Enviar Meu GPS) */}
            {ctx.emergencia.possui_veiculo_resgate && (
              <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-3.5 space-y-2.5">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={enderecoManual}
                    onChange={(e) => setEnderecoManual(e.target.value)}
                    placeholder="Coordenadas GPS ou digite seu endereço completo para resgate..."
                    className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-400"
                  />
                  <button
                    type="button"
                    disabled={capturandoGps}
                    onClick={() => capturarGeolocalizacao()}
                    className="shrink-0 rounded-xl border border-teal-500/40 bg-teal-500/20 hover:bg-teal-500/30 px-3 py-2 text-xs font-bold text-teal-200 cursor-pointer"
                  >
                    {capturandoGps ? 'Obtendo GPS...' : 'Usar Meu GPS'}
                  </button>
                </div>

                <button
                  type="button"
                  disabled={acionandoModalidade !== null}
                  onClick={() => acionarEmergenciaAgora('RESGATE_SOLICITADO')}
                  className="w-full flex items-center justify-center gap-2 rounded-2xl bg-amber-500 hover:bg-amber-400 disabled:opacity-50 py-3 px-4 text-xs sm:text-sm font-extrabold text-slate-950 shadow-lg cursor-pointer transition"
                >
                  <Ambulance className="h-5 w-5 shrink-0" />
                  <span>
                    {acionandoModalidade === 'RESGATE_SOLICITADO'
                      ? 'Solicitando Veículo de Resgate...'
                      : '🚑 SOLICITAR VEÍCULO DE RESGATE DA CLÍNICA (Enviar Meu GPS)'}
                  </span>
                </button>
              </div>
            )}

            {/* e) Trava de Clínica Fechada / Redirecionamento 24h */}
            <div className="pt-1 space-y-2">
              {clinicaFechadaAgora && (
                <div className="rounded-xl bg-amber-500/20 border border-amber-400/50 p-2.5 text-center text-xs font-bold text-amber-200">
                  Atenção: esta clínica encerrou o expediente ({ctx.emergencia.horario_fechamento}
                  ). Dirija-se imediatamente a um Hospital Veterinário 24h:
                </div>
              )}
              <a
                href={ctx.emergencia.url_hospital_24h}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-2 rounded-2xl border border-slate-600 bg-slate-800 hover:bg-slate-700 py-3 px-4 text-xs font-bold text-slate-100 transition"
              >
                <MapPin className="h-4 w-4 text-red-400 shrink-0" />
                <span>📍 Buscar Hospital Veterinário 24h Mais Próximo no Google Maps</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
