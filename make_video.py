# -*- coding: utf-8 -*-
"""디지털트윈 실험실 소개 영상(50초, MP4)

  C:\\Python313\\python.exe make_video.py [--url http://127.0.0.1:8790/]
    출력: docs/디지털트윈_소개.mp4 + site/preview.mp4

3D 는 실시간 녹화하면 프레임이 끊기므로, 페이지의 시계(performance.now·requestAnimationFrame)를 가짜로 바꿔
한 프레임씩 진행 → 화면 캡처 → ffmpeg 로 30fps 이어 붙인다. 카메라 비행·수위 상승·비는 모두 이 시계를 따른다.
가짜 포인터·클릭 물결·자막은 상가공실 make_video.py 와 같은 방식(디자인만 대문 톤).
"""
import math
import os
import shutil
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://127.0.0.1:8790/"
TMP = os.path.join(HERE, "data", "video_tmp")
OUT = os.path.join(HERE, "docs", "디지털트윈_소개.mp4")
SITE = os.path.join(HERE, "site", "preview.mp4")
W, H, FPS = 1440, 810, 30

CLOCK = r"""
(() => {
  let vt = 0, q = [];
  performance.now = () => vt;
  window.requestAnimationFrame = cb => { q.push(cb); return q.length; };
  window.__tick = dt => { vt += dt; const c = q; q = []; for (const f of c) f(vt); };
})();
"""

