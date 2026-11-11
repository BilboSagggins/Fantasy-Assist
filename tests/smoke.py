"""RosterIQ smoke tests: load the real app in a headless browser with Sleeper and
ESPN answered by a mock league, click through the main features, and fail on any
JavaScript error or missing result.

Run:  python3 tests/smoke.py          (needs: pip install playwright && playwright install chromium)
"""
import datetime as dt
import functools
import http.server
import json
import pathlib
import re
import sys
import threading
import traceback

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
D = lambda n: (TODAY + dt.timedelta(days=n)).isoformat()
SEASON = 2026
WEEK = 3

# ---------------- mock Sleeper NBA league ----------------
NBA_SCORING = {"pts": 1, "reb": 1.2, "ast": 1.5, "stl": 3, "blk": 3, "to": -1, "dd": 1.5}

def pts(st, sc=NBA_SCORING):
    v = sum(st.get(k, 0) * w for k, w in sc.items() if k != "dd")
    tens = sum(1 for k in ("pts", "reb", "ast", "stl", "blk") if st.get(k, 0) >= 10)
    if "dd" in sc and tens >= 2:
        v += sc["dd"]
    return round(v, 2)

def P(pid, name, pos, team, inj=None, espn=None):
    first, last = name.split(" ", 1)
    return {"player_id": pid, "full_name": name, "first_name": first, "last_name": last, "position": pos[0], "fantasy_positions": pos,
            "team": team, "active": True, "status": "Active", "injury_status": inj, "espn_id": espn}

NBA_PLAYERS = {p["player_id"]: p for p in [
    P("maxey", "Tyrese Maxey", ["PG"], "PHI"), P("ant", "Anthony Edwards", ["SG"], "MIN"), P("murray", "Jamal Murray", ["PG"], "DEN"),
    P("lebron", "LeBron James", ["SF"], "LAL"), P("sabonis", "Domantas Sabonis", ["PF", "C"], "SAC"), P("bridges", "Miles Bridges", ["SF", "PF"], "CHA"),
    P("ad", "Anthony Davis", ["C", "PF"], "DAL", "Out"), P("curry", "Stephen Curry", ["PG"], "GSW"), P("brunson", "Jalen Brunson", ["PG"], "NYK"),
    P("giannis", "Giannis Antetokounmpo", ["PF"], "MIL"), P("brown", "Jaylen Brown", ["SG", "SF"], "BOS"), P("zion", "Zion Williamson", ["PF"], "NOP"),
    # opponent
    P("jokic", "Nikola Jokic", ["C"], "DEN"), P("luka", "Luka Doncic", ["PG"], "LAL"), P("tatum", "Jayson Tatum", ["SF"], "BOS"),
    P("gobert", "Rudy Gobert", ["C"], "MIN"), P("fox", "De'Aaron Fox", ["PG"], "SAC"), P("kyrie", "Kyrie Irving", ["PG"], "DAL"),
    P("towns", "Karl-Anthony Towns", ["C"], "NYK"), P("dame", "Damian Lillard", ["PG"], "MIL"), P("lamelo", "LaMelo Ball", ["PG"], "CHA"),
    P("ingram", "Brandon Ingram", ["SF"], "NOP"),
    # free agents
    P("naz", "Naz Reid", ["PF", "C"], "MIN"), P("pritchard", "Payton Pritchard", ["PG"], "BOS"), P("kessler", "Walker Kessler", ["C"], "SAC"),
]}
SCHED = [
    (D(-2), "PHI", "DEN", "complete"),
    (D(-1), "LAL", "DEN", "complete"), (D(-1), "MIN", "BOS", "complete"), (D(-1), "SAC", "GSW", "complete"),
    (D(-1), "NYK", "DAL", "complete"), (D(-1), "CHA", "MIL", "complete"), (D(-1), "PHI", "NOP", "complete"),
    (D(0), "BOS", "LAL", "pre_game"), (D(0), "GSW", "MIN", "pre_game"),
    (D(1), "DAL", "DEN", "pre_game"), (D(1), "MIL", "SAC", "pre_game"), (D(1), "CHA", "NYK", "pre_game"), (D(1), "NOP", "PHI", "pre_game"),
    (D(2), "DEN", "BOS", "pre_game"),
]
NBA_SCHED = [{"date": d, "week": WEEK, "home": h, "away": a, "status": st} for d, h, a, st in SCHED]

