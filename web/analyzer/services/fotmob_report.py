import json
import sys
from pathlib import Path


STAT_ROWS = [
    ("possession", "점유율"),
    ("xg", "xG"),
    ("total_shots", "전체 슈팅 수"),
    ("passes", "전체 패스 수"),
    ("pass_accuracy", "패스 정확도"),
    ("corners", "코너킥 수"),
    ("offsides", "오프사이드 수"),
]


def crawl_fotmob_report(url):
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from fotmob_cralwer.main import crawl_match_stats

    return crawl_match_stats(url)


def dump_fotmob_report(report):
    return json.dumps(report, ensure_ascii=False)


def load_fotmob_report(raw_text):
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def build_fotmob_table(report):
    if not report:
        return []

    stats = report.get("stats", {})
    rows = []

    for key, label in STAT_ROWS:
        home, away = stats.get(key, ["N/A", "N/A"])
        rows.append({
            "label": label,
            "home": home,
            "away": away,
        })

    return rows


def build_fotmob_player_options(report, group):
    if not report:
        return []

    side = "home" if group == "home" else "away"
    lineups = report.get("lineups", {})
    team_lineup = lineups.get(side, {}) if isinstance(lineups, dict) else {}

    options = []
    options.extend(_player_options(team_lineup.get("starters", []), "선발"))
    options.extend(_player_options(team_lineup.get("subs", []), "교체"))
    return options


def _player_options(players, squad_type):
    options = []
    if not isinstance(players, list):
        return options

    for player in players:
        if not isinstance(player, dict):
            continue
        name = player.get("name")
        if not name:
            continue
        shirt_number = player.get("shirt_number") or player.get("shirtNumber") or ""
        label = f"#{shirt_number} {name}" if shirt_number else name
        options.append({
            "value": name,
            "label": f"{label} ({squad_type})",
            "name": name,
            "jersey_number": shirt_number,
            "shirt_number": shirt_number,
            "squad_type": squad_type,
        })

    return options
