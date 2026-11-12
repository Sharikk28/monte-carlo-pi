let limits = null;
let timer = null;
const rows = new Map();

function showAuth() {
    clearInterval(timer);
    document.getElementById("auth").hidden = false;
    document.getElementById("app").hidden = true;
}

function showApp(user) {
    limits = user.limits;
    rows.clear();
    document.getElementById("tasks").replaceChildren();
    document.getElementById("auth").hidden = true;
    document.getElementById("app").hidden = false;
    document.getElementById("who").textContent = user.username;
    document.getElementById("adminLink").hidden = !user.is_admin;
    document.getElementById("limits").textContent =
        "Від " + limits.min_points + " до " + limits.max_points + " точок, " +
        "не довше " + limits.max_seconds + " с, " +
        "не більше " + limits.max_active + " активних задач одночасно.";
    loadTasks();
    clearInterval(timer);
    timer = setInterval(loadTasks, 1000);
}

async function authorize(path) {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    try {
        const user = await api("POST", path, {username: username, password: password});
        document.getElementById("password").value = "";
        showMessage("");
        showApp(user);
    } catch (problem) {
        showMessage(problem.message);
    }
}

async function logout() {
    await api("POST", "/api/logout");
    showAuth();
}

async function startTask() {
    const points = Number(document.getElementById("points").value);
    if (!Number.isInteger(points) || points < limits.min_points || points > limits.max_points) {
        showMessage("Відмова: кількість точок має бути цілим числом від " +
            limits.min_points + " до " + limits.max_points);
        return;
    }
    try {
        const task = await api("POST", "/api/tasks", {points: points});
        if (task.eta_seconds > 0) {
            showMessage("Усі сервери зайняті. Задачу №" + task.id + " поставлено в чергу, місце " +
                task.position + ", приблизний час очікування " + task.eta_seconds + " с");
        } else {
            showMessage("");
        }
        loadTasks();
    } catch (problem) {
        showMessage("Відмова: " + problem.message);
    }
}

async function cancelTask(id) {
    try {
        await api("POST", "/api/tasks/" + id + "/cancel");
        showMessage("");
        loadTasks();
    } catch (problem) {
        showMessage(problem.message);
    }
}

async function loadTasks() {
    let tasks;
    try {
        tasks = await api("GET", "/api/tasks");
    } catch (problem) {
        if (problem.status === 401) {
            showAuth();
        }
        return;
    }
    const body = document.getElementById("tasks");
    for (const task of tasks.reverse()) {
        if (!rows.has(task.id)) {
            rows.set(task.id, createRow(task));
            body.prepend(rows.get(task.id));
        }
        updateRow(rows.get(task.id), task);
    }
}

function createRow(task) {
    const row = document.createElement("tr");
    for (let index = 0; index < 10; index++) {
        row.insertCell();
    }
    const bar = document.createElement("progress");
    bar.max = 100;
    row.cells[4].append(bar, document.createElement("span"));
    const button = document.createElement("button");
    button.textContent = "Скасувати";
    button.onclick = () => cancelTask(task.id);
    row.cells[9].append(button);
    return row;
}

function updateRow(row, task) {
    row.cells[0].textContent = task.id;
    row.cells[1].textContent = task.created;
    row.cells[2].textContent = task.points.toLocaleString("uk-UA");
    row.cells[3].textContent = STATUS_NAMES[task.status];
    row.cells[3].className = task.status;
    row.cells[4].firstChild.value = task.progress;
    row.cells[4].lastChild.textContent = " " + task.progress + "%";
    row.cells[5].textContent = describeStage(task);
    row.cells[6].textContent = task.worker;
    row.cells[7].textContent = task.seconds === null ? "" : task.seconds.toFixed(1);
    row.cells[8].textContent = describeResult(task);
    row.cells[9].firstChild.hidden = task.status !== "queued" && task.status !== "running";
}

async function start() {
    document.getElementById("login").onclick = () => authorize("/api/login");
    document.getElementById("register").onclick = () => authorize("/api/register");
    document.getElementById("logout").onclick = logout;
    document.getElementById("start").onclick = startTask;
    try {
        showApp(await api("GET", "/api/me"));
    } catch (problem) {
        showAuth();
    }
}

start();
