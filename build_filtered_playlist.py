#!/usr/bin/env python3
"""
Multi-source US IPTV builder.
Sources: iptv-org US + iptv-org English + Free-TV/IPTV
With stream validation (parallel), URL dedup, group consolidation.

Free-TV channels only accepted if:
  - Channel group is a recognized KEEP group (News, Sports, etc.)
  - OR tvg-id has @English suffix
Otherwise rejected (prevents non-English country-channels from leaking in).
"""
import re, urllib.request, concurrent.futures
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import Counter

SOURCES = [
    {"name": "iptv-org US",     "url": "https://iptv-org.github.io/iptv/countries/us.m3u"},
    {"name": "iptv-org English","url": "https://iptv-org.github.io/iptv/languages/eng.m3u"},
    {"name": "Free-TV",         "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"},
]
OUTPUT_PLAYLIST = "playlist.m3u"
OUTPUT_EPG      = "epg.xml"
MAX_WORKERS      = 32

VOD_GROUPS = {
    'pluto tv':'Pluto TV','plex':'Plex','roku channel':'Roku Channel',
    'samsung tv plus':'Samsung TV Plus','tubi':'Tubi',
    'pbs':'PBS','pbs kids':'PBS Kids',
}
KEEP_GROUPS = {
    'general','local news','sports','entertainment','movies','series','news','kids','religious',
    'lifestyle','education','music','documentary','comedy','culture','business','outdoor',
    'pluto tv','plex','roku channel','samsung tv plus','tubi','pbs','pbs kids',
}
REJECT_GROUPS = {
    'auto','cooking','travel','shop','relax','science','weather','animation','family',
    'classic','legislative',
    'vod movies (en)','vod movies (es)','vod movies (fr)','vod movies (it)','vod movies (de)',
    'vod movies (pt)','vod movies (ru)','vod movies (kr)','vod movies (cn)','vod movies (jp)',
    'vod movies (in)','vod comedy','vod documentary','vod kids','vod series','vod action',
    'vod horror','vod thriller','vod romance','vod sci-fi','vod fantasy','vod drama',
    'vod anime','vod reality','vod western','vod classic','vod musical',
    'vod family','vod crime','vod mystery','vod war','vod history',
    'vod biography','vod short','vod film','vod music','vod sport',
    'usa vod','italy vod','spain vod','france vod','germany vod',
    'mexico vod','brazil vod','argentina vod','latin america vod',
}
GROUP_CONSOLIDATIONS = {
    'auto':'Lifestyle','cooking':'Lifestyle','travel':'Lifestyle','shop':'Lifestyle','relax':'Lifestyle',
    'science':'Education','weather':'News','animation':'Kids','family':'Kids',
    'classic':'Entertainment','legislative':'General',
}
EXTRA_CHANNELS = [
    {'name':'KGW 8 News Portland','id':'KGWDT1.us','logo':'','group':'Local News','language':'English',
     'url':'https://livevideo01.kgw.com/hls/live/2015506/elvs/live.m3u8','raw_name':'KGW 8 News Portland','source':'manual'},
]

def tvg_lang(tvg_id):
    if not tvg_id: return ''
    at = tvg_id.rfind('@')
    if at == -1: return ''
    s = tvg_id[at+1:].lower()
    lm={'english':'English','en':'English','spanish':'Spanish','es':'Spanish','french':'French','fr':'French',
        'chinese':'Chinese','zh':'Chinese','korean':'Korean','ko':'Korean','arabic':'Arabic','ar':'Arabic',
        'hindi':'Hindi','hi':'Hindi','portuguese':'Portuguese','pt':'Portuguese','german':'German','de':'German',
        'italian':'Italian','it':'Italian','japanese':'Japanese','ja':'Japanese','russian':'Russian','ru':'Russian',
        'vietnamese':'Vietnamese','vi':'Vietnamese','tagalog':'Tagalog','tl':'Tagalog','polish':'Polish','pl':'Polish',
        'dutch':'Dutch','nl':'Dutch','turkish':'Turkish','tr':'Turkish','greek':'Greek','el':'Greek',
        'hebrew':'Hebrew','he':'Hebrew','persian':'Persian','fa':'Persian'}
    return lm.get(s,'')

def is_english_tvg(tvg_id):
    return tvg_lang(tvg_id) == 'English'

def consolidate_group(g):
    if not g: return 'General'
    p = g.split(';')[0].strip()
    if not p or p.lower() == 'undefined': return 'General'
    pl = p.lower()
    if pl in REJECT_GROUPS: return None
    if pl in VOD_GROUPS: return VOD_GROUPS[pl]
    if pl not in KEEP_GROUPS: return 'International'
    return GROUP_CONSOLIDATIONS.get(pl, p.title())

def fetch_m3u(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; IPTVBuilder/1.0)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        cs = r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(cs, errors='replace').replace('\r\n','\n').replace('\r','\n')

