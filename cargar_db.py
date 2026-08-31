"""Construye docentes.db a partir de:
- Directorio_Docentes_2026-20.xlsx  -> maestro DOCENTE (IDDOCE = DNI)
- Carga Lectiva 202620.xlsx         -> SECCION + puente docentes + HORARIO

Modelo:
    docente 1:N seccion (responsable = DNI 1) N:M via docente_seccion (rol/orden)
    seccion : horario (1:N)

Uso:
    python cargar_db.py
"""

import re
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

DIRECTORIO = "Directorio_Docentes_2026-20.xlsx"
CARGA = "Carga Lectiva 202620.xlsx"
NOMBRE_DB = "docentes.db"
PERIODO = "2026-20"

DT_RE = re.compile(r"^\(([^)]+)\)([A-Z]{3})\s*(\d{0,4}):(\d{0,4})\(([^)]*)\)")
DIAS = {"LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"}

ESQUEMA = """
CREATE TABLE campus (
    id_campus INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL UNIQUE
);

CREATE TABLE modalidad (
    id_modalidad INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE asignatura (
    cod_asignatura TEXT PRIMARY KEY,
    nombre         TEXT NOT NULL,
    tipo_curso     TEXT
);

CREATE TABLE docente (
    id_docente           TEXT PRIMARY KEY,
    apellidos            TEXT,
    nombres              TEXT,
    nombre_completo      TEXT,
    pidm                 TEXT,
    sede_codigo          TEXT,
    telefono_casa        TEXT,
    celular              TEXT,
    rpm                  TEXT,
    referencial          TEXT,
    correo_institucional TEXT,
    correo_personal      TEXT,
    correo_trabajo       TEXT,
    sexo                 TEXT,
    ciudadania           TEXT,
    estado_civil         TEXT,
    fecha_nac            TEXT,
    direccion            TEXT,
    distrito             TEXT,
    provincia            TEXT,
    departamento         TEXT,
    fuente               TEXT NOT NULL
);

CREATE TABLE seccion (
    nrc                    TEXT PRIMARY KEY,
    id_campus              INTEGER REFERENCES campus(id_campus),
    id_modalidad           INTEGER REFERENCES modalidad(id_modalidad),
    cod_asignatura         TEXT REFERENCES asignatura(cod_asignatura),
    id_docente             TEXT REFERENCES docente(id_docente),
    plan                   TEXT,
    metodo_asistencia      TEXT,
    estado                 TEXT,
    sec_num                TEXT,
    iden_liga              TEXT,
    cone_liga              TEXT,
    parte_periodo          TEXT,
    bloque                 TEXT,
    calificable            TEXT,
    tipo_asignatura        TEXT,
    restriction_departamento TEXT,
    restriction_programa   TEXT,
    restriction_campus     TEXT,
    restriction_facultad   TEXT,
    atributo_alumno        TEXT,
    totalhoras             TEXT,
    comentario             TEXT,
    texto_largo            TEXT,
    lista_cruzada          TEXT,
    vac_totales            INTEGER,
    vac_presencial         INTEGER,
    vac_semipresencial     INTEGER,
    vac_distancia          INTEGER,
    mat_totales            INTEGER,
    mat_presencial         INTEGER,
    mat_semipresencial     INTEGER,
    mat_distancia          INTEGER,
    disp_totales           INTEGER,
    disp_presencial        INTEGER,
    disp_semipresencial    INTEGER,
    disp_distancia         INTEGER,
    f_inicio               TEXT,
    f_fin                  TEXT,
    hor                    TEXT,
    FOREIGN KEY (id_docente) REFERENCES docente(id_docente)
);

CREATE TABLE docente_seccion (
    id_docente  TEXT NOT NULL REFERENCES docente(id_docente) ON DELETE CASCADE,
    nrc         TEXT NOT NULL REFERENCES seccion(nrc)         ON DELETE CASCADE,
    rol         TEXT NOT NULL,
    orden       INTEGER NOT NULL,
    PRIMARY KEY (id_docente, nrc)
);

CREATE TABLE horario (
    id_horario  INTEGER PRIMARY KEY AUTOINCREMENT,
    nrc         TEXT REFERENCES seccion(nrc) ON DELETE CASCADE,
    tipo_sesion TEXT NOT NULL,
    dia         TEXT,
    hora_inicio TEXT,
    hora_fin    TEXT,
    aula        TEXT
);

CREATE TABLE _meta (
    periodo          TEXT,
    archivo_directorio TEXT,
    archivo_carga    TEXT,
    filas_directorio INTEGER,
    filas_carga      INTEGER,
    fecha_carga      TEXT
);

CREATE INDEX idx_asig_nombre     ON asignatura(nombre);
CREATE INDEX idx_docente_nombre  ON docente(nombre_completo);
CREATE INDEX idx_seccion_plan    ON seccion(plan);
CREATE INDEX idx_seccion_curso   ON seccion(cod_asignatura);
CREATE INDEX idx_seccion_modal   ON seccion(id_modalidad);
CREATE INDEX idx_seccion_docente ON seccion(id_docente);
CREATE INDEX idx_puente_nrc      ON docente_seccion(nrc);
CREATE INDEX idx_horario_nrc     ON horario(nrc);
"""


