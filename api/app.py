import math
import os
import random

from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import query

API_NAME = os.environ["API_NAME"]
MIN_POINTS = int(os.environ["MIN_POINTS"])
MAX_POINTS = int(os.environ["MAX_POINTS"])
MAX_SECONDS = int(os.environ["MAX_SECONDS"])
MAX_ACTIVE_PER_USER = int(os.environ["MAX_ACTIVE_PER_USER"])
MAX_QUEUE = int(os.environ["MAX_QUEUE"])
MAX_WORKERS = int(os.environ["MAX_WORKERS"])
DEAD_SECONDS = int(os.environ["DEAD_SECONDS"])
DEFAULT_TASK_SECONDS = 15
MAX_SEED = 2000000000
PUBLIC_PATHS = ["/api/register", "/api/login"]

TASK_COLUMNS = """
    t.id, t.points, t.seed, t.status, t.stage, t.progress, t.worker, t.result, t.error,
    to_char(t.created_at AT TIME ZONE 'Europe/Kyiv', 'DD.MM HH24:MI:SS') AS created,
    EXTRACT(EPOCH FROM COALESCE(t.finished_at, now()) - t.started_at)::float AS seconds,
    (SELECT count(*) FROM tasks q WHERE q.status = 'queued' AND q.id <= t.id) AS position
"""

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

query(
    "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, TRUE) "
    "ON CONFLICT (username) DO NOTHING",
    (os.environ["ADMIN_USER"], generate_password_hash(os.environ["ADMIN_PASSWORD"])),
)


def error(message, code):
    return jsonify({"error": message}), code


def read_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def remember(user):
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["is_admin"] = user["is_admin"]


def current_user():
    return {
        "username": session["username"],
        "is_admin": session["is_admin"],
        "limits": {
            "min_points": MIN_POINTS,
            "max_points": MAX_POINTS,
            "max_seconds": MAX_SECONDS,
            "max_active": MAX_ACTIVE_PER_USER,
            "max_queue": MAX_QUEUE,
            "max_workers": MAX_WORKERS,
        },
    }


def add_wait(tasks):
    workers = query(
        "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'idle') AS idle "
        "FROM workers WHERE last_heartbeat > now() - make_interval(secs => %s)",
        (DEAD_SECONDS,),
        one=True,
    )
    average = query(
        "SELECT COALESCE(avg(seconds), %s)::float AS s FROM ("
        "SELECT EXTRACT(EPOCH FROM finished_at - started_at) AS seconds FROM tasks "
        "WHERE status = 'done' ORDER BY finished_at DESC LIMIT 20) AS recent",
        (DEFAULT_TASK_SECONDS,),
        one=True,
    )["s"]
    for task in tasks:
        if task["status"] == "queued":
            ahead = max(task["position"] - workers["idle"], 0)
            task["eta_seconds"] = math.ceil(ahead * average / max(workers["total"], 1))
        else:
            task["position"] = None
            task["eta_seconds"] = None
    return tasks


@app.before_request
def check_access():
    if request.path in PUBLIC_PATHS:
        return None
    user = query(
        "SELECT is_admin FROM users WHERE id = %s AND username = %s",
        (session.get("user_id"), session.get("username")),
        one=True,
    )
    if user is None:
        session.clear()
        return error("Потрібно увійти", 401)
    if request.path.startswith("/api/admin") and not user["is_admin"]:
        return error("Доступ лише для адміністратора", 403)
    return None


@app.after_request
def add_server_name(response):
    response.headers["X-Served-By"] = API_NAME
    return response


@app.post("/api/register")
def register():
    data = read_body()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username.isalnum() or len(username) < 3 or len(username) > 30:
        return error("Логін: від 3 до 30 літер або цифр", 400)
    if len(password) < 6:
        return error("Пароль: щонайменше 6 символів", 400)
    user = query(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s) "
        "ON CONFLICT (username) DO NOTHING RETURNING id, username, is_admin",
        (username, generate_password_hash(password)),
        one=True,
    )
    if user is None:
        return error("Такий логін уже зайнятий", 409)
    remember(user)
    return jsonify(current_user()), 201


@app.post("/api/login")
def login():
    data = read_body()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    user = query(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = %s",
        (username,),
        one=True,
    )
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("Неправильний логін або пароль", 401)
    remember(user)
    return jsonify(current_user())


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    return jsonify(current_user())


