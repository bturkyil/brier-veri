# Brier OddsAPI Entegrasyonu

OddsAPI'den canlı bahis odds'larını Brier'e otomatik olarak çeken sistem.

## 🚀 Hızlı Başlangıç (3 Adım)

### 1️⃣ GitHub Secrets Ayarla
```
Settings → Secrets and variables → Actions
Add: ODDSAPI_KEY = 4a6ca9ef72befb200a0f488602d73b9a
```

### 2️⃣ index.html'i Güncelle
Closing `</body>` tag'ından önce ekle:
```html
<script src="./js/betting_data_integration.js"></script>

<script>
// Bahis verisi yöneticisini başlat
const bettingManager = new BettingDataManager('./betting_data');

// Match detaylarını gösterirken ekle:
async function displayBettingOdds(sport, league, matchId, homeTeam, awayTeam) {
  const container = document.createElement('div');
  container.id = 'betting-odds-' + matchId;
  
  // Match detay container'ına ekle
  document.getElementById('match-details').appendChild(container);
  
  const component = new BettingLinesComponent(container, bettingManager);
  await component.render(sport, league, matchId, {
    home: homeTeam,
    away: awayTeam
  });
}

// CSS'i ekle
const style = document.createElement('style');
style.textContent = BettingStyles;
document.head.appendChild(style);
</script>
```

### 3️⃣ Workflow'u Trigger Et
```bash
git add .
git commit -m "Add OddsAPI betting odds"
git push
```

Workflow otomatik çalışacak veya "Actions" tab'ında manual trigger edebilirsin.

---

## 📊 Veri Yapısı

```
betting_data/
├── baseball/
│   └── MLB_betting_data.json.gz
├── soccer/
│   ├── EPL_betting_data.json.gz
│   ├── LaLiga_betting_data.json.gz
│   └── ...
├── basketball/
│   └── NBA_betting_data.json.gz
└── ...
```

Her dosya şu yapıya sahip:
```json
{
  "sport": "baseball",
  "league": "MLB",
  "generated_at": "2026-10-11T18:55:00Z",
  "matches": [
    {
      "id": "...",
      "home": "New York Yankees",
      "away": "Boston Red Sox",
      "commence_time": "2026-10-11T21:00:00Z",
      "betting_lines": [
        {
          "bookmaker": "fanduel",
          "market": "h2h",
          "selection": "New York Yankees",
          "line": null,
          "odds": 1.95,
          "snapshot_time": "2026-10-11T18:54:30Z"
        },
        ...
      ]
    }
  ]
}
```

---

## 🔧 JavaScript API

### BettingDataManager
```javascript
const manager = new BettingDataManager('./betting_data');

// Match'in tüm odds'larını al
const lines = await manager.getMatchBettingLines('baseball', 'MLB', 'match_123');

// Tüm kitaplar
const bookmakers = await manager.getBookmakers('soccer', 'EPL');

// Market tipine göre grupla
const grouped = manager.groupLinesByMarket(lines);
// → { h2h: [...], spreads: [...], totals: [...] }

// En iyi odd bul
const best = manager.getBestLine(lines, 'New York Yankees');

// Totals çizgileri
const totals = manager.getTotalLines(lines);
// → { '7.5': [...], '8.0': [...], ... }
```

### BettingLinesComponent
```javascript
const component = new BettingLinesComponent(container, manager);

// Match'i render et
await component.render('baseball', 'MLB', 'match_123', {
  home: 'New York Yankees',
  away: 'Boston Red Sox'
});
```

---

## 📅 Otomatik Sync

**Schedule**: Her gün saat 2 AM UTC (sabah 5 AM Istanbul)

**El ile trigger**: GitHub Actions tab'ında → OddsAPI Sync → Run workflow

**Logs**: Actions tab'ında job çıktısını görebilirsin

---

## 🎯 Desteklenen Sporlar

- ⚾ Baseball (MLB, NPB, KBO)
- 🏀 Basketball (NBA, NCAAB)
- 🏈 American Football (NFL, NCAAF)
- ⚽ Soccer (EPL, LaLiga, Bundesliga, Serie A, Ligue 1, ve 50+ lig)
- 🏒 Ice Hockey (NHL, SHL)
- 🎾 Tennis (ATP, WTA)
- 🏉 Rugby (Super Rugby, NRL, etc.)
- 🏌️ Golf (PGA Tour, Major Championships)
- 🥊 MMA (UFC, Bellator)
- 🏇 Horse Racing
- Ve daha birçoğu...

---

## 📈 Bahis Marketleri

- **h2h** (Head-to-Head): Maç sonucu odds'ları
- **spreads** (Handicap): Point spread lines
- **totals** (Over/Under): Toplam puan/gol lines

---

## 🐛 Sorun Giderme

### Veri yüklenmiyorsa

```javascript
// Console'de debug et
fetch('./betting_data/baseball/MLB_betting_data.json.gz')
  .then(r => console.log('Status:', r.status))
  .catch(e => console.log('Error:', e));
```

### Workflow başarısız oldu

1. Actions tab'ında hata log'unu kontrol et
2. ODDSAPI_KEY secret'ı ayarlandı mı? (`Settings → Secrets`)
3. API key geçerli mi?

### Özel lig/sport lazım mı?

ODDS_SETUP.md'de BrierDataBuilder.SPORT_MAPPING'i düzenleyin

---

## 🔐 Security

- API key GitHub Secrets'ta tutulur (repo'da değil)
- Tüm veriler public (read-only)
- Günlük snapshot history tutulur

---

## 📚 Daha Fazla Bilgi

- **OddsAPI Docs**: https://the-odds-api.com/
- **Brier GitHub**: https://github.com/bturkyil/brier-veri

---

**Created**: 2026-10-11
**Status**: Production Ready ✅
