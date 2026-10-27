# 세종 디지털트윈 자료 만들기
#   지형(AWS terrarium z14) + 건물 외곽선(상가공실 상황판이 받아 둔 브이월드 9,284동) + OSM(물·공원·도로·랜드마크)
#   → site/twin.json(메타·이름·라벨) + site/twin.bin(지형 높이·건물 좌표·선형 자료)
# 좌표는 중심(LON0, LAT0) 기준 동(+x)·북(+y) 미터.
import json, math, os, struct, urllib.request
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "site")
FOOT = os.path.join(HERE, "..", "sejong_vacant", "data", "footprints.json")
FIRE = os.path.join(HERE, "..", "sejong_fire", "data")        # 화재안전 상황판이 모은 ITS 소통정보·표준노드링크

LON0, LAT0 = 127.285, 36.503
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
W0, E0, S0, N0 = 127.205, 127.362, 36.447, 36.558   # 지형 범위
DEM_Z = 14
CELL = 20.0                                          # 지형 격자 간격(m)


def xy(lon, lat):
    return (lon - LON0) * KX, (lat - LAT0) * KY


# ── 지형
def tile(z, x, y):
    p = os.path.join(RAW, "dem", "%d_%d_%d.png" % (z, x, y))
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        u = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/%d/%d/%d.png" % (z, x, y)
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
            open(p, "wb").write(r.read())
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def fxy(lon, lat, z):
    n = 2 ** z
    return ((lon + 180) / 360 * n,
            (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)


def build_dem():
    x0, y0 = fxy(W0, N0, DEM_Z)
    x1, y1 = fxy(E0, S0, DEM_Z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = tile(DEM_Z, tx, ty)
    # 결측 화소(-1,800m 같은 튐)는 주변 정상값 중앙값으로 메운다
    bad = mos < 3
    for j, i in zip(*np.where(bad)):
        win = mos[max(j - 3, 0):j + 4, max(i - 3, 0):i + 4]
        ok = win[win >= 3]
        mos[j, i] = np.median(ok) if ok.size else 10
    xmin, ymin = xy(W0, S0)
    xmax, ymax = xy(E0, N0)
    nx = int((xmax - xmin) / CELL) + 1
    ny = int((ymax - ymin) / CELL) + 1
    gx = xmin + np.arange(nx) * CELL
    gy = ymax - np.arange(ny) * CELL                # 북쪽 줄부터
    LON = LON0 + gx / KX
    LAT = LAT0 + gy / KY
    n = 2 ** DEM_Z
    px = ((LON + 180) / 360 * n - tx0) * 256 - 0.5
    lr = np.radians(LAT)
    py = ((1 - np.log(np.tan(lr) + 1 / np.cos(lr)) / math.pi) / 2 * n - ty0) * 256 - 0.5
    PX, PY = np.meshgrid(px, py)
    i0 = np.clip(np.floor(PX).astype(int), 0, mos.shape[1] - 2)
    j0 = np.clip(np.floor(PY).astype(int), 0, mos.shape[0] - 2)
    fx, fy = PX - i0, PY - j0
    h = (mos[j0, i0] * (1 - fx) * (1 - fy) + mos[j0, i0 + 1] * fx * (1 - fy)
         + mos[j0 + 1, i0] * (1 - fx) * fy + mos[j0 + 1, i0 + 1] * fx * fy)
    return dict(x0=float(xmin), y1=float(ymax), nx=nx, ny=ny, cell=CELL), h


def sample(dem, H, x, y):
    i = (x - dem["x0"]) / CELL
    j = (dem["y1"] - y) / CELL
    i0 = min(max(int(i), 0), dem["nx"] - 2)
    j0 = min(max(int(j), 0), dem["ny"] - 2)
    fx, fy = min(max(i - i0, 0), 1), min(max(j - j0, 0), 1)
    return (H[j0, i0] * (1 - fx) * (1 - fy) + H[j0, i0 + 1] * fx * (1 - fy)
            + H[j0 + 1, i0] * (1 - fx) * fy + H[j0 + 1, i0 + 1] * fx * fy)


def area(r):
    s = 0
    for k in range(len(r) - 1):
        s += r[k][0] * r[k + 1][1] - r[k + 1][0] * r[k][1]
    return s / 2


RK = {"living_street": 0, "residential": 0, "unclassified": 0, "tertiary": 1, "secondary": 2, "primary": 3, "trunk": 4, "motorway": 5}


def main():
    os.makedirs(OUT, exist_ok=True)
    dem, H = build_dem()
    print("지형", dem["nx"], "x", dem["ny"], "고도", round(H.min(), 1), "~", round(H.max(), 1))

    # ── 건물
    F = json.load(open(FOOT, encoding="utf-8"))["features"]
    pts, starts, meta, names = [], [], [], []
    for f in F:
        p = f["properties"]
        polys = f["geometry"]["coordinates"]
        if f["geometry"]["type"] == "Polygon":
            polys = [polys]
        ring = max((pl[0] for pl in polys), key=lambda r: abs(area(r)))   # 가장 큰 바깥 고리만
        loc = [xy(lo, la) for lo, la in ring]
        if loc[0] == loc[-1]:
            loc = loc[:-1]
        if len(loc) < 3:
            continue
        a = area(loc + [loc[0]])
        if a < 0:                                    # 반시계로 맞춘다
            loc = loc[::-1]
        base = min(sample(dem, H, x, y) for x, y in loc)
        h = p.get("h") or 4.0
        starts.append(len(pts))
        pts.extend(loc)
        meta.append((len(loc), int(round(h * 10)), int(round(base * 10)), int(p.get("fl") or 0),
                     "123456S".index(p["z"]) if p.get("z") in list("123456S") else 7, abs(a)))
        names.append([p.get("nm") or "", p.get("use") or ""])
    nb = len(meta)
    print("건물", nb, "꼭짓점", len(pts))

    # ── OSM
    osm = json.load(open(os.path.join(RAW, "osm.json"), encoding="utf-8"))["elements"]
    water, parks, roads, rails, labels, river_rings = [], [], [], [], [], []

    def ring_of(geom):
        return [xy(g["lon"], g["lat"]) for g in geom]

    for e in osm:
        t = e.get("tags", {})
        rings = []
        if e["type"] == "way" and "geometry" in e:
            rings = [ring_of(e["geometry"])]
        elif e["type"] == "relation":
            rings = [ring_of(m["geometry"]) for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        if t.get("natural") == "water" or t.get("waterway") == "riverbank":
            water += rings
            if t.get("water") == "river" or t.get("waterway") == "riverbank":
                river_rings.extend(rings)
        elif t.get("leisure") == "park" or t.get("name") == "국립세종수목원":
            parks += rings
        if e["type"] == "way" and t.get("highway") in RK and "geometry" in e:
            roads.append((ring_of(e["geometry"]), RK[t["highway"]]))
        if e["type"] == "way" and t.get("railway") == "rail":
            rails.append(ring_of(e["geometry"]))

    def centroid_of(e):
        if e["type"] == "node":
            return xy(e["lon"], e["lat"])
        b = e.get("bounds")
        if b:
            return xy((b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2)
        return None

    WANT = {"정부세종청사": "청사", "세종특별자치시청": "시청", "국립세종도서관": "도서관", "대통령기록관": "기록관",
            "세종호수공원": "공원", "국립세종수목원": "공원", "세종중앙공원": "공원", "이응다리": "다리",
            "국립도시건축박물관": "박물관", "국립어린이박물관": "박물관", "세종보 인증센터 (무인)": "세종보",
            "원수산": "산", "전월산": "산", "괴화산": "산", "방축천수변공원": "공원", "독락정 역사공원": "공원"}
    seen = set()
    for e in osm:
        nm = e.get("tags", {}).get("name")
        if nm in WANT and nm not in seen:
            c = centroid_of(e)
            if c is None and e["type"] == "way" and "geometry" in e:
                g = e["geometry"]
                c = xy(sum(q["lon"] for q in g) / len(g), sum(q["lat"] for q in g) / len(g))
            if c is None:
                continue
            seen.add(nm)
            show = {"세종보 인증센터 (무인)": "세종보", "독락정 역사공원": "독락정", "이응다리": "이응다리(금강보행교)"}.get(nm, nm)
            labels.append({"n": show, "k": WANT[nm], "x": round(c[0], 1), "y": round(c[1], 1),
                           "z": round(float(sample(dem, H, *c)), 1)})
    print("라벨", len(labels), sorted(set(WANT) - seen))

    # 금강 평상시 수면 추정: 하천 폴리곤 안 격자를 동서 1km 구간으로 나눠 하위 20% 고도 → 직선(하류=서쪽으로 낮아짐)
    from matplotlib.path import Path
    gx = dem["x0"] + np.arange(dem["nx"]) * CELL
    gy = dem["y1"] - np.arange(dem["ny"]) * CELL
    GX, GY = np.meshgrid(gx, gy)
    P = np.c_[GX.ravel(), GY.ravel()]
    inr = np.zeros(P.shape[0], bool)
    for r in river_rings:
        if abs(area(r)) > 100000:
            inr |= Path(r).contains_points(P)
    rx, rz = P[inr, 0], H.ravel()[inr]
    bx, bz = [], []
    for k in range(int(rx.min() // 1000), int(rx.max() // 1000) + 1):
        m = (rx >= k * 1000) & (rx < (k + 1) * 1000)
        if m.sum() > 30:
            bx.append(k * 1000 + 500)
            bz.append(np.percentile(rz[m], 20))
    slope, river = np.polyfit(bx, bz, 1)
    print("금강 수면 추정: x=0 에서", round(river, 2), "m, 경사", round(slope * 1000, 3), "m/km", len(bx), "구간")

    # ── 직렬화: 모든 좌표는 0.1m 정수(Int32)
    blobs, offs = [], {}

    def put(name, arr):
        b = arr.tobytes()
        pad = (-sum(len(x) for x in blobs)) % 4
        if pad:
            blobs.append(b"\0" * pad)
        offs[name] = [sum(len(x) for x in blobs), arr.dtype.str, int(arr.size)]
        blobs.append(b)

    put("dem", np.clip(np.round(H * 10), 0, 65535).astype("<u2").ravel())
    put("bpts", np.round(np.array(pts) * 10).astype("<i4").ravel())
    m = np.array([(c, h, b, fl, z) for c, h, b, fl, z, _ in meta], dtype=np.int64)
    put("bcnt", m[:, 0].astype("<u2"))
    put("bh", m[:, 1].astype("<u2"))
    put("bbase", m[:, 2].astype("<u2"))
    put("bfl", m[:, 3].astype("<u1"))
    put("bzone", m[:, 4].astype("<u1"))
    put("barea", np.array([a for *_, a in meta], dtype="<f4"))

    def lines(name, items):
        cnt, flat = [], []
        for it in items:
            cnt.append(len(it))
            flat.extend(it)
        put(name + "_n", np.array(cnt, dtype="<u4"))
        put(name, np.round(np.array(flat) * 10).astype("<i4").ravel())

    lines("water", water)
    lines("park", parks)
    lines("road", [r for r, _ in roads])
    put("road_k", np.array([k for _, k in roads], dtype="<u1"))
    lines("rail", rails)

    # ── 교통: ITS 구간 속도(30분 표본) → 구간별 평일·주말 시간대(0~23시) 중앙값
    import glob, statistics, datetime as dtm
    net = json.load(open(os.path.join(FIRE, "network.json"), encoding="utf-8"))["links"]
    net = [l for l in net if all(W0 <= q[0] <= E0 and S0 <= q[1] <= N0 for q in l["pts"])]
    ids = {l["id"] for l in net}
    obs = {}                                   # id → [[평일 0~23시 값들], [주말 …]]
    hrs = [[0] * 24, [0] * 24]
    days = set()
    for fn in sorted(glob.glob(os.path.join(FIRE, "raw", "its", "*.json"))):
        d = json.load(open(fn, encoding="utf-8"))
        t = dtm.datetime.strptime(d["created"][:12], "%Y%m%d%H%M")
        we = 1 if t.weekday() >= 5 else 0
        hrs[we][t.hour] += 1
        days.add(t.strftime("%Y-%m-%d"))
        for lid, v in d["speeds"].items():
            if lid in ids and v > 0:            # 0 은 '자료 없음'
                obs.setdefault(lid, [[[] for _ in range(24)], [[] for _ in range(24)]])[we][t.hour].append(v)

    def fill(arr):                             # 빈 시간은 앞뒤(원형) 값으로 잇는다
        known = [h for h in range(24) if arr[h] is not None]
        if not known:
            return [0] * 24
        out = []
        for h in range(24):
            if arr[h] is not None:
                out.append(arr[h]); continue
            pv = max((k for k in known if k < h), default=known[-1] - 24)
            nx = min((k for k in known if k > h), default=known[0] + 24)
            a1, a2 = arr[pv % 24], arr[nx % 24]
            out.append(a1 + (a2 - a1) * (h - pv) / (nx - pv))
        return out

    tl, tn, tsp, tmeta, tnames = [], [], [], [], []
    nm_ix = {}
    for l in net:
        if l["id"] not in obs:
            continue
        o = obs[l["id"]]
        wd = fill([statistics.median(v) if v else None for v in o[0]])
        we = fill([statistics.median(v) if v else None for v in o[1]])
        if not any(o[1][h] for h in range(24)):
            we = wd
        tl.append([xy(*q) for q in l["pts"]])
        tsp.append([min(255, round(v)) for v in wd + we])
        nm = l.get("name") or ""
        if nm not in nm_ix:
            nm_ix[nm] = len(tnames); tnames.append(nm)
        tmeta.append((int(l["rank"]) - 100, min(255, int(l.get("max") or 0)), nm_ix[nm]))
    lines("traf", tl)
    put("traf_sp", np.array(tsp, dtype="<u1").ravel())
    put("traf_m", np.array(tmeta, dtype="<u2").ravel())
    traffic = {"names": tnames, "hours": hrs, "from": min(days), "to": max(days), "snaps": sum(hrs[0]) + sum(hrs[1])}
    print("교통 구간", len(tl), "표본", traffic["snaps"], traffic["from"], "~", traffic["to"])

    blob = b"".join(blobs)
    open(os.path.join(OUT, "twin.bin"), "wb").write(blob)
    meta_j = {"center": [LON0, LAT0], "k": [KX, KY], "dem": dem, "river": round(float(river), 2), "slope": round(float(slope), 7),
              "n": nb, "offs": offs, "traffic": traffic, "names": names, "labels": labels,
              "zones": ["1생활권", "2생활권", "3생활권", "4생활권", "5생활권", "6생활권", "S생활권", "-"]}
    json.dump(meta_j, open(os.path.join(OUT, "twin.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("twin.bin", round(len(blob) / 1e6, 2), "MB, twin.json", round(os.path.getsize(os.path.join(OUT, "twin.json")) / 1e3), "KB")


if __name__ == "__main__":
    main()
