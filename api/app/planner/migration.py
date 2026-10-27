SCHEMA = '''
CREATE TABLE IF NOT EXISTS planner_records (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS planner_records_scope ON planner_records(user_id,kind,created_at);
CREATE TABLE IF NOT EXISTS planner_jobs (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 result TEXT, error TEXT, dedup_key TEXT UNIQUE, priority INTEGER NOT NULL DEFAULT 10,
 attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 retry_at TEXT
);
CREATE INDEX IF NOT EXISTS planner_jobs_queue ON planner_jobs(status,priority,created_at);
INSERT OR IGNORE INTO planner_records(id,user_id,kind,payload,version,created_at,updated_at)
 SELECT 'legacy-'||id,user_id,'task',json_object('title',title,'date',due_on,'category','study',
 'note',note,'status',CASE WHEN is_done=1 THEN 'done' ELSE 'pending' END,'locked',0,
 'start_time',null,'end_time',null,'due_on',due_on,'source_id',id),1,created_at,updated_at
 FROM nodes WHERE kind='task' AND due_on IS NOT NULL;
'''
