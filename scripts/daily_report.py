#!/usr/bin/env python3
"""每日财经报告生成 - 供飞书推送
v2: 新增"较1月前"涨跌对比（dated 快照 ±7 天容错查找）"""
import json, os
from datetime import date, timedelta

DATA = "/home/node/.openclaw/workspace/www/caijin.gaozhong.online/data"
SITE = "http://caijin.gaozhong.online"
DAYS_AGO = 30
TOLERANCE = 7  # 快照日期容错范围 ±7 天

def load(path):
    try:
        with open(path) as f: return json.load(f)
    except: return {}

def nearest_snapshot(days_ago=DAYS_AGO, tol=TOLERANCE, prefix="baijiu"):
    """找距 (today - days_ago) 最近的 dated 快照；同偏移优先更早的日期"""
    target = date.today() - timedelta(days=days_ago)
    for off in range(0, tol + 1):
        for cand in (target - timedelta(off), target + timedelta(off)):
            p = os.path.join(DATA, prefix, cand.isoformat() + ".json")
            if os.path.exists(p):
                d = load(p)
                if d:
                    return cand.isoformat(), d
    return None, {}

def fmt_delta(cur, old, unit="¥", pp=False):
    """格式化差值: +2.2pp / -1.7 / +3.2% ；old 缺失返回 ''"""
    if cur is None or old is None:
        return ""
    d = round(cur - old, 1)
    if pp:
        sign = "+" if d >= 0 else ""
        return f"{sign}{d}pp"
    sign = "+" if d >= 0 else ""
    arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
    return f"{arrow}{abs(d)}" if not pp else f"{sign}{d}"

def fmt_cmp(cur, old, unit="¥", pct=False):
    """¥891(1月前 ¥1100,↓209) / $54.8(1月前 $52.7,+2.1/+4.0%) / 22.4%(1月前 20.8%,+1.6pp)"""
    if cur is None:
        return ""
    def _v(v):
        return f"{v}%" if unit == "%" else f"{unit}{v}"
    if old is None:
        return _v(cur)
    d = round(cur - old, 1)
    if pct:
        delta = f"{d:+.1f}/{(d / old * 100):+.1f}%" if old else f"{d:+.1f}"
    else:
        delta = fmt_delta(cur, old, pp=(unit == "%"))
    return f"{_v(cur)}(1月前 {_v(old)},{delta})"

def format_baijiu():
    d = load(os.path.join(DATA, "baijiu", "latest.json"))
    if not d: return "🍶 白酒: 数据获取失败"
    gj = d.get("guojiao1573", {})
    hist = d.get("priceHistory", [])
    retail = d.get("retailPrice", {})
    rp = retail.get("price")
    bp = gj.get("today", "?")
    bp_i = int(bp) if isinstance(bp, str) and bp.isdigit() else bp

    lines = ["🍶 **白酒 · 泸州老窖**"]

    # --- 较1月前对比 ---
    sdate, snap = nearest_snapshot()
    if sdate:
        s_retail = (snap.get("retailPrice") or {}).get("price")
        s_bp = (snap.get("guojiao1573") or {}).get("today")
        s_bp_i = int(s_bp) if isinstance(s_bp, str) and s_bp.isdigit() else s_bp
        parts = []
        c = fmt_cmp(rp, s_retail)
        if c: parts.append(f"零售 {c}")
        c = fmt_cmp(bp_i, s_bp_i)
        if c: parts.append(f"批价 {c}")
        if parts:
            lines.append(f"📈 较1月前({sdate[5:]}): " + " | ".join(parts))
            # 口径注记（小字）：零售价采集口径期间有变化
            if s_retail and rp and abs(rp - s_retail) > 50:
                lines.append("   _注: 8月中旬前零售为电商参考价、9月起为酒价内参全国采集均价，对比含口径变化因素_")

    lines.append(f"📦 国窖1573 批价: ¥{bp} | 零售参考: ¥{rp} | 批零差: {(rp - bp_i) if isinstance(rp, int) and isinstance(bp_i, int) else '?'}")

    ci = d.get("channelIndex", [])
    if ci:
        last = ci[-1]
        lines.append(f"📊 存货周转: {last.get('invTurnDays','?')}天 | 毛利率: {last.get('grossMargin','?')}%")

    return "\n".join(lines)

