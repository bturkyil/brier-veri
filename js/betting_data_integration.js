/**
 * Betting Data Integration Module for Brier
 *
 * Lazy-loads betting odds from OddsAPI into match details
 * Displays lines and odds from multiple bookmakers for h2h and spread/totals markets
 */

class BettingDataManager {
  constructor(baseUrl = './betting_data') {
    this.baseUrl = baseUrl;
    this.cache = new Map();
    this.loadingPromises = new Map();
    this.statsCache = new Map();
    this.statsLoadingPromises = new Map();
  }

  /**
   * Get betting lines for a specific match
   * Supports matching by:
   * 1. Match ID (if available from betting data)
   * 2. Team names + commence time (fallback for Brier matches)
   *
   * @param {string} sport - Sport identifier (e.g., 'baseball')
   * @param {string} league - League name (e.g., 'MLB')
   * @param {string|object} matchIdOrData - Match ID string, or {home, away, commenceTime} object
   * @returns {Promise<Array>} Array of betting lines from different bookmakers
   */
  async getMatchBettingLines(sport, league, matchIdOrData) {
    // Support both old and new calling conventions
    const isObject = typeof matchIdOrData === 'object' && matchIdOrData !== null;
    const cacheKey = isObject
      ? `${sport}:${league}:${matchIdOrData.home}:${matchIdOrData.away}:${matchIdOrData.commenceTime || ''}`
      : `${sport}:${league}:${matchIdOrData}`;

    // Check cache first
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    // Avoid duplicate loads
    if (this.loadingPromises.has(cacheKey)) {
      return this.loadingPromises.get(cacheKey);
    }

    // Load data
    const loadPromise = this._loadLeagueData(sport, league)
      .then(data => {
        const matches = data.matches || [];
        let matchData;

        if (isObject) {
          // Match by team names and time
          const { home, away, commenceTime } = matchIdOrData;
          matchData = matches.find(m => {
            const homeMatch = m.home?.toLowerCase() === home?.toLowerCase();
            const awayMatch = m.away?.toLowerCase() === away?.toLowerCase();
            const timeMatch = !commenceTime ||
              this._timesClose(m.commence_time, commenceTime, 3600); // 1 hour tolerance
            return homeMatch && awayMatch && timeMatch;
          });
        } else {
          // Match by ID (with loose matching)
          matchData = matches.find(m =>
            m.id === matchIdOrData || m.id?.includes?.(matchIdOrData)
          );
        }

        return matchData?.betting_lines || [];
      })
      .catch(err => {
        console.warn(`Failed to load betting data for ${cacheKey}:`, err);
        return [];
      });

    this.loadingPromises.set(cacheKey, loadPromise);

    const result = await loadPromise;
    this.cache.set(cacheKey, result);
    this.loadingPromises.delete(cacheKey);

    return result;
  }

  /**
   * Check if two ISO time strings are within a tolerance (in seconds)
   * @private
   */
  _timesClose(time1, time2, toleranceSeconds = 3600) {
    if (!time1 || !time2) return true; // Accept if either is missing
    try {
      const date1 = new Date(time1).getTime();
      const date2 = new Date(time2).getTime();
      const diffSeconds = Math.abs(date1 - date2) / 1000;
      return diffSeconds <= toleranceSeconds;
    } catch (e) {
      return false;
    }
  }

  /**
   * Load all betting data for a league
   * @private
   */
  async _loadLeagueData(sport, league) {
    const url = `${this.baseUrl}/${sport}/${league}_betting_data.json.gz`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        // Try uncompressed fallback
        return await this._loadLeagueDataUncompressed(sport, league);
      }

