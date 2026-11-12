import os
import signal
import sys
import time

import docker

from db import query

MAX_WORKERS = int(os.environ["MAX_WORKERS"])
CHECK_SECONDS = int(os.environ["CHECK_SECONDS"])
IDLE_SECONDS = int(os.environ["IDLE_SECONDS"])
DEAD_SECONDS = int(os.environ["DEAD_SECONDS"])
WORKER_IMAGE = os.environ["WORKER_IMAGE"]
NETWORK = os.environ["NETWORK"]
AUTO_PREFIX = "worker-auto-"
AUTO_LABEL = "pi.auto"

client = docker.from_env()


def auto_containers():
    return client.containers.list(all=True, filters={"label": AUTO_LABEL})


def recover_dead():
    dead = query(
        "DELETE FROM workers WHERE last_heartbeat < now() - make_interval(secs => %s) RETURNING name",
        (DEAD_SECONDS,),
    )
    for worker in dead:
        returned = query(
            "UPDATE tasks SET status = 'queued', stage = 'Повернено в чергу', progress = 0, "
            "worker = NULL, started_at = NULL WHERE status = 'running' AND worker = %s RETURNING id",
            (worker["name"],),
        )
        print(f"scaler: {worker['name']} не відповідає, повернено задач у чергу: {len(returned)}")


def scale_up():
    queued = query("SELECT count(*) AS c FROM tasks WHERE status = 'queued'", one=True)["c"]
    workers = query("SELECT name, status FROM workers")
    registered = [worker["name"] for worker in workers]
    idle = len([worker for worker in workers if worker["status"] == "idle"])
    containers = [container.name for container in auto_containers()]
    starting = len([name for name in containers if name not in registered])
    if queued <= idle + starting:
        return
    if len(registered) + starting >= MAX_WORKERS:
        return
    number = 1
    while AUTO_PREFIX + str(number) in containers:
        number += 1
    name = AUTO_PREFIX + str(number)
    client.containers.run(
        WORKER_IMAGE,
        name=name,
        hostname=name,
        network=NETWORK,
        detach=True,
        auto_remove=True,
        labels={AUTO_LABEL: "true"},
        environment={
            "WORKER_NAME": name,
            "DATABASE_URL": os.environ["DATABASE_URL"],
            "MAX_SECONDS": os.environ["MAX_SECONDS"],
        },
    )
    print(f"scaler: у черзі {queued}, вільних серверів {idle}, запущено {name}")


def scale_down():
    queued = query("SELECT count(*) AS c FROM tasks WHERE status = 'queued'", one=True)["c"]
    if queued > 0:
        return
    stopped = query(
        "UPDATE workers SET stop_requested = TRUE "
        "WHERE starts_with(name, %s) AND status = 'idle' AND NOT stop_requested "
        "AND status_since < now() - make_interval(secs => %s) RETURNING name",
        (AUTO_PREFIX, IDLE_SECONDS),
    )
    for worker in stopped:
        print(f"scaler: {worker['name']} простоює понад {IDLE_SECONDS} с, зупиняю")


def remove_auto_workers():
    for container in auto_containers():
        container.remove(force=True)


def shutdown(number, frame):
    remove_auto_workers()
    print("scaler: зупинено, автоматичні сервери видалено")
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, shutdown)
    remove_auto_workers()
    print("scaler: запущено")
    while True:
        try:
            recover_dead()
            scale_up()
            scale_down()
        except Exception as problem:
            print(f"scaler: помилка {problem}")
        time.sleep(CHECK_SECONDS)


main()
