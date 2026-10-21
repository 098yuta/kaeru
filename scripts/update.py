#!/usr/bin/env python3
"""KAERU 週次更新（GitHub Actions 用）

data.json の各スニーカーについて、スニダンの商品ページからサイズ別の新品最安値と定価を取り直す。
- add.txt に書かれた品番は「追加待ち」として取り込む（1行に1品番）
- メルカリ・ラクマ・ヤフオクはここでは取得しない（取得日 siteAt が古くなったら画面側で非表示）
- 取得に失敗した品番は前回の値をそのまま残す
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data.json")
ADD = os.path.join(ROOT, "add.txt")
SIZES = ["24_5", "25", "25_5", "26", "26_5", "27", "27_5", "28", "28_5", "29"]
KEYS = ["s245", "s25", "s255", "s26", "s265", "s27", "s275", "s28", "s285", "s29"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
RE_RETAIL = re.compile(r'cm\\"\}\],[\s\S]{0,3000}?\\"regularPrice\\":(\d+)')
RE_SIZE = re.compile(r'footwear_size_(\d+(?:_5)?)\\"\},\\"minNewListingPrice\\":(\d+|null)')
RE_TITLE = re.compile(r"<title>([^<]*)</title>")


def today_jst():
    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).date().isoformat()


def fetch(sku):
    req = urllib.request.Request(f"https://snkrdunk.com/products/{sku}", headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def total(site, c, fees):
    p = c["p"]
    if site == "snk":
        return p + round(p * fees["snkRate"]) + fees["snkShip"]
    ship = c.get("ship")
    if ship is None:
        ship = fees.get(site + "Ship", 0)
    return p + ship


def best_totals(d, fees):
    out = {}
    for k in KEYS:
        vals = [total(s, d[s][k], fees) for s in ("snk", "mer", "rak", "yah")
                if isinstance(d.get(s), dict) and isinstance(d[s].get(k), dict)
                and d[s][k].get("p") and not d[s][k].get("bid") and not d[s][k].get("used")]
        if vals:
            out[k] = min(vals)
    return out


def guess_cat(name):
    if "×" in name:
        return "コラボ"
    if "Jordan" in name:
        return "ジョーダン"
    if "Dunk" in name:
        return "ダンク"
    return "その他"


def unescape(s):
    return (s.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'").replace("&#39;", "'"))


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    meta, rows = data["meta"], data["sneakers"]
    fees = meta["fees"]
    today = today_jst()
    by_id = {r["id"]: r for r in rows}

    # add.txt の品番を追加待ちに
    if os.path.exists(ADD):
        order = max([r.get("order") or 0 for r in rows] + [0])
        for line in open(ADD, encoding="utf-8"):
            sku = line.strip().upper()
            if not sku or sku.startswith("#") or sku in by_id:
                continue
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{3,30}", sku):
                continue
            order += 1
            r = {"id": sku, "sku": sku, "name": sku, "color": "", "cat": "その他", "retailJpy": None, "memo": "",
                 "order": order, "src": "add", "pending": True, "snk": {}, "mer": {}, "rak": {}, "yah": {}}
            rows.append(r)
            by_id[sku] = r

    ok = ng = 0
    for r in rows:
        if r.get("hidden"):
            continue
        sku = r["sku"]
        try:
            html = fetch(sku)
        except Exception as e:  # noqa: BLE001
            print(f"skip {sku}: {e}", file=sys.stderr)
            ng += 1
            time.sleep(1)
            continue
        sizes = {m.group(1): (0 if m.group(2) == "null" else int(m.group(2))) for m in RE_SIZE.finditer(html)}
        if r.get("pending"):
            t = RE_TITLE.search(html)
            title = unescape(t.group(1).split("の新品")[0]) if t else ""
            if not sizes:
                r["hidden"] = True
                r["memo"] = "スニーカー以外、またはスニダンに見つかりませんでした"
                r.pop("pending", None)
                time.sleep(1)
                continue
            m = re.match(r'(.*?)\s*"([^"]*)"\s*(.*)$', title)
            r["name"], r["color"] = ((m.group(1), (m.group(2) + (" " + m.group(3) if m.group(3) else "")).strip()) if m else (title or sku, ""))
            r["cat"] = guess_cat(title)
            r.pop("pending", None)
        else:
            r["prev"] = dict(best_totals(r, fees), at=meta.get("siteAt", {}).get("snk") or meta.get("asOf"))
        rm = RE_RETAIL.search(html)
        if rm:
            r["retailJpy"] = int(rm.group(1))
        r["snk"] = {k: {"p": sizes[s], "url": f"https://snkrdunk.com/products/{sku}", "bid": False}
                    for s, k in zip(SIZES, KEYS) if sizes.get(s)}
        r["updatedAt"] = today
        ok += 1
        time.sleep(1.2)

    print(f"updated {ok}, failed {ng}")
    if ok == 0:
        print("no data fetched; leaving data.json unchanged", file=sys.stderr)
        sys.exit(0)
    meta["asOf"] = today
    meta.setdefault("siteAt", {})["snk"] = today
    json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 取り込んだ add.txt は空にする
    if os.path.exists(ADD):
        open(ADD, "w", encoding="utf-8").write("# 追加したい品番を1行に1つ書くと、次の更新で取り込みます\n")


if __name__ == "__main__":
    main()