      // Browser automatically decompresses with Content-Encoding: gzip
      const data = await response.json();
      return data;
    } catch (err) {
      console.warn(`Error loading ${url}:`, err);
      return { matches: [] };
    }
  }

  /**
   * Load uncompressed betting data
   * @private
   */
  async _loadLeagueDataUncompressed(sport, league) {
    const url = `${this.baseUrl}/${sport}/${league}_betting_data.json`;

    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      console.warn(`Error loading ${url}:`, err);
      return { matches: [] };
    }
  }

  /**
   * Get all unique bookmakers
   */
  async getBookmakers(sport, league) {
    const data = await this._loadLeagueData(sport, league);
    const bookmakers = new Set();

    data.matches?.forEach(match => {
      match.betting_lines?.forEach(line => {
        bookmakers.add(line.bookmaker);
      });
    });

    return Array.from(bookmakers).sort();
  }

  /**
   * Get lines grouped by market type
   */
  groupLinesByMarket(bettingLines) {
    const grouped = {
      'h2h': [],
      'spreads': [],
      'totals': [],
      'other': []
    };

    bettingLines.forEach(line => {
      const market = line.market || 'other';
      if (grouped[market]) {
        grouped[market].push(line);
      } else {
        if (!grouped.other) grouped.other = [];
        grouped.other.push(line);
      }
    });

    return grouped;
  }

  /**
   * Get best available line for a selection across bookmakers
   */
  getBestLine(bettingLines, selection) {
    return bettingLines
      .filter(line =>
        (line.market === 'h2h' || line.market === 'spreads') &&
        line.selection === selection
      )
      .reduce((best, current) => {
        // Higher odds are better (best for bettors)
        return current.odds > (best?.odds || 0) ? current : best;
      }, null);
  }

  /**
   * Get all available totals lines
   */
  getTotalLines(bettingLines) {
    const totals = {};

    bettingLines
      .filter(line => line.market === 'totals')
      .forEach(line => {
        const lineValue = line.line;
        if (!totals[lineValue]) {
          totals[lineValue] = [];
        }
        totals[lineValue].push(line);
      });

    return totals;
  }

  /**
   * Get match statistics (corners, cards, goals) from brier_hafiza files
   */
  async getMatchStats(leagueCode, matchId) {
    const cacheKey = `stats:${leagueCode}:${matchId}`;

    if (this.statsCache.has(cacheKey)) {
      return this.statsCache.get(cacheKey);
    }

    if (this.statsLoadingPromises.has(cacheKey)) {
      return this.statsLoadingPromises.get(cacheKey);
    }

    const loadPromise = this._loadStatsData(leagueCode)
      .then(data => {
        // Find matching game in the h2h section
        const h2hData = data.h2h || {};
        for (const matchups of Object.values(h2hData)) {
          const match = matchups.find(m =>
            m.id === matchId || (m.home && m.away &&
            `${m.home}|${m.away}`.includes(matchId))
          );
          if (match) {
            return {
              skor: match.skor,
              corner: match.corner,
              sarı: match.sarı,
              kırmızı: match.kırmızı
            };
          }
        }
        return null;
      })
      .catch(err => {
        console.warn(`Failed to load stats for ${cacheKey}:`, err);
        return null;
      });

    this.statsLoadingPromises.set(cacheKey, loadPromise);
    const result = await loadPromise;
    this.statsCache.set(cacheKey, result);
    this.statsLoadingPromises.delete(cacheKey);

    return result;
  }

  /**
   * Load stats from brier_hafiza_[league].json
   * @private
   */
  async _loadStatsData(leagueCode) {
    const url = `./brier_hafiza_${leagueCode}.json`;

    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      console.warn(`Error loading stats from ${url}:`, err);
      return { h2h: {} };
    }
  }
}

/**
 * HTML Component for displaying betting lines
 */
class BettingLinesComponent {
  constructor(container, bettingManager) {
    this.container = container;
    this.manager = bettingManager;
  }

  /**
   * Render betting lines for a match
   * @param {string} sport - Sport identifier
   * @param {string} league - League name
   * @param {string|object} matchIdOrData - Match ID or {id, home, away, commenceTime} object
   * @param {object} matchInfo - Match info {home, away}
   * @param {string} leagueCode - League code for stats lookup
   */
  async render(sport, league, matchIdOrData, matchInfo, leagueCode) {
    try {
      // Support both string ID and object data
      let matchDataForOdds = matchIdOrData;
      let matchIdForStats = matchIdOrData;

      if (typeof matchIdOrData === 'object' && matchIdOrData !== null) {
        matchDataForOdds = matchIdOrData;
        matchIdForStats = matchIdOrData.id;
      }

      const lines = await this.manager.getMatchBettingLines(sport, league, matchDataForOdds);
      const stats = leagueCode && matchIdForStats ? await this.manager.getMatchStats(leagueCode, matchIdForStats) : null;

      if (lines.length === 0 && !stats) {
        // Silently skip if no data - don't show "Bahis verisi yok" message
        return;
      }

      const grouped = this.manager.groupLinesByMarket(lines);
      if (lines.length > 0 || stats) {
        this.container.innerHTML = this._buildHTML(grouped, matchInfo, stats);
      }
    } catch (err) {
      console.error('Error rendering betting lines:', err);
      // Silently fail - don't show error messages
    }
  }

