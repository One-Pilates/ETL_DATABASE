"""Copia gold.estudos e gold.referencias para o MySQL da IA do professor."""

from __future__ import annotations

import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pymysql

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
SCHEMA_PATH = ROOT / "sql" / "schema_mysql.sql"
ENV_VARS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
)
GROUPS = ("pilates", "fisioterapia", "mobilidade", "forca")
EXAMPLE_CALL = (
    "dor lombar",
    "pilates,fisioterapia,mobilidade,forca",
    45,
    5,
)


def require_env() -> dict[str, str]:
    missing = [name for name in ENV_VARS if not os.environ.get(name)]
    if missing:
        print(
            f"Falta variável de ambiente: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    port = os.environ["MYSQL_PORT"]
    if not port.isdigit():
        print("MYSQL_PORT precisa ser um número.", file=sys.stderr)
        sys.exit(1)
    return {
        "host": os.environ["MYSQL_HOST"],
        "port": port,
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
    }


def comment_only(statement: str) -> bool:
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return False
    return True


def sql_statements(script: str) -> list[str]:
    delimiter = ";"
    pending: list[str] = []
    statements: list[str] = []

    def flush() -> None:
        statement = "\n".join(pending).strip()
        pending.clear()
        if statement.endswith(delimiter):
            statement = statement[: -len(delimiter)].strip()
        if statement and not comment_only(statement):
            statements.append(statement)

    for line in script.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            if any(part.strip() for part in pending):
                flush()
            else:
                pending.clear()
            delimiter = stripped.split(None, 1)[1]
            continue
        pending.append(line)
        if "\n".join(pending).rstrip().endswith(delimiter):
            flush()
    if any(part.strip() for part in pending):
        flush()
    return statements


def fold(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.lower().split())


def clip(value, size: int):
    value = plain(value)
    if isinstance(value, str) and len(value) > size:
        return value[:size]
    return value


def plain(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, bool):
        return int(value)
    return value


def texto_busca(title: str | None, official: str | None, parts: list[str]) -> str:
    pieces: list[str] = []
    seen: set[str] = set()
    for raw in (title, official, *parts):
        token = fold(raw)
        if token and token not in seen:
            seen.add(token)
            pieces.append(token)
    return " ".join(pieces)[:65000]


def apply_schema(cur: pymysql.cursors.Cursor) -> None:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    for statement in sql_statements(script):
        cur.execute(statement)


def insert_rows(
    cur: pymysql.cursors.Cursor,
    sql: str,
    rows: list[tuple],
    size: int,
) -> None:
    for start in range(0, len(rows), size):
        cur.executemany(sql, rows[start : start + size])


def load_gold(duck: duckdb.DuckDBPyConnection) -> dict[str, list[tuple]]:
    estudos = duck.execute(
        """
        SELECT
            nct_id,
            brief_title,
            official_title,
            brief_summary,
            study_type,
            phase,
            overall_status,
            start_date,
            completion_date,
            primary_completion_date,
            enrollment,
            minimum_age_years,
            maximum_age_years,
            gender,
            were_results_reported,
            url,
            CAST(_gold_at AS TIMESTAMP) AS gold_at
        FROM gold.estudos
        ORDER BY nct_id
        """
    ).fetchall()
    grupos = duck.execute(
        """
        SELECT nct_id, unnest AS grupo
        FROM gold.estudos, unnest(termos_encontrados)
        WHERE unnest IS NOT NULL
        """
    ).fetchall()
    condicoes = duck.execute(
        """
        SELECT nct_id, unnest.name, unnest.name_normalized
        FROM gold.estudos, unnest(conditions)
        WHERE unnest.name IS NOT NULL OR unnest.name_normalized IS NOT NULL
        """
    ).fetchall()
    intervencoes = duck.execute(
        """
        SELECT nct_id, unnest.intervention_type, unnest.name, unnest.description
        FROM gold.estudos, unnest(interventions)
        WHERE unnest.name IS NOT NULL
           OR unnest.description IS NOT NULL
           OR unnest.intervention_type IS NOT NULL
        """
    ).fetchall()
    mesh = duck.execute(
        """
        SELECT nct_id, unnest.mesh_term, unnest.mesh_type, unnest.mesh_term_normalized
        FROM gold.estudos, unnest(mesh_terms)
        WHERE unnest.mesh_term IS NOT NULL OR unnest.mesh_term_normalized IS NOT NULL
        """
    ).fetchall()
    referencias = duck.execute(
        """
        SELECT
            nct_id,
            pmid,
            reference_type,
            citation,
            titulo,
            periodico,
            ano,
            resumo,
            busca_status
        FROM gold.referencias
        """
    ).fetchall()
    termos: dict[str, list[str]] = {}

    def add_termo(nct_id: str, value: str | None) -> None:
        if value:
            termos.setdefault(nct_id, []).append(value)

    for nct_id, nome, normalizado in condicoes:
        add_termo(nct_id, nome)
        add_termo(nct_id, normalizado)
    for nct_id, termo, _tipo, normalizado in mesh:
        add_termo(nct_id, termo)
        add_termo(nct_id, normalizado)
    for nct_id, _tipo, nome, _descricao in intervencoes:
        add_termo(nct_id, nome)
    estudo_rows = []
    for row in estudos:
        nct_id, title, official = row[0], row[1], row[2]
        limits = {0: 20, 4: 64, 5: 64, 6: 32, 13: 32, 15: 255}
        values = [
            clip(value, limits[index]) if index in limits else plain(value)
            for index, value in enumerate(row)
        ]
        values.append(texto_busca(title, official, termos.get(nct_id, [])))
        estudo_rows.append(tuple(values))
    grupo_rows = []
    seen_grupos: set[tuple[str, str]] = set()
    for nct_id, grupo in grupos:
        key = (nct_id, grupo)
        if key not in seen_grupos:
            seen_grupos.add(key)
            grupo_rows.append(key)
    return {
        "estudo": estudo_rows,
        "grupo": grupo_rows,
        "condicao": [
            (row[0], plain(row[1]), clip(row[2], 512)) for row in condicoes
        ],
        "intervencao": [
            (row[0], clip(row[1], 64), plain(row[2]), plain(row[3]))
            for row in intervencoes
        ],
        "mesh": [
            (row[0], plain(row[1]), clip(row[2], 64), clip(row[3], 512))
            for row in mesh
        ],
        "referencia": [
            (
                row[0],
                clip(row[1], 32),
                clip(row[2], 32),
                plain(row[3]),
                plain(row[4]),
                clip(row[5], 512),
                plain(row[6]),
                plain(row[7]),
                clip(row[8], 32),
            )
            for row in referencias
        ],
    }


def validate(
    cur: pymysql.cursors.Cursor,
    expected_total: int,
    expected_groups: dict[str, int],
) -> None:
    cur.execute("SELECT COUNT(*) FROM estudo")
    total = cur.fetchone()[0]
    cur.execute(
        """
        SELECT grupo, COUNT(*)
        FROM estudo_grupo
        GROUP BY grupo
        ORDER BY grupo
        """
    )
    found = {grupo: total_grupo for grupo, total_grupo in cur.fetchall()}
    cur.execute(
        """
        SELECT COUNT(*)
        FROM estudo
        WHERE overall_status IS NULL OR overall_status <> 'COMPLETED'
        """
    )
    not_completed = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*)
        FROM estudo AS e
        WHERE NOT EXISTS (
            SELECT 1 FROM estudo_grupo AS g WHERE g.nct_id = e.nct_id
        )
        """
    )
    without_group = cur.fetchone()[0]
    print(f"estudo: {total}")
    for grupo in GROUPS:
        print(f"{grupo}: {found.get(grupo, 0)}")
    mismatches = []
    if total != expected_total:
        mismatches.append(f"estudo {total} em vez de {expected_total}")
    if not_completed:
        mismatches.append(f"{not_completed} estudos fora de COMPLETED")
    if without_group:
        mismatches.append(f"{without_group} estudos sem um dos quatro grupos")
    for grupo in GROUPS:
        actual = found.get(grupo, 0)
        expected = expected_groups.get(grupo, 0)
        if actual != expected:
            mismatches.append(f"{grupo} {actual} em vez de {expected}")
    extra = sorted(set(found) - set(GROUPS))
    if extra:
        mismatches.append("grupos fora da gold: " + ", ".join(extra))
    if mismatches:
        print("Falha na carga: " + "; ".join(mismatches), file=sys.stderr)
        sys.exit(1)
    cur.execute(
        "CALL buscar_estudos_para_aula(%s, %s, %s, %s)",
        EXAMPLE_CALL,
    )
    rows = cur.fetchall()
    columns = [item[0] for item in (cur.description or [])]
    while cur.nextset():
        extra = cur.fetchall()
        if extra:
            rows = extra
            columns = [item[0] for item in cur.description or []]
    print(
        "buscar_estudos_para_aula"
        f"({EXAMPLE_CALL[0]!r}, {EXAMPLE_CALL[1]!r}, {EXAMPLE_CALL[2]}, {EXAMPLE_CALL[3]})"
        f": {len(rows)} fichas"
    )
    for row in rows:
        card = dict(zip(columns, row))
        resumo = card.get("resumo") or ""
        resumo = " ".join(str(resumo).split())
        if len(resumo) > 180:
            resumo = resumo[:180] + "..."
        print(f"{card.get('titulo')} | {card.get('link')} | {resumo}")


def main() -> None:
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(SCHEMA_PATH)
    settings = require_env()
    print("lendo gold...", flush=True)
    duck = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = load_gold(duck)
    finally:
        duck.close()
    print(
        f"gold lida: {len(tables['estudo'])} estudos, "
        f"{len(tables['referencia'])} referencias",
        flush=True,
    )
    try:
        mysql = pymysql.connect(
            host=settings["host"],
            port=int(settings["port"]),
            user=settings["user"],
            password=settings["password"],
            database=settings["database"],
            charset="utf8mb4",
            autocommit=False,
        )
    except pymysql.err.OperationalError as exc:
        if exc.args and exc.args[0] == 1049:
            print(
                f"Crie o banco {settings['database']} no MySQL antes de rodar a carga.",
                file=sys.stderr,
            )
            sys.exit(1)
        raise
    try:
        with mysql.cursor() as cur:
            print("aplicando schema...", flush=True)
            apply_schema(cur)
            print("gravando estudo...", flush=True)
            insert_rows(
                cur,
                """
                INSERT INTO estudo (
                    nct_id, brief_title, official_title, brief_summary, study_type,
                    phase, overall_status, start_date, completion_date,
                    primary_completion_date, enrollment, minimum_age_years,
                    maximum_age_years, gender, were_results_reported, url,
                    gold_at, texto_busca
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                tables["estudo"],
                500,
            )
            print("gravando grupos, condições, intervenções e MeSH...", flush=True)
            insert_rows(
                cur,
                "INSERT INTO estudo_grupo (nct_id, grupo) VALUES (%s, %s)",
                tables["grupo"],
                1000,
            )
            insert_rows(
                cur,
                """
                INSERT INTO estudo_condicao (nct_id, nome, nome_normalizado)
                VALUES (%s, %s, %s)
                """,
                tables["condicao"],
                1000,
            )
            insert_rows(
                cur,
                """
                INSERT INTO estudo_intervencao (nct_id, tipo, nome, descricao)
                VALUES (%s, %s, %s, %s)
                """,
                tables["intervencao"],
                500,
            )
            insert_rows(
                cur,
                """
                INSERT INTO estudo_mesh (nct_id, termo, tipo, termo_normalizado)
                VALUES (%s, %s, %s, %s)
                """,
                tables["mesh"],
                1000,
            )
            print("gravando referencias...", flush=True)
            insert_rows(
                cur,
                """
                INSERT INTO referencia (
                    nct_id, pmid, reference_type, citation, titulo, periodico,
                    ano, resumo, busca_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                tables["referencia"],
                200,
            )
            mysql.commit()
            print("conferindo carga...", flush=True)
            expected_groups = {grupo: 0 for grupo in GROUPS}
            for _nct_id, grupo in tables["grupo"]:
                expected_groups[grupo] = expected_groups.get(grupo, 0) + 1
            validate(cur, len(tables["estudo"]), expected_groups)
            mysql.commit()
    finally:
        mysql.close()
    print(f"banco mysql: {settings['database']} em {settings['host']}")


if __name__ == "__main__":
    main()
