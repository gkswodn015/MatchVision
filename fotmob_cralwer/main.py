import os
import re
import time
import json

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager


STAT_KEYS = {
    "Ball possession": "possession",
    "Expected goals (xG)": "xg",
    "Total shots": "total_shots",
    "Passes": "passes",
    "Accurate passes": "pass_accuracy",
    "Corners": "corners",
    "Offsides": "offsides",
}


def normalize_fotmob_url(url):
    parts = url.strip().split("/")
    if len(parts) > 3:
        parts[3] = "en-GB"
    normalized = "/".join(parts)

    if ":tab=stats" not in normalized:
        normalized += ":tab=stats"

    return normalized


def crawl_match_stats(url, wait_seconds=3):
    driver = _create_driver()

    try:
        normalized_url = normalize_fotmob_url(url)
        driver.get(normalized_url)
        time.sleep(wait_seconds)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        result = _empty_result(normalized_url)
        result.update(_extract_teams_and_score(driver.title, soup))
        result["stats"].update(_extract_list_stats(soup))
        result["stats"].update(_extract_text_stats(soup))
        result["stats"]["possession"] = _extract_possession(html)
        result["lineups"] = _extract_lineups(soup)

        return result
    finally:
        driver.quit()


def _create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")

    try:
        return webdriver.Edge(options=options)
    except Exception:
        os.environ.setdefault("WDM_SSL_VERIFY", "0")
        service = Service(EdgeChromiumDriverManager().install())
        return webdriver.Edge(service=service, options=options)


def _empty_result(url):
    return {
        "source_url": url,
        "home_team": "HOME",
        "away_team": "AWAY",
        "score": "N/A",
        "stats": {
            "possession": ["N/A", "N/A"],
            "xg": ["N/A", "N/A"],
            "total_shots": ["N/A", "N/A"],
            "passes": ["N/A", "N/A"],
            "pass_accuracy": ["N/A", "N/A"],
            "corners": ["N/A", "N/A"],
            "offsides": ["N/A", "N/A"],
        },
        "lineups": {
            "home": {"starters": [], "subs": []},
            "away": {"starters": [], "subs": []},
        },
    }


def _extract_lineups(soup):
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return {
            "home": {"starters": [], "subs": []},
            "away": {"starters": [], "subs": []},
        }

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return {
            "home": {"starters": [], "subs": []},
            "away": {"starters": [], "subs": []},
        }

    lineup = (
        data.get("props", {})
        .get("pageProps", {})
        .get("content", {})
        .get("lineup", {})
    )
    return {
        "home": _extract_team_lineup(lineup.get("homeTeam", {})),
        "away": _extract_team_lineup(lineup.get("awayTeam", {})),
    }


def _extract_team_lineup(team_data):
    return {
        "starters": [_player_summary(player) for player in team_data.get("starters", [])],
        "subs": [_player_summary(player) for player in team_data.get("subs", [])],
    }


def _player_summary(player):
    return {
        "id": player.get("id"),
        "name": player.get("name") or "Unknown player",
        "shirt_number": player.get("shirtNumber") or "",
        "position_id": player.get("positionId") or player.get("usualPlayingPositionId"),
    }


def _extract_teams_and_score(title, soup):
    clean_title = title.replace(" - FotMob", "").strip()
    home_team = "HOME"
    away_team = "AWAY"

    if " vs " in clean_title:
        home_team, away_part = clean_title.split(" vs ", 1)
        away_team = away_part.split(" - ", 1)[0].strip()
        home_team = home_team.strip()

    page_text = soup.get_text(" ", strip=True)
    score = _extract_score(page_text, home_team, away_team)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "score": score,
    }


def _extract_score(text, home_team, away_team):
    review_match = re.search(r"Match Review.*?\b(\d{1,2})-(\d{1,2})\b", text)
    if review_match:
        return f"{review_match.group(1)} - {review_match.group(2)}"

    ft_match = re.search(r"\bFT\s+(\d{1,2})\s*[-:]\s*(\d{1,2})\b", text)
    if ft_match:
        return f"{ft_match.group(1)} - {ft_match.group(2)}"

    team_score_pattern = (
        rf"{re.escape(home_team)}\s+(\d+)\s*[-:]\s*(\d+)\s+{re.escape(away_team)}"
    )
    match = re.search(team_score_pattern, text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} - {match.group(2)}"

    return "N/A"


def _extract_list_stats(soup):
    stats = {}

    for stat in soup.find_all("li"):
        text = stat.get_text(" ", strip=True)

        for display_name, key in STAT_KEYS.items():
            if display_name not in text or display_name == "Ball possession":
                continue

            if display_name == "Accurate passes":
                stats[key] = _extract_pass_accuracy(text)
            else:
                values = re.findall(r"\d+\.\d+|\d+%?", text)
                if len(values) >= 2:
                    stats[key] = [values[0], values[1]]

    return stats


def _extract_pass_accuracy(text):
    nums = re.findall(r"\d+", text)

    if len(nums) >= 4:
        return [f"{nums[0]} ({nums[1]}%)", f"{nums[2]} ({nums[3]}%)"]

    values = re.findall(r"\d+%?", text)
    if len(values) >= 2:
        return [values[0], values[1]]

    return ["N/A", "N/A"]


def _extract_text_stats(soup):
    text = soup.get_text(" ", strip=True)
    stats = {}

    text_patterns = {
        "xg": "Expected goals \\(xG\\)",
        "total_shots": "Total shots",
        "passes": "Passes",
        "pass_accuracy": "Accurate passes",
        "corners": "Corners",
        "offsides": "Offsides",
    }

    for key, label_pattern in text_patterns.items():
        value_pattern = r"\d+\.\d+|\d+\s+\(\d+%\)|\d+"
        match = re.search(
            rf"({value_pattern})\s+{label_pattern}\s+({value_pattern})",
            text,
        )
        if match:
            stats[key] = [_compact_value(match.group(1)), _compact_value(match.group(2))]

    possession_match = re.search(r"(\d+)\s+Ball possession\s+(\d+)", text)
    if possession_match:
        stats["possession"] = [
            f"{possession_match.group(1)}%",
            f"{possession_match.group(2)}%",
        ]

    return stats


def _compact_value(value):
    return re.sub(r"\s+", " ", value).strip()


def _extract_possession(html):
    index = html.find("Ball possession")
    if index == -1:
        return ["N/A", "N/A"]

    chunk = html[index - 500:index + 500]
    values = re.findall(r"\d+%", chunk)
    if len(values) >= 2:
        return [values[-2], values[-1]]

    return ["N/A", "N/A"]


def print_match_stats(result):
    print("\n========================================")
    print(f"{result['home_team']} vs {result['away_team']}")
    print(f"Score: {result['score']}")
    print("========================================\n")
    print(f"{'STAT':25} {result['home_team']:20} {result['away_team']}")
    print("-" * 75)

    labels = [
        ("Ball possession", "possession"),
        ("Expected goals (xG)", "xg"),
        ("Total shots", "total_shots"),
        ("Passes", "passes"),
        ("Accurate passes", "pass_accuracy"),
        ("Corners", "corners"),
        ("Offsides", "offsides"),
    ]

    for label, key in labels:
        home, away = result["stats"].get(key, ["N/A", "N/A"])
        print(f"{label:25} {home:20} {away}")


if __name__ == "__main__":
    while True:
        print("\n========================================")
        fotmob_url = input("FotMob 경기 URL 입력: ").strip()

        if not fotmob_url:
            continue

        try:
            print_match_stats(crawl_match_stats(fotmob_url))
        except Exception as exc:
            print(f"크롤링 실패: {exc}")
