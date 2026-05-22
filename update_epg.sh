#!/bin/bash
# Local rebuild script for us-tv repo
set -e
cd "$(dirname "$0")"

python3 - <<'PYEOF'
import urllib.request
req = urllib.request.Request('https://iptv-org.github.io/iptv/countries/us.m3u',
    headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as r:
    content = r.read().decode('utf-8')
with open('full_playlist.m3u', 'w', encoding='utf-8') as f:
    f.write(content.replace('\r\n', '\n').replace('\r', '\n'))
PYEOF

python3 generate_epg.py && cp epg.xml epg_full.xml
python3 build_filtered_playlist.py  # outputs playlist.m3u + epg.xml

echo "Done. Commit and push manually."
