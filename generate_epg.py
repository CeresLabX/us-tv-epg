#!/usr/bin/env python3
"""
Generate EPG XML from iptv-org US M3U playlist.
Outputs XMLTV format for use in IPTV players like TiMATE.
"""

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import sys

M3U_URL = "https://iptv-org.github.io/iptv/countries/us.m3u"
OUTPUT_FILE = "epg.xml"

def fetch_m3u():
    req = urllib.request.Request(
        M3U_URL,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; TV EPG Generator)'}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        # Normalize CRLF -> LF
        raw = response.read().decode('utf-8', errors='replace')
        return raw.replace('\r\n', '\n').replace('\r', '\n')

def parse_m3u(content):
    channels = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            # Extract attributes and channel name
            # Format: #EXTINF:-1 tvg-id="..." tvg-logo="..." group-title="...",Channel Name
            extinf = line[8:]  # strip '#EXTINF:'
            # Find the channel name after the last comma
            comma_idx = extinf.rfind(',')
            channel_name = extinf[comma_idx+1:].strip() if comma_idx != -1 else ''
            extinf_attrs = extinf[:comma_idx] if comma_idx != -1 else extinf
            
            tvg_id = ''
            tvg_logo = ''
            group_title = ''
            
            # Parse tvg-id
            m = re.search(r'tvg-id="([^"]*)"', extinf_attrs)
            if m: tvg_id = m.group(1)
            m = re.search(r'tvg-logo="([^"]*)"', extinf_attrs)
            if m: tvg_logo = m.group(1)
            m = re.search(r'group-title="([^"]*)"', extinf_attrs)
            if m: group_title = m.group(1)
            
            # Get URL from next non-empty line
            j = i + 1
            url = ''
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
            
            if tvg_id and channel_name:
                channels.append({
                    'id': tvg_id,
                    'name': channel_name,
                    'logo': tvg_logo,
                    'category': group_title,
                    'url': url
                })
            i = j if j > i else i + 1
        else:
            i += 1
    
    return channels

def generate_epg(channels):
    """Generate XMLTV EPG with placeholder programmes for each channel."""
    now = datetime.utcnow()
    
    # Start from last hour boundary
    start_time = now.replace(minute=0, second=0, microsecond=0)
    if now.hour >= 12:
        start_time = start_time.replace(hour=12)
    else:
        start_time = start_time.replace(hour=0)
    
    tv = ET.Element('tv')
    tv.set('generator-info-name', 'iptv-org US EPG Generator')
    tv.set('generator-info-url', 'https://github.com/CeresLabX/us-tv-epg')
    
    # Add channels
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
            category = ET.SubElement(channel_el, 'category')
            category.set('lang', 'en')
            category.text = ch['category']
    
    # Add placeholder programmes (4 x 3-hour blocks = 12 hrs coverage)
    programme_blocks = [
        ("Live Stream", "Live broadcast programming"),
        ("News & Updates", "Current news and updates"),
        ("Entertainment", "Various entertainment content"),
        ("Live Stream", "Live broadcast programming"),
    ]
    
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
            
            category_el = ET.SubElement(prog, 'category')
            category_el.set('lang', 'en')
            category_el.text = ch['category'] or 'Entertainment'
            
            block_start = block_end
    
    return tv

def main():
    print(f"Fetching M3U playlist from {M3U_URL}...")
    content = fetch_m3u()
    
    print("Parsing channels...")
    channels = parse_m3u(content)
    print(f"Found {len(channels)} channels")
    
    if not channels:
        print("ERROR: No channels parsed from M3U!", file=sys.stderr)
        sys.exit(1)
    
    print("Generating EPG XML...")
    tv = generate_epg(channels)
    
    # Write with XML declaration
    tree = ET.ElementTree(tv)
    with open(OUTPUT_FILE, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='utf-8', xml_declaration=False)
    
    print(f"EPG written to {OUTPUT_FILE}")
    print(f"URL: https://CeresLabX.github.io/us-tv-epg/epg.xml")

if __name__ == '__main__':
    main()
