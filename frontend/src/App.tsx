import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, ROTA_POR_PAPEL, useAuth } from './context/AuthContext'
import { TopBar } from './components/TopBar'
import { LoginPage } from './pages/LoginPage'

function RotaProtegida({ children }: { children: React.ReactNode }) {
  const { sessao } = useAuth()
  if (!sessao) return <Navigate to="/login" replace />
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <TopBar />
      <div className="flex-1">{children}</div>
    </div>
  )
}

function RedirecionadorRaiz() {
  const { sessao } = useAuth()
  if (!sessao) return <Navigate to="/login" replace />
  return <Navigate to={ROTA_POR_PAPEL[sessao.usuario.papel]} replace />
}

function PlaceholderOperacional({ titulo }: { titulo: string }) {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900">{titulo}</h1>
      </div>
    </main>
  )
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/recepcao"
            element={
              <RotaProtegida>
                <PlaceholderOperacional titulo="Painel Operacional da Recepção" />
              </RotaProtegida>
            }
          />
          <Route
            path="/medico"
            element={
              <RotaProtegida>
                <PlaceholderOperacional titulo="Cockpit do Médico Veterinário" />
              </RotaProtegida>
            }
          />
          <Route
            path="/gestao"
            element={
              <RotaProtegida>
                <PlaceholderOperacional titulo="Dashboard Executivo B2B (BI & ROI)" />
              </RotaProtegida>
            }
          />
          <Route path="*" element={<RedirecionadorRaiz />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