@app.post("/api/tasks")
def create_task():
    data = read_body()
    points = data.get("points")
    seed = data.get("seed")
    if type(points) is not int or points < MIN_POINTS or points > MAX_POINTS:
        return error(f"Кількість точок: ціле число від {MIN_POINTS} до {MAX_POINTS}", 400)
    if seed is None:
        seed = random.randint(1, MAX_SEED)
    if type(seed) is not int or seed < 0 or seed > MAX_SEED:
        return error(f"Seed: ціле число від 0 до {MAX_SEED}", 400)
    active = query(
        "SELECT count(*) AS c FROM tasks WHERE user_id = %s AND status IN ('queued', 'running')",
        (session["user_id"],),
        one=True,
    )["c"]
    if active >= MAX_ACTIVE_PER_USER:
        return error(f"Забагато активних задач (максимум {MAX_ACTIVE_PER_USER})", 429)
    queued = query("SELECT count(*) AS c FROM tasks WHERE status = 'queued'", one=True)["c"]
    if queued >= MAX_QUEUE:
        return error("Система перевантажена, черга заповнена. Спробуйте пізніше", 503)
    created = query(
        "INSERT INTO tasks (user_id, points, seed) VALUES (%s, %s, %s) RETURNING id",
        (session["user_id"], points, seed),
        one=True,
    )
    tasks = query(f"SELECT {TASK_COLUMNS} FROM tasks t WHERE t.id = %s", (created["id"],))
    return jsonify(add_wait(tasks)[0]), 201


@app.get("/api/tasks")
def list_tasks():
    tasks = query(
        f"SELECT {TASK_COLUMNS} FROM tasks t WHERE t.user_id = %s ORDER BY t.id DESC LIMIT 50",
        (session["user_id"],),
    )
    return jsonify(add_wait(tasks))


@app.get("/api/tasks/<int:task_id>")
def get_task(task_id):
    tasks = query(
        f"SELECT {TASK_COLUMNS} FROM tasks t WHERE t.id = %s AND t.user_id = %s",
        (task_id, session["user_id"]),
    )
    if not tasks:
        return error("Задачу не знайдено", 404)
    return jsonify(add_wait(tasks)[0])


@app.post("/api/tasks/<int:task_id>/cancel")
def cancel_task(task_id):
    owner = (task_id, session["user_id"])
    cancelled = query(
        "UPDATE tasks SET status = 'cancelled', stage = 'Скасовано користувачем', finished_at = now() "
        "WHERE id = %s AND user_id = %s AND status = 'queued' RETURNING id",
        owner,
        one=True,
    )
    if cancelled is not None:
        return jsonify({"ok": True})
    asked = query(
        "UPDATE tasks SET cancel_requested = TRUE "
        "WHERE id = %s AND user_id = %s AND status = 'running' RETURNING id",
        owner,
        one=True,
    )
    if asked is not None:
        return jsonify({"ok": True})
    exists = query("SELECT id FROM tasks WHERE id = %s AND user_id = %s", owner, one=True)
    if exists is None:
        return error("Задачу не знайдено", 404)
    return error("Задача вже завершена", 409)


@app.get("/api/admin/overview")
def admin_overview():
    workers = query(
        "SELECT name, status, task_id, tasks_done, stop_requested, "
        "EXTRACT(EPOCH FROM now() - last_heartbeat)::float AS heartbeat_age, "
        "EXTRACT(EPOCH FROM now() - status_since)::float AS state_seconds "
        "FROM workers ORDER BY name"
    )
    tasks = query(
        f"SELECT {TASK_COLUMNS}, u.username FROM tasks t JOIN users u ON u.id = t.user_id "
        "WHERE t.status IN ('queued', 'running') ORDER BY t.id"
    )
    totals = query(
        "SELECT count(*) FILTER (WHERE status = 'queued') AS queued, "
        "count(*) FILTER (WHERE status = 'running') AS running, "
        "count(*) FILTER (WHERE status = 'done') AS done, "
        "count(*) AS total FROM tasks",
        one=True,
    )
    return jsonify(
        {
            "workers": workers,
            "tasks": add_wait(tasks),
            "totals": totals,
            "max_workers": MAX_WORKERS,
            "dead_seconds": DEAD_SECONDS,
        }
    )
