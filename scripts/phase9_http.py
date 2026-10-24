"""Verify real byte limits through the isolated web proxy, without credentials."""

import http.client
import json

from phase9_browser import BASE, OUT


def main():
    results = []
    for chunked in (False, True):
        connection = http.client.HTTPConnection("localhost", 13009, timeout=15)
        body = b"x" * 131073
        connection.request(
            "POST",
            "/api/v1/auth/login",
            body=[body[:65536], body[65536:]] if chunked else body,
            headers={"Origin": BASE, "Content-Type": "application/json"},
            encode_chunked=chunked,
        )
        response = connection.getresponse()
        assert response.status == 413, response.status
        data = json.loads(response.read())
        assert data["error"]["code"] == "request_too_large", data["error"]["code"]
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("X-Content-Type-Options") == "nosniff"
        results.append(
            {"chunked": chunked, "bytes": len(body), "status": response.status}
        )
        connection.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.parent / "http.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
