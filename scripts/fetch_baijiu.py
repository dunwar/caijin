#!/usr/bin/env python3
"""
白酒板块数据采集 v4 — yunjiu.com批价 + SMZDM零售价 + AKShare渠道库存指数
"""
import json, os, sys, re
from datetime import datetime, timezone, timedelta
CST = timezone(timedelta(hours=8))
def today_cst(): return datetime.now(CST).strftime("%Y-%m-%d")
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "baijiu")
os.makedirs(DATA_DIR, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")
RETAIL_FILE = os.path.join(DATA_DIR, "retail_price.json")
CHANNEL_FILE = os.path.join(DATA_DIR, "channel_index.json")

def load_json(path, default=[]):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========= 1. 批价（yunjiu.com 每日） =========
def fetch_yunjiu_prices():
    products = []
    try:
        r = requests.get("http://www.yunjiu.com/quotations/brand9",
                         headers={"User-Agent": UA}, timeout=20)
        html = r.text
        blocks = re.findall(r'<a href="/quotations/detail(\d+)">(.*?)</a>', html, re.DOTALL)
        for detail_id, content in blocks:
            name_m = re.search(r'<span>(.*?)</span>', content)
            if not name_m: continue
            name = name_m.group(1).strip()
            spec_m = re.search(r'<li>(.*?度.*?)</li>', content)
            spec = spec_m.group(1).strip() if spec_m else ""
            prices = re.findall(r'<li>([\d,]+)</li>', content)
            if len(prices) < 2: continue
            yesterday = prices[0].replace(',', '').strip()
            today = prices[1].replace(',', '').strip()
            if name and today:
                products.append({
                    "name": name, "spec": spec,
                    "yesterday": yesterday, "today": today,
                    "detailId": detail_id,
                    "detailUrl": f"http://www.yunjiu.com/quotations/detail{detail_id}"
                })
        return products
    except Exception as e:
        print(f"yunjiu error: {e}", file=sys.stderr)
        return []

# ========= 2. 零售价（SMZDM 自动+手动） =========
def get_retail_price():
    retail = load_json(RETAIL_FILE, None)
    if retail:
        return retail
    return {
        "updated": "2026-05-17", "platform": "SMZDM(什么值得买)参考",
        "price": 790, "range": [781, 799],
        "note": "天猫精选¥781~799；京东百亿补贴¥821/瓶"
    }

# ========= 3. 批价历史累积 + 详情页回溯 =========
def update_batch_history(products):
    today = today_cst()
    history = load_json(HISTORY_FILE)

    # 尝试溯源详情页历史（30天）
    try:
        detail_url = None
        for p in products:
            if "国窖1573" in p["name"] and "52" in p["spec"]:
                detail_url = p.get("detailUrl")
                break
        if detail_url:
            r = requests.get(detail_url, headers={"User-Agent": UA}, timeout=20)
            html = r.text
            dates = re.findall(r'class="xAxis_data"[^>]*>(.*?)<', html)
            prices = re.findall(r'class="series_data"[^>]*>(.*?)<', html)
            existing = {h["date"] for h in history}
            for i in range(len(dates)):
                d = dates[i].strip()
                p = int(prices[i].replace(',','').strip())
                if d not in existing:
                    history.append({"date": d, "batch": p})
                    existing.add(d)
            print(f"详情页回溯: {len(dates)} 条")
    except: pass

    # 检查今天
    if not any(h["date"]==today for h in history):
        guojiao = None
        for p in products:
            if "国窖1573" in p["name"] and "52" in p["spec"]: guojiao = p; break
        if guojiao:
            history.append({"date": today, "batch": int(guojiao["today"])})

    history.sort(key=lambda x: x["date"])
    save_json(HISTORY_FILE, history)
    return history

# ========= 4. 渠道库存积压指数（季度） =========
def fetch_channel_index():
    """存货周转天数 + 营收增速 + 毛利率 = 渠道积压指数"""
    try:
        import akshare as ak
        df = ak.stock_financial_abstract(symbol="000568")

        # 找数据行
        rev_row = cost_row = inv_turn_row = debt_row = None
        for _, row in df.iterrows():
            opt, ind = str(row.get("选项","")), str(row["指标"]).strip()
            if opt == "常用指标":
                if ind == "营业总收入": rev_row = row
                if ind == "营业成本": cost_row = row
            if "存货周转天数" in ind and inv_turn_row is None: inv_turn_row = row
            if ind.strip() == "资产负债率" and debt_row is None: debt_row = row

        periods = ["20260331","20251231","20250930","20250630","20250331",
                   "20241231","20240930","20240630"]
        records = []
        for p in reversed(periods):
            if p not in df.columns: continue
            rec = {"date": p}

            # 存货周转天数
            if inv_turn_row is not None:
                v = inv_turn_row[p]
                if v and v != "" and v != "False":
                    try: rec["invTurnDays"] = round(float(v), 1)
                    except: pass

            # 营收（单季=本期-上期）
            if rev_row is not None and cost_row is not None:
                rev_v = rev_row[p]
                cost_v = cost_row[p]
                if rev_v and rev_v != "" and rev_v != "False" and cost_v and cost_v != "" and cost_v != "False":
                    try:
                        rec["revenue"] = float(rev_v)/1e8
                        rec["cost"] = float(cost_v)/1e8
                        if rec["cost"] > 0:
                            rec["grossMargin"] = round((1-rec["cost"]/rec["revenue"])*100,1)
                    except: pass

            # 资产负债率
            if debt_row is not None:
                v = debt_row[p]
                if v and v != "" and v != "False":
                    try: rec["debtRatio"] = float(v)
                    except: pass

            if rec.get("invTurnDays") or rec.get("revenue"):
                records.append(rec)

        save_json(CHANNEL_FILE, records)
        return records[-8:]
    except Exception as e:
        print(f"渠道指数 error: {e}", file=sys.stderr)
        return load_json(CHANNEL_FILE, [])

def main():
    today = today_cst()

    products = fetch_yunjiu_prices()
    print(f"yunjiu: {len(products)} 产品")

    history = update_batch_history(products)
    print(f"批价历史: {len(history)} 条")

    retail = get_retail_price()
    print(f"零售参考: ¥{retail['price']}")

    channel = fetch_channel_index()
    print(f"渠道指数: {len(channel)} 季度")

    guojiao_current = None
    for p in products:
        if "国窖1573" in p["name"] and "52" in p["spec"]: 
            guojiao_current = p; break

    # 保存当日 + 汇总
    path = os.path.join(DATA_DIR, f"{today}.json")
    with open(path, "w") as f:
        json.dump({"updated":today, "products":products, "guojiao1573":guojiao_current,
                   "priceHistory":history, "retailPrice":retail, "channelIndex":channel,
                   "source":{"batch":"yunjiu.com","retail":"SMZDM参考","channel":"AKShare季报"}}, f, ensure_ascii=False, indent=2)

    summary = {
        "updated": today,
        "guojiao1573": guojiao_current,
        "priceHistory": history,
        "retailPrice": retail,
        "channelIndex": channel,
        "source": {"batch":"yunjiu.com","retail":"SMZDM","channel":"AKShare"}
    }
    with open(os.path.join(DATA_DIR, "latest.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"✅ 白酒数据已保存")

if __name__ == "__main__":
    main()
