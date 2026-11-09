import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, ROTA_POR_PAPEL, useAuth } from './context/AuthContext'
import { TopBar } from './components/TopBar'
import { GestaoPage } from './pages/GestaoPage'
import { LoginPage } from './pages/LoginPage'
import { MedicoPage } from './pages/MedicoPage'
import { RecepcaoPage } from './pages/RecepcaoPage'
import { TutorWizardPage } from './pages/TutorWizardPage'

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

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/t/:token" element={<TutorWizardPage />} />
          <Route
            path="/recepcao"
            element={
              <RotaProtegida>
                <RecepcaoPage />
              </RotaProtegida>
            }
          />
          <Route
            path="/medico"
            element={
              <RotaProtegida>
                <MedicoPage />
              </RotaProtegida>
            }
          />
          <Route
            path="/gestao"
            element={
              <RotaProtegida>
                <GestaoPage />
              </RotaProtegida>
            }
          />
          <Route path="*" element={<RedirecionadorRaiz />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
