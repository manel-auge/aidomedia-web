#!/usr/bin/env python3
"""Sincroniza stats.json con los datos reales de YouTube de cada cliente.
Se ejecuta en GitHub Actions (cron diario) y también funciona en local:
    python3 update_stats.py
Lee channels.json (handles + overrides manuales) y escribe stats.json.
Si un canal oculta datos o falla el fetch, conserva el último valor conocido."""
import urllib.request, re, json, sys, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

def parse_count(txt):
    """'151K subscribers' → 151000 · '36,898,258 views' → 36898258 · '1.2M' → 1200000"""
    if not txt:
        return None
    m = re.search(r'([\d.,]+)\s*([KMB]?)', txt.replace('\xa0', ' '))
    if not m:
        return None
    num, suf = m.group(1), m.group(2)
    if suf:  # 151K / 1.2M — separador decimal con punto
        val = float(num.replace(',', ''))
        return int(val * {'K': 1e3, 'M': 1e6, 'B': 1e9}[suf])
    return int(num.replace(',', '').replace('.', ''))

def fetch_channel(handle):
    req = urllib.request.Request(
        f"https://www.youtube.com/@{handle}/about?hl=en&gl=US",
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                 "Cookie": "SOCS=CAI; CONSENT=YES+1"})
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')
    def gx(p):
        m = re.search(p, html)
        return m.group(1) if m else None
    return {
        "subs": parse_count(gx(r'"subscriberCountText":"([^"]+)"')),
        "views": parse_count(gx(r'"viewCountText":"([^"]+)"')),
        "videos": parse_count(gx(r'"videoCountText":"([^"]+)"')),
    }

def main():
    channels = json.load(open(os.path.join(HERE, 'channels.json')))
    try:
        prev = json.load(open(os.path.join(HERE, 'stats.json')))['channels']
    except Exception:
        prev = {}
    out = {}
    for key, cfg in channels.items():
        data = {"name": cfg["name"], "subs": None, "views": None, "videos": None}
        if cfg.get("handle"):
            try:
                fetched = fetch_channel(cfg["handle"])
                data.update({k: v for k, v in fetched.items() if v})
                time.sleep(1.5)
            except Exception as e:
                print(f"  ! {key}: {e}", file=sys.stderr)
        # overrides manuales (canales que ocultan subs) pisan lo público
        for k, v in cfg.get("manual", {}).items():
            data[k] = v
        # conservar último valor conocido si hoy no hay dato
        for k in ("subs", "views", "videos"):
            if not data[k] and prev.get(key, {}).get(k):
                data[k] = prev[key][k]
        out[key] = data
        print(f"  {key}: subs={data['subs']} views={data['views']} videos={data['videos']}")
    total = sum(c["subs"] or 0 for c in out.values())
    total_views = sum(c["views"] or 0 for c in out.values())
    stats = {"updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             "total_subs": total, "total_views": total_views, "channels": out}
    json.dump(stats, open(os.path.join(HERE, 'stats.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(f"total_subs={total}")

if __name__ == '__main__':
    main()
