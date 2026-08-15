import express from "express";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3000;
const DATA_FILE = "confirmaciones.json";

const GITHUB_TOKEN = process.env.GITHUB_TOKEN || "";
const GITHUB_REPO = process.env.GITHUB_REPO || "alvarezemiliove-eng/BODA_GEN-EM";
const GITHUB_BRANCH = process.env.GITHUB_BRANCH || "main";
const AUTH_TOKEN = process.env.AUTH_TOKEN || "";

const app = express();
app.use(express.json());
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Confirm-Token");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

function servir(archivo) {
  return (req, res) => res.sendFile(path.join(__dirname, archivo));
}

app.get("/", servir("index.html"));
app.get("/invitacion.html", servir("invitacion.html"));
app.get("/hoteles.html", servir("hoteles.html"));
app.get("/regalos.html", servir("regalos.html"));
app.get("/confirmaciones.html", servir("confirmaciones.html"));
app.get("/config.js", servir("config.js"));
app.use("/assets", express.static(path.join(__dirname, "assets")));

const HEADERS = {
  "Authorization": "Bearer " + GITHUB_TOKEN,
  "User-Agent": "boda-app",
  "Accept": "application/vnd.github+json",
};

async function leerLocal() {
  try {
    return JSON.parse(await readFile(path.join(__dirname, DATA_FILE), "utf8"));
  } catch {
    return null;
  }
}

async function leerRepo() {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/contents/${DATA_FILE}?ref=${encodeURIComponent(GITHUB_BRANCH)}`,
    { headers: HEADERS }
  );
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("GET contents " + r.status);
  const j = await r.json();
  return { sha: j.sha, data: JSON.parse(Buffer.from(j.content, "base64").toString("utf8")) };
}

async function escribirRepo(data, sha) {
  const body = {
    message: "Nueva confirmación de boda",
    branch: GITHUB_BRANCH,
    content: Buffer.from(JSON.stringify(data, null, 2), "utf8").toString("base64"),
  };
  if (sha) body.sha = sha;
  const r = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/${DATA_FILE}`, {
    method: "PUT",
    headers: HEADERS,
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error("PUT contents " + r.status + " " + t.slice(0, 300));
  }
  return r.json();
}

async function cargarDatos() {
  if (GITHUB_TOKEN) {
    const repo = await leerRepo();
    if (repo) return { data: repo.data, sha: repo.sha };
  }
  const local = await leerLocal();
  if (local) return { data: local, sha: null };
  throw new Error("No hay datos de confirmaciones.");
}

async function guardarDatos(data) {
  await writeFile(path.join(__dirname, DATA_FILE), JSON.stringify(data, null, 2), "utf8");
  if (GITHUB_TOKEN) {
    const repo = await leerRepo();
    await escribirRepo(data, repo ? repo.sha : null);
  }
}

function norm(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

app.get("/api/confirmaciones", async (req, res) => {
  try {
    const { data } = await cargarDatos();
    res.json(Array.isArray(data) ? data : []);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/api/confirmar", async (req, res) => {
  try {
    if (AUTH_TOKEN && req.headers["x-confirm-token"] !== AUTH_TOKEN) {
      return res.status(401).json({ error: "Token no válido" });
    }
    const { familia = "", integrantes = [], asistentes = [] } = req.body || {};
    const todos = Array.isArray(integrantes) && integrantes.length
      ? integrantes
      : (Array.isArray(asistentes) ? asistentes : []);
    const presentes = Array.isArray(asistentes) ? asistentes : [];
    if (!Array.isArray(todos) || !todos.length) {
      return res.status(400).json({ error: "Faltan integrantes" });
    }
    const { data, sha } = await cargarDatos();
    const filas = Array.isArray(data) ? data : [];
    const famB = norm(familia);
    const todosSet = new Set(todos.map((x) => norm(x)));
    const presentesSet = new Set(presentes.map((x) => norm(x)));
    let nuevos = 0, ya = 0, encontrados = 0, asistentesMarca = 0;
    for (const fila of filas) {
      if (famB && norm(fila.familia) !== famB) continue;
      const n = norm(fila.nombre);
      if (!todosSet.has(n)) continue;
      encontrados++;
      if (fila.confirmacion === "Confirmado") { ya++; } else {
        fila.confirmacion = "Confirmado";
        fila.fecha = new Date().toISOString();
        nuevos++;
      }
      if (presentesSet.has(n) && fila.asistira !== "Sí") {
        fila.asistira = "Sí";
        asistentesMarca++;
      }
    }
    await writeFile(path.join(__dirname, DATA_FILE), JSON.stringify(filas, null, 2), "utf8");
    if (GITHUB_TOKEN) {
      try {
        await escribirRepo(filas, sha);
      } catch (e) {
        return res.status(502).json({ error: "No se pudo guardar en GitHub: " + e.message });
      }
    }
    res.json({ ok: true, nuevos, ya, encontrados, asistentesMarca, total: filas.length });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/api/estado", async (req, res) => {
  try {
    if (AUTH_TOKEN && req.headers["x-confirm-token"] !== AUTH_TOKEN) {
      return res.status(401).json({ error: "Token no válido" });
    }
    const { nombre = "", familia = "", confirmacion = "", asistira = "" } = req.body || {};
    if (!nombre.trim()) {
      return res.status(400).json({ error: "Falta el nombre" });
    }
    const { data, sha } = await cargarDatos();
    const filas = Array.isArray(data) ? data : [];
    const nomB = norm(nombre);
    const famB = norm(familia);
    let encontrados = 0;
    for (const fila of filas) {
      if (norm(fila.nombre) !== nomB) continue;
      if (famB && norm(fila.familia) !== famB) continue;
      encontrados++;
      if (confirmacion === "Confirmado" || confirmacion === "No confirmado") {
        fila.confirmacion = confirmacion;
        fila.fecha = confirmacion === "Confirmado" ? (fila.fecha || new Date().toISOString()) : "";
      }
      if (asistira === "Sí" || asistira === "No") fila.asistira = asistira;
    }
    await writeFile(path.join(__dirname, DATA_FILE), JSON.stringify(filas, null, 2), "utf8");
    if (GITHUB_TOKEN) {
      try {
        await escribirRepo(filas, sha);
      } catch (e) {
        return res.status(502).json({ error: "No se pudo guardar en GitHub: " + e.message });
      }
    }
    res.json({ ok: true, encontrados, total: filas.length });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => {
  console.log("Boda app escuchando en http://localhost:" + PORT);
});
