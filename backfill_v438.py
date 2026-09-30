import json,io,zipfile,csv,requests,time
from pathlib import Path
from datetime import datetime,timezone,timedelta

STATE=Path("state/live_v4386.json")
S="SOLUSDT"; IV="1h"; H=3600
BASE="https://data.binance.vision/data/futures/um"

def raw(c):
    return c.get("timestamp") or c.get("open_time") or c.get("t") or c.get("time")

def ts(c):
    v=raw(c)
    if v is None: raise ValueError("candle without timestamp")
    if isinstance(v,(int,float)): return int(v)//1000
    return int(datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp())

def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()

def fetch(url):
    for n in range(3):
        try:
            r=requests.get(url,timeout=60)
            print("HTTP",r.status_code,"SIZE",len(r.content),"URL",url)
            if r.status_code==200:
                z=zipfile.ZipFile(io.BytesIO(r.content))
                rows=[]
                for f in z.namelist():
                    with z.open(f) as x:
                        rows+=list(csv.reader(
                            io.TextIOWrapper(x,encoding="utf-8")))
                return rows
            if r.status_code==404:
                # BUGFIX : une archive journaliere non encore publiee est un
                # etat normal et attendu (Binance publie generalement le
                # fichier d'un jour J le lendemain, parfois plus tard), pas
                # une erreur -- on ne boucle pas dessus inutilement.
                return None
            print("WAIT HTTP",r.status_code)
        except Exception as e:
            print("ERROR",e)
        if n<2: time.sleep(20)
    return []

st=json.loads(STATE.read_text())

cs=[]
for c in st["candles"]:
    if not c.get("closed",True): continue
    try: ts(c)
    except: continue
    cs.append(c)

if not cs:
    print("ERROR | NO VALID CLOSED CANDLES")
    raise SystemExit(2)

last=max(ts(c) for c in cs)

# BUGFIX : "end" et "DAY" etaient des constantes figees a une date precise
# (2026-09-29), valables pour UN SEUL run manuel. Sur un cron recurrent,
# une fois "last" arrive a cette date, le job ne detecte plus jamais aucun
# vrai trou futur -- il faut calculer "end" a partir de l'heure reelle.
now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
end=int((now-timedelta(hours=1)).timestamp())  # derniere heure certainement close

want=list(range(last+H,end,H))

print("V438.1 | SAFE BACKFILL")
print("LAST",iso(last))
print("TARGET",iso(end))
print("MISSING",len(want))

if not want:
    print("NOTHING TO BACKFILL")
    raise SystemExit(0)

# BUGFIX : le fichier journalier a recuperer dependait d'une seule date en
# dur (DAY). On calcule maintenant, pour CHAQUE heure manquante, le fichier
# journalier correspondant, et on ne telecharge chaque jour qu'une seule
# fois meme si plusieurs heures manquantes en dependent (trou de plusieurs
# jours possible apres une longue coupure).
days_needed=sorted({
    datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")
    for t in want
})

got={}
any_missing_archive=False

for day in days_needed:
    url=f"{BASE}/daily/klines/{S}/{IV}/{S}-{IV}-{day}.zip"
    print("SOURCE",url)
    rows=fetch(url)

    if rows is None:
        # archive pas encore publiee pour ce jour : normal, on reessaiera
        # au prochain declenchement du cron -- pas une erreur.
        any_missing_archive=True
        print(f"NOT YET PUBLISHED | {day}")
        continue

    if not rows:
        print(f"FETCH ERROR | {day}")
        any_missing_archive=True
        continue

    for r in rows:
        try:
            if not r or not r[0].isdigit(): continue
            t=int(r[0])//1000
            if t in want: got[t]=r
        except Exception:
            pass

print("FOUND BARS",len(got),"/",len(want))

if not got:
    if any_missing_archive:
        print("WAIT | ARCHIVE(S) NOT YET AVAILABLE, WILL RETRY NEXT RUN")
        raise SystemExit(0)  # etat attendu, pas une erreur
    print("ERROR | NO BARS FOUND")
    raise SystemExit(2)

template=cs[-1]
allc={}

for c in cs:
    try: allc[ts(c)]=c
    except Exception: pass

for t,r in got.items():
    c=template.copy()

    # BUGFIX : le script recherchait une cle "timestamp"/"open_time" qui
    # n'existe pas dans le schema reel produit par live_continuity_v4386.py
    # (qui utilise "time"), et finissait par creer une cle "timestamp"
    # jamais lue ailleurs -- laissant "time" fige a l'ancienne bougie.
    # Toutes les bougies comblees se retrouvaient avec le meme "time",
    # s'ecrasant silencieusement les unes les autres au chargement suivant.
    c["time"]=iso(t)

    vals={
        "open":float(r[1]),
        "high":float(r[2]),
        "low":float(r[3]),
        "close":float(r[4]),
        "volume":float(r[5]),
        "trades":int(r[8]),
        "closed":True
    }
    c.update(vals)
    allc[t]=c

ordered=sorted(allc)
st["candles"]=[allc[t] for t in ordered]

closed=ordered

ok=len(closed)>=20 and all(
    b-a==H for a,b in zip(closed[-20:],closed[-19:])
)

st["last_closed"]=iso(closed[-1])
st["continuous20"]=ok

STATE.write_text(json.dumps(st,indent=2)+"\n")

print("BACKFILL", "PARTIAL" if len(got)<len(want) else "OK")
print("ADDED",len(got),"/",len(want))
print("LAST CLOSED",st["last_closed"])
print("CONTINUOUS20",st["continuous20"])

if len(got)<len(want):
    # des trous subsistent (archives pas encore publiees) : on le signale
    # sans faire echouer le job, puisque le prochain run reessaiera.
    print("REMAINING GAPS", len(want)-len(got))
