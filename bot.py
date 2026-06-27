#!/usr/bin/env python3
"""
|System Monitor v0.3.3 | Bale + Telegram
- Full system monitor + live terminal (pty)
- Commands: /term /ad /lock /notif /cam /ss /ip /wifi /vol /restart /bye
- Buttons: all commands + power with confirmation + restart service
"""

import os, sys, time, json, glob, logging, signal, subprocess, uuid, io, pty, select, termios, struct, fcntl, errno
from urllib.request import Request, urlopen
from urllib.error import URLError
import threading, re

# ====== Config ======
BALE_TOKEN  = os.environ.get("BALE_BOT_TOKEN", "0")
BALE_CHAT   = os.environ.get("BALE_CHAT_ID", "0")

TG_TOKEN    = os.environ.get("TG_BOT_TOKEN", "0")
TG_CHAT     = os.environ.get("TG_CHAT_ID", "0")

ALERT_THRESHOLD = int(os.environ.get("ALERT_THRESHOLD", "90"))
INTERVAL_NORMAL = 3
# ====================

if not BALE_TOKEN or not BALE_CHAT or not TG_TOKEN or not TG_CHAT:
    print("[FATAL] Missing environment variables. Check .env file.")
    sys.exit(1)

BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"
TG_API   = f"https://api.telegram.org/bot{TG_TOKEN}/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sysmon-v0.3.3")

RUNNING = True
BALE_OFFSET = 0
TG_OFFSET   = 0
PREV_TOTAL = None
PREV_IDLE  = None
ALERT_BALE_MID = None  # message id of last thermal alert on Bale
ALERT_TG_MID   = None  # message id of last thermal alert on Telegram
THRESHOLD_WAIT = None  # {"platform": str, "msg_id": int, "time": float}

signal.signal(signal.SIGTERM, lambda *_: setattr(sys.modules[__name__], 'RUNNING', False))
signal.signal(signal.SIGINT,  lambda *_: setattr(sys.modules[__name__], 'RUNNING', False))


# ─── API ───

def api_call(base, method, payload, retries=3):
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = Request(f"{base}{method}", data=data,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=7) as r:
                return json.loads(r.read())
        except URLError as e:
            if attempt < retries - 1:
                log.warning(f"{method} ({attempt+1}): {e}")
                time.sleep(1)
    return None


def bale(method, payload):
    return api_call(BALE_API, method, payload)


def tg(method, payload):
    return api_call(TG_API, method, payload)


# ─── Photo upload ───

def send_photo(base, chat_id, file_path, caption=""):
    try:
        boundary = uuid.uuid4().hex
        with open(file_path, "rb") as f:
            file_data = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{chat_id}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(file_path)}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + file_data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        req = Request(f"{base}sendPhoto", data=body,
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"sendPhoto: {e}")
        return None


# ─── Stats collection ───

def get_cpu_temp():
    try:
        zones = sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
        if not zones: return None
        temps = [int(open(p).read().strip()) / 1000.0 for p in zones if open(p).read().strip()]
        return max(temps) if temps else None
    except: return None


def get_cpu_stats():
    global PREV_TOTAL, PREV_IDLE
    try:
        with open("/proc/stat") as f:
            parts = f.readline().strip().split()
        fields = [int(x) for x in parts[1:]]
        # Use ALL fields for total (user + nice + system + idle + iowait + irq + softirq + steal)
        u, n, s, i = fields[0], fields[1], fields[2], fields[3]
        iowait = fields[4] if len(fields) > 4 else 0
        irq = fields[5] if len(fields) > 5 else 0
        sirq = fields[6] if len(fields) > 6 else 0
        steal = fields[7] if len(fields) > 7 else 0
        t = sum(fields)  # total = all fields
        pct = 0.0
        if PREV_TOTAL is not None:
            dtot, didle = t - PREV_TOTAL, i - PREV_IDLE
            if dtot > 0:
                pct = round((1 - didle/dtot)*100, 1)
                pct = max(0, min(100, pct))
        PREV_TOTAL, PREV_IDLE = t, i
        cores = sum(1 for _ in open("/proc/cpuinfo") if _.startswith("processor"))
        lo = open("/proc/loadavg").read().strip().split()
        return {"pct": pct, "cores": cores, "l1": lo[0], "l5": lo[1], "l15": lo[2]}
    except: return None


def get_ram():
    try:
        d = {}
        for l in open("/proc/meminfo"):
            p = l.split()
            if len(p) >= 2: d[p[0].rstrip(":")] = int(p[1])
        def g(k): return round(k/1024/1024, 1)
        t, a = d["MemTotal"], d.get("MemAvailable", d.get("MemFree", 0))
        st, sf = d.get("SwapTotal", 0), d.get("SwapFree", 0)
        return {"t": g(t), "u": g(t-a), "pct": round((t-a)/t*100, 1), "st": g(st), "su": g(st-sf)}
    except: return None


