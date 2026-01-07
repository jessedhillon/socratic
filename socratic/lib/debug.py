from __future__ import annotations

import os
import socket
from contextlib import contextmanager


def _find_port() -> int:
    """Find a free port by creating and closing a temporary socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        return port


def set_trace(port: int | None = None) -> None:
    import jdbpp
    import rpdb

    if port is None:
        port = _find_port()
    rpdb.set_trace(port=port, debugger_base=jdbpp.debugger.Pdb, use_global_pdb=False)  # pyright: ignore [reportAttributeAccessIssue]


def post_mortem(port: int | None = None) -> None:
    import jdbpp
    import rpdb

    if port is None:
        port = _find_port()
    rpdb.post_mortem(port=port, debugger_base=jdbpp.debugger.Pdb, use_global_pdb=False)  # pyright: ignore [reportAttributeAccessIssue]


@contextmanager
def remote_debugger():
    prev_bp = os.environ.get("PYTHONBREAKPOINT")
    os.environ["PYTHONBREAKPOINT"] = f"{__name__}.set_trace"

    try:
        yield
    finally:
        if prev_bp is not None:
            os.environ["PYTHONBREAKPOINT"] = prev_bp
        else:
            del os.environ["PYTHONBREAKPOINT"]
