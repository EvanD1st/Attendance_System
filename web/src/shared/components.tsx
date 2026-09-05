import type { ReactNode } from 'react';
import type { NamedResource, Paged } from '../types';

export function toLocalInput(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function formatTime(value: string | null) {
  return value
    ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';
}

export function StatusPill({ state }: { state: string }) {
  return <span className={`status status-${state.toLowerCase()}`}>{state.replace('_', ' ')}</span>;
}
export function Pager({
  page,
  data,
  onPage,
}: {
  page: number;
  data: Paged<unknown>;
  onPage: (page: number) => void;
}) {
  if (!data.previous && !data.next) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        className="secondary small"
        disabled={!data.previous}
        onClick={() => onPage(Math.max(1, page - 1))}
      >
        Previous
      </button>
      <span>
        Page {page} · {data.count} records
      </span>
      <button className="secondary small" disabled={!data.next} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  );
}
export function option(item: NamedResource) {
  return (
    <option key={String(item.id)} value={String(item.id)}>
      {item.name}
    </option>
  );
}
export function Page({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">OPERATIONS</p>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        {actions && <div>{actions}</div>}
      </header>
      {children}
    </div>
  );
}
export function PanelHead({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <header className="panel-head">
      <h2>{title}</h2>
      {action}
    </header>
  );
}
