-- Local trace schema for an Agent Fleet portfolio project.
CREATE TABLE IF NOT EXISTS agent_trace (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  change_id    TEXT NOT NULL,
  agent        TEXT NOT NULL,
  started_at   TEXT NOT NULL,
  ended_at     TEXT,
  status       TEXT,
  blocker_code TEXT,
  input_ref    TEXT,
  output_ref   TEXT,
  tokens_in    INTEGER,
  tokens_out   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_trace_change ON agent_trace(change_id, started_at);

CREATE TABLE IF NOT EXISTS evaluation_run (
  run_id             TEXT PRIMARY KEY,
  change_id          TEXT NOT NULL,
  commit_sha         TEXT NOT NULL,
  dataset_version    TEXT NOT NULL,
  started_at         TEXT NOT NULL,
  ended_at           TEXT,
  verdict            TEXT NOT NULL CHECK (verdict IN ('PASS', 'FAIL')),
  pass_rate          REAL CHECK (pass_rate >= 0 AND pass_rate <= 1),
  baseline_rate      REAL CHECK (baseline_rate IS NULL OR (baseline_rate >= 0 AND baseline_rate <= 1)),
  safety_passed      INTEGER NOT NULL DEFAULT 0,
  safety_total       INTEGER NOT NULL DEFAULT 0,
  p95_latency_ms     REAL,
  estimated_cost_usd REAL,
  report_ref         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_case (
  run_id          TEXT NOT NULL REFERENCES evaluation_run(run_id),
  case_id         TEXT NOT NULL,
  category        TEXT NOT NULL,
  passed          INTEGER NOT NULL CHECK (passed IN (0, 1)),
  safety_critical INTEGER NOT NULL CHECK (safety_critical IN (0, 1)),
  latency_ms      REAL,
  tokens_in       INTEGER,
  tokens_out      INTEGER,
  evidence_ref    TEXT,
  PRIMARY KEY (run_id, case_id)
);

CREATE TABLE IF NOT EXISTS gate_result (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       TEXT NOT NULL REFERENCES evaluation_run(run_id),
  gate_name    TEXT NOT NULL,
  verdict      TEXT NOT NULL CHECK (verdict IN ('PASS', 'FAIL', 'BLOCKED')),
  blocker_code TEXT,
  evidence_ref TEXT NOT NULL,
  decided_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_change ON evaluation_run(change_id, started_at);
CREATE INDEX IF NOT EXISTS idx_gate_run ON gate_result(run_id, decided_at);
