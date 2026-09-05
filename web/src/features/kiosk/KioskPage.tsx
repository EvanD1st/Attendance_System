import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ArrowLeft, Clock3, LoaderCircle, Smartphone, Unplug } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { isAxiosError } from 'axios';
import { Link } from 'react-router-dom';
import { kioskApi as api, errorMessage } from '../../api';
export function KioskPage() {
  const [deviceId, setDeviceId] = useState(localStorage.getItem('kiosk_device_id') || '');
  const [credential, setCredential] = useState(localStorage.getItem('kiosk_credential') || '');
  const [pairingCode, setPairingCode] = useState('');
  const [token, setToken] = useState('');
  const [site, setSite] = useState('');
  const [expires, setExpires] = useState(0);
  const [error, setError] = useState('');
  const paired = Boolean(deviceId && credential);
  const loadQr = useCallback(async () => {
    if (!deviceId || !credential) return;
    try {
      const { data } = await api.get(`/kiosk/devices/${deviceId}/qr/`, {
        headers: { 'X-Kiosk-Credential': credential },
      });
      setToken(data.qr_token);
      setSite(data.site.name);
      setExpires(data.expires_in_seconds);
      setError('');
    } catch (cause) {
      if (isAxiosError(cause) && cause.response?.status === 401) {
        localStorage.removeItem('kiosk_credential');
        setCredential('');
        setToken('');
        setError('This kiosk was revoked or its credential is invalid. Enter a new pairing code.');
        return;
      }
      setError(errorMessage(cause));
      setToken('');
    }
  }, [credential, deviceId]);
  useEffect(() => {
    if (!paired) return;
    void loadQr();
    const refresh = window.setInterval(() => void loadQr(), 45000);
    return () => window.clearInterval(refresh);
  }, [loadQr, paired]);
  useEffect(() => {
    if (!expires) return;
    const timer = window.setInterval(() => setExpires((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [expires > 0]);
  async function pair(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const { data } = await api.post('/kiosk/pair/', {
        device_id: deviceId,
        pairing_code: pairingCode,
      });
      localStorage.setItem('kiosk_device_id', data.device_id);
      localStorage.setItem('kiosk_credential', data.credential);
      setDeviceId(data.device_id);
      setCredential(data.credential);
      setSite(data.site.name);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  function reset() {
    localStorage.removeItem('kiosk_device_id');
    localStorage.removeItem('kiosk_credential');
    setCredential('');
    setToken('');
  }
  if (!paired)
    return (
      <main className="kiosk-shell">
        <Link className="kiosk-back" to="/login">
          <ArrowLeft /> Portal sign in
        </Link>
        <form className="pair-card" onSubmit={pair}>
          <div className="icon-box">
            <Smartphone />
          </div>
          <p className="eyebrow">KIOSK SETUP</p>
          <h1>Pair this display</h1>
          <p>Enter the device ID and one-time code created by an administrator.</p>
          {error && <div className="alert error">{error}</div>}
          <label>
            Device ID
            <input value={deviceId} onChange={(e) => setDeviceId(e.target.value)} required />
          </label>
          <label>
            Pairing code
            <input
              className="code-input"
              value={pairingCode}
              onChange={(e) => setPairingCode(e.target.value)}
              inputMode="numeric"
              maxLength={6}
              required
            />
          </label>
          <button className="primary">Pair kiosk</button>
        </form>
      </main>
    );
  return (
    <main className="kiosk-display">
      <header>
        <div className="brand-mark">
          <Clock3 /> AC
        </div>
        <button onClick={reset}>
          <Unplug size={17} /> Unpair
        </button>
      </header>
      <section className="qr-card">
        <p className="eyebrow">{site.toUpperCase()}</p>
        <h1>Scan to record attendance</h1>
        <p>Open Attendance Control on your phone and scan this secure code.</p>
        <div className="qr-frame">
          {token ? (
            <QRCodeSVG value={token} size={280} level="H" />
          ) : (
            <LoaderCircle className="spin" size={50} />
          )}
        </div>
        {error ? (
          <div className="alert error">{error}</div>
        ) : (
          <div className="expiry">
            <span style={{ width: `${(expires / 60) * 100}%` }} />
            <strong>{expires}s</strong>
          </div>
        )}
        <small>The code refreshes automatically.</small>
      </section>
    </main>
  );
}
