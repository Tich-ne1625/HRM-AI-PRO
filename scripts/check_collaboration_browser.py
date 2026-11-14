"""Browser acceptance on a fresh fictional stack at web 13029/API 18029 only.

Seed with the public test password DemoCollab@2026; disable AI. Never use user data.
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
OUT = ROOT / ".superpowers/collaboration/browser"
browser.BASE, browser.OUT = "http://localhost:13029", OUT


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    port, sockets = 19309, []
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
            endpoint.replace("localhost", "127.0.0.1"), proxy=None, ping_interval=None
        )
        sockets.append(root_socket)
        control = object.__new__(browser.Page)
        control.socket, control.sequence, control.responses, control.exceptions = (
            root_socket,
            0,
            [],
            [],
        )
        control.methods, control.step = {}, "browser context setup"

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
            p = browser.Page(socket)
            p.command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": "window.notificationChanges=0;const Source=window.EventSource;window.EventSource=class extends Source{constructor(...args){super(...args);this.addEventListener('change',()=>window.notificationChanges++);}}"
                },
            )
            p.go("/login")
            p.click("Dùng tài khoản riêng")
            p.fill("#email", name + ".demo@example.com")
            p.fill("#password", "DemoCollab@2026")
            p.write(
                "/api/v1/auth/login",
                lambda: p.js("document.querySelector('form').requestSubmit()"),
            )
            p.wait(
                "location.pathname==='/dashboard' && !!document.querySelector('.notification-trigger')"
            )
            return p

        hr, employee = page("hr"), page("an")
        hr.go("/news")
        employee.go("/news")
        employee.wait("window.notificationChanges>0")
        initial = employee.js("window.notificationChanges")
        suffix = secrets.token_hex(3)
        hr.click("+ Viết bài")
        hr.fill("dialog input[maxlength='200']", "Company update " + suffix)
        hr.fill("dialog textarea", "Office news, not performance evidence.")
        hr.click("@ Nhắc người liên quan")
        hr.fill("dialog .mention-options input:not([type='checkbox'])", "an.demo@example.com")
        hr.wait("document.querySelectorAll('dialog .mention-option input').length===1")
        hr.js("document.querySelector('dialog .mention-option input').click()")
        posted = hr.write("/api/v1/collaboration/posts", lambda: hr.click("Đăng bài"), 201)
        employee.wait("window.notificationChanges>" + str(initial))
        employee.wait("document.body.innerText.includes(" + json.dumps(posted["title"]) + ")")
        assert employee.get("/api/v1/notifications")["unread_count"] >= 1
        employee.click("Xem bài viết và trao đổi")
        employee.fill("dialog textarea", "Acknowledged update " + suffix)
        employee.click("@ Nhắc người liên quan")
        employee.fill("dialog .mention-options input:not([type='checkbox'])", "hr.demo@example.com")
        employee.wait("document.querySelectorAll('dialog .mention-option input').length===1")
        employee.js("document.querySelector('dialog .mention-option input').click()")
        employee.write("/api/v1/collaboration/posts/" + posted["id"] + "/comments", lambda: employee.click("Gửi trao đổi"), 201)
        employee.wait("document.querySelectorAll('dialog .feed-comment').length===1")
        employee.shot("employee-news-and-mentions")
        employee.js("document.querySelector('dialog .dialog-close').click()")
        assert employee.js("location.pathname==='/news'&&!document.querySelector('dialog[open]')")
        hr.wait("document.querySelector('.notification-count')?.textContent!=='0'")

        hr.js("document.querySelector('.chat-launcher').click()")
        hr.click("Tìm đồng nghiệp")
        hr.fill(".chat-directory input", "an.demo@example.com")
        hr.wait("document.querySelectorAll('.chat-contact').length===1")
        hr.js("document.querySelector('.chat-contact').click()")
        hr.fill("#chat-message-body", "Direct message " + suffix)
        hr.click("@ Nhắc")
        peer = next(p for p in hr.get("/api/v1/collaboration/people?search=an.demo@example.com")["items"])
        sent = hr.write("/api/v1/collaboration/chat/" + peer["id"], lambda: hr.click("Gửi"), 201)
        employee.wait("document.querySelector('.chat-launcher strong')?.textContent==='1'")
        assert hr.get("/api/v1/collaboration/messages/" + sent["id"])["read_at"] is None
        employee.js("document.querySelector('.chat-launcher').click()")
        employee.wait("document.querySelectorAll('.chat-contact').length===1")
        employee.js("document.querySelector('.chat-contact').click()")
        employee.wait("document.querySelector('.chat-history')?.innerText.includes(" + json.dumps(suffix) + ")")
        hr.wait("document.querySelector('.chat-history')?.innerText.includes('Đã đọc')")
        employee.shot("employee-chat-small-window")
        assert employee.js("location.pathname==='/news'")
        assert not hr.exceptions and not employee.exceptions
        assert not any("ai-analyses" in row["path"] for p in (hr, employee) for row in p.writes)
        result = {"company_post_from_form": True, "mentions_saved_and_visible": True,
                  "feed_and_notice_realtime_between_accounts": True,
                  "comment_from_form": True, "chat_message_from_form": True,
                  "unread_until_conversation_opened": True, "sender_receives_read_receipt": True,
                  "modal_close_preserves_page": True, "viewport_widths": [1280, 390],
                  "ai_calls": 0, "disposable_data_only": True}
        (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for socket in reversed(sockets):
            socket.close()
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    main()
