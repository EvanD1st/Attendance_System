import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { kioskApi } from '../../api';
import { KioskPage } from './KioskPage';

vi.mock('../../api', () => ({
  kioskApi: { get: vi.fn(), post: vi.fn() },
  errorMessage: () => 'Network unavailable',
}));
vi.mock('qrcode.react', () => ({
  QRCodeSVG: ({ value }: { value: string }) => <div data-testid="qr">{value}</div>,
}));

const qr = (token: string, seconds = 60) => ({
  data: { qr_token: token, expires_in_seconds: seconds, site: { name: 'HQ' } },
});
async function show(paired = true) {
  if (paired) {
    localStorage.setItem('kiosk_device_id', 'device');
    localStorage.setItem('kiosk_credential', 'credential');
  }
  await act(async () => {
    render(
      <MemoryRouter>
        <KioskPage />
      </MemoryRouter>,
    );
  });
}

describe('kiosk lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => vi.useRealTimers());

  it('pairs independently and displays the fetched QR', async () => {
    vi.mocked(kioskApi.post).mockResolvedValue({
      data: { device_id: 'device', credential: 'new', site: { name: 'HQ' } },
    });
    vi.mocked(kioskApi.get).mockResolvedValue(qr('first'));
    await show(false);
    fireEvent.change(screen.getByLabelText('Device ID'), { target: { value: 'device' } });
    fireEvent.change(screen.getByLabelText('Pairing code'), { target: { value: '123456' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Pair kiosk' }));
    });
    expect(localStorage.getItem('kiosk_credential')).toBe('new');
    expect(screen.getByTestId('qr')).toHaveTextContent('first');
  });

  it('refreshes according to the server lifetime, including short lifetimes', async () => {
    vi.mocked(kioskApi.get)
      .mockResolvedValueOnce(qr('first', 8))
      .mockResolvedValue(qr('second', 8));
    await show();
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(kioskApi.get).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('qr')).toHaveTextContent('second');
  });

  it('hides expired QR codes when a refresh is stalled', async () => {
    vi.mocked(kioskApi.get)
      .mockResolvedValueOnce(qr('first', 4))
      .mockReturnValueOnce(new Promise(() => {}));
    await show();
    await act(async () => vi.advanceTimersByTimeAsync(5000));
    expect(screen.queryByTestId('qr')).not.toBeInTheDocument();
  });

  it('clears revoked credentials without clearing the portal session', async () => {
    localStorage.setItem('attendance_access', 'portal-session');
    vi.mocked(kioskApi.get).mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
    await show();
    expect(screen.getByRole('heading', { name: 'Pair this display' })).toBeInTheDocument();
    expect(localStorage.getItem('kiosk_credential')).toBeNull();
    expect(localStorage.getItem('attendance_access')).toBe('portal-session');
  });

  it('does not revive a display when a fetch completes after unpairing', async () => {
    let resolve!: (value: ReturnType<typeof qr>) => void;
    vi.mocked(kioskApi.get).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    await show();
    fireEvent.click(screen.getByRole('button', { name: 'Unpair' }));
    await act(async () => resolve(qr('late')));
    expect(screen.getByRole('heading', { name: 'Pair this display' })).toBeInTheDocument();
    expect(screen.queryByTestId('qr')).not.toBeInTheDocument();
  });
});