# DRAM 品项名 → 历史序列键 映射
DRAM_MAP = {
    "DDR5 16Gb (2Gx8) 4800/5600": "DDR5_16Gb",
    "DDR5 16Gb (2Gx8) eTT": "DDR5_eTT",
    "DDR4 16Gb (2Gx8) 3200": "DDR4_16Gb",
    "DDR4 16Gb (2Gx8) eTT": "DDR4_eTT",
}

def _hist_value_near(hist, key, target_date, tol=TOLERANCE):
    """从 history 数组找距 target_date 最近的 key 值"""
    best, best_off = None, tol + 1
    for h in hist:
        try:
            hd = date.fromisoformat(h.get("date", ""))
        except Exception:
            continue
        off = abs((hd - target_date).days)
        if off < best_off and h.get(key) is not None:
            best, best_off = h.get(key), off
    return best

def format_hardware():
    d = load(os.path.join(DATA, "hardware", "latest.json"))
    if not d: return "🔧 AI硬件: 数据获取失败"
    dram = d.get("dram", {}).get("items", [])
    dh = d.get("dram", {}).get("history", [])
    news = d.get("news", {}).get("articles", [])

    lines = ["🔧 **AI硬件**"]

    # --- 较1月前对比（历史序列内部对比，口径一致）---
    if dh:
        target = date.today() - timedelta(days=DAYS_AGO)
        cmp_parts = []
        for name, key in DRAM_MAP.items():
            # 当前值取序列最新点（与历史同口径，避免 items 现价与历史序列基准不一致的假涨跌）
            cur = next((h.get(key) for h in reversed(dh) if h.get(key) is not None), None)
            old = _hist_value_near(dh, key, target)
            c = fmt_cmp(round(cur, 1) if cur else None, round(old, 1) if old else None, unit="$", pct=True)
            if c:
                short = key.replace("_", " ")
                cmp_parts.append(f"{short} {c}")
        if cmp_parts:
            lines.append("📈 较1月前: " + " | ".join(cmp_parts))

    for item in dram[:4]:
        lines.append(f"  {item['name'][:30]}: ${item.get('avgPrice','?')} {item.get('change','')}")
    if news:
        lines.append(f"\n📡 要闻 ({len(news)}条):")
        for a in news[:3]:
            lines.append(f"  · {a['title'][:60]}")
    return "\n".join(lines)

def format_software():
    d = load(os.path.join(DATA, "software", "latest.json"))
    if not d: return "💻 AI软件: 数据获取失败"
    arena = d.get("arena", {}).get("ranking", [])
    cloud = d.get("cloudToken", {}).get("providers", [])
    ch = d.get("cloudToken", {}).get("history", [])

    lines = ["💻 **AI软件**"]

    # --- Token 份额较1月前 ---
    if ch:
        target = date.today() - timedelta(days=DAYS_AGO)
        top = sorted(cloud, key=lambda x: x.get("share", 0), reverse=True)[:4]
        cmp_parts = []
        for c0 in top:
            name, cur = c0.get("name"), c0.get("share")
            old = _hist_value_near(ch, name, target)
            c = fmt_cmp(cur, old, unit="%", )
            if c:
                cmp_parts.append(f"{name} {c}")
        if cmp_parts:
            lines.append("📈 Token份额 较1月前: " + " | ".join(cmp_parts))

    if arena:
        lines.append("🏆 Elo Top3:")
        for r in arena[:3]:
            lines.append(f"  #{r['rank']} {r['model']} ({r['vendor']}) — {r['elo']}")
    if cloud:
        top = sorted(cloud, key=lambda x: x.get('share',0), reverse=True)[:3]
        lines.append("☁️ Token份额 Top3: " + " | ".join(f"{c['name']} {c['share']}%" for c in top))
    return "\n".join(lines)

def main():
    parts = [format_baijiu(), format_hardware(), format_software()]
    report = "\n\n".join(parts)
    header = f"📊 **财经监控日报**\n🔗 [caijin.gaozhong.online]({SITE})\n\n"
    full = header + report

    out_path = os.path.join(DATA, "daily_report.txt")
    with open(out_path, "w") as f:
        f.write(full)
    print(full)

if __name__ == "__main__":
    main()
