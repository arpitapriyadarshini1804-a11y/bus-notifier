# bus-notifier

Sends a phone push notification (via the free [ntfy](https://ntfy.sh) app)
when a WMATA bus is one stop away, and again when it's within a few
minutes of your stop. Runs on GitHub Actions' free schedule, so it works
even when your computer is off.

## How it works

- `configs/*.json` - one file per person/bus. Each one names a route,
  direction, "your stop," and the stop before it, plus an ntfy topic to
  notify.
- `check.py` - reads every config, checks WMATA's live predictions, and
  sends a push notification via ntfy when it's time.
- `.github/workflows/check.yml` - runs `check.py` on a loop, roughly
  every 30 seconds, via GitHub's free scheduled Actions.
- `state/*.json` - internal bookkeeping so you don't get pinged twice for
  the same bus. Safe to ignore.

The WMATA API key lives in the repo's **Settings -> Secrets and
variables -> Actions -> WMATA_API_KEY** secret, never in a config file,
so config files are safe to have in this public repo.

## Adding a new person/bus

Use the setup page (link shared separately) to look up your route,
direction, and stop from a live list - it will generate a ready-to-paste
JSON block for you. Then in this repo:

1. Click **Add file -> Create new file**.
2. Name it `configs/<your-name>.json`.
3. Paste the JSON block you were given.
4. Click **Commit new file**.

That's it - no other setup needed. Within a few minutes you'll start
getting notifications. Install the [ntfy app](https://ntfy.sh) and
subscribe to the topic name from your JSON block to receive them.
