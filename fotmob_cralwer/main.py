from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import time
import re

# ====================================
# Edge 옵션 설정
# ====================================
options = Options()

# 브라우저 숨기기
options.add_argument("--headless")

# webdriver-manager 사용
service = Service(
    EdgeChromiumDriverManager().install()
)

# ====================================
# 반복 실행
# ====================================
while True:

    print("\n========================================")

    url = input("FotMob 경기 URL 입력: ")

    # 빈 입력 방지
    if url.strip() == "":
        continue

    # ====================================
    # URL 영어 버전 강제 변환
    # ====================================
    try:

        parts = url.split("/")

        # language 부분 강제 변경
        parts[3] = "en-GB"

        url = "/".join(parts)

    except:

        print("잘못된 URL 형식")
        continue

    # ====================================
    # stats 탭 자동 이동
    # ====================================
    if ":tab=stats" not in url:
        url += ":tab=stats"

    # ====================================
    # 매 반복마다 새 driver 생성
    # ====================================
    driver = webdriver.Edge(
        service=service,
        options=options
    )

    # ====================================
    # 페이지 접속
    # ====================================
    driver.get(url)



    # ====================================
    # HTML 가져오기
    # ====================================
    html = driver.page_source

    # BeautifulSoup 분석
    soup = BeautifulSoup(html, "html.parser")

    # ====================================
    # 팀 이름 추출
    # ====================================
    title = driver.title.replace(" - FotMob", "")

    # 영어 페이지
    if " vs " in title:

        teams = title.split(" vs ")

        home_team = teams[0].strip()

        away_team = teams[1].split(" - ")[0].strip()

    # 한국어 fallback
    elif " 대 " in title:

        teams = title.split(" 대 ")

        home_team = teams[0].strip()

        away_team = teams[1].split(" - ")[0].strip()

    else:

        home_team = "HOME"

        away_team = "AWAY"

    # ====================================
    # 경기 날짜 추출
    # ====================================
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", html)

    if date_match:
        match_date = date_match.group()
    else:
        match_date = "날짜 정보 없음"

    # ====================================
    # stat 저장
    # ====================================
    all_stats = {}

    stats = soup.find_all("li")

    for stat in stats:

        text = stat.get_text(" ", strip=True)

        stat_names = [
            "Expected goals (xG)",
            "Total shots",
            "Passes",
            "Accurate passes",
            "Corners",
            "Offsides"
        ]

        for name in stat_names:

            if name in text:

                # Accurate passes 별도 처리
                if name == "Accurate passes":

                    nums = re.findall(
                        r"\d+",
                        text
                    )

                    if len(nums) >= 4:

                        home_value = (
                            nums[0] + " (" + nums[1] + "%)"
                        )

                        away_value = (
                            nums[2] + " (" + nums[3] + "%)"
                        )

                        all_stats[name] = (
                            home_value,
                            away_value
                        )

                else:

                    values = re.findall(
                        r"\d+\.\d+|\d+%?",
                        text
                    )

                    if len(values) >= 2:

                        all_stats[name] = (
                            values[0],
                            values[1]
                        )

    # ====================================
    # Ball possession 별도 처리
    # ====================================
    possession_home = "N/A"
    possession_away = "N/A"

    index = html.find("Ball possession")

    if index != -1:

        chunk = html[index-500:index+500]

        values = re.findall(r"\d+%", chunk)

        if len(values) >= 2:

            possession_home = values[-2]
            possession_away = values[-1]

    # ====================================
    # 출력 함수
    # ====================================
    def print_stat(display_name):

        if display_name in all_stats:

            home, away = all_stats[display_name]

            print(
                f"{display_name:25} "
                f"{home:20} "
                f"{away}"
            )

        else:

            print(
                f"{display_name:25} "
                f"{'N/A':20} "
                f"{'N/A'}"
            )

    # ====================================
    # 결과 출력
    # ====================================
    print("\n========================================")
    print("경기 날짜:", match_date)
    print("========================================\n")

    print(f"{home_team} vs {away_team}\n")

    print(
        f"{'STAT':25} "
        f"{home_team:20} "
        f"{away_team}"
    )

    print("-" * 75)

    print(
        f"{'Ball possession':25} "
        f"{possession_home:20} "
        f"{possession_away}"
    )

    print_stat("Expected goals (xG)")

    print_stat("Total shots")

    print_stat("Passes")

    print_stat("Accurate passes")

    print_stat("Corners")

    print_stat("Offsides")

    # ====================================
    # driver 종료
    # ====================================
    driver.quit()
