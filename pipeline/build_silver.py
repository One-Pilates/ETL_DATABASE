"""Higieniza raw.estudos e grava silver.estudos e silver.qualidade."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
TEMP_DIR = ROOT / "data" / "tmp"

PHASE_ORDER = (
    "EARLY_PHASE1",
    "PHASE1",
    "PHASE2",
    "PHASE3",
    "PHASE4",
    "NA",
)
AGE_UNITS = ("year", "month", "week", "day", "hour", "minute")

DATE_COLS = (
    "study_first_submitted_date",
    "results_first_submitted_date",
    "disposition_first_submitted_date",
    "last_update_submitted_date",
    "study_first_submitted_qc_date",
    "study_first_posted_date",
    "results_first_submitted_qc_date",
    "results_first_posted_date",
    "disposition_first_submitted_qc_date",
    "disposition_first_posted_date",
    "last_update_submitted_qc_date",
    "last_update_posted_date",
    "start_date",
    "verification_date",
    "completion_date",
    "primary_completion_date",
    "nlm_download_date",
)
INT_COLS = (
    "enrollment",
    "number_of_arms",
    "number_of_groups",
    "number_of_facilities",
    "number_of_nsae_subjects",
    "number_of_sae_subjects",
    "registered_in_calendar_year",
    "actual_duration",
    "months_to_report_results",
    "minimum_age_num",
    "maximum_age_num",
    "number_of_primary_outcomes_to_measure",
    "number_of_secondary_outcomes_to_measure",
    "number_of_other_outcomes_to_measure",
)
BOOL_COLS = (
    "has_expanded_access",
    "expanded_access_type_individual",
    "expanded_access_type_intermediate",
    "expanded_access_type_treatment",
    "has_dmc",
    "is_fda_regulated_drug",
    "is_fda_regulated_device",
    "is_unapproved_device",
    "is_ppsd",
    "is_us_export",
    "delayed_posting",
    "fdaaa801_violation",
    "patient_registry",
    "were_results_reported",
    "has_us_facility",
    "has_single_facility",
    "subject_masked",
    "caregiver_masked",
    "investigator_masked",
    "outcomes_assessor_masked",
    "healthy_volunteers",
    "gender_based",
    "adult",
    "child",
    "older_adult",
)
CODE_COLS = (
    "study_first_posted_date_type",
    "results_first_posted_date_type",
    "disposition_first_posted_date_type",
    "last_update_posted_date_type",
    "start_month_year",
    "start_date_type",
    "verification_month_year",
    "completion_month_year",
    "completion_date_type",
    "primary_completion_month_year",
    "primary_completion_date_type",
    "study_type",
    "overall_status",
    "last_known_status",
    "phase",
    "enrollment_type",
    "source_class",
    "allocation",
    "intervention_model",
    "observational_model",
    "primary_purpose",
    "time_perspective",
    "masking",
    "sampling_method",
    "gender",
    "plan_to_share_ipd",
)
RICH_COLS = (
    "baseline_population",
    "limitations_and_caveats",
    "biospec_description",
    "ipd_time_frame",
    "ipd_access_criteria",
    "plan_to_share_ipd_description",
    "masking_description",
    "intervention_model_description",
    "population",
    "criteria",
    "gender_description",
    "brief_summary",
)
TEXT_COLS = (
    "nlm_download_date_description",
    "target_duration",
    "brief_title",
    "official_title",
    "source",
    "why_stopped",
    "biospec_retention",
    "ipd_url",
    "expanded_access_status_for_nctid",
    "baseline_type_units_analyzed",
    "minimum_age",
    "maximum_age",
)
ACTUAL_DATE_PAIRS = (
    ("study_first_posted_date", "study_first_posted_date_type"),
    ("results_first_posted_date", "results_first_posted_date_type"),
    ("disposition_first_posted_date", "disposition_first_posted_date_type"),
    ("last_update_posted_date", "last_update_posted_date_type"),
    ("start_date", "start_date_type"),
    ("completion_date", "completion_date_type"),
    ("primary_completion_date", "primary_completion_date_type"),
)
DATE_TYPE_PAIRS = (
    ("start_date", "start_date_type"),
    ("completion_date", "completion_date_type"),
    ("primary_completion_date", "primary_completion_date_type"),
)


def blank(expr: str) -> str:
    return f"nullif(trim({expr}), '')"


def code(expr: str) -> str:
    return f"upper({blank(expr)})"


def rich(expr: str) -> str:
    return (
        "replace(replace(replace("
        f"{blank(expr)}, '~', chr(10)), chr(92) || '>', '>'), chr(92) || '<', '<')"
    )


def collapse(expr: str) -> str:
    return (
        "nullif(trim(regexp_replace("
        f"{blank(expr)}, chr(92) || 's+', ' ', 'g')), '')"
    )


def as_date(expr: str) -> str:
    return f"try_cast({blank(expr)} AS DATE)"


def as_int(expr: str) -> str:
    return f"try_cast({blank(expr)} AS BIGINT)"


def as_ts(expr: str) -> str:
    return f"try_cast({blank(expr)} AS TIMESTAMP)"


def as_bool(expr: str) -> str:
    return (
        f"CASE lower({blank(expr)}) WHEN 't' THEN TRUE WHEN 'f' THEN FALSE ELSE NULL END"
    )


def age_years(num: str, unit: str) -> str:
    return f"""
    CASE {unit}
        WHEN 'year' THEN {num} / 1.0
        WHEN 'month' THEN {num} / 12.0
        WHEN 'week' THEN {num} / 52.1775
        WHEN 'day' THEN {num} / 365.25
        WHEN 'hour' THEN {num} / (365.25 * 24)
        WHEN 'minute' THEN {num} / (365.25 * 24 * 60)
        ELSE NULL
    END
    """


def dedup(items: str) -> str:
    return f"list_filter({items}, (x, i) -> list_position({items}, x) = i)"


def conditions_sql() -> str:
    src = "coalesce(conditions, CAST([] AS STRUCT(name VARCHAR)[]))"
    items = f"""
    list_transform({src}, x -> struct_pack(
        name := nullif(trim(x.name), ''),
        name_normalized := nullif(trim(regexp_replace(
            rtrim(lower(trim(x.name)), '.'), chr(92) || 's+', ' ', 'g'
        )), '')
    ))
    """
    return dedup(items)


def interventions_sql() -> str:
    src = (
        "coalesce(interventions, CAST([] AS STRUCT("
        "intervention_type VARCHAR, name VARCHAR, description VARCHAR)[]))"
    )
    items = f"""
    list_transform({src}, x -> struct_pack(
        intervention_type := upper(nullif(trim(x.intervention_type), '')),
        name := nullif(trim(x.name), ''),
        description := {rich("x.description")}
    ))
    """
    return dedup(items)


def sponsors_sql() -> str:
    src = (
        "coalesce(sponsors, CAST([] AS STRUCT("
        "agency_class VARCHAR, lead_or_collaborator VARCHAR, name VARCHAR)[]))"
    )
    items = f"""
    list_transform({src}, x -> struct_pack(
        agency_class := upper(nullif(trim(x.agency_class), '')),
        lead_or_collaborator := upper(nullif(trim(x.lead_or_collaborator), '')),
        name := {collapse("x.name")}
    ))
    """
    return dedup(items)


def countries_sql() -> str:
    src = "coalesce(countries, CAST([] AS STRUCT(name VARCHAR, removed VARCHAR)[]))"
    items = f"""
    list_transform({src}, x -> struct_pack(
        name := nullif(trim(x.name), ''),
        removed := CASE lower(nullif(trim(x.removed), ''))
            WHEN 't' THEN TRUE
            WHEN 'f' THEN FALSE
            ELSE NULL
        END
    ))
    """
    return dedup(items)


def mesh_sql() -> str:
    src = (
        "coalesce(mesh_terms, CAST([] AS STRUCT("
        "mesh_term VARCHAR, mesh_type VARCHAR)[]))"
    )
    items = f"""
    list_transform({src}, x -> struct_pack(
        mesh_term := nullif(trim(x.mesh_term), ''),
        mesh_type := nullif(trim(x.mesh_type), ''),
        mesh_term_normalized := lower(nullif(trim(x.mesh_term), ''))
    ))
    """
    return dedup(items)


def scalar_columns() -> list[tuple[str, str]]:
    columns = [("nct_id", code("nct_id")), ("acronym", code("acronym"))]
    columns += [(name, as_date(name)) for name in DATE_COLS]
    columns += [(name, as_int(name)) for name in INT_COLS]
    columns += [(name, as_bool(name)) for name in BOOL_COLS]
    columns += [(name, code(name)) for name in CODE_COLS]
    columns += [(name, rich(name)) for name in RICH_COLS]
    columns += [(name, blank(name)) for name in TEXT_COLS]
    columns += [
        ("expanded_access_nctid", code("expanded_access_nctid")),
        ("created_at", as_ts("created_at")),
        ("updated_at", as_ts("updated_at")),
        ("minimum_age_unit", f"lower({blank('minimum_age_unit')})"),
        ("maximum_age_unit", f"lower({blank('maximum_age_unit')})"),
        ("_ingested_at", "_ingested_at"),
    ]
    return columns


def build_estudos_sql() -> str:
    select_list = ",\n        ".join(
        f"{expr} AS {name}" for name, expr in scalar_columns()
    )
    phase_list = ", ".join(f"'{phase}'" for phase in PHASE_ORDER)
    return f"""
    CREATE OR REPLACE TABLE silver.estudos AS
    WITH typed AS (
        SELECT
            {select_list},
            {conditions_sql()} AS conditions,
            {interventions_sql()} AS interventions,
            {sponsors_sql()} AS sponsors,
            {countries_sql()} AS countries,
            {mesh_sql()} AS mesh_terms
        FROM raw.estudos
    )
    SELECT
        typed.*,
        CASE
            WHEN typed.phase IS NULL THEN CAST([] AS VARCHAR[])
            ELSE list_filter(
                [{phase_list}],
                p -> list_contains(string_split(typed.phase, '/'), p)
            )
        END AS phases,
        year(typed.start_date) AS ano_inicio,
        year(typed.primary_completion_date) AS ano_conclusao_primaria,
        CASE
            WHEN typed.overall_status = 'UNKNOWN' AND typed.last_known_status IS NOT NULL
                THEN typed.last_known_status
            ELSE typed.overall_status
        END AS status_efetivo,
        {age_years("typed.minimum_age_num", "typed.minimum_age_unit")} AS minimum_age_years,
        {age_years("typed.maximum_age_num", "typed.maximum_age_unit")} AS maximum_age_years,
        list_filter(typed.sponsors, x -> x.lead_or_collaborator = 'LEAD') AS lead_sponsors,
        list_filter(typed.countries, x -> x.removed IS NOT TRUE) AS countries_current,
        typed.brief_summary IS NOT NULL AS tem_resumo,
        len(typed.conditions) > 0 AS tem_condicao,
        len(typed.interventions) > 0 AS tem_intervencao,
        len(list_filter(typed.sponsors, x -> x.lead_or_collaborator = 'LEAD')) > 0
            AS tem_patrocinador_lead,
        coalesce(regexp_full_match(typed.nct_id, '^NCT[0-9]{{8}}$'), FALSE) AS nct_id_valido,
        current_timestamp AS _silver_at
    FROM typed
    """


def conversion_sql(column: str, predicate: str) -> str:
    return f"""
    SELECT upper(trim(nct_id)), 'conversao_invalida', '{column}', {blank(column)}
    FROM raw.estudos
    WHERE {predicate}
    """


def quality_statements() -> list[tuple[str, str]]:
    statements: list[tuple[str, str]] = []
    for column in DATE_COLS:
        cleaned = blank(column)
        statements.append(
            (
                f"conversao_invalida:{column}",
                conversion_sql(
                    column,
                    f"{cleaned} IS NOT NULL AND try_cast({cleaned} AS DATE) IS NULL",
                ),
            )
        )
    for column in INT_COLS:
        cleaned = blank(column)
        statements.append(
            (
                f"conversao_invalida:{column}",
                conversion_sql(
                    column,
                    f"{cleaned} IS NOT NULL AND try_cast({cleaned} AS BIGINT) IS NULL",
                ),
            )
        )
    for column in ("created_at", "updated_at"):
        cleaned = blank(column)
        statements.append(
            (
                f"conversao_invalida:{column}",
                conversion_sql(
                    column,
                    f"{cleaned} IS NOT NULL AND try_cast({cleaned} AS TIMESTAMP) IS NULL",
                ),
            )
        )
    for column in BOOL_COLS:
        cleaned = blank(column)
        statements.append(
            (
                f"conversao_invalida:{column}",
                conversion_sql(
                    column,
                    f"{cleaned} IS NOT NULL AND lower({cleaned}) NOT IN ('t', 'f')",
                ),
            )
        )
    statements.append(
        (
            "conversao_invalida:countries.removed",
            f"""
            SELECT upper(trim(nct_id)), 'conversao_invalida', 'countries.removed',
                   nullif(trim(unnest.removed), '')
            FROM raw.estudos, unnest(countries)
            WHERE nullif(trim(unnest.removed), '') IS NOT NULL
              AND lower(trim(unnest.removed)) NOT IN ('t', 'f')
            """,
        )
    )
    phase_in = ", ".join(f"'{phase}'" for phase in PHASE_ORDER)
    units_in = ", ".join(f"'{unit}'" for unit in AGE_UNITS)
    statements.extend(
        [
            (
                "nct_id_fora_do_padrao",
                """
                SELECT nct_id, 'nct_id_fora_do_padrao', 'nct_id', nct_id
                FROM silver.estudos
                WHERE NOT nct_id_valido
                """,
            ),
            (
                "fase_fora_do_dominio",
                f"""
                SELECT nct_id, 'fase_fora_do_dominio', 'phase', nullif(trim(unnest), '')
                FROM silver.estudos, unnest(string_split(phase, '/'))
                WHERE nullif(trim(unnest), '') IS NOT NULL
                  AND nullif(trim(unnest), '') NOT IN ({phase_in})
                """,
            ),
            (
                "unidade_idade_desconhecida:minimum",
                f"""
                SELECT nct_id, 'unidade_idade_desconhecida', 'minimum_age_unit', minimum_age_unit
                FROM silver.estudos
                WHERE minimum_age_unit IS NOT NULL
                  AND minimum_age_unit NOT IN ({units_in})
                """,
            ),
            (
                "unidade_idade_desconhecida:maximum",
                f"""
                SELECT nct_id, 'unidade_idade_desconhecida', 'maximum_age_unit', maximum_age_unit
                FROM silver.estudos
                WHERE maximum_age_unit IS NOT NULL
                  AND maximum_age_unit NOT IN ({units_in})
                """,
            ),
            (
                "conclusao_anterior_ao_inicio",
                """
                SELECT nct_id, 'conclusao_anterior_ao_inicio', 'completion_date',
                       cast(completion_date AS VARCHAR)
                FROM silver.estudos
                WHERE completion_date < start_date
                """,
            ),
            (
                "conclusao_primaria_posterior_a_conclusao",
                """
                SELECT nct_id, 'conclusao_primaria_posterior_a_conclusao',
                       'primary_completion_date', cast(primary_completion_date AS VARCHAR)
                FROM silver.estudos
                WHERE primary_completion_date > completion_date
                """,
            ),
            (
                "mes_ano_inicio_divergente",
                """
                SELECT nct_id, 'mes_ano_inicio_divergente', 'start_month_year', start_month_year
                FROM silver.estudos
                WHERE start_month_year IS NOT NULL
                  AND start_date IS NOT NULL
                  AND left(start_month_year, 7) <> strftime(start_date, '%Y-%m')
                """,
            ),
            (
                "postagem_anterior_a_submissao",
                """
                SELECT nct_id, 'postagem_anterior_a_submissao', 'study_first_posted_date',
                       cast(study_first_posted_date AS VARCHAR)
                FROM silver.estudos
                WHERE study_first_posted_date < study_first_submitted_date
                """,
            ),
            (
                "enrollment_negativo",
                """
                SELECT nct_id, 'enrollment_negativo', 'enrollment', cast(enrollment AS VARCHAR)
                FROM silver.estudos
                WHERE enrollment < 0
                """,
            ),
            (
                "enrollment_acima_de_10_milhoes",
                """
                SELECT nct_id, 'enrollment_acima_de_10_milhoes', 'enrollment',
                       cast(enrollment AS VARCHAR)
                FROM silver.estudos
                WHERE enrollment > 10000000
                """,
            ),
            (
                "enrollment_zero_concluido",
                """
                SELECT nct_id, 'enrollment_zero_concluido', 'enrollment', '0'
                FROM silver.estudos
                WHERE enrollment = 0 AND overall_status = 'COMPLETED'
                """,
            ),
            (
                "numero_bracos_negativo",
                """
                SELECT nct_id, 'numero_bracos_negativo', 'number_of_arms',
                       cast(number_of_arms AS VARCHAR)
                FROM silver.estudos
                WHERE number_of_arms < 0
                """,
            ),
            (
                "numero_grupos_negativo",
                """
                SELECT nct_id, 'numero_grupos_negativo', 'number_of_groups',
                       cast(number_of_groups AS VARCHAR)
                FROM silver.estudos
                WHERE number_of_groups < 0
                """,
            ),
            (
                "idade_minima_maior_que_maxima",
                """
                SELECT nct_id, 'idade_minima_maior_que_maxima', 'minimum_age_years',
                       cast(minimum_age_years AS VARCHAR)
                FROM silver.estudos
                WHERE minimum_age_years > maximum_age_years
                """,
            ),
            (
                "idade_maxima_crianca_com_older_adult",
                """
                SELECT nct_id, 'idade_maxima_crianca_com_older_adult', 'older_adult',
                       cast(maximum_age_years AS VARCHAR)
                FROM silver.estudos
                WHERE maximum_age_years < 18 AND older_adult
                """,
            ),
            (
                "idade_minima_idoso_com_child",
                """
                SELECT nct_id, 'idade_minima_idoso_com_child', 'child',
                       cast(minimum_age_years AS VARCHAR)
                FROM silver.estudos
                WHERE minimum_age_years >= 65 AND child
                """,
            ),
            (
                "multiplos_patrocinadores_lead",
                """
                SELECT nct_id, 'multiplos_patrocinadores_lead', 'lead_sponsors',
                       cast(len(lead_sponsors) AS VARCHAR)
                FROM silver.estudos
                WHERE len(lead_sponsors) > 1
                """,
            ),
            (
                "mascaramento_contraditorio",
                """
                SELECT nct_id, 'mascaramento_contraditorio', 'masking', masking
                FROM silver.estudos
                WHERE masking = 'NONE'
                  AND (
                    coalesce(subject_masked, FALSE)
                    OR coalesce(caregiver_masked, FALSE)
                    OR coalesce(investigator_masked, FALSE)
                    OR coalesce(outcomes_assessor_masked, FALSE)
                  )
                """,
            ),
            (
                "expanded_access_contraditorio",
                """
                SELECT nct_id, 'expanded_access_contraditorio', 'has_expanded_access', 'f'
                FROM silver.estudos
                WHERE has_expanded_access = FALSE
                  AND (
                    coalesce(expanded_access_type_individual, FALSE)
                    OR coalesce(expanded_access_type_intermediate, FALSE)
                    OR coalesce(expanded_access_type_treatment, FALSE)
                  )
                """,
            ),
            (
                "has_us_facility_divergente",
                """
                SELECT nct_id, 'has_us_facility_divergente', 'has_us_facility',
                       cast(has_us_facility AS VARCHAR)
                FROM silver.estudos
                WHERE has_us_facility IS NOT NULL
                  AND has_us_facility <> list_contains(
                    list_transform(countries_current, c -> lower(c.name)),
                    'united states'
                  )
                """,
            ),
            (
                "has_single_facility_divergente",
                """
                SELECT nct_id, 'has_single_facility_divergente', 'has_single_facility',
                       cast(number_of_facilities AS VARCHAR)
                FROM silver.estudos
                WHERE number_of_facilities IS NOT NULL
                  AND has_single_facility IS NOT NULL
                  AND has_single_facility <> (number_of_facilities = 1)
                """,
            ),
            (
                "resultados_sem_data_de_postagem",
                """
                SELECT nct_id, 'resultados_sem_data_de_postagem', 'results_first_posted_date',
                       NULL
                FROM silver.estudos
                WHERE were_results_reported AND results_first_posted_date IS NULL
                """,
            ),
            (
                "duracao_divergente",
                """
                SELECT nct_id, 'duracao_divergente', 'actual_duration',
                       cast(actual_duration AS VARCHAR)
                FROM silver.estudos
                WHERE start_date_type = 'ACTUAL'
                  AND completion_date_type = 'ACTUAL'
                  AND start_date IS NOT NULL
                  AND completion_date IS NOT NULL
                  AND actual_duration IS NOT NULL
                  AND abs(actual_duration - date_diff('month', start_date, completion_date)) > 1
                """,
            ),
            (
                "intervencional_sem_fase",
                """
                SELECT nct_id, 'intervencional_sem_fase', 'phase', NULL
                FROM silver.estudos
                WHERE study_type = 'INTERVENTIONAL' AND phase IS NULL
                """,
            ),
            (
                "encerrado_sem_motivo",
                """
                SELECT nct_id, 'encerrado_sem_motivo', 'why_stopped', overall_status
                FROM silver.estudos
                WHERE overall_status IN ('TERMINATED', 'WITHDRAWN')
                  AND why_stopped IS NULL
                """,
            ),
        ]
    )
    for column in DATE_COLS:
        statements.append(
            (
                f"ano_fora_do_intervalo:{column}",
                f"""
                SELECT nct_id, 'ano_fora_do_intervalo', '{column}', cast({column} AS VARCHAR)
                FROM silver.estudos
                WHERE {column} IS NOT NULL
                  AND (year({column}) < 1900 OR year({column}) > 2100)
                """,
            )
        )
    for column, type_column in ACTUAL_DATE_PAIRS:
        statements.append(
            (
                f"data_actual_no_futuro:{column}",
                f"""
                SELECT nct_id, 'data_actual_no_futuro', '{column}', cast({column} AS VARCHAR)
                FROM silver.estudos
                WHERE {type_column} = 'ACTUAL'
                  AND {column} > cast(_silver_at AS DATE)
                """,
            )
        )
    for column, type_column in DATE_TYPE_PAIRS:
        statements.append(
            (
                f"data_sem_tipo:{column}",
                f"""
                SELECT nct_id, 'data_sem_tipo', '{column}', cast({column} AS VARCHAR)
                FROM silver.estudos
                WHERE {column} IS NOT NULL AND {type_column} IS NULL
                """,
            )
        )
        statements.append(
            (
                f"tipo_sem_data:{type_column}",
                f"""
                SELECT nct_id, 'tipo_sem_data', '{type_column}', {type_column}
                FROM silver.estudos
                WHERE {column} IS NULL AND {type_column} IS NOT NULL
                """,
            )
        )
    return statements


def connect() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=2")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    return con


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
    con = connect()
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        print("gravando silver.estudos...", flush=True)
        con.execute(build_estudos_sql())
        raw_n, raw_d = con.execute(
            "SELECT count(*), count(DISTINCT nct_id) FROM raw.estudos"
        ).fetchone()
        loaded, distinct = con.execute(
            "SELECT count(*), count(DISTINCT nct_id) FROM silver.estudos"
        ).fetchone()
        print(f"raw.estudos: {raw_n}")
        print(f"silver.estudos: {loaded}")
        print(f"nct_id distintos: {distinct}")
        if loaded != raw_n or distinct != raw_n:
            print(
                "Falha: silver.estudos não tem uma linha por estudo da raw.",
                file=sys.stderr,
            )
            sys.exit(1)

        con.execute("DROP TABLE IF EXISTS silver.qualidade")
        con.execute(
            """
            CREATE TABLE silver.qualidade (
                nct_id VARCHAR,
                regra VARCHAR,
                coluna VARCHAR,
                valor VARCHAR
            )
            """
        )
        for name, sql in quality_statements():
            print(f"alerta {name}...", flush=True)
            con.execute(f"INSERT INTO silver.qualidade {sql}")
        totals = con.execute(
            """
            SELECT regra, count(*) AS total
            FROM silver.qualidade
            GROUP BY regra
            ORDER BY total DESC, regra
            """
        ).fetchall()
        alertas = sum(total for _, total in totals)
        print(f"alertas: {alertas}")
        for regra, total in totals:
            print(f"{regra}: {total}")
    finally:
        con.close()

    print("compactando banco...", flush=True)
    compact_database()
    print(f"banco: {DB_PATH}")


if __name__ == "__main__":
    main()
