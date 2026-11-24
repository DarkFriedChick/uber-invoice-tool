# -*- coding: utf-8 -*-
"""烟测：验证解析逻辑 + CDP 连接 + 登录态判断（不下载、不改任何票据）。"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uber_tool as U

print("== 解析逻辑 ==")
sample = [
    {"id": "a", "t": "Golden Dragon11月23日 • 下午4:30SAR44.10帮助详细信息"},
    {"id": "b", "t": "National Water Company (NWC)10月8日 • 上午9:11SAR26.07帮助"},
    {"id": "c", "t": "6913 An Nadir10月8日 • 下午4:23SAR0.00 • 未完成帮助"},
]
for t in U.parse_cards(sample):
    print(f"  {t.date} {t.time} {t.currency}{t.amount} status={t.status!r} 有发票={t.has_invoice} place={t.place!r}")

print("== CDP 连接 ==")
w = U.UberWorker(log=lambda m: print("  [log]", m))
w.open_browser()
print("  url =", w.cdp.current_url())
w.goto_trips()
print("  url(trips) =", w.cdp.current_url())
print("  logged_in =", w.is_logged_in())
w.cdp.close()
print("ok")
