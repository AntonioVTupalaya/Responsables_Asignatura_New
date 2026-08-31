from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

import sqlite3

# ---------------------------------------------------------------- config
BASE = Path(__file__).resolve().parent
NOMBRE_DB = BASE / "docentes.db"
LOGO = BASE / "logo_uc.png"

# Paleta PRISM (Universidad Continental)
PRINCIPAL = "#6802C1"
FRANJA = "#9632FA"
PROFUNDO = "#28075A"
TITULO = "#00143D"
LILA_DEC = "#CAA0F5"
LAVANDA = "#E0AAFF"
FONDO_SUAVE = "#F7F4FF"
BLANCO = "#FFFFFF"
GRIS_TEXTO = "#4A4A4A"

TODO_MOD = "Todas las modalidades"
TODO_BLOQ = "Todos los bloques"
TODO_PLAN = "Todos los planes"
TODO_CURSO = "Todos los cursos"
SIN_BLOQUE = "SIN BLOQUE"

# ---------------------------------------------------------------- datos

def obtener_conn():
    return sqlite3.connect(NOMBRE_DB)


@st.cache_data
def obtener_modalidades():
    with obtener_conn() as conn:
        return pd.read_sql(
            "SELECT nombre FROM modalidad ORDER BY nombre", conn
        )["nombre"].tolist()


@st.cache_data
def obtener_bloques(modalidad):
    with obtener_conn() as conn:
        df = pd.read_sql(
            """
            SELECT s.bloque AS BLOQUE
            FROM seccion s
            JOIN modalidad m ON m.id_modalidad = s.id_modalidad
            WHERE (? = '' OR m.nombre = ?)
            """,
            conn,
            params=(modalidad, modalidad),
        )
        bloques = sorted(x for x in df["BLOQUE"].dropna().unique())
        if df["BLOQUE"].isna().any():
            bloques.append(SIN_BLOQUE)
        return bloques


@st.cache_data
def obtener_planes(modalidad, bloque):
    cond_bloque, param_bloque = _filtro_bloque(bloque)
    sql = f"""
        SELECT DISTINCT s.plan AS PLAN
        FROM seccion s
        JOIN modalidad m ON m.id_modalidad = s.id_modalidad
        WHERE (? = '' OR m.nombre = ?)
          {cond_bloque}
        ORDER BY s.plan
    """
    with obtener_conn() as conn:
        df = pd.read_sql(sql, conn,
                         params=(modalidad, modalidad) + param_bloque)
    return [p for p in df["PLAN"].dropna().tolist() if p != ""]


@st.cache_data
def obtener_cursos(modalidad, bloque, plan):
    cond_bloque, param_bloque = _filtro_bloque(bloque)
    sql = f"""
        SELECT DISTINCT a.nombre AS CURSO
        FROM seccion s
        JOIN modalidad m ON m.id_modalidad = s.id_modalidad
        JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
        WHERE (? = '' OR m.nombre = ?)
          AND (? = '' OR s.plan = ?)
          {cond_bloque}
        ORDER BY a.nombre
    """
    with obtener_conn() as conn:
        return pd.read_sql(sql, conn, params=(modalidad, modalidad, plan, plan)
                           + param_bloque)["CURSO"].tolist()


def _filtro_bloque(bloque):
    """Devuelve (condicion_sql, parametro)."""
    if not bloque or bloque == TODO_BLOQ:
        return "", ()
    if bloque == SIN_BLOQUE:
        return "AND s.bloque IS NULL", ()
    return "AND s.bloque = ?", (bloque,)


@st.cache_data
def lista_carga_lectiva(modalidad, bloque, plan, curso):
    cond_bloque, param_bloque = _filtro_bloque(bloque)
    sql = f"""
        SELECT
            c.nombre AS CAMPUS,
            m.nombre AS MODALIDAD,
            s.plan   AS PLAN,
            a.cod_asignatura AS COD_ASIGNATURA,
            a.nombre AS CURSO,
            s.nrc    AS NRC,
            s.mat_totales AS MATRICULADOS,
            COALESCE((
                SELECT GROUP_CONCAT(d2.nombre_completo, ' - ')
                FROM docente_seccion ds
                JOIN docente d2 ON d2.id_docente = ds.id_docente
                WHERE ds.nrc = s.nrc
            ), 'SIN ASIGNAR') AS DOCENTE,
            s.hor AS HORARIO
        FROM seccion s
        LEFT JOIN campus c     ON c.id_campus     = s.id_campus
        LEFT JOIN modalidad m  ON m.id_modalidad  = s.id_modalidad
        LEFT JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
        WHERE (? = '' OR m.nombre = ?)
          AND (? = '' OR s.plan = ?)
          AND (? = '' OR a.nombre = ?)
          {cond_bloque}
        ORDER BY c.nombre, a.nombre, s.nrc
    """
    with obtener_conn() as conn:
        return pd.read_sql(
            sql,
            conn,
            params=(modalidad, modalidad, plan, plan, curso, curso) + param_bloque,
        )


