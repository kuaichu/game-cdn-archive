#!/usr/bin/env python3
"""Build a month-to-date game version update report."""

from __future__ import annotations

import argparse
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from summarize_version_updates import SOURCES, summarize


def git_output(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def month_start_for(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day.replace(day=1), time.min, tzinfo=tz)


def is_month_end(day: date) -> bool:
    return (day + timedelta(days=1)).month != day.month


def base_ref_before(month_start: datetime) -> str:
    cutoff = month_start.astimezone(timezone.utc).isoformat()
    before = git_output(["git", "rev-list", "-1", f"--before={cutoff}", "HEAD"])
    if before:
        return before
    after = git_output(["git", "rev-list", "--reverse", f"--since={cutoff}", "HEAD"])
    for ref in after.splitlines():
        if all(
            subprocess.run(
                ["git", "cat-file", "-e", f"{ref}:{source.path}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
            for source in SOURCES
        ):
            return ref
    return after.splitlines()[0] if after else ""


def build_report(root: Path, tz_name: str, today: date, force: bool) -> str:
    if not force and not is_month_end(today):
        return ""

    tz = ZoneInfo(tz_name)
    month_start = month_start_for(today, tz)
    base_ref = base_ref_before(month_start)
    lines = summarize(base_ref, root, max_lines=50)
    month_label = today.strftime("%Y-%m")

    report_lines = [
        "Game CDN Archive monthly update report",
        f"Month: {month_label}",
        "",
    ]
    if lines:
        report_lines.append("Updates:")
        report_lines.extend(f"- {line}" for line in lines)
    else:
        report_lines.append("No game version updates were detected this month.")

    return "\n".join(report_lines)


def parse_today(value: str | None, tz: ZoneInfo) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(tz).date()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="Timezone used for month-end detection.")
    parser.add_argument("--today", help="Override current date as YYYY-MM-DD for tests.")
    parser.add_argument("--force", action="store_true", help="Build the report even when today is not month end.")
    parser.add_argument("--output", help="Optional file to write the report to.")
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    report = build_report(Path(args.root), args.timezone, parse_today(args.today, tz), args.force)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
