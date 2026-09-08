from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def read_srt(path):
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    timestamp = r"\d{2,}:[0-5]\d:[0-5]\d,\d{3}"
    cues = []
    for block in re.split(r"\n\s*\n", text) if text else []:
        match = re.fullmatch(rf"(\d+)\n({timestamp} --> {timestamp})\n(.+)", block, re.S)
        if not match:
            raise ValueError(f"Invalid SRT block in {path}: {block[:100]!r}")
        number, timing, words = match.groups()
        start, end = [tuple(map(int, re.split(r"[:,]", t))) for t in timing.split(" --> ")]
        if start > end or not words.strip() or (cues and int(number) <= cues[-1]["id"]):
            raise ValueError(f"Invalid timing/text or out-of-order cue ID in {path}: {number}")
        cues.append({"id": int(number), "time": timing, "text": words.strip()})
    return cues


def write_srt(path, cues):
    Path(path).write_text("".join(
        f"{cue['id']}\n{cue['time']}\n{cue['text']}\n\n" for cue in cues
    ), encoding="utf-8", newline="\n")


@contextmanager
def new_output(path, extensions):
    output = Path(path).resolve()
    if output.suffix.lower() not in extensions:
        raise ValueError(f"Output extension must be one of: {', '.join(extensions)}")
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a new filename: {output}")
    started = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    # work on the same volume
    with tempfile.TemporaryDirectory(prefix="video-", dir=output.parent) as directory:
        work = Path(directory) / ("result" + output.suffix.lower())
        yield work
        if output.exists():
            raise FileExistsError(f"Output appeared during processing; refusing to replace it: {output}")
        work.rename(output)
    print(f"Saved {output} ({time.perf_counter() - started:.1f}s)")


def run(command, cwd=None):
    executable = shutil.which(command[0])
    if not executable:
        raise FileNotFoundError(f"Executable not found: {command[0]}. See README.md for setup.")
    subprocess.run([str(Path(executable).resolve()), *(str(part) for part in command[1:])], check=True, cwd=cwd)


def cli(main):
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Error: {error}") from None
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; original files were not changed.") from None
