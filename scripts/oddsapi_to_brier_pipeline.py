#!/usr/bin/env python3
"""
OddsAPI to Brier Pipeline
Fetches live betting odds from OddsAPI and transforms them into Brier format.

Usage:
    python oddsapi_to_brier_pipeline.py --api-key <YOUR_KEY> --output ./betting_data
"""

import json
import gzip
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import urllib.request
import urllib.error
import ssl

class OddsAPIClient:
    """Client for OddsAPI"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        self.session_count = 0
        self.max_sessions = 500  # API limit

    def get_sports(self):
        """Get all available sports"""
        try:
            url = f"{self.base_url}/sports?apiKey={self.api_key}"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                self.session_count += 1
                return [sport for sport in data if sport.get('active')]
        except Exception as e:
            print(f"Error fetching sports: {e}")
            return []

    def get_odds(self, sport_key, regions="us,eu,uk", markets="h2h,spreads,totals"):
        """Get odds for a specific sport"""
        try:
            url = f"{self.base_url}/sports/{sport_key}/odds"
            url += f"?apiKey={self.api_key}&regions={regions}&markets={markets}&oddsFormat=decimal"

            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                self.session_count += 1

                # Debug: log response type and first item
                if isinstance(data, dict):
                    return data.get('events', [])
                elif isinstance(data, list):
                    # API returns array directly
                    return data
                else:
                    print(f"  ⚠️  Unexpected response type for {sport_key}: {type(data)}")
                    return []
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"Sport {sport_key} not found")
            else:
                print(f"Error fetching odds for {sport_key}: {e}")
            return []
        except Exception as e:
            print(f"Error fetching odds for {sport_key}: {e}")
            return []

    def sessions_remaining(self):
        """Check API session count"""
        return self.max_sessions - self.session_count

class BrierDataBuilder:
    """Builds Brier-formatted betting data"""

    SPORT_MAPPING = {
        # American Football
        'american_football_nfl': ('american_football', 'NFL'),
        'american_football_ncaaf': ('american_football', 'NCAAF'),

        # Baseball
        'baseball_mlb': ('baseball', 'MLB'),
        'baseball_ncaa': ('baseball', 'NCAAB'),
        'baseball_japanese_league': ('baseball', 'NPB'),
        'baseball_korean_league': ('baseball', 'KBO'),

        # Basketball
        'basketball_nba': ('basketball', 'NBA'),
        'basketball_ncaab': ('basketball', 'NCAAB'),

        # Ice Hockey
        'ice_hockey_nhl': ('ice_hockey', 'NHL'),
        'ice_hockey_shl': ('ice_hockey', 'SHL'),

        # Soccer - top leagues
        'soccer_england_premier_league': ('soccer', 'EPL'),
        'soccer_spain_la_liga': ('soccer', 'LaLiga'),
        'soccer_germany_bundesliga': ('soccer', 'Bundesliga'),
        'soccer_france_ligue_1': ('soccer', 'Ligue1'),
        'soccer_italy_serie_a': ('soccer', 'SerieA'),
        'soccer_netherlands_eredivisie': ('soccer', 'Eredivisie'),
        'soccer_portugal_primeira_liga': ('soccer', 'PrimeiraLiga'),
        'soccer_brazil_serie_a': ('soccer', 'BrazilSerieA'),
        'soccer_argentina': ('soccer', 'Argentina'),
        'soccer_mexico_primera_division': ('soccer', 'MexicanLiga'),
        'soccer_turkey_super_lig': ('soccer', 'TurkishSuperLig'),
        'soccer_greece_super_league': ('soccer', 'GreeceSuperLeague'),
        'soccer_belgium': ('soccer', 'BelgianPro'),
        'soccer_australia_aleague': ('soccer', 'ALeague'),
        'soccer_japan': ('soccer', 'JLeague'),
        'soccer_korea_k_league_1': ('soccer', 'KLeague1'),
        'soccer_europe_uefa_euro': ('soccer', 'EuroChampionship'),
        'soccer_europe_champions_league': ('soccer', 'ChampionsLeague'),
        'soccer_europe_uefa_cup': ('soccer', 'EuropaLeague'),

        # Tennis
        'tennis_atp': ('tennis', 'ATP'),
        'tennis_wta': ('tennis', 'WTA'),

        # Cricket
        'cricket_ipl': ('cricket', 'IPL'),
        'cricket_big_bash': ('cricket', 'BBL'),

        # Golf
        'golf_major_championships': ('golf', 'MajorChampionships'),
        'golf_pga_tour': ('golf', 'PGATour'),

        # MMA
        'mma_ufc': ('mma', 'UFC'),
        'mma_bellator': ('mma', 'Bellator'),

        # Rugby
        'rugby_union_super_rugby': ('rugby', 'SuperRugby'),
        'rugby_league_nrl': ('rugby_league', 'NRL'),

        # Motorsports
        'motorsports_formula1': ('motorsports', 'F1'),
        'motorsports_motogp': ('motorsports', 'MotoGP'),
        'motorsports_nascar': ('motorsports', 'NASCAR'),
    }

    def __init__(self):
        self.data = defaultdict(lambda: defaultdict(list))

    def add_odds(self, sport_key, events):
        """Add OddsAPI events to Brier format"""
        if sport_key not in self.SPORT_MAPPING:
            print(f"  ⚠️  Sport {sport_key} not in mapping (will skip)")
            return 0

        sport_family, league_name = self.SPORT_MAPPING[sport_key]
        count = 0

        for event in events:
            match_id = event['id']
            home_team = event['home_team']
            away_team = event['away_team']

            betting_lines = []

            # Process each bookmaker
            for bookmaker in event.get('bookmakers', []):
                bookmaker_name = bookmaker['key']

                for market in bookmaker.get('markets', []):
                    market_name = market['key']

                    for outcome in market.get('outcomes', []):
                        line_obj = {
                            'bookmaker': bookmaker_name,
                            'market': market_name,
                            'selection': outcome['name'],
                            'line': outcome.get('point'),
                            'odds': outcome.get('price'),
                            'snapshot_time': datetime.utcnow().isoformat() + 'Z'
                        }
                        betting_lines.append(line_obj)

            if betting_lines:
                match = {
                    'id': match_id,
                    'home': home_team,
                    'away': away_team,
                    'commence_time': event.get('commence_time'),
                    'betting_lines': betting_lines,
                    'line_count': len(betting_lines),
                    'bookmakers': list(set(bl['bookmaker'] for bl in betting_lines))
                }
                self.data[sport_family][league_name].append(match)
                count += 1

        return count

    def get_data(self):
        """Return organized data structure"""
        result = {}
        for sport_family, leagues in self.data.items():
            result[sport_family] = {}
            for league_name, matches in leagues.items():
                result[sport_family][league_name] = {
                    'sport': sport_family,
                    'league': league_name,
                    'generated_at': datetime.utcnow().isoformat() + 'Z',
                    'matches': matches
                }
        return result

def save_data(data, output_dir, compress=True):
    """Save Brier data to files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files_written = 0

    for sport_family, leagues in data.items():
        sport_dir = output_path / sport_family
        sport_dir.mkdir(parents=True, exist_ok=True)

        for league_name, league_data in leagues.items():
            # Filename: MLB_betting_data.json.gz
            clean_league = league_name.replace(' ', '_').replace('/', '_')
            filename = f"{clean_league}_betting_data"

            if compress:
                filepath = sport_dir / f"{filename}.json.gz"
                with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                    json.dump(league_data, f, indent=2)
            else:
                filepath = sport_dir / f"{filename}.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(league_data, f, indent=2)

            files_written += 1
            match_count = len(league_data.get('matches', []))
            print(f"  ✓ {sport_family}/{clean_league}: {match_count} matches → {filepath.name}")

    return files_written