def norm_id(valor):
    """DNI limpio (solo digitos, sin ceros iniciales). '' si vacio."""
    if not isinstance(valor, str):
        return ""
    return re.sub(r"\D", "", valor).lstrip("0")


def limp_nombre(valor):
    """Nombres sin asteriscos, comas ni espacios repetidos."""
    if not isinstance(valor, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[,*]", " ", valor)).strip()


def separar_apellidos_nombres(completo):
    """Tokens en MAYUSCULAS -> apellidos; resto -> nombres."""
    toks = [t for t in (re.sub(r"[,*]", " ", str(completo)).split()) if t]
    ap = [t for t in toks if t.isupper()]
    no = [t for t in toks if not t.isupper()]
    return " ".join(ap), " ".join(no)


def a_fecha(valor):
    """'17/08/2026' -> '2026-08-17'."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        d, m, a = valor.strip().split("/")
        return f"{int(a):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, IndexError):
        return None


def a_int(valor):
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return None


def s_o_none(valor):
    """Texto o None (trata 'nan', 'none', 'nat' y vacios como NULL)."""
    if valor is None:
        return None
    s = str(valor).strip()
    if s.lower() in ("", "nan", "none", "nat"):
        return None
    return s


def parsear_horario(texto):
    """Campo HOR con 1..n sesiones separadas por |."""
    out = []
    if not isinstance(texto, str) or not texto.strip():
        return out
    for parte in texto.split("|"):
        m = DT_RE.match(parte.strip())
        if not m:
            continue
        tipo, dia, ini, fin, aula = m.groups()
        out.append((tipo, dia if dia in DIAS else None, ini or None,
                    fin or None, aula or None))
    return out


def cargar():
    base = Path(__file__).resolve().parent

    directorio = pd.read_excel(base / DIRECTORIO, dtype=str)
    carga = pd.read_excel(base / CARGA, dtype=str)
    col_dni_doc = "IDDOCENTE" if "IDDOCENTE" in directorio.columns else "IDDOCE"
    col_nombre_doc = "DOCENTE" if "DOCENTE" in directorio.columns else "DOCE"
    carga["NRC"] = carga["NRC"].fillna("").str.strip()

    # ---------------- maestro DOCENTE (Directorio) ----------------
    maestros = {}
    for r in directorio.itertuples(index=False):
        doc_id = norm_id(getattr(r, col_dni_doc))
        if not doc_id:
            continue
        completo = limp_nombre(getattr(r, col_nombre_doc))
        apellidos, nombres = separar_apellidos_nombres(completo)
        maestros[doc_id] = {
            "id_docente": doc_id,
            "apellidos": apellidos,
            "nombres": nombres,
            "nombre_completo": completo,
            "pidm": s_o_none(getattr(r, "PIDM", "")),
            "sede_codigo": s_o_none(getattr(r, "CAMPUS_NRC", "")),
            "telefono_casa": s_o_none(getattr(r, "TELEFONO_CASA", "")),
            "celular": s_o_none(getattr(r, "CELULAR", "")),
            "rpm": s_o_none(getattr(r, "RPM", "")),
            "referencial": s_o_none(getattr(r, "REFERENCIAL", "")),
            "correo_institucional": s_o_none(getattr(r, "CORREO_INSTITUCIONAL", "")),
            "correo_personal": s_o_none(getattr(r, "CORREO_PERSONAL", "")),
            "correo_trabajo": s_o_none(getattr(r, "CORREO_TRABAJO", "")),
            "sexo": s_o_none(getattr(r, "SEXO", "")),
            "ciudadania": s_o_none(getattr(r, "CIUDADANIA", "")),
            "estado_civil": s_o_none(getattr(r, "ESTADO_CIVIL", "")),
            "fecha_nac": s_o_none(getattr(r, "FECHA_NAC", "")),
            "direccion": s_o_none(getattr(r, "DIRECCION", "")),
            "distrito": s_o_none(getattr(r, "DISTRITO", "")),
            "provincia": s_o_none(getattr(r, "PROVINCIA", "")),
            "departamento": s_o_none(getattr(r, "DEPARTAMENTO", "")),
            "fuente": "DIRECTORIO",
        }

    # ---------------- catalogo (Carga Lectiva) ----------------
    conn = sqlite3.connect(base / NOMBRE_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    conn.executescript(
        "DROP TABLE IF EXISTS horario; DROP TABLE IF EXISTS docente_seccion; "
        "DROP TABLE IF EXISTS seccion; DROP TABLE IF EXISTS asignatura; "
        "DROP TABLE IF EXISTS docente; DROP TABLE IF EXISTS modalidad; "
        "DROP TABLE IF EXISTS campus; DROP TABLE IF EXISTS _meta;"
    )
    conn.executescript(ESQUEMA)

    campus_ids, modalidad_ids = {}, {}

    def id_campus(nombre):
        nombre = str(nombre).strip()
        if nombre not in campus_ids:
            cur.execute("INSERT INTO campus (nombre) VALUES (?)", (nombre,))
            campus_ids[nombre] = cur.lastrowid
        return campus_ids[nombre]

    def id_modalidad(nombre):
        nombre = str(nombre).strip()
        if nombre not in modalidad_ids:
            cur.execute("INSERT INTO modalidad (nombre) VALUES (?)", (nombre,))
            modalidad_ids[nombre] = cur.lastrowid
        return modalidad_ids[nombre]

    # maestro docente completo (todo el Directorio)
    COL_DOCENTE = ("id_docente", "apellidos", "nombres", "nombre_completo",
                   "pidm", "sede_codigo", "telefono_casa", "celular", "rpm",
                   "referencial", "correo_institucional", "correo_personal",
                   "correo_trabajo", "sexo", "ciudadania", "estado_civil",
                   "fecha_nac", "direccion", "distrito", "provincia",
                   "departamento", "fuente")
    for doc_id, datos in maestros.items():
        cur.execute(
            f"INSERT INTO docente ({', '.join(COL_DOCENTE)}) VALUES ({', '.join('?'*len(COL_DOCENTE))})",
            tuple(datos[c] for c in COL_DOCENTE),
        )

    basicos = set()  # dnis de CL sin ficha (por si el maestro no los tuviera)

    for i, r in enumerate(carga.itertuples(index=False)):
        nrc = str(r.NRC).strip()
        id_campus(r.CAMPUS)
        id_modalidad(r.MODALIDAD)
        cur.execute(
            "INSERT OR IGNORE INTO asignatura (cod_asignatura, nombre, tipo_curso) "
            "VALUES (?,?,?)",
            (str(r.COD_ASIGNATURA).strip(), r.CURSO, str(r.TIPO_CURSO).strip()),
        )

        # docentes de la seccion (1..3), columnas "DOCENTE 1"/"DNI 1" etc.
        dnis = [norm_id(carga.iat[i, carga.columns.get_loc(c)])
                for c in ("DNI 1", "DNI 2", "DNI 3")]
        responsable = dnis[0] or None

        cur.execute(
            "INSERT INTO seccion (nrc, id_campus, id_modalidad, cod_asignatura, "
            "id_docente, plan, metodo_asistencia, estado, sec_num, iden_liga, "
            "cone_liga, parte_periodo, bloque, calificable, tipo_asignatura, "
            "restriction_departamento, restriction_programa, restriction_campus, "
            "restriction_facultad, atributo_alumno, totalhoras, comentario, "
            "texto_largo, lista_cruzada, "
            "vac_totales, vac_presencial, vac_semipresencial, vac_distancia, "
            "mat_totales, mat_presencial, mat_semipresencial, mat_distancia, "
            "disp_totales, disp_presencial, disp_semipresencial, disp_distancia, "
            "f_inicio, f_fin, hor) "
            "VALUES (%s)" % ", ".join("?" for _ in range(39)),
            (
                nrc, id_campus(r.CAMPUS), id_modalidad(r.MODALIDAD),
                str(r.COD_ASIGNATURA).strip(), responsable,
                str(r.DESCRIPCION_ATRIBUTO_PLAN).strip() or None,
                s_o_none(getattr(r, "METODO_ASISTENCIA", "")),
                str(r.ESTADO_DESCRIPCION).strip(),
                s_o_none(getattr(r, "SECCION", "")),
                s_o_none(getattr(r, "IDEN_LIGA", "")),
                s_o_none(getattr(r, "CONE_LIGA", "")),
                s_o_none(getattr(r, "PARTEPERIODO", "")),
                s_o_none(getattr(r, "BLOQUE", "")),
                s_o_none(getattr(r, "CALIFICABLE", "")),
                s_o_none(getattr(r, "TIPO_ASIGNATURA", "")),
                s_o_none(getattr(r, "RESTRICCION_DEPARTAMENTO", "")),
                s_o_none(getattr(r, "RESTRICCION_PROGRAMA", "")),
                s_o_none(getattr(r, "RESTRICCION_CAMPUS", "")),
                s_o_none(getattr(r, "RESTRICCION_FACULTAD", "")),
                s_o_none(getattr(r, "ATRIBUTO_ALUMNO", "")),
                s_o_none(getattr(r, "TOTALHORAS", "")),
                s_o_none(getattr(r, "COMENTARIO", "")),
                s_o_none(getattr(r, "TEXTO_LARGO", "")),
                s_o_none(getattr(r, "LISTA_CRUZADA", "")),
                a_int(getattr(r, "VACANTES_TOTALES", "")),
                a_int(getattr(r, "VACANTES_PRESENCIAL", "")),
                a_int(getattr(r, "VACANTES_SEMIPRESENCIAL", "")),
                a_int(getattr(r, "VACANTES_DISTANCIA", "")),
                a_int(getattr(r, "MATRICULADOS_TOTALES", "")),
                a_int(getattr(r, "MATRICULADOS_PRESENCIAL", "")),
                a_int(getattr(r, "MATRICULADOS_SEMIPRESENCIAL", "")),
                a_int(getattr(r, "MATRICULADOS_DISTANCIA", "")),
                a_int(getattr(r, "DISPONIBLES_TOTALES", "")),
                a_int(getattr(r, "DISPONIBLES_PRESENCIAL", "")),
                a_int(getattr(r, "DISPONIBLES_SEMIPRESENCIAL", "")),
                a_int(getattr(r, "DISPONIBLES_DISTANCIA", "")),
                a_fecha(getattr(r, "F_INICIO", "")),
                a_fecha(getattr(r, "F_FIN", "")),
                s_o_none(getattr(r, "HOR", "")),
            ),
        )

        for tipo, dia, ini, fin, aula in parsear_horario(r.HOR):
            cur.execute(
                "INSERT INTO horario (nrc, tipo_sesion, dia, hora_inicio, hora_fin, aula) "
                "VALUES (?,?,?,?,?,?)",
                (nrc, tipo, dia, ini, fin, aula),
            )

        # puente docente-seccion (la seccion ya existe)
        for orden, dni in enumerate(dnis, start=1):
            if not dni:
                continue
            if dni not in maestros and dni not in basicos:
                # excepcion: sin ficha -> ficha minima para que la FK no falle
                cur.execute(
                    "INSERT INTO docente (id_docente, nombre_completo, apellidos, "
                    "nombres, fuente) VALUES (?,?,?,?,?)",
                    (dni, dni, "", "", "CARGA LECTIVA"),
                )
                basicos.add(dni)
            cur.execute(
                "INSERT INTO docente_seccion (id_docente, nrc, rol, orden) "
                "VALUES (?,?,?,?)",
                (dni, nrc, "RESPONSABLE" if orden == 1 else "ACOMPANANTE", orden),
            )

    cur.execute(
        "INSERT INTO _meta (periodo, archivo_directorio, archivo_carga, "
        "filas_directorio, filas_carga, fecha_carga) VALUES (?,?,?,?,?,?)",
        (PERIODO, DIRECTORIO, CARGA, len(directorio), len(carga),
         date.today().isoformat()),
    )

    conn.commit()

    totales = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in ("campus", "modalidad", "asignatura", "docente",
                         "seccion", "docente_seccion", "horario")}
    sin_doc = cur.execute(
        "SELECT COUNT(*) FROM seccion WHERE id_docente IS NULL").fetchone()[0]
    conn.close()

    print("Carga completada en", base / NOMBRE_DB)
    for t, c in totales.items():
        print(f"  {t:16} {c:>6}")
    print("  secciones sin docente:", sin_doc)


if __name__ == "__main__":
    cargar()