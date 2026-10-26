"""Hide local account paths before diagnostic text reaches a log destination."""
import re
from pathlib import Path


_HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s:'\"<>()[\]]+")
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])


def redact_log_text(value: str) -> str:
    """Keep useful relative paths without exposing the local account name."""
    return _HOME_PATH.sub("[HOME]", str(value).replace(_PROJECT_ROOT, "[PROJETO]"))


def forward_redacted(source, destination) -> None:
    """Drain a subprocess stream while writing only sanitized text."""
    try:
        for line in source:
            destination.write(redact_log_text(line))
            destination.flush()
    finally:
        source.close()
