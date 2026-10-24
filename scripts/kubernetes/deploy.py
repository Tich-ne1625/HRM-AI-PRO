"""Deploy existing application images to the explicitly isolated Phase 10 cluster."""

import argparse
import json
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import yaml
from common import CLUSTER, CONTEXT, ROOT, Target, k3d, run


class DeployLease:
    """CAS Lease plus active Job fence; loss stops further deployment operations."""

    def __init__(self, target):
        self.target = target
        self.holder = secrets.token_hex(12)
        self.stop = threading.Event()
        self.lost = False

    def update(self, acquire=False):
        leases = self.target.json("get", "leases")["items"]
        old = next(
            (x for x in leases if x["metadata"]["name"] == "insighthr-deploy"), None
        )
        now = datetime.now(UTC)
        if old:
            spec = old["spec"]
            until = datetime.fromisoformat(
                spec.get("renewTime", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
            ) + timedelta(seconds=spec.get("leaseDurationSeconds", 60))
            if spec.get("holderIdentity") != self.holder and (
                not acquire or until > now
            ):
                raise RuntimeError("Another deployment owns the namespace Lease")
        obj = {
            "apiVersion": "coordination.k8s.io/v1",
            "kind": "Lease",
            "metadata": {
                "name": "insighthr-deploy",
                "namespace": self.target.namespace,
            },
            "spec": {
                "holderIdentity": self.holder,
                "leaseDurationSeconds": 60,
                "renewTime": now.isoformat(timespec="microseconds").replace(
                    "+00:00", "Z"
                ),
            },
        }
        if old:
            obj["metadata"]["resourceVersion"] = old["metadata"]["resourceVersion"]
        self.target.call(
            "replace" if old else "create", "-f", "-", body=json.dumps(obj)
        )

    def __enter__(self):
        self.update(acquire=True)

        def renew():
            while not self.stop.wait(15):
                try:
                    self.update()
                except Exception:  # noqa: BLE001 -- any renewal uncertainty must fence deployment
                    self.lost = True
                    return

        self.thread = threading.Thread(target=renew, daemon=True)
        self.thread.start()
        return self

    def check(self):
        if self.lost:
            raise RuntimeError("Deployment Lease lost; no further changes allowed")

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=20)
        if not self.lost:
            old = next(
                x
                for x in self.target.json("get", "leases")["items"]
                if x["metadata"]["name"] == "insighthr-deploy"
            )
            if old["spec"].get("holderIdentity") == self.holder:
                old["spec"]["leaseDurationSeconds"] = 1
                old["spec"]["renewTime"] = "2000-01-01T00:00:00.000000Z"
                self.target.call("replace", "-f", "-", body=json.dumps(old))


def render(target, mode, release):
    text = run(
        ["kubectl", "kustomize", ROOT / "infrastructure/kubernetes/overlays" / mode]
    )
    objects = list(yaml.safe_load_all(text))
    for obj in objects:
        obj.setdefault("metadata", {})["namespace"] = target.namespace
        spec = obj.get("spec", {}).get("template", {}).get("spec", {})
        for container in spec.get("containers", []):
            if container["name"] in {"api", "web"}:
                container["image"] = f"insighthr-{container['name']}:{release}"
        assert obj["kind"] != "Secret"
    return objects


def ensure_secrets(t):
    existing = {x["metadata"]["name"] for x in t.json("get", "secrets")["items"]}
    if "database" not in existing:
        password = secrets.token_urlsafe(32)
        t.apply(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "database"},
                "type": "Opaque",
                "stringData": {
                    "POSTGRES_PASSWORD": password,
                    "DATABASE_URL": f"postgresql+psycopg://insighthr:{quote(password, safe='')}@postgres:5432/phase10_acceptance_test",
                },
            }
        )
    if "authentication" not in existing:
        t.apply(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "authentication"},
                "type": "Opaque",
                "stringData": {"AUTH_ACCESS_SECRET": secrets.token_urlsafe(48)},
            }
        )


