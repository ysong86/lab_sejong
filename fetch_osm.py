# OSM 물(금강·호수)·주요도로·랜드마크를 Overpass 로 한 번 받아 data/raw/osm.json 에 굳힌다
import json, os, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
BB = "36.445,127.205,36.560,127.365"
Q = f"""[out:json][timeout:120];
(
 way["natural"="water"]({BB}); relation["natural"="water"]({BB});
 way["waterway"="riverbank"]({BB});
 way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street)$"]({BB});
 way["railway"="rail"]({BB});
 way["bridge"="yes"]["highway"~"^(motorway|trunk|primary|secondary|pedestrian|footway)$"]({BB});
 nwr["name"]["tourism"~"attraction|museum|viewpoint"]({BB});
 nwr["name"]["amenity"~"library|townhall"]({BB});
 nwr["name"]["leisure"="park"]({BB});
 nwr["name"]["natural"="peak"]({BB});
 nwr["name"]["office"="government"]({BB});
);
out geom;"""
u = "https://overpass.kumi.systems/api/interpreter"
req = urllib.request.Request(u, data=urllib.parse.urlencode({"data": Q}).encode(), headers={"User-Agent": "sejong-twin/1.0"})
with urllib.request.urlopen(req, timeout=180) as r:
    d = json.load(r)
json.dump(d, open(os.path.join(HERE, "data", "raw", "osm.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(len(d["elements"]))
