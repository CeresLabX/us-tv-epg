#!/usr/bin/env python3
import urllib.request, re, concurrent.futures, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

SOURCES = [
    {"name": "iptv-org US", "url": "https://iptv-org.github.io/iptv/countries/us.m3u"},
    {"name": "Free-TV",     "url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"},
]
OUTPUT_PLAYLIST = "playlist.m3u"
OUTPUT_EPG      = "epg.xml"
MAX_WORKERS      = 32
VALIDATE_TIMEOUT = 6

REGION_LOCKED_KEYWORDS = [
    ' bbc ','bbc1','bbc2','itv1','channel 4','channel 5','tvp ','polsat','tvn ',
    'rai ','mediaset','canale 5','tf1','france 2','france 3','france 4','france 5','m6','arte ',
    'das erste','zdf','ard ','rte ','virgin media','channel 9','channel 7','channel 10',
    'nine network','ten ','abc australia','sbs australia','tvb ','atv ','rthk','now tv',
    'etv ','zee tv','star plus','colors tv','dubai','al jazeera','al arabiya','ansa',
    'cbc ','cbc news','global tv','citytv','tsn ','sportsnet ca','uk only','gb only','ukraine',
    'united kingdom','uk & ie','uk/ireland','australia only','canada only',
]
GEO_BLOCKED_DOMAINS = [
    'bbc.co.uk','bbc.com','channel4.com','itv.com','channel5.co.uk',
    'rte.ie','tv3.ie','abc.net.au','sbs.com.au','nine.com.au',
    'cbc.ca','ctv.ca','globaltv.com','tvb.com','now.com.hk','zee-tv.com','zee.zee',
]
GROUP_CONSOLIDATIONS = {
    'auto':'Lifestyle','cooking':'Lifestyle','travel':'Lifestyle','shop':'Lifestyle','relax':'Lifestyle',
    'science':'Education','weather':'News','animation':'Kids','family':'Kids',
    'classic':'Entertainment','legislative':'General',
}
REJECT_COUNTRY_GROUPS = {
    'italy','greece','hungary','russia','ukraine','belarus','czech republic','finland','argentina',
    'spain','france','germany','india','korea','netherlands','taiwan','albania','brazil','iraq',
    'egypt','estonia','bosnia and herzegovina','croatia','georgia','saudi arabia','sweden','austria',
    'japan','bulgaria','canada','latvia','lithuania','luxembourg','poland','portugal','serbia',
    'venezuela','costa rica','greenland','iceland','indonesia','israel','qatar','slovenia',
    'switzerland','azerbaijan','belgium','china','cyprus','denmark','iran','mexico','moldova',
    'montenegro','norway','romania','united arab emirates','united kingdom','uk','ireland',
    'north macedonia','turkey','chile','slovakia','faroe islands','dominican republic',
}
KEEP_GROUPS = {
    'general','local news','sports','entertainment','movies','series','news','kids','religious',
    'lifestyle','education','music','documentary','comedy','culture','business','outdoor',
    'pluto tv','plex','roku channel','samsung tv plus','tubi','pbs','pbs kids','usa',
}

def consolidate_group(g):
    if not g: return 'General'
    p = g.split(';')[0].strip()
    if not p or p.lower() == 'undefined': return 'General'
    return GROUP_CONSOLIDATIONS.get(p.lower(), p.title())

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
            group = consolidate_group(raw_grp) if raw_grp else 'General'
            if group.lower() in REJECT_COUNTRY_GROUPS: group = 'International'
            elif group.lower() not in KEEP_GROUPS and group.lower() not in ('general','undefined',''): group = 'International'
            lang = ''
            at = tvg_id.rfind('@')
            if at!=-1:
                s = tvg_id[at+1:].lower()
                lm={'english':'English','en':'English','spanish':'Spanish','es':'Spanish','french':'French','fr':'French',
                    'chinese':'Chinese','zh':'Chinese','korean':'Korean','ko':'Korean','arabic':'Arabic','ar':'Arabic',
                    'hindi':'Hindi','hi':'Hindi','portuguese':'Portuguese','pt':'Portuguese','german':'German','de':'German',
                    'italian':'Italian','it':'Italian','japanese':'Japanese','ja':'Japanese','russian':'Russian','ru':'Russian',
                    'vietnamese':'Vietnamese','vi':'Vietnamese','tagalog':'Tagalog','tl':'Tagalog','polish':'Polish','pl':'Polish',
                    'dutch':'Dutch','nl':'Dutch','turkish':'Turkish','tr':'Turkish','greek':'Greek','el':'Greek',
                    'hebrew':'Hebrew','he':'Hebrew','persian':'Persian','fa':'Persian'}
                lang = lm.get(s,'')
            chs.append({'name':clean,'id':tvg_id,'logo':tvg_logo,'group':group,'language':lang,'url':url,'raw_name':name,'source':src_name})
            i = j if j>i else i+1
        else: i+=1
    return chs

