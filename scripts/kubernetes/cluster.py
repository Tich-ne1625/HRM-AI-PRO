"""Create a local cluster without changing the user's current kube context."""

import argparse
import json
import shutil

from common import CLUSTER, OUT, Target, k3d, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["create", "status", "stop", "start", "delete"])
    p.add_argument("--confirm-delete")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.action == "create":
        clusters = json.loads(run([k3d(), "cluster", "list", "-o", "json"]))
        if any(c["name"] == CLUSTER for c in clusters):
            if not (OUT / "cluster-receipt.json").exists():
                raise RuntimeError(
                    "Existing cluster has no ownership receipt; refusing adoption"
                )
        else:
            run(
                [
                    k3d(),
                    "cluster",
                    "create",
                    CLUSTER,
                    "--image",
                    "rancher/k3s:v1.35.5-k3s1",
                    "--servers",
                    "1",
                    "--agents",
                    "0",
                    "--api-port",
                    "127.0.0.1:16443",
                    "--port",
                    "127.0.0.1:13010:80@loadbalancer",
                    "--port",
                    "127.0.0.1:13443:443@loadbalancer",
                    "--k3s-arg",
                    "--disable=metrics-server@server:0",
                    "--kubeconfig-update-default=false",
                    "--kubeconfig-switch-context=false",
                    "--wait",
                    "--timeout",
                    "240s",
                ],
                timeout=300,
            )
            (OUT / "kubeconfig").write_text(
                run([k3d(), "kubeconfig", "get", CLUSTER]), encoding="utf-8"
            )
            (OUT / "kubeconfig").chmod(0o600)
            t = Target()
            t.report(
                "cluster-receipt.json",
                {
                    "name": CLUSTER,
                    "uid": t.json("get", "namespace", "kube-system")["metadata"]["uid"],
                },
            )
    elif a.action in {"start", "stop", "delete"}:
        receipt = json.loads((OUT / "cluster-receipt.json").read_text())
        assert receipt["name"] == CLUSTER
        if a.action != "start":
            assert (
                Target().json("get", "namespace", "kube-system")["metadata"]["uid"]
                == receipt["uid"]
            )
        if a.action == "delete" and a.confirm_delete != CLUSTER:
            raise ValueError(
                "Deletion destroys only the test cluster: explicit --confirm-delete required"
            )
        run([k3d(), "cluster", a.action, CLUSTER])
        if a.action == "delete":
            (OUT / "cluster-receipt.json").unlink()
            (OUT / "kubeconfig").unlink()
    if a.action not in {"stop", "delete"}:
        t = Target()
        print(
            json.dumps(
                {
                    "cluster": CLUSTER,
                    "nodes": [
                        n["metadata"]["name"] for n in t.json("get", "nodes")["items"]
                    ],
                    "docker": run(
                        ["docker", "info", "--format", "{{.ServerVersion}}"]
                    ).strip(),
                    "kubectl": shutil.which("kubectl"),
                }
            )
        )


if __name__ == "__main__":
    main()
