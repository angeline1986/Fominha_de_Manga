"""Launch workers with sanitized stdout and stderr forwarding."""
import subprocess
import threading

from central_v2.backend.log_redaction import forward_redacted


def launch(command, *, cwd, destination, env=None, start_new_session=False):
    process = subprocess.Popen(
        command, cwd=cwd, env=env, start_new_session=start_new_session,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    reader = threading.Thread(target=forward_redacted,
                              args=(process.stdout, destination), daemon=True)
    reader.start()
    return process, reader
