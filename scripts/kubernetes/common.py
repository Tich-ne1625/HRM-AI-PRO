"""Guarded local-cluster operations. No user kubeconfig, .env, or secret logging."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".superpowers/sdd/phase-10"
CONTEXT = "k3d-insighthr-phase10"
CLUSTER = "insighthr-phase10"
NAMESPACES = {
    "insighthr-phase10-acceptance",
    "insighthr-phase10-restore",
    "insighthr-local",
}


def run(args, *, body=None, binary=False, timeout=300):
    result = subprocess.run(
        [str(a) for a in args],
        input=body,
        capture_output=True,
        text=not binary,
        check=False,
        cwd=ROOT,
        timeout=timeout,
    )
    if result.returncode:
        # stderr from configuration/secret failures may contain confidential input.
        raise RuntimeError(
            f"Operation failed ({result.returncode}): {Path(str(args[0])).name} {args[1]}"
        )
    return result.stdout


def k3d():
    return shutil.which("k3d") or str(ROOT / ".superpowers/tools/k3d.exe")


class Target:
    def __init__(self, namespace="insighthr-phase10-acceptance"):
        if namespace not in NAMESPACES:
            raise ValueError("Only isolated Phase 10 namespaces are allowed")
        self.namespace = namespace
        self.config = Path(
            os.environ.get("PHASE10_KUBECONFIG", OUT / "kubeconfig")
        ).resolve()
        self.prefix = [
            "kubectl",
            "--kubeconfig",
            self.config,
            "--context",
            CONTEXT,
            "--namespace",
            namespace,
        ]
        node = self.json("get", "node", "k3d-insighthr-phase10-server-0")
        if node["metadata"]["name"] != "k3d-insighthr-phase10-server-0":
            raise ValueError("Unexpected cluster")

    def call(self, *args, body=None, binary=False, timeout=300):
        return run(self.prefix + list(args), body=body, binary=binary, timeout=timeout)

    def json(self, *args):
        return json.loads(self.call(*args, "-o", "json"))

    def apply(self, obj):
        return self.call("apply", "-f", "-", body=json.dumps(obj))

    def exec(self, *args, body=None, binary=False, workload="deployment/api"):
        return self.call("exec", "-i", workload, "--", *args, body=body, binary=binary)

    def namespace_ready(self):
        names = self.json("get", "namespaces")["items"]
        found = next(
            (n for n in names if n["metadata"]["name"] == self.namespace), None
        )
        if found:
            if (
                found["metadata"].get("labels", {}).get("app.kubernetes.io/part-of")
                != CLUSTER
            ):
                raise ValueError("Namespace is not owned by Phase 10")
        else:
            self.apply(
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {
                        "name": self.namespace,
                        "labels": {"app.kubernetes.io/part-of": CLUSTER},
                    },
                }
            )

    def report(self, name, data):
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
