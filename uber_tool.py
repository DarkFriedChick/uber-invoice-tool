#!/usr/bin/env python3
"""Uber 发票助手 v1.1

填起止日期（点开日历选）→ 读取行程 → 勾选 → 选目录 → 下载 PDF 发票。

依赖：Edge（系统已装）、websocket-client。打包：PyInstaller。
第一次运行会在程序自己的配置目录里开一个浏览器窗口，需要在那里登录一次优步；
登录状态长期保存在该目录，之后不用再登。
"""

import base64
import calendar
import json
import os
import random
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

try:
    import websocket  # websocket-client
    from websocket import WebSocketConnectionClosedException
    from websocket import WebSocketException
except Exception:  # pragma: no cover
    websocket = None
    WebSocketConnectionClosedException = OSError
    WebSocketException = OSError

APP_NAME = "Uber 发票助手"
APP_VER = "1.2"
APP_AUTHOR = "Lucio"
TRIP_LIMIT = 300            # 单次读取上限（软上限，可确认继续）
CONFIRM_DOWNLOAD_OVER = 30  # 超过这个条数先确认
DL_RETRIES = 2              # 单条失败重试次数
DL_FAIL_STREAK = 3          # 连续失败多少条就自动停
DL_DELAY = (0.3, 0.9)       # 每条之间的随机延时间隔（秒）

# 限流与网络错误分开对待：限流等更久但少重试，网络错误多给几次机会
DL_RATE_RETRIES = 2
DL_RATE_BACKOFF = (5, 15)
DL_RATE_STREAK = 3
DL_NET_RETRIES = 4
DL_NET_BACKOFF = (2, 4, 8, 16)
DL_NET_STREAK = 6
DL_OTHER_RETRIES = 2
PAGE_WAIT_SECONDS = 25.0    # 等一页卡片渲染出来


def classify_error(e):
    """把异常分成 rate（限流）/ net（网络）/ other。"""
    code = getattr(e, "code", None)
    if code in (429, 403, 503):
        return "rate"
    if isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError,
                      socket.timeout, ssl.SSLError)):
        return "net"
    text = str(e).lower()
    if "429" in text or "too many" in text or "rate limit" in text or "forbidden" in text:
        return "rate"
    if any(k in text for k in ("timed out", "timeout", "connection", "reset",
                               "unreachable", "getaddrinfo", "ssl", "network")):
        return "net"
    return "other"


def jitter(lo=None, hi=None):
    """随机延迟，避免固定频率请求。"""
    a, b = DL_DELAY
    time.sleep(random.uniform(lo if lo is not None else a, hi if hi is not None else b))

# --------------------------------------------------------------------------
# 多语言
# --------------------------------------------------------------------------
LANG = "zh"

STR = {
    "zh": {
        "app_name": "Uber 发票助手",
        "author": "作者：{a}",
        "auto": "自动（推荐）",
        "browser": "浏览器",
        "from": "从",
        "to": "到",
        "load": "读取行程",
        "all": " 全选",
        "none": " 全不选",
        "clear": " 清空",
        "col_pick": "选择",
        "col_date": "日期",
        "col_time": "时间",
        "col_amount": "金额",
        "col_place": "地点 / 卡片标题",
        "col_status": "状态",
        "dl_to": "下载到",
        "choose": "选择…",
        "download": "⬇  下载所选",
        "ready": "可下载",
        "no_inv": "无发票",
        "st_incomplete": "未完成",
        "st_cancelled": "已取消",
        "sel_none": "已选 0 条",
        "sel_n": "已选 {n} 条",
        "total": "共 {n} 条 · 有发票 {m} 条",
        "total0": "共 0 条",
        "shown": " · 当前显示 {k} 条",
        "status_init": "填好日期 → 读取行程 → 勾选 → 下载。首次使用需在弹出窗口登录一次优步。",
        "empty": "还没有数据\n\n选好起止日期，点左上角「读取行程」\n首次使用需要在弹出的浏览器窗口里登录一次优步",
        "empty_filtered": "没有匹配的行程\n\n换个关键词试试，或清空搜索框",
        "opening": "正在打开 {b}…",
        "need_login": "未登录：请在弹出的浏览器窗口里登录优步，然后回来再点一次「读取行程」。",
        "need_login_title": "需要登录一次",
        "need_login_body": "请在刚弹出的浏览器窗口里登录优步。\n登录完成后回到这里，再点一次「读取行程」即可（登录状态会长期保存）。\n\n注意：读取和下载期间请不要关闭这个浏览器窗口。",
        "login_gone": "登录已失效，请先在浏览器里重新登录优步。",
        "preparing": "已登录，准备读取行程…",
        "reading": "已读取 {n} 条 · 已翻到 {d} · 已用 {s} 秒",
        "limit_title": "已读到 {n} 条上限",
        "limit_body": "本次已读取 {n} 条，最早的到 {d}。\n\n继续读取更早的行程吗？（再给 {lim} 条额度，大约还需 1–2 分钟）\n\n选「否」则先结束，建议缩小日期区间后重新读取。",
        "done": "读取完成：{n} 条行程，其中 {m} 条有发票。勾选后点「下载所选」。{w}",
        "done_trunc": "读取完成：{n} 条（已达上限，最早到 {d}），其中 {m} 条有发票。更早的未读取，请缩短日期区间或再次读取。{w}",
        "stalled": "（翻页中途卡住过，可能没读全；可再点一次「读取行程」重试）",
        "date_bad": "日期范围不对",
        "date_bad_msg": "起始日期不能晚于结束日期",
        "nothing_sel": "没选中",
        "nothing_sel_msg": "请先在「选择」列点一下勾上要下载的行程",
        "confirm_dl": "确认批量下载",
        "confirm_dl_msg": "将下载 {n} 张发票，预计需要约 {s} 秒。\n\n数量较多时 Uber 可能限流，中途失败会在最后统一报告。\n\n注意：下载期间请不要关闭弹出的浏览器窗口。\n继续吗？",
        "getting": "正在获取 {n} 条行程的发票地址…",
        "urls": "获取发票地址 {a}/{b}…",
        "dl_ing": "正在下载到 {d} …",
        "dl_n": "下载中 {a}/{b}…",
        "noclose": "请勿关闭弹出的浏览器窗口，否则下载会中断。",
        "noclose_short": "（勿关窗口）",
        "ok_n": "成功 {n} 个",
        "receipt_n": "其中 {n} 个是该地区无发票文件、由网页收据生成的 PDF",
        "miss_n": "没拿到 {n} 条：{lst}",
        "fail_n": "失败 {n} 条：{lst}",
        "abort_line": "已自动中止：连续 {n} 条失败（最后错误：{e}），可能是触发了 Uber 限流，建议几分钟后再试。",
        "abort_rate": "已自动中止：连续 {n} 条被限流（最后错误：{e}）。建议等几分钟再试。",
        "abort_net": "已自动中止：连续 {n} 条网络失败（最后错误：{e}）。请检查网络后重试。",
        "retry_note": "{k}，{s} 秒后重试（{a}/{b}）：{e}",
        "retry_kind_rate": "被限流",
        "retry_kind_net": "网络错误",
        "retry_kind_other": "出错",
        "page_retry": "页面没加载出来，正在重新加载…",
        "conn_lost": "浏览器连接断开了（可能窗口被关闭、崩溃或被休眠）。请重新点一次「读取行程」，程序会自动重开浏览器。",
        "no_cards_hint": "没读到任何行程卡片：可能未登录、账号本没有行程，或 Uber 页面结构变了。",
        "left_line": "还有 {n} 条未尝试。",
        "dl_done": "下载完成：{msg}　目录：{d}",
        "dl_title": "下载结果",
        "dl_head": "下载完成",
        "dir_line": "目录：{d}",
        "open_dir": "打开文件夹",
        "close": "关闭",
        "no_open": "打不开目录",
        "err": "出错：{m}",
        "err_title": "出错",
        "busy_title": "稍等",
        "busy_msg": "上一个操作还没结束",
        "cal_title": "选择日期",
        "cal_today": "今天",
        "cal_esc": "Esc 关闭",
        "cal_month": "{y} 年 {m} 月",
        "week": "一二三四五六日",
        "cal_month_names": "",
        "no_browser": "没有找到可用的 Chromium 浏览器。\n\n已尝试的路径：\n{t}\n\n请安装 Microsoft Edge / Google Chrome / Brave / Vivaldi 之一，或用注册表 App Paths 登记浏览器路径。",
        "no_tried": "（无）",
        "fallback_auto": "选定的浏览器已不在本机，已回退到自动选择",
        "will_use": "将使用：{b}（配置目录 {p}）",
        "bad_date_fmt": "日期格式不对",
        "receipt_prefix": "Uber收据_",
        "default_dir": "Uber发票",
        "no_file_region": "该地区没有发票文件，也没能取到网页收据",
        "not_pdf": "返回的不是 PDF",
        "missing_dep": "缺少依赖",
        "missing_dep_msg": "缺少 websocket-client，请先运行：\n\npip install websocket-client",
        "no_browser_short": "没有找到可用的 Chromium 浏览器。已尝试：\n{t}\n\n请先安装 Microsoft Edge / Google Chrome / Brave / Vivaldi 之一。",
        "debug_hint": "（翻页中途卡住过，可能没读全）",
    },
    "en": {
        "app_name": "Uber Receipt Helper",
        "author": "Author: {a}",
        "auto": "Auto (recommended)",
        "browser": "Browser",
        "from": "From",
        "to": "To",
        "load": "Load trips",
        "all": " Select all",
        "none": " Deselect",
        "clear": " Clear",
        "col_pick": "Pick",
        "col_date": "Date",
        "col_time": "Time",
        "col_amount": "Amount",
        "col_place": "Place / card title",
        "col_status": "Status",
        "dl_to": "Save to",
        "choose": "Browse…",
        "download": "⬇  Download selected",
        "ready": "Ready",
        "no_inv": "No file",
        "st_incomplete": "Incomplete",
        "st_cancelled": "Cancelled",
        "sel_none": "0 selected",
        "sel_n": "{n} selected",
        "total": "{n} trips · {m} with file",
        "total0": "0 trips",
        "shown": " · showing {k}",
        "status_init": "Pick dates → Load trips → tick rows → Download. Sign in to Uber once on first run.",
        "empty": "Nothing loaded yet\n\nChoose dates, then click “Load trips”\nOn first run, sign in to Uber in the browser window",
        "empty_filtered": "No matching trips\n\nTry another keyword or clear the filter",
        "opening": "Opening {b}…",
        "need_login": "Not signed in: sign in to Uber in the browser window, then click “Load trips” again.",
        "need_login_title": "Sign in once",
        "need_login_body": "Please sign in to Uber in the browser window that just opened.\nThen come back and click “Load trips” again (the session is remembered).\n\nNote: keep that browser window open while loading and downloading.",
        "login_gone": "Session expired. Sign in to Uber again in the browser.",
        "preparing": "Signed in. Preparing to load trips…",
        "reading": "{n} loaded · down to {d} · {s}s",
        "limit_title": "Reached {n} trips",
        "limit_body": "Loaded {n} trips, oldest is {d}.\n\nKeep loading older trips? (another {lim}, about 1–2 minutes)\n\nChoose “No” to stop now and narrow the date range instead.",
        "done": "Done: {n} trips, {m} with a downloadable file. Tick rows, then “Download selected”.{w}",
        "done_trunc": "Done: {n} trips (hit the limit, oldest {d}), {m} with a file. Older trips were not read — narrow the range or load again.{w}",
        "stalled": " (paging stalled, results may be incomplete — load again to retry)",
        "date_bad": "Invalid date range",
        "date_bad_msg": "Start date cannot be later than end date",
        "nothing_sel": "Nothing selected",
        "nothing_sel_msg": "Click the “Pick” column to tick the trips you need",
        "confirm_dl": "Confirm bulk download",
        "confirm_dl_msg": "About to download {n} files, roughly {s}s.\n\nLarge batches may be rate-limited; failures are reported at the end.\n\nNote: keep the browser window open during the download.\nContinue?",
        "getting": "Fetching file URLs for {n} trips…",
        "urls": "Resolving URLs {a}/{b}…",
        "dl_ing": "Downloading to {d} …",
        "dl_n": "Downloading {a}/{b}…",
        "noclose": "Keep the browser window open — closing it interrupts the download.",
        "noclose_short": " (keep the browser window open)",
        "ok_n": "{n} saved",
        "receipt_n": "{n} of them were web receipts (no invoice file in that region)",
        "miss_n": "{n} not available: {lst}",
        "fail_n": "{n} failed: {lst}",
        "abort_line": "Stopped automatically: {n} failures in a row (last error: {e}). That usually means rate limiting — wait a few minutes and retry.",
        "abort_rate": "Stopped automatically: {n} rate-limited responses in a row (last error: {e}). Wait a few minutes and retry.",
        "abort_net": "Stopped automatically: {n} network failures in a row (last error: {e}). Check your connection and retry.",
        "retry_note": "{k} — retrying in {s}s ({a}/{b}): {e}",
        "retry_kind_rate": "Rate limited",
        "retry_kind_net": "Network error",
        "retry_kind_other": "Error",
        "page_retry": "Page did not load; reloading…",
        "conn_lost": "Browser connection lost (window closed, crashed, or the machine slept). Click “Load trips” again — the browser will reopen automatically.",
        "no_cards_hint": "No trip cards found: not signed in, no trips on this account, or Uber changed its page structure.",
        "left_line": "{n} trips were not attempted.",
        "dl_done": "Download finished: {msg}　Folder: {d}",
        "dl_title": "Download result",
        "dl_head": "Download finished",
        "dir_line": "Folder: {d}",
        "open_dir": "Open folder",
        "close": "Close",
        "no_open": "Cannot open folder",
        "err": "Error: {m}",
        "err_title": "Error",
        "busy_title": "Please wait",
        "busy_msg": "The previous operation is still running",
        "cal_title": "Pick a date",
        "cal_today": "Today",
        "cal_esc": "Esc to close",
        "cal_month": "{mon} {y}",
        "week": "MTWTFSS",
        "cal_month_names": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
        "no_browser": "No usable Chromium browser found.\n\nTried:\n{t}\n\nInstall Microsoft Edge / Google Chrome / Brave / Vivaldi, or register its path under App Paths.",
        "no_tried": "(none)",
        "fallback_auto": "Selected browser is gone; falling back to auto",
        "will_use": "Using {b} (profile {p})",
        "bad_date_fmt": "Bad date format",
        "receipt_prefix": "UberReceipt_",
        "default_dir": "UberReceipts",
        "no_file_region": "No invoice file for this region, and the web receipt could not be fetched",
        "not_pdf": "Response was not a PDF",
        "missing_dep": "Missing dependency",
        "missing_dep_msg": "websocket-client is required:\n\npip install websocket-client",
        "no_browser_short": "No usable Chromium browser found. Tried:\n{t}\n\nInstall Microsoft Edge / Google Chrome / Brave / Vivaldi.",
        "debug_hint": " (paging stalled, results may be incomplete)",
    },
}


