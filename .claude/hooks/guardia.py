"""Guardia: control automático antes de que Claude guarde (commit) o suba (push) cambios.

Lo corre Claude Code solo (hook PreToolUse, ver .claude/settings.json), cada vez que
Claude va a ejecutar un comando con `git commit` o `git push`. Si encuentra un problema,
sale con código 2: Claude Code frena el comando y le muestra a Claude el motivo.

Revisa:
  1. Claves y datos personales: claves con forma de API key, archivos .env y, en las
     apps, cualquier .json que no sea el manifest ni .claude/settings.json.
  2. Apps (repos con sw.js): si cambió index.html, que VERSION de sw.js haya subido;
     y que APP_VERSION de index.html sea igual a VERSION.
  3. Apps: que el JavaScript de index.html no tenga errores de sintaxis (con node;
     si node no está instalado, se saltea).

Falso positivo: agregar `guardia:ok` en la misma línea para que la ignore.
El mismo archivo está copiado en cada repo (Personal y las apps): si se cambia, copiarlo a todos.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PATRONES_CLAVE = [
    ("clave de Google/Gemini", r"AIza[0-9A-Za-z_\-]{35}"),
    ("clave de Anthropic", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("clave de OpenAI", r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    ("token de GitHub", r"(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})"),
    ("token JWT (por ejemplo, clave de n8n)", r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("clave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("clave de AWS", r"AKIA[0-9A-Z]{16}"),
    ("clave de Slack", r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
    (
        "clave o contraseña escrita en el código",
        r"(?i)(?:api[_\-]?key|apikey|secret|token|password|passwd|contraseña|clave)[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_\-\.\/\+=]{16,})[\"']",
    ),
]
# Valores de ejemplo que no son claves de verdad.
EJEMPLO = re.compile(r"(?i)your|example|ejemplo|xxxx|placeholder|tu[_\-]|dummy|changeme|<")

MAX_BYTES = 2_000_000


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def carpetas_del_comando(comando, cwd):
    """Repos a los que apunta el comando (por `cd X` o `git -C X`); si no hay, el cwd."""
    ruta = r"(\"[^\"]+\"|'[^']+'|[^\s;&|]+)"
    encontradas = re.findall(r"(?:^|&&|;|\|\||\n)\s*cd\s+" + ruta, comando)
    encontradas += re.findall(r"\bgit\s+-C\s+" + ruta, comando)
    carpetas = []
    for c in encontradas:
        c = os.path.expanduser(c.strip("\"'"))
        if not os.path.isabs(c):
            c = os.path.join(cwd, c)
        carpetas.append(c)
    return carpetas or [cwd]


def base_remota(repo):
    for ref in ("@{u}", "origin/main", "origin/HEAD"):
        code, out = git(repo, "rev-parse", "--verify", "--quiet", ref)
        if code == 0 and out.strip():
            return ref
    return None


def archivos_cambiados(repo, base):
    if base:
        _, out = git(repo, "diff", "--name-only", base)
    else:
        _, out = git(repo, "ls-files")
    _, nuevos = git(repo, "ls-files", "--others", "--exclude-standard")
    nombres = set(l for l in (out + "\n" + nuevos).splitlines() if l.strip())
    return sorted(n for n in nombres if os.path.isfile(os.path.join(repo, n)))


def leer(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "rb") as f:
            datos = f.read()
    except OSError:
        return None
    if b"\0" in datos[:8000]:
        return None  # binario (imágenes, etc.)
    return datos.decode("utf-8", "replace")


def version_de(texto, nombre):
    m = re.search(r"\b" + nombre + r"\s*=\s*[\"']([^\"']+)[\"']", texto or "")
    return m.group(1) if m else None


def revisar_claves(repo, archivos, es_app):
    problemas = []
    for n in archivos:
        base = os.path.basename(n)
        if base == ".env" or (base.startswith(".env.") and "example" not in base and "ejemplo" not in base):
            problemas.append(f"{n}: es un archivo .env (claves). No se sube nunca.")
            continue
        if es_app and n.endswith(".json") and n != ".claude/settings.json":
            problemas.append(f"{n}: en las apps no se sube ningún .json (pueden ser datos personales).")
            continue
        texto = leer(os.path.join(repo, n))
        if texto is None:
            continue
        for num, linea in enumerate(texto.splitlines(), 1):
            if "guardia:ok" in linea:
                continue
            for nombre, patron in PATRONES_CLAVE:
                for m in re.finditer(patron, linea):
                    valor = m.group(m.lastindex or 0)
                    if EJEMPLO.search(valor):
                        continue
                    problemas.append(f"{n}, línea {num}: parece una {nombre}.")
                    break
    return problemas


def revisar_app(repo, archivos, base):
    problemas = []
    sw = leer(os.path.join(repo, "sw.js")) or ""
    html = leer(os.path.join(repo, "index.html")) or ""
    v_sw = version_de(sw, "VERSION")
    v_app = version_de(html, "APP_VERSION")

    if v_sw and v_app and v_sw != v_app:
        problemas.append(f"APP_VERSION de index.html ({v_app}) no es igual a VERSION de sw.js ({v_sw}).")

    if base and "index.html" in archivos:
        _, sw_viejo = git(repo, "show", f"{base}:sw.js")
        v_vieja = version_de(sw_viejo, "VERSION")
        if v_vieja and v_sw == v_vieja:
            problemas.append(
                f"Cambió index.html pero VERSION de sw.js sigue en {v_sw}: subila (y APP_VERSION), "
                "si no el celu sigue mostrando la versión vieja."
            )

    node = shutil.which("node")
    if node and html:
        bloques = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", html, re.S | re.I)
        for i, (attrs, codigo) in enumerate(bloques, 1):
            if re.search(r"type=[\"']?(application/(ld\+)?json|text/template)", attrs, re.I):
                continue
            ext = ".mjs" if "module" in attrs else ".js"
            with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, encoding="utf-8") as f:
                f.write(codigo)
                tmp = f.name
            try:
                r = subprocess.run([node, "--check", tmp], capture_output=True)
                if r.returncode != 0:
                    error = r.stderr.decode("utf-8", "replace").replace(tmp, f"index.html <script> n.º {i}")
                    problemas.append("El JavaScript de index.html tiene un error de sintaxis (la app quedaría en blanco):\n" + error.strip()[:800])
            finally:
                os.unlink(tmp)
    return problemas


def main():
    try:
        datos = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return 0
    comando = (datos.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\bgit\b[^;&|\n]*\b(commit|push)\b", comando):
        return 0
    cwd = datos.get("cwd") or os.getcwd()

    problemas = []
    vistos = set()
    for carpeta in carpetas_del_comando(comando, cwd):
        if not os.path.isdir(carpeta):
            continue
        code, raiz = git(carpeta, "rev-parse", "--show-toplevel")
        raiz = raiz.strip()
        if code != 0 or not raiz or raiz in vistos:
            continue
        vistos.add(raiz)
        base = base_remota(raiz)
        archivos = archivos_cambiados(raiz, base)
        es_app = os.path.isfile(os.path.join(raiz, "sw.js")) and os.path.isfile(os.path.join(raiz, "index.html"))
        encontrados = revisar_claves(raiz, archivos, es_app)
        if es_app:
            encontrados += revisar_app(raiz, archivos, base)
        problemas += [f"[{os.path.basename(raiz)}] {p}" for p in encontrados]

    if problemas:
        sys.stderr.write(
            "GUARDIA: frené este commit/push. Arreglá esto antes de seguir:\n- "
            + "\n- ".join(problemas)
            + "\n(Si es un falso positivo, agregá `guardia:ok` en esa línea y avisale a Agus.)\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