def parse_m3u(content, src_name):
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

            # Free-TV: only accept if in KEEP group OR has English tvg-id suffix
            if 'free-tv' in src_name.lower():
                in_keep = raw_grp and raw_grp.lower() in KEEP_GROUPS
                has_en_tvg = is_english_tvg(tvg_id)
                if not in_keep and not has_en_tvg:
                    i = j if j>i else i+1; continue
                group = consolidate_group(raw_grp) if raw_grp else 'General'
                if group is None: i=j if j>i else i+1; continue
            else:
                group = consolidate_group(raw_grp) if raw_grp else 'General'
                if group is None: i=j if j>i else i+1; continue

            lang = tvg_lang(tvg_id)
            chs.append({'name':clean,'id':tvg_id,'logo':tvg_logo,'group':group,'language':lang,'url':url,'raw_name':name,'source':src_name})
            i = j if j>i else i+1
        else: i+=1
    return chs

def is_english(ch):
    return ch.get('language','') not in {'Spanish','French','German','Italian','Portuguese','Chinese','Korean',
        'Hindi','Arabic','Japanese','Russian','Vietnamese','Tagalog','Polish','Dutch','Turkish',
        'Greek','Hebrew','Persian','Unknown'}

def validate(ch):
    try:
        req = urllib.request.Request(ch['url'], headers={'User-Agent': 'Mozilla/5.0'}, method='HEAD')
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status in (200,206,301,302,303,304)
    except urllib.error.HTTPError as e:
        return e.code not in (403,404,500,502,503)
    except: return False

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

print("="*60)
all_raw=[]
for src in SOURCES:
    print(f"Fetching [{src['name']}]... ",end='',flush=True)
    try:
        content=fetch_m3u(src['url'])
        chs=parse_m3u(content,src['name'])
        print(f"{len(chs)} channels")
        all_raw.extend([(c,src['name']) for c in chs])
    except Exception as e:
        print(f"FAILED ({e})")

total_raw=len(all_raw)
print(f"\nTotal raw (after Free-TV filter): {total_raw}")

pri = {'iptv-org US': 0, 'iptv-org English': 1, 'Free-TV': 2}
seen={}
for ch,sn in all_raw:
    p=pri.get(sn,2)
    if ch['url'] not in seen or p < seen[ch['url']]['pri']:
        seen[ch['url']]={'ch':ch,'pri':p}
deduped=[v['ch'] for v in seen.values()]
print(f"After URL dedup: {len(deduped)}")

n_en=len(deduped)
deduped=[c for c in deduped if is_english(c)]
print(f"English-language: {n_en} -> {len(deduped)}")

print(f"\nValidating {len(deduped)} streams ({MAX_WORKERS} workers)...")
valid,failed=[],[]
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs={ex.submit(validate,c):c for c in deduped}
    for fut in concurrent.futures.as_completed(futs):
        if fut.result(): valid.append(futs[fut])
        else: failed.append(futs[fut])
print(f"Passed: {len(valid)}, Failed (VPN-blocked): {len(failed)}")
deduped=valid

fm={}
for c in deduped:
    if c['url'] not in fm: fm[c['url']]=c
deduped=list(fm.values())

eu={c['url'] for c in deduped}
added=[]
for ec in EXTRA_CHANNELS:
    if ec['url'] not in eu: deduped.append(ec); eu.add(ec['url']); added.append(ec['name'])
if added: print(f"Added extras: {', '.join(added)}")

def sk(c):
    g=c['group'].lower()
    if 'local news' in g: return(0,g,c['name'])
    if 'sports'     in g: return(1,g,c['name'])
    if 'kids'       in g: return(2,g,c['name'])
    return(9,g,c['name'])
deduped.sort(key=sk)

write_m3u(deduped,OUTPUT_PLAYLIST)
print(f"Wrote {OUTPUT_PLAYLIST}")
tv=gen_epg(deduped)
with open(OUTPUT_EPG,'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    ET.ElementTree(tv).write(f,encoding='utf-8',xml_declaration=False)
print(f"Wrote {OUTPUT_EPG}")

groups=Counter(c['group'] for c in deduped)
print(f"\nGroups ({len(groups)}):")
for g,cnt in groups.most_common(): print(f"  {g}: {cnt}")

multi=sum(1 for c in deduped if ';' in c.get('group',''))
print(f"\nMulti-group entries: {multi}")
print(f"\n{'='*60}")
print(f"Total raw: {total_raw}")
print(f"Final channels: {len(deduped)}")
print(f"Playlist: https://CeresLabX.github.io/us-tv/{OUTPUT_PLAYLIST}")
print(f"EPG:      https://CeresLabX.github.io/us-tv/{OUTPUT_EPG}")
print(f"{'='*60}")
