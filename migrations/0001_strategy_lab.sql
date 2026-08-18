CREATE TABLE IF NOT EXISTS strategy_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  seed INTEGER NOT NULL,
  opponent_style TEXT NOT NULL,
  version TEXT NOT NULL,
  state_json TEXT NOT NULL,
  complete INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  day INTEGER NOT NULL,
  phase TEXT NOT NULL,
  action TEXT NOT NULL,
  coach_action TEXT NOT NULL,
  rationale TEXT NOT NULL DEFAULT '',
  confidence INTEGER NOT NULL DEFAULT 3,
  turning_point INTEGER NOT NULL DEFAULT 0,
  state_before TEXT NOT NULL,
  state_after TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES strategy_sessions(id)
);

CREATE TABLE IF NOT EXISTS strategy_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  day INTEGER NOT NULL,
  category TEXT NOT NULL,
  note TEXT NOT NULL,
  rating INTEGER NOT NULL DEFAULT 3,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES strategy_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_decisions_session ON strategy_decisions(session_id, day);
CREATE INDEX IF NOT EXISTS idx_strategy_feedback_session ON strategy_feedback(session_id, created_at);

