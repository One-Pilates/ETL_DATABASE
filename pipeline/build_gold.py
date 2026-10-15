"""Cria gold.estudos e gold.referencias a partir da silver."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
TEMP_DIR = ROOT / "data" / "tmp"
REFERENCES_PATH = ROOT / "base_dados" / "study_references.txt"

GROUPS = {
    "mobilidade": (
        "mobility",
        "mobilidade",
        "mobilization",
        "mobilisation",
        "mobilização",
        "range of motion",
        "amplitude de movimento",
        "stretching",
        "alongamento",
        "flexibility",
        "flexibilidade",
        "exercise therapy",
        "therapeutic exercise",
        "exercício terapêutico",
        "exercicio terapeutico",
    ),
    "forca": (
        "strength",
        "resistance training",
        "weight training",
        "weightlifting",
        "fortalecimento",
        "treino de força",
    ),
    "fisioterapia": ("physiotherap", "physical therapy", "fisioterapia"),
    "pilates": ("pilates",),
}


def predicate(terms: tuple[str, ...]) -> str:
    clauses = []
    for term in terms:
        safe = term.lower().replace("'", "''")
        clauses.append(f"strpos(texto, '{safe}') > 0")
    return " OR ".join(clauses)


def flags_sql() -> str:
    columns = ",\n            ".join(
        f"max(CASE WHEN {predicate(terms)} THEN 1 ELSE 0 END) AS {name}"
        for name, terms in GROUPS.items()
    )
    return f"""
    SELECT
        nct_id,
        {columns}
    FROM (
        SELECT
            nct_id,
            lower(
                coalesce(unnest.name, '') || ' ' || coalesce(unnest.description, '')
            ) AS texto
        FROM silver.estudos
        , unnest(interventions)
        WHERE overall_status = 'COMPLETED'
    )
    GROUP BY nct_id
    """


def termos_sql() -> str:
    parts = ",\n            ".join(
        f"CASE WHEN f.{name} = 1 THEN ['{name}'] ELSE [] END" for name in GROUPS
    )
    return f"list_concat({parts})"


def any_group_sql() -> str:
    return " OR ".join(f"f.{name} = 1" for name in GROUPS)


def build_estudos_sql() -> str:
    return f"""
    CREATE OR REPLACE TABLE gold.estudos AS
    WITH flags AS (
        {flags_sql()}
    )
    SELECT
        s.nct_id,
        s.brief_title,
        s.official_title,
        s.brief_summary,
        s.study_type,
        s.phase,
        s.phases,
        s.overall_status,
        s.start_date,
        s.completion_date,
        s.primary_completion_date,
        s.enrollment,
        s.minimum_age_years,
        s.maximum_age_years,
        s.gender,
        s.conditions,
        s.interventions,
        s.mesh_terms,
        s.countries_current,
        s.lead_sponsors,
        s.were_results_reported,
        {termos_sql()} AS termos_encontrados,
        'https://clinicaltrials.gov/study/' || s.nct_id AS url,
        current_timestamp AS _gold_at
    FROM silver.estudos AS s
    JOIN flags AS f USING (nct_id)
    WHERE {any_group_sql()}
    """


def references_sql() -> str:
    path = REFERENCES_PATH.as_posix().replace("'", "''")
    return f"""
    CREATE OR REPLACE TABLE gold.referencias AS
    SELECT
        g.nct_id,
        nullif(trim(r.pmid), '') AS pmid,
        upper(nullif(trim(r.reference_type), '')) AS reference_type,
        nullif(trim(r.citation), '') AS citation,
        CAST(NULL AS VARCHAR) AS titulo,
        CAST(NULL AS VARCHAR) AS periodico,
        CAST(NULL AS INTEGER) AS ano,
        CAST(NULL AS VARCHAR) AS resumo,
        CASE
            WHEN nullif(trim(r.pmid), '') IS NULL THEN 'sem_pmid'
            ELSE 'pendente'
        END AS busca_status
    FROM read_csv(
        '{path}',
        delim='|',
        header=true,
        quote='"',
        all_varchar=true,
        max_line_size=50000000
    ) AS r
    JOIN gold.estudos AS g ON g.nct_id = upper(trim(r.nct_id))
    """


def connect() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    if not REFERENCES_PATH.is_file():
        raise FileNotFoundError(REFERENCES_PATH)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=2")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    return con


def validate(con: duckdb.DuckDBPyConnection) -> None:
    loaded = con.execute("SELECT count(*) FROM gold.estudos").fetchone()[0]
    invalid = con.execute(
        """
        SELECT count(*)
        FROM gold.estudos
        WHERE overall_status <> 'COMPLETED'
           OR termos_encontrados IS NULL
           OR len(termos_encontrados) = 0
        """
    ).fetchone()[0]
    missing = con.execute(
        """
        SELECT count(*)
        FROM gold.estudos AS g
        ANTI JOIN silver.estudos AS s ON s.nct_id = g.nct_id
        """
    ).fetchone()[0]
    print(f"gold.estudos: {loaded}")
    groups = con.execute(
        """
        SELECT unnest AS grupo, count(*) AS total
        FROM gold.estudos, unnest(termos_encontrados)
        GROUP BY 1
        ORDER BY grupo
        """
    ).fetchall()
    for grupo, total in groups:
        print(f"{grupo}: {total}")
    with_pmid, references, with_summary = con.execute(
        """
        SELECT
            count(*) FILTER (WHERE pmid IS NOT NULL),
            count(*),
            count(*) FILTER (WHERE busca_status = 'ok')
        FROM gold.referencias
        """
    ).fetchone()
    print(f"gold.referencias: {references}")
    print(f"referencias com pmid: {with_pmid}")
    print(f"resumos restaurados: {with_summary}")
    if loaded == 0 or invalid or missing:
        print(
            "Falha: a gold não ficou só com estudos concluídos da silver "
            "de pilates, fisioterapia, mobilidade ou força.",
            file=sys.stderr,
        )
        sys.exit(1)


def cache_pubmed(con: duckdb.DuckDBPyConnection) -> None:
    exists = con.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'gold' AND table_name = 'referencias'
        """
    ).fetchone()[0]
    if not exists:
        return
    print("guardando resumos da PubMed...", flush=True)
    con.execute(
        """
        CREATE OR REPLACE TABLE gold._pubmed_cache AS
        SELECT nct_id, pmid, titulo, periodico, ano, resumo, busca_status
        FROM gold.referencias
        WHERE pmid IS NOT NULL
          AND busca_status IN ('ok', 'nao_encontrado', 'erro')
        """
    )


def restore_pubmed(con: duckdb.DuckDBPyConnection) -> None:
    exists = con.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'gold' AND table_name = '_pubmed_cache'
        """
    ).fetchone()[0]
    if not exists:
        return
    print("restaurando resumos da PubMed...", flush=True)
    con.execute(
        """
        UPDATE gold.referencias AS r
        SET titulo = c.titulo,
            periodico = c.periodico,
            ano = c.ano,
            resumo = c.resumo,
            busca_status = c.busca_status
        FROM gold._pubmed_cache AS c
        WHERE r.nct_id = c.nct_id
          AND r.pmid = c.pmid
        """
    )
    con.execute("DROP TABLE gold._pubmed_cache")


def main() -> None:
    con = connect()
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        cache_pubmed(con)
        print("gravando gold.estudos...", flush=True)
        con.execute(build_estudos_sql())
        print("gravando gold.referencias...", flush=True)
        con.execute(references_sql())
        restore_pubmed(con)
        validate(con)
    finally:
        con.close()
    print(f"banco: {DB_PATH}")


if __name__ == "__main__":
    main()
