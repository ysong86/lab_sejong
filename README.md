# 세종 디지털트윈 — 움직여 보는 행복도시

행복도시 건물 9,284동 + 실제 지형(20m) 위에서 해·그림자·일조시간, 금강 수위 시나리오, 조망, 밤 풍경을 시험하는 3D 실험실.

## 만들기
```
C:\Python313\python.exe fetch_osm.py   # OSM 물·공원·도로·랜드마크 → data/raw/osm.json (한 번)
C:\Python313\python.exe prepare.py     # → site/twin.json + site/twin.bin
```
- 건물 외곽선은 `../sejong_vacant/data/footprints.json`(브이월드 GIS건물통합정보)을 그대로 쓴다.
- 지형은 AWS terrarium z14 타일(data/raw/dem 캐시). 결측 화소(-1,800m)는 주변 중앙값으로 메움.
- 금강 평상시 수면은 하천 폴리곤 안 격자 하위 20% 고도를 동서 1km 구간별로 잡아 직선 맞춤(x=0 에서 12.85m, 0.39m/km).

## 소개 영상
`C:\Python313\python.exe make_video.py` → docs/디지털트윈_소개.mp4 + site/preview.mp4(50초). 가짜 시계로 한 프레임씩 캡처(로컬 서버 8790 필요).

## 화면(site/index.html, 한 파일)
three.js 0.169 + three-mesh-bvh 0.8.3(CDN). 로컬 확인은 launch.json `sejong-twin`(8790).
- 01 해와 그림자: SunCalc 식 태양 위치 → 실시간 그림자(보는 곳 따라가는 그림자 카메라). 벽을 누르면 5분 간격 광선으로 일조시간, 동지 09–15 연속 2h / 08–16 합계 4h 판정.
- 02 물이 차오르면: 경사 수면(배스터브) — 건물 지반고 < 수면이면 깊이별 색. 생활권별 집계, 비 효과.
- 03 여기서 보이는 것: 눈 위치 점광원 그림자 = 가시권, 옥상 중심 광선으로 보이는 건물·랜드마크.
- 04 출퇴근 정체: ../sejong_fire 의 ITS 소통정보(30분 표본, data/raw/its)와 표준노드링크(network.json)로 구간별 평일·주말 0~23시 중앙값.
  색 = 그 구간 하루 중 가장 빠를 때 대비 비율(40/60/80%). 도로는 LineSegments2(화면 픽셀 굵기), 차 불빛은 속도 ×8 연출.
  KTDB View-T(승용차·버스 시간대별)는 로그인 필요 — 사용자가 받아 넘기면 붙일 것.
- 05 둘러보기: 7장면 자동 비행.
- 움직이기: MapControls(끌기=이동, 오른쪽 끌기=돌리기), 두 번 누르기=그곳으로, WASD·QE·RF 키, 🚶/G 걸어 보기(사람 눈높이 1인칭, Shift 달리기, 휠·RF 로 떠오르기, 모바일은 방향판).
- 밤(해 고도 -1°~-7°)이면 창문 불빛(셰이더)·가로등·빛번짐. 링크(#m,d,t,r,c)로 장면 공유, PNG 저장.
