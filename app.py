import os
import re
import shutil
import subprocess
import zipfile
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

BASE = Path("/tmp/buttonrush-builder")
BASE.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD = 50 * 1024 * 1024
TIMEOUT = 300

DEVKITPRO = "/opt/devkitpro"
DEVKITARM = "/opt/devkitpro/devkitARM"

TOOL_PATHS = [
    "/opt/devkitpro/tools/bin",
    "/opt/devkitpro/devkitARM/bin",
    "/opt/devkitpro/pacman/bin",
    "/opt/devkitpro/portlibs/nds/bin",
]


def get_environment():
    env = os.environ.copy()
    env["DEVKITPRO"] = DEVKITPRO
    env["DEVKITARM"] = DEVKITARM

    current_path = env.get("PATH", "")
    env["PATH"] = ":".join(TOOL_PATHS) + ":" + current_path

    return env


def find_tool(name):
    env = get_environment()

    path = shutil.which(name, path=env["PATH"])

    if path:
        return path

    known_paths = {
        "ndstool": "/opt/devkitpro/tools/bin/ndstool",
        "make": "/usr/bin/make",
        "arm-none-eabi-gcc":
            "/opt/devkitpro/devkitARM/bin/arm-none-eabi-gcc",
    }

    path = known_paths.get(name)

    if path and os.path.isfile(path):
        return path

    return None


def safe_extract(zf, dest):
    root = dest.resolve()

    for info in zf.infolist():
        name = info.filename.replace("\\", "/")

        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("ZIP inválido: caminho inseguro.")

        target = (dest / name).resolve()

        if not str(target).startswith(str(root) + os.sep) and target != root:
            raise ValueError("ZIP inválido: caminho inseguro.")

    zf.extractall(dest)


def find_project(root):
    makefiles = list(root.rglob("Makefile"))

    if not makefiles:
        return None

    makefiles.sort(
        key=lambda p: (
            0 if (p.parent / "source").exists() else 1,
            len(p.parts)
        )
    )

    return makefiles[0].parent


def run_build(project, log_file):
    env = get_environment()

    make_path = find_tool("make")

    if not make_path:
        raise RuntimeError(
            "Não encontrei o comando make no servidor."
        )

    proc = subprocess.run(
        [make_path, "-j2"],
        cwd=project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=TIMEOUT
    )

    log_file.write_text(
        proc.stdout,
        encoding="utf-8",
        errors="replace"
    )

    return proc.returncode, proc.stdout