def line(p_, r, a, s=1, b=0, t=2, mins=34):
    return {"gp": 1, "pts": p_, "reb": r, "ast": a, "stl": s, "blk": b, "to": t, "sp": mins * 60}

# Jamal Murray: 34.0 two days ago (locked), 40.5 last night. Sleeper counts 34.0.
GAME_LINES = {("murray", D(-2)): line(18, 5, 6, 1, 0, 2), ("murray", D(-1)): line(22, 5, 7, 1, 0, 1)}
def game_line(pid, date):
    if (pid, date) in GAME_LINES:
        return GAME_LINES[(pid, date)]
    seed = sum(map(ord, pid + date))
    return line(12 + seed % 18, 3 + seed % 8, 2 + seed % 7, 1, seed % 2, 2, 26 + seed % 12)

def team_games(team):
    return [g for g in NBA_SCHED if team in (g["home"], g["away"])]

def nba_stats(pid):
    p = NBA_PLAYERS.get(pid)
    if not p or p["injury_status"] == "Out":
        return {}
    out = [{"date": g["date"], "week": WEEK, "opponent": g["away"] if g["home"] == p["team"] else g["home"], "stats": game_line(pid, g["date"])}
           for g in team_games(p["team"]) if g["status"] == "complete"]
    # a few earlier games for recent-form numbers
    for i in range(3):
        d = D(-9 - i * 2)
        out.append({"date": d, "week": WEEK - 1, "opponent": "OKC", "stats": game_line(pid, d)})
    return {str(WEEK): [g for g in out if g["week"] == WEEK], str(WEEK - 1): [g for g in out if g["week"] == WEEK - 1]}

def nba_proj():
    out = []
    for pid, p in NBA_PLAYERS.items():
        for g in team_games(p["team"]):
            if g["status"] == "complete":
                continue
            out.append({"player_id": pid, "date": g["date"], "player": {"injury_status": p["injury_status"]}, "stats": line(20, 6, 5)})
    return out

def counted(pid):
    p = NBA_PLAYERS[pid]
    if pid == "murray":
        return 34.0
    done = [g for g in team_games(p["team"]) if g["status"] == "complete"]
    return pts(game_line(pid, done[-1]["date"])) if done and p["injury_status"] != "Out" else 0.0

MY_STARTERS = ["maxey", "ant", "murray", "lebron", "sabonis", "bridges", "ad", "curry", "brunson", "giannis"]
MY_BENCH = ["brown", "zion"]
OPP_STARTERS = ["luka", "fox", "lamelo", "tatum", "ingram", "kyrie", "jokic", "gobert", "towns", "dame"]
POSITIONS = ["PG", "SG", "G", "SF", "PF", "F", "C", "UTIL", "UTIL", "UTIL", "BN", "BN", "BN", "BN", "BN"]
LEAGUE = {"league_id": "L1", "name": "Mock Lock League", "status": "in_season", "sport": "nba", "season": str(SEASON), "avatar": None,
          "roster_positions": POSITIONS, "scoring_settings": NBA_SCORING,
          "settings": {"waiver_type": 2, "waiver_budget": 100, "reserve_slots": 1, "reserve_allow_out": 1}}
ROSTERS = [
    {"roster_id": 7, "owner_id": "u1", "players": MY_STARTERS + MY_BENCH, "starters": MY_STARTERS, "reserve": [], "settings": {"wins": 2, "losses": 1}},
    {"roster_id": 3, "owner_id": "u2", "players": OPP_STARTERS, "starters": OPP_STARTERS, "reserve": [], "settings": {"wins": 1, "losses": 2}},
]
USERS = [{"user_id": "u1", "display_name": "BilboSagggins", "metadata": {"team_name": "Horses"}},
         {"user_id": "u2", "display_name": "Rival", "metadata": {"team_name": "Rival Squad"}}]
def matchups():
    def entry(r, starters):
        pp = {pid: counted(pid) for pid in r["players"]}
        return {"roster_id": r["roster_id"], "matchup_id": 2, "starters": starters, "players": r["players"], "players_points": pp,
                "starters_points": [pp[s] for s in starters], "points": round(sum(pp[s] for s in starters), 2)}
    return [entry(ROSTERS[0], MY_STARTERS), entry(ROSTERS[1], OPP_STARTERS)]

# ---------------- mock ESPN / Sleeper NFL bits (for the ESPN tabs) ----------------
def NP(pid, name, pos, team, inj=None, espn=None, depth=1):
    d = P(pid, name, [pos], team, inj, espn)
    d.update({"depth_chart_position": pos, "depth_chart_order": depth})
    return d
