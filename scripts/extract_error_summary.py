#!/usr/bin/env python3
import re
import sys
from pathlib import Path


ERROR_PATTERNS = re.compile(
    r"(::error::|traceback|exception|error:|error\b|failed|failure|timeout|exit code|http [45]\d\d)",
    re.IGNORECASE,
)
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
NOISE_PATTERNS = re.compile(
    r'^(echo "::|if \[|fi$|case |\*\)|esac$|message=|send_telegram|telegram_|curl |body_file=|http_code=|retry_|JOB_STATUS:|DATA_CHANGED:|shell: /usr/bin/bash|env:|Run )',
    re.IGNORECASE,
)


def clean_line(line: str) -> str:
    line = ANSI_PATTERN.sub("", line).strip()
    line = re.sub(r"^\d{4}-\d{2}-\d{2}T\S+\s+", "", line)
    line = re.sub(r"^##\[(group|endgroup|error)\]\s*", "", line)
    line = line.replace("::error::", "").strip()
    return " ".join(line.split())


def main() -> int:
    if len(sys.argv) != 2:
        print("No log file was provided.")
        return 0

    log_path = Path(sys.argv[1])
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"Could not read log file: {exc}")
        return 0

    cleaned = [line for line in (clean_line(line) for line in lines) if line and not NOISE_PATTERNS.search(line)]
    matches = [line for line in cleaned if ERROR_PATTERNS.search(line)]

    traceback_index = next(
        (index for index in range(len(cleaned) - 1, -1, -1) if "Traceback (most recent call last):" in cleaned[index]),
        None,
    )

    if traceback_index is not None:
        block = cleaned[traceback_index:]
        end_index = next(
            (index for index, line in enumerate(block) if "Process completed with exit code" in line),
            min(len(block), 25) - 1,
        )
        start_index = max(0, end_index - 8)
        selected = block[start_index : end_index + 1]
    elif matches:
        selected = matches[-4:]
    else:
        selected = cleaned[-8:]

    summary = "\n".join(selected) or "The step failed without producing log output."
    if len(summary) > 900:
        summary = summary[:897].rstrip() + "..."

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
