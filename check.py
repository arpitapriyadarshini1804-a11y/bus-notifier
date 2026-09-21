#!/usr/bin/env python3
"""
Checks every configs/*.json against WMATA's real-time predictions and
sends push notifications (via ntfy.sh) when a bus is:
  1. AT the previous stop (one stop before the person's stop), or
  2. within `threshold_minutes` of the person's stop.

Runs from GitHub Actions on a schedule - see .github/workflows/check.yml.
The WMATA API key comes from the WMATA_API_KEY repo secret (env var),
never from the config files, so configs are safe to commit even though
this repo is public.
"""
import glob
import json
import os
import time
import urllib.request
import urllib.error

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.join(REPO_DIR, "configs")
STATE_DIR = os.path.join(REPO_DIR, "state")
API_KEY = os.environ.get("WMATA_API_KEY", "")


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        log(f"WARN: could not read {path}: {e}")
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def http_get_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_predictions(stop_id):
    url = f"https://api.wmata.com/NextBusService.svc/json/jPredictions?StopID={stop_id}"
    data = http_get_json(url, headers={"api_key": API_KEY})
    return data.get("Predictions", [])


def matching_predictions(predictions, cfg):
    route = cfg["route_id"]
    direction_num = str(cfg.get("direction_num", "")).strip()
    out = []
    for p in predictions:
        if p.get("RouteID") != route:
            continue
        if direction_num and str(p.get("DirectionNum")) != direction_num:
            continue
        out.append(p)
    out.sort(key=lambda p: p.get("Minutes", 9999))
    return out


def send_ntfy(topic, title, message, priority="default"):
    url = f"https://ntfy.sh/{topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": "bus"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        log(f"  -> sent: {title} - {message}")
    except urllib.error.URLError as e:
        log(f"  -> ERROR sending notification: {e}")


def prune_old(d, now, max_age_seconds=7200):
    return {k: v for k, v in d.items() if now - v < max_age_seconds}


def check_one(config_path):
    name = os.path.splitext(os.path.basename(config_path))[0]
    cfg = load_json(config_path, None)
    if cfg is None:
        return

    state_path = os.path.join(STATE_DIR, f"{name}.json")
    state = load_json(state_path, {"notified_prev_stop": {}, "notified_arrival": {}})
    state.setdefault("notified_prev_stop", {})
    state.setdefault("notified_arrival", {})
    now = time.time()
    state["notified_prev_stop"] = prune_old(state["notified_prev_stop"], now)
    state["notified_arrival"] = prune_old(state["notified_arrival"], now)

    route_label = cfg.get("route_label", cfg.get("route_id"))
    stop_label = cfg.get("stop_label", "your stop")
    prev_label = cfg.get("prev_stop_label", "the previous stop")
    threshold = cfg.get("threshold_minutes", 5)
    topic = cfg["ntfy_topic"]

    try:
        prev_matches = matching_predictions(get_predictions(cfg["prev_stop_id"]), cfg)
    except Exception as e:
        log(f"[{name}] ERROR fetching previous-stop predictions: {e}")
        prev_matches = []

    if prev_matches:
        m = prev_matches[0]
        minutes, trip_id = m.get("Minutes"), m.get("TripID") or m.get("VehicleID")
        log(f"[{name}] {prev_label}: {minutes} min out (trip {trip_id})")
        if minutes is not None and minutes <= 0 and trip_id not in state["notified_prev_stop"]:
            send_ntfy(topic, f"{route_label} at {prev_label}",
                      f"{route_label} is now at {prev_label} - one stop before {stop_label}.")
            state["notified_prev_stop"][trip_id] = now

    try:
        matches = matching_predictions(get_predictions(cfg["stop_id"]), cfg)
    except Exception as e:
        log(f"[{name}] ERROR fetching stop predictions: {e}")
        matches = []

    if matches:
        m = matches[0]
        minutes, trip_id = m.get("Minutes"), m.get("TripID") or m.get("VehicleID")
        log(f"[{name}] {stop_label}: {minutes} min out (trip {trip_id})")
        if minutes is not None and minutes <= threshold and trip_id not in state["notified_arrival"]:
            send_ntfy(topic, f"{route_label} arriving soon",
                      f"{route_label} is {minutes} min from {stop_label}.", priority="high")
            state["notified_arrival"][trip_id] = now

    save_json(state_path, state)


def main():
    if not API_KEY:
        log("ERROR: WMATA_API_KEY environment variable / repo secret is not set.")
        return
    configs = sorted(glob.glob(os.path.join(CONFIGS_DIR, "*.json")))
    if not configs:
        log("No configs found in configs/. Nothing to check.")
        return
    for path in configs:
        check_one(path)


if __name__ == "__main__":
    main()