def T(key, **kw):
    table = STR.get(LANG) or STR["zh"]
    s = table.get(key)
    if s is None:
        s = STR["zh"].get(key, key)
    return s.format(**kw) if kw else s


def app_name():
    return T("app_name")


AUTO_LABEL = "自动（推荐）"   # 启动时会被 set_language() 覆盖


def set_language(lang):
    """zh / en；同时同步依赖语言的模块级常量。"""
    global LANG, AUTO_LABEL
    LANG = "en" if str(lang).lower().startswith("en") else "zh"
    AUTO_LABEL = T("auto")
    return LANG


def detect_language():
    """命令行 --lang 优先，其次环境变量，最后看系统 UI 语言。"""
    argv = [a.lower() for a in sys.argv[1:]]
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    env = (os.environ.get("UBER_TOOL_LANG") or "").lower()
    if env:
        return env
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "zh" if (lid & 0x3FF) == 0x04 else "en"
    except Exception:
        return "zh"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UberInvoiceTool"
PROFILE_DIR = APP_DIR / "profile"
SETTINGS_FILE = APP_DIR / "settings.json"
CDP_PORT = 9333
TRIPS_URL = "https://riders.uber.com/trips"

# 浏览器候选：key、显示名、常见安装路径、注册表 App Paths 里的 exe 名
BROWSER_SPECS = [
    ("edge", "Microsoft Edge", [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
    ], ["msedge.exe"]),
    ("chrome", "Google Chrome", [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ], ["chrome.exe"]),
    ("brave", "Brave", [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ], ["brave.exe"]),
    ("vivaldi", "Vivaldi", [
        r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
        r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe",
        r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe",
    ], ["vivaldi.exe"]),
    ("chromium", "Chromium", [
        r"C:\Program Files\Chromium\Application\chrome.exe",
        r"%LOCALAPPDATA%\Chromium\Application\chrome.exe",
    ], ["chromium.exe", "chrome.exe"]),
]

APP_PATHS_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
LEGACY_PROFILE = APP_DIR / "profile"
PROFILE_ROOT = APP_DIR / "profiles"
GET_TRIED_PATHS = []      # 探测浏览器时试过的路径，报错时展示

INVOICE_QUERY = (
    "query GetInvoiceFiles($tripUUID: ID!) {\n"
    "  invoiceFiles(tripUUID: $tripUUID) {\n"
    "    archiveURL\n"
    "    files {\n"
    "      downloadURL\n"
    "      __typename\n"
    "    }\n"
    "    __typename\n"
    "  }\n"
    "}\n"
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# ---- 配色（参考 HiBit：蓝底标题 + 浅蓝条纹表格 + 底部统计条） ----
C_BANNER_TOP = (10, 78, 190)
C_BANNER_BOT = (62, 143, 232)
C_BG = "#eef2f8"
C_PANEL = "#ffffff"
C_LINE = "#c9d6ea"
C_HEAD_BG = "#e6eefb"
C_STRIPE = "#f5f9ff"
C_SEL = "#cfe3ff"
C_TEXT = "#1a1a1a"
C_SUB = "#5a6b82"


def _expand(p):
    try:
        return os.path.expandvars(p)
    except Exception:
        return p


def _app_paths_candidates(exe_name):
    """注册表 App Paths 里的真实路径（便携/非标准安装也能命中）。"""
    out = []
    try:
        import winreg
    except Exception:
        return out
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, APP_PATHS_ROOT + "\\" + exe_name) as k:
                val, _ = winreg.QueryValueEx(k, "")
                if val:
                    out.append(_expand(val))
        except Exception:
            continue
    return out


def detect_browsers():
    """返回 (browsers, tried)。browsers = [(key, 显示名, 路径)]，尝试过的路径全部带出。"""
    found, seen, tried = [], set(), []
    for key, label, paths, exe_names in BROWSER_SPECS:
        cand = [_expand(p) for p in paths]
        for name in exe_names:
            cand.extend(_app_paths_candidates(name))
        hit = None
        for p in cand:
            tried.append(p)
            try:
                if p and Path(p).exists():
                    hit = p
                    break
            except Exception:
                continue
        if hit:
            rp = str(Path(hit))
            if rp.lower() not in seen:
                seen.add(rp.lower())
                found.append((key, label, rp))
    return found, tried


