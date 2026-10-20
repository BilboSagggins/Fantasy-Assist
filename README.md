# Fantasy-Assist
Assist in making fantasy football and basketball decisions.

**Open it:** https://bilbosagggins.github.io/Fantasy-Assist/

## Install it as a phone app
- **Android (Chrome):** open the link, tap **Install** in the top bar (or ⋮ menu → *Install app*).
- **Samsung Internet:** open the link, tap ☰ menu → *Add page to* → *Home screen*.
- **iPhone (Safari):** open the link, tap Share → *Add to Home Screen*.

The app opens full screen from your home screen and always loads the newest version when you're online.

## Updating
After changing `index.html`, bump `VERSION` in `sw.js` (e.g. `rosteriq-v2`) so installed copies refresh their cache.

## Daily lock reminder (10 AM Central)
1. In the app: Lockdown Advisor → **Daily lock reminder** → **Turn on reminders**, then **Copy code**.
2. On GitHub: Settings → Secrets and variables → Actions → **New repository secret**, name it `PUSH_CONFIG`, paste the code.
3. The **Lock reminder** workflow sends the notification every day at 10 AM Central (Actions → Lock reminder → Run workflow to test).

**Adding friends:** they turn on reminders in their app and tap **Send code** to text you their code. Add each one as its own secret: `PUSH_CONFIG_2`, `PUSH_CONFIG_3`, … up to `PUSH_CONFIG_15`. (GitHub can't show a secret after it's saved, so one secret per person means you never have to re-paste the others.) The workflow log shows who each reminder went to and flags any phone that needs a new code.
