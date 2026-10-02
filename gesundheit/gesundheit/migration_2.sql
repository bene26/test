-- Version 2: several persons under one login. Every health value belongs to a person.
-- Existing data moves to person 1 (named after the existing account), goals move from the
-- settings table into the person.

CREATE TABLE persons (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT 'blau',
  birth_year INTEGER,
  height_cm INTEGER,
  goal_steps INTEGER NOT NULL DEFAULT 10000,
  goal_active_min INTEGER NOT NULL DEFAULT 30,
  goal_active_kcal INTEGER NOT NULL DEFAULT 500,
  goal_sleep_min INTEGER NOT NULL DEFAULT 480,
  goal_workouts INTEGER NOT NULL DEFAULT 3,
  goal_weight_dg INTEGER,
  garmin_enabled INTEGER NOT NULL DEFAULT 0,
  garmin_backfill_days INTEGER NOT NULL DEFAULT 30,
  position INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

INSERT INTO persons (id, name, height_cm, goal_steps, goal_active_min, goal_active_kcal,
                     goal_sleep_min, goal_weight_dg, garmin_enabled, garmin_backfill_days,
                     created_at)
SELECT 1, (SELECT username FROM users ORDER BY id LIMIT 1),
  (SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'height_cm' AND value != ''),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'goal_steps' AND value != ''), 10000),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'goal_active_min' AND value != ''), 30),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'goal_active_kcal' AND value != ''), 500),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'goal_sleep_min' AND value != ''), 480),
  (SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'goal_weight_dg' AND value != ''),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'garmin_enabled' AND value != ''), 0),
  COALESCE((SELECT CAST(value AS INTEGER) FROM settings WHERE key = 'garmin_backfill_days' AND value != ''), 30),
  strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
WHERE EXISTS (SELECT 1 FROM users);

DELETE FROM settings WHERE key IN ('height_cm', 'goal_steps', 'goal_active_min', 'goal_active_kcal',
                                   'goal_sleep_min', 'goal_weight_dg', 'garmin_enabled',
                                   'garmin_backfill_days');

CREATE TABLE measurements_v2 (
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  measured_at TEXT NOT NULL,
  day TEXT NOT NULL,
  source TEXT NOT NULL,
  group_id TEXT NOT NULL DEFAULT '',
  UNIQUE (person_id, metric, source, measured_at)
);
INSERT INTO measurements_v2 (id, person_id, metric, value, measured_at, day, source, group_id)
  SELECT id, 1, metric, value, measured_at, day, source, group_id FROM measurements
  WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
DROP TABLE measurements;
ALTER TABLE measurements_v2 RENAME TO measurements;
CREATE INDEX measurements_person_metric_day ON measurements (person_id, metric, day);
CREATE INDEX measurements_source ON measurements (source);

CREATE TABLE daily_values_v2 (
  person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  metric TEXT NOT NULL,
  day TEXT NOT NULL,
  source TEXT NOT NULL,
  value REAL NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (person_id, metric, day, source)
);
INSERT INTO daily_values_v2 (person_id, metric, day, source, value, updated_at)
  SELECT 1, metric, day, source, value, updated_at FROM daily_values
  WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
DROP TABLE daily_values;
ALTER TABLE daily_values_v2 RENAME TO daily_values;
CREATE INDEX daily_values_source ON daily_values (source);

CREATE TABLE sleep_v2 (
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
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
  UNIQUE (person_id, night, source)
);
INSERT INTO sleep_v2 (id, person_id, night, source, bed_start, bed_end, asleep_min, deep_min,
                      light_min, rem_min, awake_min, score, hr_avg, rr_avg)
  SELECT id, 1, night, source, bed_start, bed_end, asleep_min, deep_min, light_min, rem_min,
         awake_min, score, hr_avg, rr_avg FROM sleep
  WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
DROP TABLE sleep;
ALTER TABLE sleep_v2 RENAME TO sleep;

CREATE TABLE workouts_v2 (
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
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
  UNIQUE (person_id, source, external_id)
);
INSERT INTO workouts_v2 (id, person_id, source, external_id, kind, started_at, ended_at, day,
                         duration_min, distance_km, energy_kcal, hr_avg, hr_max)
  SELECT id, 1, source, external_id, kind, started_at, ended_at, day, duration_min, distance_km,
         energy_kcal, hr_avg, hr_max FROM workouts
  WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
DROP TABLE workouts;
ALTER TABLE workouts_v2 RENAME TO workouts;
CREATE INDEX workouts_person_day ON workouts (person_id, day);

-- Withings application credentials move to meta (jobs.migrate_secrets) at the next start;
-- here the connection rows only get their person.
CREATE TABLE connections_v2 (
  provider TEXT NOT NULL,
  person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  secret_enc TEXT NOT NULL DEFAULT '',
  account_label TEXT NOT NULL DEFAULT '',
  connected_at TEXT,
  last_sync TEXT,
  last_ok TEXT,
  last_error TEXT NOT NULL DEFAULT '',
  cursor TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (provider, person_id)
);
INSERT INTO connections_v2 (provider, person_id, secret_enc, account_label, connected_at,
                            last_sync, last_ok, last_error, cursor)
  SELECT provider, 1, secret_enc, account_label, connected_at, last_sync, last_ok, last_error,
         cursor FROM connections WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
DROP TABLE connections;
ALTER TABLE connections_v2 RENAME TO connections;

ALTER TABLE imports ADD COLUMN person_id INTEGER REFERENCES persons(id) ON DELETE CASCADE;
UPDATE imports SET person_id = 1 WHERE EXISTS (SELECT 1 FROM persons WHERE id = 1);