  /**
   * Build HTML for betting lines
   * @private
   */
  _buildHTML(grouped, matchInfo, stats) {
    let html = '<div class="betting-lines-container">';

    // Match statistics section
    if (stats && (stats.skor || stats.corner || stats.sarı || stats.kırmızı)) {
      html += this._buildStatsSection(stats);
    }

    // Head-to-Head lines
    if (grouped.h2h && grouped.h2h.length > 0) {
      html += this._buildH2HSection(grouped.h2h, matchInfo);
    }

    // Spreads (point spread)
    if (grouped.spreads && grouped.spreads.length > 0) {
      html += this._buildSpreadsSection(grouped.spreads, matchInfo);
    }

    // Totals lines
    if (grouped.totals && grouped.totals.length > 0) {
      html += this._buildTotalsSection(grouped.totals);
    }

    html += '</div>';
    return html;
  }

  /**
   * Build match statistics section
   * @private
   */
  _buildStatsSection(stats) {
    let html = '<div class="betting-section stats">';
    html += '<h4>Maç İstatistikleri</h4>';
    html += '<div class="stats-row">';

    if (stats.skor) {
      html += `<div class="stat"><span class="label">Skor:</span> <strong>${stats.skor}</strong></div>`;
    }
    if (stats.corner) {
      html += `<div class="stat"><span class="label">⚽ Korner:</span> <strong>${stats.corner}</strong></div>`;
    }
    if (stats.sarı) {
      html += `<div class="stat"><span class="label">🟨 Sarı Kart:</span> <strong>${stats.sarı}</strong></div>`;
    }
    if (stats.kırmızı) {
      html += `<div class="stat"><span class="label">🟥 Kırmızı Kart:</span> <strong>${stats.kırmızı}</strong></div>`;
    }

    html += '</div></div>';
    return html;
  }

  /**
   * Build H2H section
   * @private
   */
  _buildH2HSection(h2hLines, matchInfo) {
    const home = matchInfo?.home || 'Home';
    const away = matchInfo?.away || 'Away';

    // Group by home/away
    const homeLines = h2hLines.filter(l => l.selection === home);
    const awayLines = h2hLines.filter(l => l.selection === away);

    let html = '<div class="betting-section h2h">';
    html += '<h4>Maç Sonucu</h4>';
    html += '<div class="betting-matchup">';

    // Home team
    html += '<div class="betting-team home">';
    html += `<strong>${home}</strong>`;
    if (homeLines.length > 0) {
      const bestHome = homeLines.reduce((best, l) =>
        l.odds > (best?.odds || 0) ? l : best
      );
      html += `<div class="best-line">
        <span class="odds">${bestHome.odds.toFixed(2)}</span>
        <span class="book">${bestHome.bookmaker}</span>
      </div>`;

      if (homeLines.length > 1) {
        html += '<details><summary>Tüm odds (' + homeLines.length + ')</summary>';
        html += '<ul class="all-lines">';
        homeLines.forEach(line => {
          html += `<li>${line.bookmaker}: ${line.odds.toFixed(2)}</li>`;
        });
        html += '</ul></details>';
      }
    }
    html += '</div>';

    // Away team
    html += '<div class="betting-team away">';
    html += `<strong>${away}</strong>`;
    if (awayLines.length > 0) {
      const bestAway = awayLines.reduce((best, l) =>
        l.odds > (best?.odds || 0) ? l : best
      );
      html += `<div class="best-line">
        <span class="odds">${bestAway.odds.toFixed(2)}</span>
        <span class="book">${bestAway.bookmaker}</span>
      </div>`;

      if (awayLines.length > 1) {
        html += '<details><summary>Tüm odds (' + awayLines.length + ')</summary>';
        html += '<ul class="all-lines">';
        awayLines.forEach(line => {
          html += `<li>${line.bookmaker}: ${line.odds.toFixed(2)}</li>`;
        });
        html += '</ul></details>';
      }
    }
    html += '</div>';

    html += '</div></div>';

    return html;
  }

  /**
   * Build Spreads section
   * @private
   */
  _buildSpreadsSection(spreadsLines, matchInfo) {
    const home = matchInfo?.home || 'Home';
    const away = matchInfo?.away || 'Away';

    let html = '<div class="betting-section spreads">';
    html += '<h4>Handicap</h4>';
    html += '<div class="betting-matchup">';

    // Group by line value
    const spreadsByLine = {};
    spreadsLines.forEach(line => {
      const key = `${line.selection}:${line.line}`;
      if (!spreadsByLine[key]) {
        spreadsByLine[key] = [];
      }
      spreadsByLine[key].push(line);
    });

    for (const [key, lines] of Object.entries(spreadsByLine)) {
      const [selection, lineValue] = key.split(':');
      const bestLine = lines.reduce((best, l) =>
        l.odds > (best?.odds || 0) ? l : best
      );

      html += '<div class="betting-team">';
      html += `<strong>${selection}</strong>`;
      html += `<div class="best-line">
        <span class="odds">${bestLine.odds.toFixed(2)}</span>
        <span class="line">${lineValue}</span>
        <span class="book">${bestLine.bookmaker}</span>
      </div>`;
      html += '</div>';
    }

    html += '</div></div>';

    return html;
  }

