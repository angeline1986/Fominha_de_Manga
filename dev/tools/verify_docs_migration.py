#!/usr/bin/env python3
"""Inventory and verify the documentation migration without changing files."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import html
import json
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
PLAN = DOCS / "organizacao_limpeza_baloes.md"
MAP = ROOT / "dev/tools/docs_migration_map.csv"
BASELINE = ROOT / "dev/tools/docs_migration_before.json"
ALLOWED_CHANGES = ROOT / "dev/tools/docs_migration_allowed_changes.json"
IGNORED_NAMES = {".DS_Store"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_for(source: str, destination: str) -> str:
    src = PurePosixPath(source)
    dst = PurePosixPath(destination)
    if "/auto_merge/" in source or "/balanceamento/" in source or source.endswith("mapa_metro_balanceamento.md"):
        return "FORA_DO_ESCOPO"
    if "/tickets_pendencias/" in source or "/backlog_legacy_" in source or "/99_evidencias_transversais/" in source:
        return "LOTE_4"
    if "/evidencias/" in source and "/text_off/" in source:
        return "LOTE_4"
    if source.startswith("docs/Refatoracao/pendencias_") or "/plano_" in source or "/politica_" in source or "/sanitizacao_" in source:
        return "LOTE_4"
    if destination.startswith("docs/central_v1/"):
        return "LOTE_1"
    if destination.startswith("docs/central_v2/") or source.startswith("docs/central_v2_"):
        return "LOTE_2"
    if source.startswith("docs/Refatoracao/02_processamento/text_off/"):
        return "LOTE_2" if destination.startswith("docs/central_v2/") else "LOTE_3"
    if destination.startswith(("docs/arquitetura/", "docs/historico/", "docs/reconstrucao/")):
        return "LOTE_3"
    if source.startswith("docs/OLD/") or source.startswith("docs/Refatoracao/00_arquitetura/"):
        return "LOTE_3"
    if source == "docs/organizacao_limpeza_baloes.md":
        return "CONTROLE"
    if src == dst and source.startswith("docs/"):
        return "LOTE_3"
    return "LOTE_3"


def status_for(source: str, destination: str, batch: str) -> str:
    if batch == "FORA_DO_ESCOPO" or source == destination:
        return "MANTER"
    if Path(source).suffix.lower() == ".html" or Path(destination).suffix.lower() == ".html":
        return "AGUARDAR_REVISAO_HTML"
    return "MOVER"


def rows_from_plan() -> dict[str, str]:
    text = PLAN.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for match in re.finditer(r"^\| `([^`]+)` \|[^\n]*?\| `([^`]+)` \|", text, re.M):
        source, destination = match.groups()
        if source.startswith("docs/"):
            result[source] = destination
    return result


def build_map() -> int:
    mappings = rows_from_plan()
    for source in [rel(p) for p in sorted(DOCS.rglob("*")) if p.is_file() and p.name not in IGNORED_NAMES]:
        mappings.setdefault(source, source)
    extra_ticket = "docs/Refatoracao/tickets_pendencias/CV2-PERF-01.md"
    if (ROOT / extra_ticket).is_file():
        mappings[extra_ticket] = "docs/gestao/tickets/central_v2/CV2-PERF-01.md"

    MAP.parent.mkdir(parents=True, exist_ok=True)
    with MAP.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "destination", "batch", "action"])
        writer.writeheader()
        for source, destination in sorted(mappings.items()):
            batch = batch_for(source, destination)
            writer.writerow({
                "source": source,
                "destination": destination,
                "batch": batch,
                "action": status_for(source, destination, batch),
            })
    print(f"Mapa gravado: {len(mappings)} caminhos em {rel(MAP)}")
    return 0


def local_links(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    refs: list[str] = []
    if path.suffix.lower() == ".md":
        refs.extend(re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text))
        refs.extend(re.findall(r"^\s*\[[^\]]+\]:\s*<?([^\s>]+)", text, re.M))
    elif path.suffix.lower() in {".html", ".htm"}:
        refs.extend(re.findall(r"\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", text, re.I))

    links = []
    for raw in refs:
        target = html.unescape(raw.strip().strip("<>"))
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        if target.startswith("/"):
            continue
        resolved = (path.parent / unquote(parsed.path)).resolve()
        try:
            target_rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        links.append({"source": rel(path), "target": target, "resolved": target_rel})
    return links


def inventory() -> dict:
    files = [p for p in sorted(DOCS.rglob("*")) if p.is_file() and p.name not in IGNORED_NAMES]
    links = [link for path in files for link in local_links(path)]
    return {
        "files": {rel(path): digest(path) for path in files},
        "links": links,
    }


def snapshot() -> int:
    payload = inventory()
    BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Baseline salvo: {len(payload['files'])} arquivos, {len(payload['links'])} links em {rel(BASELINE)}")
    return 0


def verify(through: str = "LOTE_4") -> int:
    if not BASELINE.is_file() or not MAP.is_file():
        print("ERRO: gere o mapa e o baseline antes da verificacao.")
        return 2
    before = json.loads(BASELINE.read_text(encoding="utf-8"))
    after = inventory()
    allowed_changes = json.loads(ALLOWED_CHANGES.read_text(encoding="utf-8")) if ALLOWED_CHANGES.is_file() else {}
    with MAP.open(encoding="utf-8", newline="") as handle:
        mappings = list(csv.DictReader(handle))

    errors: list[str] = []
    sources = {row["source"] for row in mappings}
    missing_map = sorted(set(before["files"]) - sources)
    if missing_map:
        errors.extend(f"SEM_MAPA {path}" for path in missing_map)

    destination_sources: dict[str, list[str]] = {}
    justified_hash_changes: list[str] = []
    for row in mappings:
        destination_sources.setdefault(row["destination"], []).append(row["source"])
    for destination, owners in destination_sources.items():
        if len(owners) > 1:
            errors.append(f"DESTINO_DUPLICADO {destination}: {', '.join(sorted(owners))}")
    moving_sources = {row["source"] for row in mappings if row["action"] == "MOVER"}
    for row in mappings:
        if (row["action"] == "MOVER" and row["destination"] != row["source"]
                and row["destination"] in before["files"]
                and row["destination"] not in moving_sources):
            errors.append(f"DESTINO_PREEXISTENTE {row['source']} -> {row['destination']}")

    lot_order = {"LOTE_1": 1, "LOTE_2": 2, "LOTE_3": 3, "LOTE_4": 4}
    through_number = lot_order[through]

    expected_after: set[str] = set()
    for row in mappings:
        source, destination, action = row["source"], row["destination"], row["action"]
        src_exists = source in after["files"]
        dst_exists = destination in after["files"]
        if action == "MOVER":
            if lot_order.get(row["batch"], 0) <= through_number:
                expected_after.add(destination)
                if src_exists:
                    errors.append(f"ORIGEM_AINDA_EXISTE {source}")
                if not dst_exists:
                    errors.append(f"DESTINO_AUSENTE {source} -> {destination}")
            else:
                expected_after.add(source)
                if not src_exists:
                    errors.append(f"LOTE_FUTURO_MOVIDO_ANTES_DA_AUTORIZACAO {source}")
                if dst_exists:
                    errors.append(f"DESTINO_DE_LOTE_FUTURO_JA_EXISTE {source} -> {destination}")
        elif action == "AGUARDAR_REVISAO_HTML":
            expected_after.add(source)
            if not src_exists:
                errors.append(f"HTML_REMOVIDO_ANTES_DA_REVISAO {source}")
        elif action == "MANTER":
            expected_after.add(source)
            if not src_exists:
                errors.append(f"ARQUIVO_MANTIDO_AUSENTE {source}")

        hash_path = destination if action != "AGUARDAR_REVISAO_HTML" and (
            action != "MOVER" or lot_order.get(row["batch"], 0) <= through_number
        ) else source
        if source in before["files"] and hash_path in after["files"]:
            expected_hash = before["files"][source]
            actual_hash = after["files"][hash_path]
            if actual_hash != expected_hash:
                allowance = allowed_changes.get(hash_path, {})
                if (allowance.get("before_sha256") == expected_hash
                        and allowance.get("after_sha256") == actual_hash
                        and allowance.get("reason")):
                    justified_hash_changes.append(f"{source} -> {hash_path}: {allowance['reason']}")
                else:
                    errors.append(f"CONTEUDO_DIVERGENTE {source} -> {hash_path}")
        if source in before["files"] and not src_exists and not dst_exists:
            errors.append(f"POTENCIALMENTE_PERDIDO {source} -> {destination}")

    unmapped_now = sorted(set(after["files"]) - expected_after)
    absent_after = sorted(expected_after - set(after["files"]))
    if unmapped_now:
        errors.extend(f"ARQUIVO_SEM_DESTINO_PREVISTO {path}" for path in unmapped_now)
    if absent_after:
        errors.extend(f"DESTINO_ESPERADO_AUSENTE {path}" for path in absent_after)

    baseline_paths = set(before["files"])
    broken_before = [
        link for link in before["links"]
        if link["resolved"] not in baseline_paths and not (ROOT / link["resolved"]).exists()
    ]
    broken_links = [link for link in after["links"] if not (ROOT / link["resolved"]).exists()]
    errors.extend(f"LINK_QUEBRADO {link['source']} -> {link['target']}" for link in broken_links)
    row_by_source = {row["source"]: row for row in mappings}

    def final_path(path: str) -> str:
        row = row_by_source.get(path)
        if (row and row["action"] == "MOVER"
                and lot_order.get(row["batch"], 0) <= through_number):
            return row["destination"]
        return path

    baseline_links = Counter(
        (final_path(item["source"]), final_path(item["resolved"]))
        for item in before["links"]
    )
    current_links = Counter((item["source"], item["resolved"]) for item in after["links"])
    unmatched_before = baseline_links - current_links
    unmatched_after = current_links - baseline_links

    print(f"Lotes verificados ate: {through}")
    print(f"Arquivos antes: {len(before['files'])}; depois: {len(after['files'])}")
    print(f"Destinos realizados/locais esperados: {len(expected_after)}; presentes: {len(expected_after & set(after['files']))}")
    print(f"Links locais antes/depois: {len(before['links'])}/{len(after['links'])}; sem correspondencia apos mapear destinos: {sum(unmatched_before.values())}; novos sem origem prevista: {sum(unmatched_after.values())}")
    print(f"Links quebrados antes: {len(broken_before)}; depois: {len(broken_links)}")
    print(f"Arquivos sem destino previsto: {len(unmapped_now)}; destinos esperados ausentes: {len(absent_after)}")
    print(f"Alteracoes de hash justificadas: {len(justified_hash_changes)}")
    for change in justified_hash_changes:
        print(f"  JUSTIFICADO {change}")
    if errors:
        print("DIVERGENCIAS:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Verificacao concluida sem divergencias.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-map", "snapshot", "verify"), nargs="?", default="verify")
    parser.add_argument("--through", choices=("LOTE_1", "LOTE_2", "LOTE_3", "LOTE_4"), default="LOTE_4")
    args = parser.parse_args()
    if args.command == "verify":
        return verify(args.through)
    return {"build-map": build_map, "snapshot": snapshot}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
