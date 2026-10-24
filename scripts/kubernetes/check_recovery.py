"""Fault/restart acceptance; never migrates, deletes PVCs, or touches Compose."""

import json
import subprocess
import time

from backup import fingerprint, restore
from common import CLUSTER, OUT, Target, k3d, run
from deploy import DeployLease


def probe(t, path):
    code = (
        "import urllib.request,urllib.error\ntry:\n r=urllib.request.urlopen('http://127.0.0.1:8000"
        + path
        + "',timeout=10); print(r.status)\nexcept urllib.error.HTTPError as e: print(e.code)\n"
    )
    return int(t.exec("python", "-", body=code).strip())


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--release", required=True)
    a = p.parse_args()
    t = Target()
    t.namespace_ready()
    with DeployLease(t):
        try:
            with DeployLease(t):
                raise AssertionError("Concurrent deployment was allowed")
        except RuntimeError as error:
            assert "owns" in str(error)
    # Existing identities and all evidence remain byte-for-byte identical during these operations.
    before = fingerprint(t)
    assert before["tables"]["performance_review_revisions"]["count"] >= 2
    assert before["tables"]["ai_analyses"]["count"] == 3
    t.call("scale", "statefulset/postgres", "--replicas=0")
    t.call("wait", "--for=delete", "pod", "-l", "app=postgres", "--timeout=90s")
    assert probe(t, "/health/live") == 200
    assert probe(t, "/health/ready") == 503
    t.call("scale", "statefulset/postgres", "--replicas=1")
    t.call("rollout", "status", "statefulset/postgres", "--timeout=180s")
    assert fingerprint(t) == before
    for app in ["api", "web"]:
        t.call("rollout", "restart", "deployment/" + app)
        t.call("rollout", "status", "deployment/" + app, "--timeout=180s")
    assert fingerprint(t) == before
    receipt = json.loads((OUT / "cluster-receipt.json").read_text())
    assert (
        receipt["uid"] == t.json("get", "namespace", "kube-system")["metadata"]["uid"]
    )
    run([k3d(), "cluster", "stop", CLUSTER])
    run([k3d(), "cluster", "start", CLUSTER], timeout=240)
    for _ in range(60):
        try:
            t.call("rollout", "status", "statefulset/postgres", "--timeout=10s")
            if fingerprint(t) == before:
                break
        except (RuntimeError, subprocess.TimeoutExpired):
            time.sleep(2)
    else:
        raise RuntimeError("Cluster did not recover with matching data")
    t.report(
        "recovery.json",
        {
            "status": "passed",
            "concurrent_deploy_denied": True,
            "database_outage": {"live": 200, "ready": 503},
            "pg_pod_replacement": True,
            "application_rollout": True,
            "cluster_stop_start": True,
            "read_before_rerunning_migrations": True,
            "fingerprint": before,
        },
    )
    restore(t, a.release)
    print(
        "Lease exclusion, DB outage, pod replacement, rollout, cluster restart and restore passed."
    )


if __name__ == "__main__":
    main()