@st.cache_data
def lista_directorio(_modalidad, _bloque, _plan, _curso):
    return _directorio(_modalidad, _bloque, _plan, _curso)


# --------------------------------------------------------------- UI / CSS
CSS = f"""
<style>
.stApp {{ background-color: {FONDO_SUAVE}; }}

.hero {{
  background: linear-gradient(120deg, {PROFUNDO} 0%, {PRINCIPAL} 55%, {FRANJA} 100%);
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 24px;
  box-shadow: 0 6px 18px rgba(40,7,90,.35);
}}
.hero img {{ height: 64px; }}
.hero h1 {{
  color: {BLANCO};
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: .5px;
}}
.hero .sub {{
  color: {LAVANDA};
  font-size: 14px;
  font-weight: 600;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
}}
.hero .sr {{
  color: {BLANCO};
  font-size: 17px;
  font-weight: 700;
  margin-top: 6px;
}}
.sec-h {{
  color: {TITULO};
  font-weight: 800;
  font-size: 18px;
  border-left: 6px solid {PRINCIPAL};
  padding-left: 12px;
  margin: 8px 0 14px 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}}
.tarjeta {{
  background: {BLANCO};
  border-left: 6px solid {PRINCIPAL};
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(40,7,90,.10);
}}
.tarjeta .t {{ color: {GRIS_TEXTO}; font-size: 12px; letter-spacing: 1px; }}
.tarjeta .v {{ color: {TITULO}; font-size: 26px; font-weight: 800; margin-top: 2px; }}
.stDownloadButton button {{
  background-color: {PRINCIPAL};
  color: {BLANCO};
  border: 1px solid {PRINCIPAL};
  border-radius: 8px;
}}
.stDownloadButton button:hover {{
  background-color: {PROFUNDO};
  color: {BLANCO};
  border-color: {PROFUNDO};
}}
.footer {{
  background: {PROFUNDO};
  color: {BLANCO};
  border-radius: 12px;
  padding: 14px 20px;
  margin-top: 26px;
  text-align: center;
  font-size: 13px;
}}
.footer b {{ color: {LAVANDA}; }}
[data-testid="stSidebar"] {{ display: none; }}
</style>
"""


