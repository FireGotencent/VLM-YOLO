#!/usr/bin/env python3
"""
HTTPS 开发服务器 — 手机浏览器需要 HTTPS 才能访问摄像头
用法: python mobile/start_https_server.py [端口]  (默认 8443)
"""
import datetime
import http.server
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
WS_PORT = 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(SCRIPT_DIR, "_dev_cert.pem")
KEY_FILE = os.path.join(SCRIPT_DIR, "_dev_key.pem")
TS_CERT_FILE = os.path.join(SCRIPT_DIR, "_ts_cert.pem")
TS_KEY_FILE = os.path.join(SCRIPT_DIR, "_ts_key.pem")


# ---------------------------------------------------------------------------
# 网络工具
# ---------------------------------------------------------------------------

def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def tailscale_ip() -> str | None:
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass
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


# ---------------------------------------------------------------------------
# Tailscale 受信任证书
# ---------------------------------------------------------------------------

def tailscale_cert() -> tuple[str | None, str | None, str | None]:
    """申请 Tailscale MagicDNS 证书，每步打印进度，返回 (hostname, cert, key)"""
    print("[Tailscale] 检查 MagicDNS 证书支持...")
    try:
        status = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if status.returncode != 0:
            print(f"[Tailscale] ✗ tailscale status 失败 (code={status.returncode})")
            if status.stderr.strip():
                print(f"[Tailscale]   stderr: {status.stderr.strip()}")
            return None, None, None

        dns_name = json.loads(status.stdout).get("Self", {}).get("DNSName", "").rstrip(".")
        if not dns_name:
            print("[Tailscale] ✗ 未检测到 MagicDNS 主机名")
            print("[Tailscale]   请到管理后台开启 Magic DNS:")
            print("[Tailscale]   https://login.tailscale.com/admin/dns")
            return None, None, None

        print(f"[Tailscale] ✓ MagicDNS 主机名: {dns_name}")
        print(f"[Tailscale] 正在申请 HTTPS 证书（需要管理后台已开启 HTTPS）...")

        result = subprocess.run(
            ["tailscale", "cert",
             "--cert-file", TS_CERT_FILE,
             "--key-file", TS_KEY_FILE,
             dns_name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"[Tailscale] ✗ 证书申请失败 (code={result.returncode})")
            for line in (result.stderr + result.stdout).strip().splitlines():
                print(f"[Tailscale]   {line}")
            print("[Tailscale]   → 请在管理后台开启 HTTPS 证书功能:")
            print("[Tailscale]     https://login.tailscale.com/admin/dns  (打开 HTTPS)")
            return None, None, None

        if not os.path.exists(TS_CERT_FILE):
            print("[Tailscale] ✗ 命令成功但证书文件未生成，请检查权限")
            return None, None, None

        print(f"[Tailscale] ✓ 证书获取成功 → {TS_CERT_FILE}")
        return dns_name, TS_CERT_FILE, TS_KEY_FILE

    except FileNotFoundError:
        print("[Tailscale] ✗ 未找到 tailscale 命令（Tailscale 是否已安装并在 PATH 中？）")
    except json.JSONDecodeError as e:
        print(f"[Tailscale] ✗ 解析 tailscale status 输出失败: {e}")
    except Exception as e:
        print(f"[Tailscale] ✗ 异常: {type(e).__name__}: {e}")
    return None, None, None


# ---------------------------------------------------------------------------
# 自签名证书生成
# ---------------------------------------------------------------------------

def gen_cert(ips: list[str]) -> bool:
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
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
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
    print(f"证书生成成功，SAN: {', '.join(str(s.value) for s in san_list)}")
    return True


def cert_sans(cert_path: str) -> list[str]:
    """读取证书 SAN 列表"""
    try:
        from cryptography import x509
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns = list(ext.value.get_values_for_type(x509.DNSName))
        ips = [str(ip) for ip in ext.value.get_values_for_type(x509.IPAddress)]
        return dns + ips
    except Exception:
        return []


def cert_expiry(cert_path: str) -> str:
    """读取证书到期日"""
    try:
        from cryptography import x509
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        try:
            return cert.not_valid_after_utc.strftime("%Y-%m-%d %H:%M UTC")
        except AttributeError:
            return cert.not_valid_after.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "未知"


# ---------------------------------------------------------------------------
# HTTPS 服务器
# ---------------------------------------------------------------------------

class HTTPSServer(http.server.HTTPServer):
    """修复 Python stdlib SSL 服务器不发送 close_notify 的问题"""

    def __init__(self, server_address, RequestHandlerClass, ssl_context):
        super().__init__(server_address, RequestHandlerClass)
        self.socket = ssl_context.wrap_socket(self.socket, server_side=True)

    def shutdown_request(self, request):
        try:
            request.unwrap()
        except Exception:
            pass
        super().shutdown_request(request)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    # 由 main() 在启动前设置
    cert_to_serve: str | None = None   # 用于 /install-cert 下载
    cert_file_path: str | None = None  # 用于 /diag 解析
    cert_type: str = "self-signed"     # "tailscale" | "self-signed"
    ts_hostname: str | None = None
    ws_port: int = WS_PORT

    # ------------------------------------------------------------------

    def do_GET(self):
        if self.path in ("/", ""):
            self._redirect("/web_client.html")
            return
        if self.path == "/install-cert":
            self._serve_install_cert()
            return
        if self.path == "/diag":
            self._serve_diag()
            return
        super().do_GET()

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    # ------------------------------------------------------------------

    def _serve_install_cert(self):
        cert = self.__class__.cert_to_serve
        if not cert or not os.path.exists(cert):
            self.send_error(404, "证书文件不存在")
            return
        with open(cert, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-x509-ca-cert")
        self.send_header("Content-Disposition", 'attachment; filename="visionguide-dev.crt"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------

    def _serve_diag(self):
        cls = self.__class__
        host = self.headers.get("Host", "").split(":")[0] or "localhost"
        ws_url = f"wss://{host}:{cls.ws_port}"

        sans = cert_sans(cls.cert_file_path) if cls.cert_file_path else []
        expiry = cert_expiry(cls.cert_file_path) if cls.cert_file_path else "未知"
        host_covered = (
            host in sans
            or host == "localhost"
            or any(s.lstrip("*.") in host for s in sans if s.startswith("*."))
        )

        # 服务端 TCP 探测：检查 WebSocket 端口是否在本机监听
        ws_up = False
        try:
            with socket.create_connection(("127.0.0.1", cls.ws_port), timeout=1.0):
                ws_up = True
        except Exception:
            pass

        def row(label, value, ok=True):
            icon = "✓" if ok else "✗"
            color = "#1a7a1a" if ok else "#b00020"
            return (
                f"<tr><td>{label}</td>"
                f"<td style='color:{color}'><b>{icon}</b> {value}</td></tr>"
            )

        ws_status = (
            f"端口 {cls.ws_port} 监听中"
            if ws_up
            else f"端口 {cls.ws_port} 无响应 — 请运行: python server/main.py"
        )
        rows = "".join([
            row("证书类型",
                "Tailscale 受信任证书" if cls.cert_type == "tailscale" else "自签名证书（浏览器可能拒绝）",
                cls.cert_type == "tailscale"),
            row(f"覆盖 {host}",
                "已覆盖" if host_covered else "未覆盖 — 需要受信任证书",
                host_covered),
            row("证书 SAN",
                ", ".join(sans) if sans else "（无法读取）",
                bool(sans)),
            row("证书有效期", expiry, True),
            row("WebSocket 服务", ws_status, ws_up),
        ])

        if not host_covered:
            hint = (
                "<div class='warn'><b>⚠ 证书不覆盖当前主机名，这是连接失败的原因。</b><br>"
                "请到 <a href='https://login.tailscale.com/admin/dns' target='_blank'>"
                "Tailscale 管理后台</a> 同时开启 <b>Magic DNS</b> 和 <b>HTTPS 证书</b>，"
                "然后重启本服务，系统将自动获取受信任的 Tailscale 证书。</div>"
            )
        elif cls.cert_type == "tailscale":
            hint = (
                "<div class='ok'>✓ 证书配置正常。若 WebSocket 仍无法连接，"
                "请确认 <code>python server/main.py</code> 已启动。</div>"
            )
        else:
            hint = (
                "<div class='warn'>自签名证书 — 手机 Chrome 可能拒绝连接。"
                "建议开启 Tailscale HTTPS 或改用 Firefox。</div>"
            )

        cert_link = (
            "<a href='/install-cert'>下载证书</a> · "
            if cls.cert_type == "self-signed"
            else ""
        )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VisionGuide 连接诊断</title>
<style>
body{{font:14px/1.6 sans-serif;max-width:620px;margin:28px auto;padding:0 16px}}
h2{{margin-bottom:4px}}table{{width:100%;border-collapse:collapse;margin:10px 0}}
td{{padding:7px 10px;border:1px solid #ddd}}td:first-child{{width:150px;background:#f5f5f5;font-weight:bold}}
.warn{{background:#fff3cd;border:1px solid #ffc107;padding:10px 14px;border-radius:4px;margin:10px 0}}
.ok{{background:#d4edda;border:1px solid #28a745;padding:10px 14px;border-radius:4px;margin:10px 0}}
.btn{{padding:8px 16px;background:#007bff;color:#fff;border-radius:4px;border:none;cursor:pointer;font-size:14px}}
#log{{height:90px;overflow-y:auto;background:#111;color:#0f0;padding:8px;border-radius:4px;
      font:12px/1.4 monospace;margin-top:8px;white-space:pre-wrap}}
footer{{font-size:12px;color:#888;margin-top:16px}}
</style></head><body>
<h2>VisionGuide 连接诊断</h2>
<p style="color:#666">当前访问主机：<code>{host}</code></p>
<table>{rows}</table>
{hint}
<h3 style="margin-top:18px">WebSocket 连通性测试</h3>
<p>目标地址：<code id="wsAddr">{ws_url}</code></p>
<button class="btn" onclick="testWS()">▶ 立即测试</button>
<div id="log"></div>
<script>
function log(msg, color) {{
  var el = document.getElementById('log');
  el.textContent += '[' + new Date().toLocaleTimeString() + '] ' + msg + '\\n';
  el.scrollTop = el.scrollHeight;
}}
function testWS() {{
  var url = document.getElementById('wsAddr').textContent.trim();
  log('正在连接 ' + url + ' ...');
  try {{
    var ws = new WebSocket(url);
    var t = setTimeout(function(){{ ws.close(); log('✗ 超时（5s）'); }}, 5000);
    ws.onopen  = function()  {{ clearTimeout(t); log('✓ WebSocket 连接成功！服务端已就绪。'); ws.close(); }};
    ws.onerror = function()  {{ clearTimeout(t); log('✗ 连接失败（证书/防火墙/服务未启动？）'); }};
    ws.onclose = function(e) {{ if (e.code && e.code !== 1000 && e.code !== 1006) log('已关闭 code=' + e.code); }};
  }} catch(e) {{ log('✗ ' + e.message); }}
}}
</script>
<footer>
<a href="/web_client.html">← 返回主页面</a> · {cert_link}刷新本页重新检测
</footer>
</body></html>"""

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------

    def log_message(self, fmt, *args):
        # 显示所有请求，方便排查
        super().log_message(fmt, *args)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    os.chdir(SCRIPT_DIR)

    # ── 1. 优先尝试 Tailscale 受信任证书 ──────────────────────────────
    ts_hostname, ts_cert, ts_key = tailscale_cert()

    if ts_hostname:
        cert_file, key_file = ts_cert, ts_key
        QuietHandler.cert_type = "tailscale"
        QuietHandler.ts_hostname = ts_hostname
        QuietHandler.cert_to_serve = None
    else:
        # ── 2. 降级：自签名证书 ───────────────────────────────────────
        print("[自签名] 将使用自签名证书（Tailscale HTTPS 未启用或申请失败）")
        lan_ip = local_ip()
        ts_ip = tailscale_ip()
        all_ips = [lan_ip]
        if ts_ip and ts_ip != lan_ip:
            all_ips.append(ts_ip)
        if not gen_cert(all_ips):
            sys.exit(1)
        cert_file, key_file = CERT_FILE, KEY_FILE
        QuietHandler.cert_type = "self-signed"
        QuietHandler.cert_to_serve = CERT_FILE

    QuietHandler.cert_file_path = cert_file
    QuietHandler.ws_port = WS_PORT

    # ── 3. 打印证书 SAN，方便确认覆盖范围 ─────────────────────────────
    sans = cert_sans(cert_file)
    if sans:
        print(f"[证书] SAN: {', '.join(sans)}")
        print(f"[证书] 有效期至: {cert_expiry(cert_file)}")

    # ── 4. 启动 HTTPS 服务器 ──────────────────────────────────────────
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert_file, key_file)

    with HTTPSServer(("0.0.0.0", PORT), QuietHandler, ctx) as httpd:
        lan_ip = local_ip()
        ts_ip = tailscale_ip()
        access_ip = ts_ip or lan_ip

        print(f"\n{'='*55}")
        print(f"  HTTPS 服务器已启动（端口 {PORT}）")
        print(f"{'='*55}")
        print(f"  本机:        https://localhost:{PORT}")
        print(f"  局域网:      https://{lan_ip}:{PORT}")
        if ts_ip:
            print(f"  Tailscale:   https://{ts_ip}:{PORT}")
        if ts_hostname:
            print(f"  域名(受信任): https://{ts_hostname}:{PORT}")
        print(f"\n  诊断页面:    https://{access_ip}:{PORT}/diag")
        if ts_hostname:
            print(f"               https://{ts_hostname}:{PORT}/diag")
        print(f"{'='*55}")

        if ts_hostname:
            print("\n✓ Tailscale 证书已加载，手机无需任何操作直接访问。")
            print(f"  WebSocket 地址将自动填为: wss://{ts_hostname}:{WS_PORT}")
        else:
            print(f"\n⚠ 自签名证书模式 — 手机首次访问步骤：")
            print(f"  ① 打开 https://{access_ip}:{PORT}  接受 HTTPS 证书")
            print(f"  ② 打开 https://{access_ip}:{WS_PORT} 接受 WebSocket 端口证书")
            print(f"  ③ 返回主页面点「连接服务端」")
            print(f"\n  Android Chrome 若无「高级」按钮：")
            print(f"    推荐 → 开启 Tailscale HTTPS: https://login.tailscale.com/admin/dns")
            print(f"    备用 → 改用 Firefox（支持用户 CA 证书）")
            print(f"\n  防火墙（管理员身份运行）：")
            print(f"    netsh advfirewall firewall add rule name=\"VG-{PORT}\" "
                  f"dir=in action=allow protocol=TCP localport={PORT}")
            print(f"    netsh advfirewall firewall add rule name=\"VG-{WS_PORT}\" "
                  f"dir=in action=allow protocol=TCP localport={WS_PORT}")

        print(f"\n按 Ctrl+C 停止\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


if __name__ == "__main__":
    main()