def get_gpu():
    info = {"t": None, "u": None, "n": None}
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,name",
             "--format=csv,noheader,nounits"], timeout=3, stderr=subprocess.DEVNULL).decode(errors="replace").strip()
        if out:
            p = [x.strip() for x in out.split(",")]
            if len(p) >= 3: info["t"], info["u"], info["n"] = float(p[0]), float(p[1]), p[2]
            return info
    except: pass
    try:
        for p in sorted(glob.glob("/sys/class/hwmon/hwmon*/temp*_input")):
            nm = open(os.path.join(os.path.dirname(p), "name")).read().strip().lower()
            if any(k in nm for k in ("amdgpu","radeon","nouveau","i915")):
                info["t"] = float(open(p).read().strip())/1000.0
                info["n"] = nm
                return info
    except: pass
    try:
        ps = sorted(glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/temp*_input"))
        if ps: info["t"] = float(open(ps[0]).read().strip())/1000.0; info["n"] = "GPU"
    except: pass
    return info


def get_procs(limit=5):
    """Return top processes by CPU and by memory usage."""
    result = {"cpu": [], "mem": []}
    try:
        procs = []
        out = subprocess.check_output(["ps", "aux"], timeout=3).decode(errors="replace")
        for l in out.strip().split("\n")[1:]:
            p = l.split(None, 10)
            if len(p) >= 11:
                procs.append({"c": p[2], "m": p[3], "r": p[5], "cmd": p[10][:35]})
        # Sort by CPU
        result["cpu"] = sorted(procs, key=lambda x: float(x["c"]), reverse=True)[:limit]
        # Sort by RSS (memory)
        result["mem"] = sorted(procs, key=lambda x: int(x["r"]) if x["r"].isdigit() else 0, reverse=True)[:limit]
    except:
        pass
    return result


def get_up():
    try:
        s = float(open("/proc/uptime").read().strip().split()[0])
        d, h, m = int(s//86400), int((s%86400)//3600), int((s%3600)//60)
        return " ".join(f"{x}{y}" for x,y in [(d,"d"),(h,"h"),(m,"m")] if x) or "0m"
    except: return "?"


# ─── Widgets ───

def _bar(p, w=10, fill="\u2593", empty="\u2591"):
    f = round(min(p,100)/100*w)
    return f"{fill*f}{empty*(w-f)}"


def _now_ts():
    return time.strftime("%H:%M:%S")


def _thermometer(temp, width=12):
    if temp is None: return f"[{'?'*width}] ?C"
    f = round(min(temp, 100) / 100 * width)
    f = max(0, min(width, f))
    return f"[{'#'*f}{'.'*(width-f)}] {temp:.1f}C"


def _md(text, is_bale):
    """Wrap text in backticks for Telegram, plain for Bale."""
    if is_bale:
        return text
    return f"`{text}`"


def build_text(temp, cpu, ram, gpu, procs, up, update_time="", is_bale=False):
    L, sep = [], "---------------"
    if cpu: L.append(f"System Monitor | {cpu['cores']}C")
    else:   L.append("System Monitor")
    uptime_line = f"Uptime: {up}"
    if update_time:
        uptime_line += f"  |  {update_time}"
    L.append(uptime_line)
    L.append(sep)

    # CPU
    tl = "CPU"
    if temp is not None:
        tl += f"  {_thermometer(temp)}"
    if cpu:
        tl += f"\n  Usage: {_md(str(cpu['pct']) + '%', is_bale)} {_bar(int(cpu['pct']))}"
        tl += f"\n  Load: {_md(cpu['l1'] + ' / ' + cpu['l5'] + ' / ' + cpu['l15'], is_bale)}"
    L.append(tl)
    L.append("")

    # RAM
    if ram:
        L.append(f"RAM  {_md(str(ram['u']) + '/' + str(ram['t']) + 'GB', is_bale)}  {_md(str(ram['pct']) + '%', is_bale)} {_bar(int(ram['pct']))}")
        if ram['st'] > 0:
            sp = round(ram['su']/ram['st']*100) if ram['st'] else 0
            L.append(f"  Swap: {_md(str(ram['su']) + '/' + str(ram['st']) + 'GB', is_bale)}  {_md(str(sp) + '%', is_bale)} {_bar(sp)}")
    L.append("")

    # GPU
    if gpu.get('n') or gpu.get('t') is not None:
        gl = "GPU"
        if gpu.get('n'): gl += f" ({gpu['n'].upper()})"
        items = []
        if gpu['t'] is not None: items.append(f"{gpu['t']:.0f}C")
        if gpu['u'] is not None: items.append(f"{gpu['u']:.0f}%")
        if items: gl += "  " + _md(" | ".join(items), is_bale)
        L.append(gl)

    # Processes
    if (procs.get("cpu") if isinstance(procs, dict) else None):
        L.append("")
        L.append("Top CPU")
        for i, p in enumerate(procs["cpu"], 1):
            rss = round(int(p['r'])/1024, 1) if p['r'].isdigit() else "?"
            cmd_short = p['cmd'][:30]
            L.append(f"  {i}. {cmd_short}")
            L.append(f"     CPU {_md(p['c'] + '%', is_bale)}  MEM {_md(p['m'] + '%', is_bale)} ({rss}MB)")
    if (procs.get("mem") if isinstance(procs, dict) else None):
        L.append("")
        L.append("Top MEM")
        for i, p in enumerate(procs["mem"], 1):
            rss = round(int(p['r'])/1024, 1) if p['r'].isdigit() else "?"
            cmd_short = p['cmd'][:30]
            L.append(f"  {i}. {cmd_short}")
            L.append(f"     CPU {_md(p['c'] + '%', is_bale)}  MEM {_md(p['m'] + '%', is_bale)} ({rss}MB)")
    return "\n".join(L)


# ─── Live Terminal (PTY) ───

TERMINAL_PROC = None  # subprocess
TERMINAL_PID  = None  # pty child pid
TERMINAL_FD   = None  # pty master fd
TERMINAL_BUF  = ""    # output buffer
TERMINAL_PLATFORM = None  # "bale" or "tg"
TERMINAL_TICK = 0
TERM_SHELL = "bash"
TERM_ARGS  = ["--norc", "--noprofile"]

def term_start(platform):
    global TERMINAL_PROC, TERMINAL_PID, TERMINAL_FD, TERMINAL_BUF, TERMINAL_PLATFORM, TERMINAL_TICK

    if TERMINAL_FD is not None:
        return "A terminal is already open. Use /bye first to close it."

    try:
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "dumb"
            os.environ["PS1"] = "> "
            os.execle("/bin/bash", "-bash", "--norc", "--noprofile", os.environ)
            os._exit(1)

        TERMINAL_PID = pid
        TERMINAL_FD = fd
        TERMINAL_BUF = ""
        TERMINAL_PLATFORM = platform
        TERMINAL_TICK = 0

        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        time.sleep(0.5)
        try:
            out = os.read(fd, 4096).decode(errors="replace")
        except:
            pass

        return "Terminal (bash)\nConnected to shell. Send any command to execute.\n/bye to exit."

    except Exception as e:
        log.error(f"term_start: {e}")
        return f"Error: {e}"


def term_send(text):
    global TERMINAL_FD, TERMINAL_BUF, TERMINAL_PID

    if TERMINAL_FD is None:
        return "No terminal open. Use /term to start one."

    if text.strip() == "/bye":
        return term_stop()

    try:
        os.write(TERMINAL_FD, (text + "\n").encode())
        time.sleep(0.7)
        out = ""
        try:
            for _ in range(3):
                r, _, _ = select.select([TERMINAL_FD], [], [], 0.5)
                if r:
                    chunk = os.read(TERMINAL_FD, 4096)
                    if not chunk: break
                    out += chunk.decode(errors="replace")
                else:
                    break
        except: pass

        TERMINAL_BUF += out
        if len(TERMINAL_BUF) > 5000:
            TERMINAL_BUF = TERMINAL_BUF[-3000:]

        display = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][0-9;]*[^\x07]*\x07|\x1b[^\\[].', '', TERMINAL_BUF[-2000:])
        display = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', display).strip()
        return f"Terminal\n\n{display[:2000]}"

    except Exception as e:
        log.error(f"term_send: {e}")
        return f"Error: {e}"


def term_stop():
    global TERMINAL_FD, TERMINAL_PID, TERMINAL_BUF, TERMINAL_PLATFORM

    if TERMINAL_FD is None:
        return "No terminal open."

    try:
        if TERMINAL_PID:
            os.kill(TERMINAL_PID, signal.SIGKILL)
            os.waitpid(TERMINAL_PID, 0)
    except: pass

    try:
        if TERMINAL_FD is not None:
            os.close(TERMINAL_FD)
    except: pass

    TERMINAL_FD = None
    TERMINAL_PID = None
    TERMINAL_BUF = ""
    TERMINAL_PLATFORM = None

    return "Terminal closed."


def term_is_active():
    return TERMINAL_FD is not None


# ─── Keyboard ───

def kb(mode="stats"):
    k = {"inline_keyboard": []}
    if mode == "stats":
        k["inline_keyboard"] = [
            [
                {"text": "AnyDesk", "callback_data": "ad"},
                {"text": "Lock", "callback_data": "lock"},
            ],
            [
                {"text": "Webcam", "callback_data": "cam"},
                {"text": "Screenshot", "callback_data": "ss"},
            ],
            [
                {"text": "IP", "callback_data": "ip"},
                {"text": "WiFi", "callback_data": "wifi"},
            ],
            [
                {"text": "Vol 0%", "callback_data": "vol_0"},
                {"text": "Vol 100%", "callback_data": "vol_100"},
            ],
            [
                {"text": "Change Threshold", "callback_data": "change_threshold"},
                {"text": "Reset 90C", "callback_data": "reset_threshold"},
            ],
            [
                {"text": "Restart Bot", "callback_data": "restart_svc"},
            ],
            [
                {"text": "Reboot", "callback_data": "reboot"},
                {"text": "Shutdown", "callback_data": "shutdown"},
                {"text": "Sleep", "callback_data": "sleep"},
            ],
        ]
    return k


def edit_both(text, keyboard, bale_mid, tg_mid):
    global BALE_MID, TG_MID
    threads = []
    if bale_mid:
        def _eb_bale():
            global BALE_MID
            BALE_MID = _safe_edit("bale", BALE_CHAT, bale_mid, text, keyboard)
        threads.append(threading.Thread(target=_eb_bale))
    if tg_mid:
        def _eb_tg():
            global TG_MID
            TG_MID = _safe_edit("tg", TG_CHAT, tg_mid, text, keyboard)
        threads.append(threading.Thread(target=_eb_tg))
    for t in threads: t.start()
    for t in threads: t.join()


def send_text(platform, text):
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    return api_call(base, "sendMessage", {
        "chat_id": chat, "text": text, "parse_mode": "Markdown"})


def delete_msg(platform, msg_id):
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    return api_call(base, "deleteMessage", {
        "chat_id": chat, "message_id": msg_id})


def _safe_edit(platform, chat_id, msg_id, text, keyboard):
    """Try to edit existing message. If it fails, send a new one and return the new msg_id.
    
    Strategy:
    1. Try editMessageText WITH reply_markup (atomic — no flicker, works on Telegram).
    2. If that fails, try WITHOUT reply_markup + Markdown (Bale-compatible text edit).
    3. If text edit succeeded, set keyboard separately via editMessageReplyMarkup.
    4. If all fails, send a new message.
    """
    base = BALE_API if platform == "bale" else TG_API

    # Step 1: try atomic edit (text + keyboard together — Telegram)
    r = api_call(base, "editMessageText", {
        "chat_id": chat_id, "message_id": msg_id,
        "text": text, "parse_mode": "Markdown",
        "reply_markup": keyboard})
    if r and r.get("ok"):
        return msg_id

    # Step 2: failed — try text-only (no keyboard, works on Bale)
    r = api_call(base, "editMessageText", {
        "chat_id": chat_id, "message_id": msg_id,
        "text": text, "parse_mode": "Markdown"})
    if not r or not r.get("ok"):
        # Try without Markdown too
        r = api_call(base, "editMessageText", {
            "chat_id": chat_id, "message_id": msg_id,
            "text": text})

    if r and r.get("ok"):
        # Text edit worked — set keyboard separately
        if keyboard:
            api_call(base, "editMessageReplyMarkup", {
                "chat_id": chat_id, "message_id": msg_id,
                "reply_markup": keyboard})
        return msg_id

    # Step 4: completely failed — send new message
    r = api_call(base, "sendMessage", {
        "chat_id": chat_id, "text": text,
        "parse_mode": "Markdown", "reply_markup": keyboard})
    if r and r.get("ok"):
        new_id = r["result"]["message_id"]
        log.warning(f"{platform} edit failed, sent new message {new_id}")
        return new_id
    return msg_id


# ─── Commands ───

def cmd_ad():
    for cmd in ["/var/lib/flatpak/exports/bin/com.anydesk.Anydesk", "/usr/bin/anydesk"]:
        if os.path.exists(cmd):
            subprocess.Popen([cmd]); return "AnyDesk launched."
    try:
        subprocess.Popen(["flatpak", "run", "com.anydesk.Anydesk"]); return "AnyDesk launched."
    except: return "AnyDesk is not installed."

def cmd_lock():
    subprocess.run(["loginctl", "lock-sessions"], timeout=5); return "Screen locked."

def cmd_notif(text):
    if not text.strip(): return "Usage: /notif <message>"
    subprocess.run(["notify-send", "System Monitor", text], timeout=5); return "Notification sent."

def cmd_cam():
    path = "/tmp/bot_webcam.jpg"
    try:
        subprocess.run(["ffmpeg", "-f", "v4l2", "-video_size", "640x480", "-i", "/dev/video0",
            "-frames:v", "1", "-q:v", "5", "-y", path], timeout=10, capture_output=True)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return ("PHOTO", path, "Webcam")
        return "Webcam capture failed."
    except Exception as e: return f"Error: {e}"

def cmd_ss():
    path = "/tmp/bot_screenshot.jpg"
    try:
        from Xlib import display, X
        d = display.Display(os.environ.get("DISPLAY", ":1"))
        root = d.screen().root; geom = root.get_geometry()
        raw = root.get_image(0, 0, geom.width, geom.height, X.ZPixmap, 0xffffffff)
        from PIL import Image
        img = Image.frombytes("RGB", (geom.width, geom.height), raw.data, "raw", "BGRX")
        img.save(path, "JPEG", quality=80); d.close()
        if os.path.exists(path) and os.path.getsize(path) > 100: return ("PHOTO", path, "Screenshot")
        return "Screenshot failed."
    except Exception as e: return f"Error: {e}"

def cmd_ip():
    private = "?"
    try: private = subprocess.check_output(["hostname", "-I"], timeout=5).decode().strip().replace(" ", "\n")
    except: pass
    public = "?"
    try: public = urlopen(Request("https://api.ipify.org"), timeout=5).read().decode().strip()
    except: pass
    return f"IP Address\n---------------\nPrivate:\n{private}\n\nPublic:\n{public}"

def cmd_wifi():
    try:
        out = subprocess.check_output(["nmcli", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], timeout=10).decode(errors="replace").strip()
        lines = out.split("\n")
        if len(lines) <= 1: return "No WiFi networks found."
        result = ["WiFi Networks", "---------------"]
        for line in lines[1:]:
            parts = line.split(None, 2)
            if len(parts) >= 2:
                bars = int(parts[1])//20 if parts[1].isdigit() else 0
                result.append(f"{parts[0][:25]:25} {'####'[:bars]+'.'*(4-bars)} {parts[1]}%")
        return "\n".join(result)
    except: return "Error scanning WiFi."

def cmd_vol(level_str):
    try:
        level = max(0, min(100, int(level_str)))
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], timeout=5, stderr=subprocess.DEVNULL)
        return f"Volume set to {level}%."
    except: return "Invalid number."


