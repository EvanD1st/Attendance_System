import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({
  user: null as null | {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
    role: 'admin' | 'manager' | 'employee';
    must_change_password: boolean;
  },
}));

vi.mock('./auth', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    user: authState.user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
  }),
}));

vi.mock('./api', () => ({
  api: {
    get: vi.fn(async (path: string) => ({
      data: path.includes('/summary/')
        ? {
            present: 0,
            late: 0,
            absent: 0,
            excused: 0,
            attendance_rate: 0,
            missing_clock_out: 0,
            rejected_attempts: 0,
          }
        : { count: 0, next: null, previous: null, results: [] },
    })),
    post: vi.fn(),
  },
  downloadAttendance: vi.fn(),
  errorMessage: () => 'Request failed.',
}));

import App from './App';

const user = (role: 'admin' | 'manager' | 'employee', mustChange = false) => ({
  id: 1,
  email: `${role}@attendance.local`,
  first_name: 'Test',
  last_name: 'User',
  role,
  must_change_password: mustChange,
});

describe('portal permissions', () => {
  beforeEach(() => {
    authState.user = null;
  });

  it('redirects a manager away from administrator configuration', async () => {
    authState.user = user('manager');
    render(
      <MemoryRouter initialEntries={['/configuration']}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: 'Today at a glance' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Configuration' })).not.toBeInTheDocument();
  });

  it('shows administrator configuration controls', async () => {
    authState.user = user('admin');
    render(
      <MemoryRouter initialEntries={['/configuration']}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: 'Configuration' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'sites' })).toBeInTheDocument();
  });

  it('does not show employee creation to managers', async () => {
    authState.user = user('manager');
    render(
      <MemoryRouter initialEntries={['/people']}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: 'People and access' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /add employee/i })).not.toBeInTheDocument();
  });

  it('forces a temporary-password user into the password-change flow', async () => {
    authState.user = user('employee', true);
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole('heading', { name: 'Set your permanent password' }),
    ).toBeInTheDocument();
  });
});
