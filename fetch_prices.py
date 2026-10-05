import asyncio, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from futbin_sdk import FutbinClient, PlayerSearchOptions

PAGES = int(os.getenv("PAGES", "5"))  # nombre de pages de la liste FUTBIN à lire
D = Path("data"); D.mkdir(exist_ok=True)
HIST = D / "history.json"

def g(o, *keys):
    for k in keys:
        v = o.get(k) if isinstance(o, dict) else getattr(o, k, None)
        if v not in (None, ""): return v

def card(o):
    i, p = g(o, "futbin_id", "id", "player_id"), g(o, "price_ps", "price")
    try: p = int(str(p).replace(",", "").replace(" ", ""))
    except Exception: return None
    if i is None or p <= 0: return None
    n = " ".join(str(x) for x in (g(o, "name", "player_name"), g(o, "rating"), g(o, "version", "card_version")) if x)
    return {"id": str(i), "n": n or str(i), "p": p}

async def main():
    found, pop, errs = {}, set(), []
    async def take(label, fn, popular=False):
        try:
            for o in await fn():
                c = card(o)
                if c:
                    found[c["id"]] = c
                    if popular: pop.add(c["id"])
        except Exception as e:
            errs.append(f"{label}: {e}")
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.futbin.com/"
}

async with FutbinClient(headers=headers) as c:
        await take("populaires", lambda: cl.get_popular_players(), True)
        await take("nouveaux", lambda: cl.get_latest_players())
        await take("totw", lambda: cl.get_totw())
        for p in range(1, PAGES + 1):
            await take(f"page {p}", lambda p=p: cl.search_players(options=PlayerSearchOptions(platform="PS", page=p)))
            await asyncio.sleep(2)
    print(f"{len(found)} cartes récupérées")
    for e in errs: print("ERREUR", e)
    if not found: sys.exit(1)  # on garde l'ancien fichier de prix
    now = int(time.time())
    H = json.loads(HIST.read_text()) if HIST.exists() else {}
    for c in found.values():
        H[c["id"]] = [x for x in H.get(c["id"], []) + [[now, c["p"]]] if now - x[0] < 50 * 3600]
    H = {k: v for k, v in H.items() if v and now - v[-1][0] < 50 * 3600}
    def chg(h, hrs):
        if h[0][0] > now - hrs * 1800: return 0  # pas encore assez d'historique
        old = min(h, key=lambda x: abs(x[0] - (now - hrs * 3600)))[1]
        return round((h[-1][1] - old) / old * 100, 1) if old > 0 else 0
    out = [{**c, "a": chg(H[c["id"]], 6), "b": chg(H[c["id"]], 24), "c": chg(H[c["id"]], 48),
            "o": 80 if c["id"] in pop else 40} for c in found.values()]
    HIST.write_text(json.dumps(H, separators=(",", ":")))
    (D / "prices.json").write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(),
        "errors": errs, "cards": out}, ensure_ascii=False, separators=(",", ":")))

asyncio.run(main())
