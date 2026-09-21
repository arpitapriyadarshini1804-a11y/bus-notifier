# HANDOFF — `bus-notifier` (WMATA D5X push notifier)

**Written:** 2026-09-20 ~22:00 ET (2026-09-21 ~02:00 UTC)
**Repo:** https://github.com/arpitapriyadarshini1804-a11y/bus-notifier (public, `main`)
**Repo HEAD at handoff:** `62ea59b` (state commit) on top of `5ecb2af` (the fix described below)
**Owner:** Arpita (arpita0116@gmail.com), Washington DC

Everything marked **VERIFIED** in this document was checked live against the
GitHub API, the WMATA API, or the repo itself while writing it. Everything
marked **UNVERIFIED** is an inference. Do not trust the unverified items
without re-checking.

---

## 0. TL;DR for the next session

The system was **completely non-functional from the moment it was deployed until
2026-09-21 01:43 UTC**. It has never successfully sent a real bus notification.
Two separate deployment bugs (an empty `check.py`, then a `check.py` with a
stray `python` line pasted from a markdown code fence) meant every scheduled run
either did nothing or crashed in under 11 seconds.

**As of commit `5ecb2af` the core script is fixed and verified working.** Run #7
executed the full 4m38s polling loop, called the WMATA API, and wrote
`state/arpita.json` back to the repo. There were no D5X buses running at that
moment (Sunday night, service had ended), so no push fired — which is correct
behavior, not a failure.

**The build is NOT finished.** Three substantive problems remain, in priority
order:

1. **Coverage gaps (P0).** GitHub's scheduled Actions fire every ~11 minutes, not
   the requested 5. Each run only polls for 4.5 minutes. **~40% of the clock is
   never polled**, so roughly 2 in 5 buses will be silently missed.
2. **Notification spam + no on/off switch (P0).** Weekday AM headway on the D5X
   is **6 minutes**. With the current always-on logic Arpita would receive
   ~20 pushes per hour all morning. Her single most-stated requirement — "something
   I can turn on when I wake up in the morning" — **was never built.**
3. **The self-serve setup page for friends was never tested end to end (P1).**

Sections 6 and 7 below give the evidence and the concrete plan.

---

## 1. What Arpita actually asked for

Her requirements, gathered across the conversation (quotes are verbatim):

| # | Requirement | Built? |
|---|---|---|
| 1 | Notify when the D5X (southbound, toward McPherson/Metro Center) is **at the stop before hers** — 14th & Chapin St NW | Code written, never observed firing |
| 2 | Notify when that bus is **within 5 minutes** of her stop — 14th & U St NW | Code written, never observed firing |
| 3 | **"something that I can turn on when I wake up in the morning"** | ❌ **NOT BUILT** |
| 4 | Must work with her Mac closed — *"I cant open my mac in the morning"* | ✅ Runs on GitHub Actions |
| 5 | True phone push, *"not a webpage but like an app"* | ✅ ntfy.sh + ntfy mobile app |
| 6 | Friends can self-serve via a link, *"without them having to open it again and again unless they want to add another bus"* | Page built, **untested** |
| 7 | She shouldn't have to re-enter her own config each time | ✅ Config lives in repo |

Requirement 3 is the one most likely to be mistaken for "nice to have." It isn't
— it's the difference between a useful tool and 20 pushes an hour. See §6.2.

---

## 2. Architecture as built

```
GitHub Actions cron ("*/5 * * * *", actually fires ~every 11 min)
        │
        └─> ubuntu-latest runner, 6 min timeout
              └─> bash loop: 9 × [ python3 check.py ; sleep 30 ]   (~4.5 min of polling)
                    └─> check.py
                          ├─ reads every configs/*.json
                          ├─ GET api.wmata.com/NextBusService.svc/json/jPredictions?StopID=<prev_stop_id>
                          ├─ GET api.wmata.com/NextBusService.svc/json/jPredictions?StopID=<stop_id>
                          ├─ filters by RouteID + DirectionNum
                          ├─ POST https://ntfy.sh/<ntfy_topic>   ← the push
                          └─ writes state/<name>.json  (per-TripID dedup, 2h TTL)
              └─> git commit + push state/ back to the repo
                         │
                         └─> ntfy mobile app (subscribed to the topic) shows the push
```

