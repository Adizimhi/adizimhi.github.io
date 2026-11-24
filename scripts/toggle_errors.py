"""Generate the scan error scenario pages under errors/.

Usage:
  python3 scripts/toggle_errors.py healthy   # every error URL is a normal page (run an audit so the pages get added)
  python3 scripts/toggle_errors.py broken    # the same URLs now fail (404, empty, redirect, other domain, invalid domain, time-out)
"""
import os, sys, html
MODE = sys.argv[1] if len(sys.argv) > 1 else ""
if MODE not in ("healthy", "broken"):
    sys.exit(__doc__)
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "errors")
HEALTHY = MODE == "healthy"

def write(fn, content, title):
    path = os.path.join(root, fn)
    if HEALTHY:
        content = page(title, "", f"<main>\n<h1>{title}</h1>\n<p>This page is part of the scan error scenario set. It currently loads normally.</p>\n<p><a href=\"index.html\">Back to Scan Error Scenarios</a></p>\n</main>")
    with open(path, "w") as f:
        f.write(content)
os.makedirs(root, exist_ok=True)

def page(title, head_extra="", body=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{head_extra}</head>
<body>
{body}
</body>
</html>
"""

groups = []  # (heading, description, [(href, label)])

# 1. 404 - links to files that do not exist
items = [(f"notFound{i:02d}.html", f"Missing page {i:02d}") for i in range(1, 17)]
for fn, _ in items:
    p = os.path.join(root, fn)
    if HEALTHY:
        write(fn, "", f"Not Found {fn[8:10]}")
    elif os.path.exists(p):
        os.remove(p)
groups.append(("404 - Page not found", "Links to pages that do not exist on the server. GitHub Pages answers with a real HTTP 404.", items))

# 2. Empty content
items = []
for i in range(1, 6):
    fn = f"emptyFile{i:02d}.html"
    write(fn, "", f"Empty File {i:02d}")  # 0-byte file when broken
    items.append((fn, f"Zero-byte file {i:02d}"))
for i in range(1, 6):
    fn = f"emptyBody{i:02d}.html"
    write(fn, page(f"Empty Body {i:02d}"), f"Empty Body {i:02d}")
    items.append((fn, f"Empty body {i:02d}"))
groups.append(("Empty content", "Pages that return HTTP 200 with no content: zero-byte files and documents with an empty body.", items))

# 3. Client-side redirect inside the site
targets = ["../fieldLabelSuccess.html", "../emptyLinksFailures2.html", "../keyboardNavigationSuccess.html",
           "../backgroundImagesFailures.html", "../decorativeContentSuccess.html", "../searchFormTaggingFailures.html",
           "../navigationDiscernibleSuccess.html", "../interactiveTargetSizeFailures.html"]
methods = ["meta", "js-replace", "js-href", "meta-delay", "js-assign", "js-delay", "meta", "js-replace"]
items = []
def redirect_page(title, url, method):
    u = html.escape(url, quote=True)
    if method == "meta":
        head = f'<meta http-equiv="refresh" content="0; url={u}">\n'
        body = f"<h1>{title}</h1>"
    elif method == "meta-delay":
        head = f'<meta http-equiv="refresh" content="2; url={u}">\n'
        body = f"<h1>{title}</h1>\n<p>Redirecting...</p>"
    elif method == "js-replace":
        head = f'<script>window.location.replace("{url}");</script>\n'
        body = f"<h1>{title}</h1>"
    elif method == "js-href":
        head = ""
        body = f'<h1>{title}</h1>\n<script>window.location.href = "{url}";</script>'
    elif method == "js-assign":
        head = ""
        body = f'<h1>{title}</h1>\n<script>document.addEventListener("DOMContentLoaded", function () {{ window.location.assign("{url}"); }});</script>'
    else:  # js-delay
        head = ""
        body = f'<h1>{title}</h1>\n<p>Redirecting...</p>\n<script>setTimeout(function () {{ window.location.href = "{url}"; }}, 1500);</script>'
    return page(title, head, body)

for i, (t, m) in enumerate(zip(targets, methods), 1):
    fn = f"redirectInternal{i:02d}.html"
    write(fn, redirect_page(f"Internal Redirect {i:02d}", t, m), f"Internal Redirect {i:02d}")
    items.append((fn, f"In-page redirect {i:02d} ({m})"))
groups.append(("Redirect inside the page", "Pages that send the browser to another page of this site with a meta refresh or JavaScript, not a server redirect.", items))

# 4. Non-licensed domain - client-side redirect to another, real domain
ext = ["https://example.com/", "https://example.org/", "https://example.net/", "https://www.iana.org/help/example-domains",
       "https://www.w3.org/", "https://developer.mozilla.org/en-US/", "https://www.wikipedia.org/", "https://httpbin.org/html",
       "https://example.com/products/", "https://example.org/about/"]
emethods = ["meta", "js-replace", "js-href", "meta", "js-assign", "js-replace", "meta-delay", "js-href", "js-delay", "meta"]
items = []
for i, (t, m) in enumerate(zip(ext, emethods), 1):
    fn = f"nonLicensedDomain{i:02d}.html"
    write(fn, redirect_page(f"Non Licensed Domain {i:02d}", t, m), f"Non Licensed Domain {i:02d}")
    items.append((fn, f"Redirect to other domain {i:02d}"))
groups.append(("Non-licensed domain", "Pages that redirect (meta refresh or JavaScript) to a different domain that is not licensed for scanning.", items))

# 5. Invalid domain - redirect to hosts that can never resolve (.invalid TLD, RFC 2606)
bad = [f"https://scan-test-{i:02d}.invalid/" for i in range(1, 7)] + [
    "https://no-such-host.invalid/page.html", "https://adizimhi-missing.invalid/", "https://broken-link.invalid/", "https://nonexistent-subdomain.adizimhi.invalid/"]
imethods = ["meta", "js-replace", "js-href", "js-assign", "meta-delay", "js-delay", "meta", "js-replace", "js-href", "meta"]
items = []
for i, (t, m) in enumerate(zip(bad, imethods), 1):
    fn = f"invalidDomain{i:02d}.html"
    write(fn, redirect_page(f"Invalid Domain {i:02d}", t, m), f"Invalid Domain {i:02d}")
    items.append((fn, f"Redirect to unresolvable domain {i:02d}"))
groups.append(("Invalid domain", "Pages that redirect to domains that can never resolve in DNS (the reserved .invalid top-level domain).", items))

# 6. Timeouts
timeouts = [
    ("Infinite loop in head", "<script>while (true) {}</script>\n", "<h1>Timeout</h1>"),
    ("Infinite loop after load", "", '<h1>Timeout</h1>\n<script>window.addEventListener("load", function () { while (true) {} });</script>'),
    ("Blocking script from unreachable host", '<script src="https://10.255.255.1/never-loads.js"></script>\n', "<h1>Timeout</h1>"),
    ("Stylesheet from unreachable host", '<link rel="stylesheet" href="https://10.255.255.1/never-loads.css">\n<script src="https://10.255.255.2/never-loads.js"></script>\n', "<h1>Timeout</h1>"),
    ("Endless network requests", "", '<h1>Timeout</h1>\n<script>\nfunction poll() { fetch("https://10.255.255.1/poll?" + Date.now()).catch(function () {}).finally(function () { setTimeout(poll, 50); }); }\nfor (var i = 0; i < 6; i++) { poll(); }\n</script>'),
    ("Endless synchronous work", "", '<h1>Timeout</h1>\n<script>\nvar start = Date.now();\nwhile (Date.now() - start < 600000) { Math.sqrt(Math.random()); }\n</script>'),
]
items = []
for i, (label, head, body) in enumerate(timeouts, 1):
    fn = f"timeout{i:02d}.html"
    write(fn, page(f"Timeout {i:02d}", head, body), f"Timeout {i:02d}")
    items.append((fn, f"Timeout {i:02d}: {label}"))
groups.append(("Time-out", "Pages that never finish loading: blocked main thread or requests to an address that never answers.", items))

# hub
sections = []
total = 0
for heading, desc, its in groups:
    total += len(its)
    lis = "\n".join(f'      <li><a href="{h}">{html.escape(l)}</a></li>' for h, l in its)
    sections.append(f"""  <section>
    <h2>{heading} ({len(its)})</h2>
    <p>{desc}</p>
    <ul>
{lis}
    </ul>
  </section>""")
hub = page("Scan Error Scenarios", "<style>body{font-family:Arial,sans-serif;margin:24px}section{margin-bottom:24px}</style>\n",
           f"""<main>
  <h1>Scan Error Scenarios</h1>
  <p><a href="../index.html">Back to Rule Library</a></p>
  <p>{total} pages that should fail to scan, used to test partial-scan thresholds.</p>
{chr(10).join(sections)}
</main>""")
open(os.path.join(root, "index.html"), "w").write(hub)
print(MODE, "- error urls:", total)
