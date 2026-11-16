import type { CorPrioridade } from '../types'

export interface EstiloManchester {
  cor: CorPrioridade
  rotulo: string
  nivel: string
  /** Badge pastel de alto contraste (uso geral). */
  badge: string
  /** Indicador luminoso discreto. */
  dot: string
  /** Barras de gráfico. */
  barra: string
  /** Faixa lateral de destaque nos itens de lista. */
  faixa: string
  hex: string
}

/** Protocolo de Manchester — cores harmonizadas (pastel + dot). Sólido vivo só no alarme real. */
export const MANCHESTER: Record<CorPrioridade, EstiloManchester> = {
  VERMELHO: {
    cor: 'VERMELHO', rotulo: 'Emergência', nivel: 'EMERGENCIA',
    badge: 'bg-red-50 text-red-800 ring-red-200', dot: 'bg-red-500', barra: 'bg-red-500',
    faixa: 'border-l-red-500', hex: '#ef4444',
  },
  LARANJA: {
    cor: 'LARANJA', rotulo: 'Muito urgente', nivel: 'MUITO_URGENTE',
    badge: 'bg-orange-50 text-orange-800 ring-orange-200', dot: 'bg-orange-500', barra: 'bg-orange-400',
    faixa: 'border-l-orange-400', hex: '#fb923c',
  },
  AMARELO: {
    cor: 'AMARELO', rotulo: 'Urgente', nivel: 'URGENTE',
    badge: 'bg-amber-50 text-amber-800 ring-amber-200', dot: 'bg-amber-400', barra: 'bg-amber-300',
    faixa: 'border-l-amber-400', hex: '#fcd34d',
  },
  VERDE: {
    cor: 'VERDE', rotulo: 'Pouco urgente', nivel: 'POUCO_URGENTE',
    badge: 'bg-emerald-50 text-emerald-800 ring-emerald-200', dot: 'bg-emerald-500', barra: 'bg-emerald-400',
    faixa: 'border-l-emerald-400', hex: '#34d399',
  },
  AZUL: {
    cor: 'AZUL', rotulo: 'Não urgente', nivel: 'NAO_URGENTE',
    badge: 'bg-sky-50 text-sky-800 ring-sky-200', dot: 'bg-sky-500', barra: 'bg-sky-400',
    faixa: 'border-l-sky-400', hex: '#38bdf8',
  },
}

const ORDEM: Record<CorPrioridade, number> = { VERMELHO: 0, LARANJA: 1, AMARELO: 2, VERDE: 3, AZUL: 4 }

/** Menor número = mais grave. Sem triagem (cor nula) fica depois do AZUL. */
export function pesoManchester(cor: CorPrioridade | null | undefined): number {
  return cor ? ORDEM[cor] : 5
}
