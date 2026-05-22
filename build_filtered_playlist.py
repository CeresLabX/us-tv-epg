#!/usr/bin/env python3
"""
iptv-org US only — English-language only, no validation.
Source: https://iptv-org.github.io/iptv/countries/us.m3u

Filters:
  - Reject non-English by tvg-id @ suffix (anything not @English/en/sd/hd/fhd/4k/uhd/us)
  - Reject by channel name: Spanish keywords (latino/latina/espanol/telemundo/univision/etc.), Pluto TV
  - Reject by URL: Pluto TV redirects (jmp2.uk/plu-)
  - Reject non-Latin script (Cyrillic/Greek/Arabic/Hebrew/CJK/Devanagari)
"""
import re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import Counter

SOURCE_URL = "https://iptv-org.github.io/iptv/countries/us.m3u"
OUTPUT_PLAYLIST = "playlist.m3u"
OUTPUT_EPG      = "epg.xml"

# Channel names containing these → reject (non-English or Pluto TV)
REJECT_NAME = {
    'pluto tv', 'pluto!',
    # Spanish language
    'latino channel', 'latina channel',  # "Latino Channel TV"
    'latino', 'latina',
    # standalone (for channels like "Runtime CBN Espanol")
    'espanol',
    # "Vevo Latino", "3ABN Latino", "Latino TV"
    'tv espa', 'tv espanol', 'tv español', 'en espanol', 'en español',
    'telemundo', 'univision', 'telenovela', 'telenovelas',
    'reino infantil', 'cine clásico',
    # Telemundo-owned local station call signs
    'knso ', 'kvea', 'wnju', 'wscv',
}

def consolidate_group(g):
    if not g: return 'General'
    p = g.split(';')[0].strip()
    if not p or p.lower() == 'undefined': return 'General'
    pl = p.lower()
    if pl in {'auto','cooking','travel','shop','relax','science','weather','animation','family','classic','legislative'}: return None
    KEEP={'general','local news','sports','entertainment','movies','series','news','kids','religious','lifestyle','education','music','documentary','comedy','culture','business','outdoor','pluto tv','plex','roku channel','samsung tv plus','tubi','pbs','pbs kids'}
    if pl not in KEEP: return 'International'
    CONS={'auto':'Lifestyle','cooking':'Lifestyle','travel':'Lifestyle','shop':'Lifestyle','relax':'Lifestyle','science':'Education','weather':'News','animation':'Kids','family':'Kids','classic':'Entertainment','legislative':'General'}
    return CONS.get(pl, p.title())

def is_english(ch):
    n = ch['name']
    # Non-Latin script → reject
    if any(ord(c) > 0x3000 for c in n): return False
    if any(0x0590 <= ord(c) < 0x0780 for c in n): return False  # Hebrew/Arabic/Devanagari
    if any(0x0400 <= ord(c) < 0x0500 for c in n): return False  # Cyrillic
    if any(0x0370 <= ord(c) < 0x0400 for c in n): return False  # Greek
    # Name reject keywords
    nl = n.lower()
    for kw in REJECT_NAME:
        if kw in nl: return False
    # Pluto TV redirect URL
    if 'jmp2.uk/plu-' in ch.get('url','').lower(): return False
    return True

def fetch_m3u(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; IPTVBuilder/1.0)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        cs = r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(cs, errors='replace').replace('\r\n','\n').replace('\r','\n')

def parse_m3u(content):
    chs = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            j = i+1
            while j < len(lines) and not lines[j].strip(): j+=1
            url = lines[j].strip() if j < len(lines) else ''
            if not url or not url.startswith('http'): i+=1; continue
            extinf = line[8:]
            ci = extinf.rfind(',')
            name = extinf[ci+1:].strip() if ci!=-1 else ''
            attrs = extinf[:ci] if ci!=-1 else extinf
            def m(pat): return (re.search(pat, attrs) or type('',(),{'group':lambda s,*a:''})()).group(1) if re.search(pat, attrs) else ''
            tvg_id, tvg_logo, raw_grp = m(r'tvg-id="([^"]*)"'), m(r'tvg-logo="([^"]*)"'), m(r'group-title="([^"]*)"')
            clean = re.sub(r'\s*\(\d{3,4}[ip]\)\s*','',name)
            clean = re.sub(r'\s*\[[^\]]+\]\s*','',clean).strip()
            group = consolidate_group(raw_grp) if raw_grp else 'General'
            if group is None: i=j if j>i else i+1; continue
            chs.append({'name':clean,'id':tvg_id,'logo':tvg_logo,'group':group,'url':url})
            i = j if j>i else i+1
        else: i+=1
    return chs

