import { useEffect, type ReactNode } from 'react';
import { BarChart3, Clock3, LogOut, MapPinned, Menu, Settings2, Users, X } from 'lucide-react';
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth';
import {
  ChangePasswordPage,
  ConfigurationPage,
  DashboardPage,
  KioskPage,
  LoginPage,
  PeoplePage,
  RecordsPage,
} from './pages';
import { registerAttendanceTools } from './webmcp';

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="app-loader">
        <Clock3 className="spin" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && location.pathname !== '/change-password')
    return <Navigate to="/change-password" replace />;
  return children;
}

function PortalLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [first, last] = [user?.first_name || '', user?.last_name || ''];
  useEffect(() => registerAttendanceTools(user?.role === 'admin'), [user?.role]);
  return (
    <div className="portal-shell">
      <input type="checkbox" id="nav-toggle" className="nav-toggle" />
      <aside className="sidebar">
        <div className="brand-mark">
          <Clock3 size={23} /> AC
        </div>
        <label htmlFor="nav-toggle" className="close-nav">
          <X />
        </label>
        <nav>
          <NavLink to="/dashboard">
            <BarChart3 /> Overview
          </NavLink>
          <NavLink to="/records">
            <Clock3 /> Attendance
          </NavLink>
          <NavLink to="/people">
            <Users /> People
          </NavLink>
          {user?.role === 'admin' && (
            <NavLink to="/configuration">
              <Settings2 /> Configuration
            </NavLink>
          )}
          <NavLink to="/kiosk">
            <MapPinned /> Kiosk display
          </NavLink>
        </nav>
        <div className="sidebar-user">
          <div className="avatar small">
            {first[0]}
            {last[0]}
          </div>
          <div>
            <strong>{`${first} ${last}`.trim() || user?.email}</strong>
            <span>{user?.role}</span>
          </div>
          <button aria-label="Sign out" onClick={() => void logout()}>
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="portal-main">
        <div className="mobile-bar">
          <label htmlFor="nav-toggle">
            <Menu />
          </label>
          <div className="brand-mark">
            <Clock3 size={20} /> AC
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route
        path="/login"
        element={
          user ? (
            <Navigate to={user.must_change_password ? '/change-password' : '/dashboard'} replace />
          ) : (
            <LoginPage />
          )
        }
      />
      <Route path="/kiosk" element={<KioskPage />} />
      <Route
        path="/change-password"
        element={
          <Protected>
            <ChangePasswordPage />
          </Protected>
        }
      />
      <Route
        path="/dashboard"
        element={
          <Protected>
            <PortalLayout>
              <DashboardPage />
            </PortalLayout>
          </Protected>
        }
      />
      <Route
        path="/records"
        element={
          <Protected>
            <PortalLayout>
              <RecordsPage />
            </PortalLayout>
          </Protected>
        }
      />
      <Route
        path="/people"
        element={
          <Protected>
            <PortalLayout>
              <PeoplePage />
            </PortalLayout>
          </Protected>
        }
      />
      <Route
        path="/configuration"
        element={
          <Protected>
            {user?.role === 'admin' ? (
              <PortalLayout>
                <ConfigurationPage />
              </PortalLayout>
            ) : (
              <Navigate to="/dashboard" replace />
            )}
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
