"""Install checksum-pinned k3d into this repository only; never edit PATH/system settings."""

import hashlib
import os
import platform
from urllib.request import urlopen

from common import ROOT


def main():
    system = platform.system()
    if platform.machine().lower() not in {"amd64", "x86_64"} or system not in {
        "Windows",
        "Linux",
    }:
        raise RuntimeError(
            "This reproducible setup currently targets Windows/Linux amd64"
        )
    name = "k3d-windows-amd64.exe" if system == "Windows" else "k3d-linux-amd64"
    expected = (
        "655d2aadcb1f0a0dd196c5cbc564687ba945a9547c8e82c9fc532051fb260e22"
        if system == "Windows"
        else "dbaa79a76ace7f4ca230a1ff41dc7d8a5036a8ad0309e9c54f9bf3836dbe853e"
    )
    path = ROOT / ".superpowers/tools" / ("k3d.exe" if system == "Windows" else "k3d")
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        with urlopen(
            "https://github.com/k3d-io/k3d/releases/download/v5.8.3/" + name, timeout=60
        ) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("k3d checksum mismatch; refusing execution")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if os.name != "nt":
            path.chmod(0o700)
    print("Repository-local k3d v5.8.3 verified; system PATH and kubeconfig unchanged.")


if __name__ == "__main__":
    main()
