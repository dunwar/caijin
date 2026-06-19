#!/usr/bin/env python3
"""每日财经报告生成 - 供飞书推送"""
import json, os

DATA = "/home/node/.openclaw/workspace/www/caijin.gaozhong.online/data"
SITE = "http://caijin.gaozhong.online"

def load(path):
    try:
        with open(path) as f: return json.load(f)
    except: return {}

def format_baijiu():
    d = load(os.path.join(DATA, "baijiu", "latest.json"))
    if not d: return "🍶 白酒: 数据获取失败"
    gj = d.get("guojiao1573", {})
    hist = d.get("priceHistory", [])
    retail = d.get("retailPrice", {})
    rp = retail.get("price", "?")
    bp = gj.get("today", "?")
    sp = f"¥{rp}" if rp else "?"
    
    # 获取最新批价
    last_batch = hist[-1].get("batch", "?") if hist else "?"
    
    lines = [
        f"🍶 **白酒 · 泸州老窖**",
        f"📦 国窖1573 批价: ¥{bp} | 零售参考: ¥{rp} | 批零差: ¥{rp - int(bp) if isinstance(rp,int) and isinstance(bp,str) and bp.isdigit() else (rp - bp if isinstance(rp,int) and isinstance(bp,int) else '?')}",
    ]
    
    ci = d.get("channelIndex", [])
    if ci:
        last = ci[-1]
        lines.append(f"📊 存货周转: {last.get('invTurnDays','?')}天 | 毛利率: {last.get('grossMargin','?')}%")
    
    return "\n".join(lines)

def format_hardware():
    d = load(os.path.join(DATA, "hardware", "latest.json"))
    if not d: return "🔧 AI硬件: 数据获取失败"
    dram = d.get("dram", {}).get("items", [])
    news = d.get("news", {}).get("articles", [])
    
    lines = ["🔧 **AI硬件**"]
    # Top DRAM items
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
    
    lines = ["💻 **AI软件**"]
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
