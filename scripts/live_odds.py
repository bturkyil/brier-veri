#!/usr/bin/env python3
"""Brier — canlı oran yolu. Odds API /odds (yaklaşan maçlar) -> odds_flow/live/<lig>.json
Her maç için zaman damgalı nokta: [ts, ev olasılığı (vig'siz, kitap medyanı), spread (ev), total, kitap sayısı].
Kullanım (repo kökünden):  ODDS_API_KEY=... python scripts/live_odds.py
Kredi: lig başına 3 (1 bölge x 3 market). 5 lig x saatlik = ~360/gün.
"""
import os, sys, json, statistics, time
from datetime import datetime, timezone, timedelta
import requests

SPORTS = {'nfl': 'americanfootball_nfl', 'nba': 'basketball_nba', 'mlb': 'baseball_mlb',
          'wnba': 'basketball_wnba', 'ncaaf': 'americanfootball_ncaaf'}
OUT = 'odds_flow/live'
KEEP_AFTER_START_H = 36     # başlamış maçın yolunu bu kadar saat tut
MAX_POINTS = 240
MIN_BOOKS = 3

def pdt(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))
def iso_min(dt): return dt.strftime('%Y-%m-%dT%H:%MZ')

def med(x): return round(statistics.median(x), 4) if x else None

def summarize(ev):
    """Odds API event -> [p_ev, spd, ou, kitap] (backfill kompakt biçimiyle aynı)."""
    ph, sp, ou = [], [], []
    for b in ev.get('bookmakers', []):
        for m in b.get('markets', []):
            oc = {x['name']: x for x in m.get('outcomes', [])}
            if m['key'] == 'h2h':
                h = oc.get(ev['home_team'], {}).get('price'); a = oc.get(ev['away_team'], {}).get('price')
                if h and a and h > 1 and a > 1:
                    ih, ia = 1 / h, 1 / a; ph.append(ih / (ih + ia))
            elif m['key'] == 'spreads':
                p = oc.get(ev['home_team'], {}).get('point')
                if p is not None: sp.append(p)
            elif m['key'] == 'totals':
                p = oc.get('Over', {}).get('point')
                if p is not None: ou.append(p)
    if len(ph) < MIN_BOOKS and not sp and not ou: return None
    return [med(ph) if len(ph) >= MIN_BOOKS else None, med(sp), med(ou), len(ph)]

def merge(store, events, now):
    """store: {event_id: {t,h,a,path:[[ts,p,spd,ou,nb],...]}} — yeni noktaları ekler, eskiyi budar."""
    ts = iso_min(now)
    for ev in events:
        v = summarize(ev)
        if not v: continue
        r = store.setdefault(ev['id'], {'t': ev['commence_time'], 'h': ev['home_team'], 'a': ev['away_team'], 'path': []})
        r['t'] = ev['commence_time']
        if r['path'] and r['path'][-1][1:] == v: continue      # değişmediyse ekleme
        r['path'].append([ts] + v)
        if len(r['path']) > MAX_POINTS: r['path'] = r['path'][:1] + r['path'][-(MAX_POINTS - 1):]
    cut = now - timedelta(hours=KEEP_AFTER_START_H)
    for k in [k for k, r in store.items() if pdt(r['t']) < cut]: del store[k]
    return store

def fetch(sport, key):
    for i in range(4):
        r = requests.get(f'https://api.the-odds-api.com/v4/sports/{sport}/odds',
                         params={'apiKey': key, 'regions': 'us', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'decimal'}, timeout=60)
        if r.status_code == 200:
            print(f'  {sport}: {len(r.json())} events · kalan kredi {r.headers.get("x-requests-remaining")}')
            return r.json()
        if r.status_code in (429, 502, 503): time.sleep(5 * (i + 1)); continue
        print(f'  {sport}: HTTP {r.status_code} {r.text[:120]}'); return None
    return None

def main():
    key = os.environ.get('ODDS_API_KEY')
    if not key: print('ODDS_API_KEY yok'); sys.exit(1)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    os.makedirs(OUT, exist_ok=True)
    for lig, sport in SPORTS.items():
        path = f'{OUT}/{lig}.json'
        try: store = json.load(open(path, encoding='utf-8')).get('maclar', {})
        except Exception: store = {}
        ev = fetch(sport, key)
        if ev is None: continue          # hata: dosyaya dokunma
        store = merge(store, ev, now)
        if not store and not os.path.exists(path): continue
        doc = {'lig': lig, 'guncelleme': iso_min(now), 'alan': ['ts', 'p_ev', 'spd', 'ou', 'kitap'], 'maclar': store}
        json.dump(doc, open(path, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)

if __name__ == '__main__':
    main()
