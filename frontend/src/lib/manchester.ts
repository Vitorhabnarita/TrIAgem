import type { CorPrioridade } from '../types'

export interface EstiloManchester {
  cor: CorPrioridade
  rotulo: string
  nivel: string
  /** Classes Tailwind (literais, para o JIT enxergar). */
  fundo: string
  fundoSuave: string
  borda: string
  texto: string
  ponto: string
  barra: string
  hex: string
}

/** Protocolo de Manchester — cores semânticas de risco. */
export const MANCHESTER: Record<CorPrioridade, EstiloManchester> = {
  VERMELHO: {
    cor: 'VERMELHO', rotulo: 'Emergência', nivel: 'EMERGENCIA',
    fundo: 'bg-red-600 text-white', fundoSuave: 'bg-red-50', borda: 'border-red-500',
    texto: 'text-red-700', ponto: 'bg-red-600', barra: 'bg-red-600', hex: '#dc2626',
  },
  LARANJA: {
    cor: 'LARANJA', rotulo: 'Muito urgente', nivel: 'MUITO_URGENTE',
    fundo: 'bg-orange-500 text-white', fundoSuave: 'bg-orange-50', borda: 'border-orange-400',
    texto: 'text-orange-700', ponto: 'bg-orange-500', barra: 'bg-orange-500', hex: '#f97316',
  },
  AMARELO: {
    cor: 'AMARELO', rotulo: 'Urgente', nivel: 'URGENTE',
    fundo: 'bg-yellow-400 text-yellow-950', fundoSuave: 'bg-yellow-50', borda: 'border-yellow-400',
    texto: 'text-yellow-800', ponto: 'bg-yellow-400', barra: 'bg-yellow-400', hex: '#facc15',
  },
  VERDE: {
    cor: 'VERDE', rotulo: 'Pouco urgente', nivel: 'POUCO_URGENTE',
    fundo: 'bg-green-600 text-white', fundoSuave: 'bg-green-50', borda: 'border-green-500',
    texto: 'text-green-700', ponto: 'bg-green-600', barra: 'bg-green-600', hex: '#16a34a',
  },
  AZUL: {
    cor: 'AZUL', rotulo: 'Não urgente', nivel: 'NAO_URGENTE',
    fundo: 'bg-sky-600 text-white', fundoSuave: 'bg-sky-50', borda: 'border-sky-500',
    texto: 'text-sky-700', ponto: 'bg-sky-600', barra: 'bg-sky-600', hex: '#0284c7',
  },
}

const ORDEM: Record<CorPrioridade, number> = { VERMELHO: 0, LARANJA: 1, AMARELO: 2, VERDE: 3, AZUL: 4 }

/** Menor número = mais grave. Sem triagem (cor nula) fica depois do AZUL. */
export function pesoManchester(cor: CorPrioridade | null | undefined): number {
  return cor ? ORDEM[cor] : 5
}
