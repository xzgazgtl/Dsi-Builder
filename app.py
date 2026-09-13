import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template_string

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

JOBS_DIR = Path("/tmp/dsi_builder_jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

BUILD_TIMEOUT = 300


HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Button Rush DSi Builder</title>
<style>
body {
    background:#15161a;
    color:#fff;
    font-family:Arial,sans-serif;
    margin:0;
    padding:20px;
}
.container {
    max-width:700px;
    margin:auto;
}
h1 {
    font-size:30px;
}
.card {
    background:#222328;
    border:1px solid #333;
    border-radius:18px;
    padding:20px;
    margin-top:20px;
}
input {
    width:100%;
    box-sizing:border-box;
    padding:14px;
    border-radius:10px;
    border:1px solid #555;
    background:#18191d;
    color:white;
}
button {
    width:100%;
    padding:16px;
    margin-top:15px;
    border:0;
    border-radius:12px;
    font-size:18px;
    font-weight:bold;
    cursor:pointer;
}
#status {
    margin-top:15px;
    font-size:17px;
}
a.download {
    display:block;
    margin-top:20px;
    padding:16px;
    background:white;
    color:#111;
    text-align:center;
    border-radius:12px;
    font-weight:bold;
    text-decoration:none;
}
.ok {
    color:#62e87b;
}
.error {
    color:#ff7070;
}
</style>
</head>
<body>
<div class="container">

<h1>🎮 Button Rush DSi Builder</h1>
<p>ZIP → verificar → compilar → .NDS</p>

<div class="card">
<h2>📦 Projeto C/Makefile em ZIP</h2>

<input id="file" type="file" accept=".zip">

<button onclick="build()">⚙️ Compilar para .NDS</button>

<div id="status"></div>

<div id="download"></div>
</div>

<div class="card">
<h2>Como funciona</h2>
<p>1. Escolha o ZIP do projeto C.</p>
<p>2. O Builder procura o Makefile.</p>
<p>3. O servidor usa devkitARM/libnds.</p>
<p>4. Se der certo, aparece o .nds.</p>
</div>

</div>

