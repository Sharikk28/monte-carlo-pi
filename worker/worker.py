import json
import os
import time

from db import query
from solver import solve

WORKER_NAME = os.environ["WORKER_NAME"]
MAX_SECONDS = int(os.environ["MAX_SECONDS"])


class Cancelled(Exception):
    pass


class TimeLimit(Exception):
    pass


def heartbeat():
    row = query(
        "INSERT INTO workers (name) VALUES (%s) "
        "ON CONFLICT (name) DO UPDATE SET last_heartbeat = now() RETURNING stop_requested",
        (WORKER_NAME,),
        one=True,
    )
    return row["stop_requested"]


def take_task():
    return query(
        "UPDATE tasks SET status = 'running', stage = 'Початок обчислення', worker = %s, started_at = now() "
        "WHERE id = (SELECT id FROM tasks WHERE status = 'queued' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED) "
        "RETURNING id, points, seed",
        (WORKER_NAME,),
        one=True,
    )


def set_state(status, task_id):
    query(
        "UPDATE workers SET status = %s, task_id = %s, status_since = now() WHERE name = %s",
        (status, task_id, WORKER_NAME),
    )


def finish(task_id, status, stage, result=None, error=None):
    query(
        "UPDATE tasks SET status = %s, stage = %s, result = %s, error = %s, finished_at = now() "
        "WHERE id = %s AND worker = %s",
        (status, stage, result, error, task_id, WORKER_NAME),
    )
    print(f"{WORKER_NAME}: задача {task_id} -> {status}")


def run(task):
    started = time.time()

    def on_progress(percent, stage):
        row = query(
            "UPDATE tasks SET progress = %s, stage = %s "
            "WHERE id = %s AND worker = %s AND status = 'running' RETURNING cancel_requested",
            (percent, stage, task["id"], WORKER_NAME),
            one=True,
        )
        heartbeat()
        if row is None or row["cancel_requested"]:
            raise Cancelled()
        if time.time() - started > MAX_SECONDS:
            raise TimeLimit()

    try:
        result = solve(task["points"], task["seed"], on_progress)
        result["seconds"] = round(time.time() - started, 2)
        finish(task["id"], "done", "Готово", result=json.dumps(result))
    except Cancelled:
        finish(task["id"], "cancelled", "Скасовано користувачем")
    except TimeLimit:
        finish(task["id"], "timeout", "Зупинено", error=f"Перевищено ліміт часу {MAX_SECONDS} с")
    except Exception as problem:
        finish(task["id"], "failed", "Помилка", error=str(problem))


def main():
    query("DELETE FROM workers WHERE name = %s", (WORKER_NAME,))
    query(
        "UPDATE tasks SET status = 'queued', stage = 'Повернено в чергу', progress = 0, "
        "worker = NULL, started_at = NULL WHERE status = 'running' AND worker = %s",
        (WORKER_NAME,),
    )
    print(f"{WORKER_NAME}: запущено")
    while not heartbeat():
        task = take_task()
        if task is None:
            time.sleep(1)
            continue
        print(f"{WORKER_NAME}: взяв задачу {task['id']} на {task['points']} точок")
        set_state("busy", task["id"])
        run(task)
        set_state("idle", None)
        query("UPDATE workers SET tasks_done = tasks_done + 1 WHERE name = %s", (WORKER_NAME,))
    query("DELETE FROM workers WHERE name = %s", (WORKER_NAME,))
    print(f"{WORKER_NAME}: зупинено на вимогу scaler")


main()
