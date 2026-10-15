"""Baixa o zip flat file mais recente da AACT e extrai os 11 txt da pipeline."""

from __future__ import annotations

import shutil
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "base_dados"
DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
SNAPSHOT_PATH = DATA_DIR / "snapshot.txt"
DAILY_URL = (
    "https://aact.ctti-clinicaltrials.org/static/exported_files/daily/"
    "{stamp}_export_ctgov.zip"
)
NEEDED = (
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
    "study_references",
)
LOOKBACK_DAYS = 45
USER_AGENT = "OnePilates-ETL/1.0"
CHUNK = 1024 * 1024
PROGRESS_EVERY = 100 * CHUNK


def snapshot_name(stamp: str) -> str:
    return f"{stamp}_export_ctgov.zip"


def daily_url(stamp: str) -> str:
    return DAILY_URL.format(stamp=stamp)


def url_exists(url: str) -> bool:
    request = Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:
            return 200 <= response.status < 400
    except HTTPError as error:
        if error.code in (301, 302, 303, 307, 308):
            return True
        if error.code in (403, 405):
            return range_exists(url)
        return False


def range_exists(url: str) -> bool:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.status in (200, 206)
    except HTTPError as error:
        return error.code in (200, 206, 302)


def latest_stamp(today: date | None = None) -> str:
    start = today or date.today()
    for offset in range(LOOKBACK_DAYS):
        stamp = (start - timedelta(days=offset)).strftime("%Y%m%d")
        if url_exists(daily_url(stamp)):
            return stamp
    raise RuntimeError(
        "Nenhum snapshot flat file da AACT encontrado nos últimos "
        f"{LOOKBACK_DAYS} dias."
    )


def local_files_ready() -> bool:
    return all((SOURCE_DIR / f"{name}.txt").is_file() for name in NEEDED)


def read_snapshot() -> str:
    if SNAPSHOT_PATH.is_file():
        return SNAPSHOT_PATH.read_text(encoding="utf-8").strip()
    return ""


def write_snapshot(name: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(name + "\n", encoding="utf-8")


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    print(f"baixando {target.name} (cerca de 2,35 GB)...", flush=True)
    with urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        reported = 0
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            handle.write(chunk)
            done += len(chunk)
            if done - reported >= PROGRESS_EVERY:
                reported = done
                if total:
                    print(
                        f"  {done / 1e9:.2f} / {total / 1e9:.2f} GB",
                        flush=True,
                    )
                else:
                    print(f"  {done / 1e9:.2f} GB", flush=True)
    partial.replace(target)


def extract(zip_path: Path) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {f"{name}.txt" for name in NEEDED}
    with zipfile.ZipFile(zip_path) as archive:
        found: dict[str, zipfile.ZipInfo] = {}
        for info in archive.infolist():
            base = Path(info.filename).name
            if base in wanted and not info.is_dir():
                found[base] = info
        missing = sorted(wanted - found.keys())
        if missing:
            raise SystemExit("O zip da AACT não tem: " + ", ".join(missing))
        for base, info in found.items():
            target = SOURCE_DIR / base
            print(f"extraindo {base}...", flush=True)
            with archive.open(info) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def _keep_local(reason: str) -> tuple[str, bool] | None:
    if not local_files_ready():
        return None
    name = read_snapshot() or "local"
    print(
        f"{reason} Seguindo com o snapshot local {name}.",
        flush=True,
    )
    return name, False


def ensure_sources() -> tuple[str, bool]:
    """Devolve o nome do snapshot e se ele mudou em relação à última carga."""
    previous = read_snapshot()
    try:
        stamp = latest_stamp()
    except (URLError, TimeoutError, OSError) as error:
        kept = _keep_local(f"Rede indisponível ({error}).")
        if kept is not None:
            return kept
        raise SystemExit(
            "Não foi possível consultar a AACT e os txt locais não estão completos."
        ) from error

    name = snapshot_name(stamp)
    if previous == name and local_files_ready():
        print(f"snapshot já está na máquina: {name}", flush=True)
        return name, False

    zip_path = DOWNLOAD_DIR / name
    try:
        if not zip_path.is_file():
            download(daily_url(stamp), zip_path)
        extract(zip_path)
    except (URLError, TimeoutError, OSError, zipfile.BadZipFile) as error:
        kept = _keep_local(f"Falha ao baixar o snapshot ({error}).")
        if kept is not None:
            return kept
        raise
    write_snapshot(name)
    return name, previous != name


def main() -> None:
    name, changed = ensure_sources()
    print(f"snapshot: {name}")
    print(f"atualizado: {'sim' if changed else 'não'}")


if __name__ == "__main__":
    main()
