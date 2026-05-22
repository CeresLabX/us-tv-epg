#!/usr/bin/env python3
"""
validate-streams.py
Validates all channels in a playlist.m3u and produces a log for Vectrix analysis.
Usage: python3 validate-streams.py [playlist.m3u]
Output: stream-validation-log.txt + failed-streams.txt + passed-streams.txt
"""
import sys, re, urllib.request, urllib.error, subprocess
from datetime import datetime

PLAYLIST = sys.argv[1] if len(sys.argv) > 1 else "playlist.m3u"
LOGFILE = "stream-validation-log.txt"
FAILED = "failed-streams.txt"
PASSED = "passed-streams.txt"
TIMEOUT = 15  # seconds per stream

def curl_head(url):
    """Returns (http_code, content_type, redirect_url, ok)"""
    try:
        proc = subprocess.run(
            ["curl", "-sI", "-L", "--max-time", str(TIMEOUT),
             "-w", "%{http_code}|%{content_type}|%{redirect_url}",
             "-o", "/dev/null", url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        out = proc.stdout.strip()
        if not out:
            return (0, "", "", False, "no response")
        parts = out.split("|")
        code = parts[0] if len(parts) > 0 else ""
        ctype = parts[1] if len(parts) > 1 else ""
        redirect = parts[2] if len(parts) > 2 else ""
        try:
            code_int = int(code)
        except:
            return (0, ctype, redirect, False, f"bad code: {code}")
        if code_int == 200:
            return (code_int, ctype, redirect, True, "ok")
        elif code_int in (301, 302):
            return (code_int, ctype, redirect, True, f"redirect ({code})")
        elif code_int in (404, 403, 400, 500, 502, 503):
            return (code_int, ctype, redirect, False, f"http {code_int}")
        else:
            return (code_int, ctype, redirect, False, f"http {code_int}")
    except subprocess.TimeoutExpired:
        return (0, "", "", False, "timeout")
    except Exception as e:
        return (0, "", "", False, str(e))

def parse_m3u(path):
    channels = []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # Get next non-blank, non-comment line as URL
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j += 1
            url = lines[j].strip() if j < len(lines) else ""
            if url.startswith("http"):
                attrs = line[8:line.rfind(",")] if "," in line else line[8:]
                name = line.rsplit(",", 1)[1].strip() if "," in line else ""
                tvg_id = (re.search(r'tvg-id="([^"]*)"', attrs) or type("",(),{"group":lambda s,*a:""})()).group(1) if re.search(r'tvg-id="([^"]*)"', attrs) else ""
                logo = (re.search(r'tvg-logo="([^"]*)"', attrs) or type("",(),{"group":lambda s,*a:""})()).group(1) if re.search(r'tvg-logo="([^"]*)"', attrs) else ""
                grp = (re.search(r'group-title="([^"]*)"', attrs) or type("",(),{"group":lambda s,*a:""})()).group(1) if re.search(r'group-title="([^"]*)"', attrs) else ""
                channels.append({"name": name, "id": tvg_id, "logo": logo, "group": grp, "url": url, "extinf": line})
            i = j if j > i else i + 1
        else:
            i += 1
    return channels

print(f"Reading: {PLAYLIST}")
channels = parse_m3u(PLAYLIST)
print(f"Found {len(channels)} channels")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

log_lines = []
log_lines.append("=" * 80)
log_lines.append(f"STREAM VALIDATION LOG — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_lines.append(f"Playlist: {PLAYLIST}")
log_lines.append(f"Total channels: {len(channels)}")
log_lines.append("=" * 80)
log_lines.append("")

failed_lines = []
passed_lines = []
fail_count = 0
pass_count = 0

for idx, ch in enumerate(channels):
    pct = (idx + 1) / len(channels) * 100
    sys.stdout.write(f"\r[{idx+1}/{len(channels)} ({pct:.1f}%)] {ch['name'][:40]:<40} ")

    code, ctype, redirect, ok, reason = curl_head(ch["url"])

    if ok:
        status = "PASS"
        pass_count += 1
        passed_lines.append(f"{ch['id']}|{ch['name']}|{ch['url']}|{code}|{ctype}")
    else:
        status = "FAIL"
        fail_count += 1
        failed_lines.append(f"{ch['id']}|{ch['name']}|{ch['group']}|{ch['url']}|{code}|{reason}")

    log_lines.append(f"[{status}] {ch['id']}")
    log_lines.append(f"  Name:   {ch['name']}")
    log_lines.append(f"  Group:  {ch['group']}")
    log_lines.append(f"  URL:    {ch['url']}")
    log_lines.append(f"  Result: HTTP {code} | {ctype} | {reason}")
    if redirect:
        log_lines.append(f"  → Redirect: {redirect}")
    log_lines.append("")

    sys.stdout.flush()

print()
print()
print(f"Results: {pass_count} passed, {fail_count} failed")

# Write logs
with open(LOGFILE, "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))
print(f"Full log: {LOGFILE}")

with open(FAILED, "w", encoding="utf-8") as f:
    f.write(f"# Failed streams — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"# Format: tvg-id|name|group|url|HTTP_code|reason\n")
    f.write("\n".join(failed_lines))
print(f"Failed channels: {FAILED} ({fail_count} entries)")

with open(PASSED, "w", encoding="utf-8") as f:
    f.write(f"# Passed streams — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"# Format: tvg-id|name|url|HTTP_code|content_type\n")
    f.write("\n".join(passed_lines))
print(f"Passed channels: {PASSED} ({pass_count} entries)")

print()
print("Done. Send these files to Vectrix for analysis:")
print(f"  1. {LOGFILE}")
print(f"  2. {FAILED}")
