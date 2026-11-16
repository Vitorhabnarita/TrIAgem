import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  AlertOctagon,
  AlertTriangle,
  Ambulance,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  ExternalLink,
  MapPin,
  MessageCircle,
  Navigation,
  Pill,
  Search,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
} from 'lucide-react'
import { BrandLogo } from '../components/BrandLogo'
import { ClinicAvatar } from '../components/ui'
import { api } from '../lib/api'
import { assinatura, avaliarGatilhos, ROTULO_CATEGORIA } from '../lib/emergencia'
import { classes, descricaoPet, semAcento } from '../lib/format'
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

type Passo = 1 | 2 | 3 | 4 | 5 | 6 | 7

const TITULOS_PASSOS = ['Termo', 'Saúde', 'Rotina', 'Sinais', 'Remédios', 'Relato']

// ---------------------------------------------------------------------------
// Componentes de interface (Touch Cards)
// ---------------------------------------------------------------------------

function Opcoes({
  rotulo,
  opcoes,
  valor,
  onChange,
}: {
  rotulo: string
  opcoes: string[]
  valor: string
  onChange: (v: string) => void
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 text-sm font-semibold text-ink">{rotulo}</legend>
      <div className="grid gap-2">
        {opcoes.map((o) => {
          const ativo = o === valor
          return (
            <button
              key={o}
              type="button"
              onClick={() => onChange(o)}
              aria-pressed={ativo}
              className={classes(
                'flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-left text-sm transition active:scale-[0.99]',
                ativo
                  ? 'border-brand bg-brand-soft font-semibold text-ink ring-2 ring-brand/20'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300',
              )}
            >
              <span
                className={classes(
                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                  ativo ? 'border-brand bg-brand text-white' : 'border-slate-300',
                )}
              >
                {ativo && <Check className="h-3 w-3" strokeWidth={3} />}
              </span>
              {o}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}

function CartaoPasso({
  titulo,
  subtitulo,
  children,
}: {
  titulo: string
  subtitulo?: string
  children: React.ReactNode
}) {
  return (
    <section className="card fade-up space-y-6 p-5 sm:p-7">
      <div>
        <h2 className="text-xl font-extrabold tracking-tight text-ink">{titulo}</h2>
        {subtitulo && <p className="mt-1 text-sm text-ink-soft">{subtitulo}</p>}
      </div>
      {children}
    </section>
  )
}

function Navegacao({
  onVoltar,
  onAvancar,
  rotuloAvancar = 'Continuar',
  desabilitar = false,
}: {
  onVoltar?: () => void
  onAvancar: () => void
  rotuloAvancar?: string
  desabilitar?: boolean
}) {
  return (
    <div className="flex items-center gap-3 pt-2">
      {onVoltar && (
        <button type="button" onClick={onVoltar} className="btn-ghost h-12 px-4" aria-label="Voltar">
          <ArrowLeft className="h-4 w-4" />
        </button>
      )}
      <button type="button" onClick={onAvancar} disabled={desabilitar} className="btn-primary h-12 flex-1 text-base">
        {rotuloAvancar}
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página
// ---------------------------------------------------------------------------

export function TutorWizardPage() {
  const { token = '' } = useParams<{ token: string }>()

  const [ctx, setCtx] = useState<TriagemContexto | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erroFatal, setErroFatal] = useState<string | null>(null)
  const [passo, setPasso] = useState<Passo>(1)

  // 1 · Termo
  const [aceiteTermo, setAceiteTermo] = useState(false)

  // 2 · Saúde preventiva
  const [vacinaPolivalente, setVacinaPolivalente] = useState('Em dia')
  const [vacinaAntirrabica, setVacinaAntirrabica] = useState('Em dia')
  const [vermifugoStatus, setVermifugoStatus] = useState('Em dia (últimos 3 a 6 meses)')
  const [ectoparasitas, setEctoparasitas] = useState('Em dia (antipulgas/carrapatos)')

  // 3 · Rotina
  const [ambiente, setAmbiente] = useState('Apartamento')
  const [alimentacao, setAlimentacao] = useState('Ração seca')
  const [acessoRua, setAcessoRua] = useState('Sem acesso à rua (domiciliado)')
  const [contactantes, setContactantes] = useState('Nenhum outro animal na casa')

  // 4 · Sinais
  const [sintomasMarcados, setSintomasMarcados] = useState<Set<number>>(new Set())
  const [busca, setBusca] = useState('')
  const [abertas, setAbertas] = useState<Set<string>>(new Set(['Emergência']))

  // 5 · Remédios e bioindicadores
  const [medicamentoContinuo, setMedicamentoContinuo] = useState('')
  const [urinaFezes, setUrinaFezes] = useState('Urina e fezes normais')
  const [urinaFezesDet, setUrinaFezesDet] = useState('')
  const [apetite, setApetite] = useState('Apetite e peso normais')
  const [apetiteDet, setApetiteDet] = useState('')
  const [hidrica, setHidrica] = useState('Bebe água normalmente')

  // 6 · Relato
  const [tempoEvolucao, setTempoEvolucao] = useState('Algumas horas')
  const [relatoLivre, setRelatoLivre] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erroForm, setErroForm] = useState<string | null>(null)

  // 7 · Resultado
  const [submissaoOut, setSubmissaoOut] = useState<TriagemSubmissaoOut | null>(null)
  const [resultadoIA, setResultadoIA] = useState<ResultadoTutor | null>(null)

  // Disjuntor RN-001 v2.0
  const [modalAberto, setModalAberto] = useState(false)
  const [alertaExibidoEm, setAlertaExibidoEm] = useState<string | null>(null)
  const [cienteRiscoMorte, setCienteRiscoMorte] = useState(false)
  const [enderecoManual, setEnderecoManual] = useState('')
  const [capturandoGps, setCapturandoGps] = useState(false)
  const [acionando, setAcionando] = useState<ModalidadeEmergencia | null>(null)
  const [emergenciaRegistrada, setEmergenciaRegistrada] = useState<AcionarEmergenciaOut | null>(null)
  const [erroEmergencia, setErroEmergencia] = useState<string | null>(null)
  const ultimaAssinaturaRef = useRef('')

  useEffect(() => {
    let cancelado = false
    async function carregar() {
      setCarregando(true)
      setErroFatal(null)
      try {
        const dados = await api<TriagemContexto>(`/publico/triagem/${token}`, { auth: false })
        if (cancelado) return
        setCtx(dados)
        if (dados.estado === 'preenchida') setPasso(7)
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

  // Disjuntor: sintoma de urgência marcado OU termo crítico no relato
  const gatilhos = useMemo(() => {
    if (!ctx) return { categorias: [], motivos: [], ativo: false }
    return avaliarGatilhos(ctx.sintomas, sintomasMarcados, relatoLivre, ctx.emergencia.gatilhos_texto)
  }, [ctx, sintomasMarcados, relatoLivre])

  useEffect(() => {
    const sig = assinatura(gatilhos)
    if (gatilhos.ativo && sig !== ultimaAssinaturaRef.current) {
      ultimaAssinaturaRef.current = sig
      if (!alertaExibidoEm) setAlertaExibidoEm(new Date().toISOString())
      setModalAberto(true)
    } else if (!gatilhos.ativo) {
      ultimaAssinaturaRef.current = ''
    }
  }, [gatilhos, alertaExibidoEm])

  // Polling do resultado da IA
  useEffect(() => {
    if (passo !== 7 || !token) return
    let ativo = true
    let timer: number | undefined
    async function consultar() {
      try {
        const res = await api<ResultadoTutor>(`/publico/triagem/${token}/resultado`, { auth: false })
        if (!ativo) return
        setResultadoIA(res)
        if (res.status_ia === 'pendente') timer = window.setTimeout(consultar, 2500)
      } catch {
        /* ainda processando */
      }
    }
    consultar()
    return () => {
      ativo = false
      if (timer) window.clearTimeout(timer)
    }
  }, [passo, token])

  // Sintomas agrupados por categoria (Emergência primeiro) com busca
  const grupos = useMemo(() => {
    if (!ctx) return []
    const q = semAcento(busca.trim())
    const mapa = new Map<string, SintomaPublico[]>()
    for (const s of ctx.sintomas) {
      if (q && !semAcento(s.nome_sintoma).includes(q) && !semAcento(s.categoria).includes(q)) continue
      mapa.set(s.categoria, [...(mapa.get(s.categoria) ?? []), s])
    }
    return Array.from(mapa.entries()).sort(([a], [b]) =>
      a === 'Emergência' ? -1 : b === 'Emergência' ? 1 : a.localeCompare(b, 'pt-BR'),
    )
  }, [ctx, busca])

  function alternarSintoma(id: number) {
    setSintomasMarcados((prev) => {
      const novo = new Set(prev)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  function alternarGrupo(cat: string) {
    setAbertas((prev) => {
      const novo = new Set(prev)
      if (novo.has(cat)) novo.delete(cat)
      else novo.add(cat)
      return novo
    })
  }

  function abrirEmergencia() {
    if (!alertaExibidoEm) setAlertaExibidoEm(new Date().toISOString())
    setModalAberto(true)
  }

  function capturarGps(): Promise<string | null> {
    return new Promise((resolve) => {
      if (!('geolocation' in navigator)) return resolve(null)
      setCapturandoGps(true)
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCapturandoGps(false)
          const c = `${pos.coords.latitude.toFixed(6)},${pos.coords.longitude.toFixed(6)}`
          setEnderecoManual(c)
          resolve(c)
        },
        () => {
          setCapturandoGps(false)
          resolve(null)
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 },
      )
    })
  }

  async function acionar(modalidade: ModalidadeEmergencia) {
    if (!ctx) return
    setErroEmergencia(null)
    if (!cienteRiscoMorte) {
      setErroEmergencia('Marque a confirmação de ciência do risco para acionar a equipe.')
      return
    }
    let loc = enderecoManual.trim() || null
    if (modalidade === 'RESGATE_SOLICITADO' && !loc) {
      loc = await capturarGps()
      if (!loc || loc.length < 5) {
        setErroEmergencia('Não conseguimos obter seu GPS. Digite seu endereço no campo acima.')
        return
      }
    }
    setAcionando(modalidade)
    try {
      const payload: AcionarEmergenciaIn = {
        modalidade,
        localizacao_gps_tutor: loc,
        ciente_risco_morte: cienteRiscoMorte,
        alerta_critico_exibido_em: alertaExibidoEm ?? new Date().toISOString(),
        categorias_emergencia: gatilhos.categorias.length ? gatilhos.categorias : ['GERAL'],
      }
      const res = await api<AcionarEmergenciaOut>(`/publico/triagem/${token}/acionar-emergencia`, {
        method: 'POST',
        body: payload,
        auth: false,
      })
      setEmergenciaRegistrada(res)
      if (modalidade === 'RESGATE_SOLICITADO' && res.whatsapp_resgate_url) {
        window.open(res.whatsapp_resgate_url, '_blank', 'noopener,noreferrer')
      }
    } catch (err) {
      setErroEmergencia((err as Error).message)
    } finally {
      setAcionando(null)
    }
  }

  function validarEAvancar(destino: Passo) {
    setErroForm(null)
    if (passo === 5 && medicamentoContinuo.trim().length < 2) {
      setErroForm('Informe os remédios das últimas 48h ou toque em “Nenhum medicamento”.')
      return
    }
    setPasso(destino)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function enviar() {
    if (!ctx) return
    setErroForm(null)
    if (relatoLivre.trim().length < 10) {
      setErroForm('Conte com um pouco mais de detalhe o que está acontecendo (mínimo 10 caracteres).')
      return
    }
    const polivalente = ctx.pet.especie === 'Gato' ? 'V4/V5' : 'V8/V10'
    const juntar = (opc: string, det: string) => (det.trim() ? `${opc} — ${det.trim()}` : opc)

    const payload: TriagemSubmissao = {
      aceite_termo: aceiteTermo,
      ambiente,
      alimentacao,
      vacinacao_em_dia: vacinaPolivalente.startsWith('Em dia') && vacinaAntirrabica.startsWith('Em dia'),
      vermifugo_em_dia: vermifugoStatus.startsWith('Em dia'),
      convivio_outros_animais: !contactantes.startsWith('Nenhum'),
      manejo_preventivo: [
        `Polivalente (${polivalente}): ${vacinaPolivalente}`,
        `Antirrábica: ${vacinaAntirrabica}`,
        `Vermífugo: ${vermifugoStatus}`,
        `Ectoparasitas: ${ectoparasitas}`,
        `Acesso à rua: ${acessoRua}`,
        `Contactantes: ${contactantes}`,
      ].join(' · '),
      medicamento_continuo: medicamentoContinuo.trim(),
      aspecto_urina_fezes: juntar(urinaFezes, urinaFezesDet),
      alteracao_peso_apetite: juntar(apetite, apetiteDet),
      ingestao_hidrica: hidrica,
      tempo_evolucao: tempoEvolucao,
      relato_livre_tutor: relatoLivre.trim(),
      sintoma_ids: Array.from(sintomasMarcados),
      ciente_risco_morte: cienteRiscoMorte,
      alerta_critico_exibido_em: alertaExibidoEm,
      modalidade_emergencia: emergenciaRegistrada?.modalidade_emergencia ?? null,
      localizacao_gps_tutor: emergenciaRegistrada?.localizacao_gps_tutor ?? (enderecoManual.trim() || null),
    }

    setEnviando(true)
    try {
      const resp = await api<TriagemSubmissaoOut>(`/publico/triagem/${token}`, {
        method: 'POST',
        body: payload,
        auth: false,
      })
      setSubmissaoOut(resp)
      setPasso(7)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setErroForm((err as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  // -------------------------------------------------------------------------
  // Estados de tela cheia
  // -------------------------------------------------------------------------
  if (carregando) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface p-6">
        <div className="flex flex-col items-center gap-4">
          <BrandLogo variant="mark" markSize="h-14 w-14" className="animate-pulse" />
          <p className="text-sm text-ink-soft">Preparando sua triagem…</p>
        </div>
      </div>
    )
  }

  if (erroFatal || !ctx) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface p-6">
        <div className="card w-full max-w-sm space-y-4 p-6 text-center">
          <AlertOctagon className="mx-auto h-10 w-10 text-red-500" />
          <h1 className="text-lg font-bold text-ink">Link indisponível</h1>
          <p className="text-sm text-ink-soft">{erroFatal ?? 'Não encontramos esta triagem.'}</p>
          <a
            href="https://www.google.com/maps/search/Hospital+Veterinario+24h/"
            target="_blank" rel="noopener noreferrer"
            className="btn-danger w-full"
          >
            <MapPin className="h-4 w-4" />
            Hospital Veterinário 24h mais próximo
          </a>
        </div>
      </div>
    )
  }

  if (ctx.estado === 'cancelada' || ctx.estado === 'expirada') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface p-6">
        <div className="card w-full max-w-sm space-y-4 p-6 text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" />
          <h1 className="text-lg font-bold text-ink">
            {ctx.estado === 'cancelada' ? 'Consulta cancelada' : 'Link expirado'}
          </h1>
          <p className="text-sm text-ink-soft">
            Peça um novo link à recepção de <strong>{ctx.clinica_nome}</strong>. Em caso de emergência, vá
            imediatamente ao pronto-socorro veterinário.
          </p>
          <a href={ctx.emergencia.url_hospital_24h} target="_blank" rel="noopener noreferrer" className="btn-danger w-full">
            <MapPin className="h-4 w-4" />
            Hospital Veterinário 24h mais próximo
          </a>
        </div>
      </div>
    )
  }

  const clinicaFechada = !ctx.emergencia.atendimento_24h && !ctx.emergencia.clinica_aberta_agora
  const categoriasAtivas = gatilhos.categorias.length ? gatilhos.categorias : ['GERAL']
  const urgenciaFinal = Boolean(submissaoOut?.urgencia_detectada || resultadoIA?.urgencia_detectada)
  const socorros = resultadoIA?.primeiros_socorros_negativos ?? submissaoOut?.primeiros_socorros_negativos ?? {}
  const progresso = passo >= 7 ? 100 : Math.round(((passo - 1) / 6) * 100) + 8
  const modalidadeAtiva = emergenciaRegistrada?.modalidade_emergencia ?? ctx.modalidade_emergencia

  return (
    <div className="min-h-screen bg-surface pb-12">
      {/* ===== Header de confiança dupla (Co-Branding Clínica × TrIAgem) ===== */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-lg items-center gap-3 px-4 py-3.5">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <ClinicAvatar nome={ctx.clinica_nome} logoUrl={ctx.logo_url} className="h-12 w-12 text-base" />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-bold text-ink">{ctx.clinica_nome}</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-soft">
                <span className={classes('h-1.5 w-1.5 rounded-full', clinicaFechada ? 'bg-slate-400' : 'bg-emerald-500')} />
                {ctx.emergencia.atendimento_24h
                  ? 'Atendimento 24h'
                  : clinicaFechada
                    ? `Fechada · fechou às ${ctx.emergencia.horario_fechamento}`
                    : `Aberta até ${ctx.emergencia.horario_fechamento}`}
              </div>
            </div>
          </div>
          <span className="select-none text-lg font-light text-slate-300" aria-hidden="true">×</span>
          <div className="shrink-0">
            <BrandLogo variant="full" textSize="text-base" markSize="h-7 w-7" selo />
          </div>
        </div>
        {/* Progresso */}
        {passo < 7 && (
          <div className="h-1 w-full bg-slate-100">
            <div className="bg-brand-gradient h-full rounded-r-full transition-all duration-500" style={{ width: `${progresso}%` }} />
          </div>
        )}
      </header>

      <main className="mx-auto max-w-lg space-y-4 px-4 pt-5">
        {/* Saudação + botão de emergência discreto */}
        {passo < 7 && (
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">
                Triagem de {ctx.pet.nome}
              </p>
              <p className="truncate text-xs text-ink-soft">{descricaoPet(ctx.pet)}</p>
            </div>
            <button
              type="button"
              onClick={abrirEmergencia}
              className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full bg-red-50 px-3.5 py-2 text-xs font-bold text-red-700 ring-1 ring-inset ring-red-200 transition hover:bg-red-100"
            >
              <Siren className="h-4 w-4" />
              Emergência
            </button>
          </div>
        )}

        {passo < 7 && (
          <p className="text-xs font-medium text-ink-soft">
            Passo {passo} de 6 · <span className="text-ink">{TITULOS_PASSOS[passo - 1]}</span>
          </p>
        )}

        {/* Banner persistente quando há gatilho/emergência */}
        {(gatilhos.ativo || modalidadeAtiva) && passo < 7 && (
          <button
            type="button"
            onClick={() => setModalAberto(true)}
            className="flex w-full cursor-pointer items-center gap-3 rounded-2xl bg-red-600 px-4 py-3 text-left text-sm font-semibold text-white shadow-md"
          >
            <Siren className="h-5 w-5 shrink-0" />
            <span className="flex-1">
              {modalidadeAtiva === 'RESGATE_SOLICITADO'
                ? 'Resgate solicitado — equipe acionada'
                : modalidadeAtiva === 'EMERGENCIA_A_CAMINHO'
                  ? 'Equipe avisada — você está a caminho'
                  : 'Sinais críticos detectados — toque para ver o que fazer'}
            </span>
            <ArrowRight className="h-4 w-4" />
          </button>
        )}

        {erroForm && (
          <div className="flex items-start gap-2 rounded-2xl bg-red-50 p-3.5 text-sm text-red-700 ring-1 ring-red-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {erroForm}
          </div>
        )}

        {/* ===== PASSO 1 · TERMO ===== */}
        {passo === 1 && (
          <CartaoPasso
            titulo={`Olá, ${ctx.tutor_primeiro_nome}!`}
            subtitulo={`Em ~2 minutos o veterinário já recebe tudo sobre ${ctx.pet.nome} antes da consulta.`}
          >
            <div className="flex gap-3 rounded-2xl bg-red-50 p-4 text-sm text-red-900">
              <Siren className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
              <p>
                Se {ctx.pet.nome} estiver com falta de ar, convulsão, sangramento intenso, atropelamento ou
                envenenamento, <strong>não preencha o formulário</strong>: toque em <strong>Emergência</strong>.
              </p>
            </div>

            <details className="group rounded-2xl border border-slate-200 p-4 text-sm text-ink-soft">
              <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-ink">
                Termo de ciência e LGPD
                <ChevronDown className="h-4 w-4 transition group-open:rotate-180" />
              </summary>
              <p className="mt-3 leading-relaxed">{ctx.texto_termo}</p>
            </details>

            <button
              type="button"
              onClick={() => setAceiteTermo((v) => !v)}
              aria-pressed={aceiteTermo}
              className={classes(
                'flex w-full cursor-pointer items-start gap-3 rounded-2xl border p-4 text-left text-sm transition',
                aceiteTermo ? 'border-brand bg-brand-soft ring-2 ring-brand/20' : 'border-slate-200 bg-white',
              )}
            >
              <span
                className={classes(
                  'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border',
                  aceiteTermo ? 'border-brand bg-brand text-white' : 'border-slate-300',
                )}
              >
                {aceiteTermo && <Check className="h-3 w-3" strokeWidth={3} />}
              </span>
              <span className="font-medium text-ink">
                Li e aceito o termo. Entendo que esta triagem não substitui atendimento de emergência.
              </span>
            </button>
            <Navegacao onAvancar={() => validarEAvancar(2)} desabilitar={!aceiteTermo} rotuloAvancar="Começar" />
          </CartaoPasso>
        )}

        {/* ===== PASSO 2 · SAÚDE PREVENTIVA ===== */}
        {passo === 2 && (
          <CartaoPasso titulo="Saúde preventiva" subtitulo={`Vacinas e cuidados de ${ctx.pet.nome}.`}>
            <Opcoes
              rotulo={`Vacina polivalente (${ctx.pet.especie === 'Gato' ? 'V4/V5' : 'V8/V10'})`}
              opcoes={['Em dia', 'Atrasada', 'Filhote em esquema vacinal', 'Nunca vacinou / não sei']}
              valor={vacinaPolivalente}
              onChange={setVacinaPolivalente}
            />
            <Opcoes
              rotulo="Vacina antirrábica"
              opcoes={['Em dia', 'Atrasada', 'Ainda não tomou / não sei']}
              valor={vacinaAntirrabica}
              onChange={setVacinaAntirrabica}
            />
            <Opcoes
              rotulo="Vermífugo"
              opcoes={['Em dia (últimos 3 a 6 meses)', 'Atrasado (mais de 6 meses)', 'Nunca tomou / não lembro']}
              valor={vermifugoStatus}
              onChange={setVermifugoStatus}
            />
            <Opcoes
              rotulo="Antipulgas e carrapatos"
              opcoes={['Em dia (antipulgas/carrapatos)', 'Atrasado / sem proteção', 'Vi pulgas ou carrapatos hoje']}
              valor={ectoparasitas}
              onChange={setEctoparasitas}
            />
            <Navegacao onVoltar={() => setPasso(1)} onAvancar={() => validarEAvancar(3)} />
          </CartaoPasso>
        )}

        {/* ===== PASSO 3 · ROTINA ===== */}
        {passo === 3 && (
          <CartaoPasso titulo="Rotina e ambiente" subtitulo="Como é o dia a dia dele(a)?">
            <Opcoes rotulo="Onde vive" opcoes={['Apartamento', 'Casa com quintal', 'Sítio / chácara']} valor={ambiente} onChange={setAmbiente} />
            <Opcoes
              rotulo="Alimentação"
              opcoes={['Ração seca', 'Ração úmida / sachê', 'Alimentação natural', 'Mista (ração + caseira)']}
              valor={alimentacao}
              onChange={setAlimentacao}
            />
            <Opcoes
              rotulo="Acesso à rua"
              opcoes={['Sem acesso à rua (domiciliado)', 'Passeia com guia', 'Acesso livre à rua / quintal aberto']}
              valor={acessoRua}
              onChange={setAcessoRua}
            />
            <Opcoes
              rotulo="Convive com outros animais?"
              opcoes={['Nenhum outro animal na casa', 'Convive com cães', 'Convive com gatos', 'Convive com cães e gatos']}
              valor={contactantes}
              onChange={setContactantes}
            />
            <Navegacao onVoltar={() => setPasso(2)} onAvancar={() => validarEAvancar(4)} />
          </CartaoPasso>
        )}

        {/* ===== PASSO 4 · SINAIS ===== */}
        {passo === 4 && (
          <CartaoPasso
            titulo="O que você notou?"
            subtitulo="Toque nos sinais observados. Pode pular se não houver nenhum."
          >
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar sinal (ex.: vômito, tosse, coceira)"
                className="input pl-10"
              />
            </div>

            {sintomasMarcados.size > 0 && (
              <p className="text-xs font-medium text-brand">
                {sintomasMarcados.size} {sintomasMarcados.size === 1 ? 'sinal selecionado' : 'sinais selecionados'}
              </p>
            )}

            <div className="space-y-3">
              {grupos.length === 0 && (
                <p className="rounded-2xl bg-slate-50 p-4 text-center text-sm text-ink-soft">Nenhum sinal encontrado.</p>
              )}
              {grupos.map(([categoria, lista]) => {
                const emerg = categoria === 'Emergência'
                const aberto = Boolean(busca.trim()) || abertas.has(categoria)
                const qtd = lista.filter((s) => sintomasMarcados.has(s.id_sintoma)).length
                return (
                  <div
                    key={categoria}
                    className={classes('overflow-hidden rounded-2xl border', emerg ? 'border-red-200' : 'border-slate-200')}
                  >
                    <button
                      type="button"
                      onClick={() => alternarGrupo(categoria)}
                      aria-expanded={aberto}
                      className={classes(
                        'flex w-full cursor-pointer items-center justify-between px-4 py-3.5 text-left',
                        emerg ? 'bg-red-50' : 'bg-white',
                      )}
                    >
                      <span className="flex items-center gap-2 text-sm font-bold text-ink">
                        {emerg && <Siren className="h-4 w-4 text-red-500" />}
                        {emerg ? 'Sinais de emergência' : categoria}
                        <span className="text-xs font-medium text-ink-soft">({lista.length})</span>
                        {qtd > 0 && (
                          <span className={classes('rounded-full px-2 py-0.5 text-[11px] font-bold text-white', emerg ? 'bg-red-500' : 'bg-brand')}>
                            {qtd}
                          </span>
                        )}
                      </span>
                      <ChevronDown className={classes('h-4 w-4 text-slate-400 transition', aberto && 'rotate-180')} />
                    </button>
                    {aberto && (
                      <div className="grid gap-2 border-t border-slate-100 bg-white p-3">
                        {lista.map((s) => {
                          const marcado = sintomasMarcados.has(s.id_sintoma)
                          return (
                            <button
                              key={s.id_sintoma}
                              type="button"
                              onClick={() => alternarSintoma(s.id_sintoma)}
                              aria-pressed={marcado}
                              className={classes(
                                'flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 text-left text-sm transition active:scale-[0.99]',
                                marcado
                                  ? s.alerta_urgencia
                                    ? 'border-red-400 bg-red-50 font-semibold text-red-900 ring-2 ring-red-200'
                                    : 'border-brand bg-brand-soft font-semibold text-ink ring-2 ring-brand/20'
                                  : 'border-slate-200 text-slate-700 hover:border-slate-300',
                              )}
                            >
                              <span
                                className={classes(
                                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-md border',
                                  marcado ? (s.alerta_urgencia ? 'border-red-500 bg-red-500 text-white' : 'border-brand bg-brand text-white') : 'border-slate-300',
                                )}
                              >
                                {marcado && <Check className="h-3 w-3" strokeWidth={3} />}
                              </span>
                              <span className="leading-snug">{s.nome_sintoma}</span>
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            <Navegacao onVoltar={() => setPasso(3)} onAvancar={() => validarEAvancar(5)} />
          </CartaoPasso>
        )}

        {/* ===== PASSO 5 · REMÉDIOS E BIOINDICADORES ===== */}
        {passo === 5 && (
          <CartaoPasso titulo="Remédios e bioindicadores" subtitulo="Informação essencial para a segurança de nosso paciente.">
            <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
              <label htmlFor="meds" className="flex items-center gap-2 text-sm font-bold text-ink">
                <Pill className="h-4 w-4 text-amber-600" />
                Remédios em uso ou dados nas últimas 48h
              </label>
              <button
                type="button"
                onClick={() => setMedicamentoContinuo('Nenhum medicamento contínuo; nada administrado nas últimas 48h')}
                className={classes(
                  'flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 text-left text-sm transition',
                  medicamentoContinuo.startsWith('Nenhum medicamento')
                    ? 'border-brand bg-brand-soft font-semibold ring-2 ring-brand/20'
                    : 'border-slate-200 bg-white',
                )}
              >
                <Check className={classes('h-4 w-4', medicamentoContinuo.startsWith('Nenhum medicamento') ? 'text-brand' : 'text-slate-300')} />
                Nenhum medicamento
              </button>
              <input
                id="meds"
                type="text"
                value={medicamentoContinuo.startsWith('Nenhum medicamento') ? '' : medicamentoContinuo}
                onChange={(e) => setMedicamentoContinuo(e.target.value)}
                placeholder="Ou digite: nome, dose e horário"
                className="input"
              />
            </div>

            <div className="space-y-2">
              <Opcoes
                rotulo="Urina e fezes"
                opcoes={['Urina e fezes normais', 'Fezes moles / diarreia', 'Urina com sangue ou alterada', 'Sem urinar ou sem fezes']}
                valor={urinaFezes}
                onChange={setUrinaFezes}
              />
              <input value={urinaFezesDet} onChange={(e) => setUrinaFezesDet(e.target.value)} placeholder="Detalhes (opcional)" className="input" />
            </div>
            <div className="space-y-2">
              <Opcoes
                rotulo="Apetite e peso"
                opcoes={['Apetite e peso normais', 'Come menos que o normal', 'Não está comendo', 'Come mais que o normal']}
                valor={apetite}
                onChange={setApetite}
              />
              <input value={apetiteDet} onChange={(e) => setApetiteDet(e.target.value)} placeholder="Detalhes (opcional)" className="input" />
            </div>
            <Opcoes
              rotulo="Água"
              opcoes={['Bebe água normalmente', 'Bebe muito mais que o normal', 'Bebe menos que o normal']}
              valor={hidrica}
              onChange={setHidrica}
            />
            <Navegacao onVoltar={() => setPasso(4)} onAvancar={() => validarEAvancar(6)} />
          </CartaoPasso>
        )}

        {/* ===== PASSO 6 · RELATO ===== */}
        {passo === 6 && (
          <CartaoPasso titulo="Conte com suas palavras" subtitulo="Quando começou e como evoluiu? Qualquer detalhe ajuda.">
            <Opcoes
              rotulo="Há quanto tempo começou?"
              opcoes={['Algumas horas', 'Desde ontem', '2 a 3 dias', 'Mais de uma semana']}
              valor={tempoEvolucao}
              onChange={setTempoEvolucao}
            />
            <div>
              <label htmlFor="relato" className="mb-2 block text-sm font-semibold text-ink">
                Relato
              </label>
              <textarea
                id="relato"
                rows={5}
                value={relatoLivre}
                onChange={(e) => setRelatoLivre(e.target.value)}
                placeholder="Ex.: vomitou espuma amarela duas vezes e está mais quieto…"
                className="input leading-relaxed"
              />
            </div>
            <div className="flex items-center gap-3 pt-2">
              <button type="button" onClick={() => setPasso(5)} className="btn-ghost h-12 px-4" aria-label="Voltar">
                <ArrowLeft className="h-4 w-4" />
              </button>
              <button type="button" onClick={enviar} disabled={enviando} className="btn-primary h-12 flex-1 text-base">
                <Sparkles className="h-4 w-4" />
                {enviando ? 'Enviando…' : 'Enviar triagem'}
              </button>
            </div>
          </CartaoPasso>
        )}

        {/* ===== PASSO 7 · CONFIRMAÇÃO ===== */}
        {passo === 7 && (
          <section className="card fade-up space-y-5 p-5 sm:p-7">
            <div className="flex items-start gap-4">
              <span
                className={classes(
                  'flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl',
                  urgenciaFinal ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600',
                )}
              >
                {urgenciaFinal ? <Siren className="h-6 w-6" /> : <CheckCircle2 className="h-6 w-6" />}
              </span>
              <div>
                <h2 className="text-xl font-extrabold tracking-tight text-ink">Triagem recebida</h2>
                <p className="mt-0.5 text-sm text-ink-soft">
                  A equipe de {ctx.clinica_nome} já tem as informações de {ctx.pet.nome}.
                </p>
              </div>
            </div>

            <div className={classes('space-y-2 rounded-2xl p-4 text-sm', urgenciaFinal ? 'bg-red-50 text-red-900' : 'bg-brand-soft text-ink')}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider">Orientação de segurança</span>
                {resultadoIA?.status_ia === 'pendente' && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-ai">
                    <Clock className="h-3.5 w-3.5 animate-spin" />
                    organizando…
                  </span>
                )}
              </div>
              <p className="leading-relaxed">
                {resultadoIA?.alerta_seguranca_tutor ??
                  submissaoOut?.mensagem_para_tutor ??
                  'Aguarde ser chamado. Não dê remédios por conta própria.'}
              </p>
            </div>

            {Object.keys(socorros).length > 0 && (
              <div className="space-y-2 rounded-2xl border-2 border-red-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-extrabold text-red-700">
                  <ShieldAlert className="h-4 w-4" />
                  ⚠️ O QUE NÃO FAZER AGORA EM CASA
                </div>
                {Object.entries(socorros).map(([cat, texto]) => (
                  <div key={cat} className="rounded-xl bg-red-50 p-3">
                    <div className="text-[11px] font-bold uppercase tracking-wide text-red-700">{ROTULO_CATEGORIA[cat] ?? cat}</div>
                    <p className="mt-0.5 text-sm leading-relaxed text-red-950">{texto}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="grid gap-2 sm:grid-cols-2">
              <button type="button" onClick={abrirEmergencia} className="btn-danger h-12">
                <Siren className="h-4 w-4" />
                Acionar emergência
              </button>
              <a href={ctx.emergencia.rota_clinica.google_maps} target="_blank" rel="noopener noreferrer" className="btn-ghost h-12">
                <Navigation className="h-4 w-4 text-brand" />
                Rota até a clínica
              </a>
            </div>
          </section>
        )}

        <p className="flex items-center justify-center gap-1.5 pt-2 text-[11px] text-ink-soft">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          Seus dados são protegidos pela LGPD · o TrIAgem não faz diagnóstico
        </p>
      </main>

      {/* ===================================================================
          DISJUNTOR DE EMERGÊNCIA RN-001 v2.0
         =================================================================== */}
      {modalAberto && (
        <div className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-slate-900/70 backdrop-blur-sm sm:items-center sm:p-4">
          <div role="dialog" aria-modal="true" aria-label="Emergência" className="fade-up w-full max-w-lg overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl">
            <div className="flex items-start justify-between gap-3 bg-red-600 px-5 py-4 text-white">
              <div className="flex items-start gap-3">
                <Siren className="mt-0.5 h-6 w-6 shrink-0" />
                <div>
                  <h2 className="text-lg font-extrabold leading-tight">Risco imediato à vida</h2>
                  <p className="mt-0.5 text-sm text-red-100">
                    {gatilhos.motivos.length > 0 ? gatilhos.motivos.slice(0, 2).join(' · ') : 'Siga as orientações abaixo e acione a equipe.'}
                  </p>
                </div>
              </div>
              <button type="button" onClick={() => setModalAberto(false)} className="shrink-0 cursor-pointer rounded-lg bg-white/15 px-3 py-1.5 text-xs font-semibold hover:bg-white/25">
                Fechar
              </button>
            </div>

            <div className="max-h-[75vh] space-y-4 overflow-y-auto p-5">
              {/* a) O QUE NÃO FAZER */}
              <div className="space-y-2 rounded-2xl border-2 border-amber-300 bg-amber-50 p-4">
                <div className="flex items-center gap-2 text-sm font-extrabold text-amber-900">
                  <AlertTriangle className="h-4 w-4" />
                  ⚠️ O QUE NÃO FAZER AGORA EM CASA
                </div>
                {categoriasAtivas.map((cat) => (
                  <div key={cat} className="rounded-xl bg-white p-3">
                    <div className="text-[11px] font-bold uppercase tracking-wide text-amber-700">{ROTULO_CATEGORIA[cat] ?? cat}</div>
                    <p className="mt-0.5 text-sm leading-relaxed text-slate-800">
                      {ctx.emergencia.primeiros_socorros_negativos[cat] ?? ctx.emergencia.primeiros_socorros_negativos.GERAL}
                    </p>
                  </div>
                ))}
              </div>

              {/* b) Ciência */}
              <button
                type="button"
                onClick={() => {
                  setCienteRiscoMorte((v) => !v)
                  setErroEmergencia(null)
                }}
                aria-pressed={cienteRiscoMorte}
                className={classes(
                  'flex w-full cursor-pointer items-start gap-3 rounded-2xl border p-4 text-left text-sm transition',
                  cienteRiscoMorte ? 'border-red-400 bg-red-50' : 'border-slate-200 bg-white',
                )}
              >
                <span className={classes('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border', cienteRiscoMorte ? 'border-red-500 bg-red-500 text-white' : 'border-slate-300')}>
                  {cienteRiscoMorte && <Check className="h-3 w-3" strokeWidth={3} />}
                </span>
                <span className="font-medium text-ink">
                  Estou ciente de que há risco imediato de morte para <strong>{ctx.pet.nome}</strong> e de que o
                  atendimento presencial não pode esperar.
                </span>
              </button>

              {erroEmergencia && <p className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700">{erroEmergencia}</p>}

              {emergenciaRegistrada && (
                <div className="space-y-3 rounded-2xl bg-emerald-50 p-4 text-sm">
                  <div className="flex items-start gap-2 font-semibold text-emerald-900">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    {emergenciaRegistrada.mensagem_para_tutor}
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <a href={emergenciaRegistrada.rota_clinica.google_maps} target="_blank" rel="noopener noreferrer" className="btn-ghost">
                      <Navigation className="h-4 w-4 text-brand" />
                      Google Maps
                    </a>
                    <a href={emergenciaRegistrada.rota_clinica.waze} target="_blank" rel="noopener noreferrer" className="btn-ghost">
                      <ExternalLink className="h-4 w-4 text-brand" />
                      Waze
                    </a>
                    {emergenciaRegistrada.whatsapp_resgate_url && (
                      <a href={emergenciaRegistrada.whatsapp_resgate_url} target="_blank" rel="noopener noreferrer" className="btn-success sm:col-span-2">
                        <MessageCircle className="h-4 w-4" />
                        Enviar localização no WhatsApp do plantão
                      </a>
                    )}
                  </div>
                </div>
              )}

              {clinicaFechada && (
                <p className="rounded-xl bg-slate-100 p-3 text-sm text-slate-700">
                  Esta clínica fechou às {ctx.emergencia.horario_fechamento}. Procure um hospital 24h.
                </p>
              )}

              {/* c) Estou a caminho */}
              <button
                type="button"
                disabled={acionando !== null}
                onClick={() => acionar('EMERGENCIA_A_CAMINHO')}
                className="btn-danger min-h-14 w-full text-base"
              >
                <Siren className="h-5 w-5 shrink-0" />
                {acionando === 'EMERGENCIA_A_CAMINHO' ? 'Avisando equipe…' : '🚨 ESTOU A CAMINHO! Avisar Equipe de Emergência Agora'}
              </button>

              {/* d) Resgate */}
              {ctx.emergencia.possui_veiculo_resgate && (
                <div className="space-y-2.5 rounded-2xl border border-slate-200 p-3.5">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={enderecoManual}
                      onChange={(e) => setEnderecoManual(e.target.value)}
                      placeholder="Seu endereço ou use o GPS"
                      className="input"
                    />
                    <button type="button" disabled={capturandoGps} onClick={() => capturarGps()} className="btn-ghost shrink-0">
                      <MapPin className="h-4 w-4 text-brand" />
                      {capturandoGps ? 'Obtendo…' : 'GPS'}
                    </button>
                  </div>
                  <button
                    type="button"
                    disabled={acionando !== null}
                    onClick={() => acionar('RESGATE_SOLICITADO')}
                    className="btn min-h-14 w-full bg-amber-500 text-base text-slate-950 hover:bg-amber-400"
                  >
                    <Ambulance className="h-5 w-5 shrink-0" />
                    {acionando === 'RESGATE_SOLICITADO' ? 'Solicitando resgate…' : '🚑 SOLICITAR VEÍCULO DE RESGATE DA CLÍNICA (Enviar Meu GPS)'}
                  </button>
                </div>
              )}

              {/* e) Hospital 24h */}
              <a href={ctx.emergencia.url_hospital_24h} target="_blank" rel="noopener noreferrer" className="btn-ghost min-h-12 w-full">
                <MapPin className="h-4 w-4 text-red-500" />
                📍 Buscar Hospital Veterinário 24h Mais Próximo no Google Maps
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