def migrate(t, release, lease):
    lease.check()
    jobs = t.json("get", "jobs", "-l", "app=insighthr-migrate")["items"]
    if any(j.get("status", {}).get("active", 0) for j in jobs):
        raise RuntimeError(
            "A migration Job is still active; operator must inspect before retry"
        )
    name = "migrate-" + secrets.token_hex(5)
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "labels": {"app": "insighthr-migrate"}},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 180,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "metadata": {"labels": {"app": "insighthr-migrate"}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "runAsGroup": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "migrate",
                            "image": f"insighthr-api:{release}",
                            "imagePullPolicy": "IfNotPresent",
                            "command": ["alembic", "upgrade", "head"],
                            "envFrom": [
                                {"configMapRef": {"name": "app-config"}},
                                {"secretRef": {"name": "database"}},
                                {"secretRef": {"name": "authentication"}},
                            ],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "1", "memory": "384Mi"},
                            },
                        }
                    ],
                },
            },
        },
    }
    t.apply(job)
    for _ in range(90):
        lease.check()
        status = t.json("get", "job", name).get("status", {})
        if status.get("failed"):
            raise RuntimeError(
                "Migration failed; rollout stopped (inspect sanitized Job status)"
            )
        if status.get("succeeded"):
            return name
        time.sleep(2)
    raise RuntimeError("Migration deadline exceeded; rollout stopped")


def deploy(t, mode, release, db_only=False):
    t.namespace_ready()
    with DeployLease(t) as lease:
        ensure_secrets(t)
        objects = render(t, mode, release)
        for obj in objects:
            if (
                obj["kind"] in {"ConfigMap", "StatefulSet"}
                or obj["kind"] == "Service"
                and obj["metadata"]["name"] == "postgres"
            ):
                lease.check()
                t.apply(obj)
        t.call("rollout", "status", "statefulset/postgres", "--timeout=180s")
        if db_only:
            return
        job = migrate(t, release, lease)
        for obj in objects:
            if obj["kind"] not in {"ConfigMap", "StatefulSet"} and not (
                obj["kind"] == "Service" and obj["metadata"]["name"] == "postgres"
            ):
                lease.check()
                # Full server-side validation, not just YAML parsing.
                t.call("apply", "--dry-run=server", "-f", "-", body=json.dumps(obj))
                t.apply(obj)
        for app in ["api", "web"]:
            t.call("rollout", "restart", f"deployment/{app}")
            t.call("rollout", "status", f"deployment/{app}", "--timeout=240s")
            lease.check()
        t.report(
            "deployment.json",
            {
                "namespace": t.namespace,
                "context": CONTEXT,
                "mode": mode,
                "release": release,
                "migration_job": job,
                "status": "ready",
            },
        )
    print(f"Ready: {t.namespace}, {mode}, release {release}", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--namespace", default="insighthr-phase10-acceptance")
    p.add_argument(
        "--mode", choices=["local-http", "local-https"], default="local-http"
    )
    p.add_argument("--release", required=True)
    p.add_argument("--build", action="store_true")
    p.add_argument("--db-only", action="store_true")
    a = p.parse_args()
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", a.release):
        raise ValueError("Release must be a safe immutable image tag")
    t = Target(a.namespace)
    if a.build:
        for app in ["api", "web"]:
            run(
                [
                    "docker",
                    "build",
                    "-f",
                    f"infrastructure/docker/{app}.Dockerfile",
                    "-t",
                    f"insighthr-{app}:{a.release}",
                    "--label",
                    f"org.opencontainers.image.revision={run(['git', 'rev-parse', 'HEAD']).strip()}",
                    ".",
                ],
                timeout=600,
            )
        run(
            [
                k3d(),
                "image",
                "import",
                f"insighthr-api:{a.release}",
                f"insighthr-web:{a.release}",
                "--cluster",
                CLUSTER,
            ],
            timeout=300,
        )
    deploy(t, a.mode, a.release, a.db_only)


if __name__ == "__main__":
    main()
