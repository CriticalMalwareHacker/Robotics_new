"""Phase 1 test shim (new file, no existing code touched).

`app/services/printer.py` does `import fcntl` at module top level. `fcntl`
exists only on POSIX, so importing `app.main` on a Windows laptop fails
before any test runs — including the pre-existing `tests/test_printer.py`.
The printer code itself is untouched (hard rule 1); this conftest only
installs a minimal stub into `sys.modules` when the real module is absent,
so the whole suite stays runnable on hardware-less laptops. On Pi/Linux the
real `fcntl` is used and this stub is a no-op.
"""

import sys
import types

if "fcntl" not in sys.modules:
    try:
        import fcntl  # noqa: F401
    except ImportError:
        stub = types.ModuleType("fcntl")

        def _ioctl(*args, **kwargs):
            raise OSError("fcntl.ioctl stub: no POSIX ioctl on this host")

        stub.ioctl = _ioctl
        sys.modules["fcntl"] = stub
