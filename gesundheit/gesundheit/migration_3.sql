-- Version 0.3: a date for the weight goal (forecast on the overview) and the findings a
-- person has already seen (the overview only announces new ones).
ALTER TABLE persons ADD COLUMN goal_weight_date TEXT;
ALTER TABLE persons ADD COLUMN seen_findings TEXT NOT NULL DEFAULT '';
