"""AC-2997 scan-threshold pool: switch pages between "good" and "broken".

accessFlow only counts a page as failed when it is already known from an earlier
audit. A URL that fails the first time the crawler sees it is dropped, not
counted. So testing is always two steps:

  1. baseline  -> every pool page loads (200). Run an audit so they become known.
  2. break     -> some pool pages now fail. Run the audit again.

Usage (from the repo root):
  python3 scan-threshold/scan_state.py baseline
  python3 scan-threshold/scan_state.py break --total 400 --rate 65
  python3 scan-threshold/scan_state.py break --total 400 --rate 30 --timeout 5 --nonlicensed 5 --empty 5
  python3 scan-threshold/scan_state.py status

--total = "Audited pages" shown on the Dashboard after the baseline audit.
--rate  = success % you want. Failed pages = total - round(total * rate / 100).
Broken pages are 404 (file removed) unless you ask for other reasons.
"""
import argparse
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "pool")
CHILDREN = 256  # + pool/index.html = 257 pool pages

GOOD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scan threshold pool - page {n}</title>
</head>
<body>
<header><nav><a href="index.html">Pool index</a></nav></header>
<main>
<h1>Scan threshold pool - page {n}</h1>
<p>Test page for AC-2997. It loads normally in the baseline state.</p>
<p>Known issues so the audit has results: an image with no alt text and an empty link.</p>
<img src="../../image%20(14).png" width="40" height="40">
<a href="index.html"></a>
<ul><li>Item one</li><li>Item two</li><li>Item three</li></ul>
<button type="button">Button</button>
</main>
</body>
</html>
"""

# Blocks parsing in <head>, so DOMContentLoaded never fires -> navigation time-out.
TIMEOUT = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Slow page</title>
<script>while (true) {}</script>
</head>
<body><p>Never loads.</p></body>
</html>
"""

# Lands on another domain within the scanner's 3s client-redirect wait.
NONLICENSED = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Redirect</title>
<meta http-equiv="refresh" content="0; url=https://example.com/">
<script>location.replace("https://example.com/");</script>
</head>
<body></body>
</html>
"""

# Empty content is only a failure when the aflwScannerEmptyContentFailure flag is on.
EMPTY = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title></title></head><body></body></html>
"""


def page_path(n):
    return os.path.join(POOL, f"page-{n:03d}.html")


def write(path, body):
    with open(path, "w") as f:
        f.write(body)


def write_index():
    links = "\n".join(f'<li><a href="page-{n:03d}.html">Pool page {n}</a></li>' for n in range(1, CHILDREN + 1))
    write(os.path.join(POOL, "index.html"), f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scan threshold pool</title></head>
<body><main>
<h1>Scan threshold pool (AC-2997)</h1>
<p>{CHILDREN} pages used to test partial and failed audits.</p>
<ul>
{links}
</ul>
</main></body>
</html>
""")


def baseline():
    os.makedirs(POOL, exist_ok=True)
    write_index()
    for n in range(1, CHILDREN + 1):
        write(page_path(n), GOOD.format(n=n))
    print(f"Baseline: all {CHILDREN + 1} pool pages load. Push, then run an audit.")


def brk(total, rate, timeout, nonlicensed, empty):
    success = round(total * rate / 100)
    fail = total - success
    special = timeout + nonlicensed + empty
    if fail > CHILDREN:
        raise SystemExit(f"Need {fail} failed pages but the pool only has {CHILDREN}. Use a higher --rate.")
    if special > fail:
        raise SystemExit(f"--timeout/--nonlicensed/--empty add up to {special}, more than the {fail} failed pages.")
    baseline_quiet()
    kinds = ["timeout"] * timeout + ["nonlicensed"] * nonlicensed + ["empty"] * empty
    kinds += ["notfound"] * (fail - special)
    # Break from the end of the pool so page-001… stay good.
    for n, kind in zip(range(CHILDREN, 0, -1), kinds):
        if kind == "notfound":
            os.remove(page_path(n))
        else:
            write(page_path(n), {"timeout": TIMEOUT, "nonlicensed": NONLICENSED, "empty": EMPTY}[kind])
    tier = "Full" if rate >= 80 else "Partial" if rate >= 50 else "Failed"
    print(f"Break: {fail} of {total} pages fail -> {success}/{total} = {success / total:.2%} -> expected {tier}.")
    print(f"  404: {fail - special}, time-out: {timeout}, non-licensed: {nonlicensed}, empty: {empty}")
    print("Push, then run the audit again.")


def baseline_quiet():
    os.makedirs(POOL, exist_ok=True)
    write_index()
    for n in range(1, CHILDREN + 1):
        write(page_path(n), GOOD.format(n=n))


def status():
    counts = {"good": 0, "notfound": 0, "timeout": 0, "nonlicensed": 0, "empty": 0}
    for n in range(1, CHILDREN + 1):
        p = page_path(n)
        if not os.path.exists(p):
            counts["notfound"] += 1
            continue
        body = open(p).read()
        kind = ("timeout" if body == TIMEOUT else "nonlicensed" if body == NONLICENSED
                else "empty" if body == EMPTY else "good")
        counts[kind] += 1
    print(counts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("baseline")
    sub.add_parser("status")
    b = sub.add_parser("break")
    b.add_argument("--total", type=int, required=True, help="Audited pages after the baseline audit")
    b.add_argument("--rate", type=float, required=True, help="success %% wanted")
    b.add_argument("--timeout", type=int, default=0)
    b.add_argument("--nonlicensed", type=int, default=0)
    b.add_argument("--empty", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "baseline":
        baseline()
    elif a.cmd == "status":
        status()
    else:
        brk(a.total, a.rate, a.timeout, a.nonlicensed, a.empty)
