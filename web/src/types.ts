export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: 'admin' | 'manager' | 'employee';
  must_change_password: boolean;
  employee_id: number | null;
  employee_number: string | null;
}

export interface AttendanceRecord {
  id: number;
  employee: number;
  employee_number: string;
  employee_name: string;
  department_name: string;
  work_date: string;
  site: number;
  site_name: string;
  shift: number;
  shift_name: string;
  scheduled_start: string;
  scheduled_end: string;
  clock_in: string | null;
  clock_out: string | null;
  state: 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED';
  worked_minutes: number | null;
  missing_clock_out: boolean;
}

export interface Employee {
  id: number;
  user: number;
  employee_number: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  department: number;
  department_name: string;
  work_site: number;
  site_name: string;
  shift: number;
  shift_name: string;
  is_active: boolean;
}

export interface Paged<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Summary {
  present: number;
  late: number;
  absent: number;
  excused: number;
  attendance_rate: number;
  missing_clock_out: number;
  rejected_attempts: number;
}
export interface NamedResource {
  id: number | string;
  name: string;
  is_active?: boolean;
  [key: string]: unknown;
}