def cmd_restart_service():
    """Restart the bale-cpu-alert systemd service."""
    try:
        subprocess.run(["systemctl", "--user", "restart", "bale-cpu-alert"], timeout=10)
        return "Bot service restarting..."
    except Exception as e:
        return f"Restart failed: {e}"


# ─── Command handler ───

def handle_command(platform, text, chat_id):
    global ALERT_THRESHOLD, THRESHOLD_WAIT
    text = text.strip()

    # Threshold input mode: intercept non-command messages
    if THRESHOLD_WAIT and THRESHOLD_WAIT["platform"] == platform:
        if not text.startswith("/"):
            try:
                val = int(text)
                if 0 <= val <= 110:
                    old = ALERT_THRESHOLD
                    ALERT_THRESHOLD = val
                    delete_msg(platform, THRESHOLD_WAIT["msg_id"])
                    THRESHOLD_WAIT = None
                    return ("text", f"Thermal threshold changed: {old}C -> {val}C")
                else:
                    return ("text", "Value must be between 0 and 110.")
            except ValueError:
                return ("text", "Please enter a valid number (0-110) or /cancel to abort.")

    if text == "/cancel":
        if THRESHOLD_WAIT:
            delete_msg(platform, THRESHOLD_WAIT["msg_id"])
            THRESHOLD_WAIT = None
            return ("text", "Cancelled.")
        return ("text", "Nothing to cancel.")

    if text == "/start":
        return ("text", "System Monitor v0.3 is running.\n\n"
                "/term - Live terminal\n"
                "/notif <text> - Desktop notification\n"
                "/vol <0-100> - Set volume\n"
                "/restart - Restart bot service\n"
                "/cancel - Cancel pending action\n\n"
                "More buttons below.")

    # Terminal
    if text in ("/term", "/terminal", ".term", ".terminal", "/ter"):
        return ("text", term_start(platform))

    if text == "/bye" or text == ".bye":
        if term_is_active():
            return ("text", term_stop())
        return ("text", "No terminal open.")

    if term_is_active():
        return ("text", term_send(text))

    # Regular commands
    if text in ("/ad", ".ad"): return ("text", cmd_ad())
    if text in ("/lock", ".lock"): return ("text", cmd_lock())
    if text.startswith("/notif "): return ("text", cmd_notif(text[7:]))
    if text == "/notif": return ("text", cmd_notif(""))
    if text in ("/cam", ".cam"): return cmd_cam()
    if text in ("/ss", ".ss", "/screenshot"): return cmd_ss()
    if text in ("/ip", ".ip"): return ("text", cmd_ip())
    if text in ("/wifi", ".wifi"): return ("text", cmd_wifi())
    if text.startswith("/vol "): return ("text", cmd_vol(text[5:]))
    if text in ("/restart", ".restart"): return ("text", cmd_restart_service())

    if text.startswith("/"): return ("text", f"Unknown command: {text.split()[0]}\nType /start for help.")
    return None