  /**
   * Build Totals section
   * @private
   */
  _buildTotalsSection(totalsLines) {
    const totals = {};
    totalsLines.forEach(line => {
      if (!totals[line.line]) {
        totals[line.line] = [];
      }
      totals[line.line].push(line);
    });

    let html = '<div class="betting-section totals">';
    html += '<h4>Toplam</h4>';
    html += '<div class="betting-totals">';

    Object.entries(totals).sort().forEach(([lineValue, lines]) => {
      const overLines = lines.filter(l =>
        l.selection?.toLowerCase().includes('over') ||
        l.selection?.toLowerCase().includes('üstü')
      );
      const underLines = lines.filter(l =>
        l.selection?.toLowerCase().includes('under') ||
        l.selection?.toLowerCase().includes('altı')
      );

      html += `<div class="total-line" data-line="${lineValue}">`;
      html += `<span class="line-value">${lineValue}</span>`;

      if (overLines.length > 0) {
        const bestOver = overLines.reduce((best, l) =>
          l.odds > (best?.odds || 0) ? l : best
        );
        html += `<span class="ou">Ü: <strong>${bestOver.odds.toFixed(2)}</strong> (${bestOver.bookmaker})</span>`;
      }

      if (underLines.length > 0) {
        const bestUnder = underLines.reduce((best, l) =>
          l.odds > (best?.odds || 0) ? l : best
        );
        html += `<span class="ou">A: <strong>${bestUnder.odds.toFixed(2)}</strong> (${bestUnder.bookmaker})</span>`;
      }

      html += '</div>';
    });

    html += '</div></div>';
    return html;
  }
}

// CSS Styles
const BettingStyles = `
.betting-lines-container {
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 12px;
  margin: 12px 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.betting-section {
  margin-bottom: 16px;
}

.betting-section h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  text-transform: uppercase;
  color: #666;
  border-bottom: 1px solid #ddd;
  padding-bottom: 4px;
}

.betting-matchup {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.betting-team {
  flex: 1;
  min-width: 150px;
  background: white;
  padding: 8px;
  border-radius: 3px;
  border: 1px solid #eee;
}

.betting-team strong {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
}

.best-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.odds {
  font-weight: bold;
  font-size: 16px;
  color: #1a73e8;
}

.line {
  font-weight: bold;
  color: #666;
}

.book {
  font-size: 10px;
  color: #999;
  background: #fafafa;
  padding: 2px 4px;
  border-radius: 2px;
}

.all-lines {
  margin: 4px 0 0 0;
  padding-left: 16px;
  font-size: 11px;
  list-style: none;
}

.all-lines li {
  padding: 2px 0;
  color: #666;
}

.betting-totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}

.total-line {
  background: white;
  padding: 8px;
  border: 1px solid #eee;
  border-radius: 3px;
  text-align: center;
  font-size: 11px;
}

.line-value {
  display: block;
  font-weight: bold;
  margin-bottom: 4px;
  font-size: 13px;
}

.ou {
  display: block;
  padding: 2px 0;
}

.stats-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
}

.stat {
  background: white;
  padding: 6px 10px;
  border-radius: 3px;
  border-left: 3px solid #1a73e8;
}

.stat .label {
  color: #666;
  font-size: 11px;
}

.stat strong {
  color: #1a73e8;
  font-weight: bold;
  font-size: 14px;
}

.ou strong {
  color: #1a73e8;
  font-size: 12px;
}

.betting-no-data,
.betting-error {
  color: #999;
  font-size: 12px;
  text-align: center;
  padding: 12px;
}

.betting-error {
  color: #d32f2f;
}

details {
  cursor: pointer;
  margin-top: 4px;
}

summary {
  font-size: 11px;
  color: #1a73e8;
  outline: none;
}

@media (prefers-color-scheme: dark) {
  .betting-lines-container {
    background: #1e1e1e;
    border-color: #444;
    color: #e0e0e0;
  }

  .betting-team {
    background: #2a2a2a;
    border-color: #444;
    color: #e0e0e0;
  }

  .total-line {
    background: #2a2a2a;
    border-color: #444;
    color: #e0e0e0;
  }

  .odds {
    color: #64b5f6;
  }
}
`;

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    BettingDataManager,
    BettingLinesComponent,
    BettingStyles
  };
}
