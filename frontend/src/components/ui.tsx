import { Stethoscope } from 'lucide-react'
import { classes } from '../lib/format'
import { MANCHESTER } from '../lib/manchester'
import type { CorPrioridade } from '../types'

/** Badge Manchester pastel com dot luminoso. `cor` nula = triagem ainda não preenchida. */
export function ManchesterBadge({
  cor,
  compacto = false,
}: {
  cor: CorPrioridade | null | undefined
  compacto?: boolean
}) {
  if (!cor) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
        Sem triagem
      </span>
    )
  }
  const m = MANCHESTER[cor]
  return (
    <span
      className={classes(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset',
        m.badge,
      )}
    >
      <span className={classes('h-1.5 w-1.5 rounded-full', m.dot)} />
      {compacto ? m.cor.charAt(0) + m.cor.slice(1).toLowerCase() : `${m.rotulo}`}
    </span>
  )
}

/** Emblema institucional da clínica: logo_url (se houver) ou iniciais sobre gradiente. */
export function ClinicAvatar({
  nome,
  logoUrl,
  className = 'h-12 w-12 text-base',
}: {
  nome: string
  logoUrl?: string | null
  className?: string
}) {
  const iniciais = nome
    .split(/\s+/)
    .filter((p) => p.length > 2)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={nome}
        className={classes('rounded-2xl border border-slate-200 bg-white object-contain p-1', className)}
      />
    )
  }
  return (
    <span
      className={classes(
        'relative inline-flex shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-sky-700 font-extrabold text-white shadow-sm',
        className,
      )}
      aria-label={nome}
    >
      {iniciais || <Stethoscope className="h-1/2 w-1/2" />}
    </span>
  )
}

/** Pílula compacta de indicador (valor + rótulo). */
export function Pilula({
  valor,
  rotulo,
  tom = 'slate',
}: {
  valor: number | string
  rotulo: string
  tom?: 'slate' | 'brand' | 'amber' | 'red' | 'emerald'
}) {
  const tons: Record<string, string> = {
    slate: 'bg-white text-slate-700 ring-slate-200',
    brand: 'bg-brand-soft text-sky-800 ring-sky-200',
    amber: 'bg-amber-50 text-amber-800 ring-amber-200',
    red: 'bg-red-50 text-red-800 ring-red-200',
    emerald: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  }
  return (
    <span
      className={classes(
        'inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium ring-1 ring-inset',
        tons[tom],
      )}
    >
      <span className="text-base font-extrabold leading-none">{valor}</span>
      {rotulo}
    </span>
  )
}

/** Botão de ícone discreto com tooltip nativo. */
export function IconButton({
  titulo,
  onClick,
  children,
  perigo = false,
}: {
  titulo: string
  onClick: () => void
  children: React.ReactNode
  perigo?: boolean
}) {
  return (
    <button
      type="button"
      title={titulo}
      aria-label={titulo}
      onClick={onClick}
      className={classes(
        'inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl border border-transparent text-slate-500 transition hover:border-slate-200 hover:bg-slate-50',
        perigo ? 'hover:text-red-600' : 'hover:text-brand',
      )}
    >
      {children}
    </button>
  )
}
