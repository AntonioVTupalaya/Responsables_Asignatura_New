from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

import sqlite3


BASE = Path(__file__).resolve().parent
NOMBRE_DB = BASE / "docentes.db"

TODAS_MODALIDADES = "Todas las modalidades"
TODOS_PLANES = "Todos los planes"
TODOS_CURSOS = "Todos los cursos"


def obtener_conn():
    return sqlite3.connect(NOMBRE_DB)


@st.cache_data
def obtener_modalidades():
    with obtener_conn() as conn:
        return pd.read_sql(
            "SELECT nombre FROM modalidad ORDER BY nombre",
            conn
        )["nombre"].tolist()


@st.cache_data
def obtener_planes(modalidad):
    with obtener_conn() as conn:
        return pd.read_sql(
            """
            SELECT DISTINCT a.plan AS PLAN
            FROM seccion s
            JOIN modalidad m ON m.id_modalidad = s.id_modalidad
            JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
            WHERE (? = '' OR m.nombre = ?)
            ORDER BY a.plan
            """,
            conn,
            params=(modalidad, modalidad),
        )["PLAN"].tolist()


@st.cache_data
def obtener_cursos(modalidad, plan):
    with obtener_conn() as conn:
        return pd.read_sql(
            """
            SELECT DISTINCT a.nombre AS CURSO
            FROM seccion s
            JOIN modalidad m ON m.id_modalidad = s.id_modalidad
            JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
            WHERE (? = '' OR m.nombre = ?)
              AND (? = '' OR a.plan = ?)
            ORDER BY a.nombre
            """,
            conn,
            params=(modalidad, modalidad, plan, plan),
        )["CURSO"].tolist()


@st.cache_data
def filtrar_docentes(modalidad, plan, curso):
    with obtener_conn() as conn:
        return pd.read_sql(
            """
            SELECT
                c.nombre AS CAMPUS,
                m.nombre AS MODALIDAD,
                a.plan AS PLAN,
                s.nrc AS NRC,
                a.cod_asignatura AS COD_ASIGNATURA,
                a.nombre AS CURSO,
                d.nombre_completo AS DOCENTE
            FROM seccion s
            JOIN campus c     ON c.id_campus     = s.id_campus
            JOIN modalidad m  ON m.id_modalidad  = s.id_modalidad
            JOIN asignatura a ON a.cod_asignatura = s.cod_asignatura
            JOIN docente d    ON d.id_docente    = s.id_docente
            WHERE (? = '' OR m.nombre = ?)
              AND (? = '' OR a.plan = ?)
              AND (? = '' OR a.nombre = ?)
            ORDER BY c.nombre, a.nombre, s.nrc
            """,
            conn,
            params=(modalidad, modalidad, plan, plan, curso, curso),
        )


def callback_reiniciar_plan():
    st.session_state["filtro_plan"] = TODOS_PLANES
    callback_reiniciar_curso()


def callback_reiniciar_curso():
    st.session_state["filtro_curso"] = TODOS_CURSOS


def main():
    # Configuración general de la página
    st.set_page_config(
        page_title="Gestión de Docentes",
        page_icon="📂",
        layout="wide"
    )

    # Títulos
    st.title("📂 Recursos de Gestión del Docente")
    st.subheader(
        "Docentes de Asignaturas Generales Ciencias"
    )

    try:
        # Filtros anidados
        col_mod, col_plan, col_curso = st.columns(3)

        with col_mod:
            st.selectbox(
                "🏫 Modalidad",
                [TODAS_MODALIDADES] + obtener_modalidades(),
                key="filtro_modalidad",
                on_change=callback_reiniciar_plan,
            )

        modalidad = st.session_state["filtro_modalidad"]
        modalidad_sql = "" if modalidad == TODAS_MODALIDADES else modalidad

        with col_plan:
            st.selectbox(
                "📋 Plan",
                [TODOS_PLANES] + obtener_planes(modalidad_sql),
                key="filtro_plan",
                on_change=callback_reiniciar_curso,
            )

        plan = st.session_state["filtro_plan"]
        plan_sql = "" if plan == TODOS_PLANES else plan

        with col_curso:
            st.selectbox(
                "🎓 Curso",
                [TODOS_CURSOS] + obtener_cursos(modalidad_sql, plan_sql),
                key="filtro_curso",
            )

        curso = st.session_state["filtro_curso"]
        curso_sql = "" if curso == TODOS_CURSOS else curso

        # Consulta con filtros aplicados
        df_filtrado = filtrar_docentes(
            modalidad_sql, plan_sql, curso_sql
        )

        st.divider()

        # Encabezado y total
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("👨‍🏫 Lista de Docentes")

        with col2:
            st.metric(
                "Total de registros",
                len(df_filtrado)
            )

        # Columnas que se mostrarán
        columnas_resultado = [
            "CAMPUS",
            "MODALIDAD",
            "PLAN",
            "NRC",
            "COD_ASIGNATURA",
            "CURSO",
            "DOCENTE"
        ]

        # Preparar descarga
        csv = df_filtrado[columnas_resultado].to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Descargar lista filtrada (CSV)",
            data=csv,
            file_name="Docentes_filtrado.csv",
            mime="text/csv"
        )

        # Mostrar tabla
        st.dataframe(
            df_filtrado[columnas_resultado],
            width="stretch",
            hide_index=True
        )

    except sqlite3.OperationalError as error:
        st.error(
            f"No se pudo leer la base de datos. "
            f"Ejecute primero 'python cargar_db.py'. Detalle: {error}"
        )

    except pd.errors.DatabaseError as error:
        st.error(
            f"Error de consulta a la base de datos: {error}"
        )

    except Exception as error:
        st.error(
            f"Error inesperado: {error}"
        )


if __name__ == "__main__":
    import subprocess
    import sys

    # Si se ejecuta con `python app.py`, relanzar con Streamlit.
    if get_script_run_ctx() is None:
        # Evita el prompt de bienvenida de la primera ejecución de Streamlit.
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