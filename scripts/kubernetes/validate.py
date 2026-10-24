"""Render and validate both profiles against the isolated API server OpenAPI schema."""

import json

from common import Target
from deploy import render


def main():
    target = Target()
    target.namespace_ready()
    counts = {}
    for mode in ("local-http", "local-https"):
        objects = render(target, mode, "phase10-validation")
        for obj in objects:
            assert obj["kind"] != "Secret"
            if obj["kind"] == "Service":
                assert obj["spec"].get("type", "ClusterIP") == "ClusterIP"
            target.call(
                "apply",
                "--dry-run=server",
                "--validate=strict",
                "-f",
                "-",
                body=json.dumps(obj),
            )
        counts[mode] = len(objects)
    target.report(
        "validation.json",
        {
            "status": "passed",
            "tool": "kubectl server-side strict validation",
            "objects": counts,
        },
    )
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
