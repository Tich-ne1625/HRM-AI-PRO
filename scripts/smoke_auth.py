"""Exercise a disposable Compose stack through the web's same-origin API proxy.

Passwords are generated in memory and delivered to bootstrap only through stdin.
Run from repository root; the selected project must already be up and healthy.
"""

import argparse
import json
import secrets
import subprocess
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Browser:
    def __init__(self, base: str, origin: str) -> None:
        self.base = base.rstrip("/")
        self.origin = origin
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, str] | None = None,
        expected: int = 200,
        csrf: bool = True,
    ) -> dict:
        headers = {"Origin": self.origin, "Content-Type": "application/json"}
        if csrf:
            for cookie in self.jar:
                if cookie.name == "insighthr_csrf":
                    headers["X-CSRF-Token"] = cookie.value
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            if response.status != expected:
                raise RuntimeError(f"Unexpected status for {method} {path}: {response.status}")
            raw = response.read()
            return json.loads(raw) if raw else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", required=True)
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--origin", default="http://localhost:3000")
    args = parser.parse_args()
    admin_password, initial, replacement = [secrets.token_urlsafe(24) for _ in range(3)]
    suffix = secrets.token_hex(5)
    admin_email, hr_email = f"admin-{suffix}@example.com", f"hr-{suffix}@example.com"
    bootstrap = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            args.compose_project,
            "--env-file",
            ".env.example",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "app.cli.create_admin",
            "--email",
            admin_email,
            "--password-stdin",
        ],
        input=f"{admin_password}\n{admin_password}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if bootstrap.returncode:
        raise RuntimeError("Compose administrator bootstrap failed")
    admin = Browser(args.base_url, args.origin)
    admin.request(
        "/api/v1/auth/login",
        method="POST",
        body={
            "email": admin_email,
            "password": admin_password,
        },
    )
    cookies = {cookie.name: cookie for cookie in admin.jar}
    assert cookies["insighthr_access"].path == "/"
    assert cookies["insighthr_refresh"].path == "/api/v1/auth/refresh"
    assert cookies["insighthr_csrf"].path == "/"
    assert cookies["insighthr_access"].has_nonstandard_attr("HttpOnly")
    assert cookies["insighthr_refresh"].has_nonstandard_attr("HttpOnly")
    assert not cookies["insighthr_csrf"].has_nonstandard_attr("HttpOnly")
    assert admin.request("/api/v1/auth/me")["role"] == "ADMIN"
    admin.request(
        "/api/v1/users",
        method="POST",
        expected=201,
        body={
            "email": hr_email,
            "password": initial,
            "role": "HR",
        },
    )
    current, other = Browser(args.base_url, args.origin), Browser(args.base_url, args.origin)
    for browser in (current, other):
        browser.request(
            "/api/v1/auth/login",
            method="POST",
            body={
                "email": hr_email,
                "password": initial,
            },
        )
    current.request("/api/v1/users", expected=403)
    current.request("/api/v1/auth/refresh", method="POST", csrf=False, expected=403)
    current.request(
        "/api/v1/auth/change-password",
        method="POST",
        expected=204,
        body={
            "old_password": initial,
            "new_password": replacement,
        },
    )
    other.request("/api/v1/auth/me", expected=401)
    current.request("/api/v1/auth/refresh", method="POST", expected=204)
    stale = Browser(args.base_url, args.origin)
    for cookie in current.jar:
        stale.jar.set_cookie(cookie)
    current.request("/api/v1/auth/logout", method="POST", expected=204)
    stale.request("/api/v1/auth/me", expected=401)
    stale.request("/api/v1/auth/refresh", method="POST", expected=401)
    print(
        "Authentication HTTP smoke passed: "
        "bootstrap, proxy, roles, CSRF, password, refresh, logout."
    )


if __name__ == "__main__":
    main()
