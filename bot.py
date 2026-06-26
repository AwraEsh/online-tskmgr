#!/usr/bin/env python3
"""
System Monitor v5 🔥🤖🎮💻 | Bale + Telegram
- مانیتور کامل سیستم + ترمینال زنده (pty)
- کامند: /term /ad /lock /notif /cam /ss /ip /wifi /vol /bye
- دکمه: همه کامندها + پاور با تأیید مجزا
"""

import os, sys, time, json, glob, logging, signal, subprocess, uuid, io, pty, select, termios, struct, fcntl, errno
from urllib.request import Request, urlopen
from urllib.error import URLError
import threading

# ====== کانفیگ ======
BALE_TOKEN  = os.environ.get("BALE_BOT_TOKEN", "0")
BALE_CHAT   = os.environ.get("BALE_CHAT_ID", "0")

TG_TOKEN    = os.environ.get("TG_BOT_TOKEN", "0")
TG_CHAT     = os.environ.get("TG_CHAT_ID", "0")

ALERT_THRESHOLD = 90
INTERVAL_NORMAL = 2
HOT_SKIP_RATE   = 5
# ====================

if not BALE_TOKEN or not BALE_CHAT or not TG_TOKEN or not TG_CHAT:
    print("❌ یکی از متغیرهای محیطی کمه!")
    sys.exit(1)

BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"
TG_API   = f"https://api.telegram.org/bot{TG_TOKEN}/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sysmon-v5")

RUNNING = True
BALE_OFFSET = 0
TG_OFFSET   = 0
PREV_TOTAL = None
PREV_IDLE  = None
HOT_TICK   = 0

signal.signal(signal.SIGTERM, lambda *_: setattr(sys.modules[__name__], 'RUNNING', False))
signal.signal(signal.SIGINT,  lambda *_: setattr(sys.modules[__name__], 'RUNNING', False))


# ─── API ───

def api_call(base, method, payload, retries=3):
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = Request(f"{base}{method}", data=data,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=15) as r:
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


# ─── آپلود عکس ───

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


# ─── جمع‌آوری آمار ───

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
        u, n, s, i = fields[0], fields[1], fields[2], fields[3]
        t = u + n + s + i
        pct = 0.0
        if PREV_TOTAL is not None:
            dtot, didle = t - PREV_TOTAL, i - PREV_IDLE
            if dtot > 0: pct = round(min((1 - didle/dtot)*100, 100), 1)
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


def get_procs(limit=7):
    try:
        out = subprocess.check_output(["ps", "aux", "--sort=-%cpu"], timeout=3).decode(errors="replace")
        procs = []
        for l in out.strip().split("\n")[1:limit+1]:
            p = l.split(None, 10)
            if len(p) >= 11: procs.append({"c": p[2], "m": p[3], "r": p[5], "cmd": p[10][:35]})
        return procs
    except: return []