<script>
async function build() {

    const file = document.getElementById("file").files[0];
    const status = document.getElementById("status");
    const download = document.getElementById("download");

    download.innerHTML = "";

    if (!file) {
        status.innerHTML = '<span class="error">❌ Escolha um arquivo ZIP.</span>';
        return;
    }

    status.innerHTML = "⏳ Enviando e compilando com devkitARM...";

    const form = new FormData();
    form.append("file", file);

    try {

        const response = await fetch("/api/build", {
            method: "POST",
            body: form
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            status.innerHTML =
                '<span class="error">❌ Erro na compilação.</span><br><pre>' +
                (data.output || data.error || "Erro desconhecido") +
                '</pre>';
            return;
        }

        status.innerHTML =
            '<span class="ok">✅ Compilação concluída!</span>';

        download.innerHTML =
            '<a class="download" href="' +
            data.download +
            '">⬇️ Baixar ButtonRush.nds</a>';

    } catch (error) {

        status.innerHTML =
            '<span class="error">❌ Erro de conexão: ' +
            error.message +
            '</span>';
    }
}
</script>

</body>
</html>
"""


def find_command(name, alternatives=None):
    """Encontra uma ferramenta no PATH ou em caminhos conhecidos."""

    path = shutil.which(name)

    if path:
        return path

    alternatives = alternatives or []

    for candidate in alternatives:
        if Path(candidate).exists():
            return candidate

    return None


def safe_extract(zip_path, destination):
    """Extrai ZIP com proteção contra Zip Slip."""

    destination = destination.resolve()

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.infolist():

            member_path = (destination / member.filename).resolve()

            if not str(member_path).startswith(str(destination)):
                raise RuntimeError(
                    f"Arquivo suspeito no ZIP: {member.filename}"
                )

        z.extractall(destination)


def find_makefile(root):
    """Procura o Makefile dentro do projeto."""

    for path in root.rglob("Makefile"):
        if path.is_file():
            return path

    for path in root.rglob("makefile"):
        if path.is_file():
            return path

    return None


def find_nds(root):
    """Procura o arquivo NDS produzido pelo Makefile."""

    candidates = list(root.rglob("*.nds"))

    if not candidates:
        return None

    candidates.sort(
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    return candidates[0]


def print_log(message):
    """Mostra mensagens imediatamente nos logs do Render."""

    print(message, flush=True)


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/health")
def health():

    gcc = find_command(
        "arm-none-eabi-gcc",
        [
            "/opt/devkitpro/devkitARM/bin/arm-none-eabi-gcc",
            "/opt/devkitpro/devkitARM/arm-none-eabi/bin/arm-none-eabi-gcc"
        ]
    )

    make = find_command(
        "make",
        [
            "/usr/bin/make"
        ]
    )

    ndstool = find_command(
        "ndstool",
        [
            "/opt/devkitpro/tools/bin/ndstool"
        ]
    )

    return jsonify({
        "ok": True,
        "gcc": gcc,
        "make": make,
        "ndstool": ndstool,
        "devkitpro": os.environ.get("DEVKITPRO"),
        "devkitarm": os.environ.get("DEVKITARM")
    })


@app.route("/api/build", methods=["POST"])
def build():

    print_log("")
    print_log("========================================")
    print_log("🚀 NOVA COMPILAÇÃO BUTTON RUSH")
    print_log("========================================")

    uploaded = request.files.get("file")

    if uploaded is None:
        print_log("❌ Nenhum arquivo enviado.")
        return jsonify({
            "success": False,
            "error": "Nenhum arquivo ZIP enviado."
        }), 400

    if not uploaded.filename.lower().endswith(".zip"):
        print_log("❌ O arquivo não é ZIP.")
        return jsonify({
            "success": False,
            "error": "Envie um arquivo .zip."
        }), 400

    job_id = uuid.uuid4().hex

    job_dir = JOBS_DIR / job_id
    zip_dir = job_dir / "upload"
    project_dir = job_dir / "project"

    job_dir.mkdir(parents=True, exist_ok=True)
    zip_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    zip_path = zip_dir / "project.zip"

    try:

        uploaded.save(zip_path)

        print_log(f"📦 ZIP recebido: {uploaded.filename}")
        print_log(f"📏 Tamanho: {zip_path.stat().st_size} bytes")
        print_log(f"🆔 Job: {job_id}")

        print_log("📂 Extraindo ZIP...")

        safe_extract(zip_path, project_dir)

        print_log("✅ ZIP extraído.")

        makefile = find_makefile(project_dir)

        if makefile is None:
            print_log("❌ Makefile não encontrado.")

            return jsonify({
                "success": False,
                "error": "Makefile não encontrado no ZIP."
            }), 400

        project_root = makefile.parent

        print_log(f"📄 Makefile encontrado: {makefile}")
        print_log(f"📁 Diretório do projeto: {project_root}")

        gcc = find_command(
            "arm-none-eabi-gcc",
            [
                "/opt/devkitpro/devkitARM/bin/arm-none-eabi-gcc",
                "/opt/devkitpro/devkitARM/arm-none-eabi/bin/arm-none-eabi-gcc"
            ]
        )

        make = find_command(
            "make",
            [
                "/usr/bin/make"
            ]
        )

        ndstool = find_command(
            "ndstool",
            [
                "/opt/devkitpro/tools/bin/ndstool"
            ]
        )

        print_log(f"🔧 GCC: {gcc}")
        print_log(f"🔧 Make: {make}")
        print_log(f"🔧 ndstool: {ndstool}")

        if not gcc:
            raise RuntimeError("arm-none-eabi-gcc não encontrado.")

        if not make:
            raise RuntimeError("make não encontrado.")

        if not ndstool:
            raise RuntimeError("ndstool não encontrado.")

        env = os.environ.copy()

        extra_paths = [
            "/opt/devkitpro/tools/bin",
            "/opt/devkitpro/devkitARM/bin",
            "/opt/devkitpro/devkitARM/arm-none-eabi/bin",
            "/opt/devkitpro/pacman/bin",
            "/opt/devkitpro/portlibs/nds/bin"
        ]

        old_path = env.get("PATH", "")

        env["PATH"] = ":".join(
            extra_paths + [old_path]
        )

        env["DEVKITPRO"] = env.get(
            "DEVKITPRO",
            "/opt/devkitpro"
        )

        env["DEVKITARM"] = env.get(
            "DEVKITARM",
            "/opt/devkitpro/devkitARM"
        )

        print_log("")
        print_log("========================================")
        print_log("🛠️ INICIANDO MAKE")
        print_log("========================================")

        command = [
            make,
            "-j2"
        ]

        print_log(
            "▶️ Comando: " +
            " ".join(command)
        )

        print_log(
            f"📁 CWD: {project_root}"
        )

        process = subprocess.Popen(
            command,
            cwd=str(project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []

        try:

            for line in iter(process.stdout.readline, ""):

                if line == "":
                    break

                line = line.rstrip()

                output_lines.append(line)

                # MOSTRA IMEDIATAMENTE NO RENDER
                print_log("[MAKE] " + line)

            process.stdout.close()

            return_code = process.wait(
                timeout=BUILD_TIMEOUT
            )

        except subprocess.TimeoutExpired:

            process.kill()

            print_log(
                f"⏰ COMPILAÇÃO EXCEDEU {BUILD_TIMEOUT} SEGUNDOS."
            )

            return jsonify({
                "success": False,
                "error": "A compilação excedeu o tempo limite.",
                "output": "\n".join(output_lines)
            }), 504

        output = "\n".join(output_lines)

        print_log("")
        print_log(
            f"🏁 MAKE terminou com código: {return_code}"
        )

        if return_code != 0:

            print_log("❌ ERRO DE COMPILAÇÃO!")

            return jsonify({
                "success": False,
                "error": "make terminou com erro.",
                "output": output
            }), 500

        print_log("✅ MAKE terminou com sucesso.")

        nds_file = find_nds(project_root)

        if nds_file is None:

            print_log(
                "❌ MAKE terminou, mas nenhum .nds foi encontrado."
            )

            return jsonify({
                "success": False,
                "error": "A compilação terminou, mas nenhum arquivo .nds foi encontrado.",
                "output": output
            }), 500

        print_log(
            f"🎮 NDS ENCONTRADO: {nds_file}"
        )

        final_name = "ButtonRush.nds"

        final_path = job_dir / final_name

        shutil.copy2(
            nds_file,
            final_path
        )

        print_log(
            f"✅ ARQUIVO FINAL: {final_path}"
        )

        print_log("")
        print_log("========================================")
        print_log("🎉 BUTTON RUSH COMPILADO COM SUCESSO!")
        print_log("========================================")

        return jsonify({
            "success": True,
            "job_id": job_id,
            "filename": final_name,
            "download": f"/api/download/{job_id}"
        })

    except Exception as e:

        print_log("")
        print_log("========================================")
        print_log("💥 ERRO NO BUILDER")
        print_log("========================================")

        print_log(str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/download/<job_id>")
def download(job_id):

    job_dir = JOBS_DIR / job_id
    file_path = job_dir / "ButtonRush.nds"

    if not file_path.exists():
        return jsonify({
            "error": "Arquivo NDS não encontrado."
        }), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name="ButtonRush.nds"
    )


if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
