import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';

// Lazy-load pages to improve initial bundle size
import Login         from './pages/Login';
import Dashboard     from './pages/Dashboard';
import Patients      from './pages/Patients';
import PatientDetail from './pages/PatientDetail';
import Records       from './pages/Records';
import EncryptionLab from './pages/EncryptionLab';
import AuditTrail    from './pages/AuditTrail';
import UserManagement from './pages/UserManagement';
import Exchange      from './pages/Exchange';
import Settings      from './pages/Settings';
import Timeline      from './pages/Timeline';

// Layout shell — sidebar + header + main content
function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      <div className="ml-64">
        <Header />
        <main className="pt-20 min-h-screen">
          <div className="p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

// Redirects to /login if not authenticated
function ProtectedRoute() {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

// Admin-only guard
function AdminRoute() {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role !== 'admin') return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

export default function App() {
  useEffect(() => {
    useAuthStore.getState().initialize();
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<Login />} />

        {/* Protected — rendered inside Layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard"  element={<Dashboard />} />
            <Route path="/patients"   element={<Patients />} />
            <Route path="/patients/:id" element={<PatientDetail />} />
            <Route path="/records"    element={<Records />} />
            <Route path="/timeline"   element={<Timeline />} />
            <Route path="/exchange"   element={<Exchange />} />
            <Route path="/encryption" element={<EncryptionLab />} />
            <Route path="/settings"   element={<Settings />} />

            {/* Admin only */}
            <Route element={<AdminRoute />}>
              <Route path="/audit"    element={<AuditTrail />} />
              <Route path="/users"    element={<UserManagement />} />
            </Route>
          </Route>
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