def get_up():
    try:
        s = float(open("/proc/uptime").read().strip().split()[0])
        d, h, m = int(s//86400), int((s%86400)//3600), int((s%3600)//60)
        return " ".join(f"{x}{y}" for x,y in [(d,"d"),(h,"h"),(m,"m")] if x) or "0m"
    except: return "?"


# ─── ویجت‌ها ───

def _bar(p, w=10, fill="▓", empty="░"):
    f = round(min(p,100)/100*w)
    return f"`{fill*f}{empty*(w-f)}`"

def _now_ts():
    return time.strftime("%H:%M:%S")


def _thermometer(temp, width=12):
    if temp is None: return "`[░░░░░░░░░░░░]` ?°C"
    f = round(min(temp, 100) / 100 * width)
    f = max(0, min(width, f))
    icon = "🔥" if temp >= 90 else "🔴" if temp >= 75 else "🟠" if temp >= 60 else "🟡" if temp >= 45 else "🟢"
    return f"{icon}`[{'█'*f}{'░'*(width-f)}]` {temp:.1f}°C"


def build_text(temp, cpu, ram, gpu, procs, up, is_hot, skip_info="", update_time=""):
    L, sep = [], "▬▬▬▬▬▬▬▬▬▬▬▬▬"
    if cpu: L.append(f"💻 **System Monitor** · {cpu['cores']}C")
    else:   L.append("💻 **System Monitor**")
    L.append(f"⏱ `{up}` {skip_info}")
    if update_time:
        L[-1] += f" 🕐 `{update_time}`"
    L.append(sep)
    tl = "🖥 **CPU**"
    if temp is not None: tl += f" {_thermometer(temp)}"
    if cpu:
        tl += f"\n   ⚡ `{cpu['pct']}%` {_bar(int(cpu['pct']))}"
        tl += f"\n   📊 Load: `{cpu['l1']} / {cpu['l5']} / {cpu['l15']}`"
    L.append(tl); L.append("")
    if ram:
        ri = "🔴" if ram['pct'] > 80 else "🟠" if ram['pct'] > 60 else "🟢"
        L.append(f"💾 **RAM** {ri} `{ram['u']}/{ram['t']}GB` · `{ram['pct']}%` {_bar(int(ram['pct']))}")
        if ram['st'] > 0:
            sp = round(ram['su']/ram['st']*100) if ram['st'] else 0
            L.append(f"   💿 Swap: `{ram['su']}/{ram['st']}GB` · `{sp}%` {_bar(sp)}")
    L.append("")
    if gpu.get('n') or gpu.get('t') is not None:
        gl = "🎮 **GPU"
        if gpu.get('n'): gl += f" ({gpu['n'].upper()})"
        gl += "**"
        items = []
        if gpu['t'] is not None: items.append(f"🌡{gpu['t']:.0f}°C")
        if gpu['u'] is not None: items.append(f"⚡{gpu['u']:.0f}%")
        if items: gl += " · " + " ".join(items)
        L.append(gl)
    if procs:
        L.append(""); L.append("📌 **Top Processes**")
        for i, p in enumerate(procs, 1):
            rss = round(int(p['r'])/1024, 1) if p['r'].isdigit() else "?"
            L.append(f"  `{i}.` `{p['cmd']}`")
            L.append(f"      ⚡`{p['c']}%`  💾`{p['m']}%` ({rss}MB)")
    return "\n".join(L)


# ─── ترمینال زنده با PTY ───

TERMINAL_PROC = None  # subprocess
TERMINAL_PID  = None  # pty child pid
TERMINAL_FD   = None  # pty master fd
TERMINAL_BUF  = ""    # output buffer
TERMINAL_PLATFORM = None  # "bale" or "tg"
TERMINAL_TICK = 0
TERM_SHELL = "bash"
TERM_ARGS  = ["--norc", "--noprofile"]

def term_start(platform):
    """یه ترمینال جدید با pty بزن (bash ساده، بدون ANSI)"""
    global TERMINAL_PROC, TERMINAL_PID, TERMINAL_FD, TERMINAL_BUF, TERMINAL_PLATFORM, TERMINAL_TICK

    if TERMINAL_FD is not None:
        return "⚠️ یه ترمینال از قبل بازه. اول `/bye` کن بعد دوباره باز کن."

    try:
        pid, fd = pty.fork()
        if pid == 0:
            # child process - bash خام
            os.environ["TERM"] = "dumb"
            os.environ["PS1"] = "> "
            os.execle("/bin/bash", "-bash", "--norc", "--noprofile", os.environ)
            os._exit(1)

        # parent
        TERMINAL_PID = pid
        TERMINAL_FD = fd
        TERMINAL_BUF = ""
        TERMINAL_PLATFORM = platform
        TERMINAL_TICK = 0

        # make fd non-blocking
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        # receive initial prompt
        time.sleep(0.5)
        out = ""
        try:
            out = os.read(fd, 4096).decode(errors="replace")
        except:
            pass

        # no initial read - just send welcome, first command fetches real output
        return "💻 **Terminal** (bash)\nبه شل متصل شدی. هر دستوری بزن برات اجرا میکنم.\n`/bye` برای خروج."

    except Exception as e:
        log.error(f"term_start: {e}")
        return f"❌ خطا: {e}"


def term_send(text):
    """دستور بفرست به ترمینال"""
    global TERMINAL_FD, TERMINAL_BUF, TERMINAL_PID

    if TERMINAL_FD is None:
        return "⚠️ ترمینالی باز نیست. `/term` بزن."

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

        # strip ANSI
        import re
        display = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][0-9;]*[^\x07]*\x07|\x1b[^\[].', '', TERMINAL_BUF[-2000:])
        display = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', display).strip()
        return f"💻 **Terminal**\n\n`{display[:2000]}`"

    except Exception as e:
        log.error(f"term_send: {e}")
        return f"❌ خطا: {e}"


def term_stop():
    """ترمینال رو بکش و ببند"""
    global TERMINAL_FD, TERMINAL_PID, TERMINAL_BUF, TERMINAL_PLATFORM

    if TERMINAL_FD is None:
        return "⚠️ ترمینالی باز نیست."

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

    return "👋 **ترمینال بسته شد.**"


def term_is_active():
    return TERMINAL_FD is not None


# ─── کیبورد ───

def kb(mode="stats"):
    k = {"inline_keyboard": []}
    if mode == "stats":
        k["inline_keyboard"] = [
            [
                {"text": "🖥 AnyDesk", "callback_data": "ad"},
                {"text": "🔒 Lock", "callback_data": "lock"},
            ],
            [
                {"text": "📸 Webcam", "callback_data": "cam"},
                {"text": "🖼 SS", "callback_data": "ss"},
            ],
            [
                {"text": "🌐 IP", "callback_data": "ip"},
                {"text": "📶 WiFi", "callback_data": "wifi"},
            ],
            [
                {"text": "🔊 25", "callback_data": "vol_25"},
                {"text": "🔊 50", "callback_data": "vol_50"},
                {"text": "🔊 75", "callback_data": "vol_75"},
                {"text": "🔊 100", "callback_data": "vol_100"},
            ],
            [
                {"text": "🔄 ریستارت", "callback_data": "reboot"},
                {"text": "⏻ خاموش", "callback_data": "shutdown"},
                {"text": "💤 خواب", "callback_data": "sleep"},
            ],
        ]
    return k


def edit_both(text, keyboard, bale_mid, tg_mid):
    if bale_mid:
        bale("editMessageText", {
            "chat_id": BALE_CHAT, "message_id": bale_mid,
            "text": text, "parse_mode": "Markdown",
            "reply_markup": keyboard})
    if tg_mid:
        tg("editMessageText", {
            "chat_id": TG_CHAT, "message_id": tg_mid,
            "text": text, "parse_mode": "Markdown",
            "reply_markup": keyboard})


def send_text(platform, text):
    """فرستادن یه پیام متنی جدید به پلتفرم مشخص"""
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    return api_call(base, "sendMessage", {
        "chat_id": chat, "text": text, "parse_mode": "Markdown"})


def delete_msg(platform, msg_id):
    """پاک کردن یه پیام"""
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    return api_call(base, "deleteMessage", {
        "chat_id": chat, "message_id": msg_id})


# ─── کامندها ───

def cmd_ad():
    for cmd in ["/var/lib/flatpak/exports/bin/com.anydesk.Anydesk", "/usr/bin/anydesk"]:
        if os.path.exists(cmd):
            subprocess.Popen([cmd]); return "🖥️ **AnyDesk** باز شد!"
    try:
        subprocess.Popen(["flatpak", "run", "com.anydesk.Anydesk"]); return "🖥️ **AnyDesk** باز شد!"
    except: return "❌ AnyDesk روی سیستم نصب نیست."

def cmd_lock():
    subprocess.run(["loginctl", "lock-sessions"], timeout=5); return "🔒 **صفحه قفل شد!**"

def cmd_notif(text):
    if not text.strip(): return "ℹ️ `متن نوتیفیکیشن رو وارد کن`\nمثال: `/notif سلام`"
    subprocess.run(["notify-send", "🖥 System Monitor", text], timeout=5); return "✅ **نوتیفیکیشن** فرستاده شد."

def cmd_cam():
    path = "/tmp/bot_webcam.jpg"
    try:
        subprocess.run(["ffmpeg", "-f", "v4l2", "-video_size", "640x480", "-i", "/dev/video0",
            "-frames:v", "1", "-q:v", "5", "-y", path], timeout=10, capture_output=True)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return ("PHOTO", path, "📸 **وبکم**")
        return "❌ وبکم کار نکرد."
    except Exception as e: return f"❌ خطا: {e}"

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
        if os.path.exists(path) and os.path.getsize(path) > 100: return ("PHOTO", path, "🖥 **اسکرین‌شات**")
        return "❌ اسکرین‌شات کار نکرد."
    except Exception as e: return f"❌ خطا: {e}"

def cmd_ip():
    private = "?"
    try: private = subprocess.check_output(["hostname", "-I"], timeout=5).decode().strip().replace(" ", "\n")
    except: pass
    public = "?"
    try: public = urlopen(Request("https://api.ipify.org"), timeout=5).read().decode().strip()
    except: pass
    return f"🌐 **IP Address**\n▬▬▬▬▬▬▬▬▬▬▬▬▬\n🏠 **پرایوت:**\n`{private}`\n\n🌍 **پابلیک:**\n`{public}`"

def cmd_wifi():
    try:
        out = subprocess.check_output(["nmcli", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], timeout=10).decode(errors="replace").strip()
        lines = out.split("\n")
        if len(lines) <= 1: return "📶 وای‌فای‌ای پیدا نشد."
        result = ["📶 **WiFi Networks**", "▬▬▬▬▬▬▬▬▬▬▬▬▬"]
        for line in lines[1:]:
            parts = line.split(None, 2)
            if len(parts) >= 2:
                bars = int(parts[1])//20 if parts[1].isdigit() else 0
                result.append(f"`{parts[0][:25]:25}` {'▂▄▆█'[:bars]+'_'*(4-bars)} {parts[1]}%")
        return "\n".join(result)
    except: return "❌ خطا"

def cmd_vol(level_str):
    try:
        level = max(0, min(100, int(level_str)))
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], timeout=5, stderr=subprocess.DEVNULL)
        return f"🔊 **صدا** روی `{level}%` تنظیم شد."
    except: return "ℹ️ عدد وارد کن"


