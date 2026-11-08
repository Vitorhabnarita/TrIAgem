import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, gravarSessao, lerSessao } from '../lib/api'
import type { Papel, Sessao } from '../types'

interface AuthContextValue {
  sessao: Sessao | null
  carregando: boolean
  login: (email: string, senha: string) => Promise<Sessao>
  loginDemo: (papel: Papel) => Promise<Sessao>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export const ROTA_POR_PAPEL: Record<Papel, string> = {
  recepcao: '/recepcao',
  medico: '/medico',
  gestor: '/gestao',
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(() => lerSessao())
  const [carregando, setCarregando] = useState(false)

  useEffect(() => {
    const onExpirada = () => setSessao(null)
    window.addEventListener('triagem:sessao-expirada', onExpirada)
    return () => window.removeEventListener('triagem:sessao-expirada', onExpirada)
  }, [])

  const login = useCallback(async (email: string, senha: string): Promise<Sessao> => {
    setCarregando(true)
    try {
      const nova = await api<Sessao>('/auth/login', {
        method: 'POST',
        body: { email, senha },
        auth: false,
      })
      gravarSessao(nova)
      setSessao(nova)
      return nova
    } finally {
      setCarregando(false)
    }
  }, [])

  const loginDemo = useCallback(async (papel: Papel): Promise<Sessao> => {
    setCarregando(true)
    try {
      const nova = await api<Sessao>(`/auth/demo/${papel}`, {
        method: 'POST',
        auth: false,
      })
      gravarSessao(nova)
      setSessao(nova)
      return nova
    } finally {
      setCarregando(false)
    }
  }, [])

  const logout = useCallback(() => {
    gravarSessao(null)
    setSessao(null)
  }, [])

  return (
    <AuthContext.Provider value={{ sessao, carregando, login, loginDemo, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
