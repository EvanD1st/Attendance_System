import { useState, type FormEvent } from 'react';
import { Clock3, MapPin, Plus } from 'lucide-react';
import { api, errorMessage } from '../../api';
import { useAuth } from '../../auth';
import type { Employee, NamedResource, Paged } from '../../types';
import { useLoad } from '../../shared/useLoad';
import { Page, PanelHead, StatusPill, option } from '../../shared/components';
export function PeoplePage() {
  const { user } = useAuth();
  const employees = useLoad<Paged<Employee>>('/management/employees/', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const departments = useLoad<Paged<NamedResource>>('/management/departments/', {
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
  const shifts = useLoad<Paged<NamedResource>>('/management/shifts/', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const scopes = useLoad<Paged<Record<string, unknown>>>('/management/manager-scopes/', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const [showForm, setShowForm] = useState(false);
  const [actionError, setActionError] = useState('');
  const [form, setForm] = useState({
    email: '',
    first_name: '',
    last_name: '',
    temporary_password: '',
    role: 'employee',
    employee_number: '',
    department: '',
    work_site: '',
    shift: '',
  });
  const [scope, setScope] = useState({ manager: '', site: '', department: '' });
  async function createEmployee(event: FormEvent) {
    event.preventDefault();
    setActionError('');
    try {
      await api.post('/management/employees/', form);
      setShowForm(false);
      await employees.reload();
    } catch (cause) {
      setActionError(errorMessage(cause));
    }
  }
  async function createScope(event: FormEvent) {
    event.preventDefault();
    setActionError('');
    try {
      await api.post('/management/manager-scopes/', {
        ...scope,
        department: scope.department || null,
      });
      setScope({ manager: '', site: '', department: '' });
      await scopes.reload();
    } catch (cause) {
      setActionError(errorMessage(cause));
    }
  }
  async function toggleEmployee(employee: Employee) {
    setActionError('');
    try {
      await api.patch(`/management/employees/${employee.id}/`, { is_active: !employee.is_active });
      await employees.reload();
    } catch (cause) {
      setActionError(errorMessage(cause));
    }
  }
  const managers = employees.data.results.filter((employee) => employee.role === 'manager');
  return (
    <Page
      title="People and access"
      subtitle="Employee assignments determine where and when each person can record attendance."
      actions={
        user?.role === 'admin' ? (
          <button className="primary" onClick={() => setShowForm(true)}>
            <Plus size={17} /> Add employee
          </button>
        ) : undefined
      }
    >
      {actionError && <div className="alert error">{actionError}</div>}
      <section className="panel">
        <PanelHead title={`${employees.data.count} employees`} />
        <div className="people-grid">
          {employees.data.results.map((employee) => (
            <article className="person-card" key={employee.id}>
              <div className="avatar">
                {employee.first_name[0]}
                {employee.last_name[0]}
              </div>
              <div>
                <strong>{employee.full_name}</strong>
                <p>
                  {employee.employee_number} · {employee.department_name}
                </p>
                <small>
                  <MapPin size={13} /> {employee.site_name} · <Clock3 size={13} />{' '}
                  {employee.shift_name}
                </small>
              </div>
              {user?.role === 'admin' ? (
                <button className="secondary small" onClick={() => void toggleEmployee(employee)}>
                  {employee.is_active ? 'Deactivate' : 'Activate'}
                </button>
              ) : (
                <StatusPill state={employee.is_active ? 'ACTIVE' : 'INACTIVE'} />
              )}
            </article>
          ))}
        </div>
      </section>
      {user?.role === 'admin' && (
        <section className="panel form-panel">
          <PanelHead title="Manager scopes" />
          <form className="inline-form" onSubmit={createScope}>
            <select
              value={scope.manager}
              onChange={(e) => setScope({ ...scope, manager: e.target.value })}
              required
            >
              <option value="">Manager</option>
              {managers.map((m) => (
                <option key={m.id} value={m.user}>
                  {m.full_name}
                </option>
              ))}
            </select>
            <select
              value={scope.site}
              onChange={(e) => setScope({ ...scope, site: e.target.value })}
              required
            >
              <option value="">Site</option>
              {sites.data.results.map(option)}
            </select>
            <select
              value={scope.department}
              onChange={(e) => setScope({ ...scope, department: e.target.value })}
            >
              <option value="">Whole site</option>
              {departments.data.results.map(option)}
            </select>
            <button className="secondary">Add scope</button>
          </form>
          <div className="chip-row">
            {scopes.data.results.map((item) => (
              <span className="chip" key={String(item.id)}>
                {String(item.manager_email)} · {String(item.site_name)}
                {item.department_name ? ` / ${item.department_name}` : ''}
              </span>
            ))}
          </div>
        </section>
      )}
      {showForm && (
        <div className="dialog-backdrop">
          <form className="dialog wide" onSubmit={createEmployee}>
            <h2>Create employee</h2>
            {actionError && <div className="alert error">{actionError}</div>}
            <div className="form-grid">
              <label>
                First name
                <input
                  value={form.first_name}
                  onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  required
                />
              </label>
              <label>
                Last name
                <input
                  value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  required
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </label>
              <label>
                Employee number
                <input
                  value={form.employee_number}
                  onChange={(e) => setForm({ ...form, employee_number: e.target.value })}
                  required
                />
              </label>
              <label>
                Temporary password
                <input
                  type="password"
                  value={form.temporary_password}
                  onChange={(e) => setForm({ ...form, temporary_password: e.target.value })}
                  required
                />
              </label>
              <label>
                Account role
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                >
                  <option value="employee">Employee</option>
                  <option value="manager">Manager</option>
                </select>
              </label>
              <label>
                Department
                <select
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  required
                >
                  <option value="">Select</option>
                  {departments.data.results.map(option)}
                </select>
              </label>
              <label>
                Work site
                <select
                  value={form.work_site}
                  onChange={(e) => setForm({ ...form, work_site: e.target.value })}
                  required
                >
                  <option value="">Select</option>
                  {sites.data.results.map(option)}
                </select>
              </label>
              <label>
                Shift
                <select
                  value={form.shift}
                  onChange={(e) => setForm({ ...form, shift: e.target.value })}
                  required
                >
                  <option value="">Select</option>
                  {shifts.data.results.map(option)}
                </select>
              </label>
            </div>
            <div className="dialog-actions">
              <button type="button" className="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button className="primary">Create employee</button>
            </div>
          </form>
        </div>
      )}
    </Page>
  );
}
