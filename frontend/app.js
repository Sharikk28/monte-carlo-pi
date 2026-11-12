let limits = null;
let timer = null;

function showAuth() {
    clearInterval(timer);
    document.getElementById("auth").hidden = false;
    document.getElementById("app").hidden = true;
}

function showApp(user) {
    limits = user.limits;
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
    body.replaceChildren();
    for (const task of tasks) {
        const row = body.insertRow();
        addCell(row, task.id);
        addCell(row, task.created);
        addCell(row, task.points.toLocaleString("uk-UA"));
        addCell(row, STATUS_NAMES[task.status]).className = task.status;
        addProgress(row, task);
        addCell(row, describeStage(task));
        addCell(row, task.worker);
        addCell(row, task.seconds === null ? "" : task.seconds.toFixed(1));
        addCell(row, describeResult(task));
        const action = row.insertCell();
        if (task.status === "queued" || task.status === "running") {
            const button = document.createElement("button");
            button.textContent = "Скасувати";
            button.onclick = () => cancelTask(task.id);
            action.append(button);
        }
    }
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
