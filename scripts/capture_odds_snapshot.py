#!/usr/bin/env python3
"""
Brier — acilis -> kapanis arsivleyici (v2)

NE YAPAR
  Railway worker'in dun.json'unu (sonuclanmis maclar) ceker ve her mac icin
  GERCEK acilis (ac) + GERCEK kapanis (kap) oranlarini lig basina
  odds_history/<gkarne_lig>.json dosyasina ekler.

NEDEN dun.json (bugun.json DEGIL)
  bugun.json'u gunluk tiklemek "ilk gorulen = acilis, son gorulen = kapanis" demek
  olur — gunluk cozunurluk, gercek degil. Worker zaten acilisi (ac, v4.5) ve
  kapanis konsensusunu (kap) mac bazinda tutuyor; dun.json bunlari tasir.

ANAHTAR
  '|'.join(sorted([ev.lower(), dep.lower()]))  -> ev/dep sirasindan BAGIMSIZ.
  Her kayit kendi o gunku h/a'sini tasir; PWA "kim evdeydi" bilgisini oradan okur.

DOSYA YAPISI (odds_history/<lig>.json)
  {"lig": "turkiye", "guncelleme": "2026-10-15",
   "maclar": {"fenerbahce|galatasaray": [
       {"t": "...Z", "h": "Galatasaray", "a": "Fenerbahçe",
        "ac":  {"h":0.48,"d":0.26,"a":0.26},      # acilis de-vig konsensus (varsa)
        "kap": {"h":0.55,"d":0.24,"a":0.21},      # kapanis de-vig konsensus
        "kap_tot": {...}, "kap_spr": {...},       # kapanis totals/spread (varsa)
        "skor": "2-1"} ]}}

CALISTIRMA
  python3 scripts/capture_odds_snapshot.py        (GitHub Actions: gunluk 02:00 UTC)
  RAILWAY_URL env ile worker adresi degistirilebilir.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

RAILWAY_URL = os.environ.get('RAILWAY_URL', 'https://worker-production-a1ba.up.railway.app')
OUT_DIR = Path('odds_history')

# index.html'deki LIG_ESLE ile BIREBIR ayni (worker key -> golkarne lig). Yeni lig eklenince ikisini de guncelle.
LIG_ESLE = {
  'soccer_epl':'epl','soccer_spain_la_liga':'laliga','soccer_italy_serie_a':'seriea',
  'soccer_germany_bundesliga':'bundesliga','soccer_germany_bundesliga2':'bundes2',
  'soccer_france_ligue_one':'ligue1','soccer_france_ligue_two':'ligue2',
  'soccer_turkey_super_league':'turkiye','soccer_portugal_primeira_liga':'portekiz',
  'soccer_netherlands_eredivisie':'eredivisie','soccer_belgium_first_div':'belcika',
  'soccer_spl':'iskocya','soccer_greece_super_league':'yunanistan',
  'soccer_austria_bundesliga':'avusturya','soccer_switzerland_superleague':'isvicre',
  'soccer_denmark_superliga':'danimarka','soccer_sweden_allsvenskan':'isvec',
  'soccer_norway_eliteserien':'norvec','soccer_japan_j_league':'japonya',
  'soccer_brazil_campeonato':'brezilya','soccer_brazil_serie_b':'brezilya2',
  'soccer_china_superleague':'superleague','soccer_argentina_primera_division':'arjantin',
  'soccer_mexico_ligamx':'meksika','soccer_usa_mls':'mls','soccer_australia_aleague':'aleague',
  'soccer_efl_champ':'champ','soccer_england_league1':'efl1','soccer_england_league2':'efl2',
  'soccer_spain_segunda_division':'segunda','soccer_italy_serie_b':'serieb',
  'soccer_uefa_champs_league':'ucl','soccer_uefa_europa_league':'uel',
  'soccer_conmebol_copa_libertadores':'libertadores','soccer_conmebol_copa_sudamericana':'sudamericana',
  'americanfootball_nfl':'nfl','americanfootball_ncaaf':'ncaaf',
  'basketball_nba':'nba','basketball_nba_preseason':'nba','basketball_wnba':'wnba','basketball_ncaab':'ncaab',
  'baseball_mlb':'mlb','icehockey_nhl':'nhl','aussierules_afl':'afl',
  'basketball_euroleague':'euroleague','americanfootball_cfl':'cfl',
  'soccer_finland_veikkausliiga':'veikkausliiga','soccer_poland_ekstraklasa':'ekstraklasa',
  'soccer_league_of_ireland':'ireland','soccer_korea_kleague1':'kleague1',
  'soccer_sweden_superettan':'superettan','soccer_ireland_premier_division':'ireland',
  'soccer_germany_liga3':'liga3',
}


def fetch_json(url):
    req = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'brier-archiver/2'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def lig_bul(entry):
    """Sonuclanmis mac kaydindan golkarne lig adi. key yoksa 'lig'/'ligAd' dener; yoksa '_diger'."""
    key = entry.get('key') or ''
    if key in LIG_ESLE:
        return LIG_ESLE[key]
    if key.startswith('tennis_'):
        return 'tenis'
    for alt in ('lig', 'ligKey'):
        v = entry.get(alt)
        if isinstance(v, str) and v in LIG_ESLE:
            return LIG_ESLE[v]
        if isinstance(v, str) and v:
            return v.lower().replace(' ', '_')
    return '_diger'


def anahtar(h, a):
    return '|'.join(sorted([str(h or '').lower(), str(a or '').lower()]))


def kayit_olustur(e):
    """dun.json girdisi -> arsiv kaydi. ac/kap yoksa None birakir (PWA zarif duser)."""
    h, a = e.get('h'), e.get('a')
    if not h or not a:
        return None
    kap = e.get('kap') or {}
    ac = e.get('ac')
    rec = {
        't': e.get('t'),
        'h': h, 'a': a,
        'ac': ac if isinstance(ac, dict) and ac.get('h') is not None else None,
        'kap': kap.get('p') if isinstance(kap.get('p'), dict) else None,
        'kap_tot': kap.get('tot'),
        'kap_spr': kap.get('spr'),
    }
    hs, as_ = e.get('hs'), e.get('as')
    if hs is not None and as_ is not None:
        rec['skor'] = f"{hs}-{as_}"
    elif e.get('skor'):
        rec['skor'] = e['skor']
    # hicbir oran bilgisi yoksa arsivlemenin anlami yok
    if rec['ac'] is None and rec['kap'] is None:
        return None
    return rec


def yukle(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'lig': path.stem, 'guncelleme': None, 'maclar': {}}


BEKLEYEN_DOSYA = OUT_DIR / '_acilis_bekleyen.json'
BEKLEYEN_GUN = 21   # bu kadar gunden eski bekleyen acilislar temizlenir


def mac_id(t, h, a):
    return f"{t}|{h}|{a}"


def bekleyen_yukle():
    if BEKLEYEN_DOSYA.exists():
        try:
            return json.loads(BEKLEYEN_DOSYA.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def bekleyen_topla(bekleyen):
    """bugun.json'daki yaklasan maclarin ACILIS (ac) degerini bekleyen havuza yazar.
    dun.json acilisi tasimadigi icin (worker kopyalamiyor) acilisi burada yakaliyoruz."""
    try:
        bugun = fetch_json(f"{RAILWAY_URL}/bugun.json")
    except Exception as ex:
        print(f"⚠️  bugun.json alinamadi (acilis toplanamadi): {ex}")
        return 0
    yeni = 0
    for blk in (bugun.get('ligler') or {}).values():
        for m in (blk or {}).get('maclar') or []:
            ac = m.get('ac')
            if not (isinstance(ac, dict) and ac.get('h') is not None):
                continue
            mid = mac_id(m.get('t'), m.get('h'), m.get('a'))
            if mid not in bekleyen:          # ilk gorulen acilis korunur (gercek acilisa en yakin)
                bekleyen[mid] = {'ac': ac, 'g': datetime.now(timezone.utc).strftime('%Y-%m-%d')}
                yeni += 1
    return yeni


def bekleyen_temizle(bekleyen):
    sinir = datetime.now(timezone.utc).timestamp() - BEKLEYEN_GUN * 86400
    sil = [k for k, v in bekleyen.items()
           if datetime.strptime(v.get('g', '1970-01-01'), '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() < sinir]
    for k in sil:
        del bekleyen[k]
    return len(sil)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 0) Acilislari topla (bugun.json -> bekleyen havuz)
    bekleyen = bekleyen_yukle()
    yeni_ac = bekleyen_topla(bekleyen)
    print(f"📥 bekleyen acilis: +{yeni_ac} yeni, toplam {len(bekleyen)}")

    url = f"{RAILWAY_URL}/dun.json"
    print(f"🔗 {url}")
    try:
        dun = fetch_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as ex:
        print(f"❌ dun.json alinamadi: {ex}")
        BEKLEYEN_DOSYA.write_text(json.dumps(bekleyen, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        return 1

    gunler = dun.get('gunler') or {}
    if not gunler:
        print("⚠️  dun.json'da 'gunler' yok/bos — yapi degismis olabilir. Ust anahtarlar:", list(dun.keys())[:10])
        BEKLEYEN_DOSYA.write_text(json.dumps(bekleyen, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        return 1

    bugun = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    dokunulan = {}   # lig -> dosya objesi
    eklenen = 0; atlanan = 0; ac_var = 0; ac_birlesen = 0

    for gun, entries in gunler.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            rec = kayit_olustur(e)
            if rec is None:
                atlanan += 1
                continue
            # dun acilisi tasimiyorsa bekleyen havuzdan birlestir
            if rec['ac'] is None:
                b = bekleyen.get(mac_id(rec['t'], rec['h'], rec['a']))
                if b and isinstance(b.get('ac'), dict):
                    rec['ac'] = b['ac']
                    ac_birlesen += 1
            lig = lig_bul(e)
            if lig not in dokunulan:
                dokunulan[lig] = yukle(OUT_DIR / f"{lig}.json")
            d = dokunulan[lig]
            k = anahtar(rec['h'], rec['a'])
            liste = d['maclar'].setdefault(k, [])
            dup = any(x.get('t') == rec['t'] and x.get('h') == rec['h'] and x.get('a') == rec['a'] for x in liste)
            if dup:
                continue
            liste.append(rec)
            eklenen += 1
            if rec['ac'] is not None:
                ac_var += 1

    for lig, d in dokunulan.items():
        for k, liste in d['maclar'].items():
            liste.sort(key=lambda x: str(x.get('t') or ''), reverse=True)
        d['lig'] = lig
        d['guncelleme'] = bugun
        (OUT_DIR / f"{lig}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    silinen = bekleyen_temizle(bekleyen)
    BEKLEYEN_DOSYA.write_text(json.dumps(bekleyen, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    print(f"✅ eklenen: {eklenen}  (acilis tasiyan: {ac_var}, bunun {ac_birlesen}'i bekleyen havuzdan)  atlanan: {atlanan}  lig dosyasi: {len(dokunulan)}  bekleyen temizlenen: {silinen}")
    if eklenen and ac_var == 0:
        print("ℹ️  Bu calismada acilis yok: bekleyen havuz yeni doluyor. Yarinki calismadan itibaren dun'a dusen maclar acilisla gelir.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
