"""Read-only, deliberately narrow Linux capture; no config contents collected."""
import hashlib
import platform
import shutil
from pathlib import Path

from .core import CATALOG, ReforgeError

CONFIGS = {"neovim": ".config/nvim/init.lua", "git": ".gitconfig"}
BINARIES = {**{app: app for app in CATALOG}, "neovim": "nvim"}


def capture(home=None):
    if platform.system() != "Linux":
        raise ReforgeError("v0.1 capture supports Linux; Windows/macOS import is a future adapter")
    home = Path(home) if home is not None else Path.home()
    os_info = platform.freedesktop_os_release()
    configs = {}
    for app, relative in CONFIGS.items():
        path = home / relative
        # Symlinks and oversized files are excluded; hashes are for local drift detection.
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000:
            configs[app] = {"relative_path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    model_path = Path("/sys/firmware/devicetree/base/model")
    machine_model = "unknown"
    if model_path.is_file():
        machine_model = model_path.read_text(errors="replace").strip("\x00\n")[:200] or "unknown"
    return {"schema_version": 1, "os_id": os_info.get("ID", "unknown"),
            "os_version": os_info.get("VERSION_ID", "unknown"),
            "architecture": platform.machine(), "machine_model": machine_model,
            "installed_applications": sorted(app for app, exe in BINARIES.items() if shutil.which(exe)),
            "config_fingerprints": configs}
