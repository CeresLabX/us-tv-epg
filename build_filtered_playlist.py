#!/usr/bin/env python3
"""
Build a filtered US-accessible, English-language IPTV playlist from iptv-org US data.
Outputs:
  - custom_playlist.m3u  (filtered playlist)
  - epg.xml             (EPG for filtered channels only)
"""

import urllib.request
import xml.etree.ElementTree as ET
import re
import sys
from datetime import datetime, timedelta

M3U_URL = "https://iptv-org.github.io/iptv/countries/us.m3u"
PLAYLIST_OUT = "playlist.m3u"
EPG_OUT = "epg.xml"

# ---- Language detection ----
KNOWN_ENGLISH_KEYWORDS = {
    # Explicitly English-tagged
    'english', 'en',
    # Channel name keywords suggesting English content
    'english', ' news', ' tv', ' channel', ' network', ' live',
    ' family', ' movie', ' sports', ' music', ' entertainment',
    ' comedy', ' drama', ' series', ' life', ' plus', ' world',
    ' america', ' us ', ' usa ', ' united states',
    ' abc', ' cbs', ' nbc', ' fox', ' pbs', ' cw', ' ion',
    ' abc news', ' cbs news', ' nbc news', ' fox news',
    ' bbc',  # BBC World is often accessible in US
    ' cnn', ' msnbc', ' tbs', ' tnt', ' usa network', ' syfy',
    ' amc', ' hbo', ' showtime', ' starz', ' cinemax',
    ' espn', ' fox sports', ' nbcs sports', ' tnt sports',
    ' discovery', ' history', ' national geographic', ' animal planet',
    ' food network', ' hgtv', ' travel channel', ' tlc',
    ' nickelodeon', ' cartoon network', ' disney', ' sesame',
    ' weather', ' accuweather',
    # Common US local/regional
    ' wbal', ' wabc', ' wnbc', ' kabc', ' kcra', ' ktla',
    ' wfxg', ' wjla', ' wcvb', ' wmar', ' kmgh', ' ksdk',
    ' whio', ' whdh', ' wsaz', ' wthr', ' wltx', ' ksat',
    ' wtvh', ' ksdk', ' khou', ' kgun', ' kvoa',
    ' local', ' news', ' weather',
}

# Keywords that strongly suggest NON-US or region-locked content
REGION_LOCKED_KEYWORDS = [
    # Country-specific
    ' bbc ', ' bbc1', ' bbc2', ' itv1', ' channel 4', ' channel 5',
    ' sky uk', ' sky news uk', ' bt sport', ' eurosport uk',
    ' tvp ', ' polsat', ' tvn ',
    ' rai ', ' mediaset', ' canale 5',
    ' tf1', ' france 2', ' france 3', ' france 4', ' france 5',
    ' m6', ' arte ',
    ' das erste', ' zdf', ' ard ',
    ' rte ', ' virgin media',
    ' channel 9', ' channel 7', ' channel 10', ' nine network',
    ' ten ', ' abc australia', ' sbs australia',
    ' tvb ', ' atv ', ' rthk', ' now tv',
    ' etv ', ' zee tv', ' star plus', ' colors tv',
    ' dubai', ' al jazeera', ' al arabiya',  # Middle East - often geo'd
    'ansa',
    # Canada
    ' cbc ', ' cbc news', ' global tv', ' citytv',
    ' tsn ', ' sportsnet ca',
    # UK/Europe specific
    ' uk only', 'gb only', ' ukraine',
    # Generic indicators of region lock
    'united kingdom', 'uk & ie', 'uk/ireland',
    'australia only', 'canada only',
]

# ---- Group consolidation ----
GROUP_CONSOLIDATIONS = {
    # Merge smaller groups into larger parent categories
    'auto': 'Lifestyle',
    'cooking': 'Lifestyle',
    'travel': 'Lifestyle',
    'shop': 'Lifestyle',
    'relax': 'Lifestyle',
    'science': 'Education',
    'weather': 'News',
    'animation': 'Kids',
    'family': 'Kids',
    'classic': 'Entertainment',
    'legislative': 'General',
    # Undefined stays as-is (channels with no group-title attr)
}


def consolidate_group(group):
    """Consolidate a group name, taking first semicolon-separated value."""
    if not group:
        return 'General'
    # Take only the first group (some channels have "General;Religious")
    primary = group.split(';')[0].strip()
    if not primary or primary.lower() == 'undefined':
        return 'General'
    return GROUP_CONSOLIDATIONS.get(primary.lower(), primary)