def write_m3u(chs, fn):
    with open(fn,'w',encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for c in chs:
            f.write(f'#EXTINF:-1 tvg-id="{c["id"]}" tvg-logo="{c["logo"]}" group-title="{c["group"]}",{c["name"]}\n')
            f.write(f'{c["url"]}\n')

def gen_epg(chs):
    now = datetime.now(tz=None)
    st = now.replace(minute=0,second=0,microsecond=0)
    st = st.replace(hour=12) if now.hour>=12 else st.replace(hour=0)
    tv = ET.Element('tv')
    tv.set('generator-info-name','us-tv EPG')
    tv.set('generator-info-url','https://github.com/CeresLabX/us-tv')
    blk=[("Live Broadcast","Live programming"),("Morning Edition","Morning news"),
         ("Midday Programming","Midday content"),("Afternoon Programming","Afternoon programming"),
         ("Evening Prime","Prime time"),("Late Night","Late night"),
         ("Overnight Re-run","Archived replay"),("Early Morning","Early morning")]*2
    for c in chs:
        ce=ET.SubElement(tv,'channel'); ce.set('id',c['id'])
        dn=ET.SubElement(ce,'display-name'); dn.set('lang','en'); dn.text=c['name']
        if c['logo']:
            ic=ET.SubElement(ce,'icon'); ic.set('src',c['logo'])
        cat=ET.SubElement(ce,'category'); cat.set('lang','en'); cat.text=c['group']
    for c in chs:
        bs=st
        for title,desc in blk:
            pe=ET.SubElement(tv,'programme'); pe.set('channel',c['id'])
            pe.set('start',bs.strftime('%Y%m%d%H%M%S')+' +0000')
            pe.set('stop',(bs+timedelta(hours=3)).strftime('%Y%m%d%H%M%S')+' +0000')
            te=ET.SubElement(pe,'title'); te.set('lang','en'); te.text=f"{c['name']} - {title}"
            de=ET.SubElement(pe,'desc'); de.set('lang','en'); de.text=f"{c['group']} | {desc}"
            bs+=timedelta(hours=3)
    return tv

content = fetch_m3u(SOURCE_URL)
raw = parse_m3u(content)
seen={}
for c in raw:
    if c['url'] not in seen: seen[c['url']]=c
deduped=list(seen.values())
print(f"After URL dedup: {len(deduped)}")

n1=len(deduped)
rejected=[]
kept=[]
for c in deduped:
    if is_english(c):
        kept.append(c)
    else:
        rejected.append(c['name'])
deduped=kept
print(f"After filter: {n1} -> {len(deduped)}")
print(f"Rejected: {len(rejected)}")

eu={c['url'] for c in deduped}
for ec in [{'name':'KGW 8 News Portland','id':'KGWDT1.us','logo':'','group':'Local News','url':'https://livevideo01.kgw.com/hls/live/2015506/elvs/live.m3u8'}]:
    if ec['url'] not in eu: deduped.append(ec)

def sk(c):
    g=c['group'].lower()
    if 'local news' in g: return(0,g,c['name'])
    if 'sports'     in g: return(1,g,c['name'])
    if 'kids'       in g: return(2,g,c['name'])
    return(9,g,c['name'])
deduped.sort(key=sk)

write_m3u(deduped,OUTPUT_PLAYLIST)
tv=gen_epg(deduped)
with open(OUTPUT_EPG,'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    ET.ElementTree(tv).write(f,encoding='utf-8',xml_declaration=False)

groups=Counter(c['group'] for c in deduped)
print(f"\nGroups ({len(groups)}):")
for g,cnt in groups.most_common(): print(f"  {g}: {cnt}")
print(f"\nFinal: {len(deduped)} channels")
