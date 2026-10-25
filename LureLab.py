#!/usr/bin/env python3
"""
LureLab v1.0 - Phishing Awareness & Security Lab
"""

import os
import re
import sys
import json
import time
import queue
import shutil
import threading
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import http.server
import webbrowser
import socket


# LureLab - Phishing Awareness & Security Lab
# Developer: sudopenmark
# This project is designed for authorized security-awareness testing.
# It records only simulation metadata and intentionally never stores credentials.

# ─── HACKER THEME ──────────────────────────────────────────────────────────────
BG       = "#000000"
FG       = "#00ff41"
FG_DIM   = "#005511"
PANEL    = "#0a0a0a"
ERROR    = "#ff0000"
CYAN     = "#00ffff"
FONT     = ("Courier New", 10, "bold")
FONT_L   = ("Courier New", 12, "bold")
FONT_T   = ("Courier New", 16, "bold")

# ─── TUNNEL PROVIDERS ──────────────────────────────────────────────────────────
def get_cloudflared():
    cf = shutil.which("cloudflared")
    if cf: return cf
    local = Path(__file__).parent / ("cloudflared.exe" if os.name == 'nt' else "cloudflared")
    if local.exists(): return str(local)
    return None

def download_cloudflared(log_callback):
    log_callback("[*] cloudflared not found. Downloading...")
    sys_os = "windows" if os.name == 'nt' else "linux" if sys.platform.startswith("linux") else "darwin"
    import platform
    arch = "amd64" if "64" in platform.machine() else "arm64"
    fname = f"cloudflared-{sys_os}-{arch}"
    if sys_os == "windows": fname += ".exe"
    
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{fname}"
    dest = Path(__file__).parent / ("cloudflared.exe" if sys_os == "windows" else "cloudflared")
    
    try:
        urllib.request.urlretrieve(url, dest)
        if sys_os != "windows": os.chmod(dest, 0o755)
        log_callback(f"[+] Downloaded to {dest}")
        return str(dest)
    except Exception as e:
        log_callback(f"[!] Download failed: {e}")
        return None

# ─── VISUAL SCRAPER & POISONER ─────────────────────────────────────────────────
def build_poison_page(url, out_dir, log_callback, manual_bg=None, manual_logo=None, manual_color=None):
    """Create a local-only security-awareness demo; no credentials are requested or stored."""
    os.makedirs(out_dir, exist_ok=True)
    safe_color = manual_color if re.fullmatch(r"#[0-9a-fA-F]{6}", manual_color or "") else "#0b2c5c"
    payload = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Security Awareness Demo</title>
<style>
body { margin:0; min-height:100vh; display:grid; place-items:center;
       background:COLOR; font-family:system-ui,sans-serif; }