NFL_PLAYERS = {p["player_id"]: p for p in [
    NP("caleb", "Caleb Williams", "QB", "CHI"), NP("bagent", "Tyson Bagent", "QB", "CHI", depth=2),
    NP("odunze", "Rome Odunze", "WR", "CHI", espn=4685), NP("moore", "DJ Moore", "WR", "CHI", depth=2),
    NP("swift", "Dandre Swift", "RB", "CHI", "Out"), NP("mona", "Kyle Monangai", "RB", "CHI", depth=2),
    NP("bijan", "Bijan Robinson", "RB", "ATL"), NP("kmet", "Cole Kmet", "TE", "CHI"), NP("santos", "Cairo Santos", "K", "CHI"),
    NP("smith", "Jaxon Smith", "WR", "SEA"), NP("cb1", "Terrion Arnold", "CB", "DET", "Out"),
]}
NFL_SCHED = [{"week": 7, "home": "CHI", "away": "DET", "date": D(4), "status": "pre_game"}, {"week": 7, "home": "ATL", "away": "SEA", "date": D(4), "status": "pre_game"}]
NFL_PROJ = [{"player_id": k, "stats": v} for k, v in {
    "caleb": {"pass_yd": 250, "pass_td": 2, "pass_int": 1}, "odunze": {"rec": 5, "rec_yd": 70, "rec_td": 0.4}, "moore": {"rec": 6, "rec_yd": 60, "rec_td": 0.3},
    "smith": {"rec": 7, "rec_yd": 85, "rec_td": 0.6}, "mona": {"rush_yd": 60, "rush_td": 0.4}, "bijan": {"rush_yd": 90, "rush_td": 0.8, "rec": 4, "rec_yd": 30},
    "kmet": {"rec": 4, "rec_yd": 40, "rec_td": 0.3}, "santos": {"fgm_30_39": 1, "fgm_40_49": 1, "xpm": 2}, "CHI": {"sack": 2.5, "int": 1}}.items()]

FAIL = set()
SHOTS = pathlib.Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None  # endpoints to fail with HTTP 500, per test

def sleeper(url):
    u = url.split("?")[0]
    m = re.search(r"/stats/(nba|nfl)/player/([^/?]+)", u)
    if m:
        return nba_stats(m.group(2)) if m.group(1) == "nba" else {}
    table = [
        (r"/v1/user/bilbosagggins$", lambda: {"user_id": "u1", "display_name": "BilboSagggins"}),
        (r"/v1/user/u1/leagues/nba/", lambda: [LEAGUE]),
        (r"/v1/user/u1/leagues/nfl/", lambda: []),
        (r"/v1/state/nba", lambda: {"season": str(SEASON), "week": WEEK}),
        (r"/v1/state/nfl", lambda: {"season": str(SEASON), "week": 7}),
        (r"/v1/league/L1$", lambda: LEAGUE),
        (r"/v1/league/L1/rosters", lambda: ROSTERS),
        (r"/v1/league/L1/users", lambda: USERS),
        (r"/v1/league/L1/matchups/", matchups),
        (r"/v1/league/L1/transactions/", lambda: []),
        (r"/v1/players/nba$", lambda: NBA_PLAYERS),
        (r"/v1/players/nfl$", lambda: NFL_PLAYERS),
        (r"/trending/", lambda: []),
        (r"/schedule/nba/", lambda: NBA_SCHED),
        (r"/schedule/nfl/", lambda: NFL_SCHED),
        (r"/projections/nba/", nba_proj),
        (r"/projections/nfl/", lambda: NFL_PROJ),
    ]
    for pat, fn in table:
        if re.search(pat, u, re.I):
            return fn()
    return {}