# ─── Callback handler ───

def handle_cb(platform, cq_id, data, from_id, bale_mid, tg_mid, cq_msg_id):
    """Returns (new_mode, alt_text, delete_confirm_id)"""
    global THRESHOLD_WAIT, ALERT_THRESHOLD
    plat_chat = BALE_CHAT if platform == "bale" else TG_CHAT

    if str(from_id) != str(plat_chat):
        ans = {"callback_query_id": cq_id, "text": "Access denied."}
        if platform == "bale": bale("answerCallbackQuery", ans)
        else: tg("answerCallbackQuery", ans)
        return None, None, None

    def ack(txt):
        ans = {"callback_query_id": cq_id, "text": txt}
        if platform == "bale": bale("answerCallbackQuery", ans)
        else: tg("answerCallbackQuery", ans)

    # Power buttons: send a new confirmation message
    if data == "reboot":
        ack("Confirming reboot...")
        r = send_text(platform, "Are you sure?\nComputer will reboot.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "Are you sure?\nComputer will reboot.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Yes", "callback_data": "do_reboot"},
                    {"text": "No", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    if data == "shutdown":
        ack("Confirming shutdown...")
        r = send_text(platform, "Are you sure?\nComputer will shut down.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "Are you sure?\nComputer will shut down.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Yes", "callback_data": "do_shutdown"},
                    {"text": "No", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    if data == "sleep":
        ack("Confirming sleep...")
        r = send_text(platform, "Are you sure?\nComputer will go to sleep.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "Are you sure?\nComputer will go to sleep.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Yes", "callback_data": "do_sleep"},
                    {"text": "No", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    # Confirmation buttons
    if data == "cancel":
        ack("Cancelled.")
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "stats", None, None

    if data == "do_reboot":
        ack("Rebooting...")
        msg = "Rebooting...\nSystem will be back shortly."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "reboot"])
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    if data == "do_shutdown":
        ack("Shutting down...")
        msg = "Shutting down..."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "poweroff"])
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    if data == "do_sleep":
        ack("Going to sleep...")
        msg = "Going to sleep..."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "suspend"])
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    # Command buttons
    if data == "ad":
        txt = cmd_ad(); ack(txt); return None, None, None
    if data == "lock":
        txt = cmd_lock(); ack(txt); return None, None, None
    if data == "cam":
        ack("Capturing...")
        r = cmd_cam(); send_cmd_response(platform, r); return None, None, None
    if data == "ss":
        ack("Taking screenshot...")
        r = cmd_ss(); send_cmd_response(platform, r); return None, None, None
    if data == "ip":
        ack("Fetching IP...")
        send_cmd_response(platform, ("text", cmd_ip())); return None, None, None
    if data == "wifi":
        ack("Scanning...")
        send_cmd_response(platform, ("text", cmd_wifi())); return None, None, None
    if data.startswith("vol_"):
        level = data.split("_")[1]; txt = cmd_vol(level); ack(txt); return None, None, None
    if data == "restart_svc":
        ack("Restarting service...")
        txt = cmd_restart_service()
        send_cmd_response(platform, ("text", txt))
        return None, None, None

    # Change threshold
    if data == "change_threshold":
        ack("Setting threshold...")
        plat_chat = BALE_CHAT if platform == "bale" else TG_CHAT
        r = api_call(BALE_API if platform == "bale" else TG_API,
                     "sendMessage", {
                         "chat_id": plat_chat,
                         "text": f"Current thermal threshold: {ALERT_THRESHOLD}C\n\nEnter new threshold (0-110):",
                         "parse_mode": "Markdown",
                         "reply_markup": {"inline_keyboard": [[
                             {"text": "Cancel", "callback_data": "cancel_threshold"},
                         ]]}})
        if r and r.get("ok"):
            THRESHOLD_WAIT = {
                "platform": platform,
                "msg_id": r["result"]["message_id"],
                "time": time.time()
            }
        return None, None, None

    if data == "cancel_threshold":
        ack("Cancelled.")
        if THRESHOLD_WAIT:
            delete_msg(THRESHOLD_WAIT["platform"], THRESHOLD_WAIT["msg_id"])
            THRESHOLD_WAIT = None
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "stats", None, None

    if data == "reset_threshold":
        old = ALERT_THRESHOLD
        ALERT_THRESHOLD = 90
        # Cancel any pending threshold input
        if THRESHOLD_WAIT:
            delete_msg(THRESHOLD_WAIT["platform"], THRESHOLD_WAIT["msg_id"])
            THRESHOLD_WAIT = None
        ack(f"Threshold reset: {old}C -> 90C")
        return None, None, None

    return None, None, None


