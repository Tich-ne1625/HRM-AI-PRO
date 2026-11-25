"""Real form acceptance ONLY on the isolated Phase 12 stack (13049/18049)."""

import json
import secrets
import subprocess
import time
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen

import phase9_browser as browser
from check_work_management_browser import click, tab
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".superpowers/phase12/browser"
browser.BASE, browser.OUT = "http://localhost:13049", OUT


def fill_label(page, label, value, *, prefix="dialog"):
    expression = (
        "[...document.querySelectorAll("
        + json.dumps(prefix + " label")
        + ")].find(e=>e.getClientRects().length&&e.textContent==="
        + json.dumps(label)
        + ")"
    )
    page.wait(f"!!{expression}")
    selector = page.js(f"'#'+CSS.escape({expression}.htmlFor)")
    page.wait("!document.querySelector(" + json.dumps(selector) + ").disabled")
    page.fill(selector, value)


def card_button(page, title, button, *, heading="h3"):
    expression = (
        "[...document.querySelectorAll('.work-card')].find(e=>e.querySelector("
        + json.dumps(heading)
        + ")?.textContent==="
        + json.dumps(title)
        + ")"
    )
    expression += (
        "&&[..."
        + expression
        + ".querySelectorAll('button')].find(e=>e.getClientRects().length&&!e.disabled&&e.textContent==="
        + json.dumps(button)
        + ")"
    )
    page.wait(f"!!({expression})")
    page.js(f"({expression}).click()")


