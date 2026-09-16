#!/usr/bin/env python3
"""扫描 dated 快照生成零售价真实历史序列 retail_history.json
输出: data/baijiu/retail_history.json
  {updated, count, points: [{date, retail, batch, platform}]}
用法: python3 build_retail_history.py  （每次采集后运行，全量重建）"""
import json, glob, os, re
from datetime import date

BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "baijiu")
OUT = os.path.join(BASE, "retail_history.json")

def main():
    points = []
    for path in glob.glob(os.path.join(BASE, "20??-??-??.json")):
        m = re.search(r"(\d{4}-\d{2}-\d{2})\.json$", path)
        if not m:
            continue
        try:
            with open(path) as f:
                s = json.load(f)
        except Exception:
            continue
        retail = (s.get("retailPrice") or {}).get("price")
        batch = (s.get("guojiao1573") or {}).get("today")
        batch = int(batch) if isinstance(batch, str) and batch.isdigit() else batch
        if retail is None and batch is None:
            continue
        # 口径 tag: official=挂牌/指导价 | neican=酒价内参终端均价 | ecom=电商参考价
        rp = s.get("retailPrice") or {}
        srcs = " ".join((x.get("mall") or "") + (x.get("note") or "") for x in (rp.get("sources") or []))
        if retail is not None and retail >= 1350:
            tag = "official"
        elif "内参" in srcs or "内参" in (rp.get("note") or ""):
            tag = "neican"
        else:
            tag = "ecom"
        points.append({
            "date": m.group(1),
            "retail": retail,
            "batch": batch,
            "platform": rp.get("platform", ""),
            "tag": tag,
        })
    points.sort(key=lambda p: p["date"])
    out = {"updated": date.today().isoformat(), "count": len(points), "points": points}
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"retail_history.json: {len(points)} points ({points[0]['date']} -> {points[-1]['date']})" if points else "retail_history.json: EMPTY")

if __name__ == "__main__":
    main()