# ─── پردازش کامند ───

def handle_command(platform, text, chat_id):
    text = text.strip()

    if text == "/start":
        return ("text", "🤖 **System Monitor v5** فعاله!\n"
                "`/term` ← ترمینال زنده\n"
                "`/notif <text>` ← نوتیفیکیشن\n"
                "`/vol <0-100>` ← صدا\n"
                "بقیه دکمه‌ها تو پنل پایین ⬇️")

    # ترمینال
    if text in ("/term", "/terminal", ".term", ".terminal", "/ter"):
        return ("text", term_start(platform))

    if text == "/bye" or text == ".bye":
        if term_is_active():
            return ("text", term_stop())
        return ("text", "⚠️ ترمینالی باز نیست.")

    if term_is_active():
        return ("text", term_send(text))

    # کامندهای معمولی
    if text in ("/ad", ".ad"): return ("text", cmd_ad())
    if text in ("/lock", ".lock"): return ("text", cmd_lock())
    if text.startswith("/notif "): return ("text", cmd_notif(text[7:]))
    if text == "/notif": return ("text", cmd_notif(""))
    if text in ("/cam", ".cam"): return cmd_cam()
    if text in ("/ss", ".ss", "/screenshot"): return cmd_ss()
    if text in ("/ip", ".ip"): return ("text", cmd_ip())
    if text in ("/wifi", ".wifi"): return ("text", cmd_wifi())
    if text.startswith("/vol "): return ("text", cmd_vol(text[5:]))

    if text.startswith("/"): return ("text", f"❌ کامند `{text.split()[0]}` شناخته نشد.\n`/start` برای راهنما")
    return None


