import shutil
import subprocess
import typing as t
from collections.abc import Mapping

try:
    import gi  # pyright: ignore [reportMissingImports]

    gi.require_version("Notify", "0.7")

    from gi.repository import Notify  # pyright: ignore [reportMissingImports, reportUnknownVariableType]

    Notify.init("basis")
except (ImportError, ValueError):
    Notify = None

KT = t.TypeVar("KT")
VT = t.TypeVar("VT")
T = t.TypeVar("T", bound=dict[t.Any, t.Any])
RecursiveMapping = VT | Mapping[KT, "RecursiveMapping[KT, VT]"]


def deep_update(
    d1: dict[KT, RecursiveMapping[KT, VT]], d2: Mapping[KT, RecursiveMapping[KT, VT]]
) -> dict[KT, RecursiveMapping[KT, VT]]:
    result = d1.copy()
    for k, v in d2.items():
        if isinstance(v, Mapping) and k in result and isinstance(result[k], Mapping):
            result[k] = deep_update(result[k], v)  # type: ignore
        else:
            result[k] = v
    return result


F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def serial(f: F) -> F:
    f.__serial__ = True  # pyright: ignore [reportFunctionMemberAccess]
    return f


def is_serial(f: t.Callable[..., t.Any]) -> bool:
    return getattr(f, "__serial__", False)


def clipboard_notify(name: str, s: str) -> bool:
    wl_copy_path = shutil.which("wl-copy")
    if not wl_copy_path:
        raise RuntimeError("cannot find wl-copy")
    cmd = [wl_copy_path]
    subprocess.run(cmd, text=True, input=s, stdout=subprocess.DEVNULL)
    notify(f"Copied {name!s}", f"{s!r} was copied to the clipboard", "edit-copy")
    return True


def notify(title: str, text: str, icon: str):
    if Notify is None:
        return
    n = Notify.Notification.new(title, text, icon)  # pyright: ignore [reportUnknownVariableType]
    n.show()
