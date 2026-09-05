import { useState, type FormEvent, type ReactNode } from 'react';
import { LoaderCircle, Plus, RefreshCw } from 'lucide-react';
import { api, errorMessage } from '../../api';
import type { Employee, NamedResource, Paged } from '../../types';
import { useLoad } from '../../shared/useLoad';
import { Page, PanelHead, option } from '../../shared/components';
type ConfigTab = 'sites' | 'departments' | 'shifts' | 'holidays' | 'kiosks' | 'exceptions';
export function ConfigurationPage() {
  const [tab, setTab] = useState<ConfigTab>('sites');
  return (
    <Page
      title="Configuration"
      subtitle="Control site verification, schedules, holidays, kiosks, and approved exceptions."
    >
      <div className="tabs config-tabs">
        {(
          ['sites', 'departments', 'shifts', 'holidays', 'kiosks', 'exceptions'] as ConfigTab[]
        ).map((item) => (
          <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </div>
      <ConfigSection key={tab} type={tab} />
    </Page>
  );
}

function ConfigSection({ type }: { type: ConfigTab }) {
  const endpoint = `/management/${type}/`;
  const resources = useLoad<Paged<Record<string, unknown>>>(endpoint, {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const sites = useLoad<Paged<NamedResource>>('/management/sites/', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const employees = useLoad<Paged<Employee>>('/management/employees/', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const [form, setForm] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      const payload: Record<string, unknown> = { ...form };
      if (type === 'sites') {
        payload.geofence_radius_meters = Number(form.geofence_radius_meters || 200);
        payload.timezone = form.timezone || 'Africa/Lagos';
      }
      if (type === 'shifts') {
        payload.grace_minutes = Number(form.grace_minutes || 15);
        payload.working_weekdays = (form.working_weekdays || '0,1,2,3,4').split(',').map(Number);
      }
      if (type === 'holidays') payload.site = form.site || null;
      if (type === 'exceptions') payload.employee = Number(form.employee);
      await api.post(endpoint, payload);
      setForm({});
      setMessage(`${singular(type)} created.`);
      await resources.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  async function pairingCode(id: unknown) {
    try {
      const { data } = await api.post(`/management/kiosks/${id}/pairing-code/`);
      setMessage(`Pairing code ${data.pairing_code} · device ${data.device_id}`);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  async function toggle(item: Record<string, unknown>) {
    try {
      await api.patch(`${endpoint}${item.id}/`, { is_active: !item.is_active });
      await resources.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  async function revoke(id: unknown) {
    try {
      await api.post(`/management/kiosks/${id}/revoke/`);
      setMessage('Kiosk credential revoked.');
      await resources.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }
  return (
    <div className="config-grid">
      <section className="panel form-panel">
        <PanelHead title={`Add ${singular(type)}`} />
        {error && <div className="alert error">{error}</div>}
        {message && <div className="alert success">{message}</div>}
        <form className="stack-form" onSubmit={submit}>
          {configFields(type, form, setForm, sites.data.results, employees.data.results)}
          <button className="primary">
            <Plus size={17} /> Add {singular(type)}
          </button>
        </form>
      </section>
      <section className="panel">
        <PanelHead
          title={`${resources.data.count} ${type}`}
          action={
            <button
              className="icon-button"
              onClick={() => void resources.reload()}
              aria-label="Refresh"
            >
              <RefreshCw size={17} />
            </button>
          }
        />
        {resources.loading ? (
          <div className="empty">
            <LoaderCircle className="spin" />
          </div>
        ) : (
          <div className="resource-list">
            {resources.data.results.map((item) => (
              <article key={String(item.id)}>
                <div>
                  <strong>{String(item.name || item.employee_name || singular(type))}</strong>
                  <p>{resourceDescription(type, item)}</p>
                </div>
                <div className="resource-actions">
                  {type === 'kiosks' && (
                    <>
                      <button className="secondary small" onClick={() => void pairingCode(item.id)}>
                        Pair
                      </button>
                      {item.is_paired && (
                        <button className="secondary small" onClick={() => void revoke(item.id)}>
                          Revoke
                        </button>
                      )}
                    </>
                  )}
                  {item.is_active !== undefined && (
                    <button className="secondary small" onClick={() => void toggle(item)}>
                      {item.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function singular(value: string) {
  return value.endsWith('ies')
    ? `${value.slice(0, -3)}y`
    : value.endsWith('s')
      ? value.slice(0, -1)
      : value;
}
function field(
  form: Record<string, string>,
  setForm: (value: Record<string, string>) => void,
  name: string,
  label: string,
  type = 'text',
  required = true,
) {
  return (
    <label key={name}>
      {label}
      <input
        type={type}
        step={type === 'number' ? 'any' : undefined}
        value={form[name] || ''}
        onChange={(e) => setForm({ ...form, [name]: e.target.value })}
        required={required}
      />
    </label>
  );
}
function configFields(
  type: ConfigTab,
  form: Record<string, string>,
  setForm: (value: Record<string, string>) => void,
  sites: NamedResource[],
  employees: Employee[],
): ReactNode {
  if (type === 'sites')
    return (
      <>
        {field(form, setForm, 'name', 'Site name')}
        {field(form, setForm, 'address', 'Address', 'text', false)}
        <div className="form-grid">
          {field(form, setForm, 'latitude', 'Latitude', 'number')}
          {field(form, setForm, 'longitude', 'Longitude', 'number')}
          {field(form, setForm, 'geofence_radius_meters', 'Radius (metres)', 'number')}
          {field(form, setForm, 'timezone', 'Timezone (defaults to Africa/Lagos)', 'text', false)}
        </div>
      </>
    );
  if (type === 'departments') return field(form, setForm, 'name', 'Department name');
  if (type === 'shifts')
    return (
      <>
        {field(form, setForm, 'name', 'Shift name')}
        <div className="form-grid">
          {field(form, setForm, 'start_time', 'Start time', 'time')}
          {field(form, setForm, 'end_time', 'End time', 'time')}
          {field(form, setForm, 'grace_minutes', 'Grace minutes', 'number')}
          {field(form, setForm, 'working_weekdays', 'Weekdays (0=Mon … 6=Sun)', 'text', false)}
        </div>
        <small>
          Working days default to 0,1,2,3,4. End times before start times create overnight shifts.
        </small>
      </>
    );
  if (type === 'holidays')
    return (
      <>
        {field(form, setForm, 'name', 'Holiday name')}
        {field(form, setForm, 'date', 'Date', 'date')}
        <label>
          Site
          <select
            value={form.site || ''}
            onChange={(e) => setForm({ ...form, site: e.target.value })}
          >
            <option value="">Company-wide</option>
            {sites.map(option)}
          </select>
        </label>
      </>
    );
  if (type === 'kiosks')
    return (
      <>
        {field(form, setForm, 'name', 'Kiosk name')}
        <label>
          Work site
          <select
            value={form.site || ''}
            onChange={(e) => setForm({ ...form, site: e.target.value })}
            required
          >
            <option value="">Select</option>
            {sites.map(option)}
          </select>
        </label>
      </>
    );
  return (
    <>
      <label>
        Employee
        <select
          value={form.employee || ''}
          onChange={(e) => setForm({ ...form, employee: e.target.value })}
          required
        >
          <option value="">Select</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name} · {employee.employee_number}
            </option>
          ))}
        </select>
      </label>
      {field(form, setForm, 'date', 'Exception date', 'date')}
      {field(form, setForm, 'reason', 'Approved reason')}
    </>
  );
}

function resourceDescription(type: ConfigTab, item: Record<string, unknown>) {
  if (type === 'sites')
    return `${item.address || 'No address'} · ${item.geofence_radius_meters} m radius`;
  if (type === 'shifts')
    return `${item.start_time}–${item.end_time} · ${item.grace_minutes} min grace`;
  if (type === 'holidays') return `${item.date} · ${item.site_name || 'All sites'}`;
  if (type === 'kiosks') return `${item.site_name} · ${item.is_paired ? 'Paired' : 'Not paired'}`;
  if (type === 'exceptions') return `${item.employee_number} · ${item.date} · ${item.reason}`;
  return item.is_active ? 'Active' : 'Inactive';
}