HTML = r"""
<!doctype html>
<html lang="pt-BR">

<head>

<meta charset="utf-8">

<meta name="viewport"
      content="width=device-width,initial-scale=1">

<title>Button Rush DSi Builder</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #111;
    color: #eee;
    font-family: system-ui, -apple-system, Segoe UI, sans-serif;
}

main {
    max-width: 680px;
    margin: auto;
    padding: 20px 14px 40px;
}

h1 {
    font-size: 25px;
    margin: 8px 0;
}

.sub {
    color: #aaa;
    margin-top: 0;
}

.card {
    background: #1d1d1d;
    border: 1px solid #333;
    border-radius: 14px;
    padding: 16px;
    margin: 14px 0;
}

label {
    display: block;
    font-weight: 700;
    margin-bottom: 10px;
}

input {
    width: 100%;
    padding: 12px;
    background: #292929;
    color: #fff;
    border-radius: 10px;
    border: 1px solid #555;
}

.checks {
    font-size: 14px;
    margin-top: 8px;
    color: #bbb;
}

.ok {
    color: #7ee787;
}

.bad {
    color: #ff7b72;
}

button {
    width: 100%;
    margin-top: 14px;
    padding: 14px;
    border: 0;
    border-radius: 10px;
    background: #eee;
    color: #111;
    font-weight: 800;
    font-size: 16px;
}

button:disabled {
    opacity: .45;
}

.download {
    display: block;
    text-align: center;
    margin-top: 14px;
    padding: 14px;
    border-radius: 10px;
    background: #eee;
    color: #111;
    text-decoration: none;
    font-weight: 800;
}

.bar {
    height: 10px;
    background: #333;
    border-radius: 20px;
    overflow: hidden;
}

.bar span {
    display: block;
    height: 100%;
    width: 0;
    background: #eee;
    transition: width .3s;
}

.info {
    color: #ccc;
}

.info ol {
    padding-left: 22px;
    line-height: 1.7;
}

#filename {
    margin-top: 8px;
    color: #aaa;
    font-size: 14px;
    word-break: break-all;
}

pre {
    white-space: pre-wrap;
    max-height: 300px;
    overflow: auto;
    background: #090909;
    border-radius: 10px;
    padding: 12px;
    font-size: 12px;
    margin-top: 12px;
}

</style>

</head>

<body>

<main>

<h1>🎮 Button Rush DSi Builder</h1>

<p class="sub">
ZIP → verificar → compilar → .NDS
</p>

<section class="card">

<div id="status">
🔄 Verificando ambiente...
</div>

<div id="checks" class="checks"></div>

</section>

<section class="card">

<label for="project">
📦 Projeto C/Makefile em ZIP
</label>

<input
    id="project"
    type="file"
    accept=".zip,application/zip"
>

<div id="filename">
Nenhum arquivo escolhido
</div>

<button id="build" disabled>
⚙️ Compilar para .NDS
</button>

<div id="progress" hidden>

<div class="bar">
<span id="bar"></span>
</div>

<p id="progressText">
Enviando...
</p>

</div>

<pre id="log" hidden></pre>

<a
    id="download"
    class="download"
    hidden
>
⬇️ Baixar ButtonRush.nds
</a>

</section>

<section class="card info">

<b>Como funciona</b>

<ol>
<li>Escolha o ZIP do projeto C.</li>
<li>O Builder procura o Makefile.</li>
<li>O servidor usa devkitARM/libnds.</li>
<li>Se der certo, aparece o .nds.</li>
</ol>

</section>

<script>

const file =
    document.getElementById("project");

const nameBox =
    document.getElementById("filename");

const build =
    document.getElementById("build");

const status =
    document.getElementById("status");

const checks =
    document.getElementById("checks");

const progress =
    document.getElementById("progress");

const bar =
    document.getElementById("bar");

const progressText =
    document.getElementById("progressText");

const log =
    document.getElementById("log");

const download =
    document.getElementById("download");


async function health() {

    try {

        const response =
            await fetch("/api/health");

        const data =
            await response.json();

        status.textContent =
            data.ok
            ? "✅ Ambiente pronto para compilar"
            : "⚠️ Ambiente incompleto";

        checks.innerHTML =
            Object.entries(data.checks)
            .map(([key, value]) => {

                return (
                    '<div class="' +
                    (value ? "ok" : "bad") +
                    '">' +
                    (value ? "✓" : "✗") +
                    " " +
                    key +
                    "</div>"
                );

            })
            .join("");

        build.disabled = !data.ok;

    } catch (error) {

        status.textContent =
            "❌ Não foi possível verificar o servidor";

        build.disabled = true;
    }
}


file.addEventListener("change", () => {

    if (file.files[0]) {

        nameBox.textContent =
            file.files[0].name +
            " (" +
            Math.round(
                file.files[0].size / 1024
            ) +
            " KB)";

    } else {

        nameBox.textContent =
            "Nenhum arquivo escolhido";
    }

    download.hidden = true;
    log.hidden = true;
});


build.addEventListener("click", async () => {

    if (!file.files[0]) {

        alert("Escolha um ZIP primeiro.");
        return;
    }

    build.disabled = true;

    progress.hidden = false;
    log.hidden = true;
    download.hidden = true;

    bar.style.width = "15%";

    progressText.textContent =
        "Enviando projeto...";

    const formData =
        new FormData();

    formData.append(
        "project",
        file.files[0]
    );

    try {

        bar.style.width = "35%";

        progressText.textContent =
            "Compilando com devkitARM...";

        const response =
            await fetch(
                "/api/build",
                {
                    method: "POST",
                    body: formData
                }
            );

        const data =
            await response.json();

        bar.style.width = "100%";

        if (data.ok) {

            progressText.textContent =
                "✅ Compilação concluída!";

            download.href =
                data.file;

            download.hidden = false;

        } else {

            progressText.textContent =
                "❌ Falha na compilação";

            log.hidden = false;

            log.textContent =
                data.error +
                "\n\n" +
                (data.log || "");
        }

    } catch (error) {

        progressText.textContent =
            "❌ Erro de conexão";

        log.hidden = false;

        log.textContent =
            String(error);

    } finally {

        build.disabled = false;
    }

});


health();

</script>

</main>

</body>

</html>
"""


