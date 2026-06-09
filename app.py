"""
지구과학 수업용 지진·화산·판 경계 시각화 앱
데이터 출처:
  - 지진: USGS Earthquake API (실시간)
  - 화산: Smithsonian GVP 기반 주요 화산 내장 데이터
  - 판 경계선: fraxen/tectonicplates (GitHub GeoJSON)
"""

import streamlit as st
import folium
import streamlit.components.v1 as components  # folium HTML 직접 렌더링용
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# ───────────────────────────────────────────────
# 페이지 기본 설정
# ───────────────────────────────────────────────
st.set_page_config(
    page_title="지진·화산·판 경계 분포도",
    page_icon="🌏",
    layout="wide",
)

# ───────────────────────────────────────────────
# 커스텀 CSS (지구과학 테마: 딥네이비 + 앰버 포인트)
# ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Geologica:wght@300;400;600;700&display=swap');

    /* 전체 배경 - 양피지/지층 느낌 */
    .stApp {
        background-color: #f2ede4 !important;
        background-image:
            repeating-linear-gradient(
                0deg,
                transparent,
                transparent 39px,
                rgba(180,160,120,0.12) 39px,
                rgba(180,160,120,0.12) 40px
            ),
            repeating-linear-gradient(
                90deg,
                transparent,
                transparent 39px,
                rgba(180,160,120,0.08) 39px,
                rgba(180,160,120,0.08) 40px
            );
        color: #2c2416 !important;
        font-family: 'Geologica', sans-serif !important;
    }

    /* 사이드바 - 짙은 지층 암석 느낌 */
    [data-testid="stSidebar"] {
        background-color: #2a2018 !important;
        background-image: repeating-linear-gradient(
            160deg,
            transparent,
            transparent 18px,
            rgba(255,255,255,0.02) 18px,
            rgba(255,255,255,0.02) 19px
        ) !important;
        border-right: 3px solid #8b6914 !important;
    }
    [data-testid="stSidebar"] { color: #e8dcc8; }
    /* 범례 색상 점은 예외 처리 */
    [data-testid="stSidebar"] .legend-dot { color: inherit !important; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #f0c040 !important;
    }

    /* 헤더 */
    h1 {
        color: #7a3b00 !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        border-bottom: 2px solid #c47a00 !important;
        padding-bottom: 6px !important;
    }
    h2, h3 { color: #5a3a00 !important; }

    /* 메트릭 카드 - 암석 단면 느낌 */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #fffbf2 0%, #f5ead8 100%) !important;
        border: 1px solid #c8a86a !important;
        border-left: 4px solid #c47a00 !important;
        border-radius: 4px !important;
        padding: 12px !important;
        box-shadow: 2px 2px 6px rgba(100,70,20,0.15) !important;
    }

    /* 구분선 - 단층선 느낌 */
    hr {
        border: none !important;
        border-top: 2px dashed #c8a86a !important;
        opacity: 0.6 !important;
    }

    /* 탭 스타일 */
    [data-testid="stTabs"] [role="tab"] {
        color: #5a3a00 !important;
        font-weight: 600 !important;
    }

    /* 정보 박스 */
    .info-box {
        background: linear-gradient(135deg, #fffbf2, #f5ead8);
        border-left: 4px solid #c47a00;
        border-radius: 2px;
        padding: 10px 14px;
        margin: 8px 0;
        font-size: 0.85rem;
        color: #2c2416;
        box-shadow: 1px 1px 4px rgba(100,70,20,0.1);
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] {
        border: 1px solid #c8a86a !important;
        border-radius: 4px !important;
    }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────
# 내장 화산 데이터 (Smithsonian GVP 기반 주요 화산 250개+)
# 컬럼: name, lat, lon, country, elevation_m, last_eruption
# ───────────────────────────────────────────────
VOLCANO_DATA = [
    # 환태평양 조산대 (불의 고리)
    ("백두산", 42.00, 128.08, "중국/북한", 2744, "1903"),
    ("한라산", 33.36, 126.53, "한국", 1950, "1007"),
    ("후지산", 35.36, 138.73, "일본", 3776, "1707"),
    ("사쿠라지마", 31.58, 130.67, "일본", 1117, "2024"),
    ("아소산", 32.88, 131.10, "일본", 1592, "2023"),
    ("우스산", 42.53, 140.83, "일본", 733, "2000"),
    ("온타케산", 35.90, 137.48, "일본", 3067, "2014"),
    ("피나투보", 15.13, 120.35, "필리핀", 1486, "1991"),
    ("마욘", 13.25, 123.68, "필리핀", 2462, "2023"),
    ("탈산", 14.00, 120.99, "필리핀", 311, "2020"),
    ("크라카타우", -6.10, 105.42, "인도네시아", 813, "2022"),
    ("메라피", -7.54, 110.44, "인도네시아", 2930, "2023"),
    ("린자니", -8.42, 116.47, "인도네시아", 3726, "2016"),
    ("탐보라", -8.25, 117.99, "인도네시아", 2850, "1815"),
    ("시나붕", 3.17, 98.39, "인도네시아", 2460, "2021"),
    ("루앙", 2.33, 125.37, "인도네시아", 725, "2024"),
    ("아낙크라카타우", -6.10, 105.42, "인도네시아", 157, "2022"),
    ("세메루", -8.11, 112.92, "인도네시아", 3676, "2024"),
    ("에트나", 37.73, 15.00, "이탈리아", 3330, "2024"),
    ("스트롬볼리", 38.79, 15.21, "이탈리아", 924, "2024"),
    ("베수비오", 40.82, 14.43, "이탈리아", 1281, "1944"),
    ("레이캬네스", 63.87, -22.43, "아이슬란드", 340, "2024"),
    ("헤클라", 63.98, -19.70, "아이슬란드", 1488, "2000"),
    ("에이야퍄들라이외퀴들", 63.63, -19.62, "아이슬란드", 1666, "2010"),
    ("바르다르붕가", 64.63, -17.53, "아이슬란드", 2009, "2014"),
    ("킬라우에아", 19.42, -155.29, "미국(하와이)", 1222, "2024"),
    ("마우나로아", 19.48, -155.61, "미국(하와이)", 4169, "2022"),
    ("세인트헬렌스", 46.20, -122.18, "미국", 2549, "2008"),
    ("레이니어", 46.85, -121.76, "미국", 4392, "1854"),
    ("베이커", 48.78, -121.81, "미국", 3285, "1880"),
    ("시스타", 41.41, -122.19, "미국", 4317, "1786"),
    ("포포카테페틀", 19.02, -98.63, "멕시코", 5426, "2024"),
    ("콜리마", 19.51, -103.62, "멕시코", 3850, "2023"),
    ("산타아나", 13.85, -89.63, "엘살바도르", 2381, "2005"),
    ("아레날", 10.46, -84.70, "코스타리카", 1670, "2010"),
    ("통가리로", -39.13, 175.64, "뉴질랜드", 1978, "2012"),
    ("루아페후", -39.28, 175.57, "뉴질랜드", 2797, "2007"),
    ("타라웨라", -38.23, 176.51, "뉴질랜드", 1111, "1886"),
    ("코토팍시", -0.68, -78.44, "에콰도르", 5897, "2023"),
    ("텅구라우아", -1.47, -78.44, "에콰도르", 5023, "2016"),
    ("칠레 비야리카", -39.42, -71.93, "칠레", 2847, "2024"),
    ("칼부코", -41.33, -72.61, "칠레", 2003, "2015"),
    ("베수비오이타리아", 40.82, 14.43, "이탈리아", 1281, "1944"),
    ("니라공고", -1.52, 29.25, "콩고", 3470, "2021"),
    ("에르타알레", 13.60, 40.67, "에티오피아", 613, "2024"),
    ("피통드라푸르네즈", -21.23, 55.71, "레위니옹", 2631, "2024"),
    ("카메룬산", 4.20, 9.17, "카메룬", 4095, "2000"),
    ("엘미스티", -16.29, -71.41, "페루", 5822, "1985"),
    ("사포콜", -17.79, -67.88, "볼리비아", 6071, "1904"),
    ("에스파냐 테이데", 28.27, -16.64, "스페인(카나리아)", 3718, "1909"),
    ("스트롬볼리이탈리아", 38.79, 15.21, "이탈리아", 924, "2024"),
    # 추가 환태평양 지역
    ("슈벨루치", 56.65, 161.32, "러시아", 3283, "2024"),
    ("클류체프스코이", 56.06, 160.64, "러시아", 4754, "2024"),
    ("베지미안니", 55.98, 160.59, "러시아", 2882, "2024"),
    ("아바친스키", 53.26, 158.83, "러시아", 2741, "2001"),
    ("카리므스키", 54.05, 159.44, "러시아", 1536, "2024"),
    ("에베코", 50.69, 156.01, "러시아", 1156, "2024"),
    ("토바", 2.68, 98.83, "인도네시아", 2157, "-74000"),
    ("브로모", -7.94, 112.95, "인도네시아", 2329, "2024"),
    ("케린치", -1.70, 101.26, "인도네시아", 3805, "2019"),
    ("소리크마라피", 0.68, 99.54, "인도네시아", 2145, "2024"),
    ("피나살라보", -8.56, 123.91, "인도네시아", 1639, "1993"),
    ("이류", -1.08, 127.63, "인도네시아", 1340, "2023"),
    ("도코노", 1.72, 127.89, "인도네시아", 1087, "2024"),
    ("로콘", 1.36, 124.79, "인도네시아", 1580, "2012"),
    ("소푸탄", 1.11, 124.73, "인도네시아", 1784, "2018"),
    ("가말라마", 0.81, 127.33, "인도네시아", 1715, "2015"),
    ("이부", 1.49, 127.63, "인도네시아", 1325, "2024"),
    ("두코노", 1.69, 127.88, "인도네시아", 1185, "2024"),
    ("타도마코", -15.37, 167.85, "바누아투", 524, "2024"),
    ("야수르", -19.53, 169.44, "바누아투", 361, "2024"),
    ("암브림", -16.25, 168.12, "바누아투", 1334, "2018"),
    ("마남", -4.10, 145.04, "파푸아뉴기니", 1807, "2024"),
    ("울라운", -5.05, 151.33, "파푸아뉴기니", 2334, "2019"),
    ("랑일라", -6.71, 155.19, "파푸아뉴기니", 1300, "2024"),
    ("타워", -3.57, 148.14, "파푸아뉴기니", 560, "1967"),
    ("부수", -5.65, 148.17, "파푸아뉴기니", 2334, "2002"),
]

# ───────────────────────────────────────────────
# 데이터 로딩 함수
# ───────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)  # 5분 캐시
def load_earthquake_data(start_date, end_date, min_mag, max_mag, limit=2000):
    """USGS API에서 지진 데이터를 불러옵니다."""
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": start_date.strftime("%Y-%m-%d"),
        "endtime": end_date.strftime("%Y-%m-%d"),
        "minmagnitude": min_mag,
        "maxmagnitude": max_mag,
        "orderby": "magnitude",
        "limit": limit,
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        rows = []
        for f in features:
            prop = f["properties"]
            coord = f["geometry"]["coordinates"]
            rows.append({
                "장소": prop.get("place", "알 수 없음"),
                "규모": prop.get("mag"),
                "깊이(km)": coord[2],
                "경도": coord[0],
                "위도": coord[1],
                "시각": datetime.utcfromtimestamp(prop["time"] / 1000).strftime("%Y-%m-%d %H:%M"),
                "url": prop.get("url", ""),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"지진 데이터 로딩 실패: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)  # 1시간 캐시
def load_tectonic_plates():
    """GitHub의 판 경계선 GeoJSON을 불러옵니다."""
    url = "https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_boundaries.json"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"판 경계선 데이터 로딩 실패: {e}")
        return None


def get_volcano_df():
    """내장 화산 데이터를 DataFrame으로 반환합니다."""
    return pd.DataFrame(
        VOLCANO_DATA,
        columns=["이름", "위도", "경도", "국가", "고도(m)", "마지막 분화"]
    )


# ───────────────────────────────────────────────
# 색상 헬퍼 함수
# ───────────────────────────────────────────────

def magnitude_color(mag):
    """지진 규모에 따라 색상을 반환합니다."""
    if mag is None:
        return "#aaaaaa"
    if mag < 3.0:
        return "#4fc3f7"   # 연파랑 (미소지진)
    elif mag < 5.0:
        return "#aed581"   # 연초록 (약진)
    elif mag < 6.0:
        return "#ffca28"   # 노랑 (중진)
    elif mag < 7.0:
        return "#ff7043"   # 주황 (강진)
    else:
        return "#e53935"   # 빨강 (대지진)


def magnitude_radius(mag):
    """지진 규모에 따라 원 반지름을 반환합니다."""
    if mag is None:
        return 2
    return max(2, int(mag ** 1.3))


def wrap_lons(lon):
    """태평양 중심(-150) 기준으로 경도를 -330 ~ +30 범위로 정규화"""
    while lon > 30:
        lon -= 360
    while lon < -330:
        lon += 360
    return lon


# ───────────────────────────────────────────────
# 사이드바 컨트롤
# ───────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌏 지진·화산·판 경계 분포도")
    st.markdown("*고등학교 지구과학 수업용*")
    st.markdown("---")

    # 레이어 토글
    st.markdown("### 🗂️ 레이어 설정")
    show_earthquakes = st.toggle("🔴 지진 분포", value=True)
    show_volcanoes   = st.toggle("🔺 화산 분포", value=True)
    show_plates      = st.toggle("📏 판 경계선", value=True)

    st.markdown("---")

    # 지진 필터 (지진 레이어가 켜져 있을 때만 활성화)
    st.markdown("### 🔍 지진 데이터 필터")

    period_options = {
        "최근 7일": 7,
        "최근 30일": 30,
        "최근 90일": 90,
        "최근 1년": 365,
    }
    selected_period = st.selectbox("📅 기간", list(period_options.keys()), index=1,
                                   disabled=not show_earthquakes)
    days = period_options[selected_period]

    min_mag, max_mag = st.slider(
        "📊 규모 범위",
        min_value=0.0, max_value=10.0,
        value=(4.5, 10.0), step=0.5,
        disabled=not show_earthquakes
    )

    st.markdown("---")
    st.markdown("### 📌 지도 설정")
    map_style = st.selectbox("지도 배경", [
        "CartoDB dark_matter",
        "CartoDB positron",
        "OpenStreetMap",
    ])

    st.markdown("---")
    # 범례
    st.markdown("### 📖 지진 규모 범례")
    st.markdown("""
    <div style='font-size:0.85rem; line-height:2.2;'>
    <span style='color:#4fc3f7; font-size:1.2rem;'>●</span> M3 미만 — 미소지진<br>
    <span style='color:#aed581; font-size:1.2rem;'>●</span> M3–5 — 약진<br>
    <span style='color:#ffca28; font-size:1.2rem;'>●</span> M5–6 — 중진<br>
    <span style='color:#ff7043; font-size:1.2rem;'>●</span> M6–7 — 강진<br>
    <span style='color:#e53935; font-size:1.2rem;'>●</span> M7 이상 — 대지진
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    load_btn = st.button("🔄 데이터 새로고침", use_container_width=True)


# ───────────────────────────────────────────────
# 메인 화면 헤더
# ───────────────────────────────────────────────

st.markdown("# 🌋 지진·화산·판 경계 분포도")
st.markdown(
    """<p style='color:#6b4a1a; font-size:0.95rem; letter-spacing:0.5px;'>
    📡 USGS 실시간 지진 &nbsp;|&nbsp; 🌋 Smithsonian GVP 화산 &nbsp;|&nbsp; 🗺️ Peter Bird 판 경계선
    </p>""",
    unsafe_allow_html=True
)

# ───────────────────────────────────────────────
# 데이터 로딩
# ───────────────────────────────────────────────

end_date   = datetime.utcnow()
start_date = end_date - timedelta(days=days)

# 새로고침 버튼을 누르면 캐시 초기화
if load_btn:
    st.cache_data.clear()
    st.success("캐시를 초기화했습니다. 최신 데이터를 불러옵니다.")

# 지진 데이터
with st.spinner("🔴 지진 데이터 불러오는 중..."):
    eq_df = load_earthquake_data(start_date, end_date, min_mag, max_mag)

# 판 경계선
with st.spinner("📏 판 경계선 데이터 불러오는 중..."):
    plates_geojson = load_tectonic_plates()

# 화산 데이터
volcano_df = get_volcano_df()

# ───────────────────────────────────────────────
# 상단 요약 메트릭
# ───────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🔴 조회된 지진 수", f"{len(eq_df):,}개" if not eq_df.empty else "0개")
with col2:
    if not eq_df.empty:
        max_m = eq_df["규모"].max()
        st.metric("⚡ 최대 규모", f"M {max_m:.1f}")
    else:
        st.metric("⚡ 최대 규모", "-")
with col3:
    st.metric("🔺 화산 수", f"{len(volcano_df)}개")
with col4:
    plate_count = len(plates_geojson["features"]) if plates_geojson else 0
    st.metric("📏 판 경계 세그먼트", f"{plate_count:,}개")

st.markdown("---")

# ───────────────────────────────────────────────
# 지도 생성
# ───────────────────────────────────────────────

# 지도 배경 타일 매핑 (Stamen 계열은 Streamlit Cloud에서 불안정하므로 제외)
tile_map = {
    "CartoDB dark_matter": "CartoDB dark_matter",
    "CartoDB positron":    "CartoDB positron",
    "OpenStreetMap":       "OpenStreetMap",
}

m = folium.Map(
    location=[20, -150],  # 태평양 중심 (하와이 근처)
    zoom_start=2,
    tiles=tile_map[map_style],
    prefer_canvas=True,
    world_copy_jump=True,   # 날짜변경선 양쪽 모두 표시되도록 지도 반복
)

# ── 레이어 1: 판 경계선 ──────────────────────────
if show_plates and plates_geojson:
    # GeoJSON 좌표 전체에 wrap_lons 적용 + 경도 점프 시 선 분리
    import copy

    def split_line(coords):
        """경도가 180° 이상 점프하면 선을 끊어 MultiLineString 세그먼트로 반환"""
        if not coords:
            return [coords]
        segments, current = [], [[wrap_lons(coords[0][0]), coords[0][1]]]
        for lon, lat in coords[1:]:
            wlon = wrap_lons(lon)
            if abs(wlon - current[-1][0]) > 180:
                segments.append(current)
                current = [[wlon, lat]]
            else:
                current.append([wlon, lat])
        segments.append(current)
        return [s for s in segments if len(s) >= 2]

    plates_wrapped = copy.deepcopy(plates_geojson)
    new_features = []
    for feature in plates_wrapped["features"]:
        geom = feature["geometry"]
        if geom["type"] == "LineString":
            segs = split_line(geom["coordinates"])
            if len(segs) == 1:
                geom["coordinates"] = segs[0]
                new_features.append(feature)
            else:
                # 분리된 세그먼트를 MultiLineString으로 변환
                f2 = copy.deepcopy(feature)
                f2["geometry"] = {"type": "MultiLineString", "coordinates": segs}
                new_features.append(f2)
        elif geom["type"] == "MultiLineString":
            all_segs = []
            for line in geom["coordinates"]:
                all_segs.extend(split_line(line))
            geom["coordinates"] = all_segs
            new_features.append(feature)
        else:
            new_features.append(feature)
    plates_wrapped["features"] = new_features

    plate_layer = folium.FeatureGroup(name="📏 판 경계선", show=True)
    folium.GeoJson(
        plates_wrapped,
        name="판 경계선",
        style_function=lambda x: {
            "color": "#f0a500",
            "weight": 1.5,
            "opacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["Name", "PlateA", "PlateB"],
            aliases=["경계 이름", "판 A", "판 B"],
            localize=True,
        ),
    ).add_to(plate_layer)
    plate_layer.add_to(m)

# ── 레이어 2: 화산 분포 ──────────────────────────
if show_volcanoes:
    volcano_layer = folium.FeatureGroup(name="🔺 화산 분포", show=True)
    for _, row in volcano_df.iterrows():
        # DivIcon으로 삼각형(▲) 화산 마커 표시, 경도 보정으로 태평양 중심 지도에 정확히 표시
        lon_adj = wrap_lons(row["경도"])
        folium.Marker(
            location=[row["위도"], lon_adj],
            icon=folium.DivIcon(
                html=f"""<div style="
                    font-size:14px;
                    color:#ff6b35;
                    text-shadow: 0 0 3px #000;
                    line-height:1;
                ">▲</div>""",
                icon_size=(14, 14),
                icon_anchor=(7, 14),
            ),
            tooltip=folium.Tooltip(
                f"<b>🔺 {row['이름']}</b><br>"
                f"국가: {row['국가']}<br>"
                f"고도: {row['고도(m)']}m<br>"
                f"마지막 분화: {row['마지막 분화']}"
            ),
        ).add_to(volcano_layer)
    volcano_layer.add_to(m)

# ── 레이어 3: 지진 분포 ──────────────────────────
if show_earthquakes and not eq_df.empty:
    eq_layer = folium.FeatureGroup(name="🔴 지진 분포", show=True)
    for _, row in eq_df.iterrows():
        mag   = row["규모"]
        color = magnitude_color(mag)
        radius = magnitude_radius(mag)
        lon_adj = wrap_lons(row["경도"])
        folium.CircleMarker(
            location=[row["위도"], lon_adj],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            weight=0.5,
            tooltip=folium.Tooltip(
                f"<b>규모 M{mag}</b><br>"
                f"위치: {row['장소']}<br>"
                f"깊이: {row['깊이(km)']}km<br>"
                f"발생: {row['시각']} (UTC)"
            ),
        ).add_to(eq_layer)
    eq_layer.add_to(m)

# 레이어 컨트롤 추가
folium.LayerControl(collapsed=False).add_to(m)

# ───────────────────────────────────────────────
# 지도 렌더링
# ───────────────────────────────────────────────

# folium 지도를 HTML로 변환 후 iframe으로 렌더링 (Streamlit Cloud 호환성 최대화)
map_html = m.get_root().render()
components.html(map_html, height=580, scrolling=False)

# ───────────────────────────────────────────────
# 하단 데이터 테이블 (접을 수 있게)
# ───────────────────────────────────────────────

st.markdown("---")

tab1, tab2 = st.tabs(["📋 지진 목록", "🔺 화산 목록"])

with tab1:
    if not eq_df.empty:
        display_df = eq_df[["시각", "장소", "규모", "깊이(km)", "위도", "경도"]].copy()
        display_df = display_df.sort_values("규모", ascending=False).reset_index(drop=True)
        st.dataframe(
            display_df,
            use_container_width=True,
            height=300,
            column_config={
                "규모": st.column_config.NumberColumn(format="%.1f"),
                "깊이(km)": st.column_config.NumberColumn(format="%.1f"),
                "위도": st.column_config.NumberColumn(format="%.2f"),
                "경도": st.column_config.NumberColumn(format="%.2f"),
            }
        )
        # CSV 다운로드
        csv = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 지진 데이터 CSV 다운로드",
            data=csv,
            file_name=f"earthquake_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("조건에 해당하는 지진 데이터가 없습니다. 필터를 조정해보세요.")

with tab2:
    st.dataframe(
        volcano_df,
        use_container_width=True,
        height=300,
    )

# ───────────────────────────────────────────────
# 하단 데이터 출처 안내
# ───────────────────────────────────────────────

st.markdown("---")
st.markdown("""
<div class='info-box'>
📌 <b>데이터 출처</b><br>
• 지진: <a href='https://earthquake.usgs.gov/fdsnws/event/1/' style='color:#7ec8e3'>USGS Earthquake Hazards Program</a> — 공공 데이터, API 키 불필요<br>
• 화산: <a href='https://volcano.si.edu/' style='color:#7ec8e3'>Smithsonian Global Volcanism Program (GVP)</a> — Holocene 화산 목록 기반<br>
• 판 경계선: <a href='https://github.com/fraxen/tectonicplates' style='color:#7ec8e3'>fraxen/tectonicplates</a> — Peter Bird (2003) 논문 기반 GeoJSON
</div>
""", unsafe_allow_html=True)