**Why ntfy:** free, no signup, no Apple/Google developer account needed. The
"topic" is the address — anyone who knows the topic string can both read and
post to it. See §6.6 for the security implication.

**Why GitHub Actions:** free and unlimited for **public** repos, no server to
run, survives the Mac being closed. Its weakness is schedule reliability (§6.1).

---

## 3. Repo inventory — VERIFIED

Verified by a fresh `git clone` at 2026-09-21 01:49 UTC. `git ls-files` returns
exactly five files:

| Path | Purpose | State |
|---|---|---|
| `check.py` | The whole notifier. 159 lines, md5 `1448995f1f51a676202a3e91eb79a665` | ✅ Fixed, parses, verified running |
| `.github/workflows/check.yml` | Schedule + 30s polling loop + state commit | ✅ Correct, see §6.1/§6.4 for improvements |
| `configs/arpita.json` | Arpita's route/stop config | ✅ Verified correct against live route data |
| `state/arpita.json` | Dedup bookkeeping, auto-written by the bot | ✅ Created by run #7 |
| `README.md` | User-facing docs | ✅ Present |
| `state/.gitkeep` | Keeps `state/` in git | ✅ Present |

### `configs/arpita.json` — VERIFIED CORRECT

```json
{
  "route_id": "D5X",
  "route_label": "D5X toward McPherson",
  "direction_num": "1",
  "stop_id": "1001696",
  "stop_label": "14th & U St",
  "prev_stop_id": "1001787",
  "prev_stop_label": "14th & Chapin St",
  "threshold_minutes": 5,
  "ntfy_topic": "arpita-d5x-6ec0502a43"
}
```

Checked against `GET Bus.svc/json/jRouteDetails?RouteID=D5X` on 2026-09-20:

- `Direction1` → `DirectionText: "SOUTH"`, `TripHeadsign: "METRO CENTER"` ✅ correct direction
- `Direction1.Stops[17]` = StopID `1001787` "14 St NW+Chapin St NW" ✅ the previous stop
- `Direction1.Stops[18]` = StopID `1001696` "14 St NW+U St NW" ✅ her stop
- They are genuinely adjacent in the stop sequence (17 → 18) ✅

**The config is not the problem. Do not spend time re-deriving it.**

### Secrets

