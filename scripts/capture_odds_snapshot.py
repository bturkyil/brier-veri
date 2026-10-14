#!/usr/bin/env python3
"""
Railway'den odds snapshot'ı çekip odds_history/'ne kaydet
Her maçın açılış → kapanış oranlarını takip et
"""

import json
import os
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error

# Railway worker URL
RAILWAY_URL = os.environ.get('RAILWAY_URL', 'https://worker-production-a1ba.up.railway.app')

# Lig → odds_history klasör adı eşlemesi
LIG_ESLE = {
    'soccer_epl': 'epl',
    'soccer_spain_la_liga': 'laliga',
    'soccer_italy_serie_a': 'seriea',
    'soccer_germany_bundesliga': 'bundesliga',
    'soccer_france_ligue_one': 'ligue1',
    'soccer_netherlands_eredivisie': 'eredivisie',
    'soccer_portugal_primeira_liga': 'portekiz',
    'soccer_turkey': 'turkiye',
    'soccer_argentina_primera_division': 'arjantin',
    'soccer_brazil_campeonato': 'brezilya',
    'soccer_mexico_ligamx': 'meksika',
    'soccer_australia_aleague': 'aleague',
    'soccer_usa_mls': 'mls',
    'basketball_nba': 'nba',
    'americanfootball_nfl': 'nfl',
    'baseball_mlb': 'mlb',
    'icehockey_nhl': 'nhl',
}

def fetch_odds():
    """Railway'den bugun.json'u çek"""
    try:
        url = f"{RAILWAY_URL}/bugun.json"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"❌ Odds fetch hatası: {e}")
        return None

def create_daily_summary(odds_data):
    """
    Günlük özet oluştur: her maç için opening → closing oranları
    """

    timestamp = datetime.utcnow().isoformat() + 'Z'
    date_str = timestamp.split('T')[0]

    summary = {
        "date": date_str,
        "timestamp": timestamp,
        "lig_oranları": {}
    }

    if not odds_data:
        return summary

    # Ligleri işle
    ligler = odds_data.get('ligler', {})

    for lig_ad, lig_data in ligler.items():
        key = lig_data.get('key', '')
        klasor_adi = LIG_ESLE.get(key, key.replace('_', ''))

        if klasor_adi not in summary['lig_oranları']:
            summary['lig_oranları'][klasor_adi] = []

        maclar = lig_data.get('maclar', [])

        for mac in maclar:
            # En iyi oranları bulma
            best = mac.get('best', [None, None, None])
            p = mac.get('p', {})  # consensus probability

            odds_entry = {
                "h": mac.get('h', 'Home'),
                "a": mac.get('a', 'Away'),
                "t": mac.get('t', ''),
                "open": {
                    "h": best[0] if best[0] else (1/p.get('h', 0.5) if p.get('h') else None),
                    "a": best[1] if best[1] else (1/p.get('a', 0.5) if p.get('a') else None),
                    "d": best[2] if best[2] else (1/p.get('d', 0.2) if p.get('d') else None)
                },
                "close": {
                    "h": best[0] if best[0] else (1/p.get('h', 0.5) if p.get('h') else None),
                    "a": best[1] if best[1] else (1/p.get('a', 0.5) if p.get('a') else None),
                    "d": best[2] if best[2] else (1/p.get('d', 0.2) if p.get('d') else None)
                },
                "change": {"h": 0, "a": 0, "d": 0}
            }

            summary['lig_oranları'][klasor_adi].append(odds_entry)

    return summary

def save_snapshot(summary):
    """Snapshot'ı odds_history klasörüne kaydet"""

    if not summary or 'lig_oranları' not in summary:
        print("❌ Geçerli veri yok")
        return 0

    saved_count = 0

    for klasor, maclar in summary['lig_oranları'].items():
        if not maclar:
            continue

        # Klasör oluştur
        klasor_path = Path('odds_history') / klasor
        klasor_path.mkdir(parents=True, exist_ok=True)

        # Dosya adı: YYYY-MM-DD.json
        dosya_adi = f"{summary['date']}.json"
        dosya_path = klasor_path / dosya_adi

        # Eğer dosya var ise, update etme (açılış oranlarını koru)
        if dosya_path.exists():
            with open(dosya_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                # Kapanış oranlarını güncelle
                for i, mac in enumerate(maclar):
                    if i < len(existing.get('lig_oranları', {}).get(klasor, [])):
                        existing['lig_oranları'][klasor][i]['close'] = mac['close']
                        existing['lig_oranları'][klasor][i]['timestamp'] = summary['timestamp']
                        # Change hesapla
                        open_h = existing['lig_oranları'][klasor][i]['open']['h'] or 1
                        open_a = existing['lig_oranları'][klasor][i]['open']['a'] or 1
                        close_h = mac['close']['h'] or 1
                        close_a = mac['close']['a'] or 1
                        existing['lig_oranları'][klasor][i]['change'] = {
                            'h': round(((close_h - open_h) / open_h) * 100, 2),
                            'a': round(((close_a - open_a) / open_a) * 100, 2)
                        }
                summary = existing

        # Kaydet
        with open(dosya_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        saved_count += len(maclar)
        print(f"  ✓ {klasor}: {len(maclar)} maç → {dosya_path}")

    return saved_count

def main():
    print("🎲 Odds Snapshot - Railway'den Çek ve Kaydet")
    print("=" * 60)

    # Railway'den veri çek
    print(f"\n🔗 {RAILWAY_URL}/bugun.json'dan çekiliyor...")
    odds_data = fetch_odds()

    if not odds_data:
        print("❌ Veri çekilemedi, iptal.")
        return

    # Özet oluştur
    print("📊 Günlük özet oluşturuluyor...")
    summary = create_daily_summary(odds_data)

    # Kaydet
    print("\n💾 Kaydediliyor...")
    count = save_snapshot(summary)

    print(f"\n✅ Tamamlandı!")
    print(f"   • {count} maç kaydedildi")
    print(f"   • odds_history/ klasörü güncellendi")
    print(f"   • Tarih: {summary['date']}")

if __name__ == '__main__':
    main()
