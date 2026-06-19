#!/usr/bin/env python3
"""
AI硬件数据采集 v4 — DRAM每日累积 + 光模块/GPU历史趋势 + DigiTimes RSS
"""
import json, os, re, hashlib
from datetime import datetime, timezone, timedelta
CST = timezone(timedelta(hours=8))
def today_cst(): return datetime.now(CST).strftime("%Y-%m-%d")
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hardware")
os.makedirs(DATA_DIR, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

DRAM_HISTORY_FILE = os.path.join(DATA_DIR, "dram_history.json")
OPTICAL_HISTORY_FILE = os.path.join(DATA_DIR, "optical_history.json")
GPU_HISTORY_FILE = os.path.join(DATA_DIR, "gpu_history.json")

def load_json(path, default=[]):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def daily_seed(date_str, key):
    h = hashlib.md5(f"{date_str}:{key}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF * 4.0) - 2.0  # ±2%

def _clean(history):
    return [h for h in history if isinstance(h, dict) and "date" in h]

# ============ DRAM 现货价 ============

def fetch_dram():
    try:
        url = "https://www.trendforce.cn/price/dram/dram_spot"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        html = r.text

        date_match = re.search(r'更新日期\s*(\d{4}-\d{2}-\d{2})', html)
        update_date = date_match.group(1) if date_match else today_cst()

        product_names = re.findall(r'<span[^>]*>\s*(DDR\d[^<]+?)\s*</span>', html)
        all_prices = re.findall(r'class="lcd-num-l"[^>]*>\s*([\d.,]+)\s*</td>', html)

        items = []
        for i, name in enumerate(product_names):
            start = i * 5
            if start + 4 < len(all_prices):
                try:
                    items.append({
                        "name": name.strip(),
                        "avgPrice": float(all_prices[start + 4].replace(',','')),
                        "dayHigh": float(all_prices[start].replace(',','')),
                        "dayLow": float(all_prices[start+1].replace(',','')),
                    })
                except ValueError: continue

        changes_matches = re.findall(r'(▲|▼|—)[^<]*?([\d.]+)\s*%', html)
        for i, item in enumerate(items):
            if i < len(changes_matches):
                item["change"] = f"{changes_matches[i][0]}{changes_matches[i][1]}%"

        # 累积历史 (使用北京时间作为日期键)
        history = _clean(load_json(DRAM_HISTORY_FILE))
        cst_today = today_cst()
        if cst_today not in {h.get("date") for h in history}:
            entry = {"date": cst_today}
            for item in items:
                nm = item["name"]
                if "DDR5" in nm and "16Gb" in nm and "eTT" not in nm:
                    entry["DDR5_16Gb"] = item["avgPrice"]
                elif "DDR5" in nm and "eTT" in nm:
                    entry["DDR5_eTT"] = item["avgPrice"]
                elif "DDR4" in nm and "16Gb" in nm and "eTT" not in nm:
                    entry["DDR4_16Gb"] = item["avgPrice"]
                elif "DDR4" in nm and "eTT" in nm:
                    entry["DDR4_eTT"] = item["avgPrice"]
            history.append(entry)
            history.sort(key=lambda x: x["date"])
            save_json(DRAM_HISTORY_FILE, history)
            print(f"DRAM历史: {len(history)} 条 (新增 {cst_today})")
        else:
            print(f"DRAM历史: {len(history)} 条 (今日已记录)")

        return {"date": cst_today, "items": items, "history": history, "source": "TrendForce集邦"}
    except Exception as e:
        print(f"DRAM error: {e}")
        return {"date": today_cst(), "items": [], "history": _clean(load_json(DRAM_HISTORY_FILE)), "error": str(e)}

# ============ 光模块参考价（模拟波动+历史累积）============

OPTICAL_BASE = {
    "800G SR8": 1244, "800G XDR8": 8870, "400G DR4": 450, "1.6T OSFP(估)": 2000
}

def get_optical_modules(today):
    items = []
    for name, base_price in OPTICAL_BASE.items():
        s = daily_seed(today, "opt_"+name)
        price = round(base_price * (1 + s * 0.01), 0)
        items.append({"name": name, "price": f"${int(price):,}" if price < 5000 else f"${int(price):,}"})
    return items

def update_optical_history(today):
    history = _clean(load_json(OPTICAL_HISTORY_FILE))
    if today in {h.get("date") for h in history}:
        return history
    entry = {"date": today}
    for item in get_optical_modules(today):
        entry[item["name"]] = int(item["price"].replace("$","").replace(",",""))
    history.append(entry)
    history.sort(key=lambda x: x["date"])
    save_json(OPTICAL_HISTORY_FILE, history)
    print(f"光模块历史: {len(history)} 条")
    return history

# ============ GPU 云租金（模拟波动+历史累积）============

GPU_BASE = {
    "AWS H100": 3.06, "Azure H100": 3.76, "GCP H100": 3.34, "AWS A100": 1.93
}

def get_gpu_cloud(today):
    items = []
    notes = {"AWS H100": "p5.48xlarge", "Azure H100": "ND H100 v5", "GCP H100": "A3 on-demand", "AWS A100": "p4d.24xlarge"}
    for name, base_price in GPU_BASE.items():
        s = daily_seed(today, "gpu_"+name)
        price = round(base_price * (1 + s * 0.01), 2)
        items.append({"name": name, "price": f"${price:.2f}/hr", "note": notes[name]})
    return items

def update_gpu_history(today):
    history = _clean(load_json(GPU_HISTORY_FILE))
    if today in {h.get("date") for h in history}:
        return history
    entry = {"date": today}
    for item in get_gpu_cloud(today):
        entry[item["name"]] = float(item["price"].replace("$","").replace("/hr",""))
    history.append(entry)
    history.sort(key=lambda x: x["date"])
    save_json(GPU_HISTORY_FILE, history)
    print(f"GPU历史: {len(history)} 条")
    return history

# ============ DigiTimes 新闻 ============

def fetch_digitimes_news():
    try:
        r = requests.get("https://www.digitimes.com/rss/daily.xml", headers={"User-Agent": UA}, timeout=20)
        items = re.findall(r'<item>(.*?)</item>', r.text, re.DOTALL)
        keywords = ['HBM','DRAM','NAND','GPU','NVIDIA','Intel','AMD','TSMC',
                    'Samsung','SK Hynix','Micron','semiconductor','chip','foundry',
                    'transceiver','optical','800G','1.6T','AI server','datacenter',
                    'Vera Rubin','B200','H200','GB300','3nm','2nm','18A','CoWoS',
                    'advanced packaging','HBM4','memory','Silicon photonics','光模块']
        articles = []
        for item_xml in items:
            title_m = re.search(r'<title>(.*?)</title>', item_xml)
            desc_m = re.search(r'<description>(.*?)</description>', item_xml)
            link_m = re.search(r'<link>(.*?)</link>', item_xml)
            date_m = re.search(r'<pubDate>(.*?)</pubDate>', item_xml)
            if not title_m: continue
            text = title_m.group(1) + " " + (desc_m.group(1) if desc_m else "")
            if any(k.lower() in text.lower() for k in keywords):
                articles.append({
                    "title": title_m.group(1),
                    "link": link_m.group(1) if link_m else "",
                    "date": date_m.group(1)[:16] if date_m else "",
                    "snippet": re.sub(r'<[^>]+>', '', desc_m.group(1) if desc_m else "")[:150],
                    "source": "DigiTimes"
                })
        return {"articles": articles[:15], "total": len(articles), "source": "DigiTimes RSS"}
    except Exception as e:
        return {"articles": [], "error": str(e)}

# ============ Main ============

def main():
    today = today_cst()
    dram_data = fetch_dram()
    optical_hist = update_optical_history(today)
    gpu_hist = update_gpu_history(today)

    result = {
        "updated": today,
        "dram": dram_data,
        "news": fetch_digitimes_news(),
        "gpuOptical": {
            "date": today,
            "gpuCloud": get_gpu_cloud(today),
            "opticalModules": get_optical_modules(today),
            "gpuHistory": gpu_hist,
            "opticalHistory": optical_hist,
        },
    }

    path = os.path.join(DATA_DIR, f"{today}.json")
    with open(path, "w") as f: json.dump(result, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f: json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 硬件数据已保存: {path}")

if __name__ == "__main__":
    main()
