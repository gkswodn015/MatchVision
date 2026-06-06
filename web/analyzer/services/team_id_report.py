import json


EMPTY_TEAM_IDS = {
    "home_ids": [],
    "away_ids": [],
    "referee_ids": [],
    "unknown_ids": [],
}


def dump_team_ids(team_ids):
    return json.dumps(team_ids or EMPTY_TEAM_IDS, ensure_ascii=False)


def load_team_ids(raw_text):
    if not raw_text:
        return EMPTY_TEAM_IDS.copy()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return EMPTY_TEAM_IDS.copy()

    result = EMPTY_TEAM_IDS.copy()
    if not isinstance(data, dict):
        return result

    for key in result:
        values = data.get(key, [])
        result[key] = values if isinstance(values, list) else []

    return result


def build_team_id_sections(team_ids, fotmob_report):
    home_name = "홈팀"
    away_name = "원정팀"

    if fotmob_report:
        home_name = fotmob_report.get("home_team") or home_name
        away_name = fotmob_report.get("away_team") or away_name

    return [
        {
            "title": home_name,
            "group": "home",
            "entries": _entries(team_ids.get("home_ids", [])),
        },
        {
            "title": away_name,
            "group": "away",
            "entries": _entries(team_ids.get("away_ids", [])),
        },
    ]


def _entries(items):
    entries = []
    for item in items:
        if isinstance(item, dict) and "id" in item:
            entries.append({
                "id": item["id"],
                "frames": item.get("frames", 0),
            })
        elif isinstance(item, int):
            entries.append({
                "id": item,
                "frames": 0,
            })
    return sorted(entries, key=lambda entry: entry["id"])
