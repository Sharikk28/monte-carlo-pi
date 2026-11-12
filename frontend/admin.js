function describeWorker(worker, deadSeconds) {
    if (worker.heartbeat_age > deadSeconds) {
        return "Не відповідає";
    }
    if (worker.stop_requested) {
        return "Зупиняється";
    }
    return worker.status === "busy" ? "Зайнятий" : "Вільний";
}

async function loadOverview() {
    let overview;
    try {
        overview = await api("GET", "/api/admin/overview");
    } catch (problem) {
        showMessage(problem.message);
        return;
    }
    showMessage("");

    const busy = overview.workers.filter(worker => worker.status === "busy").length;
    const total = overview.workers.length;
    const load = total === 0 ? 0 : Math.round(100 * busy / total);
    document.getElementById("summary").textContent =
        "Серверів обчислень: " + total + " із " + overview.max_workers + " можливих. " +
        "Зайнято: " + busy + " (навантаження " + load + "%). " +
        "У черзі: " + overview.totals.queued + ". " +
        "Виконується: " + overview.totals.running + ". " +
        "Виконано за весь час: " + overview.totals.done + " із " + overview.totals.total + ".";

    const workers = document.getElementById("workers");
    workers.replaceChildren();
    for (const worker of overview.workers) {
        const row = workers.insertRow();
        addCell(row, worker.name);
        addCell(row, describeWorker(worker, overview.dead_seconds)).className = worker.status;
        addCell(row, worker.task_id === null ? "" : "№" + worker.task_id);
        addCell(row, worker.state_seconds.toFixed(0));
        addCell(row, worker.heartbeat_age.toFixed(1));
        addCell(row, worker.tasks_done);
    }

    const tasks = document.getElementById("tasks");
    tasks.replaceChildren();
    for (const task of overview.tasks) {
        const row = tasks.insertRow();
        addCell(row, task.id);
        addCell(row, task.username);
        addCell(row, task.points.toLocaleString("uk-UA"));
        addCell(row, STATUS_NAMES[task.status]).className = task.status;
        addProgress(row, task);
        addCell(row, describeStage(task));
        addCell(row, task.worker);
        addCell(row, task.seconds === null ? "" : task.seconds.toFixed(1));
    }
}

loadOverview();
setInterval(loadOverview, 2000);