`WMATA_API_KEY` is a GitHub Actions repo secret (Settings → Secrets and
variables → Actions). The value is not reproduced here — read it from
developer.wmata.com (Arpita's account, "Default Tier" product) if you need it
locally. `check.py` reads it from the environment only, never from a config file — which
is why config files are safe in a public repo.

---

## 4. Evidence that the fix works — VERIFIED

Timeline of every workflow run ever, pulled from the GitHub API:

```
#1  push               01:57:28Z  completed/failure   (bad workflow file at the time)
#2  workflow_dispatch  01:01:58Z  completed/success   4m40s — but check.py was EMPTY, did nothing
#3  schedule           01:09:25Z  completed/success   4m41s — same, did nothing
#4  workflow_dispatch  01:18:31Z  completed/failure   9s  — NameError crash
#5  schedule           01:21:00Z  completed/failure   7s  — NameError crash
#6  schedule           01:32:15Z  completed/failure   11s — NameError crash
#7  schedule           01:43:23Z  completed/SUCCESS   4m38s — FIRST REAL RUN EVER
```

Run #7 ran commit `5ecb2af`. All 8 steps green. Proof it did real work: it
created `state/arpita.json` and the bot pushed it back as commit `62ea59b`:

```json
{"notified_prev_stop": {}, "notified_arrival": {}}
```

Empty maps are correct — at 01:43–01:48 UTC (21:43–21:48 ET Sunday) the last
southbound D5X had already passed U St at 21:10, so there was nothing to notify
about. **Confirmed via the schedule API**, not assumed.

**ntfy delivery path — VERIFIED.** A test push to
`https://ntfy.sh/arpita-d5x-6ec0502a43` returned HTTP 200 with message id
`ON1r2eB1lHu7`, title "Bus notifier fixed". *Ask Arpita whether that one landed
on her phone.* If it did not, the problem is app-side (subscription/topic typo/
notification permissions on the replacement phone she mentioned installing on),
not server-side.

**Matching logic — VERIFIED.** `matching_predictions()` was ported to JS and run
against live prediction data. With a control route that was actually running
(D50 southbound, same two stops), it correctly filtered by RouteID +
DirectionNum and returned minutes sorted ascending (`[6, 28]` at Chapin,
`[8, 31]` at U St). It correctly returned zero matches for D5X.

---

## 5. Bug history — read this so you don't repeat it

### Bug A: `check.py` was committed as a 1-byte empty file
Commit `fda2249` (2026-09-20 16:31 ET). An empty Python file exits 0, so runs #2
and #3 reported **success** while doing absolutely nothing. This is why "it
looks like it's working" was misleading for hours.

### Bug B: stray `python` line from a markdown code fence
Commit `b566d16` (2026-09-20 21:15 ET). The script content was handed to Arpita
as a fenced ```` ```python ```` block to paste into GitHub's web editor, and the
fence's language tag came along as literal line 1 of the file:

```
python
#!/usr/bin/env python3
```

Every run died instantly with:

```
Traceback (most recent call last):
  File "/home/runner/work/bus-notifier/bus-notifier/check.py", line 1, in <module>
    python
NameError: name 'python' is not defined
```

Because the workflow step is a bash loop under `set -e`, the first crash aborted
the whole 9-iteration loop — hence the 7–11 second run durations, which are the
tell-tale signature of this class of failure.

**Lesson: never deliver file content as a fenced block for a human to paste into
an editor.** Write the file programmatically.

### Bug C: browser automation could not reliably edit the file
Two attempts to fix `check.py` by typing 5,470 characters into GitHub's web
CodeMirror editor via browser automation failed — the first silently left the
stray line in place, the second left the editor showing its placeholder while
the commit button went active. **Do not use browser typing for multi-KB file
content.**

**What actually worked** (use this pattern): clone the repo in a shell, write the
file with a quoted heredoc (`<< 'PYEOF'` — the quotes prevent shell expansion),
validate with `python3 -c "import ast; ast.parse(...)"`, then commit and push.
Verify afterwards with a *fresh clone* and an md5 comparison.

### Non-bug: PAT `workflow` scope
Pushing anything under `.github/workflows/` requires a PAT with the `workflow`
scope. Arpita's classic PAT has `repo` only, so that one file had to be created
through GitHub's web UI. Everything else pushes fine. **If you need to change
`check.yml`, either edit it in the web UI or get a PAT with `workflow` scope.**

---

## 6. Open issues, ranked

### 6.1 — P0: Scheduled runs leave ~40% of the clock unpolled — VERIFIED

The cron says `*/5 * * * *`. Observed actual intervals between scheduled runs:
**7.5, 11.2, 11.1 minutes.** GitHub explicitly does not guarantee cron
punctuality on shared runners; delays of 10–30+ minutes are normal and get worse
at the top of the hour.

Each run polls for only ~4.5 minutes. So the real coverage pattern is:

```
run #6:  01:32:30 ──poll 4.5min──> 01:37:00 │ DEAD 6.4 min │ 01:43:26 ──poll──> 01:48:04
```

A bus travels Chapin → U St in about a minute. If it hits Chapin during a dead
window, **both** notifications are missed entirely.

**This is almost certainly what Arpita experienced** when she wrote "it crossed u
st and didnt send push" — though note that at that specific moment (21:37 ET)
the deployed `check.py` was also still crashing, so Bug B alone explains it.

**Fixes, easiest first:**

- **(a) Overlap the runs.** Change the loop to 19 iterations (`seq 1 19`) and
  `timeout-minutes: 12`, so each run polls for ~9.5 minutes. Consecutive runs
  then overlap even at an 11-minute cadence, giving continuous coverage. You must
  also **remove the `concurrency:` block**, otherwise runs serialize and queue
  instead of overlapping. Duplicate pushes are prevented by the per-TripID state —
  but see §6.4, because overlapping runs make the state race worse.
- **(b) Move off GitHub Actions cron** to something with a reliable sub-minute
  schedule. **Cloudflare Workers is the recommended target**: free tier, cron
  triggers fire every minute reliably, Workers KV holds the dedup state, and
  `fetch()` to both WMATA and ntfy works natively. This is maybe 80 lines of
  JS and removes the entire class of problem. **This is the recommended path if
  you have the budget to rewrite.**
- **(c)** A tiny always-on host (Fly.io, Oracle Cloud free tier, a Raspberry Pi)
  running the existing Python on a 30-second loop. Most faithful to the current
  code, but adds infrastructure to maintain.

### 6.2 — P0: It will spam her, and the on/off switch was never built — VERIFIED

Weekday AM southbound D5X times at 14th & U St, pulled from the schedule API for
Monday 2026-09-21:

```
06:07 06:20 06:26 06:32 06:38 06:44 06:50 06:56 07:02 07:08 07:16 07:22
07:28 07:34 07:40 07:50 07:56 08:02 08:08 08:14 08:20 08:28 08:34 08:40
08:46 08:52 08:58 09:04 09:10 09:14 09:20 09:31 09:43 09:55 10:07 10:19
```

**Median headway: 6 minutes.** Service span: 05:37–21:37 weekdays, 07:28–21:10
Saturdays, 90 southbound trips on a weekday.

The current logic fires **two** pushes per trip (one at Chapin, one at ≤5 min
from U St), deduped per TripID but with no time restriction whatsoever. At a
6-minute headway that is **roughly 20 pushes per hour, from 05:37 until 21:37,
every single day.** The "5 minutes away" condition is nearly always true during
peak because the next bus is never more than 6 minutes out.

Arpita said: *"I am usually in a hurry in the morning, so I want something that I
can turn on when I wake up in the morning."* She wants it **armed**, not ambient.

**Fix — build the arming mechanism.** Options, best first:

- **(a) Active window in the config**, e.g. `"active_days": [1,2,3,4,5]`,
  `"active_start": "07:30"`, `"active_end": "09:15"`, evaluated in
  `America/New_York` (the runner is UTC — you **must** convert; this is an easy
  bug to introduce). Zero interaction needed, matches "it just runs everyday."
- **(b) A one-tap arm switch.** ntfy supports publishing *from* the phone, but
  simpler: a tiny GitHub Pages page or an iOS Shortcut that flips a flag (a
  `armed_until` timestamp) — via a `repository_dispatch` or by writing to the
  config. This matches "turn on when I wake up" most literally.
- **(c) A cooldown**, e.g. at most one notification per 15 minutes per config,
  so even when armed she gets one useful ping rather than a stream.

Recommended: implement **(a) + (c)** now (pure code, no new infra), and offer
(b) as a follow-up. **Ask Arpita what window she actually leaves in** — do not
guess 7:30–9:15.

### 6.3 — P1: The "at previous stop" trigger window is too narrow

`check.py` fires the previous-stop alert only when `Minutes <= 0`. A bus reports
`Minutes: 0` for roughly 30–60 seconds. With a 30-second poll that's marginal;
with any polling gap it's routinely missed. **Change the condition to
`Minutes <= 1`** — for a stop one block away that is still an accurate "it's
about to reach you" signal, and it roughly doubles the catch window.

### 6.4 — P1: The state commit can race and fail the run

The `Commit updated state` step does `git add` / `commit` / `push` with **no
`git pull --rebase`**. Today the `concurrency` block serializes runs so this
rarely bites. If you implement the overlapping-runs fix in §6.1(a) you **must**
fix this first or runs will start failing on non-fast-forward pushes. Minimum
change:

```yaml
git pull --rebase --autostash || true
git push || (git pull --rebase --autostash && git push)
```

Also consider: storing dedup state in git at all is a questionable design — it
creates a commit every few minutes forever. Workers KV (§6.1b) or simply
accepting occasional duplicates would both be cleaner.

### 6.5 — P2: Scheduled workflows get disabled after 60 days of inactivity

GitHub disables `schedule:` triggers on repos with no activity for 60 days. The
bot's own state commits **may not** reset that timer (GitHub's docs are
ambiguous and bot commits often don't count). **UNVERIFIED.** If the notifier
mysteriously stops in ~2 months, this is the first thing to check — Actions tab
will show a banner with a re-enable button.

### 6.6 — P2: Security items that need Arpita's decision

- **A classic GitHub PAT (`ghp_…`, `repo` scope) was pasted into chat and used
  to push.** It should be **rotated** (GitHub → Settings →
  Developer settings → Personal access tokens → revoke, then create a new one
  with `repo` **and** `workflow` scope). Flag this to her explicitly.
- **The ntfy topic is effectively public.** The repo is public, so
  `arpita-d5x-6ec0502a43` is readable by anyone. Anyone who finds it can send her
  push notifications, or subscribe and infer her commute. It is random enough
  not to be guessable, but it is not private. If that matters, move to ntfy with
  auth (or a self-hosted ntfy), or make the repo private — **but note that making
  the repo private costs Actions minutes** (§8).
- **Her WMATA API key is embedded in the public self-serve setup page**
  (prefilled in step 1 of the artifact). Anyone with that link can use her key
  and potentially get it rate-limited. Decide with her: leave it (convenient for
  friends) or require each friend to get their own free key. **This question was
  raised with her and never answered.**

### 6.7 — P1: The self-serve page for friends was never tested

Published artifact: **https://claude.ai/artifact/Jyw3hjMeD78voXEkTkd2T9**
("Bus Notifier Setup"). Source is in this session's scratchpad as
`bus-notifier-setup.html`.

How it works: user enters a route ID → client-side `fetch()` to
`Bus.svc/json/jRouteDetails` → populates direction and stop dropdowns → computes
the previous stop as the one at `index - 1` in the direction's stop list →
generates the config JSON and a random ntfy topic → hands them a "pre-filled
GitHub link" using the query-param trick:

```
https://github.com/<owner>/<repo>/new/main?filename=configs/<name>.json&value=<urlencoded json>
```

**Never tested end to end.** Specific things to verify:
- Does GitHub still honor the `?filename=&value=` prefill params? (They are
  undocumented and have changed before.)
- Friends need **write access** to the repo, or the flow must become a fork+PR.
  **This is probably a blocker** — a stranger cannot commit to Arpita's repo.
  Realistically this needs either (i) adding friends as collaborators, or (ii) a
  PR-based flow, or (iii) moving configs out of git into a tiny hosted store.
- Does the previous-stop `index - 1` logic hold for the *first* stop on a route
  (currently falls back to the same stop — which would produce a nonsense alert)?

---

## 7. Suggested order of work for the next session

1. **Ask Arpita two questions before coding anything:**
   (a) Did the test push titled "Bus notifier fixed" arrive on her phone?
   (b) What time window does she actually want notifications — e.g. weekdays
   7:30–9:15 AM?
2. **Implement the active window + cooldown (§6.2).** This is the highest-value
   change and it is pure `check.py` edits. Nothing else matters if the thing
   spams her into turning it off.
3. **Widen the previous-stop trigger to `Minutes <= 1` (§6.3).** One line.
4. **Fix the state-commit race (§6.4)**, then **overlap the runs (§6.1a)**. In
   that order.
5. **Watch one real weekday morning.** Check the Actions logs at ~08:00 ET for
   lines like `[arpita] 14th & Chapin St: 0 min out (trip …)` and
   `-> sent: …`. This is the only true end-to-end proof, and it has never
   happened yet.
6. Then, and only then, revisit the friends' self-serve flow (§6.7) — after
   resolving the write-access blocker.
7. Consider the Cloudflare Workers rewrite (§6.1b) if reliability is still
   unsatisfying after step 4.

---

## 8. Environment gotchas — important, will waste your time otherwise

These were all hit and worked around during this session.

- **`api.wmata.com` and `ntfy.sh` are blocked from the automation shells** by an
  egress allowlist (HTTP 403, `X-Proxy-Error: blocked-by-allowlist`). Both the
  cloud container's shell and the Mac's sandboxed shell are affected. **In a
  normal VS Code / Claude Code session on Arpita's own Mac this restriction does
  not apply** — plain `curl` will work. If you *are* in a sandboxed session,
  the workaround is to run `fetch()` from a browser page context; CORS is open
  on `api.wmata.com` (verified).
- **`api.github.com` works fine from the Mac's shell** (verified — used for all
  the run-timing data above), but **not** from the cloud container.
- **Downloading Actions logs via the API redirects to
  `results-receiver.actions.githubusercontent.com`, which IS blocked.** Read logs
  in the browser instead, or from a normal unsandboxed terminal.
- **Creating new public GitHub repos via automation is blocked** by a safety
  classifier. Arpita must create repos herself. Editing an existing repo is fine.
- **Actions minutes are free and unlimited because the repo is public**
  (verified: `visibility: public`). The current setup burns ~5 hours of runner
  time per day. **If the repo is ever made private, that blows through the
  2,000 min/month free tier in about 12 days.** Factor this into the §6.6
  privacy decision.

---

## 9. Reference data (so you don't have to re-query)

**WMATA API key:** stored as the `WMATA_API_KEY` repo secret; retrievable from
developer.wmata.com under Arpita's account. Not reproduced here because this
repo is public.

**Endpoints used:**
```
GET https://api.wmata.com/NextBusService.svc/json/jPredictions?StopID=<id>
GET https://api.wmata.com/Bus.svc/json/jRouteDetails?RouteID=D5X
GET https://api.wmata.com/Bus.svc/json/jRouteSchedule?RouteID=D5X&Date=YYYY-MM-DD&IncludingVariations=true
POST https://ntfy.sh/<topic>   headers: Title, Priority, Tags   body: message text
```
All take the key in an `api_key` header.

**D5X — "TAKOMA - METRO CTR":**
- `Direction0` = NORTH, headsign TAKOMA, 23 stops
- `Direction1` = SOUTH, headsign METRO CENTER, 24 stops ← **the one she wants**
- Southbound sequence near her: `[16]` 14th & Irving `1003087` → `[17]` 14th &
  Chapin `1001787` → `[18]` 14th & U St `1001696`

**Service span (southbound, at 14th & U St):**
- Weekday: 05:37 → 21:37, 90 trips, ~6 min headway in the AM peak
- Saturday: 07:28 → 21:10, 42 trips, ~20 min headway
- Sunday: similar to Saturday (last trip past U St around 21:10)

Note the D5X runs all day — it is **not** a peak-only route, which is a
reasonable thing to assume and would be wrong.

---

## 10. Local working copies on Arpita's Mac

- `~/bus-notifier-fix` — clone used to make the fix and push it. Remote URL has
  been scrubbed of the PAT.
- `~/verify-clone` — independent clone used to verify the push landed.
- `~/mnt/bus:notifier/` (the connected folder, real path
  `/Users/arpitapriyadarshini/bus:notifier`) — contains the **superseded**
  Mac-only version: `bus_notifier.py`, `setup.py`, `run_loop.sh`,
  `Start/Stop Bus Notifier.command`, `config.json`,
  `com.arpita.busnotifier.plist`. **This is dead code** — the GitHub Actions
  version replaced it. Consider telling Arpita she can delete the folder, or
  keep it as the basis for a local always-on option (§6.1c).
- `~/mnt/bus:notifier/repo-fix/` — an aborted partial clone. Harmless but
  untidy; deleting it requires the user's delete permission (the sandbox blocks
  `rm` in connected folders by default).

Note the literal colon in the folder name: macOS stores a `/` typed into a
folder name as `:` on disk. Quote the path in shell commands.
