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
