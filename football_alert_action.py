#!/usr/bin/env python3

import os
import json
import time
import requests
from datetime import datetime


API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_URL = "https://v3.football.api-sports.io"

# ================= FILTRI =================

MINUTE_MIN = 10
MINUTE_MAX = 25

GOALS_ALLOWED = True        # deve essere 0-0
SHOTS_ON_TARGET_MIN = 2     # tiri in porta totali
POSSESSION_MIN = None       # esempio 65, altrimenti None

# ===========================================

STATE_FILE = "notified_matches.json"


def load_notified():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_notified(data):
    with open(STATE_FILE, "w") as f:
        json.dump(list(data), f)


def api_get(endpoint, params=None):

    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }

    try:
        r = requests.get(
            BASE_URL + endpoint,
            headers=headers,
            params=params,
            timeout=15
        )

        if r.status_code == 429:
            print("Limite API raggiunto")
            return None

        r.raise_for_status()

        return r.json()

    except Exception as e:
        print("Errore API:", e)
        return None



def get_live_matches():

    data = api_get(
        "/fixtures",
        {"live": "all"}
    )

    if not data:
        return []

    return data.get("response", [])



def get_statistics(fixture_id):

    data = api_get(
        "/fixtures/statistics",
        {"fixture": fixture_id}
    )

    if not data:
        return None

    response = data.get("response", [])

    if not response:
        return None


    shots = 0
    possession = 0
    details = []


    for team in response:

        name = team.get("team", {}).get("name")

        for stat in team.get("statistics", []):

            value = stat.get("value")


            if stat["type"] == "Shots on Goal":

                if isinstance(value, int):
                    shots += value

                details.append(
                    f"{name}: {value} tiri in porta"
                )


            if stat["type"] == "Ball Possession":

                try:
                    pct = int(str(value).replace("%",""))
                    possession = max(possession, pct)

                except:
                    pass


                details.append(
                    f"{name}: {value} possesso"
                )


    return shots, possession, details



def send_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:

        r = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text
            },
            timeout=15
        )

        r.raise_for_status()

        return True

    except Exception as e:

        print("Errore Telegram:", e)
        return False



def main():

    notified = load_notified()

    matches = get_live_matches()

    print(
        f"[{datetime.now()}] "
        f"Partite live trovate: {len(matches)}"
    )


    for match in matches:

        fixture_id = match["fixture"]["id"]

        elapsed = match["fixture"]["status"].get("elapsed")


        if elapsed is None:
            continue


        if elapsed < MINUTE_MIN or elapsed > MINUTE_MAX:
            continue


        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]


        home_goals = match["goals"]["home"]
        away_goals = match["goals"]["away"]


        if GOALS_ALLOWED:

            if home_goals != 0 or away_goals != 0:
                continue


        if fixture_id in notified:
            continue


        print(
            f"Analizzo {home} - {away} "
            f"({elapsed}')"
        )


        stats = get_statistics(fixture_id)


        if stats is None:

            print(
                "Statistiche non disponibili"
            )

            continue



        shots, possession, details = stats


        print(
            f"{home} vs {away} -> "
            f"{shots} tiri porta, "
            f"{possession}% possesso"
        )


        if shots < SHOTS_ON_TARGET_MIN:
            continue


        if POSSESSION_MIN:

            if possession < POSSESSION_MIN:
                continue



        msg = (
            "🚨 POSSIBILE GOL\n\n"
            f"{home} - {away}\n"
            f"Minuto: {elapsed}'\n"
            f"Risultato: {home_goals}-{away_goals}\n"
            f"Tiri in porta: {shots}\n\n"
            + "\n".join(details)
        )


        if send_telegram(msg):

            notified.add(fixture_id)

            print(
                "NOTIFICA INVIATA"
            )


    save_notified(notified)



if __name__ == "__main__":
    main()