# ─── پردازش کلیک ───

def handle_cb(platform, cq_id, data, from_id, bale_mid, tg_mid, cq_msg_id):
    """برگردونه (new_mode, alt_text, delete_confirm_id)
    delete_confirm_id: اگه پیام تأیید داشت، آیدی اون پیام برای پاک کردن
    """
    plat_chat = BALE_CHAT if platform == "bale" else TG_CHAT

    if str(from_id) != str(plat_chat):
        ans = {"callback_query_id": cq_id, "text": "⛔ نه مال تو"}
        if platform == "bale": bale("answerCallbackQuery", ans)
        else: tg("answerCallbackQuery", ans)
        return None, None, None

    def ack(txt):
        ans = {"callback_query_id": cq_id, "text": txt}
        if platform == "bale": bale("answerCallbackQuery", ans)
        else: tg("answerCallbackQuery", ans)

    # ── دکمه‌های پاور: بجای ادیت پیام موجود، یه پیام تأیید جدید میفرستیم ──
    if data == "reboot":
        ack("🔘 تأیید ریستارت...")
        r = send_text(platform, "🔄 **آیا مطمئنی؟**\nکامپیوتر **ریستارت** میشه.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            # ادیت کنیم دکمه بذاریم
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "🔄 **آیا مطمئنی؟**\nکامپیوتر **ریستارت** میشه.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "✅ آره", "callback_data": "do_reboot"},
                    {"text": "❌ نه", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    if data == "shutdown":
        ack("🔘 تأیید خاموشی...")
        r = send_text(platform, "⏻ **آیا مطمئنی؟**\nکامپیوتر **خاموش** میشه.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "⏻ **آیا مطمئنی؟**\nکامپیوتر **خاموش** میشه.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "✅ آره", "callback_data": "do_shutdown"},
                    {"text": "❌ نه", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    if data == "sleep":
        ack("🔘 تأیید خواب...")
        r = send_text(platform, "💤 **آیا مطمئنی؟**\nکامپیوتر میره به حالت **Sleep**.")
        if r and r.get("ok"):
            confirm_id = r["result"]["message_id"]
            base = BALE_API if platform == "bale" else TG_API
            chat = BALE_CHAT if platform == "bale" else TG_CHAT
            api_call(base, "editMessageText", {
                "chat_id": chat, "message_id": confirm_id,
                "text": "💤 **آیا مطمئنی؟**\nکامپیوتر میره به حالت **Sleep**.",
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "✅ آره", "callback_data": "do_sleep"},
                    {"text": "❌ نه", "callback_data": "cancel"},
                ]]}
            })
            return "confirm", None, confirm_id
        return None, None, None

    # ── دکمه‌های تأیید ──
    if data == "cancel":
        ack("✅ لغو شد")
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "stats", None, None

    if data == "do_reboot":
        ack("🔄 ریستارت...")
        msg = "🔄 **در حال ریستارت شدن...**\n\nتا چند لحظه دیگه سیستم بالا میاد."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "reboot"])
        # پاک کردن پیام تأیید
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    if data == "do_shutdown":
        ack("⏻ خاموش...")
        msg = "⏻ **خاموش شدن...**\n\nتا چند لحظه دیگه سیستم خاموش میشه."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "poweroff"])
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    if data == "do_sleep":
        ack("💤 خواب...")
        msg = "💤 **خواب...**\n\nتا چند لحظه دیگه سیستم میره تو حالت Sleep."
        edit_both(msg, {"inline_keyboard": []}, bale_mid, tg_mid)
        subprocess.Popen(["systemctl", "suspend"])
        if cq_msg_id:
            delete_msg(platform, cq_msg_id)
        return "executing", msg, None

    # ─── دکمه‌های کامند ───
    if data == "ad":
        txt = cmd_ad(); ack(txt); return None, None, None
    if data == "lock":
        txt = cmd_lock(); ack(txt); return None, None, None
    if data == "cam":
        ack("📸 یکی دقیقه...")
        r = cmd_cam(); send_cmd_response(platform, r); return None, None, None
    if data == "ss":
        ack("🖥 یکی دقیقه...")
        r = cmd_ss(); send_cmd_response(platform, r); return None, None, None
    if data == "ip":
        ack("🌐 ...")
        send_cmd_response(platform, ("text", cmd_ip())); return None, None, None
    if data == "wifi":
        ack("📶 ...")
        send_cmd_response(platform, ("text", cmd_wifi())); return None, None, None
    if data.startswith("vol_"):
        level = data.split("_")[1]; txt = cmd_vol(level); ack(txt); return None, None, None

    return None, None, None


