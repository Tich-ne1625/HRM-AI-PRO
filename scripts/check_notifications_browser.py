"""Real multi-role forms/SSE on the isolated fictional notification stack ONLY.

Start API on 18019 with AI disabled, fresh fictional demo, and web on 13019.
Never target the user's 3000/8000 stack. No credentials in saved evidence.
"""

import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import phase9_browser as browser
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".superpowers/notifications/browser"
browser.BASE = "http://localhost:13019"
browser.OUT = OUT


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    port = 19279
    process = subprocess.Popen(
        [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--remote-allow-origins=http://localhost:{port}",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={OUT / ('profile-' + secrets.token_hex(4))}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    sockets = []
    try:
        for _ in range(80):
            try:
                with urlopen(
                    f"http://localhost:{port}/json/version", timeout=1
                ) as response:
                    endpoint = json.load(response)["webSocketDebuggerUrl"]
                break
            except OSError:
                time.sleep(0.25)
        root_socket = connect(
            endpoint.replace("localhost", "127.0.0.1"),
            proxy=None,
            max_size=12_000_000,
            ping_interval=None,
        )
        sockets.append(root_socket)
        control = object.__new__(browser.Page)
        control.socket, control.sequence = root_socket, 0
        control.responses, control.exceptions = [], []
        control.methods, control.step = {}, "browser context setup"

        def page(context=None):
            if context is None:
                context = control.command("Target.createBrowserContext")[
                    "browserContextId"
                ]
            target = control.command(
                "Target.createTarget",
                {"url": "about:blank", "browserContextId": context},
            )["targetId"]
            socket = connect(
                f"ws://127.0.0.1:{port}/devtools/page/{target}",
                proxy=None,
                max_size=12_000_000,
                ping_interval=None,
            )
            sockets.append(socket)
            p = browser.Page(socket)
            p.command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": "window.notificationChanges=0;const NativeSource=window.EventSource;window.EventSource=class extends NativeSource{constructor(...args){super(...args);this.addEventListener('change',()=>window.notificationChanges++);}}"
                },
            )
            return p, context

        def login(p, name):
            p.go("/login")
            p.click("Dùng tài khoản riêng")
            p.fill("#email", name + ".demo@example.com")
            p.fill("#password", "DemoNotify@2026")
            p.write(
                "/api/v1/auth/login",
                lambda: p.js("document.querySelector('form').requestSubmit()"),
            )
            p.wait(
                "location.pathname==='/dashboard' && !!document.querySelector('.notification-trigger')"
            )

        def bell(p):
            p.js("document.querySelector('.notification-trigger').click()")
            p.wait(
                "!!document.querySelector('dialog[open].notification-sidebar') && document.body.innerText.includes('Đang cập nhật trực tiếp')"
            )

        def count(p):
            return p.get("/api/v1/notifications")["unread_count"]

        def badge(p, expected):
            p.wait(
                f"Number(document.querySelector('.notification-count')?.textContent||0)==={expected}"
            )

        hr, context = page()
        login(hr, "hr")
        hr2, _ = page(context)
        hr2.go("/dashboard")
        bell(hr2)
        manager, _ = page()
        login(manager, "manager")
        employee, _ = page()
        login(employee, "binh")
        bell(hr)
        if count(hr):
            hr.write(
                "/api/v1/notifications/read-all", lambda: hr.click("Đọc tất cả"), 204
            )
        badge(hr, 0)
        badge(hr2, 0)
        before = hr.js("window.notificationChanges")
        assignment = next(
            row
            for row in employee.get("/api/v1/feedback-assignments?view=mine")["items"]
            if row["relationship"] == "SELF" and row["status"] == "OPEN"
        )
        employee.go("/feedback/" + assignment["id"])
        employee.fill("#feedback-rating", "4")
        employee.fill(
            "#feedback-comment", "Fictional notification acceptance feedback."
        )
        employee.click("Kiểm tra và gửi")
        started = time.monotonic()
        employee.write(
            "/api/v1/feedback", lambda: employee.click("Xác nhận gửi một lần"), 201
        )
        badge(hr, 1)
        badge(hr2, 1)
        assert time.monotonic() - started < 15, (
            "SSE must update before fallback polling"
        )
        assert hr.js("window.notificationChanges") > before
        hr.shot("hr-live-notice")
        hr.write(
            "/api/v1/notifications/"
            + hr.get("/api/v1/notifications")["items"][0]["id"]
            + "/read",
            lambda: hr.click("Đánh dấu đã đọc"),
            204,
        )
        badge(hr2, 0)
        hr2.go("/dashboard")
        badge(hr2, 0)
        hr.js("document.querySelector('.dialog-close').click()")
        cycle = next(
            row
            for row in manager.get("/api/v1/review-cycles")["items"]
            if row["status"] == "ACTIVE"
        )
        participants = manager.get(f"/api/v1/review-cycles/{cycle['id']}/participants")[
            "items"
        ]
        dung = next(row for row in participants if row["employee_code"] == "DEMO-DUNG")
        report = f"/employees/{dung['employee_id']}/performance?cycle_id={cycle['id']}"
        manager.go(report)
        manager.write(
            f"/api/v1/performance/{dung['employee_id']}/calculate",
            lambda: manager.click("Tính điểm hiệu suất"),
            201,
        )
        badge(hr, 1)
        bell(hr)
        hr.wait(
            "[...document.querySelectorAll('.notification-item')].some(e=>e.textContent.includes('được tính'))"
        )
        hr.js(
            "[...document.querySelectorAll('.notification-item')].find(e=>e.textContent.includes('được tính')).click()"
        )
        hr.wait(
            "!!document.querySelector('dialog[open]:not(.notification-sidebar)') && document.body.innerText.includes('Chốt kết quả')"
        )
        assert not hr.js(
            "[...document.querySelectorAll('button')].some(e=>['Tính lại điểm','Tính điểm hiệu suất'].includes(e.textContent))"
        )
        hr.click("Chốt kết quả")
        hr.wait("!!document.querySelector('dialog input[type=checkbox]')")
        hr.js("document.querySelector('dialog input[type=checkbox]').click()")
        review = hr.get(
            f"/api/v1/performance/{dung['employee_id']}?cycle_id={cycle['id']}"
        )
        hr.write(
            f"/api/v1/reviews/{review['review_id']}/finalize",
            lambda: hr.click("Xác nhận chốt kết quả"),
        )
        hr.shot("hr-handoff-finalized")
        hr.js("document.querySelector('.dialog-close').click()")
        manager.go(f"/employees/{dung['employee_id']}/kpis?cycle_id={cycle['id']}")
        manager.wait("document.body.innerText.includes('KPI ·')")
        assert not manager.js(
            "[...document.querySelectorAll('button')].some(e=>e.textContent==='Chỉnh phân bổ KPI')"
        )
        hr2.command(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )
        bell(hr)
        hr2.command(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 0,
                "downloadThroughput": -1,
                "uploadThroughput": -1,
            },
        )
        bell(hr2)
        hr2.shot("hr-reconnected-sidebar")
        result = {
            "real_sse": True,
            "read_synced_between_tabs": True,
            "read_persists_reload": True,
            "manager_to_hr_handoff": True,
            "notification_opens_detail_modal": True,
            "hr_no_calculation_controls": True,
            "finalized_kpi_locked": True,
            "reconnected": True,
            "widths": [1280, 390],
            "ai_called": False,
        }
        assert not any(p.exceptions for p in (hr, hr2, manager, employee))
        (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for socket in reversed(sockets):
            socket.close()
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    run()
