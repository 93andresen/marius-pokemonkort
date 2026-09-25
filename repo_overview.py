"""
READ-ONLY git repository overview.

This script NEVER mutates the repository. It only runs read-only git
commands: rev-parse, status, log, diff-tree, ls-tree, count-objects.
It is designed to give a complete picture of the repo in one run:

  1. Current branch / HEAD / upstream state
  2. Working tree state (staged, unstaged, untracked)
  3. Full commit history (with per-commit change counts)
  4. Detailed file changes for every commit (A/M/D/R status per file)
  5. Largest files currently tracked in HEAD, with the commit that
     first added each path (so you can see what is taking up space
     and when it was added)
  6. Pack/database object statistics

Usage:
    uv run repo_overview.py
"""

import subprocess
import sys
from collections import defaultdict

# git commands that are allowed. Anything else is refused.
ALLOWED_GIT_COMMANDS = {
    "rev-parse",
    "status",
    "log",
    "diff-tree",
    "ls-tree",
    "count-objects",
    "show-ref",
    "branch",
}


def git(*args):
    """Run a read-only git command and return stdout. Fails loudly."""
    if not args or args[0] not in ALLOWED_GIT_COMMANDS:
        raise RuntimeError(
            f"Refusing to run git command not in allow-list: git {' '.join(args)}"
        )
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"ERROR: git {' '.join(args)} exited {result.returncode}")
        print(result.stderr)
        sys.exit(result.returncode)
    return result.stdout


def human_size(num_bytes):
    if num_bytes is None:
        return "?"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def section(title):
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. Current state
# ---------------------------------------------------------------------------
section("1. CURRENT STATE")

head = git("rev-parse", "HEAD").strip()
branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
print(f"HEAD:            {head}")
print(f"Branch:          {branch}")

upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
print(f"Upstream:        {upstream}")
status_sb_first = git("status", "-sb").splitlines()[0]
# e.g. "## main...origin/main [ahead 1, behind 2]"
ahead = behind = 0
if "[" in status_sb_first and "]" in status_sb_first:
    info = status_sb_first.split("[", 1)[1].split("]", 1)[0]
    for token in info.split(","):
        token = token.strip()
        if token.startswith("ahead"):
            ahead = int(token.split()[1])
        elif token.startswith("behind"):
            behind = int(token.split()[1])
print(f"Ahead/behind:    ahead {ahead}, behind {behind} (vs {upstream})")

# ---------------------------------------------------------------------------
# 2. Working tree state
# ---------------------------------------------------------------------------
section("2. WORKING TREE STATE (uncommitted changes)")

status_lines = git("status", "--porcelain", "-M").splitlines()
staged, unstaged, untracked = [], [], []
for line in status_lines:
    code, path = line[:2], line[3:]
    if code == "??":
        untracked.append(path)
    else:
        x, y = code[0], code[1]
        if x not in (" ", "?"):
            staged.append((x, path))
        if y not in (" ", "?"):
            unstaged.append((y, path))

print(f"Staged changes:     {len(staged)}")
print(f"Unstaged changes:   {len(unstaged)}")
print(f"Untracked entries:  {len(untracked)}")

if staged:
    print("\n  -- staged --")
    for code, path in staged:
        print(f"  {code}  {path}")
if unstaged:
    print("\n  -- unstaged --")
    for code, path in unstaged:
        print(f"  {code}  {path}")
if untracked:
    print("\n  -- untracked --")
    for path in untracked:
        print(f"  ??  {path}")
if not status_lines:
    print("  (clean - no uncommitted changes)")

# ---------------------------------------------------------------------------
# 3. Full commit history
# ---------------------------------------------------------------------------
section("3. COMMIT HISTORY (all commits, newest first)")

log_lines = git(
    "log", "--format=%H%x09%h%x09%as%x09%s"
).splitlines()

commits = []  # (full_hash, short_hash, date, subject)
for line in log_lines:
    full, short, date, subject = line.split("\t", 3)
    commits.append((full, short, date, subject))
print(f"Total commits: {len(commits)}")
print()
print(f"{'hash':<10} {'date':<10} {'files':>6} {'+lines':>8} {'-lines':>8}  subject")
print("-" * 100)