# ─── Polling ───

def poll_platform(platform, offset):
    fn = bale if platform == "bale" else tg
    updates = fn("getUpdates", {"offset": offset})
    if not updates or not updates.get("ok") or not updates["result"]:
        return offset, None, None, [], None

    new_offset = offset
    new_mode = None
    alt_text = None
    cmds = []
    cq_msg_id = None

    for upd in updates["result"]:
        uid = upd["update_id"]

        cq = upd.get("callback_query")
        if cq:
            new_offset = uid + 1
            cq_msg_id = cq.get("message", {}).get("message_id", None)
            mode, alt, _ = handle_cb(
                platform,
                cq.get("id", ""),
                cq.get("data", ""),
                cq.get("from", {}).get("id", 0),
                BALE_MID, TG_MID,
                cq_msg_id)
            if mode:
                new_mode = mode
                alt_text = alt

        msg = upd.get("message")
        if msg and msg.get("text"):
            chat_id = msg.get("chat", {}).get("id", "")
            text = msg["text"]
            expected = BALE_CHAT if platform == "bale" else TG_CHAT
            if str(chat_id) == str(expected):
                new_offset = uid + 1
                result = handle_command(platform, text, chat_id)
                if result:
                    cmds.append(result)

    return new_offset, new_mode, alt_text, cmds, cq_msg_id