@app.get("/")
def index():
    return HTML


@app.get("/api/health")
def health():

    checks = {}
    paths = {}

    for cmd in [
        "make",
        "arm-none-eabi-gcc",
        "ndstool"
    ]:

        path = find_tool(cmd)

        paths[cmd] = path
        checks[cmd] = path is not None

    return jsonify({
        "ok": all(checks.values()),
        "checks": checks,
        "paths": paths,
        "devkitpro": os.environ.get(
            "DEVKITPRO",
            DEVKITPRO
        ),
        "devkitarm": os.environ.get(
            "DEVKITARM",
            DEVKITARM
        )
    })


@app.post("/api/build")
def build():

    uploaded = request.files.get("project")

    if (
        not uploaded
        or not uploaded.filename.lower().endswith(".zip")
    ):

        return jsonify({
            "ok": False,
            "error":
                "Envie um arquivo .zip de um projeto NDS com Makefile."
        }), 400

    data = uploaded.read(MAX_UPLOAD + 1)

    if len(data) > MAX_UPLOAD:

        return jsonify({
            "ok": False,
            "error":
                "ZIP muito grande. Limite: 50 MB."
        }), 413

    job_id = uuid.uuid4().hex

    job = BASE / job_id
    src = job / "src"
    out = job / "out"

    job.mkdir()
    src.mkdir()
    out.mkdir()

    zip_path = job / "project.zip"

    zip_path.write_bytes(data)

    log_path = job / "build.log"

    try:

        with zipfile.ZipFile(zip_path) as zf:

            safe_extract(
                zf,
                src
            )

        project = find_project(src)

        if not project:

            return jsonify({
                "ok": False,
                "error":
                    "Não encontrei um Makefile no ZIP."
            }), 400

        rc, log = run_build(
            project,
            log_path
        )

        nds = sorted(
            project.rglob("*.nds"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if rc != 0 or not nds:

            tail = (
                log[-12000:]
                if log
                else
                "Sem saída do compilador."
            )

            return jsonify({
                "ok": False,
                "error":
                    "A compilação falhou.",
                "log":
                    tail
            }), 422

        artifact =
            out / "ButtonRush.nds"

        shutil.copy2(
            nds[0],
            artifact
        )

        return jsonify({
            "ok": True,
            "message":
                "Compilação concluída!",
            "job":
                job_id,
            "file":
                f"/api/download/{job_id}"
        })

    except subprocess.TimeoutExpired:

        return jsonify({
            "ok": False,
            "error":
                "A compilação demorou mais de 5 minutos e foi interrompida."
        }), 408

    except zipfile.BadZipFile:

        return jsonify({
            "ok": False,
            "error":
                "O arquivo enviado não é um ZIP válido."
        }), 400

    except Exception as e:

        return jsonify({
            "ok": False,
            "error":
                f"Erro no Builder: {e}"
        }), 500

    finally:

        zip_path.unlink(
            missing_ok=True
        )


@app.get("/api/download/<job_id>")
def download(job_id):

    if not re.fullmatch(
        r"[0-9a-f]{32}",
        job_id
    ):

        return "ID inválido", 400

    artifact = (
        BASE /
        job_id /
        "out" /
        "ButtonRush.nds"
    )

    if not artifact.exists():

        return "Arquivo não encontrado", 404

    return send_file(
        artifact,
        as_attachment=True,
        download_name="ButtonRush.nds",
        mimetype="application/octet-stream"
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "7700"
            )
        )
)
