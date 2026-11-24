#!/usr/bin/env python3
"""Copia gli orari settimanali dalle schede Google Maps in orari-google.json.

Lo lancia ogni notte GitHub (.github/workflows/orari-google.yml).
Serve la chiave Google Places nella variabile GOOGLE_PLACES_KEY
(su GitHub: Settings → Secrets and variables → Actions → GOOGLE_PLACES_KEY).
Senza chiave non fa niente e il sito usa gli orari scritti in index.html.

Gli orari speciali delle feste restano quelli scritti a mano in CONFIG.speciali.
"""
import json, os, sys, urllib.request, urllib.error, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "orari-google.json"
KEY = os.environ.get("GOOGLE_PLACES_KEY", "").strip()

# id del negozio nel sito → Place ID Google (vuoto = lo cerca per nome)
SEDI = {
    "azienda":       ("ChIJ9RjiVftc0xIRimRibxbNcT0", ""),
    "nervi":         ("ChIJCW5t0dhc0xIR3JfBtcZovew", ""),
    "albaro":        ("ChIJOxdqLCVD0xIRxNYUnxHBtV4", ""),
    "recco-chiosco": ("", "Floricoltura Lagomarsino Chiosco Recco, Via XX Settembre, 16036 Recco"),
    "recco":         ("ChIJQ0Pswqxf0xIRAE82QCYan38", ""),
}

def chiama(url, campi, corpo=None):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo else None,
        headers={"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": campi, "Content-Type": "application/json"},
        method="POST" if corpo else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def trova_id(query):
    d = chiama("https://places.googleapis.com/v1/places:searchText", "places.id", {"textQuery": query, "languageCode": "it"})
    return (d.get("places") or [{}])[0].get("id", "")

def hhmm(p):
    return f'{p.get("hour",0):02d}:{p.get("minute",0):02d}'

def settimana(oh):
    """periods di Google → [domenica..sabato], ogni giorno lista di "HH:MM-HH:MM"."""
    giorni = [[] for _ in range(7)]
    for per in oh.get("periods", []):
        a, c = per.get("open"), per.get("close")
        if not a:
            continue
        if not c:  # aperto 24 ore
            giorni[a["day"]].append("00:00-24:00"); continue
        fine = hhmm(c)
        if c.get("day") != a.get("day") and fine == "00:00":
            fine = "24:00"
        giorni[a["day"]].append(f"{hhmm(a)}-{fine}")
    return [sorted(g) for g in giorni]

def main():
    if not KEY:
        print("Nessuna chiave GOOGLE_PLACES_KEY: niente da fare."); return 0
    negozi, errori = {}, []
    for sid, (pid, query) in SEDI.items():
        try:
            pid = pid or trova_id(query)
            if not pid:
                errori.append(f"{sid}: scheda non trovata"); continue
            d = chiama(f"https://places.googleapis.com/v1/places/{pid}?languageCode=it", "regularOpeningHours")
            oh = d.get("regularOpeningHours")
            if not oh or not oh.get("periods"):
                print(f"{sid}: nessun orario su Google, resta quello del sito"); continue
            negozi[sid] = settimana(oh)
            print(f"{sid}: {negozi[sid]}")
        except urllib.error.HTTPError as e:
            errori.append(f"{sid}: HTTP {e.code} {e.read()[:200]!r}")
        except Exception as e:
            errori.append(f"{sid}: {e}")
    for e in errori: print("ERRORE", e, file=sys.stderr)
    if not negozi:
        return 1 if errori else 0
    vecchio = json.loads(OUT.read_text()) if OUT.exists() else {}
    if vecchio.get("negozi") == negozi:
        print("Orari invariati."); return 0
    OUT.write_text(json.dumps({"aggiornato": datetime.date.today().isoformat(), "negozi": negozi}, ensure_ascii=False, indent=1) + "\n")
    print("orari-google.json aggiornato."); return 0

if __name__ == "__main__":
    sys.exit(main())
