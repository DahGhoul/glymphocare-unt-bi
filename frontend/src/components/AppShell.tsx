import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  ClipboardEdit,
  FileSpreadsheet,
  GitCompareArrows,
  Layers,
  LogOut,
  Menu,
  Settings,
  UserCheck,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard Ejecutivo', icon: <BarChart3 size={17} strokeWidth={1.75} /> },
  { to: '/calidad-psqi', label: 'Calidad Subjetiva (PSQI)', icon: <Activity size={17} strokeWidth={1.75} /> },
  { to: '/limpieza-cerebral', label: 'Limpieza Cerebral (N3)', icon: <Layers size={17} strokeWidth={1.75} /> },
  { to: '/habitos', label: 'Hábitos y Correlaciones', icon: <GitCompareArrows size={17} strokeWidth={1.75} /> },
  { to: '/participantes', label: 'Perfil e Interpretación IA', icon: <UserCheck size={17} strokeWidth={1.75} /> },
  { to: '/captura', label: 'Captura de Datos / CSV', icon: <ClipboardEdit size={17} strokeWidth={1.75} /> },
  { to: '/reportes', label: 'Reportes y Exportación', icon: <FileSpreadsheet size={17} strokeWidth={1.75} /> },
  { to: '/admin', label: 'Administración y ETL', icon: <Settings size={17} strokeWidth={1.75} />, roles: ['admin'] },
];

export const AppShell: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const visibleNav = NAV_ITEMS.filter(
    (item) => !item.roles || (user && item.roles.includes(user.rol))
  );

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const sidebarContent = (
    <div className="flex flex-col h-full bg-white border-r border-[#dce2ea]">
      <div className="px-4 py-4 border-b border-[#dce2ea]">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[15px] font-bold tracking-tight text-[#14202b]">
              Glympho<span className="text-[#0f766e]">Care</span>
            </div>
            <div className="text-[11px] text-[#5a6877]">UNT · Analítica de Sueño N3</div>
          </div>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            className="md:hidden p-1 text-[#5a6877]"
            aria-label="Cerrar menú"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <nav className="flex-1 px-2.5 py-3 space-y-0.5 overflow-y-auto">
        {visibleNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={() => setDrawerOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors ${
                isActive
                  ? 'bg-[#e6f4f3] text-[#0f766e]'
                  : 'text-[#334155] hover:bg-[#f1f5f9] hover:text-[#14202b]'
              }`
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-[#dce2ea] bg-[#f8fafc]">
        <div className="text-[12px] font-semibold text-[#14202b] truncate">
          {user?.nombre_display}
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-[11px] uppercase font-mono-num px-1.5 py-0.5 rounded bg-white border border-[#dce2ea] text-[#5a6877]">
            {user?.rol}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-1 text-[12px] text-[#5a6877] hover:text-[#b91c1c] cursor-pointer"
          >
            <LogOut size={13} />
            Salir
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-[#f6f8fa]">
      {/* Sidebar fijo en desktop */}
      <aside className="hidden md:block w-[240px] shrink-0 sticky top-0 h-screen">
        {sidebarContent}
      </aside>

      {/* Drawer movil */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div className="w-[260px] h-full shadow-lg">{sidebarContent}</div>
          <div
            className="flex-1 bg-black/30"
            onClick={() => setDrawerOpen(false)}
          />
        </div>
      )}

      {/* Contenido principal */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden sticky top-0 z-30 bg-white border-b border-[#dce2ea] px-4 py-2.5 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="p-1.5 rounded border border-[#dce2ea] text-[#14202b]"
            aria-label="Abrir menú"
          >
            <Menu size={18} />
          </button>
          <span className="text-[14px] font-bold text-[#14202b]">
            Glympho<span className="text-[#0f766e]">Care</span>
          </span>
          <span className="text-[11px] font-mono-num text-[#5a6877]">{user?.rol}</span>
        </header>

        <main className="flex-1 p-4 md:p-6 max-w-[1440px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
