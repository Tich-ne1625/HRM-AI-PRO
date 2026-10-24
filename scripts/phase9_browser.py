"""Actual form submissions against ONLY the disposable Phase 9 Compose stack.

Requires websockets and Chrome/Edge. No live Gemini, passwords or cookies in artifacts.
Start with infrastructure/docker/phase9-test.compose.yml; requires a fresh database.
"""

import base64
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".superpowers/sdd/phase-9/browser"
BASE = "http://localhost:13009"
COMPOSE = [
    "docker",
    "compose",
    "--project-name",
    "insighthr-phase9-acceptance",
    "--env-file",
    "infrastructure/docker/phase9.env.example",
    "-f",
    "docker-compose.yml",
    "-f",
    "infrastructure/docker/phase9-test.compose.yml",
]


class Page:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.responses = []
        self.exceptions = []
        self.cookies = {}
        self.methods = {}
        self.writes = []
        self.step = "startup"
        for method in ("Page.enable", "Runtime.enable", "Network.enable"):
            self.command(method)

    def command(self, method, params=None):
        self.sequence += 1
        self.socket.send(
            json.dumps({"id": self.sequence, "method": method, "params": params or {}})
        )
        while True:
            msg = json.loads(self.socket.recv(timeout=30))
            if msg.get("method") == "Network.requestWillBeSent":
                self.methods[msg["params"]["requestId"]] = msg["params"]["request"][
                    "method"
                ]
            if msg.get("method") == "Runtime.exceptionThrown":
                self.exceptions.append(msg["params"]["exceptionDetails"].get("text"))
            if msg.get("method") == "Network.responseReceived":
                response = msg["params"]["response"]
                self.responses.append(
                    {
                        "id": msg["params"]["requestId"],
                        "path": urlsplit(response["url"]).path,
                        "status": response["status"],
                        "headers": response["headers"],
                    }
                )
            if msg.get("id") == self.sequence:
                assert "error" not in msg, f"CDP failed at {self.step}"
                return msg.get("result", {})

    def js(self, expression):
        result = self.command(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        assert "exceptionDetails" not in result, (
            f"Browser evaluation failed at {self.step}"
        )
        return result.get("result", {}).get("value")

    def wait(self, expression):
        for _ in range(150):
            if self.js(expression):
                return
            time.sleep(0.2)
        # Synthetic data only; exclude all input values, password and token fields.
        (OUT / "failure.txt").write_text(
            self.step + "\n" + self.js("document.body.innerText"), encoding="utf-8"
        )
        raise RuntimeError(f"Browser timeout at {self.step}")

    def go(self, path):
        self.step = path
        self.command("Page.navigate", {"url": BASE + path})
        self.wait(
            "location.pathname === "
            + json.dumps(urlsplit(path).path)
            + " && document.readyState === 'complete' && !!document.querySelector('main h1')"
        )

    def fill(self, selector, value):
        self.wait(f"!!document.querySelector({json.dumps(selector)})")
        self.js(
            "document.querySelector("
            + json.dumps(selector)
            + ").closest('details:not([open])')?.querySelector('summary')?.click()"
        )
        self.js(
            "(()=>{const e=document.querySelector(" + json.dumps(selector) + ");"
            "const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:"
            "e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;"
            "Object.getOwnPropertyDescriptor(p,'value').set.call(e,"
            + json.dumps(value)
            + ");"
            "e.dispatchEvent(new Event('input',{bubbles:true}));"
            "e.dispatchEvent(new Event('change',{bubbles:true}));})()"
        )

    def select_label(self, label, value=None):
        expr = (
            "[...document.querySelectorAll('label')].find(e=>e.textContent==="
            + json.dumps(label)
            + ")"
        )
        self.wait(
            f"!!{expr} && document.getElementById({expr}.htmlFor).options.length>1"
        )
        selector = self.js(f"'#'+CSS.escape({expr}.htmlFor)")
        if value is None:
            value = self.js(
                f"[...document.querySelector({json.dumps(selector)}).options].find(o=>o.value&&!o.disabled).value"
            )
        self.fill(selector, value)

    def click(self, text):
        expr = (
            "[...document.querySelectorAll('button')].find(e=>e.textContent==="
            + json.dumps(text)
            + ")"
        )
        self.wait(f"!!{expr} && !{expr}.disabled")
        self.js(expr + ".click()")

    def write(self, path, action, status=200):
        self.step = "UI submit " + path
        before = len(self.responses)
        action()
        for _ in range(150):
            self.js("true")  # Drain network events without issuing an API request.
            matches = [
                r
                for r in self.responses[before:]
                if r["path"] == path
                and self.methods.get(r["id"]) not in ("GET", "OPTIONS")
            ]
            if matches:
                response = matches[0]
                assert response["status"] == status, (self.step, response["status"])
                for _ in range(30):
                    try:
                        body = self.command(
                            "Network.getResponseBody", {"requestId": response["id"]}
                        )["body"]
                        print(json.dumps({"ui": path, "status": status}), flush=True)
                        self.writes.append(
                            {
                                "method": self.methods.get(response["id"]),
                                "path": path,
                                "status": status,
                            }
                        )
                        return json.loads(body) if body else {}
                    except (AssertionError, KeyError):
                        time.sleep(0.1)
            time.sleep(0.2)
        self.wait("false")

    def get(self, path, status=200):
        # Read-only assertions/IDs. Domain writes MUST use form controls above.
        assert path.startswith("/api/v1/")
        result = self.js(
            "fetch(" + json.dumps(path) + ",{cache:'no-store'}).then(async r=>"
            "({status:r.status,data:await r.json()}))"
        )
        assert result["status"] == status, (path, result["status"])
        return result["data"]

    def login(self, role, password):
        self.command("Network.clearBrowserCookies")
        self.go("/login")
        self.fill("#email", f"{role}.phase9@example.com")
        self.fill("#password", password)
        self.write(
            "/api/v1/auth/login",
            lambda: self.js("document.querySelector('form').requestSubmit()"),
        )
        self.wait("location.pathname === '/dashboard'")
        self.cookies[role] = self.command("Network.getAllCookies")["cookies"]

    def switch(self, role, path):
        self.command("Network.clearBrowserCookies")
        self.command("Network.setCookies", {"cookies": self.cookies[role]})
        self.go(path)

    def shot(self, name):
        for width in (1280, 390):
            self.command(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": 1000,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            time.sleep(0.2)
            assert self.js("document.documentElement.scrollWidth<=innerWidth+2"), name
            data = self.command("Page.captureScreenshot", {"format": "png"})["data"]
            (OUT / f"{name}-{width}.png").write_bytes(base64.b64decode(data))
        self.command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )


def workflow(p, password):
    p.login("admin", password)
    p.go("/admin/users")
    for role in ("hr", "manager", "employee"):
        p.fill("#new-email", f"{role}.phase9@example.com")
        p.fill("#initial-password", password)
        p.fill("#new-role", role.upper())
        p.write("/api/v1/users", lambda: p.click("Tạo tài khoản"), 201)
        p.wait("document.querySelector('#new-email').value === ''")
    p.shot("admin-users")
    p.login("hr", password)
    for kind, label in (("departments", "phòng ban"), ("positions", "chức danh")):
        p.go("/" + kind)
        p.fill("#reference-code", "P9")
        p.fill("#reference-name", "Phase 9 Fictional " + kind)
        p.write("/api/v1/" + kind, lambda label=label: p.click("Thêm " + label), 201)
    employees = {}
    for role in ("manager", "employee"):
        p.go("/employees")
        p.click("Thêm nhân viên")
        p.fill("#employee-code", "P9-" + role.upper())
        p.fill("#employee-name", "Phase 9 " + role)
        p.select_label("Phòng ban")
        p.select_label("Chức danh")
        if role == "employee":
            p.fill("#manager-select", employees["manager"])
        p.fill("#linked-email", f"{role}.phase9@example.com")
        p.click("Tìm tài khoản")
        p.click("Liên kết tài khoản này")
        row = p.write("/api/v1/employees", lambda: p.click("Lưu hồ sơ"), 201)
        employees[role] = row["id"]
    p.go("/review-cycles")
    p.fill("#cycle-name", "Phase 9 actual UI workflow")
    p.fill("#cycle-start", "2026-01-01")
    p.fill("#cycle-end", "2026-12-31")
    cycle = p.write("/api/v1/review-cycles", lambda: p.click("Tạo chu kỳ nháp"), 201)[
        "id"
    ]
    p.go("/review-cycles/" + cycle)
    p.wait(
        "[...document.querySelectorAll('label')].some(e=>e.textContent.includes('P9-EMPLOYEE')&&e.querySelector('input[type=checkbox]'))"
    )
    p.js(
        "[...document.querySelectorAll('label')].find(e=>e.textContent.includes('P9-EMPLOYEE')&&e.querySelector('input[type=checkbox]')).querySelector('input').click()"
    )
    p.write(
        f"/api/v1/review-cycles/{cycle}/participants",
        lambda: p.click("Thêm người đã chọn"),
    )
    version = p.get(f"/api/v1/review-cycles/{cycle}")["version"]
    p.wait(
        "document.body.innerText.includes(" + json.dumps(f"Phiên bản {version}") + ")"
    )
    p.click("Kích hoạt chu kỳ")
    p.write(
        f"/api/v1/review-cycles/{cycle}/activate", lambda: p.click("Xác nhận kích hoạt")
    )
    participant = p.get(f"/api/v1/review-cycles/{cycle}/participants")["items"][0]["id"]
    p.click("Đóng chu kỳ")
    p.write(
        f"/api/v1/review-cycles/{cycle}/close",
        lambda: p.click("Xác nhận đóng chu kỳ"),
        409,
    )
    assert p.get(f"/api/v1/review-cycles/{cycle}")["status"] == "ACTIVE"
    p.shot("hr-close-denied-before-finalize")
    p.go("/kpis")
    for selector, value in (
        ("#def-code", "P9"),
        ("#def-name", "Fictional deliveries"),
        ("#def-unit", "items"),
    ):
        p.fill(selector, value)
    p.write("/api/v1/kpis", lambda: p.click("Thêm định nghĩa"), 201)
    kpi_path = f"/employees/{employees['employee']}/kpis?cycle_id={cycle}"
    report_path = f"/employees/{employees['employee']}/performance?cycle_id={cycle}"
    p.go(kpi_path)
    p.click("Chỉnh phân bổ KPI")
    p.click("Thêm P9")
    p.fill("input[id^=target-]", "100")
    p.fill("input[id^=weight-]", "100")
    # Discover exact route from the API helper; no scripted mutation here.
    allocation_path = f"/api/v1/employees/{employees['employee']}/kpis"
    p.write(allocation_path, lambda: p.click("Lưu toàn bộ phân bổ"))
    p.click("Nhập thực tế P9")
    p.fill("input[id^=actual-]", "90")
    actual_id = p.get(allocation_path + f"?cycle_id={cycle}")["items"][0]["id"]
    p.write(f"/api/v1/employee-kpis/{actual_id}", lambda: p.click("Lưu thực tế P9"))
    assignments = []
    for relation in ("SELF", "MANAGER"):
        p.go(f"/feedback-administration?participant_id={participant}&cycle_id={cycle}")
        p.fill("#feedback-relationship", relation)
        p.select_label("Người đánh giá hợp lệ")
        assignments.append(
            p.write(
                "/api/v1/feedback-assignments", lambda: p.click("Giao phản hồi"), 201
            )["id"]
        )
    for role, assignment in zip(("employee", "manager"), assignments, strict=True):
        p.login(role, password)
        p.go("/feedback/" + assignment)
        p.fill("#feedback-rating", "4")
        p.fill(
            "#feedback-comment",
            "Fictional acceptance feedback. No personal information.",
        )
        p.click("Kiểm tra và gửi")
        p.write("/api/v1/feedback", lambda: p.click("Xác nhận gửi một lần"), 201)
    p.go(report_path)
    calculate_path = f"/api/v1/performance/{employees['employee']}/calculate"
    review = p.write(calculate_path, lambda: p.click("Tính điểm hiệu suất"), 201)[
        "review_id"
    ]
    p.wait("document.body.innerText.includes('87.00')")
    p.go(kpi_path)
    p.click("Nhập thực tế P9")
    p.fill("input[id^=actual-]", "80")
    p.write(f"/api/v1/employee-kpis/{actual_id}", lambda: p.click("Lưu thực tế P9"))
    p.go(report_path)
    p.wait("document.body.innerText.includes('Cần tính lại')")
    p.shot("manager-stale")
    p.write(calculate_path, lambda: p.click("Tính lại điểm"))
    p.wait("document.body.innerText.includes('80.00')")
    p.switch("hr", report_path)
    p.click("Chốt kết quả")
    p.wait("!!document.querySelector('.confirmation input[type=checkbox]')")
    p.js("document.querySelector('.confirmation input[type=checkbox]').click()")
    p.write(
        f"/api/v1/reviews/{review}/finalize", lambda: p.click("Xác nhận chốt kết quả")
    )
    p.wait("document.body.innerText.includes('Đã chốt kết quả')")
    # Explicit UI AI generation; only the bind-mounted offline provider can answer.
    for audience in ("PUBLIC", "HR_PRIVATE", "PUBLIC"):
        p.click("Nội bộ HR" if audience == "HR_PRIVATE" else "Tư vấn chung")
        scope = "Nội bộ HR" if audience == "HR_PRIVATE" else "Tư vấn chung"
        p.wait(
            "[...document.querySelectorAll('button[aria-pressed=true]')].some(e=>e.textContent==="
            + json.dumps(scope)
            + ")"
        )
        p.wait(
            "[...document.querySelectorAll('button')].some(e=>e.textContent==='Tạo tư vấn AI'||e.textContent==='Tạo lại tư vấn AI')"
        )
        text = p.js(
            "[...document.querySelectorAll('button')].find(e=>e.textContent==='Tạo tư vấn AI'||e.textContent==='Tạo lại tư vấn AI').textContent"
        )
        p.click(text)
        p.wait(
            "!!document.querySelector('[aria-label=\"Xác nhận tạo tư vấn AI\"] input[type=checkbox]')"
        )
        p.js(
            "document.querySelector('[aria-label=\"Xác nhận tạo tư vấn AI\"] input[type=checkbox]').click()"
        )
        p.write(
            f"/api/v1/performance/{review}/ai-analysis",
            lambda: p.click("Xác nhận tạo tư vấn"),
            201 if audience != "PUBLIC" or text == "Tạo tư vấn AI" else 503,
        )
        p.wait(
            "document.body.innerText.includes("
            + json.dumps(
                "OFFLINE PRIVATE SENTINEL"
                if audience == "HR_PRIVATE"
                else "OFFLINE PUBLIC ADVICE"
            )
            + ")"
        )
    p.shot("hr-ai-quota-preserves-success")
    p.go("/review-cycles/" + cycle)
    p.click("Đóng chu kỳ")
    p.write(
        f"/api/v1/review-cycles/{cycle}/close", lambda: p.click("Xác nhận đóng chu kỳ")
    )
    dashboard = p.get("/api/v1/dashboard?cycle_id=" + cycle)
    assert dashboard["average"] == "80.00" and dashboard["sample_size"] == 1
    p.go("/dashboard?cycle_id=" + cycle)
    p.wait(
        "!!document.querySelector('#dashboard-cycle') && document.querySelector('#dashboard-cycle').options.length>0"
    )
    p.fill("#dashboard-cycle", cycle)
    p.wait("document.body.innerText.includes('80.00')")
    p.shot("hr-dashboard-closed")
    p.go("/ai-reports")
    p.fill("#ai-report-audience", "HR_PRIVATE")
    p.wait(
        "[...document.querySelectorAll('button')].some(e=>e.textContent.startsWith('Xem tư vấn '))"
    )
    p.js(
        "[...document.querySelectorAll('button')].find(e=>e.textContent.startsWith('Xem tư vấn ')).click()"
    )
    p.wait("document.body.innerText.includes('OFFLINE PRIVATE SENTINEL')")
    private_id = p.get("/api/v1/ai-reports?audience=HR_PRIVATE")["items"][0]["id"]
    p.shot("hr-private-detail")
    p.switch("employee", "/ai-reports")
    assert p.get("/api/v1/ai-reports")["total"] == 1
    p.get(f"/api/v1/reviews/{review}/ai-analyses/" + private_id, 404)
    assert not p.js("document.body.innerText.includes('OFFLINE PRIVATE SENTINEL')")
    p.shot("employee-public-only")
    p.switch("admin", "/admin/users")
    p.write(
        "/api/v1/users/"
        + p.get("/api/v1/users")["items"][
            [u["email"] for u in p.get("/api/v1/users")["items"]].index(
                "hr.phase9@example.com"
            )
        ]["id"],
        lambda: p.fill(
            'select[aria-label="Vai trò của hr.phase9@example.com"]', "EMPLOYEE"
        ),
    )
    p.command("Network.clearBrowserCookies")
    p.command("Network.setCookies", {"cookies": p.cookies["hr"]})
    p.command("Page.navigate", {"url": BASE + "/ai-reports"})
    p.wait("document.body.innerText.includes('Chưa có tư vấn đã lưu')")
    assert p.get("/api/v1/auth/me")["role"] == "EMPLOYEE"
    p.get(f"/api/v1/reviews/{review}/ai-analyses/" + private_id, 404)
    assert not p.js("document.body.innerText.includes('OFFLINE PRIVATE SENTINEL')")
    p.shot("hr-role-demoted")
    p.switch("admin", "/admin/users")
    p.wait(
        "!!document.querySelector('button[aria-label=\"Vô hiệu hóa hr.phase9@example.com\"]')"
    )
    p.js(
        "document.querySelector('button[aria-label=\"Vô hiệu hóa hr.phase9@example.com\"]').click()"
    )
    user_id = next(
        u["id"]
        for u in p.get("/api/v1/users")["items"]
        if u["email"] == "hr.phase9@example.com"
    )
    p.write("/api/v1/users/" + user_id, lambda: p.click("Xác nhận vô hiệu hóa"))
    p.command("Network.clearBrowserCookies")
    p.command("Network.setCookies", {"cookies": p.cookies["hr"]})
    p.command("Page.navigate", {"url": BASE + "/ai-reports"})
    p.wait("location.pathname==='/login'")
    assert not p.js("document.body.innerText.includes('OFFLINE PRIVATE SENTINEL')")
    p.shot("revoked-hr-session")
    assert not p.exceptions, p.exceptions
    html = [r for r in p.responses if r["path"] == "/login"][-1]
    headers = {k.lower(): v for k, v in html["headers"].items()}
    assert "'nonce-" in headers["content-security-policy"]
    assert "'unsafe-eval'" not in headers["content-security-policy"]
    result = {
        "status": "passed",
        "roles": ["ADMIN", "HR", "MANAGER", "EMPLOYEE"],
        "form_writes": True,
        "numeric_before": "87.00",
        "numeric_final": "80.00",
        "closed_sample_size": 1,
        "offline_ai_generations": 3,
        "live_gemini_calls": 0,
        "quota_preserves_success": True,
        "private_uuid_denied": True,
        "revoked_session_denied": True,
        "demoted_role_applied_without_logout": True,
        "widths": [1280, 390],
        "runtime_exceptions": 0,
        "nonce_csp_hydrates": True,
    }
    result["writes"] = p.writes
    result["browser"] = p.command("Browser.getVersion")["product"]
    result["commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    (OUT / "failure.txt").unlink(missing_ok=True)
    (OUT / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    boot = subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "app.cli.create_admin",
            "--email",
            "admin.phase9@example.com",
            "--password-stdin",
        ],
        input=password + "\n" + password + "\n",
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )
    assert boot.returncode == 0, (
        "Fresh isolated database and healthy test harness required"
    )
    browser = (
        os.environ.get("PHASE9_BROWSER")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
    )
    if not browser:
        browser = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    process = subprocess.Popen(
        [
            browser,
            "--headless=new",
            "--remote-debugging-port=19249",
            "--remote-allow-origins=http://localhost:19249",
            "--no-first-run",
            "--disable-extensions",
            *(["--no-sandbox"] if os.environ.get("CI") == "true" else []),
            f"--user-data-dir={OUT / ('profile-' + secrets.token_hex(4))}",
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
                    target = next(t for t in json.load(response) if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.25)
        else:
            raise RuntimeError("Test browser did not start")
        with connect(
            target["webSocketDebuggerUrl"], proxy=None, max_size=12_000_000
        ) as socket:
            workflow(Page(socket), password)
    finally:
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    main()