# ─── پال کردن ───

def poll_platform(platform, offset):
    fn = bale if platform == "bale" else tg
    updates = fn("getUpdates", {"offset": offset})
    if not updates or not updates.get("ok") or not updates["result"]:
        return offset, None, None, [], None

    new_offset = offset
    new_mode = None
    alt_text = None
    cmds = []
    cq_msg_id = None  # برای ذخیره message_id callback query

    for upd in updates["result"]:
        uid = upd["update_id"]

        cq = upd.get("callback_query")
        if cq:
            new_offset = uid + 1
            # ذخیره message_id از callback_query (برای پاک کردن)
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


# ─── ارسال پاسخ کامند ───

def send_cmd_response(platform, result):
    if result is None: return
    typ = result[0]
    base = BALE_API if platform == "bale" else TG_API
    chat = BALE_CHAT if platform == "bale" else TG_CHAT
    if typ == "text":
        api_call(base, "sendMessage", {"chat_id": chat, "text": result[1], "parse_mode": "Markdown"})
    elif typ == "PHOTO":
        send_photo(base, chat, result[1], result[2])


# ─── ارسال اولیه ───

BALE_MID = None
TG_MID   = None

def send_initial(text):
    global BALE_MID, TG_MID
    r = bale("sendMessage", {"chat_id": BALE_CHAT, "text": text,
        "parse_mode": "Markdown", "reply_markup": kb("stats")})
    if r and r.get("ok"):
        BALE_MID = r["result"]["message_id"]
        log.info(f"📨 بله → ID: {BALE_MID}")
    else:
        log.error("❌ بله استارت نشد!"); sys.exit(1)
    r = tg("sendMessage", {"chat_id": TG_CHAT, "text": text,
        "parse_mode": "Markdown", "reply_markup": kb("stats")})
    if r and r.get("ok"):
        TG_MID = r["result"]["message_id"]
        log.info(f"📨 تلگرام → ID: {TG_MID}")
    else:
        log.error("❌ تلگرام استارت نشد!"); sys.exit(1)
    log.info("✅ هر دو پلتفرم فعالن!")


