"""TLS with private trust bundle and correct SNI; never disables verification."""

import argparse
import base64
import http.client
import json
import socket
import ssl
import time
from datetime import UTC, datetime, timedelta

from common import OUT, Target
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from deploy import deploy


def certificate(t):
    OUT.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Phase 10 test CA")])
    now = datetime.now(UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    leaf = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "insighthr.test")])
        )
        .issuer_name(name)
        .public_key(leaf.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("insighthr.test")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    t.apply(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "local-tls"},
            "type": "kubernetes.io/tls",
            "data": {
                "tls.crt": base64.b64encode(
                    cert.public_bytes(serialization.Encoding.PEM)
                ).decode(),
                "tls.key": base64.b64encode(
                    leaf.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption(),
                    )
                ).decode(),
            },
        }
    )
    path = OUT / "test-ca.pem"
    path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    return path


class LocalTLS(http.client.HTTPSConnection):
    def connect(self):
        raw = socket.create_connection(("127.0.0.1", 13443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def check(t, ca):
    context = ssl.create_default_context(cafile=str(ca))
    for _ in range(30):
        connection = LocalTLS("insighthr.test", 13443, context=context, timeout=15)
        try:
            connection.request("GET", "/login")
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                break
        except (ssl.SSLError, OSError):
            pass  # Certificate verification remains enabled on every attempt.
        connection.close()
        time.sleep(1)
    else:
        raise RuntimeError("Verified TLS ingress did not become ready")
    assert response.status == 200
    assert response.getheader("Strict-Transport-Security") == "max-age=31536000"
    assert "'nonce-" in response.getheader("Content-Security-Policy", "")
    connection.close()
    # HTTP ingress + Next proxy enforce real byte counts before JSON parsing.
    results = []
    for chunked in [False, True]:
        c = LocalTLS("insighthr.test", 13443, context=context, timeout=15)
        body = b"x" * 131073
        c.request(
            "POST",
            "/api/v1/auth/login",
            body=[body] if chunked else body,
            encode_chunked=chunked,
            headers={
                "Origin": "https://insighthr.test:13443",
                "Content-Type": "application/json",
                "Host": "insighthr.test",
            },
        )
        r = c.getresponse()
        data = r.read()
        assert r.status == 413, (r.status, data[:100])
        results.append({"chunked": chunked, "status": r.status})
        c.close()
    # A separate temporary account is created via stdin; no existing demo password is read.
    import secrets

    password = secrets.token_urlsafe(24)
    email = "tls-" + secrets.token_hex(4) + "@example.com"
    t.exec(
        "python",
        "-m",
        "app.cli.create_admin",
        "--email",
        email,
        "--password-stdin",
        body=password + "\n" + password + "\n",
    )
    c = LocalTLS("insighthr.test", 13443, context=context, timeout=15)
    c.request(
        "POST",
        "/api/v1/auth/login",
        body=json.dumps({"email": email, "password": password}),
        headers={
            "Origin": "https://insighthr.test:13443",
            "Content-Type": "application/json",
        },
    )
    r = c.getresponse()
    r.read()
    assert r.status == 200, r.status
    cookies = [value for key, value in r.getheaders() if key.lower() == "set-cookie"]
    assert len(cookies) == 3 and all(
        "Secure" in cookie and "SameSite=lax" in cookie for cookie in cookies
    )
    assert sum("HttpOnly" in cookie for cookie in cookies) == 2
    c.close()
    from http.cookies import SimpleCookie

    jar = SimpleCookie()
    for value in cookies:
        jar.load(value)
    cookie_header = "; ".join(f"{name}={m.value}" for name, m in jar.items())
    for origin, csrf, expected in [
        ("https://insighthr.test:13443", None, 403),
        ("https://other.invalid", jar["insighthr_csrf"].value, 403),
        ("https://insighthr.test:13443", jar["insighthr_csrf"].value, 204),
    ]:
        c = LocalTLS("insighthr.test", 13443, context=context, timeout=15)
        headers = {"Origin": origin, "Cookie": cookie_header}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        c.request("POST", "/api/v1/auth/logout", headers=headers)
        response = c.getresponse()
        response.read()
        assert response.status == expected
        c.close()
    t.report(
        "tls-http.json",
        {
            "status": "passed",
            "chain_hostname_verified": True,
            "host": "insighthr.test",
            "secure_cookies": True,
            "hsts_nonce": True,
            "oversize": results,
            "browser_tls_trust_tested": False,
        },
    )
    print(
        "TLS chain/hostname, secure cookies, HSTS, nonce and proxy body limits verified."
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--release", required=True)
    a = p.parse_args()
    t = Target()
    ca = certificate(t)
    deploy(t, "local-https", a.release)
    check(t, ca)


if __name__ == "__main__":
    main()
