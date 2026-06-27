# System Monitor v0.2 — Bale + Telegram Bot

> مانیتورینگ سیستم: دمای CPU، RAM، GPU، ترمینال زنده، اسکرینشات، کنترل صدا و بیشتر — از طریق بله و تلگرام.

<p align="center">
  <a href="README.md" style="color:#2196F3; font-size:18px; text-decoration:none; font-weight:bold;">
    English Version — README.md
  </a>
</p>

---

## قابلیتها

- **CPU**: دما، درصد مصرف، لود سیستم
- **RAM**: مصرف/کل، swap
- **GPU**: دما و استفاده (NVIDIA/AMD/Intel)
- **پردازشها**: پرمصرفترین پردازشهای CPU
- **ترمینال زنده**: شل bash تعاملی در چت (`/term`)
- **اسکرینشات** + **وبکم**
- **کنترل صدا** (0% / 100%)، **قفل صفحه**، **نوتیفیکیشن دسکتاپ**
- **اسکن WiFi**، **نمایش IP**
- **اجرا AnyDesk**
- **خاموش/ریاستارت/اسلیپ** با تأیید
- **ریاستارت ربات**: ریاستارت سرویس ربات از داخل چت
- **هشدار دمایی**: پیام جداگانه وقتی CPU/GPU از 90C رد میشه، با خنک شدن خودکار پاک میشه

---

## پیشنیازها

```bash
# پایتون
sudo apt install python3 python3-pil python3-xlib

# ابزارهای سیستمی
sudo apt install ffmpeg libnotify-bin network-manager pulseaudio-utils
```

### توکنهای ربات

| پلتفرم | ساخت ربات | گرفتن Chat ID |
|---------|-----------|---------------|
| **Telegram** | [@BotFather](https://t.me/BotFather) | [@userinfobot](https://t.me/userinfobot) |
| **Bale** | [@BotFather](https://t.me/BotFather) | [@idfinderbot](https://t.me/idfinderbot) — بفرست `/MyID` |

---

## نصب سریع

```bash
cd ~/Documents/My-PJ/bale-cpu-alert
chmod +x start.sh
bash start.sh
```

اسکریپت خودش پیشنیازها رو چک میکنه، توکنها رو میپرسه، `.env` میسازه، سرویس systemd تنظیم میکنه و ربات رو اجرا میکنه.

---

## اسکریپتهای کمکی

### `start.sh` — نصب و اجرا

```bash
bash start.sh
```

همه کارها رو یکجا انجام میده:
1. پیشنیازها رو چک و نصب میکنه
2. توکنها و آیدی چت رو میپرسه
3. فایل `.env` میسازه
4. سرویس systemd تنظیم میکنه
5. اجرای خودکار موقع بالا اومدن سیستم رو فعال میکنه
6. ربات رو اجرا میکنه

### `disable.sh` — توقف و غیرفعالسازی

```bash
# توقف ربات و غیرفعالسازی اجرای خودکار (فایل سرویس باقی میمونه)
bash disable.sh

# توقف ربات، غیرفعالسازی اجرای خودکار، و حذف کامل فایل سرویس
bash disable.sh --remove-service
```

| دستور | توقف ربات | غیرفعالسازی اجرای خودکار | حذف فایل سرویس |
|-------|:---------:|:------------------------:|:---------------:|
| `bash disable.sh` | بله | بله | نه |
| `bash disable.sh --remove-service` | بله | بله | بله |

---

## مدیریت سرویس

| دستور | کارش |
|-------|------|
| `systemctl --user start bale-cpu-alert` | اجرای ربات |
| `systemctl --user stop bale-cpu-alert` | توقف ربات |
| `systemctl --user restart bale-cpu-alert` | ریاستارت |
| `systemctl --user status bale-cpu-alert` | وضعیت |
| `journalctl --user -u bale-cpu-alert -f` | لاگ زنده |
| `sudo loginctl enable-linger debian` | اجرا بعد از خروج از سیستم |

---

## تنظیمات

فایل `.env` رو تو پوشه پروژه ویرایش کن:

```ini
BALE_BOT_TOKEN=توکن بله
TG_BOT_TOKEN=توکن تلگرام
BALE_CHAT_ID=آیدی چت بله
TG_CHAT_ID=آیدی چت تلگرام
```

### تنظیمات ربات (در `bot.py`)

| متغیر | مقدار پیشفرض | توضیح |
|--------|--------------|------|
| `ALERT_THRESHOLD` | 90C | آستانه دما برای هشدار دمایی |
| `INTERVAL_NORMAL` | 3s | فاصله ثابت آپدیت (همیشه 3 ثانیه) |

---

## دستورات

| دستور | توضیح |
|-------|------|
| `/start` | نمایش راهنما |
| `/term` | باز کردن ترمینال زنده |
| `/bye` | بستن ترمینال |
| `/notif <text>` | ارسال نوتیفیکیشن دسکتاپ |
| `/vol <0-100>` | تنظیم صدا |
| `/cam` | عکس وبکم |
| `/ss` | اسکرینشات |
| `/ip` | نمایش آدرس IP |
| `/wifi` | اسکن شبکههای WiFi |
| `/ad` | اجرای AnyDesk |
| `/lock` | قفل صفحه |
| `/restart` | ریاستارت سرویس ربات |

---

## ساختار فایلها

```
bale-cpu-alert/
├── bot.py              # اسکریپت اصلی ربات
├── start.sh            # نصبکننده و اجراکننده
├── disable.sh          # حذفکننده سرویس
├── CHANGELOG.md        # تاریخچه نسخهها
├── README.md           # راهنمای انگلیسی
├── README-fa.md        # این فایل (راهنمای فارسی)
├── .env                # توکنها (از git خارج شده)
└── .env.example        # نمونه تنظیمات
```

---

## امنیت

- فایل `.env` رو محرمانه نگه دار — **هرگز commit نکن**
- دستورات خاموش/ریاستارت/اسلیپ نیاز به تأیید دارن
- ترمینال = دسترسی کامل شل — Chat ID محدود کن
- برای کارهای حساس از رباتهای جداگانه استفاده کن
