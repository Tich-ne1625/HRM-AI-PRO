"""Record runtime versions/images/status without reading Secret values or pod environments."""

import json
import platform
from importlib.metadata import version

from common import Target, run


def main():
    t = Target()
    pods = t.json("get", "pods")["items"]
    client = json.loads(run(["kubectl", "version", "--client", "-o", "json"]))
    t.report(
        "runtime.json",
        {
            "commit": run(["git", "rev-parse", "HEAD"]).strip(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "tools": {k: version(k) for k in ["PyYAML", "cryptography", "websockets"]},
            "kubectl": client["clientVersion"]["gitVersion"],
            "kustomize": client["kustomizeVersion"],
            "server": t.json("get", "node", "k3d-insighthr-phase10-server-0")["status"][
                "nodeInfo"
            ]["kubeletVersion"],
            "pods": [
                {
                    "name": p["metadata"]["name"],
                    "phase": p["status"]["phase"],
                    "containers": [
                        {
                            "name": c["name"],
                            "image_id": c.get("imageID"),
                            "ready": c.get("ready"),
                            "restarts": c.get("restartCount"),
                        }
                        for c in p["status"].get("containerStatuses", [])
                    ],
                }
                for p in pods
            ],
        },
    )
    print("Sanitized runtime/version/image report saved.")


if __name__ == "__main__":
    main()
