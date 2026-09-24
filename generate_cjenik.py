#!/usr/bin/env python3
"""
MARRUBI - automatski cjenik (NN 101/2026)
Povlaci proizvode sa Shopify webshopa, generira CSV + XML s datumom u nazivu,
vodi arhivu zadnjih 30+ dana i slaze index.html za cjenik.<domena>.
"""
import csv, json, os, re, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CFG.get("timezone", "Europe/Zagreb"))
DOCS = ROOT / "docs"
FILES = DOCS / "files"
STATE = ROOT / "state.json"
EXTRA = ROOT / "proizvodi_dodatno.csv"

COLUMNS = ["vrsta", "naziv", "sifra", "marka", "jedinica_mjere", "cijena_za_jedinicu_mjere",
           "maloprodajna_cijena", "posebni_oblik_prodaje", "naziv_posebnog_oblika_prodaje",
           "sidrena_cijena", "datum_sidrene_cijene", "barkod", "dostupnost"]
WARN = []


def money(v):
    if v in (None, ""):
        return ""
    s = f"{float(v):.2f}"
    return s.replace(".", ",") if CFG.get("decimal_separator", ",") == "," else s


def fetch_products():
    """Javni /products.json endpoint, bez API kljuca."""
    base = CFG["shop_url"].rstrip("/")
    out, page = [], 1
    while True:
        req = urllib.request.Request(f"{base}/products.json?limit=250&page={page}",
                                     headers={"User-Agent": "marrubi-cjenik/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r).get("products", [])
        if not batch:
            return out
        out += batch
        page += 1


def load_extra():
    """sifra;neto_kolicina;jedinica;sidrena_cijena;datum_sidrene (barkod opcionalno)"""
    if not EXTRA.exists():
        return {}
    with EXTRA.open(encoding="utf-8-sig") as f:
        return {r["sifra"].strip(): r for r in csv.DictReader(f, delimiter=";") if r.get("sifra")}


def build_rows(products, extra):
    rows = []
    skip = set(CFG.get("exclude_product_types", []))
    for p in products:
        if p.get("product_type") in skip:
            continue
        for v in p.get("variants", []):
            sku = (v.get("sku") or "").strip() or str(v["id"])
            name = p["title"] if v.get("title") in (None, "", "Default Title") else f'{p["title"]} - {v["title"]}'
            price = float(v["price"])
            cmp = float(v["compare_at_price"]) if v.get("compare_at_price") else 0
            x = extra.get(sku, {})

            unit_price, unit = "", "kom"
            if x.get("neto_kolicina") and x.get("jedinica"):
                qty = float(x["neto_kolicina"].replace(",", "."))
                if qty > 0:
                    unit_price = money(price / qty)
                    unit = x["jedinica"].strip()

            anchor = (x.get("sidrena_cijena") or "").replace(",", ".")
            anchor_date = (x.get("datum_sidrene") or "").strip() or CFG["default_anchor_date"]
            if not anchor:
                anchor = price
                WARN.append(f"{sku} ({name}): nema sidrene cijene u proizvodi_dodatno.csv, koristim trenutnu")

            sale = cmp > price
            rows.append({
                "vrsta": "proizvod", "naziv": name, "sifra": sku,
                "marka": CFG["brand"],
                "jedinica_mjere": unit, "cijena_za_jedinicu_mjere": unit_price,
                "maloprodajna_cijena": money(price),
                "posebni_oblik_prodaje": "DA" if sale else "NE",
                "naziv_posebnog_oblika_prodaje": CFG.get("sale_label", "Akcija") if sale else "",
                "sidrena_cijena": money(anchor), "datum_sidrene_cijene": anchor_date,
                "barkod": (x.get("barkod") or "").strip(),
                "dostupnost": "dostupno" if v.get("available") else "nedostupno",
            })
    for s in CFG.get("services", []):
        rows.append({
            "vrsta": "usluga", "naziv": s["naziv"], "sifra": s["sifra"], "marka": CFG["brand"],
            "jedinica_mjere": s.get("jedinica", "usluga"), "cijena_za_jedinicu_mjere": "",
            "maloprodajna_cijena": money(s["cijena"]), "posebni_oblik_prodaje": "NE",
            "naziv_posebnog_oblika_prodaje": "", "sidrena_cijena": money(s["sidrena_cijena"]),
            "datum_sidrene_cijene": s["datum_sidrene"], "barkod": "", "dostupnost": "dostupno",
        })
    return rows


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def write_xml(path, rows, now):
    c = CFG["company"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<cjenik trgovac="{escape(c["name"])}" oib="{escape(c.get("oib", ""))}" '
             f'adresa="{escape(c["address"])}" oblik="webshop" oznaka_objekta="{escape(CFG["object_code"])}" '
             f'datum_objave="{now:%d.%m.%Y. %H:%M}">']
    for r in rows:
        lines.append(f'  <stavka vrsta="{r["vrsta"]}">')
        for k in COLUMNS[1:]:
            lines.append(f"    <{k}>{escape(str(r[k]))}</{k}>")
        lines.append("  </stavka>")
    lines.append("</cjenik>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def slug(s):
    return re.sub(r"[^\w.\-]+", "-", s, flags=re.UNICODE).strip("-")


def render_index(current, archive, now):
    c = CFG["company"]
    def li(f):
        return f'<li><a href="files/{f}">{f}</a></li>'
    arch = "\n".join(li(f) for f in archive) or "<li>Arhiva se puni od prve objave.</li>"
    html = (ROOT / "index_template.html").read_text(encoding="utf-8")
    return (html.replace("{{COMPANY}}", escape(c["name"])).replace("{{ADDRESS}}", escape(c["address"]))
                .replace("{{SHOP}}", escape(CFG["shop_url"])).replace("{{CURRENT}}", "\n".join(li(f) for f in current))
                .replace("{{ARCHIVE}}", arch).replace("{{UPDATED}}", f"{now:%d.%m.%Y. u %H:%M}"))


def main():
    now = datetime.now(TZ)
    state = json.loads(STATE.read_text()) if STATE.exists() else {"counter": 0}
    state["counter"] += 1

    products = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else fetch_products()
    if isinstance(products, dict):
        products = products["products"]
    rows = build_rows(products, load_extra())
    if not [r for r in rows if r["vrsta"] == "proizvod"]:
        sys.exit("Nema proizvoda - prekidam da ne objavim prazan cjenik.")

    FILES.mkdir(parents=True, exist_ok=True)
    stem = "_".join([
        "webshop", slug(CFG["company"]["address"]), CFG["object_code"],
        str(state["counter"]), now.strftime("%d.%m.%Y_" + CFG.get("time_format", "%H-%M")),
    ])
    write_csv(FILES / f"{stem}.csv", rows)
    write_xml(FILES / f"{stem}.xml", rows, now)
    # stabilni linkovi za automatsko preuzimanje
    write_csv(DOCS / "cjenik.csv", rows)
    write_xml(DOCS / "cjenik.xml", rows, now)

    # arhiva: zadrzi najmanje keep_days dana
    # (brise po state.json, ne po mtime - git checkout resetira mtime)
    cutoff = now - timedelta(days=CFG.get("keep_days", 35))
    published = state.setdefault("published", [])
    published.append({"stem": stem, "time": now.isoformat()})
    state["published"] = [p for p in published if datetime.fromisoformat(p["time"]) >= cutoff]
    keep = {p["stem"] for p in state["published"]}
    for f in FILES.iterdir():
        if f.stem not in keep:
            f.unlink()

    current = [f"{stem}.xml", f"{stem}.csv"]
    archive = [f"{p['stem']}.{ext}" for p in reversed(state["published"][:-1]) for ext in ("xml", "csv")
               if (FILES / f"{p['stem']}.{ext}").exists()]
    (DOCS / "index.html").write_text(render_index(current, archive, now), encoding="utf-8")
    if CFG.get("custom_domain"):
        (DOCS / "CNAME").write_text(CFG["custom_domain"] + "\n")
    (DOCS / ".nojekyll").write_text("")
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    print(f"Objavljeno: {stem} ({len(rows)} stavki)")
    for w in WARN:
        print("UPOZORENJE:", w)


if __name__ == "__main__":
    main()
