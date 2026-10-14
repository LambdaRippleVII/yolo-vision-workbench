-- YOLO Vision Workbench project DB — schema v1
-- See docs/IMPLEMENTATION_DESIGN_v0.1.md §3

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project_meta (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
  model_id            TEXT PRIMARY KEY,
  name                TEXT NOT NULL,
  backend             TEXT NOT NULL,
  task_type           TEXT NOT NULL,
  model_path          TEXT NOT NULL,
  config_path         TEXT,
  package_id          TEXT,
  version             TEXT,
  class_map_json      TEXT,
  default_params_json TEXT,
  source              TEXT,
  enabled             INTEGER NOT NULL DEFAULT 1,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
  profile_id  TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT,
  payload_json TEXT NOT NULL,
  is_default  INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id            TEXT PRIMARY KEY,
  type               TEXT NOT NULL,
  status             TEXT NOT NULL,
  progress           REAL NOT NULL DEFAULT 0,
  progress_detail_json TEXT,
  params_json        TEXT NOT NULL,
  profile_id         TEXT,
  session_id         TEXT,
  project_id         TEXT,
  error              TEXT,
  error_code         TEXT,
  result_ref         TEXT,
  parent_task_id     TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  finished_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

CREATE TABLE IF NOT EXISTS media (
  media_id     TEXT PRIMARY KEY,
  task_id      TEXT NOT NULL,
  kind         TEXT NOT NULL,
  path         TEXT NOT NULL,
  width        INTEGER,
  height       INTEGER,
  fps          REAL,
  frame_count  INTEGER,
  duration_ms  INTEGER,
  sha256       TEXT,
  created_at   TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_media_task ON media(task_id);

CREATE TABLE IF NOT EXISTS frames (
  task_id         TEXT NOT NULL,
  frame_id        INTEGER NOT NULL,
  media_id        TEXT,
  infer_ms        REAL,
  pipeline_ms     REAL,
  is_detect_frame INTEGER NOT NULL DEFAULT 1,
  meta_json       TEXT,
  created_at      TEXT NOT NULL,
  PRIMARY KEY (task_id, frame_id),
  FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS objects (
  task_id      TEXT NOT NULL,
  frame_id     INTEGER NOT NULL,
  object_id    INTEGER NOT NULL,
  model_id     TEXT NOT NULL,
  class_id     INTEGER NOT NULL,
  class_name   TEXT NOT NULL,
  display_name TEXT,
  confidence   REAL NOT NULL,
  geom_type    TEXT NOT NULL,
  geom_json    TEXT NOT NULL,
  track_id     INTEGER,
  visible      INTEGER NOT NULL DEFAULT 1,
  style_json   TEXT,
  extra_json   TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  PRIMARY KEY (task_id, frame_id, object_id, model_id),
  FOREIGN KEY (task_id, frame_id) REFERENCES frames(task_id, frame_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_objects_frame ON objects(task_id, frame_id);
CREATE INDEX IF NOT EXISTS idx_objects_model ON objects(model_id);

CREATE TABLE IF NOT EXISTS ops (
  op_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT NOT NULL,
  frame_id    INTEGER,
  action      TEXT NOT NULL,
  target_type TEXT,
  target_id   TEXT,
  payload_json TEXT NOT NULL,
  actor       TEXT,
  created_at  TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ops_task ON ops(task_id, frame_id);