def encabezado():
    b64 = ""
    if LOGO.exists():
        b64 = (
            "data:image/png;base64,"
            + __import__("base64").b64encode(LOGO.read_bytes()).decode()
        )
    st.markdown(CSS, unsafe_allow_html=True)
    img = f'<img src="{b64}" alt="Logo UC"/>' if b64 else ""
    st.markdown(
        f"""
        <div class="hero">
          {img}
          <div>
            <div class="sub">Dirección de Estudios Generales de Ciencias</div>
            <h1>RESPONSABLES DE ASIGNATURA</h1>
            <div class="sr">Docentes por Asignatura · Directorio</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tarjeta_metrica(titulo, valor, lado=PRINCIPAL):
    st.markdown(
        f"""
        <div class="tarjeta" style="border-left-color:{lado};">
          <div class="t">{titulo}</div>
          <div class="v">{valor}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------- callbacks
def cb_reset_bloque():
    st.session_state["f_bloque"] = TODO_BLOQ
    cb_reset_plan()


def cb_reset_plan():
    st.session_state["f_plan"] = TODO_PLAN
    cb_reset_curso()


def cb_reset_curso():
    st.session_state["f_curso"] = TODO_CURSO


def main():
    st.set_page_config(
        page_title="Relación Docentes por Curso",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    encabezado()

    try:
        modalidades = obtener_modalidades()

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.selectbox(
                "MODALIDAD",
                [TODO_MOD] + modalidades,
                key="f_modalidad",
                on_change=cb_reset_bloque,
            )
        modalidad = st.session_state["f_modalidad"]
        modalidad_sql = "" if modalidad == TODO_MOD else modalidad

        # BLOQUE solo se habilita cuando la modalidad es semipresencial
        # (UC-PRESENCIAL no usa bloques).
        bloque_habilitado = modalidad == "UC-SEMIPRESENCIAL"

        with c2:
            st.selectbox(
                "BLOQUE",
                [TODO_BLOQ] + obtener_bloques(modalidad_sql),
                key="f_bloque",
                on_change=cb_reset_plan,
                disabled=not bloque_habilitado,
            )
        bloque = st.session_state["f_bloque"]
        bloque_sql = (
            bloque if (bloque_habilitado and bloque != TODO_BLOQ) else ""
        )

        with c3:
            st.selectbox(
                "PLAN DE ESTUDIOS",
                [TODO_PLAN] + obtener_planes(modalidad_sql, bloque_sql),
                key="f_plan",
                on_change=cb_reset_curso,
            )
        plan = st.session_state["f_plan"]
        plan_sql = "" if plan == TODO_PLAN else plan

        with c4:
            st.selectbox(
                "CURSO",
                [TODO_CURSO] + obtener_cursos(modalidad_sql, bloque_sql, plan_sql),
                key="f_curso",
            )
        curso = st.session_state["f_curso"]
        curso_sql = "" if curso == TODO_CURSO else curso

        df = lista_carga_lectiva(modalidad_sql, bloque_sql, plan_sql, curso_sql)
        df_dir = _directorio(modalidad_sql, bloque_sql, plan_sql, curso_sql)

        # ---------------------------------------------------- metricas
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        with c_m1:
            tarjeta_metrica("NRC", len(df), PRINCIPAL)
        with c_m2:
            tarjeta_metrica("DOCENTES", len(df_dir), FRANJA)
        with c_m3:
            tarjeta_metrica("CURSOS", df["CURSO"].nunique(), LILA_DEC)
        with c_m4:
            tarjeta_metrica("CAMPUS", df["CAMPUS"].nunique(), GRIS_TEXTO)

        st.divider()

        # ------------------------------------------- lista Carga Lectiva
        st.markdown('<div class="sec-h">Carga Lectiva 202620</div>',
                    unsafe_allow_html=True)
        cols_lista = [
            "CAMPUS", "MODALIDAD", "PLAN",
            "COD_ASIGNATURA", "CURSO", "NRC", "MATRICULADOS",
            "DOCENTE", "HORARIO",
        ]
        st.download_button(
            "📥 Descargar lista (CSV)",
            df[cols_lista].to_csv(index=False).encode("utf-8-sig"),
            file_name="Carga_lectiva_filtrado.csv",
            mime="text/csv",
        )
        st.dataframe(df[cols_lista], width="stretch", hide_index=True)

        st.divider()

        # --------------------------------------------------- DIRECTORIO
        st.markdown('<div class="sec-h">Directorio Docentes 2026-20</div>',
                    unsafe_allow_html=True)
        cols_dir = ["DOCENTE", "IDDOCENTE", "CORREO_INSTITUCIONAL", "CELULAR"]
        st.download_button(
            "📥 Descargar directorio (CSV)",
            df_dir[cols_dir].to_csv(index=False).encode("utf-8-sig"),
            file_name="Directorio_filtrado.csv",
            mime="text/csv",
        )
        st.dataframe(df_dir[cols_dir], width="stretch", hide_index=True)

        st.markdown(
            f'<div class="footer">Universidad Continental · '
            f'<b>Dirección de Estudios Generales de Ciencias</b> · '
            f'Periodo <b>2026-20</b> · @Quispe</div>',
            unsafe_allow_html=True,
        )

    except sqlite3.OperationalError as error:
        st.error(
            f"No se pudo leer la base de datos. "
            f"Ejecute primero 'python cargar_db.py'. Detalle: {error}"
        )
    except pd.errors.DatabaseError as error:
        st.error(f"Error de consulta a la base de datos: {error}")
    except Exception as error:
        st.error(f"Error inesperado: {error}")


@st.cache_data
def _directorio(modalidad, bloque, plan, curso):
    cond_bloque, param_bloque = _filtro_bloque(bloque)
    sql = f"""
        SELECT DISTINCT
            d.nombre_completo AS DOCENTE,
            d.id_docente AS IDDOCENTE,
            d.correo_institucional AS CORREO_INSTITUCIONAL,
            d.celular AS CELULAR
        FROM seccion s
        JOIN modalidad m ON m.id_modalidad = s.id_modalidad
        JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
        JOIN docente_seccion ds ON ds.nrc = s.nrc
        JOIN docente d ON d.id_docente = ds.id_docente
        WHERE (? = '' OR m.nombre = ?)
          AND (? = '' OR s.plan = ?)
          AND (? = '' OR a.nombre = ?)
          {cond_bloque}
        ORDER BY d.nombre_completo
    """
    with obtener_conn() as conn:
        return pd.read_sql(
            sql,
            conn,
            params=(modalidad, modalidad, plan, plan, curso, curso) + param_bloque,
        )


if __name__ == "__main__":
    import subprocess
    import sys

    if get_script_run_ctx() is None:
        dir_credenciales = Path.home() / ".streamlit"
        archivo_credenciales = dir_credenciales / "credentials.toml"
        if not archivo_credenciales.exists():
            dir_credenciales.mkdir(parents=True, exist_ok=True)
            archivo_credenciales.write_text(
                '[general]\nemail = ""\n',
                encoding="utf-8",
            )
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", __file__],
            check=True,
        )
    else:
        main()