#!/usr/bin/env python3
"""
Mac Pomodoro-ish timer — records how long you stall at the "Type 'clear'..." prompt.

Changes:
- Tracks cumulative idle time (seconds) when the program asks "Type 'clear'... ENTER to continue".
- Stores data in ~/.task_summary.json as a dict:
  {"tasks": [...], "idle_seconds": 123}
- Backwards-compatible: converts older list-style files to the new structure automatically.
- Shows total idle time in the printed summary.
"""

import os
import time
import json
import shutil
import subprocess
import math
from datetime import datetime, timedelta
from pathlib import Path

# ---------- Config ----------
SUMMARY_PATH = Path.home() / ".task_summary.json"
TASK_DURATION_SECONDS = 25 * 60  # 25 minutes
SNOOZE_SECONDS = 5 * 60          # 5 minutes
SYSTEM_SOUND = "/System/Library/Sounds/Glass.aiff"
SOUND_REPEAT = 2
# ----------------------------

def play_sound(times=SOUND_REPEAT):
    """Play a short notification sound `times` times (macOS-friendly)."""
    for _ in range(times):
        if shutil.which("afplay") and os.path.exists(SYSTEM_SOUND):
            try:
                subprocess.run(["afplay", SYSTEM_SOUND], check=False)
            except Exception:
                fallback_beep()
        else:
            fallback_beep()
        time.sleep(0.25)

def fallback_beep():
    try:
        subprocess.run(["osascript", "-e", 'beep'], check=False)
    except Exception:
        print("\a", end="", flush=True)

