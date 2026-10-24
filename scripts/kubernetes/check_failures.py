"""Exercise migration failure and expired-owner/active-Job fences on the test namespace."""

import argparse
import json
import secrets
import time

from common import Target
from deploy import DeployLease, migrate


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--release", required=True)
    a = p.parse_args()
    t = Target()
    revision = t.json("get", "deployment", "api")["metadata"]["generation"]
    config = t.json("get", "configmap", "app-config")
    assert config["data"]["APP_ENV"] == "test"
    original = dict(config["data"])
    with DeployLease(t) as lease:
        config["data"]["COOKIE_SECURE"] = "invalid-boolean-for-negative-test"
        t.call("replace", "-f", "-", body=json.dumps(config))
        try:
            try:
                migrate(t, a.release, lease)
            except RuntimeError as error:
                assert "Migration failed" in str(error)
            else:
                raise AssertionError("Failed migration was reported successful")
        finally:
            config = t.json("get", "configmap", "app-config")
            config["data"] = original
            t.call("replace", "-f", "-", body=json.dumps(config))
    assert t.json("get", "deployment", "api")["metadata"]["generation"] == revision
    name = "migration-fence-test-" + secrets.token_hex(4)
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "labels": {"app": "insighthr-migrate"}},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 120,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "runAsGroup": 10001,
                    },
                    "containers": [
                        {
                            "name": "hold",
                            "image": "insighthr-api:" + a.release,
                            "command": ["python", "-c", "import time; time.sleep(110)"],
                            "resources": {
                                "requests": {"cpu": "10m", "memory": "32Mi"},
                                "limits": {"cpu": "100m", "memory": "64Mi"},
                            },
                        }
                    ],
                }
            },
        },
    }
    t.apply(job)
    try:
        for _ in range(30):
            if t.json("get", "pods", "-l", "job-name=" + name)["items"]:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Fence test pod was not scheduled")
        t.call(
            "wait",
            "--for=condition=Ready",
            "pod",
            "-l",
            "job-name=" + name,
            "--timeout=60s",
        )
        # Expired old holder does not authorize another migration while a Job still exists.
        expired = t.json("get", "lease", "insighthr-deploy")
        expired["spec"]["holderIdentity"] = "dead-test-holder"
        expired["spec"]["renewTime"] = "2000-01-01T00:00:00.000000Z"
        t.call("replace", "-f", "-", body=json.dumps(expired))
        with DeployLease(t) as lease:
            count = len(t.json("get", "jobs")["items"])
            try:
                migrate(t, a.release, lease)
            except RuntimeError as error:
                assert "still active" in str(error)
            else:
                raise AssertionError("Active migration fence bypassed")
            assert len(t.json("get", "jobs")["items"]) == count
    finally:
        t.call("delete", "job", name, "--wait=true")
    t.report(
        "failure-gates.json",
        {
            "status": "passed",
            "failed_migration_stops_before_rollout": True,
            "expired_lease_active_job_denied": True,
            "deployment_generation_unchanged": True,
        },
    )
    print("Migration failure and expired-holder/active-Job fences passed.")


if __name__ == "__main__":
    main()
