import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ambulance,
  CalendarPlus,
  CheckCircle2,
  Link2,
  MapPin,
  MessageCircle,
  RefreshCw,
  Search,
  Siren,
  Smartphone,
  Stethoscope,
  X,
  XCircle,
} from 'lucide-react'
import { IconButton, ManchesterBadge, Pilula } from '../components/ui'
import { api } from '../lib/api'
import { classes, descricaoPet, formatarHora, formatarTelefone, linkTutorLocal } from '../lib/format'
import type { ConsultaAgendar, ConsultaFilaItem, MedicoOut, PetResumo, TutorComPets } from '../types'

type Aba = 'todos' | 'aguardando' | 'prontos' | 'urgencias'

const ABAS: { id: Aba; rotulo: string }[] = [
  { id: 'todos', rotulo: 'Todos' },
  { id: 'aguardando', rotulo: 'Aguardando triagem' },
  { id: 'prontos', rotulo: 'Prontos' },
  { id: 'urgencias', rotulo: 'Urgências' },
]

const aberta = (c: ConsultaFilaItem) => c.status === 'agendada' || c.status === 'em_andamento'

export function RecepcaoPage() {
  const [fila, setFila] = useState<ConsultaFilaItem[]>([])
  const [medicos, setMedicos] = useState<MedicoOut[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [aba, setAba] = useState<Aba>('todos')
  const [filtroMedico, setFiltroMedico] = useState<number | ''>('')

  // Modal de novo agendamento
  const [modalAberto, setModalAberto] = useState(false)
  const [buscaTutor, setBuscaTutor] = useState('')
  const [tutores, setTutores] = useState<TutorComPets[]>([])
  const [idMedicoNovo, setIdMedicoNovo] = useState(0)
  const [tutorNome, setTutorNome] = useState('')
  const [tutorTelefone, setTutorTelefone] = useState('')
  const [petNome, setPetNome] = useState('')
  const [petEspecie, setPetEspecie] = useState('Cão')
  const [petRaca, setPetRaca] = useState('Sem raça definida (SRD)')
  const [petSexo, setPetSexo] = useState<'Macho' | 'Fêmea' | 'Não informado'>('Macho')
  const [petIdade, setPetIdade] = useState('3 anos')
  const [petPeso, setPetPeso] = useState('')
  const [petPorte, setPetPorte] = useState<'' | 'Mini' | 'Pequeno' | 'Médio' | 'Grande' | 'Gigante'>('Médio')
  const [petRepro, setPetRepro] = useState<'' | 'Castrado' | 'Inteiro'>('Castrado')
  const [salvando, setSalvando] = useState(false)
  const [agendada, setAgendada] = useState<ConsultaFilaItem | null>(null)

  const carregar = useCallback(async () => {
    setErro(null)
    try {
      const [lista, meds] = await Promise.all([
        api<ConsultaFilaItem[]>('/consultas/fila', { query: { id_medico: filtroMedico || undefined } }),
        api<MedicoOut[]>('/clinicas/me/medicos'),
      ])
      setFila(lista)
      setMedicos(meds)
      setIdMedicoNovo((atual) => atual || meds[0]?.id_medico || 0)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setCarregando(false)
    }
  }, [filtroMedico])

  useEffect(() => {
    carregar()
    const t = window.setInterval(carregar, 8000)
    return () => window.clearInterval(t)
  }, [carregar])

  useEffect(() => {
    if (!modalAberto) return
    let ativo = true
    const h = window.setTimeout(async () => {
      try {
        const r = await api<TutorComPets[]>('/clinicas/me/tutores', { query: { q: buscaTutor.trim() } })
        if (ativo) setTutores(r)
      } catch {
        /* silencioso */
      }
    }, 220)
    return () => {
      ativo = false
      window.clearTimeout(h)
    }
  }, [modalAberto, buscaTutor])

  const emergencias = useMemo(() => fila.filter((c) => aberta(c) && c.modalidade_emergencia), [fila])

  const indicadores = useMemo(
    () => ({
      total: fila.length,
      aguardando: fila.filter((c) => aberta(c) && c.status_triagem === 'pendente').length,
      prontos: fila.filter((c) => c.status === 'agendada' && c.status_triagem !== 'pendente').length,
      emergencias: fila.filter((c) => aberta(c) && c.urgencia).length,
    }),
    [fila],
  )

  const visiveis = useMemo(
    () =>
      fila.filter((c) => {
        if (aba === 'aguardando') return aberta(c) && c.status_triagem === 'pendente'
        if (aba === 'prontos') return c.status === 'agendada' && c.status_triagem !== 'pendente'
        if (aba === 'urgencias') return aberta(c) && c.urgencia
        return true
      }),
    [fila, aba],
  )

  function escolher(t: TutorComPets, p?: PetResumo) {
    setTutorNome(t.nome)
    setTutorTelefone(t.telefone)
    if (p) {
      setPetNome(p.nome)
      setPetEspecie(p.especie)
      setPetRaca(p.raca)
      setPetSexo(p.sexo === 'Macho' || p.sexo === 'Fêmea' ? p.sexo : 'Não informado')
      setPetIdade(p.idade_texto)
      setPetPeso(p.peso_kg != null ? String(p.peso_kg) : '')
      setPetPorte((p.porte as typeof petPorte) ?? '')
      setPetRepro((p.status_reprodutivo as typeof petRepro) ?? '')
    }
  }

  async function criar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    setSalvando(true)
    try {
      const peso = petPeso.trim() ? Number(petPeso.replace(',', '.')) : null
      const payload: ConsultaAgendar = {
        id_medico: idMedicoNovo || medicos[0]?.id_medico,
        tutor: { nome: tutorNome.trim(), telefone: tutorTelefone.trim() },
        pet: {
          nome: petNome.trim(),
          especie: petEspecie.trim(),
          raca: petRaca.trim() || 'Sem raça definida',
          sexo: petSexo,
          idade_texto: petIdade.trim() || 'Não informada',
          peso_kg: peso && !Number.isNaN(peso) ? peso : null,
          porte: petPorte || null,
          status_reprodutivo: petRepro || null,
        },
      }
      setAgendada(await api<ConsultaFilaItem>('/consultas', { method: 'POST', body: payload }))
      await carregar()
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  async function novoLink(id: number) {
    try {
      await api(`/consultas/${id}/novo-link`, { method: 'POST' })
      await carregar()
    } catch (e) {
      setErro((e as Error).message)
    }
  }

  async function cancelar(c: ConsultaFilaItem) {
    if (!window.confirm(`Cancelar a consulta de ${c.pet_nome}?`)) return
    try {
      await api(`/consultas/${c.id_consulta}/cancelar`, { method: 'PATCH' })
      await carregar()
    } catch (e) {
      setErro((e as Error).message)
    }
  }

  function abrirModal() {
    setAgendada(null)
    setTutorNome('')
    setTutorTelefone('')
    setPetNome('')
    setPetPeso('')
    setBuscaTutor('')
    setModalAberto(true)
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      {/* Título + ação principal */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-ink">Fila de hoje</h1>
          <p className="mt-1 text-sm text-ink-soft">Envie o link, acompanhe as triagens e receba alertas em tempo real.</p>
        </div>
        <button type="button" onClick={abrirModal} className="btn-primary">
          <CalendarPlus className="h-4 w-4" />
          Novo agendamento
        </button>
      </div>

      {/* Indicadores */}
      <div className="flex flex-wrap gap-2.5">
        <Pilula valor={indicadores.total} rotulo="hoje" />
        <Pilula valor={indicadores.aguardando} rotulo="aguardando triagem" tom="amber" />
        <Pilula valor={indicadores.prontos} rotulo="prontos para consulta" tom="brand" />
        <Pilula valor={indicadores.emergencias} rotulo="emergências" tom={indicadores.emergencias ? 'red' : 'slate'} />
      </div>

      {/* Banner de emergência/resgate (só quando há paciente acionado) */}
      {emergencias.length > 0 && (
        <section className="emergency-pulse space-y-3 rounded-2xl bg-red-600 p-4 text-white shadow-lg sm:p-5">
          <div className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-wider">
            <Siren className="h-5 w-5" />
            {emergencias.length === 1 ? 'Paciente em emergência' : `${emergencias.length} pacientes em emergência`}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {emergencias.map((c) => {
              const resgate = c.modalidade_emergencia === 'RESGATE_SOLICITADO'
              return (
                <div key={c.id_consulta} className="flex flex-col gap-3 rounded-xl bg-white p-4 text-ink">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-extrabold">{c.pet_nome}</span>
                      <span className="text-xs text-ink-soft">{c.especie} · {c.pet_raca}</span>
                    </div>
                    <p className="mt-1 text-sm font-semibold text-red-700">
                      {resgate
                        ? 'Resgate solicitado — despache o veículo até o GPS do tutor.'
                        : 'Paciente crítico em deslocamento — Preparar Box de Emergência e Oxigênio.'}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      {c.tutor_nome} · {formatarTelefone(c.tutor_telefone)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {c.maps_url_tutor && (
                      <a href={c.maps_url_tutor} target="_blank" rel="noopener noreferrer" className="btn-danger px-3.5 py-2 text-xs">
                        <MapPin className="h-4 w-4" />
                        Abrir mapa GPS
                      </a>
                    )}
                    <span className="inline-flex items-center gap-1.5 rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                      {resgate ? <Ambulance className="h-4 w-4" /> : <Siren className="h-4 w-4" />}
                      {resgate ? 'Resgate' : 'A caminho'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {erro && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 p-3.5 text-sm text-red-700 ring-1 ring-red-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {erro}
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-xl bg-slate-100 p-1">
          {ABAS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setAba(a.id)}
              className={classes(
                'cursor-pointer rounded-lg px-3.5 py-1.5 text-xs font-semibold transition',
                aba === a.id ? 'bg-white text-ink shadow-sm' : 'text-ink-soft hover:text-ink',
              )}
            >
              {a.rotulo}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filtroMedico}
            onChange={(e) => setFiltroMedico(e.target.value ? Number(e.target.value) : '')}
            className="input w-auto py-2 text-xs"
            aria-label="Filtrar por veterinário"
          >
            <option value="">Todos os veterinários</option>
            {medicos.map((m) => (
              <option key={m.id_medico} value={m.id_medico}>{m.nome}</option>
            ))}
          </select>
          <IconButton titulo="Atualizar agora" onClick={carregar}>
            <RefreshCw className="h-4 w-4" />
          </IconButton>
        </div>
      </div>

      {/* Fila */}
      <section className="space-y-3">
        {carregando ? (
          <div className="card p-10 text-center text-sm text-ink-soft">Carregando fila…</div>
        ) : visiveis.length === 0 ? (
          <div className="card space-y-3 p-10 text-center">
            <p className="text-sm text-ink-soft">Nada por aqui nesta visão.</p>
            <button type="button" onClick={abrirModal} className="btn-primary mx-auto">
              <CalendarPlus className="h-4 w-4" />
              Novo agendamento
            </button>
          </div>
        ) : (
          visiveis.map((c) => {
            const pendente = c.status_triagem === 'pendente'
            const encerrada = c.status === 'finalizada' || c.status === 'cancelada'
            return (
              <article
                key={c.id_consulta}
                className={classes(
                  'card flex flex-col gap-4 border-l-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5',
                  c.urgencia && !encerrada ? 'border-l-red-500' : 'border-l-transparent',
                  encerrada && 'opacity-70',
                )}
              >
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-bold text-ink">{c.pet_nome}</h3>
                    <ManchesterBadge cor={c.cor_prioridade} />
                    {c.modalidade_emergencia && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-0.5 text-[11px] font-bold text-white">
                        {c.modalidade_emergencia === 'RESGATE_SOLICITADO' ? <Ambulance className="h-3 w-3" /> : <Siren className="h-3 w-3" />}
                        {c.modalidade_emergencia === 'RESGATE_SOLICITADO' ? 'Resgate' : 'A caminho'}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-ink-soft">
                    {descricaoPet({
                      especie: c.especie, raca: c.pet_raca, peso_kg: c.pet_peso_kg,
                      porte: c.pet_porte, status_reprodutivo: c.pet_status_reprodutivo,
                    })}
                  </p>
                  <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-soft">
                    <span>Tutor: <span className="font-medium text-ink">{c.tutor_nome}</span></span>
                    <span className="inline-flex items-center gap-1">
                      <Stethoscope className="h-3.5 w-3.5" />
                      {c.medico.nome}
                    </span>
                    <span>{formatarHora(c.agendada_para)}</span>
                    {encerrada && <span className="font-semibold uppercase">{c.status}</span>}
                    {c.status === 'em_andamento' && <span className="font-semibold uppercase text-brand">em consulta</span>}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {!encerrada && pendente && (
                    <>
                      <a href={c.whatsapp_url} target="_blank" rel="noopener noreferrer" className="btn-success">
                        <MessageCircle className="h-4 w-4" />
                        Enviar link WhatsApp
                      </a>
                      <a href={linkTutorLocal(c.link_triagem)} target="_blank" rel="noopener noreferrer" className="btn-ghost" title="Abrir como se fosse o celular do tutor">
                        <Smartphone className="h-4 w-4" />
                        <span className="hidden lg:inline">Simular celular</span>
                      </a>
                    </>
                  )}
                  {!encerrada && !pendente && c.status === 'agendada' && (
                    <span className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-emerald-700">
                      <CheckCircle2 className="h-4 w-4" />
                      Triagem pronta
                    </span>
                  )}
                  {!encerrada && (
                    <div className="flex items-center">
                      {!pendente && (
                        <a href={linkTutorLocal(c.link_triagem)} target="_blank" rel="noopener noreferrer" title="Ver como o tutor" aria-label="Ver como o tutor" className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-50 hover:text-brand">
                          <Smartphone className="h-4 w-4" />
                        </a>
                      )}
                      <IconButton titulo="Gerar novo link (invalida o anterior)" onClick={() => novoLink(c.id_consulta)}>
                        <Link2 className="h-4 w-4" />
                      </IconButton>
                      <IconButton titulo="Cancelar consulta" onClick={() => cancelar(c)} perigo>
                        <XCircle className="h-4 w-4" />
                      </IconButton>
                    </div>
                  )}
                </div>
              </article>
            )
          })
        )}
      </section>

      {/* Modal novo agendamento */}
      {modalAberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm">
          <div role="dialog" aria-modal="true" className="fade-up my-auto w-full max-w-xl rounded-3xl bg-white p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-extrabold text-ink">Novo agendamento</h2>
                <p className="text-sm text-ink-soft">Gere o link de triagem para o tutor.</p>
              </div>
              <button type="button" onClick={() => setModalAberto(false)} aria-label="Fechar" className="cursor-pointer rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
                <X className="h-5 w-5" />
              </button>
            </div>

            {agendada ? (
              <div className="space-y-4">
                <div className="flex gap-3 rounded-2xl bg-emerald-50 p-4">
                  <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-600" />
                  <div className="text-sm text-emerald-900">
                    <p className="font-bold">Consulta de {agendada.pet_nome} agendada!</p>
                    <p>Envie o link para {agendada.tutor_nome} ou simule a jornada do tutor.</p>
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <a href={agendada.whatsapp_url} target="_blank" rel="noopener noreferrer" className="btn-success h-12">
                    <MessageCircle className="h-4 w-4" />
                    Enviar link no WhatsApp
                  </a>
                  <a href={linkTutorLocal(agendada.link_triagem)} target="_blank" rel="noopener noreferrer" className="btn-ghost h-12">
                    <Smartphone className="h-4 w-4" />
                    Simular celular do tutor
                  </a>
                </div>
                <div className="flex justify-end">
                  <button type="button" onClick={() => setModalAberto(false)} className="btn-primary">Concluir</button>
                </div>
              </div>
            ) : (
              <form onSubmit={criar} className="space-y-4">
                <div>
                  <label className="label" htmlFor="busca"><Search className="mr-1 inline h-3 w-3" />Tutor já cadastrado? Busque</label>
                  <input id="busca" value={buscaTutor} onChange={(e) => setBuscaTutor(e.target.value)} placeholder="Nome ou telefone" className="input" />
                  {tutores.length > 0 && (
                    <div className="mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
                      {tutores.flatMap((t) =>
                        t.pets.map((p) => (
                          <button key={`${t.telefone}-${p.nome}`} type="button" onClick={() => escolher(t, p)} className="cursor-pointer rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200 hover:bg-sky-100">
                            {p.nome} · {t.nome}
                          </button>
                        )),
                      )}
                    </div>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="label" htmlFor="tn">Nome do tutor</label>
                    <input id="tn" required value={tutorNome} onChange={(e) => setTutorNome(e.target.value)} className="input" />
                  </div>
                  <div>
                    <label className="label" htmlFor="tt">WhatsApp (DDD + número)</label>
                    <input id="tt" required value={tutorTelefone} onChange={(e) => setTutorTelefone(e.target.value)} placeholder="(62) 99999-8888" className="input" />
                  </div>
                  <div>
                    <label className="label" htmlFor="pn">Nome do pet</label>
                    <input id="pn" required value={petNome} onChange={(e) => setPetNome(e.target.value)} className="input" />
                  </div>
                  <div>
                    <label className="label" htmlFor="md">Veterinário</label>
                    <select id="md" value={idMedicoNovo} onChange={(e) => setIdMedicoNovo(Number(e.target.value))} className="input">
                      {medicos.map((m) => <option key={m.id_medico} value={m.id_medico}>{m.nome}</option>)}
                    </select>
                  </div>
                </div>

                <details className="group rounded-2xl border border-slate-200 p-4">
                  <summary className="cursor-pointer list-none text-sm font-semibold text-ink">
                    Dados do pet <span className="font-normal text-ink-soft">(espécie, raça, peso… opcional)</span>
                  </summary>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div>
                      <label className="label" htmlFor="pe">Espécie</label>
                      <select id="pe" value={petEspecie} onChange={(e) => setPetEspecie(e.target.value)} className="input">
                        <option>Cão</option><option>Gato</option>
                      </select>
                    </div>
                    <div>
                      <label className="label" htmlFor="pr">Raça</label>
                      <input id="pr" value={petRaca} onChange={(e) => setPetRaca(e.target.value)} className="input" />
                    </div>
                    <div>
                      <label className="label" htmlFor="ps">Sexo</label>
                      <select id="ps" value={petSexo} onChange={(e) => setPetSexo(e.target.value as typeof petSexo)} className="input">
                        <option>Macho</option><option>Fêmea</option><option>Não informado</option>
                      </select>
                    </div>
                    <div>
                      <label className="label" htmlFor="pi">Idade</label>
                      <input id="pi" value={petIdade} onChange={(e) => setPetIdade(e.target.value)} className="input" />
                    </div>
                    <div>
                      <label className="label" htmlFor="pk">Peso (kg)</label>
                      <input id="pk" value={petPeso} onChange={(e) => setPetPeso(e.target.value)} placeholder="12,5" className="input" />
                    </div>
                    <div>
                      <label className="label" htmlFor="pp">Porte</label>
                      <select id="pp" value={petPorte} onChange={(e) => setPetPorte(e.target.value as typeof petPorte)} className="input">
                        <option value="">Não informado</option><option>Mini</option><option>Pequeno</option>
                        <option>Médio</option><option>Grande</option><option>Gigante</option>
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="label" htmlFor="pc">Status reprodutivo</label>
                      <select id="pc" value={petRepro} onChange={(e) => setPetRepro(e.target.value as typeof petRepro)} className="input">
                        <option value="">Não informado</option><option>Castrado</option><option>Inteiro</option>
                      </select>
                    </div>
                  </div>
                </details>

                <div className="flex justify-end gap-2 pt-1">
                  <button type="button" onClick={() => setModalAberto(false)} className="btn-ghost">Cancelar</button>
                  <button type="submit" disabled={salvando} className="btn-primary">
                    {salvando ? 'Agendando…' : 'Agendar e gerar link'}
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
