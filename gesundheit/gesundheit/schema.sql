-- Gesundheits-Cockpit, schema version 1. Times are local time 'YYYY-MM-DD HH:MM:SS'.

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Profile, goals, retention and similar single values (see settings.py).
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  theme TEXT NOT NULL DEFAULT '',
  appearance TEXT NOT NULL DEFAULT ''
);

CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

-- Single readings at a point in time: weight, blood pressure, temperature, VO2max …
-- group_id links values taken together (systolic, diastolic and pulse of one reading).
CREATE TABLE measurements (
  id INTEGER PRIMARY KEY,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  measured_at TEXT NOT NULL,
  day TEXT NOT NULL,
  source TEXT NOT NULL,
  group_id TEXT NOT NULL DEFAULT '',
  UNIQUE (metric, source, measured_at)
);
CREATE INDEX measurements_metric_day ON measurements (metric, day);
CREATE INDEX measurements_source ON measurements (source);

-- One value per day and source: steps, active energy, resting heart rate, HRV …
CREATE TABLE daily_values (
  metric TEXT NOT NULL,
  day TEXT NOT NULL,
  source TEXT NOT NULL,
  value REAL NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (metric, day, source)
);
CREATE INDEX daily_values_source ON daily_values (source);

-- One night per source; night = day of waking up. Durations in minutes.
CREATE TABLE sleep (
  id INTEGER PRIMARY KEY,
  night TEXT NOT NULL,
  source TEXT NOT NULL,
  bed_start TEXT,
  bed_end TEXT,
  asleep_min INTEGER,
  deep_min INTEGER,
  light_min INTEGER,
  rem_min INTEGER,
  awake_min INTEGER,
  score INTEGER,
  hr_avg REAL,
  rr_avg REAL,
  UNIQUE (night, source)
);

CREATE TABLE workouts (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  day TEXT NOT NULL,
  duration_min REAL,
  distance_km REAL,
  energy_kcal REAL,
  hr_avg REAL,
  hr_max REAL,
  UNIQUE (source, external_id)
);
CREATE INDEX workouts_day ON workouts (day);

-- Connections to Withings and Garmin. secret_enc holds tokens (and for Withings the
-- client credentials) encrypted with the app key (crypto.py). cursor: sync positions as JSON.
CREATE TABLE connections (
  provider TEXT PRIMARY KEY,
  secret_enc TEXT NOT NULL DEFAULT '',
  account_label TEXT NOT NULL DEFAULT '',
  connected_at TEXT,
  last_sync TEXT,
  last_ok TEXT,
  last_error TEXT NOT NULL DEFAULT '',
  cursor TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE imports (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  status TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  records INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL DEFAULT ''
);

-- Order of sources per family (katalog.FAMILIES), comma separated. Missing rows = default.
CREATE TABLE source_priority (
  family TEXT PRIMARY KEY,
  sources TEXT NOT NULL
);