def is_us(ch):
    url, name = ch['url'].lower(), ch['raw_name'].lower()
    for d in GEO_BLOCKED_DOMAINS:
        if d in url: return False
    for kw in REGION_LOCKED_KEYWORDS:
        if kw in f' {name} ': return False
    return True

def is_en(ch):
    return ch.get('language','') not in {'Spanish','French','German','Italian','Portuguese','Chinese','Korean',
        'Hindi','Arabic','Japanese','Russian','Vietnamese','Tagalog','Polish','Dutch','Turkish',
        'Greek','Hebrew','Persian','Unknown'}

def validate(ch):
    try:
        req = urllib.request.Request(ch['url'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=VALIDATE_TIMEOUT) as r:
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
print("Multi-source US IPTV Playlist Builder")
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
print(f"\nTotal raw: {total_raw}")

seen={}
for ch,sn in all_raw:
    p=0 if 'iptv-org' in sn else 1
    if ch['url'] not in seen or p==0: seen[ch['url']]=(ch,sn,p)
deduped=[v[0] for v in seen.values()]
print(f"After URL dedup: {len(deduped)}")
deduped=[c for c in deduped if is_us(c)]
print(f"US-accessible: {len(deduped)}")
deduped=[c for c in deduped if is_en(c)]
print(f"English-language: {len(deduped)}")

print(f"Validating ({MAX_WORKERS} parallel)...")
valid,failed=[],[]
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs={ex.submit(validate,c):c for c in deduped}
    for fut in concurrent.futures.as_completed(futs):
        if fut.result(): valid.append(futs[fut])
        else: failed.append(futs[fut])
print(f"Passed: {len(valid)}, Failed: {len(failed)}")

fm={}
for c in valid:
    if c['url'] not in fm: fm[c['url']]=c
final=list(fm.values())
def sk(c):
    g=c['group'].lower()
    if 'local news' in g: return(0,g,c['name'])
    if 'sports'     in g: return(1,g,c['name'])
    if 'kids'       in g: return(2,g,c['name'])
    return(9,g,c['name'])
final.sort(key=sk)

write_m3u(final,OUTPUT_PLAYLIST)
print(f"Wrote {OUTPUT_PLAYLIST}")
tv=gen_epg(final)
with open(OUTPUT_EPG,'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    ET.ElementTree(tv).write(f,encoding='utf-8',xml_declaration=False)
print(f"Wrote {OUTPUT_EPG}")

if failed:
    with open('failed-streams.txt','w') as f:
        for c in failed: f.write(c['url']+'\n')

print(f"\n{'='*60}")
print("SUMMARY")
print(f"  Sources fetched:    {len(SOURCES)}")
print(f"  Total raw:         {total_raw}")
print(f"  Duplicates removed: {total_raw-len(final)}")
print(f"  Failed validation:  {len(failed)}")
print(f"  Final channels:    {len(final)}")
print(f"  Playlist: https://CeresLabX.github.io/us-tv/{OUTPUT_PLAYLIST}")
print(f"  EPG:      https://CeresLabX.github.io/us-tv/{OUTPUT_EPG}")
print(f"{'='*60}")
