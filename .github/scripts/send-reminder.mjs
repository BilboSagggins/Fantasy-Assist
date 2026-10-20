// Sends the daily "lock your picks" push notification.
// PUSH_CONFIG is the code copied from RosterIQ (Lockdown Advisor > Daily lock reminder).
import webpush from 'web-push';

const raw = process.env.PUSH_CONFIG;
if (!raw) {
    console.log('PUSH_CONFIG secret is not set yet, so there is nothing to send.');
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

let cfg;
try { cfg = JSON.parse(raw); } catch (e) {
    console.error('PUSH_CONFIG is not valid. Copy the code from the app again and replace the secret.');
    process.exit(1);
}
webpush.setVapidDetails(cfg.subject || 'https://bilbosagggins.github.io/Fantasy-Assist/', cfg.publicKey, cfg.privateKey);

const payload = JSON.stringify({
    title: 'Time to lock your picks',
    body: "Open RosterIQ to see who to lock or wait on, and fix today's lineup.",
    url: './?sport=nba'
});

let sent = 0;
for (const sub of cfg.subscriptions || []) {
    try {
        await webpush.sendNotification(sub, payload, { TTL: 4 * 3600, urgency: 'high' });
        sent++;
    } catch (e) {
        const gone = e.statusCode === 404 || e.statusCode === 410;
        console.error(gone
            ? 'This phone is no longer subscribed. Turn reminders on again in the app and replace the PUSH_CONFIG secret.'
            : `Send failed (${e.statusCode || ''}): ${e.body || e.message}`);
    }
}
console.log(`Sent ${sent} reminder(s).`);
if (!sent) process.exit(1);
