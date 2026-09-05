import { useState, type FormEvent } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  KeyRound,
  LoaderCircle,
  MapPin,
  ShieldCheck,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api';
import { useAuth } from '../../auth';
export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@attendance.local');
  const [password, setPassword] = useState('DemoAdmin!2026');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const user = await login(email, password);
      navigate(user.must_change_password ? '/change-password' : '/dashboard');
    } catch (cause) {
      setError(errorMessage(cause, 'Unable to sign in.'));
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <main className="login-shell">
      <section className="login-story" aria-label="Attendance Control overview">
        <div className="brand-mark">
          <Clock3 size={25} /> AC
        </div>
        <div className="story-copy">
          <p className="eyebrow">ATTENDANCE CONTROL</p>
          <h1>
            Every shift,
            <br />
            accounted for.
          </h1>
          <p>Secure QR attendance with site-aware GPS verification and a clear audit trail.</p>
        </div>
        <div className="trust-row">
          <span>
            <ShieldCheck size={18} /> Site-bound QR
          </span>
          <span>
            <MapPin size={18} /> Verified location
          </span>
          <span>
            <CheckCircle2 size={18} /> Audited corrections
          </span>
        </div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in to your workspace</h2>
          {error && (
            <div className="alert error">
              <AlertTriangle size={17} /> {error}
            </div>
          )}
          <label>
            Email address
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button disabled={submitting}>
            {submitting ? (
              <LoaderCircle className="spin" />
            ) : (
              <>
                Sign in <KeyRound size={18} />
              </>
            )}
          </button>
          <Link to="/kiosk">Pair a kiosk display</Link>
        </form>
      </section>
    </main>
  );
}

export function ChangePasswordPage() {
  const { changePassword } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (form.next !== form.confirm) {
      setError('New passwords do not match.');
      return;
    }
    try {
      await changePassword(form.current, form.next);
      navigate('/dashboard');
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  return (
    <main className="center-page">
      <form className="modal-card" onSubmit={submit}>
        <div className="icon-box">
          <KeyRound />
        </div>
        <p className="eyebrow">ACCOUNT SECURITY</p>
        <h1>Set your permanent password</h1>
        <p>Your temporary password must be replaced before attendance can be recorded.</p>
        {error && <div className="alert error">{error}</div>}
        <label>
          Current password
          <input
            type="password"
            value={form.current}
            onChange={(e) => setForm({ ...form, current: e.target.value })}
            required
          />
        </label>
        <label>
          New password
          <input
            type="password"
            value={form.next}
            onChange={(e) => setForm({ ...form, next: e.target.value })}
            required
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            required
          />
        </label>
        <button className="primary">Save password</button>
      </form>
    </main>
  );
}
