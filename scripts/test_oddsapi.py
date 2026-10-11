#!/usr/bin/env python3
"""
Test script to diagnose OddsAPI response format
"""

import json
import urllib.request
import urllib.error
import sys

def test_api(api_key, sport_key="soccer_epl"):
    """Test API with a single sport"""
    base_url = "https://api.the-odds-api.com/v4"

    print(f"Testing OddsAPI with sport: {sport_key}")
    print(f"=" * 60)

    try:
        # Test 1: Get sports list
        print("\n1️⃣  Testing /sports endpoint...")
        url = f"{base_url}/sports?apiKey={api_key}"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"   Response type: {type(data)}")
            print(f"   Is list: {isinstance(data, list)}")
            if isinstance(data, list) and len(data) > 0:
                print(f"   First item type: {type(data[0])}")
                print(f"   First item keys: {data[0].keys() if isinstance(data[0], dict) else 'N/A'}")
                active = [s for s in data if s.get('active')]
                print(f"   Active sports: {len(active)}")

        # Test 2: Get odds for specific sport
        print(f"\n2️⃣  Testing /odds endpoint for {sport_key}...")
        url = f"{base_url}/sports/{sport_key}/odds"
        url += f"?apiKey={api_key}&regions=us,eu,uk&markets=h2h,spreads,totals&oddsFormat=decimal"

        with urllib.request.urlopen(url) as response:
            raw = response.read().decode()
            print(f"   Raw response length: {len(raw)} chars")
            print(f"   First 300 chars: {raw[:300]}")

            data = json.loads(raw)
            print(f"   Response type: {type(data)}")

            if isinstance(data, dict):
                print(f"   Dict keys: {list(data.keys())}")
                if 'events' in data:
                    events = data['events']
                    print(f"   'events' type: {type(events)}")
                    print(f"   'events' length: {len(events) if isinstance(events, list) else 'N/A'}")
                    if isinstance(events, list) and len(events) > 0:
                        print(f"   First event type: {type(events[0])}")
                        if isinstance(events[0], dict):
                            print(f"   First event keys: {list(events[0].keys())}")
            elif isinstance(data, list):
                print(f"   List length: {len(data)}")
                if len(data) > 0:
                    print(f"   First item type: {type(data[0])}")
                    if isinstance(data[0], dict):
                        print(f"   First item keys: {list(data[0].keys())}")

    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP Error {e.code}: {e}")
        print(f"   Response: {e.read().decode()[:500]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_oddsapi.py <API_KEY> [sport_key]")
        sys.exit(1)

    api_key = sys.argv[1]
    sport = sys.argv[2] if len(sys.argv) > 2 else "soccer_epl"

    test_api(api_key, sport)
