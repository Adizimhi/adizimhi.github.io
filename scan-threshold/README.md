# AC-2997 scan-threshold pool

256 pages + an index (`pool/`), linked from `errors/index.html`, used to make audits Partial or Failed on purpose.

**Why two steps:** accessFlow only counts a page as failed if it was already known from an earlier audit.
A URL that fails the first time the crawler sees it is dropped (that's why the `errors/` pages never showed as failures).

## Flow

1. `python3 scan-threshold/scan_state.py baseline` → commit, push, wait for GitHub Pages, run an audit.
   Note **Audited pages** on the Dashboard (= `--total`).
2. `python3 scan-threshold/scan_state.py break --total <T> --rate <success %>` → commit, push, run the audit again.
3. Before the next scenario go back to step 1 (baseline + audit) so every pool page is known and good again.

| Scenario | Command (example with T = 400) | Expected |
|---|---|---|
| Full, 80% boundary | `break --total 400 --rate 80` (80 fail) | Full success |
| Partial, just under 80% | `break --total 400 --rate 79.75` (81 fail) | Partial |
| Partial, middle | `break --total 400 --rate 65` (140 fail) | Partial |
| Partial, 50% boundary | `break --total 400 --rate 50` (200 fail) | Partial |
| Failed, just under 50% | `break --total 400 --rate 49.75` (201 fail) | Failed |
| Failed with reasons | `break --total 400 --rate 40 --timeout 5 --nonlicensed 5 --empty 5` | Failed + reason list |

Broken pages are 404 by default (most reliable). Extra reasons:
- `--timeout`: page never finishes loading (each one costs about 60s of audit time).
- `--nonlicensed`: page redirects to example.com.
- `--empty`: only counted when the `aflwScannerEmptyContentFailure` flag is on.

GitHub Pages can't return 429, 403, 5xx, Cloudflare blocks or no response.

`python3 scan-threshold/scan_state.py status` shows the current state.
