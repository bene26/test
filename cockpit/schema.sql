-- Schema version 1. Later changes go into db.MIGRATIONS, not into this file.

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE projects (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    code       TEXT NOT NULL DEFAULT '',
    client     TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'aktiv'
               CHECK (status IN ('geplant', 'aktiv', 'pausiert', 'abgeschlossen')),
    priority   INTEGER NOT NULL DEFAULT 2 CHECK (priority IN (1, 2, 3)),
    start_date TEXT,
    end_date   TEXT,
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE firms (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    contract_type TEXT NOT NULL
                  CHECK (contract_type IN ('werkvertrag', 'dienstvertrag', 'anue')),
    contact_name  TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Internal staff, plus staff of firms under Arbeitnehmerüberlassung (firm_id set).
CREATE TABLE people (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT '',
    email        TEXT NOT NULL DEFAULT '',
    weekly_hours REAL NOT NULL DEFAULT 40 CHECK (weekly_hours > 0 AND weekly_hours <= 80),
    availability REAL NOT NULL DEFAULT 0.8 CHECK (availability > 0 AND availability <= 1),
    firm_id      INTEGER REFERENCES firms(id) ON DELETE RESTRICT,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE meetings (
    id                  INTEGER PRIMARY KEY,
    type                TEXT NOT NULL,
    title               TEXT NOT NULL,
    project_id          INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    firm_id             INTEGER REFERENCES firms(id) ON DELETE SET NULL,
    starts_at           TEXT NOT NULL,              -- 'YYYY-MM-DD HH:MM', local time
    duration_min        INTEGER NOT NULL DEFAULT 45,
    location            TEXT NOT NULL DEFAULT '',
    participants        TEXT NOT NULL DEFAULT '',   -- one per line
    protocol_status     TEXT NOT NULL DEFAULT 'offen'
                        CHECK (protocol_status IN ('offen', 'abgeschlossen')),
    version             INTEGER NOT NULL DEFAULT 0, -- number of finalized versions
    previous_meeting_id INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE agenda_items (
    id         INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    title      TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',
    auto       TEXT                                 -- see meeting_types.AUTO_KINDS
);

CREATE TABLE decisions (
    id         INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    number     INTEGER NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE protocol_versions (
    id            INTEGER PRIMARY KEY,
    meeting_id    INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    finalized_at  TEXT NOT NULL,
    sent_to       TEXT NOT NULL DEFAULT '',
    UNIQUE (meeting_id, version)
);

CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    person_id    INTEGER REFERENCES people(id) ON DELETE SET NULL,
    firm_id      INTEGER REFERENCES firms(id) ON DELETE SET NULL,
    effort_hours REAL CHECK (effort_hours IS NULL OR (effort_hours >= 0 AND effort_hours <= 10000)),
    start_date   TEXT,
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'offen'
                 CHECK (status IN ('offen', 'in_arbeit', 'wartet', 'erledigt', 'abgenommen')),
    waiting_for  TEXT NOT NULL DEFAULT '',
    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority IN (1, 2, 3)),
    meeting_id   INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    done_at      TEXT,
    CHECK (person_id IS NULL OR firm_id IS NULL)
);

CREATE TABLE routine_checks (
    routine TEXT NOT NULL,
    period  TEXT NOT NULL,
    done_at TEXT NOT NULL,
    PRIMARY KEY (routine, period)
);

CREATE TABLE reminder_log (
    key     TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);

CREATE INDEX idx_tasks_status_due ON tasks(status, due_date);
CREATE INDEX idx_tasks_person ON tasks(person_id);
CREATE INDEX idx_tasks_firm ON tasks(firm_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_meeting ON tasks(meeting_id);
CREATE INDEX idx_meetings_starts ON meetings(starts_at);
CREATE INDEX idx_agenda_meeting ON agenda_items(meeting_id, position);
CREATE INDEX idx_decisions_project ON decisions(project_id, number);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
