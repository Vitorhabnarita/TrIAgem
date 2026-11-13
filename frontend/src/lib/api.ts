import type { Sessao } from '../types'

const STORAGE_KEY = 'triagem.sessao.v1'

function resolverApiUrl(): string {
  const envUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
  if (envUrl) return envUrl
  if (typeof window !== 'undefined' && window.location.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

/** Base da API. Em produção defina VITE_API_URL no build. */
export const API_URL: string = resolverApiUrl()

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function lerSessao(): Sessao | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Sessao) : null
  } catch {
    return null
  }
}

export function gravarSessao(s: Sessao | null): void {
  if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  else localStorage.removeItem(STORAGE_KEY)
}

type Query = Record<string, string | number | boolean | undefined | null>

interface Opcoes {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Query
  /** Envia o Bearer token da sessão (padrão: true). Rotas públicas do tutor usam false. */
  auth?: boolean
  signal?: AbortSignal
}

/** Extrai uma mensagem legível do corpo de erro do FastAPI (string ou lista de erros de validação). */
function mensagemDeErro(corpo: unknown, status: number): string {
  if (corpo && typeof corpo === 'object' && 'detail' in corpo) {
    const d = (corpo as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d
        .map((e) => {
          const item = e as { msg?: string; loc?: (string | number)[] }
          const campo = item.loc?.filter((p) => p !== 'body').join('.')
          return campo ? `${campo}: ${item.msg ?? 'inválido'}` : (item.msg ?? 'inválido')
        })
        .join(' · ')
    }
  }
  if (status === 0) return 'Sem conexão com o servidor. Verifique sua internet e tente novamente.'
  if (status === 429) return 'Muitas requisições. Aguarde um instante e tente novamente.'
  return `Erro inesperado (${status}).`
}

export async function api<T>(caminho: string, op: Opcoes = {}): Promise<T> {
  const { method = 'GET', body, query, auth = true, signal } = op
  const url = new URL(API_URL + caminho)
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    }
  }
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const s = lerSessao()
    if (s) headers.Authorization = `Bearer ${s.access_token}`
  }

  let resp: Response
  try {
    resp = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, mensagemDeErro(null, 0))
  }

  const texto = await resp.text()
  let json: unknown = null
  if (texto) {
    try {
      json = JSON.parse(texto)
    } catch {
      json = null
    }
  }
  if (!resp.ok) {
    // Sessão expirada/inválida em rota autenticada: encerra e volta ao login.
    if (resp.status === 401 && auth) {
      gravarSessao(null)
      window.dispatchEvent(new Event('triagem:sessao-expirada'))
    }
    throw new ApiError(resp.status, mensagemDeErro(json, resp.status))
  }
  return json as T
}