def decide(page, path, action, body=""):
    fill_label(page, "Bước cần thực hiện", action)
    if body:
        fill_label(page, "Nhận xét / nội dung quyết định", body)
    click(page, "Xem lại trước khi gửi")
    return page.write(path, lambda: click(page, "Xác nhận gửi"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    port, sockets = 19349, []
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
    try:
        endpoint = None
        for _ in range(80):
            try:
                with urlopen(
                    f"http://localhost:{port}/json/version", timeout=1
                ) as response:
                    endpoint = json.load(response)["webSocketDebuggerUrl"]
                break
            except OSError:
                time.sleep(0.25)
        assert endpoint
        root = connect(
            endpoint.replace("localhost", "127.0.0.1"), proxy=None, ping_interval=None
        )
        sockets.append(root)
        control = object.__new__(browser.Page)
        control.socket, control.sequence, control.responses, control.exceptions = (
            root,
            0,
            [],
            [],
        )
        control.methods, control.step = {}, "setup"

        def page(name):
            context = control.command("Target.createBrowserContext")["browserContextId"]
            target = control.command(
                "Target.createTarget",
                {"url": "about:blank", "browserContextId": context},
            )["targetId"]
            socket = connect(
                f"ws://127.0.0.1:{port}/devtools/page/{target}",
                proxy=None,
                ping_interval=None,
                max_size=12_000_000,
            )
            sockets.append(socket)
            current = browser.Page(socket)
            current.command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": "window.notificationChanges=0;const Source=window.EventSource;window.EventSource=class extends Source{constructor(...args){super(...args);this.addEventListener('change',()=>window.notificationChanges++);}}"
                },
            )
            current.go("/login")
            click(current, "Dùng tài khoản riêng")
            current.fill("#email", f"{name}.demo@example.com")
            current.fill("#password", "1")
            current.write(
                "/api/v1/auth/login",
                lambda: current.js("document.querySelector('form').requestSubmit()"),
            )
            current.wait(
                "location.pathname==='/dashboard'&&!!document.querySelector('.notification-trigger')"
            )
            return current

        manager, owner, hr, admin = (
            page(name) for name in ("care.manager", "care01", "hr", "admin")
        )
        owner.go("/work-management?tab=measurements")
        plan = owner.get("/api/v1/work-management/participants")["items"][0]["plan_id"]
        metrics = owner.get(f"/api/v1/progress/plans/{plan}/goals")
        goal = next(g for g in metrics["goals"] if g["method"] == "SUM")
        before = Decimal(goal["actual"])
        original = owner.get(f"/api/v1/progress/plans/{plan}/snapshots")["items"][0]
        old_snapshot = owner.get(f"/api/v1/progress/snapshots/{original['id']}")
        card_button(owner, goal["name"], "Lập số đo")
        key = "UI-SOURCE-" + secrets.token_hex(4)
        fill_label(owner, "Mã hồ sơ / sự kiện duy nhất", key)
        fill_label(
            owner, f"Giá trị phát sinh riêng của nguồn này ({goal['unit']})", "2"
        )
        fill_label(
            owner,
            "Mô tả bằng chứng và cách đối chiếu",
            "Hai yêu cầu của hồ sơ đã có kiểm tra QA.",
        )
        click(owner, "Xem lại số đo")
        row = owner.write(
            f"/api/v1/progress/goals/{goal['goal_id']}/measurements",
            lambda: click(owner, "Lưu bản khai"),
        )
        path = f"/api/v1/progress/measurements/{row['id']}/actions"
        decide(owner, path, "submit")
        manager.go(f"/work-management?measurement={row['id']}")
        decide(
            manager,
            path,
            "return",
            "Một yêu cầu chưa đạt QA; bổ sung danh sách cụ thể.",
        )
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes('Cần bổ sung')"
        )
        click(owner, "Sửa bản khai / đề nghị điều chỉnh")
        fill_label(
            owner, f"Giá trị phát sinh riêng của nguồn này ({goal['unit']})", "1"
        )
        fill_label(
            owner,
            "Bằng chứng và lý do thay đổi / rút số",
            "Chỉ một yêu cầu đạt QA; đã loại yêu cầu còn thiếu bằng chứng.",
        )
        click(owner, "Xem lại số đo")
        owner.write(
            f"/api/v1/progress/measurements/{row['id']}/draft",
            lambda: click(owner, "Lưu bản khai"),
        )
        decide(owner, path, "submit")
        manager.wait("document.querySelector('dialog')?.innerText.includes('Bản 2')")
        decide(
            manager,
            path,
            "verify",
            "Đã đối chiếu danh sách nguồn, xác nhận một yêu cầu hợp lệ.",
        )
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes('Đã xác minh')"
        )
        owner.js("document.querySelector('dialog .dialog-close').click()")
        owner.wait("!document.querySelector('dialog[open]')")
        current = owner.get(f"/api/v1/progress/plans/{plan}/goals")
        assert (
            Decimal(next(g for g in current["goals"] if g["method"] == "SUM")["actual"])
            == before + 1
        )
        owner.shot("employee-verified-metrics")
        assert owner.get(f"/api/v1/progress/snapshots/{original['id']}") == old_snapshot

        manager.go(f"/work-management?tab=checkins&plan_ref={plan}")
        click(manager, "Lên lịch check-in")
        title = "[UI] Rà soát hỗ trợ " + secrets.token_hex(3)
        fill_label(manager, "Tên buổi rà soát", title)
        click(manager, "Xem lại lịch hẹn")
        meeting = manager.write(
            f"/api/v1/progress/plans/{plan}/checkins",
            lambda: click(manager, "Tạo lịch và thông báo"),
        )
        meeting_path = f"/api/v1/checkins/{meeting['id']}"
        owner.go(f"/work-management?checkin={meeting['id']}")
        fill_label(
            owner, "Nội dung chuẩn bị", "Cần quản lý hỗ trợ xin dữ liệu QA từ đối tác."
        )
        click(owner, "Xem lại phần chuẩn bị")
        owner.write(
            meeting_path + "/preparation",
            lambda: click(owner, "Xác nhận lưu phần chuẩn bị"),
        )
        assert manager.get(meeting_path)["preparations"] == []
        owner.wait(
            "!!document.querySelector('dialog input[type=checkbox]:not(:disabled)')"
        )
        owner.js("document.querySelector('dialog input[type=checkbox]').click()")
        owner.wait("document.querySelector('dialog input[type=checkbox]').checked")
        click(owner, "Xem lại phần chuẩn bị")
        owner.write(
            meeting_path + "/preparation",
            lambda: click(owner, "Xác nhận lưu phần chuẩn bị"),
        )
        manager.wait(
            "document.querySelector('dialog')?.innerText.includes('Cần quản lý hỗ trợ xin dữ liệu QA')"
        )
        decide(manager, meeting_path + "/actions", "open")
        tab(manager, "Biên bản")
        decide(
            manager,
            meeting_path + "/actions",
            "publish",
            "Đã rà soát số có nguồn. Mai Anh hỗ trợ đối tác cung cấp QA để Huy tiếp tục.",
        )
        owner.wait("document.querySelector('dialog')?.innerText.includes('Đã công bố')")
        tab(owner, "Biên bản")
        pinned = owner.get(meeting_path)["snapshot"]
        decide(
            owner,
            meeting_path + "/actions",
            "clarify",
            "Cần làm rõ thời hạn nhận kết quả QA.",
        )
        manager.wait(
            "document.querySelector('dialog')?.innerText.includes('đang chờ quản lý phản hồi')"
        )
        decide(
            manager,
            meeting_path + "/actions",
            "addendum",
            "Mai Anh nhận hỗ trợ trong một ngày; Huy kiểm tra dữ liệu sau khi nhận.",
        )
        owner.wait("document.querySelector('dialog')?.innerText.includes('Phụ lục 1')")
        decide(owner, meeting_path + "/actions", "acknowledge")
        manager.wait(
            "document.querySelector('dialog')?.innerText.includes('Nhân viên đã đọc đúng bản mới nhất')"
        )
        tab(manager, "Hành động")
        click(manager, "Giao hành động hỗ trợ")
        action_title = "Xin kết quả QA đối tác " + secrets.token_hex(3)
        fill_label(manager, "Đầu ra / hỗ trợ cần có", action_title)
        fill_label(manager, "Người chịu trách nhiệm", metrics["manager_id"])
        click(manager, "Xem lại hành động hỗ trợ")
        action = manager.write(
            meeting_path + "/follow-ups",
            lambda: click(manager, "Giao và thông báo người nhận"),
        )
        action_path = f"/api/v1/checkin-actions/{action['id']}/actions"
        decide(manager, action_path, "start", "Đã bắt đầu liên hệ đối tác.")
        decide(manager, action_path, "submit", "Đã nhận kết quả QA và gửi cho Huy.")
        assert not any(
            "complete" in a["actions"]
            for a in manager.get(meeting_path)["followups"]["items"]
            if a["id"] == action["id"]
        )
        tab(owner, "Hành động")
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes("
            + json.dumps(action_title)
            + ")"
        )
        decide(
            owner,
            action_path,
            "complete",
            "Đã nhận đủ QA; xác nhận quản lý hoàn thành hỗ trợ.",
        )
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes('Đã hoàn thành')"
        )
        owner.shot("employee-confirms-manager-support")
        # Correct this run's own source after publishing. This proves a real data
        # change cannot rewrite the pinned check-in, even when the script is rerun.
        owner.go(f"/work-management?measurement={row['id']}")
        click(owner, "Sửa bản khai / đề nghị điều chỉnh")
        fill_label(
            owner, f"Giá trị phát sinh riêng của nguồn này ({goal['unit']})", "2"
        )
        fill_label(
            owner,
            "Bằng chứng và lý do thay đổi / rút số",
            "Đã bổ sung xác nhận QA cho yêu cầu thứ hai của cùng hồ sơ.",
        )
        click(owner, "Xem lại số đo")
        owner.write(
            f"/api/v1/progress/measurements/{row['id']}/draft",
            lambda: click(owner, "Lưu bản khai"),
        )
        decide(owner, path, "submit")
        manager.go(f"/work-management?measurement={row['id']}")
        decide(
            manager, path, "verify", "Đã kiểm tra bản điều chỉnh đầy đủ hai yêu cầu."
        )
        assert owner.get(meeting_path)["snapshot"] == pinned
        owner.go(f"/work-management?checkin={meeting['id']}")
        tab(owner, "Biên bản")
        owner.shot("checkin-pinned-snapshot-and-addendum")
        proof = owner.get(f"/api/v1/progress/snapshots/{pinned['id']}")
        proof_sources = list(proof["sources"]["items"])
        for source_page in range(2, (proof["sources"]["total"] + 19) // 20 + 1):
            proof_sources.extend(
                owner.get(
                    f"/api/v1/progress/snapshots/{pinned['id']}?page={source_page}"
                )["sources"]["items"]
            )
        source_index = next(
            i
            for i, source in enumerate(proof_sources)
            if source["measurement_id"] == row["id"]
        )
        old_source = proof_sources[source_index]
        owner.go(
            f"/work-management?tab=measurements&snapshot={pinned['id']}&plan_ref={plan}"
        )
        owner.wait("!!document.querySelector('dialog .work-card')")
        for number in range(2, source_index // 20 + 2):
            owner.js(
                "[...document.querySelectorAll('dialog button')].find(e=>e.textContent==='Trang sau'&&!e.disabled).click()"
            )
            owner.wait(
                "document.querySelector('dialog')?.innerText.includes("
                + json.dumps(f"Trang {number}")
                + ")"
            )
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes("
            + json.dumps(key)
            + ")"
        )
        owner.js(
            "(()=>{const c=[...document.querySelectorAll('dialog .work-card')].find(e=>e.querySelector('strong')?.textContent.startsWith("
            + json.dumps(key)
            + "));c.querySelector('button').click();})()"
        )
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes("
            + json.dumps(f"Bản nguồn đang đối chiếu: {old_source['number']}")
            + ")"
        )
        assert not owner.js(
            "[...document.querySelectorAll('dialog button')].some(e=>e.textContent==='Sửa bản khai / đề nghị điều chỉnh')"
        )
        owner.shot("exact-historical-source-revision")
        hr.go("/work-management")
        click(hr, "Điều phối số liệu & check-in")
        hr.wait("document.querySelector('dialog')?.innerText.includes('Số đo KPI')")
        hr.shot("hr-coordination-metadata-only")
        hr.get(f"/api/v1/progress/measurements/{row['id']}", 404)
        hr.get(meeting_path, 404)
        admin.get(f"/api/v1/progress/plans/{plan}/goals", 404)
        assert owner.js("window.notificationChanges>0") and manager.js(
            "window.notificationChanges>0"
        )
        assert not any(p.exceptions for p in (owner, manager, hr, admin))
        assert not any(
            w["path"].startswith("/api/v1/ai")
            for p in (owner, manager, hr, admin)
            for w in p.writes
        )
        result = {
            "isolated_demo_only": True,
            "form_measurement_return_edit_resubmit_verify": True,
            "correct_actual_after_verification": True,
            "private_preparation_not_shared": True,
            "form_schedule_publish_clarify_addendum_acknowledge": True,
            "manager_support_employee_confirmation": True,
            "old_snapshots_and_checkin_pin_unchanged": True,
            "exact_historical_revision_readonly": True,
            "hr_metadata_admin_denied": True,
            "realtime_between_accounts": True,
            "viewport_widths": [1280, 390],
            "ai_calls": 0,
        }
        (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for socket in sockets:
            socket.close()
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


if __name__ == "__main__":
    main()
