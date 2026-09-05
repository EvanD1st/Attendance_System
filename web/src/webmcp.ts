import { api } from './api';
import type { Summary } from './types';

interface ToolContext {
  registerTool(
    tool: Record<string, unknown>,
    options?: { signal?: AbortSignal },
  ): void | Promise<void>;
}

declare global {
  interface Document {
    modelContext?: ToolContext;
  }
}

export function registerAttendanceTools(isAdmin: boolean) {
  const context = document.modelContext;
  if (!context?.registerTool) return () => undefined;
  const lifecycle = new AbortController();
  void Promise.resolve(
    context.registerTool(
      {
        name: 'read_attendance_summary',
        title: 'Read attendance summary',
        description: 'Read the same current attendance totals shown on the dashboard.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: false },
        async execute() {
          const { data } = await api.get<Summary>('/management/attendance/summary/');
          return data;
        },
      },
      { signal: lifecycle.signal },
    ),
  );
  if (isAdmin)
    void Promise.resolve(
      context.registerTool(
        {
          name: 'create_attendance_exception',
          title: 'Create attendance exception',
          description:
            'Create an excused attendance day for an employee after an administrator supplies the employee ID, date, and reason.',
          inputSchema: {
            type: 'object',
            properties: {
              employee: { type: 'integer' },
              date: { type: 'string', format: 'date' },
              reason: { type: 'string', minLength: 5 },
            },
            required: ['employee', 'date', 'reason'],
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: false },
          async execute(input: unknown) {
            if (!input || typeof input !== 'object')
              throw new Error('A valid exception request is required.');
            const { employee, date, reason } = input as Record<string, unknown>;
            if (
              !Number.isInteger(employee) ||
              typeof date !== 'string' ||
              typeof reason !== 'string' ||
              reason.trim().length < 5
            ) {
              throw new Error(
                'employee, date, and a reason of at least five characters are required.',
              );
            }
            const { data } = await api.post('/management/exceptions/', { employee, date, reason });
            window.dispatchEvent(new CustomEvent('attendance-data-changed'));
            return {
              id: data.id,
              employee: data.employee_number,
              date: data.date,
              state: 'EXCUSED',
            };
          },
        },
        { signal: lifecycle.signal },
      ),
    );
  return () => lifecycle.abort();
}