def route(r):
    url = r.request.url
    if url.startswith("http://127.0.0.1"):
        return r.continue_()
    for f in FAIL:
        if f in url:
            return r.fulfill(status=500, body="{}", headers={"Access-Control-Allow-Origin": "*"})
    if "sleeper" in url:
        return r.fulfill(status=200, body=json.dumps(sleeper(url)), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
    if "fantasy.espn.com" in url:  # every ESPN fantasy league is private in these tests
        return r.fulfill(status=401, body="{}", headers={"Access-Control-Allow-Origin": "*"})
    if "site.api.espn.com" in url and "/news" in url:
        return r.fulfill(status=200, body=json.dumps({"articles": [{"headline": "Rome Odunze cleared, returns to full practice", "published": dt.datetime.now(dt.timezone.utc).isoformat(),
            "categories": [{"type": "athlete", "athleteId": 4685}], "links": {"web": {"href": "https://espn.com/x"}}}]}), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
    if url.endswith(".css") or "fonts.g" in url:
        return r.fulfill(status=200, body=FA_CSS if "font-awesome" in url else "", content_type="text/css")
    if url.endswith(".js") or "jsdelivr" in url:
        return r.fulfill(status=200, body="", content_type="application/javascript")
    if re.search(r"\.(png|jpg|svg|woff2?)", url):
        return r.fulfill(status=404, body="")
    return r.fulfill(status=200, body="{}", headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})

FA_CSS = ""  # icons are left out of the checks

# ---------------- test runner ----------------
def serve():
    h = functools.partial(type('Quiet', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}), directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/index.html"

class Check:
    def __init__(self): self.fails, self.passes = [], 0
    def ok(self, cond, what):
        if cond: self.passes += 1
        else: self.fails.append(what); print("  FAIL:", what)

def new_page(b, url, errs):
    ctx = b.new_context(viewport={"width": 390, "height": 900}, service_workers="block")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", route)
    pg.goto(url)
    pg.wait_for_timeout(400)
    return ctx, pg

def wait_text(pg, sel, text, ms=8000):
    try:  # textContent: also finds text inside closed cards
        pg.wait_for_function("([s, t]) => (document.querySelector(s)?.textContent || '').includes(t)", arg=[sel, text], timeout=ms)
        return True
    except Exception:
        return False

def test_sleeper_nba(b, url, c):
    errs = []
    ctx, pg = new_page(b, url, errs)
    pg.click("#landing-sleeper")
    pg.fill("#league-username", "BilboSagggins")
    pg.evaluate("connectSleeper()")
    c.ok(wait_text(pg, "#league-msg", "updated", 20000), "Sleeper league loads (league message says updated)")
    ok10 = wait_text(pg, "#lineup-fix", "of 10")
    if not ok10: print("    lineup-fix:", pg.inner_text("#lineup-fix")[:400], "| format:", pg.evaluate("league.format"))
    c.ok(ok10, "Lineup fixes show all 10 lock chips")
    murray = pg.evaluate("(() => { const p = league.players.find(x => x.pid === 'murray'); return p && { locked: isLocked(p), pts: p.lockedPts, date: p.lockedGame && p.lockedGame.date }; })()")
    c.ok(murray and murray["locked"] and abs(murray["pts"] - 34.0) < 0.01 and murray["date"] == D(-2), f"Jamal Murray detected locked at 34.0 on his earlier game (got {murray})")
    plan = pg.evaluate("document.getElementById('league-plan').textContent")
    c.ok("Start these this week" in plan and "34.0" in plan, "Lock plan shows Murray's locked 34.0")
    pg.click("#matchup-wrap summary")
    c.ok(wait_text(pg, "#matchup-body", "to win"), "Matchup card shows a win chance")
    c.ok("Rival Squad" in pg.inner_text("#matchup-wrap"), "Matchup names the opponent")
    c.ok(pg.locator("#matchup-body .grid-cols-\\[2\\.5rem_1fr_1fr\\]").count() >= 10, "Matchup lists every slot")
    pg.click("#news-wrap summary")
    c.ok(wait_text(pg, "#news-wrap", "steady", 15000), "Team news loads")
    c.ok("OUT" in pg.inner_text("#news-body").upper(), "Team news flags Anthony Davis as out on his card")
    pg.click("#lock-report-wrap summary")
    c.ok(wait_text(pg, "#lock-report-body", "Your locks"), "Lock report renders")
    pg.click("#fa-wrap summary")
    c.ok(wait_text(pg, "#fa-body", "Top 50 free agents", 15000), "Free agents load")
    jump = pg.inner_text("#jump-sleeper")
    c.ok(all(x in jump for x in ("Matchup", "News", "Lock plan")), f"Jump bar lists the cards (got: {jump!r})")
    if SHOTS:
        pg.evaluate("document.querySelectorAll('#league-panel details[data-card]').forEach(d => d.open = false); document.getElementById('matchup-wrap').open = true")
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(SHOTS / "sleeper.png"), full_page=True)
    c.ok(not errs, f"No JavaScript errors in the Sleeper flow: {errs[:3]}")
    # second visit: the player list comes from the phone, not a fresh multi-MB download
    hits = []
    pg.on("request", lambda r: hits.append(r.url) if "/v1/players/nba" in r.url else None)
    pg.reload()
    pg.wait_for_timeout(400)
    pg.click("#landing-sleeper")
    c.ok(wait_text(pg, "#league-msg", "updated", 20000), "League loads again on a second visit")
    c.ok(not hits, f"Second visit reuses the saved player list ({len(hits)} downloads)")
    ctx.close()

