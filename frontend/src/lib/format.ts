/** Formatação e utilitários de apresentação (pt-BR). */

export function semAcento(t: string): string {
  return t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

export function formatarHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function formatarDataHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export function formatarTelefone(tel: string): string {
  const d = tel.replace(/\D/g, '').replace(/^55(?=\d{10,11}$)/, '')
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return tel
}

export function formatarMoeda(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function formatarNumero(v: number, casas = 1): string {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: casas })
}

/** mm:ss (ou h:mm:ss) a partir de segundos. */
export function formatarCronometro(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  const mm = String(m).padStart(2, '0')
  const sss = String(ss).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${sss}` : `${mm}:${sss}`
}

/** Token do link único: último segmento de /t/:token. */
export function tokenDoLink(link: string): string {
  return link.replace(/\/+$/, '').split('/').pop() ?? ''
}

/** Link do simulador do tutor na origem ATUAL (independe de FRONTEND_BASE_URL do backend). */
export function linkTutorLocal(link: string): string {
  return `${window.location.origin}/t/${tokenDoLink(link)}`
}

export function idadeLegivel(t: string): string {
  return t && t !== 'Não informada' ? t : 'idade n/i'
}

export function descricaoPet(p: {
  especie: string
  raca: string
  peso_kg: number | null
  porte: string | null
  status_reprodutivo: string | null
}): string {
  const partes = [p.especie, p.raca]
  if (p.peso_kg != null) partes.push(`${formatarNumero(p.peso_kg, 2)} kg`)
  if (p.porte) partes.push(`porte ${p.porte.toLowerCase()}`)
  if (p.status_reprodutivo) partes.push(p.status_reprodutivo.toLowerCase())
  return partes.join(' · ')
}

export function classes(...c: (string | false | null | undefined)[]): string {
  return c.filter(Boolean).join(' ')
}
