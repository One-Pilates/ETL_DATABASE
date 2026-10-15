"""Carrega as tabelas centrais do ClinicalTrials.gov em raw.estudos."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "base_dados"
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
TEMP_DIR = ROOT / "data" / "tmp"

CSV_OPTIONS = "delim='|', header=true, quote='\"', all_varchar=true, max_line_size=50000000"


def source_path(name: str) -> Path:
    path = SOURCE_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def read_csv(name: str) -> str:
    path = source_path(name).as_posix().replace("'", "''")
    return f"read_csv('{path}', {CSV_OPTIONS})"


def connect() -> duckdb.DuckDBPyConnection:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for path in (DB_PATH, Path(str(DB_PATH) + ".wal")):
        if path.exists():
            path.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=2")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    return con


def attach(
    con: duckdb.DuckDBPyConnection,
    stage_sql: str,
    *,
    unique_nct: str | None = None,
) -> None:
    con.execute(f"CREATE OR REPLACE TABLE raw._stage AS {stage_sql}")
    if unique_nct is not None:
        rows, distinct = con.execute(
            "SELECT count(*), count(DISTINCT nct_id) FROM raw._stage"
        ).fetchone()
        if rows != distinct:
            raise SystemExit(
                f"{unique_nct} tem nct_id duplicado ({rows} linhas, {distinct} distintos)."
            )
    con.execute("ALTER TABLE raw.estudos RENAME TO _estudos_prev")
    con.execute(
        """
        CREATE TABLE raw.estudos AS
        SELECT prev.*, stage.* EXCLUDE (nct_id)
        FROM raw._estudos_prev AS prev
        LEFT JOIN raw._stage AS stage USING (nct_id)
        """
    )
    con.execute("DROP TABLE raw._estudos_prev")
    con.execute("DROP TABLE raw._stage")


def compact_database() -> None:
    compact_path = DB_PATH.with_name("clinical_trials.compact.duckdb")
    for path in (compact_path, Path(str(compact_path) + ".wal")):
        if path.exists():
            path.unlink()
    source = DB_PATH.as_posix().replace("'", "''")
    target = compact_path.as_posix().replace("'", "''")
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{source}' AS src (READ_ONLY)")
        con.execute(f"ATTACH '{target}' AS dst")
        con.execute("COPY FROM DATABASE src TO dst")
    finally:
        con.close()
    DB_PATH.unlink()
    wal = Path(str(DB_PATH) + ".wal")
    if wal.exists():
        wal.unlink()
    compact_path.replace(DB_PATH)


def main() -> None:
    for name in (
        "studies",
        "calculated_values",
        "designs",
        "eligibilities",
        "brief_summaries",
        "conditions",
        "interventions",
        "sponsors",
        "countries",
        "browse_conditions",
    ):
        source_path(name)

    con = connect()
    try:
        print("carregando studies...", flush=True)
        con.execute(
            f"""
            CREATE TABLE raw.estudos AS
            SELECT * FROM {read_csv("studies")}
            """
        )
        expected, distinct_studies = con.execute(
            "SELECT count(*), count(DISTINCT nct_id) FROM raw.estudos"
        ).fetchone()
        if expected != distinct_studies:
            raise SystemExit(
                "studies.txt tem nct_id duplicado "
                f"({expected} linhas, {distinct_studies} distintos)."
            )

        one_to_one = {
            "calculated_values": f"SELECT * EXCLUDE (id) FROM {read_csv('calculated_values')}",
            "designs": f"SELECT * EXCLUDE (id) FROM {read_csv('designs')}",
            "eligibilities": f"SELECT * EXCLUDE (id) FROM {read_csv('eligibilities')}",
            "brief_summaries": (
                "SELECT nct_id, description AS brief_summary "
                f"FROM {read_csv('brief_summaries')}"
            ),
        }
        for name, sql in one_to_one.items():
            print(f"juntando {name}...", flush=True)
            attach(con, sql, unique_nct=name)

        lists = {
            "conditions": f"""
                SELECT
                    nct_id,
                    list(struct_pack(name := name) ORDER BY id::BIGINT) AS conditions
                FROM {read_csv("conditions")}
                GROUP BY nct_id
            """,
            "interventions": f"""
                SELECT
                    nct_id,
                    list(
                        struct_pack(
                            intervention_type := intervention_type,
                            name := name,
                            description := description
                        )
                        ORDER BY id::BIGINT
                    ) AS interventions
                FROM {read_csv("interventions")}
                GROUP BY nct_id
            """,
            "sponsors": f"""
                SELECT
                    nct_id,
                    list(
                        struct_pack(
                            agency_class := agency_class,
                            lead_or_collaborator := lead_or_collaborator,
                            name := name
                        )
                        ORDER BY id::BIGINT
                    ) AS sponsors
                FROM {read_csv("sponsors")}
                GROUP BY nct_id
            """,
            "countries": f"""
                SELECT
                    nct_id,
                    list(
                        struct_pack(name := name, removed := removed)
                        ORDER BY id::BIGINT
                    ) AS countries
                FROM {read_csv("countries")}
                GROUP BY nct_id
            """,
            "browse_conditions": f"""
                SELECT
                    nct_id,
                    list(
                        struct_pack(mesh_term := mesh_term, mesh_type := mesh_type)
                        ORDER BY id::BIGINT
                    ) AS mesh_terms
                FROM {read_csv("browse_conditions")}
                GROUP BY nct_id
            """,
        }
        for name, sql in lists.items():
            print(f"agregando {name}...", flush=True)
            attach(con, sql)

        print("gravando _ingested_at...", flush=True)
        con.execute("ALTER TABLE raw.estudos RENAME TO _estudos_prev")
        con.execute(
            """
            CREATE TABLE raw.estudos AS
            SELECT *, current_timestamp AS _ingested_at
            FROM raw._estudos_prev
            """
        )
        con.execute("DROP TABLE raw._estudos_prev")

        loaded, distinct = con.execute(
            "SELECT count(*), count(DISTINCT nct_id) FROM raw.estudos"
        ).fetchone()
    finally:
        con.close()

    print(f"studies.txt: {expected}")
    print(f"raw.estudos: {loaded}")
    print(f"nct_id distintos: {distinct}")
    print(f"banco: {DB_PATH}")

    if loaded != expected or distinct != expected:
        print(
            "Falha: raw.estudos não tem uma linha por estudo de studies.txt.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("compactando banco...", flush=True)
    compact_database()

    file_lines = sum(1 for _ in source_path("studies").open("rb")) - 1
    print(f"linhas físicas de studies.txt (sem cabeçalho): {file_lines}")
    if file_lines != expected:
        print(
            "Aviso: o arquivo tem quebras de linha dentro de campos; "
            "a validação usou a contagem de registros."
        )


if __name__ == "__main__":
    main()