OVERLAY = r"""
(() => {
  const css = document.createElement('style');
  css.textContent = `
  #vcur{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
        transform:translate(-3px,-2px);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .vring{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;border:3px solid #152484;
         z-index:2147483646;pointer-events:none;animation:vr .6s ease-out forwards}
  :root[data-night="1"] .vring{border-color:#8EA0F2}
  @keyframes vr{from{transform:scale(.3);opacity:.9}to{transform:scale(1.4);opacity:0}}
  #vcap{position:fixed;left:calc((100vw - 404px) / 2);bottom:104px;transform:translateX(-50%);z-index:2147483645;pointer-events:none;
        background:#141414;color:#F3F2EE;padding:12px 22px 13px;opacity:0;transition:opacity .35s;white-space:nowrap;
        font-family:"IBM Plex Sans KR",sans-serif;text-align:center}
  #vcap .n{display:block;font:500 11px/1 "IBM Plex Mono","IBM Plex Sans KR",monospace;letter-spacing:.16em;color:#8EA0F2;margin-bottom:7px}
  #vcap b{display:block;font-weight:600;font-size:23px;letter-spacing:-.01em;line-height:1.25}
  #vcap small{display:block;font-size:14.5px;opacity:.78;margin-top:4px}`;
  document.head.appendChild(css);
  const c = document.createElement('div'); c.id = 'vcur';
  c.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l15 9.5-6.6 1.6 3.9 7.4-3.1 1.6-3.9-7.5L4 19.5z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  document.body.appendChild(c);
  const cap = document.createElement('div'); cap.id = 'vcap'; document.body.appendChild(cap);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', e => {
    const r = document.createElement('div'); r.className = 'vring';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.body.appendChild(r); setTimeout(() => r.remove(), 700);
  }, true);
  window.__cap = (n, t, s) => { cap.innerHTML = t ? `<span class="n">${n}</span><b>${t}</b>${s ? '<small>' + s + '</small>' : ''}` : ''; cap.style.opacity = t ? 1 : 0; };
})();
"""


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        ctx.route("**/hits.sh/**", lambda r: r.abort())      # 녹화가 조회수를 올리지 않게
        ctx.route("**/nav.js", lambda r: r.abort())          # 대문 탭 줄 없이 깔끔하게
        ctx.add_init_script(CLOCK)
        pg = ctx.new_page()
        pg.goto(URL, wait_until="networkidle", timeout=90000)
        pg.wait_for_function("window.__twin && document.querySelector('#load.done')", timeout=90000)
        pg.wait_for_timeout(1200)                            # 불러오기 화면이 다 사라지게
        pg.evaluate(OVERLAY)
        pg.evaluate("document.fonts.ready")

        st = {"f": 0, "x": W * 0.42, "y": H * 0.5}
        pg.mouse.move(st["x"], st["y"])

        def js(code, arg=None):
            return pg.evaluate(code, arg)

        def frame(n=1):
            for _ in range(n):
                js("__tick(1000/30)")
                pg.wait_for_timeout(8)                       # CSS 전환·DOM 갱신이 그려질 틈
                pg.screenshot(path=os.path.join(TMP, "f%05d.jpg" % st["f"]), type="jpeg", quality=92)
                st["f"] += 1

        def move(x, y, n=24, drag=False):
            x0, y0 = st["x"], st["y"]
            for i in range(1, n + 1):
                k = i / n
                e = k * k * (3 - 2 * k)
                pg.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
                frame()
            st["x"], st["y"] = x, y

        def click(hold=4):
            pg.mouse.down()
            frame(2)
            pg.mouse.up()
            frame(hold)

        def box(sel, dx=.5, dy=.5):
            r = pg.locator(sel).first.bounding_box()
            return r["x"] + r["width"] * dx, r["y"] + r["height"] * dy

        def cap(n, t="", s=""):
            js("([n,t,s]) => __cap(n,t,s)", [n, t, s])

        def scrub_x(minute):
            r = pg.locator("#scrub").bounding_box()
            return r["x"] + r["width"] * minute / 1439, r["y"] + r["height"] / 2

        def fly(at, d, az, po, ms):
            js("([a,d,az,po,ms]) => { const T = __twin; T.flyTo(T.V(a[0], a[1], a[2]), d, az, po, ms); }", [at, d, az, po, ms])

        def screen(p3):  # 세계 좌표(동,북,위) → 화면 좌표
            return js("""([x,y,z]) => { const T = __twin, v = T.V(x,y,z).project(T.camera);
                       return [(v.x + 1) / 2 * innerWidth, (1 - v.y) / 2 * innerHeight]; }""", p3)

        # ── 0~5초: 도시로 날아 들어간다(페이지가 처음에 하는 비행)
        cap("SEJONG DIGITAL TWIN · LAB", "세종 디지털트윈 실험실", "행복도시 9,284동과 실제 지형을 한 모형 위에")
        frame(150)

        # ── 5~13초: 시각을 끌면 실제 해가 그림자를 옮긴다
        gov = js("__twin.M.labels.find(l => l.n === '정부세종청사')")
        fly([gov["x"] + 300, gov["y"] - 200, gov["z"]], 1700, 335, 58, 2400)
        cap("01 · 해와 그림자", "시각을 움직이면 실제 해가 그림자를 옮깁니다", "동지(12월 22일) · 세종 위도·경도로 계산한 태양 위치")
        frame(30)
        x, y = scrub_x(9 * 60)
        move(x, y, 36)
        pg.mouse.down()
        frame(3)
        x2, _ = scrub_x(16 * 60 + 30)
        move(x2, y, 120)
        pg.mouse.up()
        frame(12)

        # ── 13~20초: 아파트 남쪽 벽을 누르면 하루 일조시간
        bb = js("""() => { const T = __twin; let best = -1;
                  for (let i = 0; i < T.M.n; i++) if (T.B.h[i] > 45 && T.B.h[i] < 80 && Math.hypot(T.B.cx[i] + 900, T.B.cy[i] + 500) < 900) { best = i; break; }
                  return {i: best, x: T.B.cx[best], y: T.B.cy[best], base: T.B.base[best], h: T.B.h[best]}; }""")
        fly([bb["x"], bb["y"], bb["base"] + 20], 430, 14, 63, 2000)
        cap("01 · 해와 그림자", "벽을 누르면 그 자리의 하루 일조시간", "5분마다 해 쪽으로 광선 · 동지 일조 기준(연속 2시간·합계 4시간) 판정")
        frame(64)
        wall = js("""([x,y,base]) => { const T = __twin, THREE = T.THREE;
                     const o = new THREE.Vector3(x, base + 9, -y + 160); T.ray.set(o, new THREE.Vector3(0,0,-1)); T.ray.far = 400;
                     const h = T.ray.intersectObject(T.bMesh, false)[0]; return h ? [h.point.x, -h.point.z, h.point.y] : null; }""",
                  [bb["x"], bb["y"], bb["base"]])
        sx, sy = screen(wall)
        move(sx, sy, 34)
        click(10)
        frame(40)
        move(*box("#sunOut .verdict"), 30)
        frame(42)

        # ── 20~28초: 금강 수면을 올리면
        move(*box('#modes [data-m="water"]'), 26)
        click(2)
        fly([-700, -1500, 20], 6800, 8, 55, 2400)
        cap("02 · 물이 차오르면", "금강 수면을 올리면 어디까지 잠길까", "하천 경사를 반영한 수면 · 잠기는 건물·연면적·생활권별 집계")
        frame(20)
        move(*box('#lvPre [data-v="9"]'), 30)
        click(4)
        frame(80)
        move(*box("#wZ"), 30)
        frame(48)

        # ── 28~34초: 산 위에서 보이는 곳
        move(*box('#modes [data-m="view"]'), 24)
        click(2)
        won = js("__twin.M.labels.find(l => l.n === '원수산')")
        fly([won["x"], won["y"], won["z"]], 5200, 188, 50, 2000)
        cap("03 · 여기서 보이는 것", "한 점을 누르면 보이는 곳만 밝게 남습니다", "원수산 정상, 사람 눈높이 1.6m")
        frame(62)
        sx, sy = screen([won["x"], won["y"], won["z"] + 1])
        move(sx, sy, 30)
        click(4)
        frame(60)

        # ── 34~44초: 출퇴근 정체(ITS 구간 속도)
        move(*box('#modes [data-m="traffic"]'), 24)
        click(2)
        js("() => { const T = __twin; T.S.date = T.S.date.slice(0,4) + '-10-28'; document.querySelector('#date').value = T.S.date; T.applySun(); }")
        fly([-1100, -350, 30], 5600, 16, 54, 2200)
        cap("04 · 출퇴근 정체", "실제로 잰 구간 속도로 도로를 칠합니다", "국가교통정보센터(ITS) 30분 간격 일주일 표본 · 평일 시간대별")
        frame(10)
        move(*box('#hrPre [data-v="480"]'), 26)
        click(4)
        frame(56)
        move(*box('#hrPre [data-v="1080"]'), 22)
        click(4)
        cap("04 · 출퇴근 정체", "퇴근 18시, 붉을수록 평소보다 느립니다", "정체·서행 구간 길이 · 시간대별 평균 속도 · 가장 막히는 길")
        frame(52)
        js("() => { const b = document.querySelector('#body'), li = document.querySelector('#trTop'); b.scrollTo({top: li.offsetTop - 120, behavior: 'smooth'}); }")
        frame(18)
        move(*box("#trTop li"), 22)
        click(2)
        frame(16)
        js("() => { const b = document.querySelector('#body'), el = document.querySelector('#trLink'); b.scrollTo({top: el.offsetTop - 40, behavior: 'smooth'}); }")
        cap("04 · 출퇴근 정체", "길을 누르면 그 구간의 하루", "평일·주말 24시간 속도와 제한속도")
        frame(40)

        # ── 44~50초: 해가 지면
        move(*box('#modes [data-m="sun"]'), 22)
        click(2)
        js("() => { const T = __twin; T.S.date = T.S.date.slice(0,4) + '-12-22'; document.querySelector('#date').value = T.S.date; document.querySelector('#body').scrollTo(0, 0); }")
        fly([-1700, -350, 30], 3700, 28, 63, 2600)
        cap("밤의 도시", "해가 지면 9,284동의 창에 불이 켜집니다", "시간 막대 하나로 낮에서 밤까지")
        x, y = scrub_x(16 * 60 + 30)
        move(x, y, 20)
        pg.mouse.down()
        frame(2)
        x2, _ = scrub_x(19 * 60 + 25)
        move(x2, y, 64)
        pg.mouse.up()
        move(W * 0.36, H * 0.42, 20)
        frame(24)
        cap("ysong86.github.io/#/lab", "직접 만져 보세요", "세종연구원 송양호 · 세종 이슈 대시보드")
        frame(54)
        b.close()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    subprocess.run([ff, "-y", "-framerate", str(FPS), "-i", os.path.join(TMP, "f%05d.jpg"),
                    "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "29",
                    "-movflags", "+faststart", "-an", OUT], check=True, capture_output=True)
    shutil.copyfile(OUT, SITE)
    print("영상", OUT, "%.1f초" % (st["f"] / FPS), "%.1fMB" % (os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
