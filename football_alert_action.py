#!/usr/bin/env python3
"""
Football Alert Bot - versione per GitHub Actions
---------------------------------------------------
Esegue UN SOLO controllo (non un loop infinito): GitHub Actions si occupa
di richiamarlo periodicamente secondo lo schedule definito nel workflow.

Controlla le partite LIVE e invia un messaggio Telegram quando, entro il
20esimo minuto di gioco, il totale dei tiri in porta delle due squadre
raggiunge o supera la soglia (default: 4).
"""

import os
import json
import requests
from datetime import datetime

API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ============== FILTRI (modifica solo qui) ==============
# --- VALORI DI TEST: coprono qualsiasi minuto e qualsiasi tiro in porta ---
MINUTE_MIN = 0                   # minuto minimo da cui iniziare a controllare
MINUTE_MAX = 30                 # minuto massimo entro cui controllare (200 = nessun limite pratico)
SHOTS_ON_TARGET_THRESHOLD = 2    # tiri in porta totali (somma delle due squadre)
POSSESSION_THRESHOLD = None      # es. 65 per avvisare se una squadra ha >=65% possesso, None per disattivare
# Tutti i filtri attivi devono essere veri insieme (AND) perché scatti la notifica
# ===========================================================

STATE_FILE = "notified_matches.json"
BASE_URL = "https://v3.football.api-sports.io"


def load_notified():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_notified(notified_set):
    with open(STATE_FILE, "w") as f:
        json.dump(list(notified_set), f)


def get_live_fixtures():
    url = f"{BASE_URL}/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    resp = requests.get(url, headers=headers, params={"live": "all"}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_match_stats(fixture_id):
    """Restituisce: tiri in porta totali, possesso massimo tra le due squadre, dettaglio testuale."""
    url = f"{BASE_URL}/fixtures/statistics"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    resp = requests.get(url, headers=headers, params={"fixture": fixture_id}, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("response", [])

    total_sot = 0
    max_possession = 0
    breakdown = []
    for team_stats in data:
        team_name = team_stats.get("team", {}).get("name", "?")
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "Shots on Goal":
                value = stat.get("value") or 0
                total_sot += value
                breakdown.append(f"{team_name}: {value} tiri in porta")
            elif stat.get("type") == "Ball Possession":
                raw = stat.get("value") or "0%"
                pct = int(str(raw).replace("%", "") or 0)
                max_possession = max(max_possession, pct)
                breakdown.append(f"{team_name}: {raw} possesso")

    return total_sot, max_possession, breakdown


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def main():
    notified = load_notified()
    fixtures = get_live_fixtures()

    print(f"Partite live trovate: {len(fixtures)}")

    for fixture in fixtures:
        fixture_id = fixture["fixture"]["id"]
        elapsed = fixture["fixture"]["status"].get("elapsed")

        if elapsed is None or elapsed < MINUTE_MIN or elapsed > MINUTE_MAX:
            print(f"Fixture {fixture_id}: fuori dalla finestra minuto ({elapsed}') -> scartata")
            continue

        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        total_sot, max_poss, breakdown = get_match_stats(fixture_id)

        already_notified = fixture_id in notified
        print(f"[{datetime.now()}] {home} vs {away} ({elapsed}') -> "
              f"{total_sot} tiri in porta, possesso max {max_poss}% "
              f"(gia notificata: {already_notified})")

        if already_notified:
            continue

        conditions_met = total_sot >= SHOTS_ON_TARGET_THRESHOLD
        if POSSESSION_THRESHOLD is not None:
            conditions_met = conditions_met and max_poss >= POSSESSION_THRESHOLD

        if conditions_met:
            text = (f"⚽ {home} - {away}\n"
                    f"Al {elapsed}': {total_sot} tiri in porta\n" + "\n".join(breakdown))
            send_telegram_message(text)
            notified.add(fixture_id)
            print(f"-> Notifica Telegram inviata per fixture {fixture_id}")

    save_notified(notified)


if __name__ == "__main__":
    main()
