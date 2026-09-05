import { useMemo, useState, type FormEvent } from 'react';
import { AlertTriangle, Download, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, downloadAttendance, errorMessage } from '../../api';
import { useAuth } from '../../auth';
import type { AttendanceRecord, NamedResource, Paged, Summary } from '../../types';
import { useLoad } from '../../shared/useLoad';
import {
  Page,
  PanelHead,
  StatusPill,
  Pager,
  option,
  formatTime,
  toLocalInput,
} from '../../shared/components';
const emptySummary: Summary = {
  present: 0,
  late: 0,
  absent: 0,
  excused: 0,
  attendance_rate: 0,
  missing_clock_out: 0,
  rejected_attempts: 0,
};
export function DashboardPage() {
  const summary = useLoad<Summary>('/management/attendance/summary/', emptySummary);
  const records = useLoad<Paged<AttendanceRecord>>('/management/attendance/?page=1', {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const cards = [
    ['Attendance rate', `${summary.data.attendance_rate}%`, 'blue'],
    ['Present', summary.data.present, 'green'],
    ['Late', summary.data.late, 'amber'],
    ['Absent', summary.data.absent, 'red'],
  ];
  return (
    <Page title="Today at a glance" subtitle="Live operational view across your permitted sites.">
      {summary.error && <div className="alert error">{summary.error}</div>}
      <div className="metric-grid">
        {cards.map(([label, value, tone]) => (
          <article className={`metric ${tone}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>
              {label === 'Attendance rate' ? 'Present + late employees' : 'Finalized records'}
            </small>
          </article>
        ))}
      </div>
      <div className="split-grid">
        <section className="panel">
          <PanelHead title="Recent attendance" action={<Link to="/records">View all</Link>} />
          <RecordTable records={records.data.results.slice(0, 7)} loading={records.loading} />
        </section>
        <aside className="panel signal-panel">
          <PanelHead title="Review queue" />
          <QueueItem
            tone="red"
            value={summary.data.rejected_attempts}
            label="Rejected location attempts"
          />
          <QueueItem
            tone="amber"
            value={summary.data.missing_clock_out}
            label="Missing clock-outs"
          />
          <QueueItem tone="blue" value={summary.data.excused} label="Approved exceptions" />
        </aside>
      </div>
    </Page>
  );
}

function QueueItem({ tone, value, label }: { tone: string; value: number; label: string }) {
  return (
    <div className="queue-item">
      <span className={`queue-dot ${tone}`} />
      <div>
        <strong>{value}</strong>
        <p>{label}</p>
      </div>
    </div>
  );
}

function RecordTable({
  records,
  loading,
  onCorrect,
}: {
  records: AttendanceRecord[];
  loading?: boolean;
  onCorrect?: (record: AttendanceRecord) => void;
}) {
  if (loading)
    return (
      <div className="empty">
        <LoaderCircle className="spin" /> Loading attendance…
      </div>
    );
  if (!records.length) return <div className="empty">No attendance records match this view.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Work date</th>
            <th>Site</th>
            <th>Clock in</th>
            <th>Clock out</th>
            <th>State</th>
            <th>Worked</th>
            {onCorrect && <th />}
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id}>
              <td>
                <strong>{record.employee_name}</strong>
                <small>
                  {record.employee_number} · {record.department_name}
                </small>
              </td>
              <td>{record.work_date}</td>
              <td>{record.site_name}</td>
              <td>{formatTime(record.clock_in)}</td>
              <td className={record.missing_clock_out ? 'warning-text' : ''}>
                {record.missing_clock_out ? 'Missing' : formatTime(record.clock_out)}
              </td>
              <td>
                <StatusPill state={record.state} />
              </td>
              <td>
                {record.worked_minutes == null
                  ? '—'
                  : `${Math.floor(record.worked_minutes / 60)}h ${record.worked_minutes % 60}m`}
              </td>
              {onCorrect && (
                <td>
                  <button className="text-button" onClick={() => onCorrect(record)}>
                    Correct
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecordsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({
    from: '',
    to: '',
    state: '',
    site: '',
    department: '',
    missing_clock_out: '',
  });
  const [page, setPage] = useState(1);
  const [attemptPage, setAttemptPage] = useState(1);
  const query = useMemo(() => {
    const p = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => v && p.set(k, v));
    return p;
  }, [filters]);
  const records = useLoad<Paged<AttendanceRecord>>(
    `/management/attendance/?${query}&page=${page}`,
    { count: 0, next: null, previous: null, results: [] },
  );
  const attempts = useLoad<Paged<Record<string, unknown>>>(
    `/management/attempts/?accepted=false&page=${attemptPage}`,
    { count: 0, next: null, previous: null, results: [] },
  );
  const sites = useLoad<Paged<NamedResource>>('/management/sites/', {
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
  const [tab, setTab] = useState<'records' | 'attempts'>('records');
  const [correcting, setCorrecting] = useState<AttendanceRecord | null>(null);
  const [reason, setReason] = useState('');
  const [correctionError, setCorrectionError] = useState('');
  const [exportError, setExportError] = useState('');
  const [times, setTimes] = useState({ clock_in: '', clock_out: '' });
  function updateFilter(name: keyof typeof filters, value: string) {
    setPage(1);
    setFilters({ ...filters, [name]: value });
  }
  function openCorrection(record: AttendanceRecord) {
    setCorrecting(record);
    setReason('');
    setCorrectionError('');
    setTimes({
      clock_in: toLocalInput(record.clock_in),
      clock_out: toLocalInput(record.clock_out),
    });
  }
  async function correct(event: FormEvent) {
    event.preventDefault();
    if (!correcting) return;
    setCorrectionError('');
    try {
      await api.post('/management/corrections/', {
        employee: correcting.employee,
        work_date: correcting.work_date,
        clock_in: times.clock_in ? new Date(times.clock_in).toISOString() : null,
        clock_out: times.clock_out ? new Date(times.clock_out).toISOString() : null,
        reason,
      });
      setCorrecting(null);
      await records.reload();
    } catch (cause) {
      setCorrectionError(errorMessage(cause));
    }
  }
  return (
    <Page
      title="Attendance records"
      subtitle="Filter effective records, review blocked scans, and export the current view."
      actions={
        <button
          className="secondary"
          onClick={() => {
            setExportError('');
            void downloadAttendance(query).catch((cause) => setExportError(errorMessage(cause)));
          }}
        >
          <Download size={17} /> Export CSV
        </button>
      }
    >
      {(exportError || records.error || attempts.error) && (
        <div className="alert error">{exportError || records.error || attempts.error}</div>
      )}
      <div className="toolbar">
        <div className="tabs">
          <button className={tab === 'records' ? 'active' : ''} onClick={() => setTab('records')}>
            Effective records
          </button>
          <button className={tab === 'attempts' ? 'active' : ''} onClick={() => setTab('attempts')}>
            Rejected attempts <span>{attempts.data.count}</span>
          </button>
        </div>
        {tab === 'records' && (
          <div className="filters">
            <input
              aria-label="From date"
              type="date"
              value={filters.from}
              onChange={(e) => updateFilter('from', e.target.value)}
            />
            <input
              aria-label="To date"
              type="date"
              value={filters.to}
              onChange={(e) => updateFilter('to', e.target.value)}
            />
            <select
              aria-label="Site"
              value={filters.site}
              onChange={(e) => updateFilter('site', e.target.value)}
            >
              <option value="">All sites</option>
              {sites.data.results.map(option)}
            </select>
            <select
              aria-label="Department"
              value={filters.department}
              onChange={(e) => updateFilter('department', e.target.value)}
            >
              <option value="">All departments</option>
              {departments.data.results.map(option)}
            </select>
            <select
              aria-label="State"
              value={filters.state}
              onChange={(e) => updateFilter('state', e.target.value)}
            >
              <option value="">All states</option>
              {['PRESENT', 'LATE', 'ABSENT', 'EXCUSED'].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <select
              aria-label="Clock-out review"
              value={filters.missing_clock_out}
              onChange={(e) => updateFilter('missing_clock_out', e.target.value)}
            >
              <option value="">All clock-outs</option>
              <option value="true">Missing clock-out</option>
            </select>
          </div>
        )}
      </div>
      <section className="panel">
        {tab === 'records' ? (
          <>
            <RecordTable
              records={records.data.results}
              loading={records.loading}
              onCorrect={user?.role === 'admin' ? openCorrection : undefined}
            />
            <Pager page={page} data={records.data} onPage={setPage} />
          </>
        ) : (
          <>
            <AttemptTable rows={attempts.data.results} loading={attempts.loading} />
            <Pager page={attemptPage} data={attempts.data} onPage={setAttemptPage} />
          </>
        )}
      </section>
      {correcting && (
        <div className="dialog-backdrop">
          <form className="dialog" onSubmit={correct}>
            <h2>Correct {correcting.employee_name}</h2>
            <p>
              {correcting.work_date} · changes are permanently audited. Times use your device
              timezone.
            </p>
            {correctionError && <div className="alert error">{correctionError}</div>}
            <label>
              Clock in
              <input
                type="datetime-local"
                value={times.clock_in}
                onChange={(e) => setTimes({ ...times, clock_in: e.target.value })}
              />
            </label>
            <label>
              Clock out
              <input
                type="datetime-local"
                value={times.clock_out}
                onChange={(e) => setTimes({ ...times, clock_out: e.target.value })}
              />
            </label>
            <label>
              Correction reason
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                minLength={5}
                required
              />
            </label>
            <div className="dialog-actions">
              <button type="button" className="ghost" onClick={() => setCorrecting(null)}>
                Cancel
              </button>
              <button className="primary">Save correction</button>
            </div>
          </form>
        </div>
      )}
    </Page>
  );
}
function AttemptTable({ rows, loading }: { rows: Record<string, unknown>[]; loading: boolean }) {
  if (loading)
    return (
      <div className="empty">
        <LoaderCircle className="spin" /> Loading attempts…
      </div>
    );
  if (!rows.length) return <div className="empty">No rejected attempts.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Action</th>
            <th>Received</th>
            <th>Site</th>
            <th>Distance</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id)}>
              <td>
                <strong>{String(row.employee_name)}</strong>
                <small>{String(row.employee_number)}</small>
              </td>
              <td>{String(row.action).replace('_', ' ')}</td>
              <td>{new Date(String(row.received_at)).toLocaleString()}</td>
              <td>{row.site_name ? String(row.site_name) : 'Unknown'}</td>
              <td>{row.distance_meters ? `${Math.round(Number(row.distance_meters))} m` : '—'}</td>
              <td>
                <span className="reason">
                  <AlertTriangle size={15} /> {String(row.reason_detail)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
