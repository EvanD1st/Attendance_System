import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import App from './App';

describe('Attendance Control portal', () => {
  beforeEach(() => localStorage.clear());

  it('shows the sign-in and kiosk entry actions', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole('heading', { name: 'Sign in to your workspace' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pair a kiosk display' })).toHaveAttribute(
      'href',
      '/kiosk',
    );
  });

  it('shows kiosk pairing fields without authentication', async () => {
    render(
      <MemoryRouter initialEntries={['/kiosk']}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: 'Pair this display' })).toBeInTheDocument();
    expect(screen.getByLabelText('Device ID')).toBeInTheDocument();
  });
});
