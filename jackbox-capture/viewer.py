import json
import sys
import html
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

if len(sys.argv) < 2:
    print()
    print("Usage:")
    print("  python viewer.py captures\\traffic.jsonl")
    print()
    raise SystemExit(1)

INPUT = Path(sys.argv[1])

if not INPUT.exists():
    print(f"Fichier introuvable : {INPUT}")
    raise SystemExit(1)

OUTPUT = INPUT.parent / "traffic_view.html"


# ============================================================
# CHARGEMENT
# ============================================================

records = []

with INPUT.open("r", encoding="utf-8") as f:
    for line_number, line in enumerate(f, 1):
        line = line.strip()

        if not line:
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"Attention : ligne JSON invalide : {line_number}")


print(f"{len(records)} événements chargés.")


# ============================================================
# HTML
# ============================================================

data_json = json.dumps(
    records,
    ensure_ascii=False
).replace("</", "<\\/")


page = r"""<!DOCTYPE html>
<html lang="fr">
<head>

<meta charset="UTF-8">

<title>Jackbox Traffic Viewer</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #111318;
    color: #e8e8e8;
}

header {
    position: sticky;
    top: 0;
    z-index: 10;

    background: #181b22;
    border-bottom: 1px solid #30343d;

    padding: 18px 24px;
}

h1 {
    margin: 0 0 14px 0;
    font-size: 22px;
}

.controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

input,
select,
button {
    background: #242832;
    color: #eee;

    border: 1px solid #3a404c;
    border-radius: 6px;

    padding: 9px 11px;

    font-size: 14px;
}

input {
    min-width: 300px;
}

button {
    cursor: pointer;
}

button:hover {
    background: #303641;
}

#stats {
    margin-top: 10px;
    color: #9da4b2;
    font-size: 13px;
}

main {
    padding: 18px 24px;
}

.group {
    margin-bottom: 20px;
}

.group-title {
    background: #1b1f27;
    border: 1px solid #30343d;

    padding: 10px 14px;

    border-radius: 7px 7px 0 0;

    font-weight: 600;
}

.event {
    border: 1px solid #292e37;
    border-top: none;

    background: #16191f;
}

.event-head {
    display: grid;

    grid-template-columns:
        105px
        125px
        minmax(160px, 1fr)
        minmax(160px, 1fr)
        90px;

    gap: 10px;

    align-items: center;

    padding: 9px 12px;

    cursor: pointer;
}

.event-head:hover {
    background: #20242c;
}

.time {
    color: #9da4b2;
    font-family: monospace;
    font-size: 12px;
}

.type {
    font-weight: 600;
}

.direction {
    font-family: monospace;
    font-size: 13px;
}

.host {
    color: #7dc8ff;
    font-family: monospace;
    font-size: 13px;
}

.method {
    color: #d8b4fe;
    font-family: monospace;
}

.body {
    display: none;

    border-top: 1px solid #292e37;

    padding: 14px;

    background: #0e1014;
}

.event.open .body {
    display: block;
}

pre {
    margin: 0;

    white-space: pre-wrap;
    word-break: break-word;

    font-family:
        "Cascadia Code",
        "Consolas",
        monospace;

    font-size: 12px;

    line-height: 1.5;

    color: #d7dae0;
}

.section {
    margin-bottom: 14px;
}

.section-title {
    color: #8f98a8;
    font-size: 12px;
    font-weight: bold;

    margin-bottom: 5px;

    text-transform: uppercase;
}

.empty {
    padding: 50px;
    text-align: center;
    color: #888;
}

.badge {
    display: inline-block;

    padding: 3px 7px;

    border-radius: 5px;

    background: #2a2f39;

    font-size: 11px;
}

</style>

</head>

<body>

<header>

<h1>Jackbox Traffic Viewer</h1>

<div class="controls">

<input
    id="search"
    type="text"
    placeholder="🔎 Rechercher dans host, URL, données..."
>

<select id="type">
    <option value="">Tous les types</option>
    <option value="http_request">HTTP Request</option>
    <option value="http_response">HTTP Response</option>
    <option value="websocket_message">WebSocket</option>
    <option value="error">Erreur</option>
</select>

<select id="direction">
    <option value="">Toutes les directions</option>
    <option value="client_to_server">Client → Serveur</option>
    <option value="server_to_client">Serveur → Client</option>
</select>

<input
    id="host"
    type="text"
    placeholder="Filtrer par domaine..."
>

<button onclick="expandAll()">
    Tout ouvrir
</button>

<button onclick="collapseAll()">
    Tout fermer
</button>

<button onclick="clearFilters()">
    Effacer filtres
</button>

</div>

<div id="stats"></div>

</header>


<main id="content"></main>


<script>

const DATA = __DATA__;

const searchInput = document.getElementById("search");
const typeSelect = document.getElementById("type");
const directionSelect = document.getElementById("direction");
const hostInput = document.getElementById("host");

const content = document.getElementById("content");
const stats = document.getElementById("stats");


function formatTime(timestamp) {

    if (!timestamp)
        return "";

    const d = new Date(timestamp * 1000);

    return d.toLocaleTimeString(
        "fr-FR",
        {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            fractionalSecondDigits: 3
        }
    );
}


function safe(value) {

    if (value === null || value === undefined)
        return "";

    return String(value);
}


function jsonPretty(value) {

    if (value === null || value === undefined)
        return "";

    if (typeof value !== "string")
        return JSON.stringify(value, null, 2);

    try {

        const parsed = JSON.parse(value);

        return JSON.stringify(
            parsed,
            null,
            2
        );

    } catch {

        return value;
    }
}


function searchable(record) {

    return JSON.stringify(record).toLowerCase();
}


function direction(record) {

    if (record.direction)
        return record.direction;

    if (record.type === "http_request")
        return "client_to_server";

    if (record.type === "http_response")
        return "server_to_client";

    return "";
}


function getGroup(record) {

    return (
        record.host ||
        record.server?.[0] ||
        "inconnu"
    );
}


function render() {

    const search =
        searchInput.value
            .trim()
            .toLowerCase();

    const type =
        typeSelect.value;

    const wantedDirection =
        directionSelect.value;

    const wantedHost =
        hostInput.value
            .trim()
            .toLowerCase();


    const filtered = DATA.filter(record => {

        if (type && record.type !== type)
            return false;

        if (
            wantedDirection &&
            direction(record) !== wantedDirection
        )
            return false;

        if (
            wantedHost &&
            !getGroup(record)
                .toLowerCase()
                .includes(wantedHost)
        )
            return false;

        if (
            search &&
            !searchable(record).includes(search)
        )
            return false;

        return true;
    });


    stats.textContent =
        `${filtered.length} événement(s) affiché(s) / ${DATA.length} total`;


    if (!filtered.length) {

        content.innerHTML =
            `<div class="empty">
                Aucun événement correspondant aux filtres.
             </div>`;

        return;
    }


    const groups = new Map();


    for (const record of filtered) {

        const group = getGroup(record);

        if (!groups.has(group))
            groups.set(group, []);

        groups.get(group).push(record);
    }


    content.innerHTML = "";


    for (const [groupName, events] of groups) {

        const group = document.createElement("div");

        group.className = "group";


        const title = document.createElement("div");

        title.className = "group-title";

        title.innerHTML =
            `${escapeHtml(groupName)}
             <span class="badge">
                ${events.length}
             </span>`;


        group.appendChild(title);


        for (const record of events) {

            group.appendChild(
                createEvent(record)
            );
        }


        content.appendChild(group);
    }
}


function createEvent(record) {

    const event = document.createElement("div");

    event.className = "event";


    const head = document.createElement("div");

    head.className = "event-head";


    const time = document.createElement("div");

    time.className = "time";

    time.textContent =
        formatTime(record.timestamp);


    const type = document.createElement("div");

    type.className = "type";

    type.textContent =
        record.type;


    const dir = document.createElement("div");

    dir.className = "direction";

    const d = direction(record);

    dir.textContent =
        d === "client_to_server"
            ? "→ serveur"
            : d === "server_to_client"
                ? "← serveur"
                : "";


    const host = document.createElement("div");

    host.className = "host";

    host.textContent =
        record.host ||
        record.server?.[0] ||
        "";


    const method = document.createElement("div");

    method.className = "method";

    method.textContent =
        record.method ||
        (
            record.status
                ? String(record.status)
                : ""
        );


    head.appendChild(time);
    head.appendChild(type);
    head.appendChild(dir);
    head.appendChild(host);
    head.appendChild(method);


    const body = document.createElement("div");

    body.className = "body";


    // --------------------------------------------------------
    // URL
    // --------------------------------------------------------

    if (record.url) {

        body.appendChild(
            section(
                "URL",
                record.url
            )
        );
    }


    // --------------------------------------------------------
    // PATH
    // --------------------------------------------------------

    if (record.path) {

        body.appendChild(
            section(
                "PATH",
                record.path
            )
        );
    }


    // --------------------------------------------------------
    // CLIENT / SERVER
    // --------------------------------------------------------

    if (record.client || record.server) {

        body.appendChild(
            section(
                "CONNEXION",
                JSON.stringify(
                    {
                        client: record.client,
                        server: record.server
                    },
                    null,
                    2
                )
            )
        );
    }


    // --------------------------------------------------------
    // HEADERS
    // --------------------------------------------------------

    if (record.headers) {

        body.appendChild(
            section(
                "HEADERS",
                JSON.stringify(
                    record.headers,
                    null,
                    2
                )
            )
        );
    }


    // --------------------------------------------------------
    // BODY / CONTENT
    // --------------------------------------------------------

    const payload =
        record.body ??
        record.content;


    if (
        payload !== undefined &&
        payload !== null &&
        payload !== ""
    ) {

        body.appendChild(
            section(
                "DATA",
                jsonPretty(payload)
            )
        );
    }


    // --------------------------------------------------------
    // ERROR
    // --------------------------------------------------------

    if (record.error) {

        body.appendChild(
            section(
                "ERREUR",
                record.error
            )
        );
    }


    event.appendChild(head);
    event.appendChild(body);


    head.onclick = () => {

        event.classList.toggle("open");

    };


    return event;
}


function section(title, value) {

    const div =
        document.createElement("div");

    div.className = "section";


    const titleDiv =
        document.createElement("div");

    titleDiv.className =
        "section-title";

    titleDiv.textContent =
        title;


    const pre =
        document.createElement("pre");

    pre.textContent =
        safe(value);


    div.appendChild(titleDiv);
    div.appendChild(pre);


    return div;
}


function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function expandAll() {

    document
        .querySelectorAll(".event")
        .forEach(event => {

            event.classList.add("open");

        });
}


function collapseAll() {

    document
        .querySelectorAll(".event")
        .forEach(event => {

            event.classList.remove("open");

        });
}


function clearFilters() {

    searchInput.value = "";
    typeSelect.value = "";
    directionSelect.value = "";
    hostInput.value = "";

    render();
}


searchInput.addEventListener(
    "input",
    render
);

typeSelect.addEventListener(
    "change",
    render
);

directionSelect.addEventListener(
    "change",
    render
);

hostInput.addEventListener(
    "input",
    render
);


render();

</script>

</body>
</html>
"""


page = page.replace(
    "__DATA__",
    data_json
)


# ============================================================
# ÉCRITURE
# ============================================================

OUTPUT.write_text(
    page,
    encoding="utf-8"
)


print()
print("Viewer créé :")
print(OUTPUT)
print()
print("Ouvre ce fichier dans Chrome ou Edge.")