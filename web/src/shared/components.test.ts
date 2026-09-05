import { describe, expect, it } from 'vitest';
import { toLocalInput } from './components';

describe('correction time conversion', () => {
  it('uses local wall-clock time, not the UTC substring', () => {
    const instant = '2026-09-01T08:15:00Z';
    const date = new Date(instant);
    const value = toLocalInput(instant);
    const pad = (number: number) => String(number).padStart(2, '0');
    expect(value).toBe(
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`,
    );
    expect(new Date(value).toISOString()).toBe('2026-09-01T08:15:00.000Z');
  });

  it('keeps missing punches empty', () => expect(toLocalInput(null)).toBe(''));
});
