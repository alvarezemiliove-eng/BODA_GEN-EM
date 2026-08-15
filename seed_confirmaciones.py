#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convierte 'Base Invitaciones.xlsx' en confirmaciones.json (estado inicial).

Las familias aparecen en la columna "Nombre de la Invitacion" (celdas
combinadas: solo la primera fila trae el nombre, el resto lo hereda).
Lo mismo aplica para "Valido Para".

Uso:
    python seed_confirmaciones.py            # usa 'Base Invitaciones.xlsx'
    python seed_confirmaciones.py <archivo>  # usa otro xlsx
"""
import sys
import json
import unicodedata

import openpyxl

XLSX_DEFECTO = "Base Invitaciones.xlsx"
OUT = "confirmaciones.json"


def limpiar_telefono(t):
    return "".join(ch for ch in str(t) if ch.isdigit())


def principal():
    ruta = sys.argv[1] if len(sys.argv) > 1 else XLSX_DEFECTO
    wb = openpyxl.load_workbook(ruta, data_only=True)
    ws = wb.worksheets[0]

    filas = []
    familia_actual = ""
    valido_actual = ""
    n_inv_actual = ""

    for r in ws.iter_rows(min_row=2, values_only=True):
        if len(r) < 9:
            continue
        nombre = str(r[2] or "").strip()
        if not nombre:
            continue
        inv = str(r[3] or "").strip()
        valido = str(r[4] or "").strip()
        n_inv = r[1]
        if inv:
            familia_actual = inv
        if valido:
            valido_actual = valido
        if n_inv is not None:
            n_inv_actual = str(n_inv).strip()
        filas.append({
            "n_inv": n_inv_actual,
            "nombre": nombre,
            "familia": familia_actual,
            "telefono": limpiar_telefono(r[5] or ""),
            "valido": valido_actual,
            "confirmacion": "No confirmado",
            "asistira": "No",
            "fecha": "",
        })

    if not filas:
        sys.exit("No se encontraron invitados en {0}".format(ruta))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False, indent=2)

    print("OK: {0} invitados -> {1}".format(len(filas), OUT))
    # muestra un pequeño resumen por familia para verificar
    familias = {}
    for fila in filas:
        familias.setdefault(fila["familia"], []).append(fila["nombre"])
    print("Familias: {0}".format(len(familias)))
    for fam, nombres in list(familias.items())[:5]:
        print("  - {0} ({1})".format(fam, ", ".join(nombres)))


if __name__ == "__main__":
    principal()