def main():
    parser = argparse.ArgumentParser(
        description='Fetch odds from OddsAPI and format for Brier'
    )
    parser.add_argument('--api-key', required=True, help='OddsAPI key')
    parser.add_argument('--output', default='./betting_data', help='Output directory')
    parser.add_argument('--no-compress', action='store_true', help='Save uncompressed JSON')
    parser.add_argument('--regions', default='us,eu,uk', help='Regions to fetch')
    parser.add_argument('--markets', default='h2h,spreads,totals', help='Markets to fetch')
    parser.add_argument('--limit', type=int, help='Limit sports to fetch (for testing)')

    args = parser.parse_args()

    print("🎲 OddsAPI → Brier Pipeline")
    print(f"⏱️  {datetime.utcnow().isoformat()}Z\n")

    # Initialize
    client = OddsAPIClient(args.api_key)
    builder = BrierDataBuilder()

    # Fetch sports
    print("📊 Fetching available sports...")
    sports = client.get_sports()
    print(f"  Found {len(sports)} active sports\n")

    # Limit for testing
    if args.limit:
        sports = sports[:args.limit]
        print(f"  (Limited to {args.limit} sports for testing)\n")

    # Process each sport
    total_matches = 0
    total_bookmakers = set()
    total_markets = set()

    for i, sport in enumerate(sports, 1):
        sport_key = sport['key']
        sport_title = sport['title']

        print(f"[{i}/{len(sports)}] {sport_title} ({sport_key})")

        # Fetch odds
        events = client.get_odds(
            sport_key,
            regions=args.regions,
            markets=args.markets
        )

        if events:
            # Add to builder
            count = builder.add_odds(sport_key, events)
            total_matches += count

            # Collect bookmakers and markets
            for event in events:
                for bookmaker in event.get('bookmakers', []):
                    total_bookmakers.add(bookmaker['key'])
                    for market in bookmaker.get('markets', []):
                        total_markets.add(market['key'])

            print(f"  ✓ {count} matches, {client.sessions_remaining()} API calls remaining\n")
        else:
            print(f"  - No odds data\n")

    # Save data
    print("\n💾 Saving to files...")
    data = builder.get_data()
    files_written = save_data(data, args.output, compress=not args.no_compress)

    # Statistics
    print(f"\n📈 Summary:")
    print(f"  • Sports processed: {len(sports)}")
    print(f"  • Total matches: {total_matches}")
    print(f"  • Unique bookmakers: {len(total_bookmakers)}")
    print(f"    {', '.join(sorted(total_bookmakers))}")
    print(f"  • Unique markets: {len(total_markets)}")
    print(f"    {', '.join(sorted(total_markets))}")
    print(f"  • Files created: {files_written}")
    print(f"  • API calls used: {client.session_count}/{client.max_sessions}")
    print(f"  • Remaining quota: {client.sessions_remaining()}")

    print(f"\n✅ Done!")

if __name__ == '__main__':
    main()
