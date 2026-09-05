import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../stores/auth';
import LoginForm from '../../components/ui/LoginForm';

export default function Auth() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login, signup, user, checkAuth } = useAuthStore();
  const [mode, setMode] = useState<'login' | 'signup'>(searchParams.get('mode') === 'login' ? 'login' : 'signup');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => { checkAuth().finally(() => setChecking(false)); }, []);
  useEffect(() => { if (!checking && user) navigate('/done'); }, [user, checking]);
  useEffect(() => { setMode(searchParams.get('mode') === 'login' ? 'login' : 'signup'); }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'signup' && password !== confirm) { setError('Passwords do not match.'); return; }
    if (password.length < 6) { setError('Password needs at least 6 characters.'); return; }
    setLoading(true);
    try {
      if (mode === 'login') await login(email, password);
      else await signup(email, password, displayName);
      navigate('/done');
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  if (checking) return <div className="min-h-screen flex items-center justify-center bg-white dark:bg-black text-gray-500">Checking session…</div>;

  return (
    <LoginForm
      mode={mode}
      onToggleMode={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}
      onSubmit={handleSubmit}
      error={error}
      loading={loading}
      email={email} setEmail={setEmail}
      password={password} setPassword={setPassword}
      confirm={confirm} setConfirm={setConfirm}
      displayName={displayName} setDisplayName={setDisplayName}
    />
  );
}