# Channels known to be explicitly geo-blocked to non-US regions (by URL/domain inference)
KNOWN_GEO_BLOCKED_DOMAINS = [
    'bbc.co.uk', 'bbc.com',  # BBC iPlayer is UK-only
    'channel4.com', 'itv.com', 'channel5.co.uk',
    'rte.ie', 'tv3.ie',
    'abc.net.au', 'sbs.com.au', 'nine.com.au',
    'cbc.ca', 'ctv.ca', 'globaltv.com',
    'tvb.com', 'now.com.hk',
    'zee-tv.com', 'zee.zee',
]


def fetch_m3u():
    req = urllib.request.Request(M3U_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8').replace('\r\n', '\n')


def parse_channels(content):
    channels = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            url = lines[j].strip() if j < len(lines) else ''

            extinf = line[8:]
            comma_idx = extinf.rfind(',')
            channel_name = extinf[comma_idx+1:].strip() if comma_idx != -1 else ''
            extinf_attrs = extinf[:comma_idx] if comma_idx != -1 else extinf

            tvg_id = re.search(r'tvg-id="([^"]*)"', extinf_attrs)
            tvg_id = tvg_id.group(1) if tvg_id else ''
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', extinf_attrs)
            tvg_logo = tvg_logo.group(1) if tvg_logo else ''
            group_title_raw = re.search(r'group-title="([^"]*)"', extinf_attrs)
            group_title_raw = group_title_raw.group(1) if group_title_raw else ''
            group_title = consolidate_group(group_title_raw)

            # Clean name
            clean_name = re.sub(r'\s*\(\d{3,4}[ip]\)\s*', '', channel_name)
            clean_name = re.sub(r'\s*\[[^\]]+\]\s*', '', clean_name).strip()

            # Language from tvg-id suffix
            language = ''
            at_idx = tvg_id.rfind('@')
            if at_idx != -1:
                suffix = tvg_id[at_idx+1:].lower()
                if suffix in {'english', 'en', 'spanish', 'es', 'french', 'fr',
                              'chinese', 'zh', 'korean', 'ko', 'arabic', 'ar',
                              'hindi', 'hi', 'portuguese', 'pt', 'german', 'de',
                              'italian', 'it', 'japanese', 'ja', 'russian', 'ru',
                              'vietnamese', 'vi', 'tagalog', 'tl', 'polish', 'pl',
                              'dutch', 'nl', 'turkish', 'tr', 'greek', 'el',
                              'hebrew', 'he', 'persian', 'fa'}:
                    language = suffix.title()

            # Detect language from name keywords
            name_lower = channel_name.lower()
            if not language:
                if any(f' {kw} ' in f' {name_lower} ' or name_lower.startswith(kw) or name_lower.endswith(kw)
                       for kw in ['english', 'español', 'français', 'french', '中文', '한국어',
                                  'हिंदी', 'हिन्दी', 'العربية', 'português', 'italiano',
                                  'deutsch', 'espana', 'india', 'arabic']):
                    language = 'Unknown'
                elif any(kw in name_lower for kw in KNOWN_ENGLISH_KEYWORDS):
                    language = 'English'

            channels.append({
                'name': clean_name,
                'id': tvg_id,
                'logo': tvg_logo,
                'category': group_title,
                'language': language,
                'url': url,
                'raw_name': channel_name,
            })
            i = j if j > i else i + 1
        else:
            i += 1
    return channels


def is_english(ch):
    lang = ch.get('language', '')
    if lang in ('English', 'Spanish', 'French', 'German', 'Italian',
                 'Portuguese', 'Chinese', 'Korean', 'Hindi', 'Arabic',
                 'Japanese', 'Russian', 'Vietnamese', 'Tagalog', 'Polish',
                 'Dutch', 'Turkish', 'Greek', 'Hebrew', 'Persian', 'Unknown'):
        return False
    # If language is set and not one of the clearly non-English, lean toward English
    if lang and lang not in ('Spanish', 'French', 'German', 'Italian', 'Portuguese',
                              'Chinese', 'Korean', 'Hindi', 'Arabic', 'Japanese',
                              'Russian', 'Vietnamese', 'Tagalog', 'Polish', 'Dutch',
                              'Turkish', 'Greek', 'Hebrew', 'Persian'):
        return True
    return True  # Default: include


def is_us_accessible(ch):
    url = ch.get('url', '').lower()
    name_lower = ch.get('raw_name', '').lower()

    # Check for known geo-blocked domains
    for domain in KNOWN_GEO_BLOCKED_DOMAINS:
        if domain in url:
            return False

    # Check for region-locked keywords in name
    for kw in REGION_LOCKED_KEYWORDS:
        if kw in f' {name_lower} ':
            return False

    return True


def write_m3u(channels, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for ch in channels:
            attrs = f'tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["category"]}"'
            f.write(f'#EXTINF:-1 {attrs},{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')


def generate_epg(channels):
    now = datetime.utcnow()
    start_time = now.replace(minute=0, second=0, microsecond=0)
    if now.hour >= 12:
        start_time = start_time.replace(hour=12)
    else:
        start_time = start_time.replace(hour=0)

    tv = ET.Element('tv')
    tv.set('generator-info-name', 'US-Accessible IPTV EPG')
    tv.set('generator-info-url', 'https://github.com/CeresLabX/us-tv-epg')

    programme_blocks = [
        ("Live Broadcast", "Live programming stream"),
        ("Morning Edition", "News and current events"),
        ("Midday Entertainment", "Variety and entertainment content"),
        ("Afternoon Programming", "General programming"),
        ("Evening Prime", "Prime time entertainment"),
        ("Late Night", "Late night programming"),
        ("Overnight Re-run", "Archived programming replay"),
        ("Early Morning", "Early morning programming"),
        ("Live Broadcast", "Live programming stream"),
        ("Morning Edition", "News and current events"),
        ("Midday Entertainment", "Variety and entertainment content"),
        ("Afternoon Programming", "General programming"),
        ("Evening Prime", "Prime time entertainment"),
        ("Late Night", "Late night programming"),
        ("Overnight Re-run", "Archived programming replay"),
        ("Early Morning", "Early morning programming"),
    ]

    for ch in channels:
        channel_el = ET.SubElement(tv, 'channel')
        channel_el.set('id', ch['id'])
        display_name = ET.SubElement(channel_el, 'display-name')
        display_name.set('lang', 'en')
        display_name.text = ch['name']
        if ch['logo']:
            icon = ET.SubElement(channel_el, 'icon')
            icon.set('src', ch['logo'])
        if ch['category']:
            cat = ET.SubElement(channel_el, 'category')
            cat.set('lang', 'en')
            cat.text = ch['category']

    for ch in channels:
        block_start = start_time
        for title, desc in programme_blocks:
            block_end = block_start + timedelta(hours=3)
            prog = ET.SubElement(tv, 'programme')
            prog.set('channel', ch['id'])
            prog.set('start', block_start.strftime('%Y%m%d%H%M%S') + ' +0000')
            prog.set('stop', block_end.strftime('%Y%m%d%H%M%S') + ' +0000')
            title_el = ET.SubElement(prog, 'title')
            title_el.set('lang', 'en')
            title_el.text = f"{ch['name']} - {title}"
            desc_el = ET.SubElement(prog, 'desc')
            desc_el.set('lang', 'en')
            desc_el.text = f"{ch['category']} | {desc}" if ch['category'] else desc
            block_start = block_end

    return tv


def main():
    print(f"Fetching {M3U_URL}...")
    content = fetch_m3u()

    print("Parsing channels...")
    channels = parse_channels(content)
    print(f"Total channels parsed: {len(channels)}")

    # Filter: US accessible + likely English
    us_accessible = [ch for ch in channels if is_us_accessible(ch)]
    print(f"US-accessible: {len(us_accessible)}")

    english_channels = [ch for ch in us_accessible if is_english(ch)]
    print(f"English-language: {len(english_channels)}")

    # Deduplicate by tvg-id
    seen = set()
    unique = []
    for ch in english_channels:
        if ch['id'] not in seen:
            seen.add(ch['id'])
            unique.append(ch)

    print(f"Unique channels: {len(unique)}")

    print(f"\nWriting playlist to {PLAYLIST_OUT}...")
    write_m3u(unique, PLAYLIST_OUT)

    print(f"Generating EPG to {EPG_OUT}...")
    tv = generate_epg(unique)
    tree = ET.ElementTree(tv)
    with open(EPG_OUT, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='utf-8', xml_declaration=False)

    print("\nDone.")
    print(f"  Playlist: https://CeresLabX.github.io/us-tv-epg/{PLAYLIST_OUT}")
    print(f"  EPG:      https://CeresLabX.github.io/us-tv-epg/{EPG_OUT}")


if __name__ == '__main__':
    main()
