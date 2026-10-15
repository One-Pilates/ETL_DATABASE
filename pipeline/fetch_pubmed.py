"""Preenche título, periódico, ano e resumo da PubMed em gold.referencias."""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clinical_trials.duckdb"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 200
TOOL = os.environ.get("NCBI_TOOL", "clinical_trials_gold")
EMAIL = os.environ.get("NCBI_EMAIL", "")
API_KEY = os.environ.get("NCBI_API_KEY", "")
PAUSE_SECONDS = 0.1 if API_KEY else 0.34


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_of(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def find(parent: ET.Element, path: str) -> ET.Element | None:
    node: ET.Element | None = parent
    for part in path.split("/"):
        if node is None:
            return None
        node = next((child for child in node if local(child.tag) == part), None)
    return node


def year_of(article: ET.Element) -> int | None:
    year = text_of(find(article, "MedlineCitation/Article/Journal/JournalIssue/PubDate/Year"))
    if year and year.isdigit():
        return int(year)
    medline = text_of(
        find(article, "MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate")
    )
    if medline:
        match = re.search(r"\d{4}", medline)
        if match:
            return int(match.group(0))
    return None


def abstract_of(article: ET.Element) -> str | None:
    abstract = find(article, "MedlineCitation/Article/Abstract")
    if abstract is None:
        return None
    parts: list[str] = []
    for node in abstract:
        if local(node.tag) != "AbstractText":
            continue
        value = text_of(node)
        if not value:
            continue
        label = node.attrib.get("Label")
        parts.append(f"{label}: {value}" if label else value)
    return "\n\n".join(parts) or None


def parse_articles(payload: bytes) -> dict[str, dict[str, str | int | None]]:
    root = ET.fromstring(payload)
    found: dict[str, dict[str, str | int | None]] = {}
    for article in root.iter():
        if local(article.tag) != "PubmedArticle":
            continue
        pmid = text_of(find(article, "MedlineCitation/PMID"))
        if not pmid:
            continue
        found[pmid] = {
            "titulo": text_of(find(article, "MedlineCitation/Article/ArticleTitle")),
            "periodico": text_of(find(article, "MedlineCitation/Article/Journal/Title")),
            "ano": year_of(article),
            "resumo": abstract_of(article),
        }
    return found


def fetch_batch(pmids: list[str]) -> dict[str, dict[str, str | int | None]]:
    form = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": TOOL,
    }
    if EMAIL:
        form["email"] = EMAIL
    if API_KEY:
        form["api_key"] = API_KEY
    request = Request(
        EFETCH,
        data=urlencode(form).encode(),
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=120) as response:
                return parse_articles(response.read())
        except (HTTPError, URLError, ET.ParseError, TimeoutError) as error:
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"PubMed indisponível para o lote: {last_error}")


def pending_pmids(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        """
        SELECT DISTINCT pmid
        FROM gold.referencias
        WHERE pmid IS NOT NULL
          AND busca_status IN ('pendente', 'erro')
        ORDER BY pmid
        """
    ).fetchall()
    return [row[0] for row in rows]


def store_found(
    con: duckdb.DuckDBPyConnection,
    pmid: str,
    record: dict[str, str | int | None],
) -> None:
    con.execute(
        """
        UPDATE gold.referencias
        SET titulo = ?,
            periodico = ?,
            ano = ?,
            resumo = ?,
            busca_status = 'ok'
        WHERE pmid = ?
          AND busca_status IN ('pendente', 'erro')
        """,
        [record["titulo"], record["periodico"], record["ano"], record["resumo"], pmid],
    )


def store_missing(con: duckdb.DuckDBPyConnection, pmids: list[str]) -> None:
    con.executemany(
        """
        UPDATE gold.referencias
        SET busca_status = 'nao_encontrado'
        WHERE pmid = ?
          AND busca_status IN ('pendente', 'erro')
        """,
        [(pmid,) for pmid in pmids],
    )


def store_error(con: duckdb.DuckDBPyConnection, pmids: list[str]) -> None:
    con.executemany(
        """
        UPDATE gold.referencias
        SET busca_status = 'erro'
        WHERE pmid = ?
          AND busca_status IN ('pendente', 'erro')
        """,
        [(pmid,) for pmid in pmids],
    )


def report(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT busca_status, count(*) AS referencias, count(DISTINCT pmid) AS pmids
        FROM gold.referencias
        GROUP BY busca_status
        ORDER BY busca_status
        """
    ).fetchall()
    for status, references, pmids in rows:
        print(f"{status}: {references} referencias, {pmids} pmids")


def main() -> None:
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    con = duckdb.connect(str(DB_PATH))
    try:
        pmids = pending_pmids(con)
        print(f"pmids pendentes: {len(pmids)}", flush=True)
        for start in range(0, len(pmids), BATCH_SIZE):
            batch = pmids[start : start + BATCH_SIZE]
            print(
                f"buscando {start + 1}-{start + len(batch)} de {len(pmids)}...",
                flush=True,
            )
            try:
                found = fetch_batch(batch)
            except RuntimeError as error:
                print(error, flush=True)
                store_error(con, batch)
                time.sleep(PAUSE_SECONDS)
                continue
            missing = []
            for pmid in batch:
                record = found.get(pmid)
                if record is None:
                    missing.append(pmid)
                else:
                    store_found(con, pmid, record)
            if missing:
                store_missing(con, missing)
            time.sleep(PAUSE_SECONDS)
        report(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
