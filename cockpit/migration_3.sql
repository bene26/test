-- Schema version 3: timeline, quotas of external firms, project hours and
-- the per-user start page layout. Applied by db.MIGRATIONS; never edit.

ALTER TABLE users ADD COLUMN dashboard TEXT NOT NULL DEFAULT '';

-- Phases (Vorgänge) and milestones of a project timeline. Dates are inclusive.
CREATE TABLE schedule_items (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('phase', 'milestone')),
    title      TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    progress   INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    person_id  INTEGER REFERENCES people(id) ON DELETE SET NULL,
    firm_id    INTEGER REFERENCES firms(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (end_date >= start_date),
    CHECK (kind = 'phase' OR start_date = end_date),
    CHECK (person_id IS NULL OR firm_id IS NULL)
);

-- "Successor may only start when the predecessor is finished", also across projects.
CREATE TABLE schedule_links (
    id       INTEGER PRIMARY KEY,
    pred_id  INTEGER NOT NULL REFERENCES schedule_items(id) ON DELETE CASCADE,
    succ_id  INTEGER NOT NULL REFERENCES schedule_items(id) ON DELETE CASCADE,
    lag_days INTEGER NOT NULL DEFAULT 0 CHECK (lag_days BETWEEN -365 AND 365),
    UNIQUE (pred_id, succ_id),
    CHECK (pred_id != succ_id)
);

-- Orders (Bestellungen) with a quota for an external firm.
CREATE TABLE orders (
    id            INTEGER PRIMARY KEY,
    firm_id       INTEGER NOT NULL REFERENCES firms(id) ON DELETE RESTRICT,
    project_id    INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    number        TEXT NOT NULL DEFAULT '',
    title         TEXT NOT NULL,
    unit          TEXT NOT NULL CHECK (unit IN ('h', 'pt')),
    amount        REAL NOT NULL CHECK (amount > 0 AND amount <= 1000000),
    hours_per_day REAL NOT NULL DEFAULT 8 CHECK (hours_per_day > 0 AND hours_per_day <= 24),
    valid_from    TEXT,
    valid_to      TEXT,
    notes         TEXT NOT NULL DEFAULT '',
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Service records (Leistungsnachweise) per order, never per external person.
CREATE TABLE service_records (
    id           INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    period_start TEXT NOT NULL,
    period_end   TEXT NOT NULL,
    amount       REAL NOT NULL CHECK (amount > 0 AND amount <= 100000),
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'eingereicht'
                 CHECK (status IN ('eingereicht', 'geprueft', 'abgelehnt')),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    CHECK (period_end >= period_start)
);

-- Project hours (Ist-Aufwand) of internal and ANÜ staff: one value per person,
-- project and day. Used for plan/actual, not for attendance or performance.
CREATE TABLE time_entries (
    id         INTEGER PRIMARY KEY,
    person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    work_date  TEXT NOT NULL,
    hours      REAL NOT NULL CHECK (hours > 0 AND hours <= 24),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (person_id, project_id, work_date)
);

CREATE INDEX idx_schedule_project ON schedule_items(project_id, start_date);
CREATE INDEX idx_links_pred ON schedule_links(pred_id);
CREATE INDEX idx_links_succ ON schedule_links(succ_id);
CREATE INDEX idx_orders_firm ON orders(firm_id);
CREATE INDEX idx_records_order ON service_records(order_id, period_start);
CREATE INDEX idx_time_date ON time_entries(work_date);
CREATE INDEX idx_time_project ON time_entries(project_id, work_date);
