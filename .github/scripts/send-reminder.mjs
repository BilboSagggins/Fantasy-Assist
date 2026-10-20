// Sends the daily "lock your picks" push notification to every phone that's set up.
// Each phone's code (copied from RosterIQ > Daily lock reminder) goes in its own secret:
// PUSH_CONFIG for the first phone, then PUSH_CONFIG_2, PUSH_CONFIG_3, ... for others.
import webpush from 'web-push';

// Pull every code out of the PUSH_CONFIG* secrets (one per secret, or several pasted together)
function codesFrom(text) {
    const out = [];
    let depth = 0, start = -1, inStr = false, esc = false;
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') inStr = false; continue; }
        if (c === '"') inStr = true;
        else if (c === '{') { if (depth++ === 0) start = i; }
        else if (c === '}' && depth > 0 && --depth === 0) out.push(text.slice(start, i + 1));
    }
    return out;
}

const secrets = Object.entries(process.env)
    .filter(([k, v]) => /^PUSH_CONFIG(_\d+)?$/.test(k) && v && v.trim())
    .sort(([a], [b]) => a.localeCompare(b, 'en', { numeric: true }));
if (!secrets.length) {
    console.log('No PUSH_CONFIG secrets are set yet, so there is nothing to send.');
    process.exit(0);
}

// Scheduled runs: only send from the run that lands at 10 AM Central today
const schedule = process.env.SCHEDULE || '';
if (schedule) {
    const utcHour = Number(schedule.trim().split(/\s+/)[1]);
    const now = new Date();
    const at = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), utcHour));
    const centralHour = Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric', hourCycle: 'h23' }).format(at));
    if (centralHour !== 10) {
        console.log(`Skipping: ${utcHour}:00 UTC is ${centralHour}:00 Central today; the other run sends at 10.`);
        process.exit(0);
    }
}

const payload = JSON.stringify({
    title: 'Time to lock your picks',
    body: "Open RosterIQ to see who to lock or wait on, and fix today's lineup.",
    url: './?tab=sleeper'
});

let sent = 0, failed = 0;
for (const [secretName, value] of secrets) {
    const codes = codesFrom(value);
    if (!codes.length) { console.error(`${secretName}: no code found. Copy it from the app again.`); failed++; continue; }
    for (const raw of codes) {
        let cfg;
        try { cfg = JSON.parse(raw); } catch (e) { console.error(`${secretName}: a code is damaged. Copy it from the app again.`); failed++; continue; }
        const who = cfg.name ? `${cfg.name} (${secretName})` : secretName;
        try {
            const vapid = { subject: cfg.subject || 'https://bilbosagggins.github.io/Fantasy-Assist/', publicKey: cfg.publicKey, privateKey: cfg.privateKey };
            for (const sub of cfg.subscriptions || []) {
                await webpush.sendNotification(sub, payload, { TTL: 4 * 3600, urgency: 'high', vapidDetails: vapid });
                sent++;
                console.log(`Sent to ${who}.`);
            }
        } catch (e) {
            failed++;
            const gone = e.statusCode === 404 || e.statusCode === 410;
            console.error(gone
                ? `${who}: that phone is no longer subscribed. They need to turn reminders on again and send a new code.`
                : `${who}: send failed (${e.statusCode || ''}) ${e.body || e.message}`);
        }
    }
}
console.log(`Done: ${sent} sent, ${failed} failed.`);
if (!sent && failed) process.exit(1);
