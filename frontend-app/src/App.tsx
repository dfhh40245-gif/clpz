import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/auth';
import Landing from './pages/public/Landing';
import Auth from './pages/public/Auth';
import Done from './pages/app/Done';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, desktopMode } = useAuthStore();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading…</div>;
  if (!desktopMode && !user) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}

export default function App() {
  const { checkAuth } = useAuthStore();
  useEffect(() => { checkAuth(); }, []);

  return (
    <BrowserRouter basename="/new">
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/auth" element={<Auth />} />
        <Route path="/done" element={<ProtectedRoute><Done /></ProtectedRoute>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
