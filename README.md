# RosterIQ (Fantasy-Assist)
Start/sit and lineup help for fantasy football and basketball, built around your Sleeper and ESPN leagues.

**Open it:** https://bilbosagggins.github.io/Fantasy-Assist/

## What it does
- **NFL / NBA tabs:** compare up to three players side by side: projections, recent games, matchup, workload, and role changes (a teammate out or back, a new starting QB).
- **Sleeper tab** (enter your Sleeper username):
  - **Fix my lineup**, **My lineup scores**, **Matchup** (you vs. this week's opponent, win chance, the decisions that matter most)
  - **Team news**: injuries, playing time, role changes, roster moves, matchup notes and ESPN headlines, each marked good, bad or watch
  - Lock-In leagues: **Weekly lock plan** (lock or wait for every game) and **Lock report** (your locks vs. the advice vs. the best possible)
  - **Free Agents** (tap any player for the reasons and a side-by-side compare), **Transactions**, **Injuries & IR**
- **ESPN tab:** public leagues load from your league ID: lineup fixes, scores, team news, free agents, injuries. Private leagues: enter your scoring, lineup slots and players once (football or basketball) and get the same lineup advice.
- Text size button (**AA**) in the top bar; a jump bar at the top of each league tab.

Everything you enter (leagues, locks, hand-entered teams) is saved only in your phone's browser. Nothing is sent to the site owner.

## Install it as a phone app
- **Android (Chrome):** open the link, tap **Install** in the top bar (or ⋮ menu → *Install app*).
- **Samsung Internet:** open the link, tap ☰ menu → *Add page to* → *Home screen*.
- **iPhone (Safari):** open the link, tap Share → *Add to Home Screen*.

The app opens full screen from your home screen and loads the newest version when you're online.

## Daily lock reminder (10 AM Central)
1. In the app: Sleeper tab → **Daily lock reminder** → **Turn on reminders**, then **Copy code**.
2. On GitHub: Settings → Secrets and variables → Actions → **New repository secret**, name it `PUSH_CONFIG`, paste the code.
3. The **Lock reminder** workflow sends the notification every day at 10 AM Central (Actions → Lock reminder → Run workflow to test).

**Adding friends:** they turn on reminders in their app and tap **Send code** to text you their code. Add each one as its own secret: `PUSH_CONFIG_2`, `PUSH_CONFIG_3`, … up to `PUSH_CONFIG_15`. The workflow log shows who each reminder went to and flags any phone that needs a new code.

## Making changes
1. Edit `index.html`.
2. If you added or changed any style classes, rebuild the stylesheet: `python3 tools/build_css.py` (needs `pip install playwright` and `playwright install chromium`).
3. Bump `VERSION` in `sw.js` so installed copies pick up the update.
4. Run the checks: `python3 tests/smoke.py`. The **Checks** workflow runs them on every push and fails if anything breaks or `styles.css` is out of date.