# ─── Send command response ───

def send_cmd_response(platform, result):
    if result is None: return
    typ = result[0]
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    if typ == "text":
        api_call(base, "sendMessage", {"chat_id": chat, "text": result[1], "parse_mode": "Markdown"})
    elif typ == "PHOTO":
        send_photo(base, chat, result[1], result[2])


# ─── Initial send ───

BALE_MID = None
TG_MID   = None

def send_initial_platform(bale_text, tg_text):
    global BALE_MID, TG_MID
    r = bale("sendMessage", {"chat_id": BALE_CHAT, "text": bale_text,
        "parse_mode": "Markdown", "reply_markup": kb("stats")})
    if r and r.get("ok"):
        BALE_MID = r["result"]["message_id"]
        log.info(f"Bale message ID: {BALE_MID}")
    else:
        log.error("Failed to send initial message to Bale!")
        sys.exit(1)
    r = tg("sendMessage", {"chat_id": TG_CHAT, "text": tg_text,
        "parse_mode": "Markdown", "reply_markup": kb("stats")})
    if r and r.get("ok"):
        TG_MID = r["result"]["message_id"]
        log.info(f"Telegram message ID: {TG_MID}")
    else:
        log.error("Failed to send initial message to Telegram!")
        sys.exit(1)
    log.info("Both platforms connected.")


