import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { AuthProvider, useAuth } from './context/AuthContext';
import { FilterProvider } from './context/FilterContext';
import { AdminPage } from './pages/AdminPage';
import { DataCapturePage } from './pages/DataCapturePage';
import { ExecutiveDashboardPage } from './pages/ExecutiveDashboardPage';
import { GlymphaticPage } from './pages/GlymphaticPage';
import { HabitsCorrelationPage } from './pages/HabitsCorrelationPage';
import { LoginPage } from './pages/LoginPage';
import { ParticipantProfilePage } from './pages/ParticipantProfilePage';
import { ReportsPage } from './pages/ReportsPage';
import { SubjectiveQualityPage } from './pages/SubjectiveQualityPage';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f6f8fa] text-[13px] text-[#5a6877]">
        Verificando sesión...
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

export function App() {
  return (
    <AuthProvider>
      <FilterProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<ExecutiveDashboardPage />} />
              <Route path="calidad-psqi" element={<SubjectiveQualityPage />} />
              <Route path="limpieza-cerebral" element={<GlymphaticPage />} />
              <Route path="habitos" element={<HabitsCorrelationPage />} />
              <Route path="participantes" element={<ParticipantProfilePage />} />
              <Route path="captura" element={<DataCapturePage />} />
              <Route path="reportes" element={<ReportsPage />} />
              <Route path="admin" element={<AdminPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </FilterProvider>
    </AuthProvider>
  );
}

export default App;