main { max-width:560px; margin:24px; padding:32px; border-radius:12px;
       background:#fff; color:#222; box-shadow:0 10px 30px #0003; }
button { padding:12px 18px; border:0; border-radius:8px;
         background:#1877f2; color:white; font-weight:700; cursor:pointer; }
.note { color:#555; line-height:1.5; }
</style>
</head>
<body><main>
<h1>Security Awareness Demo</h1>
<p>This local demonstration teaches how to recognize suspicious sign-in prompts.</p>
<p class="note">Do not enter a password or other personal information. This page does not collect or transmit credentials.</p>
<button id="demo">Run awareness demo</button>
<p id="result" role="status" aria-live="polite"></p>
<script>
document.getElementById('demo').addEventListener('click', function () {
  document.getElementById('result').textContent =
    'Demo complete: verify the website address and never enter credentials on an untrusted page.';
});
</script>
</main></body></html>"""
    payload = payload.replace("COLOR", safe_color)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(payload)

    success = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Demo complete</title></head><body>
<h1>Awareness demo complete</h1>
<p>No credentials were requested, collected, or transmitted.</p>
</body></html>"""
    with open(os.path.join(out_dir, "success.html"), "w", encoding="utf-8") as f:
        f.write(success)

    log_callback("[+] Local awareness demo generated.")
    return True


# ─── C2 SERVER ─────────────────────────────────────────────────────────────────
class C2Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        self.send_header("bypass-tunnel-reminder", "true")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_POST(self):
        if self.path == "/__capture":
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode('utf-8')
            try:
                parsed = json.loads(data)
                # Never log or retain submitted credential values.
                safe_event = {
                    "event": parsed.get("event", "SIMULATION_EVENT"),
                    "username_entered": bool(parsed.get("username_entered", False)),
                    "password_entered": bool(parsed.get("password_entered", False)),
                    "credentials_stored": False,
                    "site": parsed.get("site", ""),
                    "timestamp": parsed.get("timestamp", "")
                }
                self.server.log_callback(safe_event)
            except Exception:
                self.server.log_callback({
                    "event": "INVALID_SIMULATION_EVENT",
                    "credentials_stored": False
                })
                
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def wait_for_port(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

# ─── GUI APPLICATION ───────────────────────────────────────────────────────────
class HackerHostApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LureLab v1.0")
        self.root.configure(bg=BG)
        self.root.geometry("1100x750")
        
        self.server = None
        self.tunnel_proc = None
        self.data_queue = queue.Queue()
        
        self.manual_bg = None
        self.manual_logo = None
        
        self._build_ui()
        self.root.after(100, self._process_queue)

    def _build_ui(self):
        tk.Label(self.root, text="[ LURELAB - PHISHING AWARENESS LAB ]", fg=FG, bg=BG, font=FONT_T).pack(pady=10)
        
        # Target & Tunnel Row
        f1 = tk.Frame(self.root, bg=BG)
        f1.pack(fill="x", padx=20, pady=5)
        
        tk.Label(f1, text="Target URL:", fg=FG, bg=BG, font=FONT).pack(side="left")
        self.url_var = tk.StringVar()
        tk.Entry(f1, textvariable=self.url_var, bg=PANEL, fg=FG, insertbackground=FG, font=FONT, relief="flat", width=40).pack(side="left", padx=5)
        tk.Button(f1, text="[ PASTE ]", command=self.paste_url, bg=PANEL, fg=CYAN, font=FONT, relief="flat").pack(side="left", padx=5)

        tk.Label(f1, text="Tunnel:", fg=FG, bg=BG, font=FONT).pack(side="left", padx=(15, 5))
        self.tunnel_choice = tk.StringVar(value="Cloudflare")
        ttk.Combobox(f1, textvariable=self.tunnel_choice, values=["Cloudflare", "Pinggy", "Localhost.run", "Serveo"], state="readonly", width=15).pack(side="left", padx=5)

        # Overrides Row
        f2 = tk.Frame(self.root, bg=BG)
        f2.pack(fill="x", padx=20, pady=5)
        
        tk.Button(f2, text="[ UPLOAD BACKGROUND ]", command=self.pick_bg, bg=PANEL, fg=ERROR, font=FONT, relief="flat").pack(side="left", padx=5)
        tk.Button(f2, text="[ UPLOAD LOGO ]", command=self.pick_logo, bg=PANEL, fg=ERROR, font=FONT, relief="flat").pack(side="left", padx=5)
        
        tk.Label(f2, text="Hex Color:", fg=FG, bg=BG, font=FONT).pack(side="left", padx=(15, 5))
        self.manual_color = tk.StringVar()
        tk.Entry(f2, textvariable=self.manual_color, bg=PANEL, fg=FG, insertbackground=FG, font=FONT, relief="flat", width=12).pack(side="left")

        self.btn_run = tk.Button(f2, text="[ START SIMULATION ]", command=self.start_attack, bg=FG_DIM, fg=BG, font=FONT_L, relief="flat", activebackground=FG)
        self.btn_run.pack(side="left", padx=(15, 5))
        
        self.btn_stop = tk.Button(f2, text="[ STOP ]", command=self.stop_all, bg=ERROR, fg=BG, font=FONT_L, relief="flat", activebackground=FG, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        
        # Public URL Row
        f_url = tk.Frame(self.root, bg=BG)
        f_url.pack(fill="x", padx=20, pady=10)
        tk.Label(f_url, text="PUBLIC URL:", fg=CYAN, bg=BG, font=FONT_L).pack(side="left")
        self.public_url = tk.StringVar(value="Waiting for tunnel...")
        self.url_display = tk.Entry(f_url, textvariable=self.public_url, bg=PANEL, fg=CYAN, font=FONT_L, relief="flat", state="readonly")
        self.url_display.pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(f_url, text="[ COPY ]", command=self.copy_url, bg=PANEL, fg=FG, font=FONT, relief="flat").pack(side="left")
        
        # Terminals
        split = tk.Frame(self.root, bg=BG)
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        left_frame = tk.Frame(split, bg=BG)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left_frame, text=">_ Terminal Output", fg=FG, bg=BG, font=FONT).pack(anchor="w")
        self.term = scrolledtext.ScrolledText(left_frame, bg=PANEL, fg=FG, insertbackground=FG, font=FONT, relief="flat")
        self.term.pack(fill="both", expand=True)
        
        right_frame = tk.Frame(split, bg=BG)
        right_frame.pack(side="right", fill="both", expand=True)
        tk.Label(right_frame, text="[!] Simulation Events", fg=ERROR, bg=BG, font=FONT).pack(anchor="w")
        self.data_box = scrolledtext.ScrolledText(right_frame, bg=PANEL, fg=ERROR, insertbackground=ERROR, font=FONT, relief="flat")
        self.data_box.pack(fill="both", expand=True)
        
    def paste_url(self):
        try:
            text = self.root.clipboard_get()
            if text:
                if not text.startswith("http"):
                    text = "https://" + text.strip()
                self.url_var.set(text.strip())
        except: pass

    def copy_url(self):
        url = self.public_url.get()
        if url and url.startswith("http://127.0.0.1:"):
            self.root.clipboard_clear()
            self.root.clipboard_append(url)

    def pick_bg(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png *.jpeg *.webp")])
        if path:
            self.manual_bg = path
            self.log(f"[+] Selected custom background: {os.path.basename(path)}")

    def pick_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.svg")])
        if path:
            self.manual_logo = path
            self.log(f"[+] Selected custom logo: {os.path.basename(path)}")

    def log(self, msg):
        self.data_queue.put(("log", msg))

    def log_data(self, data):
        self.data_queue.put(("data", data))

    def _process_queue(self):
        while not self.data_queue.empty():
            typ, msg = self.data_queue.get()
            if typ == "log":
                self.term.insert("end", str(msg) + "\n")
                self.term.see("end")
            elif typ == "data":
                self.data_box.insert("end", "\n" + "="*40 + "\n")
                self.data_box.insert("end", f"TIME : {datetime.now().strftime('%H:%M:%S')}\n")
                for k, v in msg.items():
                    self.data_box.insert("end", f"{k.upper():<10}: {v}\n")
                self.data_box.insert("end", "="*40 + "\n")
                self.data_box.see("end")
        self.root.after(100, self._process_queue)

    def start_attack(self):
        url = self.url_var.get().strip()
        out_dir = "phish_site"
        port = 8080
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return
            
        if not url.startswith("http"):
            url = "https://" + url
            
        self.term.delete(1.0, "end")
        self.data_box.delete(1.0, "end")
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.public_url.set("Waiting for tunnel...")
        
        threading.Thread(target=self._run_logic, args=(url, out_dir, port), daemon=True).start()

    def _run_logic(self, url, out_dir, port):
        self.log("[*] Starting local security-awareness demo...")
        if not build_poison_page(url, out_dir, self.log, self.manual_bg, self.manual_logo,
                                 self.manual_color.get().strip()):
            self.log("[!] Demo generation failed.")
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            return

        try:
            handler = lambda *args, **kwargs: C2Handler(*args, directory=out_dir, **kwargs)
            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
            self.server.log_callback = self.log_data
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            local_url = f"http://127.0.0.1:{port}"
            self.root.after(0, lambda u=local_url: self.public_url.set(u))
            self.log(f"[+] Local demo available at {local_url}")
            self.log("[i] Public tunneling and credential collection are disabled.")
            webbrowser.open(local_url)
        except Exception as e:
            self.log(f"[!] Local demo server failed to start: {e}")
            self.root.after(0, lambda: self.btn_run.config(state="normal"))

    def _found_url(self, final_url):
        self.log("\n" + "!"*50)
        self.log(f"   SIMULATION URL: {final_url}")
        self.log("!"*50 + "\n")
        self.log("[*] URL copied to clipboard. Opening in browser...")
        
        self.root.after(0, lambda u=final_url: self.public_url.set(u))
        self.root.clipboard_clear()
        self.root.clipboard_append(final_url)
        
        # Open ONLY the tunnel URL
        webbrowser.open(final_url)

    def stop_all(self):
        self.log("[*] Aborting operation...")
        if self.tunnel_proc:
            self.tunnel_proc.terminate()
            self.tunnel_proc = None
        if self.server:
            self.server.shutdown()
            self.server = None
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.manual_bg = None
        self.manual_logo = None

if __name__ == "__main__":
    root = tk.Tk()
    app = HackerHostApp(root)
    root.mainloop()