# ─── لوپ اصلی ───

def main():
    global RUNNING, BALE_OFFSET, TG_OFFSET, HOT_TICK, BALE_MID, TG_MID

    temp = get_cpu_temp()
    cpu = get_cpu_stats()
    cpu = get_cpu_stats()
    ram, gpu, procs, up = get_ram(), get_gpu(), get_procs(), get_up()
    is_hot = temp is not None and temp >= ALERT_THRESHOLD
    text = build_text(temp, cpu, ram, gpu, procs, up, is_hot, update_time=_now_ts())
    send_initial(text)

    mode = "stats"
    last_poll = 0.0
    last_stats = 0.0
    HOT_TICK = 0

    while RUNNING:
        now = time.time()
        temp = get_cpu_temp()
        is_hot = temp is not None and temp >= ALERT_THRESHOLD

        # پال کردن هر ۵ ثانیه
        if now - last_poll >= 5:
            # بله
            BALE_OFFSET, bm, ba, bcmds, _ = poll_platform("bale", BALE_OFFSET)
            if bm:
                mode = bm
                if ba and mode not in ("stats",):
                    edit_both(ba, kb(mode), BALE_MID, TG_MID)
                    log.info(f"🔘 بله → {mode}")
            for r in bcmds:
                send_cmd_response("bale", r)
                log.info(f"📩 بله ← کامند")

            # تلگرام
            TG_OFFSET, tm, ta, tcmds, _ = poll_platform("tg", TG_OFFSET)
            if tm:
                mode = tm
                if ta and mode not in ("stats",):
                    edit_both(ta, kb(mode), BALE_MID, TG_MID)
                    log.info(f"🔘 تلگرام → {mode}")
            for r in tcmds:
                send_cmd_response("tg", r)
                log.info(f"📩 تلگرام ← کامند")

            last_poll = now

        # آپدیت آمار
        if mode == "stats":
            should_update = False
            skip_info = ""
            if is_hot:
                HOT_TICK += 1
                if HOT_TICK >= HOT_SKIP_RATE:
                    should_update = True; HOT_TICK = 0
                skip_info = f"🐌 `1/{HOT_SKIP_RATE}`"
            else:
                HOT_TICK = 0
                if now - last_stats >= INTERVAL_NORMAL or last_stats == 0:
                    should_update = True
            if should_update:
                cpu = get_cpu_stats()
                ram, gpu, procs, up = get_ram(), get_gpu(), get_procs(), get_up()
                text = build_text(temp, cpu, ram, gpu, procs, up, is_hot, skip_info, _now_ts())
                edit_both(text, kb("stats"), BALE_MID, TG_MID)
                last_stats = now
                icon = "🔥" if is_hot else "✅"
                log.info(f"{icon} {temp:.1f}°C ({'hot-skip' if is_hot else '2s'})")
        elif mode in ("executing", "confirm"):
            time.sleep(5)

        time.sleep(0.5)

    # خاموشی تمیز
    edit_both("🛑 *ربات متوقف شد*", {"inline_keyboard": []}, BALE_MID, TG_MID)
    if term_is_active(): term_stop()
    log.info("✋ خداحافظ!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(f"💥 {e}")
        if term_is_active(): term_stop()
        sys.exit(1)