def profile_dir_for(key):
    r"""每个浏览器一个配置目录；老版本单目录（profile）自动迁移成 profiles\edge。"""
    target = PROFILE_ROOT / key
    if not target.exists() and LEGACY_PROFILE.exists():
        try:
            if any(LEGACY_PROFILE.iterdir()) and key == "edge":
                LEGACY_PROFILE.rename(target)
                return target
        except Exception:
            return LEGACY_PROFILE
    return target


# --------------------------------------------------------------------------
# CDP 客户端
# --------------------------------------------------------------------------
class CDP:
    def __init__(self, port=CDP_PORT):
        self.port = port
        self.ws = None
        self._id = 0
        self.ws_url = None

    def ensure_browser(self, exe, profile_dir, url=TRIPS_URL, wait=45):
        self.exe = exe
        self.profile_dir = Path(profile_dir)
        if self._try_connect():
            return True
        self.close()          # 丢弃可能已死的连接，避免复用到旧 socket
        if not exe or not Path(exe).exists():
            raise RuntimeError(T("no_browser_short", t="\n".join(GET_TRIED_PATHS)))
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen([
            exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ], close_fds=True)
        deadline = time.time() + wait
        while time.time() < deadline:
            time.sleep(1)
            if self._try_connect():
                return True
        raise RuntimeError(
            "Browser started but the DevTools port never answered.\n\n"
            f"EXE: {exe}\nProfile: {self.profile_dir}\n\n"
            "Close the browser window this tool opened and retry; if policy blocks remote "
            "debugging, install another Chromium browser.")

    def _try_connect(self):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=3) as r:
                json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            return False
        return True

    def _http_json(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))

    def _page_target(self):
        targets = self._http_json("/json/list")
        pages = [t for t in targets if t.get("type") == "page"]
        for t in pages:
            if "riders.uber.com" in (t.get("url") or ""):
                return t
        if pages:
            return pages[0]
        for method in ("PUT", "GET"):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}/json/new?{urllib.request.quote(TRIPS_URL)}",
                    method=method)
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read().decode("utf-8", "ignore"))
            except Exception:
                continue
        raise RuntimeError("Cannot open a browser tab")

    def connect(self):
        if self.ws is not None and getattr(self.ws, "connected", False):
            return self
        self.close()
        t = self._page_target()
        self.ws_url = t["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(self.ws_url, timeout=180, suppress_origin=True)
        self._send_once("Runtime.enable", {})
        self._send_once("Page.enable", {})
        return self

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.ws = None

    @staticmethod
    def _is_closed_error(e):
        txt = str(e).lower()
        return (isinstance(e, (WebSocketConnectionClosedException, BrokenPipeError,
                               ConnectionResetError, ConnectionAbortedError))
                or "already closed" in txt or "connection is closed" in txt
                or "broken pipe" in txt or "socket" in txt and "closed" in txt)

    def _send_once(self, method, params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            raw = self.ws.recv()
            if not raw:
                raise WebSocketConnectionClosedException("Browser connection closed")
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(str(data["error"]))
                return data.get("result", {})

    def _send(self, method, params):
        """连接断了（关窗/崩溃/休眠）自动重连一次，再失败就给可读的错。"""
        try:
            return self._send_once(method, params)
        except Exception as e:
            if not self._is_closed_error(e):
                raise
            try:
                self.close()
                self.connect()
                return self._send_once(method, params)
            except Exception:
                raise RuntimeError(T("conn_lost"))

    def navigate(self, url):
        self._send("Page.navigate", {"url": url})

    def current_url(self):
        return self.evaluate("location.href", await_promise=False, timeout_ms=8000)

    def wait_ready(self, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.evaluate("document.readyState", await_promise=False, timeout_ms=5000) == "complete":
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def evaluate(self, expression, await_promise=True, timeout_ms=120000):
        res = self._send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
            "timeout": timeout_ms,
        })
        if "exceptionDetails" in res:
            raise RuntimeError("Page script error: " + json.dumps(res["exceptionDetails"], ensure_ascii=False)[:300])
        return res.get("result", {}).get("value")


# --------------------------------------------------------------------------
# 优步业务逻辑
# --------------------------------------------------------------------------
class Trip:
    __slots__ = ("id", "date", "time", "currency", "amount", "place", "status", "selected")

    def __init__(self, tid, d, t, cur, amount, place, status):
        self.id = tid
        self.date = d
        self.time = t
        self.currency = cur
        self.amount = amount
        self.place = place
        self.status = status
        self.selected = False

    @property
    def has_invoice(self):
        return self.status == "" and self.amount not in ("0.00", "0", "")

    @property
    def amount_value(self):
        try:
            return float(self.amount)
        except Exception:
            return 0.0


def _yyyymmdd(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _from_yyyymmdd(v):
    try:
        v = int(v)
        return date(v // 10000, (v // 100) % 100, v % 100)
    except Exception:
        return None


MONTHS_EN = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_cards(raw_items):
    """兼容中英文两种卡片格式：
    中文：Golden Dragon11月23日 • 下午4:30SAR44.10
    英文：Golden Dragon Nov 23 • 4:30 PMS$44.10
    """
    today = date.today()
    out = []
    for item in raw_items:
        text = re.sub(r"\s+", " ", item.get("t") or "").strip()
        if not text:
            continue
        month = day = None
        tm = ""
        start = 0
        m = re.search(r"(\d{1,2})月(\d{1,2})日\s*•\s*(上午|下午)?\s*(\d{1,2}):(\d{2})", text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            tm = f"{m.group(3) or ''}{m.group(4)}:{m.group(5)}"
            start = m.start()
        else:
            m2 = re.search(r"([A-Z][a-z]{2})[a-z]*\s+(\d{1,2})\s*•\s*(\d{1,2}):(\d{2})\s*([AP]M)?",
                           text)
            if m2 and m2.group(1) in MONTHS_EN:
                month, day = MONTHS_EN[m2.group(1)], int(m2.group(2))
                tm = f"{m2.group(3)}:{m2.group(4)} {m2.group(5) or ''}".strip()
                start = m2.start()
        if month is None:
            continue
        year = today.year
        if (month, day) > (today.month, today.day):
            year -= 1
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        am = re.search(r"([A-Z]{3})\s?([\d,]+\.?\d*)", text)
        cur = am.group(1) if am else ""
        amount = (am.group(2) if am else "").replace(",", "")
        place = text[:start].strip() or "—"
        low = text.lower()
        status = ""
        if "未完成" in text or "incomplete" in low:
            status = "incomplete"
        elif "已取消" in text or "cancel" in low:
            status = "cancelled"
        out.append(Trip(item["id"], d, tm, cur, amount, place[:40], status))
    return out


def status_label(t):
    if t.status == "incomplete":
        return T("st_incomplete")
    if t.status == "cancelled":
        return T("st_cancelled")
    return T("ready") if t.has_invoice else T("no_inv")


def weekdays():
    """日历表头：中文用一二三…，英文用 M T W T F S S。"""
    return list(T("week")) if LANG == "zh" else ["M", "T", "W", "T", "F", "S", "S"]


def month_title(year, month):
    if LANG == "zh":
        return T("cal_month", y=year, m=month)
    return T("cal_month", mon=calendar.month_abbr[month], y=year)


# 旧的「点更多」翻页（已被 cursor 分页取代，保留仅供对照，不再调用）
LIST_JS = r"""
(async (n) => {
  const S = window.__us || (window.__us = { seen: new Map(), stalled: 0, done: false, reason: '' });
  if (S.done) return { count: S.seen.size, oldest: null, done: true, reason: S.reason };
  const START = %(start)d;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const parse = (t) => {
    const m = /(\d{1,2})月(\d{1,2})日/.exec(t || '');
    if (!m) return null;
    const now = new Date();
    const mo = +m[1], da = +m[2];
    let y = now.getFullYear();
    if (mo > now.getMonth() + 1 || (mo === now.getMonth() + 1 && da > now.getDate())) y -= 1;
    return y * 10000 + mo * 100 + da;
  };
  const grab = () => {
    document.querySelectorAll('[href*="/trips/"]').forEach(el => {
      const id = (el.getAttribute('href') || '').split('/trips/')[1];
      const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (id && t && !S.seen.has(id)) S.seen.set(id, t);
    });
  };
  const findMore = () =>
    Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '更多');
  const oldestOf = () => {
    let o = null;
    for (const t of S.seen.values()) { const v = parse(t); if (v && (o === null || v < o)) o = v; }
    return o;
  };

  grab();
  for (let i = 0; i < n && !S.done; i++) {
    const before = S.seen.size;
    let grew = false;
    // 网络慢时同一页会给到 3 次机会（约 4 秒），不因一次没新增就判定到底
    for (let attempt = 0; attempt < 3; attempt++) {
      const more = findMore();
      if (more) more.click();
      window.scrollTo(0, document.body.scrollHeight);
      await sleep(1200);
      grab();
      if (S.seen.size > before) { grew = true; break; }
    }
    const oldest = oldestOf();
    if (oldest !== null && oldest < START) { S.done = true; S.reason = 'reached'; break; }
    if (!grew) {
      if (!findMore()) { S.done = true; S.reason = 'exhausted'; break; }
      S.stalled = (S.stalled || 0) + 1;
      if (S.stalled >= 3) { S.done = true; S.reason = 'stalled'; break; }
    } else {
      S.stalled = 0;
    }
  }
  return { count: S.seen.size, oldest: oldestOf(), done: S.done, reason: S.reason, stalled: S.stalled || 0 };
})(%(n)d)
"""

DUMP_JS = "(() => [...(window.__us ? window.__us.seen.entries() : [])].map(([id, t]) => ({ id, t })))()"
RESET_JS = "(() => { window.__us = null; return true; })()"

# 行程列表页用 URL 上的 cursor（base64 的 UTC 时间戳）分页，直接跳时间点最稳
# 注意：日期格式中英文都要认（Nov 23 • 4:30 PM / 11月23日 • 下午4:30）
CARDS_JS = r"""(() => Array.from(document.querySelectorAll('[href*="/trips/"]'))
  .map(el => {
    const id = (el.getAttribute('href') || '').split('/trips/')[1];
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    return { id, t };
  })
  .filter(x => x.id && (/\d{1,2}月\d{1,2}日/.test(x.t)
    || /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*•/.test(x.t))))()"""

INVOICE_JS = r"""
(async (ids) => {
  const Q = %(query)s;
  const out = [];
  for (const id of ids) {
    try {
      const r = await fetch('/graphql', {
        method: 'POST', credentials: 'include',
        headers: { 'content-type': 'application/json', 'x-csrf-token': 'x' },
        body: JSON.stringify({ operationName: 'GetInvoiceFiles', variables: { tripUUID: id }, query: Q })
      });
      const j = await r.json();
      const f = (j.data && j.data.invoiceFiles && j.data.invoiceFiles.files) || [];
      out.push([id, f.length ? f[0].downloadURL : null]);
    } catch (e) { out.push([id, null]); }
    await new Promise(r => setTimeout(r, 180));
  }
  return out;
})(%(ids)s)
"""


class UberWorker:
    def __init__(self, log=print):
        self.cdp = CDP()
        self.log = log
        self.browser = None
        self.last_stalled = False
        self.abort_reason = ""
        self.abort_kind = ""
        self.not_attempted = 0

    def open_browser(self, browser):
        """browser = (key, 显示名, 路径)"""
        self.browser = browser
        key, label, path = browser
        self.log(T("opening", b=label))
        self.cdp.ensure_browser(path, profile_dir_for(key))
        self.cdp.connect()
        self.cdp.wait_ready(25)
        return True

    def is_logged_in(self):
        url = self.cdp.current_url() or ""
        if "auth.uber.com" in url:
            return False
        body = self.cdp.evaluate("document.body ? document.body.innerText.slice(0,300) : ''",
                                 await_promise=False, timeout_ms=8000) or ""
        if "登录" in body and "行程" not in body:
            return False
        low = body.lower()
        if ("sign in" in low or "log in" in low) and "trip" not in low:
            return False
        return True

    def goto_trips(self):
        self.cdp.navigate(TRIPS_URL)
        time.sleep(2.5)
        self.cdp.wait_ready(20)

    def _wait_cards(self, timeout=12.0):
        """等当前页渲染出行程卡片，返回 [{id, t}]。"""
        deadline = time.time() + timeout
        last = []
        while time.time() < deadline:
            try:
                cards = self.cdp.evaluate(CARDS_JS, await_promise=False, timeout_ms=8000) or []
            except Exception:
                cards = []
            if cards:
                if len(cards) == len(last):
                    return cards
                last = cards
            time.sleep(0.4)
        return last

    def list_trips(self, start: date, end: date, on_progress=None, on_limit=None, limit=300, note=None):
        """按 cursor 往回翻页（每页约 10 条）。on_progress(count, oldest_int, seconds)；
        on_limit(count, oldest_int) 返回 True 表示继续。返回 (trips, truncated)。"""
        cap = limit
        truncated = False
        started = time.time()
        cards_map = {}
        cursor = None
        guard = 0
        while guard < 400:
            guard += 1
            if cursor is None:
                url = TRIPS_URL
            else:
                url = f"{TRIPS_URL}?cursor={cursor}&id=214"
            self.cdp.navigate(url)
            time.sleep(1.0)
            got = self._wait_cards(PAGE_WAIT_SECONDS)
            if not got:
                # 弱网/渲染慢时页面可能是空的，先重载一次再判定“到底了”
                if note:
                    note(T("page_retry"))
                self.cdp.navigate(url)
                time.sleep(2.0)
                got = self._wait_cards(PAGE_WAIT_SECONDS)
            if not got:
                if note and guard == 1:
                    note(T("no_cards_hint"))
                break
            new = 0
            for c in got:
                cid = c.get("id")
                if cid and cid not in cards_map:
                    cards_map[cid] = c.get("t") or ""
                    new += 1
            parsed = parse_cards([{"id": k, "t": v} for k, v in cards_map.items()])
            if not parsed:
                break
            oldest = min(t.date for t in parsed)
            oldest_int = _yyyymmdd(oldest)
            inside = [t for t in parsed if start <= t.date <= end]
            if on_progress:
                on_progress(len(inside), oldest_int, int(time.time() - started))
            if oldest < start:
                break
            if new == 0 and len(got) < 10:
                break
            if len(inside) >= cap:
                if on_limit and on_limit(len(inside), oldest_int):
                    cap = len(inside) + limit
                else:
                    truncated = True
                    break
            # 下一页：取最早那天往前 6 小时（覆盖 +4 时区并留缓冲），避免跳过同一分钟的多笔
            nxt = datetime.combine(oldest - timedelta(days=1), datetime.min.time()) + timedelta(hours=18)
            cursor = base64.b64encode(nxt.strftime("%Y-%m-%dT%H:%M:%S.000Z").encode()).decode().rstrip("=")
        trips = [t for t in parse_cards([{"id": k, "t": v} for k, v in cards_map.items()])
                 if start <= t.date <= end]
        trips.sort(key=lambda t: (t.date, t.time), reverse=True)
        self.last_stalled = False
        return trips, truncated

    # ---- 非沙特国家没有发票文件时的备选：把页面里的收据打成 PDF ----
    def _open_receipt(self, trip_id):
        self.cdp.navigate(f"https://riders.uber.com/trips/{trip_id}")
        time.sleep(2.5)
        self.cdp.wait_ready(20)
        ok = self.cdp.evaluate("""
        (() => {
          const b = Array.from(document.querySelectorAll('button'))
            .find(x => /收据|receipt/i.test(x.innerText || ''));
          if (!b) return false;
          b.click();
          return true;
        })()
        """, await_promise=False, timeout_ms=15000)
        time.sleep(2.0)
        return bool(ok)

    def _find_receipt_pdf_href(self):
        """在已打开的收据弹窗里找「下载 PDF」链接。"""
        return self.cdp.evaluate(r"""
        (() => {
          const links = Array.from(document.querySelectorAll('a'));
          const hit = links.find(a =>
            /下载\s*PDF|Download\s*PDF|receipt\?contentType=PDF/i.test(
              (a.innerText || '') + ' ' + (a.getAttribute('href') || '')));
          return hit ? hit.getAttribute('href') : null;
        })()
        """, await_promise=False, timeout_ms=15000)

    def _fetch_bytes_in_page(self, url):
        """在页面里 fetch（带登录态）拿字节，base64 传回。"""
        res = self.cdp.evaluate("""
        (async () => {
          try {
            const r = await fetch(%s, { credentials: 'include' });
            if (!r.ok) return { status: r.status, b64: null };
            const buf = new Uint8Array(await r.arrayBuffer());
            let bin = '';
            const chunk = 0x8000;
            for (let i = 0; i < buf.length; i += chunk) {
              bin += String.fromCharCode.apply(null, buf.subarray(i, i + chunk));
            }
            return { status: r.status, b64: btoa(bin) };
          } catch (e) { return { status: 0, b64: null, err: String(e) }; }
        })()
        """ % json.dumps(url), timeout_ms=120000)
        if not res or not res.get("b64"):
            return None
        try:
            return base64.b64decode(res["b64"])
        except Exception:
            return None

    def receipt_pdf(self, trip_id):
        """非沙特国家没有发票文件：优先用弹窗里的「下载 PDF」（官方收据），
        拿不到再退回把弹窗打印成 PDF。"""
        if not self._open_receipt(trip_id):
            return None
        href = self._find_receipt_pdf_href()
        if href:
            from urllib.parse import urljoin
            url = urljoin("https://riders.uber.com", href)
            blob = self._fetch_bytes_in_page(url)
            if blob and blob[:4] == b"%PDF":
                return blob
        # 兜底：打印弹窗
        return self._print_receipt_pdf()

    def _print_receipt_pdf(self):
        box = self.cdp.evaluate("""
        (() => {
          const el = document.querySelector('[role=dialog]')
            || document.querySelector('[class*=modal]')
            || document.querySelector('[class*=receipt]');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { w: Math.round(r.width), h: Math.round(r.height + 60) };
        })()
        """, await_promise=False, timeout_ms=15000)
        w_in, h_in = 4.2, 7.5
        try:
            if box and box.get("w") and box.get("h"):
                w_in = max(3.0, min(6.5, box["w"] / 96 + 0.4))
                h_in = max(3.0, min(16.0, box["h"] / 96 + 0.4))
        except Exception:
            pass
        res = self.cdp._send("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": w_in, "paperHeight": h_in,
            "marginTop": 0.15, "marginBottom": 0.15,
            "marginLeft": 0.15, "marginRight": 0.15,
        })
        data = base64.b64decode(res.get("data") or "")
        return data if data[:4] == b"%PDF" else None

    def invoice_urls(self, ids, progress=None):
        result = {}
        for i in range(0, len(ids), 8):
            chunk = ids[i:i + 8]
            js = INVOICE_JS % {"query": json.dumps(INVOICE_QUERY), "ids": json.dumps(chunk)}
            got = self.cdp.evaluate(js, timeout_ms=180000) or []
            for tid, url in got:
                result[tid] = url
            if progress:
                progress(min(len(ids), i + len(chunk)), len(ids))
            if i + 8 < len(ids):
                jitter(0.4, 1.0)
        return result

    def _fetch_one(self, t, url, note=None):
        """取单条的文件内容；限流与网络错误分则处理。
        返回 (blob, err_text, kind)，kind 为 ok / nofile / rate / net / other。"""
        n_rate = n_net = n_other = 0
        while True:
            try:
                if url:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        blob = r.read()
                    if not blob[:4] == b"%PDF":
                        raise RuntimeError(T("not_pdf"))
                    return blob, "", "ok"
                blob = self.receipt_pdf(t.id)
                if blob and blob[:4] == b"%PDF":
                    return blob, "", "ok"
                return None, T("no_file_region"), "nofile"
            except Exception as e:
                kind = classify_error(e)
                err = str(e)[:90]
                if kind == "rate":
                    if n_rate >= DL_RATE_RETRIES:
                        return None, err, "rate"
                    delay = DL_RATE_BACKOFF[min(n_rate, len(DL_RATE_BACKOFF) - 1)]
                    n_rate += 1
                    total = DL_RATE_RETRIES
                    cur = n_rate
                elif kind == "net":
                    if n_net >= DL_NET_RETRIES:
                        return None, err, "net"
                    delay = DL_NET_BACKOFF[min(n_net, len(DL_NET_BACKOFF) - 1)]
                    n_net += 1
                    total = DL_NET_RETRIES
                    cur = n_net
                else:
                    if n_other >= DL_OTHER_RETRIES:
                        return None, err, "other"
                    delay = 2
                    n_other += 1
                    total = DL_OTHER_RETRIES
                    cur = n_other
                if note:
                    label = (T("retry_kind_rate") if kind == "rate"
                             else T("retry_kind_net") if kind == "net"
                             else T("retry_kind_other"))
                    note(T("retry_note", k=label, a=cur, b=total, s=delay, e=err))
                time.sleep(delay)

    def download(self, trips, urls, outdir: Path, progress=None, note=None):
        outdir.mkdir(parents=True, exist_ok=True)
        ok, skipped, failed, receipts = [], [], [], []
        self.abort_reason = ""
        self.abort_kind = ""
        self.not_attempted = 0
        streak_rate = streak_net = 0
        for idx, t in enumerate(trips, 1):
            url = urls.get(t.id)
            name = f"{T('receipt_prefix')}{t.date.isoformat()}_{t.currency}{t.amount}.pdf"
            blob, err, kind = self._fetch_one(t, url, note=note)
            if blob is None:
                if kind == "nofile":
                    skipped.append((name, err or T("no_file_region")))
                else:
                    failed.append((name, err))
                    if kind == "rate":
                        streak_rate += 1
                        streak_net = 0
                    else:
                        streak_net += 1
                        streak_rate = 0
                    if streak_rate >= DL_RATE_STREAK or streak_net >= DL_NET_STREAK:
                        self.abort_reason = err or "error"
                        self.abort_kind = "rate" if streak_rate >= DL_RATE_STREAK else "net"
                        self.not_attempted = len(trips) - idx
                        if progress:
                            progress(idx, len(trips))
                        break
            else:
                target = outdir / name
                n = 2
                while target.exists():
                    target = outdir / f"{name[:-4]}({n}).pdf"
                    n += 1
                try:
                    target.write_bytes(blob)
                    ok.append(name)
                    if not url:
                        receipts.append(name)
                    streak_rate = streak_net = 0
                except Exception as e:
                    failed.append((name, str(e)[:80]))
                    streak_net += 1
            if progress:
                progress(idx, len(trips))
            if idx < len(trips):
                jitter()
        return ok, skipped, failed, receipts


# --------------------------------------------------------------------------
# 日历弹窗
# --------------------------------------------------------------------------
class CalendarPopup(tk.Toplevel):
    """点一下日期按钮弹出的小日历。"""

    def __init__(self, master, initial: date, on_pick):
        super().__init__(master)
        self.on_pick = on_pick
        self.view = date(initial.year, initial.month, 1)
        self.selected = initial
        self.title(T("cal_title"))
        self.overrideredirect(True)
        self.configure(bg=C_LINE)
        self.attributes("-topmost", True)
        self._build()
        self._place_near(master)
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    # --- 定位到按钮下方 ---
    def _place_near(self, anchor):
        try:
            self.update_idletasks()
            x = anchor.winfo_rootx()
            y = anchor.winfo_rooty() + anchor.winfo_height() + 2
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if x + w > sw - 8:
                x = sw - w - 8
            if y + h > sh - 40:
                y = anchor.winfo_rooty() - h - 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build(self):
        body = tk.Frame(self, bg=C_PANEL, bd=0, highlightthickness=1,
                        highlightbackground=C_LINE)
        body.pack(padx=1, pady=1)

        head = tk.Frame(body, bg=C_PANEL)
        head.pack(fill="x", padx=6, pady=(6, 2))
        # 先摆两侧按钮，再放中间月份，左右对称
        left_box = tk.Frame(head, bg=C_PANEL)
        left_box.pack(side="left")
        right_box = tk.Frame(head, bg=C_PANEL)
        right_box.pack(side="right")
        self.month_lbl = tk.Label(head, bg=C_PANEL, fg=C_TEXT,
                                  font=("Microsoft YaHei UI", 10, "bold"))
        self.month_lbl.pack(side="left", expand=True, fill="x")
        self._nav_btn(left_box, "«", lambda: self._shift(-12)).pack(side="left")
        self._nav_btn(left_box, "‹", lambda: self._shift(-1)).pack(side="left")
        self._nav_btn(right_box, "›", lambda: self._shift(1)).pack(side="left")
        self._nav_btn(right_box, "»", lambda: self._shift(12)).pack(side="left")

        grid = tk.Frame(body, bg=C_PANEL)
        grid.pack(padx=6, pady=(2, 6))
        for i, wd in enumerate(weekdays()):
            tk.Label(grid, text=wd, bg=C_PANEL, fg=C_SUB, width=3,
                     font=("Microsoft YaHei UI", 8)).grid(row=0, column=i, pady=(0, 2))

        self.day_cells = []
        for r in range(1, 7):
            row = []
            for c in range(7):
                b = tk.Label(grid, text="", width=3, bg=C_PANEL, fg=C_TEXT, anchor="center",
                             justify="center", font=("Microsoft YaHei UI", 9), cursor="hand2")
                b.grid(row=r, column=c, padx=1, pady=1, ipady=2)
                b.bind("<Button-1>", self._pick)
                row.append(b)
            self.day_cells.append(row)

        foot = tk.Frame(body, bg=C_PANEL)
        foot.pack(fill="x", padx=6, pady=(0, 6))
        quick = tk.Label(foot, text=T("cal_today"), bg="#e6eefb", fg="#0a4eba", cursor="hand2",
                         font=("Microsoft YaHei UI", 9), padx=10, pady=2)
        quick.pack(side="left")
        quick.bind("<Button-1>", lambda e: self._choose(date.today()))
        tk.Label(foot, text=T("cal_esc"), bg=C_PANEL, fg="#9aa8bb",
                 font=("Microsoft YaHei UI", 8)).pack(side="right")

        self._render()

    def _nav_btn(self, parent, text, cmd):
        lbl = tk.Label(parent, text=text, bg=C_PANEL, fg="#0a4eba", width=2,
                       cursor="hand2", font=("Microsoft YaHei UI", 10))
        lbl.bind("<Button-1>", lambda e: cmd())
        lbl.bind("<Enter>", lambda e: lbl.configure(bg="#e6eefb"))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=C_PANEL))
        return lbl

    def _shift(self, months):
        y = self.view.year + (self.view.month - 1 + months) // 12
        m = (self.view.month - 1 + months) % 12 + 1
        self.view = date(y, m, 1)
        self._render()

    def _render(self):
        self.month_lbl.configure(text=month_title(self.view.year, self.view.month))
        today = date.today()
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.view.year, self.view.month)
        for r in range(6):
            for c in range(7):
                cell = self.day_cells[r][c]
                if r < len(weeks) and c < len(weeks[r]):
                    d = weeks[r][c]
                    cell.configure(text=str(d.day))
                    cell._date = d
                    if d == self.selected:
                        cell.configure(bg="#1a73e8", fg="white")
                    elif d.month != self.view.month:
                        cell.configure(bg=C_PANEL, fg="#c2cad6")
                    elif d == today:
                        cell.configure(bg="#e6f0ff", fg="#0a4eba")
                    else:
                        cell.configure(bg=C_PANEL, fg=C_TEXT)
                else:
                    cell.configure(text="", bg=C_PANEL)
                    cell._date = None

    def _pick(self, event):
        d = getattr(event.widget, "_date", None)
        if d:
            self._choose(d)

    def _choose(self, d: date):
        self.on_pick(d)
        self.destroy()