# numstat per commit: adds/dels/path (renames shown as old => new)
commit_numstat = {}
for full, short, date, subject in commits:
    out = git("diff-tree", "-r", "--numstat", "-M", "--root", full).splitlines()
    # diff-tree prints a bare commit-id line first; only lines containing a
    # tab are numstat rows.
    rows = [line for line in out if "\t" in line]
    n_files = len(rows)
    adds = dels = 0
    for line in rows:
        parts = line.split("\t")
        if len(parts) < 3:
            print(f"  WARNING: skipping malformed numstat line: {line!r}")
            continue
        a, d = parts[0], parts[1]
        adds += 0 if a == "-" else int(a)
        dels += 0 if d == "-" else int(d)
    commit_numstat[full] = (n_files, adds, dels)
    print(f"{short:<10} {date:<10} {n_files:>6} {adds:>8} {dels:>8}  {subject}")

# ---------------------------------------------------------------------------
# 4. Detailed file changes per commit
# ---------------------------------------------------------------------------
section("4. FILES CHANGED IN EACH COMMIT (A=added M=modified D=deleted R=renamed)")

for full, short, date, subject in commits:
    n_files, adds, dels = commit_numstat[full]
    print()
    print(f"--- {short} {date}  \"{subject}\"  ({n_files} files, +{adds}/-{dels}) ---")
    changes = git("diff-tree", "-r", "--name-status", "-M", "--root", full).splitlines()
    for line in changes:
        if "\t" not in line:
            continue  # bare commit-id line, not a file row
        parts = line.split("\t")
        st = parts[0]
        if st.startswith("R") or st.startswith("C"):
            print(f"  {st:<6} {parts[1]}  =>  {parts[2]}")
        else:
            print(f"  {st:<6} {parts[1]}")

# ---------------------------------------------------------------------------
# 5. Largest tracked files in HEAD + when each path was first added
# ---------------------------------------------------------------------------
section("5. LARGEST FILES IN HEAD (what is taking up space) + when first added")

# blob sizes in HEAD
sizes = {}  # path -> bytes
for line in git("ls-tree", "-r", "-l", "HEAD").splitlines():
    meta, path = line.split("\t", 1)
    fields = meta.split()
    # fields: mode, type, sha, size
    if len(fields) >= 4 and fields[1] == "blob":
        sizes[path] = int(fields[3])

# when each path first appeared (A = genuinely new, R = appeared via rename)
first_added = {}  # path -> (short_hash, date, how)
current_commit = None
for line in git(
    "log", "--reverse", "--name-status", "-M", "--format=C %h %as"
).splitlines():
    if line.startswith("C "):
        _, short, date = line.split(" ", 2)
        current_commit = (short, date)
        continue
    if not line.strip() or current_commit is None:
        continue
    parts = line.split("\t")
    st = parts[0]
    if st.startswith("R") or st.startswith("C"):
        paths = [parts[2]]
    else:
        paths = [parts[1]] if len(parts) > 1 else []
    for path in paths:
        if path not in first_added:
            first_added[path] = (current_commit[0], current_commit[1], st[0])

top_n = 40
largest = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
total = sum(sizes.values())
print(f"Tracked files in HEAD: {len(sizes)}   total blob size: {human_size(total)}")
print(f"Showing top {top_n} largest:\n")
print(f"{'size':>12} {'added in':<10} {'date':<10} {'how':<4} path")
print("-" * 110)
for path, size in largest:
    info = first_added.get(path)
    if info:
        short, date, how = info
    else:
        short, date, how = "?", "?", "?"
    print(f"{human_size(size):>12} {short:<10} {date:<10} {how:<4} {path}")

# aggregate size per top-level directory in HEAD
dir_sizes = defaultdict(int)
dir_counts = defaultdict(int)
for path, size in sizes.items():
    top = path.split("/")[0] if "/" in path else "(repo root files)"
    dir_sizes[top] += size
    dir_counts[top] += 1

print("\nSize per top-level directory (tracked files in HEAD):\n")
print(f"{'size':>12} {'files':>7}  directory")
print("-" * 80)
for top, size in sorted(dir_sizes.items(), key=lambda kv: kv[1], reverse=True):
    print(f"{human_size(size):>12} {dir_counts[top]:>7}  {top}/")

# ---------------------------------------------------------------------------
# 6. Object database statistics
# ---------------------------------------------------------------------------
section("6. OBJECT DATABASE (size of .git)")

for line in git("count-objects", "-vH").splitlines():
    print(f"  {line}")

print()
print("Done. (Read-only: no git state was modified.)")
