"""Atualiza o snapshot da AACT e deixa a gold pronta com um comando."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb

from download_aact import ensure_sources

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
CACHE_PATH = ROOT / "data" / "pubmed_cache.parquet"
MYSQL_VARS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
)


def run_script(name: str) -> None:
    script = ROOT / "pipeline" / name
    print(f"\n=== {name} ===", flush=True)
    subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True)


def export_pubmed_cache() -> None:
    if not DB_PATH.is_file():
        return
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        exists = con.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'gold' AND table_name = 'referencias'
            """
        ).fetchone()[0]
        if not exists:
            return
        rows = con.execute(
            """
            SELECT count(*)
            FROM gold.referencias
            WHERE pmid IS NOT NULL
              AND busca_status IN ('ok', 'nao_encontrado', 'erro')
            """
        ).fetchone()[0]
        if not rows:
            return
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        target = CACHE_PATH.as_posix().replace("'", "''")
        con.execute(
            f"""
            COPY (
                SELECT pmid, titulo, periodico, ano, resumo, busca_status
                FROM (
                    SELECT
                        pmid,
                        titulo,
                        periodico,
                        ano,
                        resumo,
                        busca_status,
                        row_number() OVER (
                            PARTITION BY pmid
                            ORDER BY (busca_status = 'ok') DESC
                        ) AS rn
                    FROM gold.referencias
                    WHERE pmid IS NOT NULL
                      AND busca_status IN ('ok', 'nao_encontrado', 'erro')
                )
                WHERE rn = 1
            ) TO '{target}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    print(f"cache PubMed: {CACHE_PATH}", flush=True)


def restore_pubmed_cache() -> None:
    if not CACHE_PATH.is_file() or not DB_PATH.is_file():
        return
    print("devolvendo cache PubMed pelo pmid...", flush=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        source = CACHE_PATH.as_posix().replace("'", "''")
        con.execute(
            f"""
            UPDATE gold.referencias AS r
            SET titulo = c.titulo,
                periodico = c.periodico,
                ano = c.ano,
                resumo = c.resumo,
                busca_status = c.busca_status
            FROM read_parquet('{source}') AS c
            WHERE r.pmid = c.pmid
            """
        )
    finally:
        con.close()


def mysql_ready() -> bool:
    return all(os.environ.get(name) for name in MYSQL_VARS)


def main() -> None:
    name, changed = ensure_sources()
    if changed or not DB_PATH.is_file():
        print(f"refazendo a base a partir de {name}", flush=True)
        export_pubmed_cache()
        run_script("ingest_raw.py")
        run_script("build_silver.py")
        run_script("build_gold.py")
        restore_pubmed_cache()
    else:
        print(
            f"snapshot {name} já carregado. Pulando raw, silver e gold.",
            flush=True,
        )
    run_script("fetch_pubmed.py")
    if mysql_ready():
        run_script("load_mysql.py")
    else:
        print(
            "MySQL pulado. Defina MYSQL_HOST, MYSQL_PORT, MYSQL_USER, "
            "MYSQL_PASSWORD e MYSQL_DATABASE para copiar a gold.",
            flush=True,
        )
    print(f"gold pronta em {DB_PATH}")


if __name__ == "__main__":
    main()
