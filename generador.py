#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generador de invitaciones personalizadas por WhatsApp (v2).

Lee el CSV exportado de la hoja "Base de datos"
(columnas: Nombre, Nombre de la Invitacion, Válido Para,
Numero de Telefono, Numero emisor, Mensaje antes del link)
y genera por cada invitado con telefono un enlace:
    .../invitacion.html?n=<invitado>&p=<valido>&fam=<familia>&m=<integrantes>

Uso:
    python generador.py                       # usa base_datos_exportada.csv
    python generador.py <csv>                 # usa otro CSV (salida con prefijo pruebas_)
    python generador.py https://mi-sitio.netlify.app/invitacion.html
    python generador.py <csv> <url>           # ambos en cualquier orden
    python generador.py --short               # acorta los links con tinyurl
"""
import csv
import sys
import urllib.parse
import urllib.request
import os

CSV_FILE = "base_datos_exportada.csv"
ENVIO_FILE = "envio.csv"
ENLACES_FILE = "enlaces.txt"
PANEL_FILE = "panel.html"
CONFIG_FILE = "config.js"

MENSAJE_DEFECTO = (
    "Hola {nombre}! {novios} tenemos el gusto de invitarte a nuestra boda. "
    "Aqui esta tu invitacion personalizada: {link}"
)

BASE_URL_DEFECTO = "https://alvarezemiliove-eng.github.io/BODA_GEN-EM/invitacion.html"


def leer_novios():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        contenido = f.read()
    m = __import__("re").search(r'noviosCorto:\s*"([^"]+)"', contenido)
    if not m:
        sys.exit("No encontre noviosCorto en {0}".format(CONFIG_FILE))
    return m.group(1)


def limpiar_telefono(t):
    return "".join(ch for ch in str(t) if ch.isdigit())


def leer_csv(ruta):
    """Devuelve lista de dicts con las columnas de la hoja."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r.get("Nombre", "").strip()]


def agrupar_familias(filas):
    """Agrupa por 'Nombre de la Invitacion' (celdas combinadas o repetidas)."""
    familias = []
    actual = None
    for r in filas:
        inv = (r.get("Nombre de la Invitacion") or "").strip()
        if inv and inv != (actual["nombre"] if actual else None):
            if actual and actual["integrantes"]:
                familias.append(actual)
            actual = {
                "nombre": inv,
                "valido": (r.get("Válido Para") or "").strip(),
                "emisor": limpiar_telefono(r.get("Numero emisor", "")),
                "mensaje_personalizado": (r.get("Mensaje antes del link") or "").strip(),
                "integrantes": [],
            }
        nombre = (r.get("Nombre") or "").strip()
        telefono = limpiar_telefono(r.get("Numero de Telefono", ""))
        if nombre:
            actual["integrantes"].append({"nombre": nombre, "telefono": telefono})
    if actual and actual["integrantes"]:
        familias.append(actual)
    return familias


def enlace_invitacion(base, familia, integrantes, valido, remitente):
    miembros = "|".join(i["nombre"] for i in integrantes)
    url = base + "?n=" + urllib.parse.quote(remitente)
    url += "&p=" + urllib.parse.quote(valido or str(len(integrantes)))
    url += "&fam=" + urllib.parse.quote(familia)
    url += "&m=" + urllib.parse.quote(miembros)
    return url


def acortar(enlace):
    """Acorta la URL con tinyurl (sin necesidad de cuenta)."""
    api = "https://tinyurl.com/api-create.php?url=" + urllib.parse.quote(enlace, safe="")
    try:
        with urllib.request.urlopen(api, timeout=30) as r:
            corto = r.read().decode("utf-8").strip()
        return corto if corto.startswith("http") else enlace
    except Exception:
        return enlace


def mensaje_para(familia, remitente, enlace, novios):
    personalizado = (familia.get("mensaje_personalizado") or "").strip()
    if personalizado:
        if "-link-" in personalizado:
            return personalizado.replace("-link-", enlace)
        return personalizado + " " + enlace
    return MENSAJE_DEFECTO.format(nombre=remitente, novios=novios, link=enlace)