# ─── Thermal alerts (separate messages) ───

def _handle_thermal_alerts(cpu_temp, gpu_info):
    """Check temps every cycle. Send alert if hot, delete if cooled down."""
    global ALERT_BALE_MID, ALERT_TG_MID

    # Suppress thermal alerts while user is changing threshold
    if THRESHOLD_WAIT is not None:
        return

    hot_parts = []
    if cpu_temp is not None and cpu_temp >= ALERT_THRESHOLD:
        hot_parts.append(("CPU", cpu_temp))
    gpu_temp = gpu_info.get("t")
    if gpu_temp is not None and gpu_temp >= ALERT_THRESHOLD:
        gpu_name = gpu_info.get("n") or "GPU"
        hot_parts.append((gpu_name.upper(), gpu_temp))

    if hot_parts:
        lines = ["THERMAL ALERT", ""]
        for name, t in hot_parts:
            lines.append(f"{name} is at {t:.1f}C")
        lines.append("")
        lines.append(f"Threshold: {ALERT_THRESHOLD}C")
        alert_text = "\n".join(lines)

        # delete old alert first
        _delete_alerts()

        # send new alert to both platforms (parallel)
        def _send_bale_alert():
            global ALERT_BALE_MID
            r = bale("sendMessage", {"chat_id": BALE_CHAT, "text": alert_text, "parse_mode": "Markdown"})
            if r and r.get("ok"):
                ALERT_BALE_MID = r["result"]["message_id"]

        def _send_tg_alert():
            global ALERT_TG_MID
            r = tg("sendMessage", {"chat_id": TG_CHAT, "text": alert_text, "parse_mode": "Markdown"})
            if r and r.get("ok"):
                ALERT_TG_MID = r["result"]["message_id"]

        t1 = threading.Thread(target=_send_bale_alert)
        t2 = threading.Thread(target=_send_tg_alert)
        t1.start(); t2.start()
        t1.join(); t2.join()

        log.warning(f"Thermal alert sent: {hot_parts}")
    else:
        if ALERT_BALE_MID or ALERT_TG_MID:
            _delete_alerts()
            log.info("Thermal cleared - alert deleted")


