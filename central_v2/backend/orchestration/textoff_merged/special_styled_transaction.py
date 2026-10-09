"""Recoverable directory publication for Artístico reexecution."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
from threading import local
from uuid import uuid4

from .special_styled_durability import replace as durable_replace

ROOT_NAME = ".central_v2_special_transactions"
LOCK_NAME = ".central_v2_special_transactions.lock"
_held = local()


@contextmanager
def transaction_lock(manga: Path):
    manga = Path(manga).resolve()
    manga.mkdir(parents=True, exist_ok=True)
    held = getattr(_held, "paths", set())
    if manga in held:
        yield
        return
    with (manga / LOCK_NAME).open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        _held.paths = {*held, manga}
        try:
            recover_locked(manga)
            yield
        finally:
            _held.paths = held
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def begin(manga: Path, chapter: str) -> tuple[str, Path]:
    manga = Path(manga).resolve()
    with transaction_lock(manga):
        root = manga / ROOT_NAME
        root.mkdir(parents=True, exist_ok=True)
        identity = uuid4().hex
        folder = root / identity
        folder.mkdir()
        try:
            _write(folder / "journal.json", {"id": identity, "chapter": chapter,
                    "pid": os.getpid(), "state": "staging", "entries": []})
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return identity, folder


def discard_staging(folder: Path) -> None:
    folder = Path(folder).resolve()
    if not folder.exists() or not folder.parent.is_dir() or folder.parent.name != ROOT_NAME:
        return
    journal = folder / "journal.json"
    if not journal.exists():
        shutil.rmtree(folder)
        return
    try:
        state = _read(journal).get("state")
    except (OSError, ValueError, json.JSONDecodeError):
        return
    if state == "staging":
        shutil.rmtree(folder, ignore_errors=True)


def publish(manga: Path, folder: Path, entries: list[dict], validate) -> None:
    """Publish under the manga lock; participating readers must take that lock."""
    manga, folder = Path(manga).resolve(), Path(folder).resolve()
    if not folder.is_relative_to(manga / ROOT_NAME):
        raise ValueError("Transação Artístico fora da obra.")
    with _lock_only(manga):
        recover_locked(manga, skip=folder)
        validate()
        journal_path = folder / "journal.json"
        journal = _read(journal_path)
        prepared, targets = [], set()
        for index, item in enumerate(entries):
            target = Path(item["target"]).resolve()
            staged = Path(item["staged"]).resolve()
            if (not target.is_relative_to(manga) or not staged.is_relative_to(folder)
                    or not staged.is_dir() or target in targets
                    or (target.exists() and not target.is_dir())):
                raise ValueError("Destino ou estágio da transação inválido.")
            targets.add(target)
            prepared.append({"target": str(target.relative_to(manga)),
                "staged": str(staged.relative_to(folder)), "backup": f"backup-{index}",
                "had_previous": target.exists()})
        journal.update(state="publishing", entries=prepared)
        try:
            _write(journal_path, journal)
            for item in prepared:
                target, staged, backup = _paths(manga, folder, item)
                target.parent.mkdir(parents=True, exist_ok=True)
                if item["had_previous"]:
                    durable_replace(target, backup)
                durable_replace(staged, target)
            journal["state"] = "committed"
            _write(journal_path, journal)
        except BaseException:
            _rollback(manga, folder, prepared)
            raise
        shutil.rmtree(folder, ignore_errors=True)


def recover_locked(manga: Path, skip: Path | None = None) -> None:
    root = Path(manga).resolve() / ROOT_NAME
    if not root.is_dir():
        return
    for folder in sorted(root.iterdir()):
        if folder == skip or not folder.is_dir():
            continue
        journal_path = folder / "journal.json"
        if not journal_path.is_file():
            shutil.rmtree(folder)
            continue
        journal = _read(journal_path)
        if journal.get("state") == "committed":
            shutil.rmtree(folder, ignore_errors=True)
        elif journal.get("state") == "publishing":
            _rollback(manga, folder, journal.get("entries", []))
        elif journal.get("state") == "staging" and not _pid_alive(journal.get("pid")):
            shutil.rmtree(folder, ignore_errors=True)
        elif journal.get("state") != "staging":
            shutil.rmtree(folder)


@contextmanager
def _lock_only(manga: Path):
    with (manga / LOCK_NAME).open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _rollback(manga: Path, folder: Path, entries: list[dict]) -> None:
    for item in reversed(entries):
        target, staged, backup = _paths(manga, folder, item)
        if backup.exists():
            _remove(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            durable_replace(backup, target)
        elif not staged.exists() and target.exists() and not item["had_previous"]:
            _remove(target)
    shutil.rmtree(folder)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _pid_alive(pid) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def _paths(manga: Path, folder: Path, item: dict):
    target = (manga / item["target"]).resolve()
    staged = (folder / item["staged"]).resolve()
    backup = (folder / item["backup"]).resolve()
    if (not target.is_relative_to(manga) or not staged.is_relative_to(folder)
            or not backup.is_relative_to(folder)):
        raise ValueError("Caminho inválido no journal de reexecução Artístico.")
    return target, staged, backup


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Journal de reexecução Artístico inválido.")
    return value