def principal():
    args = sys.argv[1:]
    base_url = BASE_URL_DEFECTO
    csv_file = CSV_FILE
    acortar_links = "--short" in args
    for a in args:
        if a.startswith("http"):
            base_url = a
        elif a.lower().endswith(".csv"):
            csv_file = a

    if not os.path.exists(csv_file):
        sys.exit(
            "No encuentro {0}. Exporta la pestaña 'Base de datos' a CSV "
            "con ese nombre en esta carpeta.".format(csv_file)
        )

    if not base_url.startswith("http"):
        sys.exit("La URL debe empezar con http:// o https://")

    pruebas = csv_file != CSV_FILE
    prefijo = "pruebas_" if pruebas else ""
    envio_file = prefijo + ENVIO_FILE
    enlaces_file = prefijo + ENLACES_FILE
    panel_file = prefijo + PANEL_FILE
    mensajes_file = prefijo + "mensajes_a_enviar.csv"

    novios = leer_novios()
    filas = leer_csv(csv_file)
    familias = agrupar_familias(filas)

    if not familias:
        sys.exit("No se pudieron agrupar familias del CSV.")

    envio = []
    enlaces = []
    manuales = []

    for fam in familias:
        familia_nombre = fam["nombre"]
        valido = fam["valido"] or str(len(fam["integrantes"]))
        emisor = fam["emisor"]
        con_telefono = [i for i in fam["integrantes"] if i["telefono"]]
        sin_telefono = [i for i in fam["integrantes"] if not i["telefono"]]

        if not con_telefono:
            manuales.append(fam)
            continue

        for inv in con_telefono:
            link = enlace_invitacion(base_url, familia_nombre, fam["integrantes"], valido, inv["nombre"])
            if acortar_links:
                link = acortar(link)
            texto = mensaje_para(fam, inv["nombre"], link, novios)
            wa = "https://wa.me/+{0}?text={1}".format(inv["telefono"], urllib.parse.quote(texto))
            envio.append({"nombre": inv["nombre"], "telefono": inv["telefono"], "emisor": emisor, "mensaje": texto})
            enlaces.append("{0}\t{1}\t{2}".format(inv["nombre"], inv["telefono"], wa))

        if sin_telefono:
            manuales.append(fam)

    with open(envio_file, "w", encoding="utf-8") as f:
        f.write("nombre,telefono,emisor,mensaje\n")
        for e in envio:
            f.write('{0},{1},{2},"{3}"\n'.format(
                e["nombre"].replace('"', '""'),
                e["telefono"],
                e["emisor"],
                e["mensaje"].replace('"', '""'),
            ))

    with open(enlaces_file, "w", encoding="utf-8") as f:
        f.write("\n".join(enlaces) + "\n")

    with open(panel_file, "w", encoding="utf-8") as f:
        f.write(generar_panel(enlaces))

    # Mensajes completos listos para copiar y pegar (envio manual)
    with open(mensajes_file, "w", encoding="utf-8") as f:
        f.write("Nombre,Telefono,Mensaje\n")
        for e in envio:
            f.write('{0},{1},"{2}"\n'.format(
                e["nombre"].replace('"', '""'),
                e["telefono"],
                e["mensaje"].replace('"', '""'),
            ))

    print("\nRESUMEN")
    print("  CSV utilizado      : {0}".format(csv_file))
    print("  Familias detectadas : {0}".format(len(familias)))
    print("  Envios automaticos  : {0}".format(len(envio)))
    print("  Familias incompletas (sin telefono de algun integrante): {0}".format(len(manuales)))
    print("\nArchivos generados:")
    print("  - {0} : mensajes listos para el enviador".format(envio_file))
    print("  - {0} : links wa.me por invitado".format(enlaces_file))
    print("  - {0} : panel de envio manual".format(panel_file))
    print("  - {0} : mensajes para copiar y pegar (envio manual)".format(mensajes_file))
    print("\nEjemplo de enlace personalizado:")
    if envio:
        print("  " + envio[0]["mensaje"])

    if manuales:
        print("\nFAMILIAS QUE REQUIEREN ATENCION MANUAL (sin todos los telefonos):")
        for fam in manuales:
            con = [i["nombre"] for i in fam["integrantes"] if i["telefono"]]
            sin = [i["nombre"] for i in fam["integrantes"] if not i["telefono"]]
            print("  - {0} (Válido: {1}) | con tlf: {2} | sin tlf: {3}".format(
                fam["nombre"], fam["valido"], ", ".join(con) or "-", ", ".join(sin) or "-"))


def generar_panel(enlaces):
    tarjetas = ""
    for linea in enlaces:
        partes = linea.split("\t")
        nombre = partes[0]
        enlace = partes[2]
        tarjetas += (
            '<div class="c">'
            "<strong>{0}</strong>"
            '<a href="{1}" target="_blank" rel="noopener">Abrir WhatsApp</a>'
            "<code>{1}</code>"
            "</div>"
        ).format(nombre, enlace)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"es\">\n"
        "<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<title>Panel de envio - Invitaciones</title>\n"
        "<style>\n"
        "  body { font-family: Georgia, serif; background: #faf6ef; color: #2e2a26; margin: 0; padding: 2rem; }\n"
        "  h1 { font-size: 1.3rem; font-weight: normal; letter-spacing: .1em; }\n"
        "  p { color: #8a8377; font-size: .9rem; }\n"
        "  .c { background: #fff; border: 1px solid rgba(176,141,87,.3); border-radius: 10px;\n"
        "       padding: 1rem 1.2rem; margin-bottom: .8rem; display: flex; align-items: center; gap: 1rem; }\n"
        "  .c strong { min-width: 160px; }\n"
        "  .c a { background: #2e2a26; color: #faf6ef; text-decoration: none; padding: .5rem 1rem;\n"
        "         border-radius: 50px; font-size: .85rem; white-space: nowrap; }\n"
        "  .c a:hover { background: #b08d57; }\n"
        "  .c code { color: #b08d57; font-size: .72rem; word-break: break-all; flex: 1; }\n"
        "  @media (max-width: 640px) { .c { flex-direction: column; align-items: flex-start; } }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Panel de envio - " + str(len(enlaces)) + " invitaciones</h1>\n"
        "<p>Haz clic en cada boton para abrir WhatsApp con el mensaje ya escrito.</p>\n"
        + tarjetas +
        "\n</body>\n</html>"
    )


if __name__ == "__main__":
    principal()