def test_issue_banner(b, url, c):
    errs = []
    FAIL.add("/projections/nba/")
    try:
        ctx, pg = new_page(b, url, errs)
        pg.click("#landing-sleeper")
        pg.fill("#league-username", "BilboSagggins")
        pg.evaluate("connectSleeper()")
        c.ok(wait_text(pg, "#issues-sleeper", "Sleeper's projections", 20000), "A failed projections request shows the warning banner")
        c.ok(not errs, f"No JavaScript errors when a source fails: {errs[:3]}")
        ctx.close()
    finally:
        FAIL.clear()

def test_espn_manual(b, url, c):
    errs = []
    ctx, pg = new_page(b, url, errs)
    pg.click("#landing-espn")
    pg.fill("#espn-league-id", "123456")
    pg.evaluate("connectEspn()")
    c.ok(wait_text(pg, "#espn-msg", "private"), "Private ESPN league is recognized")
    pg.evaluate("espnStartManual('nfl')")
    pg.wait_for_timeout(1500)
    pg.evaluate("""mwAdd('QB','caleb'); mwAdd('RB','mona'); mwAdd('RB','swift'); mwAdd('WR','odunze'); mwAdd('WR','smith'); mwAdd('TE','kmet');
                   mwAdd('FLEX','moore'); mwAdd('D/ST','DEF_CHI'); mwAdd('K','santos'); mwAdd('BN','bijan'); mwAdd('BN','bagent'); mwGo(mwSteps().length-1)""")
    pg.click("text=Save my team")
    c.ok(wait_text(pg, "#espn-fix", "Make", 15000), "Hand-entered team gets lineup fixes")
    c.ok("Bijan Robinson" in pg.inner_text("#espn-fix"), "Fix suggests starting Bijan over the injured Swift")
    c.ok("Caleb Williams" in pg.inner_text("#espn-lineup-body"), "My lineup card lists the team")
    pg.click("#espn-news-wrap summary")
    c.ok(wait_text(pg, "#espn-news-wrap", "steady", 15000), "Team news loads on the ESPN tab")
    pg.click("#espn-lineup-wrap summary")
    pg.click("#espn-lineup-body button:has-text('Edit my lineup')")
    pg.evaluate("mwStartMove('BN','bijan')")
    c.ok(pg.locator("text=swap with Dandre Swift").count() == 1, "Move offers a swap with Swift")
    c.ok(not errs, f"No JavaScript errors in the ESPN flow: {errs[:3]}")
    ctx.close()

def test_basics(b, url, c):
    errs = []
    ctx, pg = new_page(b, url, errs)
    c.ok(pg.locator("#landing").is_visible(), "Start screen shows")
    pg.click("#landing-nba")
    pg.wait_for_timeout(1500)
    pg.evaluate("cycleTextSize()")
    z = pg.evaluate("document.documentElement.style.zoom")
    c.ok(z == "1.15", f"Text size button enlarges the app (zoom {z!r})")
    pg.evaluate("cycleTextSize(); cycleTextSize()")
    c.ok(pg.evaluate("document.documentElement.style.zoom") == "", "Text size cycles back to normal")
    c.ok(pg.locator("text=v3.5").count() == 0, "No stale version badge")
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    c.ok(len(css) > 20000 and ".bg-emerald-500" in css, "styles.css is built")
    c.ok(not errs, f"No JavaScript errors on start: {errs[:3]}")
    ctx.close()

def main():
    url = serve()
    c = Check()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for t in (test_basics, test_sleeper_nba, test_issue_banner, test_espn_manual):
            print(f"- {t.__name__}")
            try:
                t(b, url, c)
            except Exception as e:
                traceback.print_exc()
                c.ok(False, f"{t.__name__} crashed: {e}")
        b.close()
    print(f"\n{c.passes} passed, {len(c.fails)} failed")
    sys.exit(1 if c.fails else 0)

if __name__ == "__main__":
    main()
