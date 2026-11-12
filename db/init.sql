CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id),
    points INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT NOT NULL DEFAULT 'Очікує вільний сервер',
    progress INTEGER NOT NULL DEFAULT 0,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    worker TEXT,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX tasks_status_index ON tasks (status, id);

CREATE TABLE workers (
    name TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'idle',
    task_id INTEGER,
    status_since TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT now(),
    stop_requested BOOLEAN NOT NULL DEFAULT FALSE,
    tasks_done INTEGER NOT NULL DEFAULT 0
);
