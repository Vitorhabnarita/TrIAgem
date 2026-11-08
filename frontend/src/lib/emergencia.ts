import type { GatilhoTexto, SintomaPublico } from '../types'
import { semAcento } from './format'

/** Chaves de categoria do "O que NÃO fazer" — espelham guardrails.PRIMEIROS_SOCORROS_NEGATIVOS. */
export const ROTULO_CATEGORIA: Record<string, string> = {
  INTOXICACAO: 'Intoxicação / Envenenamento',
  NEUROLOGICO: 'Convulsão / Quadro neurológico',
  DISPNEIA: 'Dificuldade respiratória / Engasgo',
  TRAUMA: 'Trauma / Atropelamento',
  HEMORRAGIA: 'Hemorragia',
  GERAL: 'Emergência',
}

export interface GatilhosAtivos {
  /** Categorias distintas (ordem estável) que exigem o card "O que NÃO fazer". */
  categorias: string[]
  /** Descrição humana do que disparou o disjuntor (sintomas marcados e termos digitados). */
  motivos: string[]
  ativo: boolean
}

/**
 * DISJUNTOR RN-001 v2.0 — mesmo critério do servidor:
 *  (a) qualquer sintoma com alerta_urgencia marcado; ou
 *  (b) termo crítico digitado no relato livre (regex normalizada sem acento, fornecida pela API).
 */
export function avaliarGatilhos(
  sintomas: SintomaPublico[],
  marcados: Set<number>,
  relato: string,
  gatilhosTexto: GatilhoTexto[],
): GatilhosAtivos {
  const categorias: string[] = []
  const motivos: string[] = []
  const add = (c: string) => {
    if (!categorias.includes(c)) categorias.push(c)
  }

  for (const s of sintomas) {
    if (s.alerta_urgencia && marcados.has(s.id_sintoma)) {
      add(s.categoria_emergencia ?? 'GERAL')
      motivos.push(s.nome_sintoma)
    }
  }

  const t = semAcento(relato)
  if (t) {
    for (const g of gatilhosTexto) {
      try {
        if (new RegExp(g.padrao).test(t)) {
          add(g.categoria)
          motivos.push(`Relato: "${g.termo}"`)
        }
      } catch {
        /* padrão inválido nunca derruba o formulário */
      }
    }
  }
  return { categorias, motivos, ativo: categorias.length > 0 }
}

/** Assinatura estável do conjunto de gatilhos — reabre o modal só quando surge algo NOVO. */
export function assinatura(g: GatilhosAtivos): string {
  return [...g.categorias].sort().join('|')
}