def mac_notify(title, message):
    """Best-effort macOS notification."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], check=False)
    except Exception:
        pass

# ---- Summary storage helpers (new structure) ----
# File format will be:
# {
#   "tasks": [ <task-records-as-before> ],
#   "idle_seconds": 0
# }

def load_summary_data():
    """Load summary data, handling legacy list files by converting them."""
    if SUMMARY_PATH.exists():
        try:
            raw = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
            # If file is a plain list (old format), convert to new dict format
            if isinstance(raw, list):
                return {"tasks": raw, "idle_seconds": 0}
            if isinstance(raw, dict):
                # ensure keys exist
                tasks = raw.get("tasks") if isinstance(raw.get("tasks"), list) else []
                idle = int(raw.get("idle_seconds", 0) or 0)
                return {"tasks": tasks, "idle_seconds": idle}
        except Exception:
            # corrupted file -> return empty structure
            return {"tasks": [], "idle_seconds": 0}
    return {"tasks": [], "idle_seconds": 0}

def save_summary_data(summary_data):
    try:
        SUMMARY_PATH.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print("Warning: couldn't save summary:", e)

def humanize_seconds(sec):
    sec = int(sec)
    m = sec // 60
    s = sec % 60
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

# ---- old helpers adapted to new summary_data ----

def format_time(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S")

def supports_ansi_strikethrough():
    term = os.environ.get("TERM", "")
    return "xterm" in term or "screen" in term or "vt100" in term or os.environ.get("COLORTERM") is not None

ANSI_STRIKE_ON = "\x1b[9m"
ANSI_STRIKE_OFF = "\x1b[0m"

def render_task_line(idx, record, use_ansi):
    name = record.get("name", "<unnamed>")
    checked = record.get("completed", False)
    if checked:
        if use_ansi:
            display_name = f"{ANSI_STRIKE_ON}{name}{ANSI_STRIKE_OFF}"
            box = "[x]"
        else:
            display_name = f"~~{name}~~"
            box = "[x]"
    else:
        display_name = name
        box = "[ ]"
    planned = record.get("planned_seconds", 0) // 60
    end = record.get("end", "")
    return f"{idx:>2}. {box} {display_name} ({planned}m) — {end}"

def print_summary(summary_data):
    tasks = summary_data.get("tasks", [])
    idle = summary_data.get("idle_seconds", 0)
    if not tasks:
        print("\n--- Summary: (empty) ---")
        print(f"Total idle time at 'clear' prompts: {humanize_seconds(idle)}")
        print()
        return
    print("\n--- Task Summary ---")
    use_ansi = supports_ansi_strikethrough()
    for i, rec in enumerate(tasks, start=1):
        print(render_task_line(i, rec, use_ansi))
    print(f"\nSaved to: {SUMMARY_PATH}")
    print(f"Total idle time at 'clear' prompts: {humanize_seconds(idle)}\n")

def record_for_task(name, start_dt, end_dt, planned_seconds, actual_seconds, completed=True):
    return {
        "name": name,
        "start": format_time(start_dt),
        "end": format_time(end_dt),
        "planned_seconds": int(planned_seconds),
        "actual_seconds": int(actual_seconds),
        "completed": bool(completed)
    }

def _print_single_line(msg):
    """Print a single-line status that overwrites itself."""
    padded = msg + " " * 20
    print("\r" + padded, end="", flush=True)

def run_timer(duration_seconds, label):
    start = datetime.now()
    end_time = start + timedelta(seconds=duration_seconds)
    nice_label = label.capitalize()
    header = f"{nice_label} started at {format_time(start)} — {duration_seconds//60} minutes. Focus."
    print("\n" + header)
    mac_notify(f"{nice_label} started", f"{duration_seconds//60} minutes")

    try:
        while True:
            now = datetime.now()
            remaining = (end_time - now).total_seconds()
            if remaining <= 0:
                break

            if remaining >= 60:
                minutes_left = math.ceil(remaining / 60)
                status = f"{nice_label} — {minutes_left} min left ⏳"
                _print_single_line(status)

                next_change_remaining = (minutes_left - 1) * 60
                sleep_time = remaining - next_change_remaining
                if sleep_time <= 0:
                    sleep_time = 1
                sleep_time = min(sleep_time, remaining)
                time.sleep(sleep_time)
                continue
            else:
                status = f"{nice_label} — Less than 1 min left ⏳"
                _print_single_line(status)
                time.sleep(remaining)
                break

    except KeyboardInterrupt:
        actual_end = datetime.now()
        elapsed = (actual_end - start).total_seconds()
        print("\r" + " " * 80 + "\r", end="", flush=True)
        print("Timer cancelled early.")
        mac_notify(f"{nice_label} cancelled", f"Cancelled after {int(elapsed//60)} min")
        return record_for_task(label, start, actual_end, duration_seconds, elapsed, completed=False)

    finish = datetime.now()
    print("\r" + " " * 80 + "\r", end="", flush=True)
    print(f"{nice_label} done at {format_time(finish)} — good job.")
    play_sound(times=SOUND_REPEAT)
    mac_notify(f"{nice_label} finished", f"{label} finished")
    return record_for_task(label, start, finish, duration_seconds, duration_seconds, completed=True)

def confirm(prompt):
    ans = input(prompt + " (y/N): ").strip().lower()
    return ans == "y" or ans == "yes"

# ---- New helper: timed input for the inline clear prompt ----

def timed_input(prompt):
    """
    Show a prompt and measure how long the user takes to respond.
    Returns (response_string, elapsed_seconds).
    """
    start = time.time()
    try:
        resp = input(prompt)
    except KeyboardInterrupt:
        # if user Ctrl+C while responding, treat as immediate interrupt (0 elapsed)
        raise
    elapsed = time.time() - start
    return resp, elapsed

# ---- Main loop adapted to new summary_data structure ----

def main_loop():
    summary_data = load_summary_data()
    print("Tiny Mac Pomodoro-ish timer — tracks idle time at 'clear' prompts. Commands: 'list', 'clear', 'quit'\n")
    try:
        while True:
            try:
                play_sound(times=1)  # short ping before asking
            except Exception:
                pass

            user = input("What task? (or 'break' / 'list' / 'clear' / 'quit') ").strip()
            if not user:
                print("Say something or type 'quit'.")
                continue

            cmd = user.lower()

            if cmd in ("quit", "exit"):
                print("Exiting. Saved tasks to", SUMMARY_PATH)
                save_summary_data(summary_data)
                break

            if cmd == "list":
                print_summary(summary_data)
                continue

            if cmd == "clear":
                # explicit clear command: ask confirm (no timed measurement requested by user)
                tasks = summary_data.get("tasks", [])
                if not tasks:
                    print("Summary already empty.")
                    continue
                if confirm("Are you sure you want to CLEAR the saved summary? This cannot be undone"):
                    summary_data = {"tasks": [], "idle_seconds": 0}
                    save_summary_data(summary_data)
                    print("Summary cleared.")
                else:
                    print("Not cleared.")
                continue

            if cmd == "break":
                rec = run_timer(SNOOZE_SECONDS, "break")
                summary_data["tasks"].append(rec)
                save_summary_data(summary_data)
                print_summary(summary_data)

                # inline clear prompt — timed measurement happens here
                if summary_data["tasks"]:
                    resp, elapsed = timed_input("Type 'clear' to wipe summary, ENTER to continue: ")
                    # record idle time
                    summary_data["idle_seconds"] = int(summary_data.get("idle_seconds", 0) + elapsed)
                    save_summary_data(summary_data)

                    # handle clear action if user typed 'clear'
                    if resp.strip().lower() == "clear":
                        if confirm("Confirm CLEAR?"):
                            summary_data = {"tasks": [], "idle_seconds": summary_data.get("idle_seconds", 0)}
                            save_summary_data(summary_data)
                            print("Summary cleared.")
                continue

            # otherwise treat as task name
            task_name = user
            rec = run_timer(TASK_DURATION_SECONDS, task_name)
            summary_data["tasks"].append(rec)
            save_summary_data(summary_data)
            print_summary(summary_data)

            # inline clear prompt — timed measurement here as well
            if summary_data["tasks"]:
                resp, elapsed = timed_input("Type 'clear' to wipe summary, ENTER to continue: ")
                summary_data["idle_seconds"] = int(summary_data.get("idle_seconds", 0) + elapsed)
                save_summary_data(summary_data)

                if resp.strip().lower() == "clear":
                    if confirm("Confirm CLEAR?"):
                        summary_data = {"tasks": [], "idle_seconds": summary_data.get("idle_seconds", 0)}
                        save_summary_data(summary_data)
                        print("Summary cleared.")

    except KeyboardInterrupt:
        print("\nInterrupted. Saving summary and quitting.")
        save_summary_data(summary_data)

if __name__ == "__main__":
    main_loop()