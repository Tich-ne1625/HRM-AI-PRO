"""Real browser writes through Kubernetes ingress, with an isolated offline test provider."""

import argparse
import atexit
import copy
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

from common import OUT, ROOT, Target
from websockets.sync.client import connect

sys.path.insert(0, str(ROOT / "scripts"))
import phase9_browser as browser


def harness(t):
    assert t.namespace == "insighthr-phase10-acceptance"
    source = (ROOT / "apps/api/tests/acceptance/phase9_app.py").read_text(
        encoding="utf-8"
    )
    source = (
        source.replace("PHASE9_PROJECT", "PHASE10_NAMESPACE")
        .replace("insighthr-phase9-acceptance", t.namespace)
        .replace("phase9_ui_test", "phase10_acceptance_test")
    )
    t.apply(
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "offline-test-harness"},
            "data": {"phase10_app.py": source},
        }
    )
    deployment = t.json("get", "deployment", "api")
    original = copy.deepcopy(deployment)

    def restore_runtime():
        original["metadata"]["resourceVersion"] = t.json("get", "deployment", "api")[
            "metadata"
        ]["resourceVersion"]
        t.call("replace", "-f", "-", body=json.dumps(original))
        t.call("rollout", "status", "deployment/api", "--timeout=180s")
        t.call("delete", "configmap", "offline-test-harness")

    atexit.register(restore_runtime)
    spec = deployment["spec"]["template"]["spec"]
    spec["volumes"] = [
        v for v in spec.get("volumes", []) if v["name"] != "offline-provider"
    ] + [{"name": "offline-provider", "configMap": {"name": "offline-test-harness"}}]
    container = spec["containers"][0]
    container["volumeMounts"] = [
        m for m in container.get("volumeMounts", []) if m["name"] != "offline-provider"
    ] + [{"name": "offline-provider", "mountPath": "/test-harness", "readOnly": True}]
    container["env"] = [{"name": "PHASE10_NAMESPACE", "value": t.namespace}]
    container["command"] = [
        "uvicorn",
        "phase10_app:app",
        "--app-dir",
        "/test-harness",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--no-access-log",
    ]
    t.call("replace", "-f", "-", body=json.dumps(deployment))
    t.call("rollout", "status", "deployment/api", "--timeout=180s")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--with-offline-provider", action="store_true")
    a = p.parse_args()
    if not a.with_offline_provider:
        raise ValueError("Explicit isolated offline provider acknowledgment required")
    t = Target()
    harness(t)
    password = secrets.token_urlsafe(24)
    t.exec(
        "python",
        "-m",
        "app.cli.create_admin",
        "--email",
        "admin.phase9@example.com",
        "--password-stdin",
        body=password + "\n" + password + "\n",
    )
    browser.BASE = "http://localhost:13010"
    browser.OUT = OUT / "browser"
    browser.OUT.mkdir(parents=True, exist_ok=True)
    executable = (
        os.environ.get("PHASE9_BROWSER")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
        or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    )
    process = subprocess.Popen(
        [
            executable,
            "--headless=new",
            "--remote-debugging-port=19249",
            "--remote-allow-origins=http://localhost:19249",
            "--no-first-run",
            "--disable-extensions",
            *(["--no-sandbox"] if os.environ.get("CI") == "true" else []),
            f"--user-data-dir={browser.OUT / ('profile-' + secrets.token_hex(4))}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        for _ in range(80):
            try:
                with urlopen("http://localhost:19249/json", timeout=1) as response:
                    target = next(x for x in json.load(response) if x["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.25)
        else:
            raise RuntimeError("Browser unavailable")
        with connect(
            target["webSocketDebuggerUrl"], proxy=None, max_size=12_000_000
        ) as socket:
            browser.workflow(browser.Page(socket), password)
    finally:
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    main()
