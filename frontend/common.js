const STATUS_NAMES = {
    queued: "У черзі",
    running: "Виконується",
    done: "Виконано",
    cancelled: "Скасовано",
    timeout: "Перевищено час",
    failed: "Помилка"
};

async function api(method, path, body) {
    const response = await fetch(path, {
        method: method,
        headers: {"Content-Type": "application/json"},
        body: body ? JSON.stringify(body) : undefined
    });
    const server = response.headers.get("X-Served-By");
    if (server) {
        document.getElementById("server").textContent = server;
    }
    let data;
    try {
        data = await response.json();
    } catch (problem) {
        data = {error: "Сервер тимчасово недоступний"};
    }
    if (!response.ok) {
        const failure = new Error(data.error);
        failure.status = response.status;
        throw failure;
    }
    return data;
}

function showMessage(text) {
    document.getElementById("message").textContent = text;
}

function addCell(row, text) {
    const cell = row.insertCell();
    cell.textContent = text === null || text === undefined ? "" : text;
    return cell;
}

function addProgress(row, task) {
    const cell = row.insertCell();
    const bar = document.createElement("progress");
    bar.max = 100;
    bar.value = task.progress;
    cell.append(bar, " " + task.progress + "%");
}

function describeStage(task) {
    if (task.status === "queued" && task.eta_seconds > 0) {
        return "Місце в черзі: " + task.position + ", очікування ≈ " + task.eta_seconds + " с";
    }
    return task.stage;
}

function describeResult(task) {
    if (task.result) {
        return "π ≈ " + task.result.pi.toFixed(6) + ", похибка " + task.result.error.toFixed(6);
    }
    return task.error;
}
