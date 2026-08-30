"""Carga Docentes.xlsx a una base de datos SQLite normalizada.

Uso:
    python cargar_db.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

NOMBRE_EXCEL = "Docentes.xlsx"
NOMBRE_DB = "docentes.db"

DIAS = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]

# (TIPO)DAY HHMM:HHMM(AULA)  |  (AVIR)SIN :(-Sin asignar)
REGEX_SESION = re.compile(
    r"^\(([^)]+)\)"
    r"([A-Z]{3})"
    r"\s*"
    r"(\d{0,4}):(\d{0,4})"
    r"\(([^)]*)\)$"
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS campus (
    id_campus    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS modalidad (
    id_modalidad INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS asignatura (
    cod_asignatura TEXT PRIMARY KEY,
    nombre         TEXT NOT NULL,
    tipo_curso     TEXT NOT NULL,
    plan           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS docente (
    id_docente     INTEGER PRIMARY KEY AUTOINCREMENT,
    dni            TEXT UNIQUE,
    apellidos      TEXT,
    nombres        TEXT,
    nombre_completo TEXT
);

CREATE TABLE IF NOT EXISTS seccion (
    nrc                TEXT PRIMARY KEY,
    id_campus          INTEGER NOT NULL REFERENCES campus(id_campus),
    id_modalidad       INTEGER NOT NULL REFERENCES modalidad(id_modalidad),
    cod_asignatura     TEXT NOT NULL REFERENCES asignatura(cod_asignatura),
    id_docente         INTEGER NOT NULL REFERENCES docente(id_docente),
    metodo_asistencia  TEXT,
    estado             TEXT NOT NULL,
    parte_periodo      TEXT NOT NULL,
    bloque             TEXT,
    f_inicio           TEXT,
    f_fin              TEXT
);

CREATE TABLE IF NOT EXISTS horario (
    id_horario  INTEGER PRIMARY KEY AUTOINCREMENT,
    nrc         TEXT NOT NULL REFERENCES seccion(nrc),
    tipo_sesion TEXT NOT NULL,
    dia         TEXT,
    hora_inicio TEXT,
    hora_fin    TEXT,
    aula        TEXT
);

CREATE INDEX IF NOT EXISTS idx_seccion_curso ON seccion(cod_asignatura);
CREATE INDEX IF NOT EXISTS idx_horario_nrc  ON horario(nrc);
"""


def parsear_sesiones(texto):
    """Convierte 'HOR' (una o varias sesiones separadas por |) en tuplas."""
    sesiones = []
    if not isinstance(texto, str) or not texto.strip():
        return sesiones
    for parte in texto.split("|"):
        m = REGEX_SESION.match(parte.strip())
        if not m:
            continue
        tipo, dia, ini, fin, aula = m.groups()
        if dia not in DIAS:
            dia = None
        sesiones.append((tipo, dia, ini or None, fin or None, aula or None))
    return sesiones


def normalizar_nombre_docente(nombre):
    """'GARCIA, PENA Yahaira Shirley*' -> (apellidos, nombres)."""
    limpio = re.sub(r"[*\s]+$", "", str(nombre).strip())
    if "," in limpio:
        apellidos, nombres = limpio.split(",", 1)
        return apellidos.strip(), nombres.strip()
    return None, limpio


def a_fecha(valor):
    """Convierte '17/08/2026' -> '2026-08-17' (ISO) o None."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        d, m, a = valor.strip().split("/")
        return f"{int(a):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return None


def cargar():
    base = Path(__file__).resolve().parent
    ruta_excel = base / NOMBRE_EXCEL
    ruta_db = base / NOMBRE_DB

    df = pd.read_excel(ruta_excel, dtype={"NRC": str})
    df.columns = df.columns.str.strip()
    df["NRC"] = df["NRC"].fillna("").str.strip()
    df["CURSO"] = df["CURSO"].fillna("").str.strip()

    conexion = sqlite3.connect(ruta_db)
    conexion.executescript("PRAGMA foreign_keys = ON;" + ESQUEMA)
    cursor = conexion.cursor()
    cursor.executescript(
        "DELETE FROM horario; DELETE FROM seccion; DELETE FROM docente; "
        "DELETE FROM asignatura; DELETE FROM modalidad; DELETE FROM campus;"
    )
    conexion.commit()

    campus_ids = {}
    modalidad_ids = {}

    for fila in df.itertuples(index=False):
        camp = str(getattr(fila, "CAMPUS")).strip()
        mod = str(getattr(fila, "MODALIDAD")).strip()

        if camp not in campus_ids:
            cursor.execute("INSERT INTO campus (nombre) VALUES (?)", (camp,))
            campus_ids[camp] = cursor.lastrowid
        if mod not in modalidad_ids:
            cursor.execute("INSERT INTO modalidad (nombre) VALUES (?)", (mod,))
            modalidad_ids[mod] = cursor.lastrowid

        cursor.execute(
            "INSERT OR IGNORE INTO asignatura "
            "(cod_asignatura, nombre, tipo_curso, plan) VALUES (?,?,?,?)",
            (
                str(getattr(fila, "COD_ASIGNATURA")).strip(),
                getattr(fila, "CURSO"),
                str(getattr(fila, "TIPO_CURSO")).strip(),
                str(getattr(fila, "DESCRIPCION_ATRIBUTO_PLAN")).strip(),
            ),
        )

        dni = re.sub(r"\*", "", str(getattr(fila, "DNI_DOCENTE"))).strip()
        apellidos, nombres = normalizar_nombre_docente(getattr(fila, "DOCENTE"))
        cursor.execute(
            "INSERT OR IGNORE INTO docente "
            "(dni, apellidos, nombres, nombre_completo) VALUES (?,?,?,?)",
            (
                dni,
                apellidos,
                nombres,
                f"{apellidos or ''}, {nombres or ''}".strip(", "),
            ),
        )

        cursor.execute("SELECT id_docente FROM docente WHERE dni = ?", (dni,))
        id_docente = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO seccion "
            "(nrc, id_campus, id_modalidad, cod_asignatura, id_docente, "
            " metodo_asistencia, estado, parte_periodo, bloque, f_inicio, f_fin) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                getattr(fila, "NRC"),
                campus_ids[camp],
                modalidad_ids[mod],
                str(getattr(fila, "COD_ASIGNATURA")).strip(),
                id_docente,
                str(getattr(fila, "METODO_ASISTENCIA")).strip() or None,
                str(getattr(fila, "ESTADO_DESCRIPCION")).strip(),
                str(getattr(fila, "PARTEPERIODO")).strip(),
                str(getattr(fila, "BLOQUE")).strip() or None,
                a_fecha(getattr(fila, "F_INICIO")),
                a_fecha(getattr(fila, "F_FIN")),
            ),
        )

        for tipo, dia, ini, fin, aula in parsear_sesiones(
            getattr(fila, "HOR")
        ):
            cursor.execute(
                "INSERT INTO horario "
                "(nrc, tipo_sesion, dia, hora_inicio, hora_fin, aula) "
                "VALUES (?,?,?,?,?,?)",
                (getattr(fila, "NRC"), tipo, dia, ini, fin, aula),
            )

    conexion.commit()

    totales = {t: cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in ("campus", "modalidad", "asignatura", "docente",
                         "seccion", "horario")}
    conexion.close()

    print("Carga completada en", ruta_db)
    for tabla, total in totales.items():
        print(f"  {tabla:12} {total:>6} filas")


if __name__ == "__main__":
    cargar()