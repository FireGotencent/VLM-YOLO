#!/usr/bin/env python3
"""
HTTPS 开发服务器 — 手机浏览器需要 HTTPS 才能访问摄像头
用法: python mobile/start_https_server.py [端口]  (默认 8443)
"""
import http.server
import ssl
import os
import sys
import socket
import datetime
import ipaddress

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(SCRIPT_DIR, "_dev_cert.pem")
KEY_FILE = os.path.join(SCRIPT_DIR, "_dev_key.pem")


def local_ip() -> str:
    """获取出口局域网 IP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def tailscale_ip() -> str | None:
    """检测本机 Tailscale IP（100.64.0.0/10 段）"""
    try:
        import subprocess
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass

    # 备用：扫描网络接口
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            try:
                n = ipaddress.IPv4Address(addr)
                if n in ipaddress.IPv4Network("100.64.0.0/10"):
                    return addr
            except ValueError:
                pass
    except Exception:
        pass
    return None


def gen_cert(ips: list[str]) -> bool:
    """生成包含所有 IP 的自签名证书"""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print("证书已存在，跳过生成（如需重新生成请删除 _dev_cert.pem / _dev_key.pem）")
        return True

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print("缺少 cryptography 库，请运行: pip install cryptography")
        return False

    print("正在生成自签名证书...")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    for ip in ips:
        try:
            addr = ipaddress.IPv4Address(ip)
            entry = x509.IPAddress(addr)
            if entry not in san_list:
                san_list.append(entry)
        except ValueError:
            pass

    primary = ips[0] if ips else "localhost"
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, primary)])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    san_strs = [str(s.value) for s in san_list]
    print(f"证书生成成功，SAN: {', '.join(san_strs)}")
    return True


class HTTPSServer(http.server.HTTPServer):
    """修复 Python stdlib SSL 服务器不发送 close_notify 的问题"""

    def __init__(self, server_address, RequestHandlerClass, ssl_context):
        super().__init__(server_address, RequestHandlerClass)
        self.socket = ssl_context.wrap_socket(self.socket, server_side=True)

    def shutdown_request(self, request):
        try:
            request.unwrap()  # 发送 TLS close_notify，避免 EOF 错误
        except Exception:
            pass
        super().shutdown_request(request)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/web_client.html")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format, *args):
        code = args[1] if len(args) > 1 else ""
        if str(code) not in ("200", "304", "302"):
            super().log_message(format, *args)


def main():
    lan_ip = local_ip()
    ts_ip = tailscale_ip()

    all_ips = [lan_ip]
    if ts_ip and ts_ip != lan_ip:
        all_ips.append(ts_ip)

    if not gen_cert(all_ips):
        sys.exit(1)

    os.chdir(SCRIPT_DIR)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)

    with HTTPSServer(("0.0.0.0", PORT), QuietHandler, ctx) as httpd:
        print(f"\nHTTPS 服务器已启动")
        print(f"  本机访问:    https://localhost:{PORT}")
        print(f"  局域网访问:  https://{lan_ip}:{PORT}")
        if ts_ip:
            print(f"  Tailscale:   https://{ts_ip}:{PORT}")
        print(f"\n首次访问浏览器会提示证书不受信任：")
        print(f"  Chrome: 点击「高级」→「继续前往（不安全）」")
        print(f"\n按 Ctrl+C 停止\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


if __name__ == "__main__":
    main()