class DateField(tk.Frame):
    """显示日期 + 点开日历的字段。"""

    def __init__(self, master, value: date, on_change=None):
        super().__init__(master, bg=C_BG)
        self._value = value
        self.on_change = on_change
        self.btn = tk.Label(self, text="", bg="#ffffff", fg=C_TEXT, anchor="w", padx=8, pady=3,
                            cursor="hand2", font=("Microsoft YaHei UI", 9),
                            highlightthickness=1, highlightbackground=C_LINE)
        self.btn.pack(side="left")
        self.btn.bind("<Button-1>", self._open)
        self._refresh()

    @property
    def value(self):
        return self._value

    def set(self, d: date, fire=True):
        self._value = d
        self._refresh()
        if fire and self.on_change:
            self.on_change(d)

    def _refresh(self):
        self.btn.configure(text=f"📅  {self._value.isoformat()}  ▾")

    def _open(self, _event=None):
        CalendarPopup(self, self._value, self.set)


# --------------------------------------------------------------------------
# 主界面
# --------------------------------------------------------------------------
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{app_name()} v{APP_VER}")
        self.root.geometry("1120x700")
        self.root.minsize(940, 560)
        self.root.configure(bg=C_BG)

        self.trips = []
        self.rows = []           # 当前显示的 trip 下标
        self.worker = UberWorker(log=self.set_status)
        self.busy = False
        self.sort_key = None
        self.sort_reverse = True
        self.truncated = False
        self._flag_cache = {}
        self._cell_cache = {}
        self.outdir = tk.StringVar()

        s = self._load_settings()
        today = date.today()
        first = today.replace(day=1)
        self.start_date = date.fromisoformat(s.get("start") or first.isoformat())
        self.end_date = date.fromisoformat(s.get("end") or today.isoformat())
        self.outdir.set(s.get("outdir") or str(Path.home() / "Documents" / T("default_dir")))

        self.browsers, self.tried_paths = detect_browsers()
        GET_TRIED_PATHS[:] = list(self.tried_paths)
        self.browser_choice = s.get("browser") or ""      # 空 = 自动
        self.sel_browser_var = tk.StringVar()
        self.sel_browser_var.set(self._label_of(self.browser_choice) or AUTO_LABEL)

        self._init_style()
        self._load_check_images()
        self._load_btn_icons()
        self._build_banner()
        self._build_toolbar()
        self._build_table()
        self._build_summary()
        self._build_status()
        self._refresh_summary()

    # ---------- 浏览器 ----------
    def _label_of(self, key):
        for k, label, _p in self.browsers:
            if k == key:
                return label
        return None

    def _browser_labels(self):
        return [AUTO_LABEL] + [label for _k, label, _p in self.browsers]

    def _on_browser_change(self, _evt=None):
        label = self.sel_browser_var.get()
        self.browser_choice = "" if label == AUTO_LABEL else next(
            (k for k, lab, _p in self.browsers if lab == label), "")
        self._save_settings()
        cur = self._resolve_browser()
        self.set_status(T("will_use", b=cur[1], p=profile_dir_for(cur[0]).name))

    def _resolve_browser(self):
        if not self.browsers:
            tried = "\n".join(GET_TRIED_PATHS) or T("no_tried")
            raise RuntimeError(T("no_browser", t=tried))
        if self.browser_choice:
            for k, label, path in self.browsers:
                if k == self.browser_choice:
                    return (k, label, path)
            self.set_status(T("fallback_auto"))
        return self.browsers[0]

    # ---------- 设置 ----------
    def _load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_settings(self):
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps({
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
                "outdir": self.outdir.get(),
                "browser": self.browser_choice,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- 样式 ----------
    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        base = ("Microsoft YaHei UI", 9)
        st.configure(".", font=base, background=C_BG, foreground=C_TEXT)
        st.configure("TFrame", background=C_BG)
        st.configure("TLabel", background=C_BG, foreground=C_TEXT)
        st.configure("Tool.TButton", background="#ffffff", foreground=C_TEXT, padding=(10, 5),
                     borderwidth=1, relief="flat", focusthickness=0)
        st.map("Tool.TButton",
               background=[("active", "#e8f0fd"), ("pressed", "#d8e6fb")],
               bordercolor=[("!disabled", C_LINE)])
        st.configure("Primary.TButton", background="#1a73e8", foreground="#ffffff",
                     padding=(14, 6), borderwidth=1, relief="solid", bordercolor="#1667d2")
        st.map("Primary.TButton",
               background=[("active", "#1667d2"), ("pressed", "#1157b3")],
               bordercolor=[("!disabled", "#1667d2")])

        # 彩色次要按钮（图标 + 淡色底 + 描边，比普通工具栏按钮更突出）
        for name, bg, bd, fg, hover in (
            ("Green", "#e9f7ee", "#a9d9bd", "#186c3a", "#d7efe1"),
            ("Red", "#fdeeec", "#efc3bb", "#a5332a", "#f9dcd7"),
            ("Amber", "#fdf4e5", "#ecd5a9", "#8a5a10", "#f8e6c9"),
        ):
            st.configure(f"{name}.TButton", background=bg, foreground=fg, bordercolor=bd,
                         padding=(12, 6), borderwidth=1, relief="solid", focusthickness=0)
            st.map(f"{name}.TButton",
                   background=[("active", hover), ("pressed", hover)],
                   bordercolor=[("!disabled", bd)])

        # Win11 风下拉框：白底、细描边、聚焦变蓝
        st.configure("Modern.TCombobox", fieldbackground="#ffffff", background="#ffffff",
                     foreground=C_TEXT, arrowcolor="#54657e", bordercolor=C_LINE,
                     lightcolor="#ffffff", darkcolor="#ffffff", insertcolor=C_TEXT,
                     padding=(10, 5), relief="solid", borderwidth=1)
        st.map("Modern.TCombobox",
               fieldbackground=[("readonly", "#ffffff")],
               bordercolor=[("focus", "#1a73e8"), ("hover", "#9db8de"), ("!disabled", C_LINE)],
               arrowcolor=[("active", "#1a73e8")])
        self.root.option_add("*TCombobox*Listbox.background", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.foreground", C_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#e8f1ff")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#0a3d91")
        self.root.option_add("*TCombobox*Listbox.font", base)
        self.root.option_add("*TCombobox*Listbox.borderWidth", 0)
        st.configure("Data.Treeview", background=C_PANEL, fieldbackground=C_PANEL,
                     foreground=C_TEXT, rowheight=27, borderwidth=0, font=base)
        st.configure("Data.Treeview.Heading", background=C_HEAD_BG, foreground="#22364f",
                     font=("Microsoft YaHei UI", 9, "bold"), relief="flat", padding=(6, 5))
        st.map("Data.Treeview.Heading", background=[("active", "#d8e6fb")])
        st.map("Data.Treeview", background=[("selected", C_SEL)], foreground=[("selected", C_TEXT)])
        st.configure("Vertical.TScrollbar", background="#cfdcee", troughcolor=C_PANEL,
                     borderwidth=0, arrowsize=12)

    # ---------- 顶部蓝底标题 ----------
    def _build_banner(self):
        self.banner = tk.Canvas(self.root, height=66, bd=0, highlightthickness=0)
        self.banner.pack(fill="x")
        self.banner.bind("<Configure>", self._draw_banner)

    def _draw_banner(self, _event=None):
        cv = self.banner
        cv.delete("all")
        w = max(cv.winfo_width(), 600)
        h = 66
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(C_BANNER_TOP[0] + (C_BANNER_BOT[0] - C_BANNER_TOP[0]) * t)
            g = int(C_BANNER_TOP[1] + (C_BANNER_BOT[1] - C_BANNER_TOP[1]) * t)
            b = int(C_BANNER_TOP[2] + (C_BANNER_BOT[2] - C_BANNER_TOP[2]) * t)
            cv.create_line(0, y, w, y, fill=f"#{r:02x}{g:02x}{b:02x}")
        cv.create_text(22, h // 2, text=app_name(), anchor="w", fill="#ffffff",
                       font=("Microsoft YaHei UI", 17, "bold"))
        cv.create_text(w - 22, h // 2 - 10, text=f"v{APP_VER}", anchor="e", fill="#e8f1ff",
                       font=("Microsoft YaHei UI", 9))
        cv.create_text(w - 22, h // 2 + 10, text=T("author", a=APP_AUTHOR), anchor="e",
                       fill="#d6e6ff", font=("Microsoft YaHei UI", 9))

    # ---------- 工具条 ----------
    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=C_PANEL, highlightthickness=1, highlightbackground=C_LINE)
        bar.pack(fill="x")

        inner = tk.Frame(bar, bg=C_PANEL)
        inner.pack(fill="x", padx=10, pady=8)

        # 右上：浏览器选择（先 pack 右侧，窗口变窄时不会被挤掉）
        right = tk.Frame(inner, bg=C_PANEL)
        right.pack(side="right")
        tk.Label(right, text=T("browser"), bg=C_PANEL, fg=C_SUB,
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 6))
        self.browser_combo = ttk.Combobox(right, textvariable=self.sel_browser_var,
                                          state="readonly", style="Modern.TCombobox",
                                          width=16, values=self._browser_labels())
        self.browser_combo.pack(side="left")
        self.browser_combo.bind("<<ComboboxSelected>>", self._on_browser_change)

        tk.Label(inner, text=T("from"), bg=C_PANEL, fg=C_SUB,
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.f_start = DateField(inner, self.start_date)
        self.f_start.pack(side="left", padx=(4, 1))
        tk.Label(inner, text=T("to"), bg=C_PANEL, fg=C_SUB,
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(8, 0))
        self.f_end = DateField(inner, self.end_date)
        self.f_end.pack(side="left", padx=(4, 10))

        self.btn_load = ttk.Button(inner, text=T("load"), style="Primary.TButton",
                                   command=self.on_load)
        self.btn_load.pack(side="left")

        tk.Frame(inner, bg=C_LINE, width=1, height=24).pack(side="left", padx=12, fill="y")

        self.btn_all = ttk.Button(inner, text=T("all"), image=self.ico_all, compound="left",
                                  style="Green.TButton", command=lambda: self.set_all(True))
        self.btn_all.pack(side="left", padx=(0, 6))
        self.btn_none = ttk.Button(inner, text=T("none"), image=self.ico_none, compound="left",
                                   style="Red.TButton", command=lambda: self.set_all(False))
        self.btn_none.pack(side="left", padx=(0, 6))
        self.btn_clear = ttk.Button(inner, text=T("clear"), image=self.ico_clear, compound="left",
                                    style="Amber.TButton", command=self.clear_list)
        self.btn_clear.pack(side="left")

    # ---------- 表格 ----------
    def _load_btn_icons(self):
        self.ico_all = tk.PhotoImage(file=resource_path("btn_all.png"))
        self.ico_none = tk.PhotoImage(file=resource_path("btn_none.png"))
        self.ico_clear = tk.PhotoImage(file=resource_path("btn_clear.png"))

    def _load_check_images(self):
        """三态复选框位图（未选 / 选中 / 禁用）。"""
        self.img_off = tk.PhotoImage(file=resource_path("chk_off.png"))
        self.img_on = tk.PhotoImage(file=resource_path("chk_on.png"))
        self.img_dis = tk.PhotoImage(file=resource_path("chk_disabled.png"))

    def _build_table(self):
        wrap = tk.Frame(self.root, bg=C_BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        cols = ("date", "time", "amount", "place", "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings", style="Data.Treeview",
                                 selectmode="browse")
        self.tree.heading("#0", text=T("col_pick"))
        self.tree.column("#0", width=46, anchor="center", stretch=False)
        heads = {
            "date": (T("col_date"), 110),
            "time": (T("col_time"), 100),
            "amount": (T("col_amount"), 100),
            "place": (T("col_place"), 470),
            "status": (T("col_status"), 100),
        }
        for c in cols:
            title, w = heads[c]
            self.tree.heading(c, text=title, command=lambda cc=c: self.sort_by(cc))
            self.tree.column(c, width=w, anchor="center" if c != "place" else "w",
                             stretch=(c == "place"))
        self.tree.tag_configure("odd", background=C_PANEL)
        self.tree.tag_configure("even", background=C_STRIPE)
        self.tree.tag_configure("picked", background="#e8f1ff")
        self.tree.tag_configure("off", foreground="#9aa8bb")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview,
                            style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.bind("<Button-1>", self.on_tree_click)

        # 空状态提示
        self.empty_hint = tk.Label(wrap, bg=C_PANEL, fg="#9aa8bb", justify="center",
                                   font=("Microsoft YaHei UI", 10),
                                   text=T("empty"))
        self.empty_hint.place(relx=0.5, rely=0.45, anchor="center")

    # ---------- 统计条 ----------
    def _build_summary(self):
        bar = tk.Frame(self.root, bg="#e9f0fb", highlightthickness=1, highlightbackground=C_LINE)
        bar.pack(fill="x", padx=10, pady=(6, 0))
        inner = tk.Frame(bar, bg="#e9f0fb")
        inner.pack(fill="x", padx=10, pady=6)

        self.sel_box = tk.Frame(inner, bg="#e9f0fb")
        self.sel_box.pack(side="left")
        self.lbl_sel = tk.Label(self.sel_box, text=T("sel_none"), bg="#e9f0fb", fg="#0a3d91",
                                font=("Microsoft YaHei UI", 9, "bold"))
        self.lbl_sel.pack(side="left")

        tk.Label(inner, text=T("dl_to"), bg="#e9f0fb", fg=C_SUB,
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(18, 4))
        self.dir_entry = tk.Entry(inner, textvariable=self.outdir, relief="flat",
                                  bg="#ffffff", fg=C_TEXT, font=("Microsoft YaHei UI", 9),
                                  highlightthickness=1, highlightbackground=C_LINE)
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=3)
        ttk.Button(inner, text=T("choose"), style="Tool.TButton",
                   command=self.pick_dir).pack(side="left", padx=6)
        self.btn_dl = ttk.Button(inner, text=T("download"), style="Primary.TButton",
                                 command=self.on_download)
        self.btn_dl.pack(side="left")

    def _build_status(self):
        bar = tk.Frame(self.root, bg=C_PANEL, highlightthickness=1, highlightbackground=C_LINE)
        bar.pack(fill="x", side="bottom")
        self.status = tk.StringVar(value=T("status_init"))
        tk.Label(bar, textvariable=self.status, bg=C_PANEL, fg="#33455c", anchor="w",
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=10, pady=6)
        self.lbl_total = tk.Label(bar, text="", bg=C_PANEL, fg=C_SUB,
                                  font=("Microsoft YaHei UI", 9))
        self.lbl_total.pack(side="right", padx=10)

    # ---------- 交互 ----------
    def set_status(self, text):
        self.status.set(text)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get() or str(Path.home()))
        if d:
            self.outdir.set(d)
            self._save_settings()

    def clear_list(self):
        self.trips = []
        self._render()
        self._refresh_summary()

    def sort_by(self, col):
        keys = {
            "date": lambda i: (self.trips[i].date, self.trips[i].time),
            "time": lambda i: self.trips[i].time,
            "amount": lambda i: self.trips[i].amount_value,
            "place": lambda i: self.trips[i].place,
            "status": lambda i: self.trips[i].status,
        }
        if col not in keys:
            return
        self.sort_reverse = not self.sort_reverse if self.sort_key == col else True
        self.sort_key = col
        self.trips.sort(key=keys[col], reverse=self.sort_reverse)
        self._render()

    def on_tree_click(self, event):
        # tree 列的 identify_region 是 "tree"而不是 "cell"，不能按区域判，只看列
        if self.tree.identify_column(event.x) != "#0":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self._toggle(int(iid))

    def on_tree_double(self, event):
        # 保留占位：单击已能切换，双击不再绑定（否则两次切换互相抵消）
        return

    def _toggle(self, idx):
        t = self.trips[idx]
        if not t.has_invoice:
            self.set_status(f"{t.date} {t.currency}{t.amount} — {status_label(t)}")
            return
        t.selected = not t.selected
        self._render()
        self._refresh_summary()

    def _row_image(self, t):
        """第一列图：勾选框 + 币种国旗拼成的一张图（Treeview 只有树列能放图）。"""
        if not t.has_invoice:
            state = "dis"
        else:
            state = "on" if t.selected else "off"
        return self._cell_img(t.currency, state)

    def _cell_img(self, currency, state):
        key = ((currency or "").upper(), state)
        if key in self._cell_cache:
            return self._cell_cache[key]
        img = None
        for name in (f"cell_{key[0]}_{state}.png", f"cell_OTHER_{state}.png"):
            try:
                img = tk.PhotoImage(file=resource_path(os.path.join("cells", name)))
                break
            except Exception:
                continue
        if img is None:      # 极端情况：没打包成功，退回纯勾选框
            img = {"on": self.img_on, "off": self.img_off}.get(state, self.img_dis)
        self._cell_cache[key] = img
        return img

    def set_all(self, value):
        for t in self.trips:
            if t.has_invoice and self._visible(t):
                t.selected = value
        self._render()
        self._refresh_summary()

    def _visible(self, t):
        return True

    def _render(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        n = 0
        for i, t in enumerate(self.trips):
            if not self._visible(t):
                continue
            n += 1
            if t.selected:
                tags = ["picked"]
            else:
                tags = ["odd" if n % 2 else "even"]
            if not t.has_invoice:
                tags.append("off")
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             image=self._row_image(t), values=(
                                 t.date.isoformat(),
                                 t.time,
                                 f"{t.currency}{t.amount}",
                                 t.place,
                                 status_label(t),
                             ))
            self.rows.append(i)
        self._update_empty()

    def _update_empty(self):
        try:
            if self.rows:
                self.empty_hint.place_forget()
                return
            if self.trips:
                self.empty_hint.configure(text=T("empty_filtered"))
            else:
                self.empty_hint.configure(text=T("empty"))
            self.empty_hint.place(relx=0.5, rely=0.45, anchor="center")
        except Exception:
            pass

    def _refresh_summary(self):
        sel = [t for t in self.trips if t.selected and t.has_invoice]
        self._render_sel_summary(sel)
        have = sum(1 for t in self.trips if t.has_invoice)
        if self.trips:
            shown = len(self.rows)
            self.lbl_total.configure(
                text=T("total", n=len(self.trips), m=have) +
                     (T("shown", k=shown) if shown != len(self.trips) else ""))
        else:
            self.lbl_total.configure(text=T("total0"))

    def _flag_img(self, currency):
        """货币对应的小国旗；没收录的货币用灰底占位图。"""
        key = (currency or "").upper()
        if key in self._flag_cache:
            return self._flag_cache[key]
        img = None
        for name in (f"flag_{key}.png", "flag_OTHER.png"):
            try:
                img = tk.PhotoImage(file=resource_path(name))
                break
            except Exception:
                continue
        self._flag_cache[key] = img
        return img

    def _render_sel_summary(self, sel):
        """按货币分组统计（AED 不跟 SAR 相加），每种货币前加国旗。"""
        for w in self.sel_box.winfo_children():
            w.destroy()
        tk.Label(self.sel_box, text=T("sel_n", n=len(sel)), bg="#e9f0fb", fg="#0a3d91",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
        if not sel:
            return
        groups = {}
        for t in sel:
            cur = (t.currency or "?").upper()
            g = groups.setdefault(cur, [0.0, 0])
            g[0] += t.amount_value
            g[1] += 1
        # 里亚尔排最前（本地主用），其余按金额降序
        for cur in sorted(groups, key=lambda c: (c != "SAR", -groups[c][0])):
            total, cnt = groups[cur]
            txt = f"{cur} {total:,.2f}" if cnt == 1 else f"{cur} {total:,.2f} ({cnt})"
            tk.Label(self.sel_box, text=" " + txt, image=self._flag_img(cur),
                     compound="left", bg="#e9f0fb", fg="#0a3d91",
                     font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(12, 0))

    def _set_busy(self, busy):
        self.busy = busy
        state = ["disabled"] if busy else ["!disabled"]
        for b in (self.btn_load, self.btn_dl, self.btn_all, self.btn_none, self.btn_clear):
            try:
                b.state(state)
            except Exception:
                pass

    def _run(self, fn):
        if self.busy:
            messagebox.showinfo(T("busy_title"), T("busy_msg"))
            return
        self._set_busy(True)

        def wrapper():
            try:
                fn()
            except Exception as e:
                self.set_status(T("err", m=str(e)[:200]))
                self.root.after(0, lambda: messagebox.showerror(T("err_title"), str(e)[:600]))
            finally:
                self._set_busy(False)

        threading.Thread(target=wrapper, daemon=True).start()

    # ---------- 演示数据（仅开发调试用） ----------
    def _demo_fill(self):
        pm, am = ("PM", "AM") if LANG == "en" else ("下午", "上午")
        samples = [
            ("a1", "2026-11-23", f"{pm}4:30", "SAR", "44.10", "Golden Dragon", ""),
            ("a2", "2026-11-23", f"{am}9:08", "SAR", "28.65", "6934 شارع العليا", ""),
            ("a3", "2026-11-22", f"{pm}4:33", "SAR", "43.27", "Golden Dragon", ""),
            ("a4", "2026-09-12", f"{am}9:27", "SAR", "104.26", "6913 An Nadir", ""),
            ("a5", "2026-09-11", f"{am}9:30", "AED", "148.19", "Marina Beach", ""),
            ("a6", "2026-09-10", f"{pm}6:38", "SAR", "38.93", "6913 An Nadir", ""),
            ("a7", "2026-09-09", f"{pm}6:21", "SAR", "50.50", "6913 An Nadir", ""),
            ("a8", "2026-10-08", f"{pm}4:23", "SAR", "0.00", "6913 An Nadir", "incomplete"),
        ]
        self.trips = []
        for tid, d, tm, cur, amt, place, st in samples:
            t = Trip(tid, date.fromisoformat(d), tm, cur, amt, place, st)
            self.trips.append(t)
        for i in (3, 4, 5, 6):      # 复现混合币种场景：SAR×3 + AED×1
            self.trips[i].selected = True
        self._render()
        self._refresh_summary()
        self.set_status("8 trips / 7 downloadable (demo data)" if LANG == "en"
                        else "读取完成：8 条行程，其中 7 条有发票。（演示数据）")

    # ---------- 主流程 ----------
    def _ask_on_ui(self, title, message, default=False):
        """从工作线程弹一个同步确认框（工作线程等结果）。"""
        box = {"v": default}
        ev = threading.Event()

        def ui():
            try:
                box["v"] = messagebox.askyesno(title, message, parent=self.root)
            finally:
                ev.set()

        self.root.after(0, ui)
        ev.wait()
        return box["v"]

    def _open_folder(self, folder):
        try:
            p = Path(folder)
            p.mkdir(parents=True, exist_ok=True)
            os.startfile(str(p))
        except Exception as e:
            messagebox.showerror(T("no_open"), f"{folder}\n\n{e}")

    def _show_result(self, lines, folder):
        """下载完成弹窗：带「打开文件夹」按钮。"""
        top = tk.Toplevel(self.root)
        top.title(T("dl_title"))
        top.configure(bg=C_PANEL)
        top.transient(self.root)
        top.resizable(False, False)

        body = tk.Frame(top, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        tk.Label(body, text=T("dl_head"), bg=C_PANEL, fg="#0a3d91", anchor="w",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(fill="x")
        for line in lines:
            tk.Label(body, text=line, bg=C_PANEL, fg=C_TEXT, anchor="w", justify="left",
                     wraplength=460, font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=(6, 0))
        tk.Label(body, text=T("dir_line", d=folder), bg=C_PANEL, fg=C_SUB, anchor="w", justify="left",
                 wraplength=460, font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=(10, 0))

        btns = tk.Frame(body, bg=C_PANEL)
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text=T("close"), style="Tool.TButton",
                   command=top.destroy).pack(side="right")
        ttk.Button(btns, text=T("open_dir"), style="Primary.TButton",
                   command=lambda: (self._open_folder(folder), top.destroy())).pack(side="right", padx=(0, 8))

        top.bind("<Escape>", lambda e: top.destroy())
        top.update_idletasks()
        try:
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            w, h = top.winfo_reqwidth(), top.winfo_reqheight()
            top.geometry(f"+{rx + (rw - w) // 2}+{ry + (rh - h) // 3}")
        except Exception:
            pass
        top.grab_set()
        top.focus_force()

    def on_load(self):
        self.start_date = self.f_start.value
        self.end_date = self.f_end.value
        if self.start_date > self.end_date:
            messagebox.showerror(T("date_bad"), T("date_bad_msg"))
            return

        def job():
            self._save_settings()
            browser = self._resolve_browser()
            self.set_status(T("opening", b=browser[1]))
            self.worker.open_browser(browser)
            if not self.worker.is_logged_in():
                self.set_status(T("need_login"))
                self.root.after(0, lambda: messagebox.showinfo(
                    T("need_login_title"), T("need_login_body")))
                return
            self.set_status(T("preparing"))
            self.worker.goto_trips()

            def on_progress(count, oldest, secs):
                d = _from_yyyymmdd(oldest) if oldest else None
                self.set_status(T("reading", n=count, d=d or "—", s=secs))

            def on_limit(count, oldest):
                d = _from_yyyymmdd(oldest) if oldest else None
                return self._ask_on_ui(
                    T("limit_title", n=count),
                    T("limit_body", n=count, d=d or "—", lim=TRIP_LIMIT))

            trips, truncated = self.worker.list_trips(
                self.start_date, self.end_date,
                on_progress=on_progress, on_limit=on_limit, limit=TRIP_LIMIT,
                note=lambda m: self.set_status(m))
            self.trips = trips
            self.truncated = truncated
            self.root.after(0, self._after_load)

        self._run(job)

    def _after_load(self):
        self._render()
        self._refresh_summary()
        have = sum(1 for t in self.trips if t.has_invoice)
        warn = ""
        if getattr(self.worker, "last_stalled", False):
            warn = T("stalled")
        if getattr(self, "truncated", False) and self.trips:
            edge = self.trips[-1].date.isoformat()
            self.set_status(T("done_trunc", n=len(self.trips), d=edge, m=have, w=warn))
        else:
            self.set_status(T("done", n=len(self.trips), m=have, w=warn))

    def on_download(self):
        sel = [t for t in self.trips if t.selected and t.has_invoice]
        if not sel:
            messagebox.showinfo(T("nothing_sel"), T("nothing_sel_msg"))
            return
        if len(sel) > CONFIRM_DOWNLOAD_OVER:
            est = max(1, round(len(sel) * 0.5))
            if not messagebox.askyesno(T("confirm_dl"), T("confirm_dl_msg", n=len(sel), s=est)):
                return
        outdir = Path(self.outdir.get().strip()
                      or (Path.home() / "Documents" / T("default_dir")))
        self._save_settings()

        def job():
            browser = self._resolve_browser()
            self.worker.open_browser(browser)
            if not self.worker.is_logged_in():
                self.set_status(T("login_gone"))
                return
            self.worker.goto_trips()
            self.set_status(T("getting", n=len(sel)))
            urls = self.worker.invoice_urls([t.id for t in sel],
                                            progress=lambda a, b: self.set_status(T("urls", a=a, b=b)))
            self.set_status(T("dl_ing", d=outdir) + "　" + T("noclose"))
            ok, skipped, failed, receipts = self.worker.download(
                sel, urls, outdir,
                progress=lambda a, b: self.set_status(
                    T("dl_n", a=a, b=b) + T("noclose_short")),
                note=lambda m: self.set_status(m))
            lines = [T("ok_n", n=len(ok))]
            if receipts:
                lines.append(T("receipt_n", n=len(receipts)))
            sep = "、" if LANG == "zh" else ", "
            if skipped:
                lines.append(T("miss_n", n=len(skipped), lst=sep.join(n for n, _ in skipped[:4])))
            if failed:
                lines.append(T("fail_n", n=len(failed), lst=sep.join(n for n, _ in failed[:4])))
            if getattr(self.worker, "abort_reason", ""):
                if getattr(self.worker, "abort_kind", "") == "net":
                    lines.append(T("abort_net", n=DL_NET_STREAK, e=self.worker.abort_reason))
                else:
                    lines.append(T("abort_rate", n=DL_RATE_STREAK, e=self.worker.abort_reason))
                if getattr(self.worker, "not_attempted", 0):
                    lines.append(T("left_line", n=self.worker.not_attempted))
            self.set_status(T("dl_done", msg=("；" if LANG == "zh" else "; ").join(lines), d=outdir))
            self.root.after(0, lambda: self._show_result(lines, str(outdir)))

        self._run(job)


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def set_window_icon(root):
    """窗口 / 任务栏图标：用打包进去的 PNG，避免显示成 Tk 默认羽毛图标。"""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cindy.UberInvoice.Assistant")
    except Exception:
        pass
    for name in ("app_icon.png", "icon_preview.png"):
        try:
            img = tk.PhotoImage(file=resource_path(name))
            root.iconphoto(True, img)
            root._icon_ref = img  # 防止被回收
            return
        except Exception:
            continue
    try:
        root.iconbitmap(default=resource_path("icon.ico"))
    except Exception:
        pass


def main():
    set_language(detect_language())
    if websocket is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(T("missing_dep"), T("missing_dep_msg"))
        return
    root = tk.Tk()
    set_window_icon(root)
    app = App(root)
    if "--demo-calendar" in sys.argv:
        root.after(1200, lambda: app.f_start._open())
    if "--demo-data" in sys.argv:
        root.after(800, lambda: app._demo_fill())
    if "--demo-result" in sys.argv:
        root.after(900, lambda: app._demo_fill())
        root.after(1400, lambda: app._show_result(
            ["成功 4 个",
             "其中 1 个是该地区无发票文件、由网页收据生成的 PDF",
             "没拿到 1 条：Uber收据_2026-10-08_SAR0.00.pdf"],
            str(Path.home() / "Documents" / "Uber发票")))
    root.mainloop()


if __name__ == "__main__":
    main()