def _delete_alerts():
    global ALERT_BALE_MID, ALERT_TG_MID
    if ALERT_BALE_MID:
        bale("deleteMessage", {"chat_id": BALE_CHAT, "message_id": ALERT_BALE_MID})
        ALERT_BALE_MID = None
    if ALERT_TG_MID:
        tg("deleteMessage", {"chat_id": TG_CHAT, "message_id": ALERT_TG_MID})
        ALERT_TG_MID = None


# ─── Main loop ───

def main():
    global RUNNING, BALE_OFFSET, TG_OFFSET, BALE_MID, TG_MID, ALERT_BALE_MID, ALERT_TG_MID, THRESHOLD_WAIT

    temp = get_cpu_temp()
    cpu = get_cpu_stats()
    ram, gpu, procs, up = get_ram(), get_gpu(), get_procs(), get_up()

    # Send platform-specific initial text
    bale_text = build_text(temp, cpu, ram, gpu, procs, up, update_time=_now_ts(), is_bale=True)
    tg_text   = build_text(temp, cpu, ram, gpu, procs, up, update_time=_now_ts(), is_bale=False)
    send_initial_platform(bale_text, tg_text)

    mode       = "stats"
    last_poll  = 0.0
    last_stats = 0.0

    while RUNNING:
        now  = time.time()
        temp = get_cpu_temp()

        # Poll every 2 seconds
        if now - last_poll >= 2:
            # Bale
            BALE_OFFSET, bm, ba, bcmds, _ = poll_platform("bale", BALE_OFFSET)
            if bm:
                mode = bm
                if ba and mode not in ("stats",):
                    edit_both(ba, kb(mode), BALE_MID, TG_MID)
                    log.info(f"Bale callback -> {mode}")
            for r in bcmds:
                send_cmd_response("bale", r)
                log.info("Bale command received")

            # Telegram
            TG_OFFSET, tm, ta, tcmds, _ = poll_platform("tg", TG_OFFSET)
            if tm:
                mode = tm
                if ta and mode not in ("stats",):
                    edit_both(ta, kb(mode), BALE_MID, TG_MID)
                    log.info(f"Telegram callback -> {mode}")
            for r in tcmds:
                send_cmd_response("tg", r)
                log.info("Telegram command received")

            last_poll = now

        # Stats update
        if mode == "stats":
            if now - last_stats >= INTERVAL_NORMAL or last_stats == 0:
                cpu = get_cpu_stats()
                ram, gpu, procs, up = get_ram(), get_gpu(), get_procs(), get_up()
                bale_text = build_text(temp, cpu, ram, gpu, procs, up, _now_ts(), is_bale=True)
                tg_text   = build_text(temp, cpu, ram, gpu, procs, up, _now_ts(), is_bale=False)

                # Edit each platform with its own formatting (parallel)
                new_bale_mid = BALE_MID
                new_tg_mid = TG_MID
                edit_threads = []
                if BALE_MID:
                    def _edit_bale():
                        nonlocal new_bale_mid
                        new_bale_mid = _safe_edit("bale", BALE_CHAT, BALE_MID, bale_text, kb("stats"))
                    edit_threads.append(threading.Thread(target=_edit_bale))
                if TG_MID:
                    def _edit_tg():
                        nonlocal new_tg_mid
                        new_tg_mid = _safe_edit("tg", TG_CHAT, TG_MID, tg_text, kb("stats"))
                    edit_threads.append(threading.Thread(target=_edit_tg))
                for t in edit_threads: t.start()
                for t in edit_threads: t.join()
                BALE_MID = new_bale_mid
                TG_MID = new_tg_mid

                last_stats = now

                # Thermal alerts (separate messages)
                gpu_info = gpu or {}
                _handle_thermal_alerts(temp, gpu_info)

                log.info(f"{temp:.1f}C | 3s interval")

        # Threshold timeout (1 minute)
        if THRESHOLD_WAIT and now - THRESHOLD_WAIT["time"] > 60:
            delete_msg(THRESHOLD_WAIT["platform"], THRESHOLD_WAIT["msg_id"])
            THRESHOLD_WAIT = None
            log.info("Threshold input timed out")

        elif mode in ("executing", "confirm"):
            time.sleep(5)

        time.sleep(0.15)

    # Clean shutdown
    edit_both("Bot stopped.", {"inline_keyboard": []}, BALE_MID, TG_MID)
    if term_is_active(): term_stop()
    log.info("Goodbye.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(f"Fatal: {e}")
        if term_is_active(): term_stop()
        sys.exit(1)
