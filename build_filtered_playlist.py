#!/usr/bin/env python3
"""
iptv-org US only — English-language only, no validation.
Source: https://iptv-org.github.io/iptv/countries/us.m3u

Filters:
  - Reject non-English by tvg-id @ suffix (anything not @English/en/sd/hd/fhd/4k/uhd/us)
  - Reject by channel name: Spanish keywords, Pluto TV
  - Reject by URL: dead streams from US validation (154 channels) + Pluto TV redirects
  - Reject non-Latin script (Cyrillic/Greek/Arabic/Hebrew/CJK/Devanagari)
"""
import re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import Counter

SOURCE_URL = "https://iptv-org.github.io/iptv/countries/us.m3u"
OUTPUT_PLAYLIST = "playlist.m3u"
OUTPUT_EPG      = "epg.xml"

# Channel names containing these -> reject (non-English or Pluto TV)
REJECT_NAME = {
    'pluto tv', 'pluto!',
    # Spanish language
    'latino channel', 'latina channel',
    'latino', 'latina', 'espanol',
    'tv espa', 'tv espanol', 'tv español', 'en espanol', 'en español',
    'telemundo', 'univision', 'telenovela', 'telenovelas',
    'reino infantil', 'cine clásico',
    # Telemundo-owned local station call signs
    'knso ', 'kvea', 'wnju', 'wscv',
}

# === PERMANENTLY BLOCKED URLS ===
# Channels that FAILED US validation (from failed-streams.txt, May 21 2026)
# Format: lowercase URLs from PowerShell validation run on US machine
REJECT_URLS = {
    # Sports - 404 / timeout
    'http://tdo@origin.thetvapp.to/hls/espn-deportes/mono.m3u8',
    'https://d2w9q46ikgrcwx.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-of5cbk3sav3w5/v1/sysdata_s_p_a_fifa_7/samsungheadend_us/latest/main/hls/playlist.m3u8',
    'https://d3d85c7qkywguj.cloudfront.net/scheduler/schedulemaster/263.m3u8',
    'https://cors-proxy.cooks.fyi/http://23.237.104.106:8080/usa_fox_deportes/index.m3u8',
    'https://tvpass.org/live/msg-plus/hd',
    'https://d4whmvwm0rdvi.cloudfront.net/10007/99993008/hls/master.m3u8?ads.xumo_channelid=99993008',
    'https://aegis-cloudfront-1.tubi.video/b474c2bb-b34d-4c53-a94b-c4ffe884563c/playlist.m3u8',
    'https://cdn-ue1-prod.tsv2.amagi.tv/linear/amg01444-tennischannelth-tennischannelnl-samsungnl/playlist.m3u8',
    'https://2-fss-2.streamhoster.com/pl_118/204972-2205186-1/playlist.m3u8',
    # Kids
    'https://dmr1h4skdal9h.cloudfront.net/playlist.m3u8',
    'https://tvpass.org/live/disneychanneleast/hd',
    'http://23.237.104.106:8080/usa_disney_junior/index.m3u8',
    'http://23.237.104.106:8080/usa_disney_xd/index.m3u8',
    'http://23.237.104.106:8080/usa_nickelodeon/index.m3u8',
    'https://stream-us-east-1.getpublica.com/cl/260415d7g24jv4hnf3ahfafgog/318x234_424101_3_f.m3u8?i=513_2256',
    # Business
    'https://86fdc85a.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/tectz2jfbgxvb21izwvyb3Jpz2luYWxzx0hmuw/playlist.m3u8',
    # Comedy
    'http://23.237.104.106:8080/usa_comedy_central/index.m3u8',
    'https://comedydynamics-plex-ingest.cinedigm.com/playlist.m3u8',
    'https://aegis-cloudfront-1.tubi.video/54f95462-b44d-4c99-b74b-af49467454fa/playlist.m3u8',
    'https://d4whmvwm0rdvi.cloudfront.net/10007/99993017/hls/master.m3u8?ads.xumo_channelid=99993017',
    'http://190.2.212.209:8050/play/a0q4',
    # Culture
    'https://2nbyjjx7y53k-hls-live.5centscdn.com/cls040318/b0d2763968fd0bdd2dc0d44ba2abf9ce.sdp/playlist.m3u8',
    'https://pemirateshls.persiana.live/hls/stream.m3u8',
    'https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/flowers_nim_https/050522/flowers/playlist.m3u8',
    'https://fox-foxsoul-samsungus.amagi.tv/playlist.m3u8',
    'http://103.154.3.101:5001/live/960.m3u8',
    'http://103.154.3.101:5001/live/961.m3u8',
    'http://103.154.3.101:5001/live/959.m3u8',
    # Documentary
    'https://9e754fa707344ccca6d84955c8fcaf36.mediatailor.us-east-1.amazonaws.com/v1/master/44f73ba4d03e9607dcd9bebdcb8494d86964f1d8/rlaxxtv-eu_authentichistory/playlist.m3u8',
    'https://eb3933ec.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/um9ydv9dcml0zti2mf9itfs/playlist.m3u8',
    'https://d1si3n1st4nkgb.cloudfront.net/10502/88896029/hls/master.m3u8?ads.xumo_channelid=88896029',
    'https://ef79b15c8c7c46c7a9de9d33001dbd07.mediatailor.us-west-2.amazonaws.com/v1/master/ba62fe743df0fe93366eba3a257d792884136c7f/linear-859-documentaryplus-documentaryplus/mt/documentaryplus/859/hls/master/playlist.m3u8',
    'https://docurama-plex-ingest.cinedigm.com/playlist.m3u8',
    'https://api.v3.invintus.com/streamuri/persis/2147483647/ktoo360tv.stream/media.m3u8',
    'https://d3serb1fmh623s.cloudfront.net/playlist.m3u8',
    # Education - PBS regional (403)
    'https://ketsdt.lls.pbs.org/out/v1/03c094dbd7874a4a8c3fe9fb10081bdb/index.m3u8',
    'https://s3-us-west-2.amazonaws.com/beverly-hills-high-school.castus-vod/live/ch1/video.m3u8',
    'https://khetdt.lls.pbs.org/out/v1/7ec7903413294b72bb64f83963d8ea9b/index.m3u8',
    'https://kuondt.lls.pbs.org/out/v1/91d8b5ffc5c1453c8a621508a07749a6/index.m3u8',
    'http://147.174.13.196/live/live.m3u8',
    # Entertainment
    'https://stream.ads.ottera.tv/playlist.m3u8?network_id=1544',
    'https://d1h1d6qoy9vnra.cloudfront.net/v1/master/9d062541f2ff39b5c0f48b743c6411d25f62fc25/freebie-plex/187.m3u8',
    'https://stream.ads.ottera.tv/cl/260421d7jmp97108ighs2i413g/1280x720_2300000_0_f.m3u8?i=475_567',
    'https://linear-59.frequency.stream/dist/plex/59/hls/master/playlist.m3u8',
    'https://cdn-unified-hls.streamspot.com/ingest1/4b4d895dd6/playlist.m3u8?origin=1',
    'http://txc4-swbb-mn.fibernet-tv.com/kaby-cw-2364/index.m3u8',
    'https://tvpass.org/live/logoeast/hd',
    'https://linear-10.frequency.stream/dist/stirr/10/hls/master/playlist.m3u8',
    'https://linear-142.frequency.stream/dist/24i/142/hls/master/playlist.m3u8',
    'https://tixbolt.com/royaltv/index.fmp4.m3u8',
    'https://sh7hls.wns.live/hls/stream.m3u8',
    'https://haititivi.com/haiti/telemix1/index.m3u8',
    # General
    'https://fuel-streaming-prod01.fuelmedia.io/v1/sem/e48409e7-672d-42f2-b5e0-ebb6744b0425.m3u8',
    'https://live.field59.com/wrde/wrde1/playlist.m3u8',
    'https://reflect-creatv.cablecast.tv/live-19/live/live.m3u8',
    'https://pubads.g.doubleclick.net/ssai/event/1kithngwtque54njjbiitgg/master.m3u8',
    'https://livechannel.mdc.akamaized.net/stitch/livechannel/1342/master1400000.m3u8;session=live_stream_1342',
    'https://tvpass.org/live/abc-kabc-los-angeles-ca/sd',
    'https://tvpass.org/live/cbs-kcbs-los-angeles-ca/hd',
    'https://fuel-streaming-prod01.fuelmedia.io/v1/sem/c4067ddc-0e67-4928-b7ec-624481f721a6.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889711/hls/master.m3u8?ads.xumo_channelid=88889711a&ads.xumo_ifatype=&ads.xumo_providerid=3822&ads.xumo_providername=nbcnba',
    'https://stream-losangeles.scientology.org/master.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889706/hls/master.m3u8?ads.xumo_channelid=88889706a&ads.xumo_ifatype=&ads.xumo_providerid=3831&ads.xumo_providername=nbcndal',
    'https://live8fd.lakewood.org/live-2/live/live.m3u8',
    'https://reflect-live-lawndale.cablecast.tv/live-4/live/live.m3u8',
    'https://ch8.littletongov.org/live-2/live/live.m3u8',
    'https://685c08ed6d81a.streamlock.net/live/mp4:mctv_aac/playlist.m3u8',
    'https://live-manifest.production-public.tubi.io/live/e7be5ad5-9044-4151-95d4-a9aae10ab0a5/playlist.m3u8',
    'https://pubads.g.doubleclick.net/ssai/event/kpannrcbq5kwdnv3hag3wog/master.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889704/hls/master.m3u8?ads.xumo_channelid=88889704a&ads.xumo_ifatype=&ads.xumo_providerid=3818&ads.xumo_providername=nbcnchi',
    'https://live.field59.com/wlio/wlio1/playlist.m3u8',
    'https://wnjtdt.lls.pbs.org/out/v1/e62efd8d4f92403996425fc389df0ffd/index.m3u8',
    'https://2-fss-1.streamhoster.com/pl_122/202676-1357858-1/playlist.m3u8',
    'https://cdn3.wowza.com/5/cxrdyrhf0zkxn0k2/pinole/g0032_002/playlist.m3u8',
    'https://rfdtv-jw.cdn.vustreams.com/live/7cba1a3b-318a-4097-8492-374478370b91/live.isml/7cba1a3b-318a-4097-8492-374478370b91.m3u8',
    'https://reflect-scvtv.cablecast.tv/live-2/live/live.m3u8',
    'https://stream6.scientology.org/master.m3u8',
    'http://23.237.104.106:8080/usa_showtime/index.m3u8',
    'http://23.237.104.106:8080/usa_starz/index.m3u8',
    'https://6305c8676ce84.streamlock.net/live/live/playlist.m3u8',
    'https://reflector.watchtstv.com/hls/livestream.m3u8',
    'https://amg00206-amg00206c1-distrotv-us-6886.playouts.now.amagi.tv/24-25-6886.m3u8',
    'https://bcovlive-a.akamaihd.net/rce33d845cb9e42dfa302c7ac345f7858/ap-northeast-1/6282251407001/playlist.m3u8',
    'https://maxtvhls.wns.live/hls/stream.m3u8',
    'https://amg01312-cw-amg01312c15-firetv-us-3444.playouts.now.amagi.tv/playlist.m3u8',
    'https://0888934ec1a5.us-east-1.playback.live-video.net/api/video/v1/us-east-1.289485033693.channel.aeaac0zpvcaz.m3u8',
    'https://cdn-unified-hls.streamspot.com/ingest1/8b0796adaf/playlist.m3u8?origin=1',
    'https://vallejo.cablecast.tv/live-3/live/live.m3u8',
    'https://vdopanel.jlahozconsulting.com:3407/hybrid/play.m3u8',
    'https://dai.google.com/linear/hls/event/hz3jdlvcq463l3b1blxmmq/master.m3u8',
    'https://livestream.pbskids.org/out/v1/1e3d77b418ad4a819b3f4c80ac0373b5/est_124.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889713/hls/master.m3u8?ads.xumo_channelid=88889713a&ads.xumo_ifatype=&ads.xumo_providerid=3820&ads.xumo_providername=nbcbos',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889705/hls/master.m3u8?ads.xumo_channelid=88889705a&ads.xumo_ifatype=&ads.xumo_providerid=3819&ads.xumo_providername=nbcphi',
    'https://stream-tampa.scientology.org/master.m3u8',
    'https://cdn-unified-hls.streamspot.com/ingest1/c7956aac88/playlist.m3u8?origin=1',
    'http://23.237.104.106:8080/usa_wgn/index.m3u8',
    'https://witn.cablecast.tv/live-4/live/live.m3u8',
    'https://e5.thetvapp.to/hls/metv-wjlp-new-jerseynew-york/index.m3u8',
    'https://dai.google.com/linear/hls/event/rdmbn03grcolng1eetekhg/master.m3u8',
    'http://d029dcec.kazmazpaz.ru/iptv/gvr4v8hyagbs5v/1098/manifest.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889709/hls/master.m3u8?ads.xumo_channelid=88889709a&ads.xumo_ifatype=&ads.xumo_providerid=3816&ads.xumo_providername=nbcny',
    'https://tvpass.org/live/wnet/hd',
    'https://e1.thetvapp.to/hls/wpix/index.m3u8',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889708/hls/master.m3u8?ads.xumo_channelid=88889708a&ads.xumo_ifatype=&ads.xumo_providerid=3830&ads.xumo_providername=nbcnwas',
    'http://68.251.105.81:5004/auto/v11.1',
    'http://68.251.105.81:5004/auto/v11.2',
    'http://68.251.105.81:5004/auto/v11.3',
    'https://d368vp0qqzvkid.cloudfront.net/11603/88889707/hls/master.m3u8?ads.xumo_channelid=88889707a&ads.xumo_ifatype=&ads.xumo_providerid=3832&ads.xumo_providername=nbcnct',
    'http://37c18028.akadatel.com/iptv/t6xncp6l7llkpd/1088/mpegts',
    'https://frontdoor.wcat-tv.org/live-12/live/live.m3u8',
    # Lifestyle
    'https://cb0c87cc605942ff9766a4e6744bbadc.mediatailor.us-east-1.amazonaws.com/v1/master/44f73ba4d03e9607dcd9bebdcb8494d86964f1d8/rlaxxtv-eu_autentictavel/playlist.m3u8',
    'https://linear-44.frequency.stream/dist/plex/44/hls/master/playlist.m3u8',
    'https://linear-43.frequency.stream/dist/galxy/43/hls/master/playlist.m3u8',
    'https://cineverse-all3-soreal-1-us.ono.wurl.tv/playlist.m3u8',
    # Movies
    'https://d1si3n1st4nkgb.cloudfront.net/10502/88886011/hls/master.m3u8?ads.xumo_channelid=88886011',
    'https://aegis-cloudfront-1.tubi.video/ea1ab5d1-f554-4f6b-b03f-2611fcd94257/playlist.m3u8',
    'https://tvpass.org/live/fxmoviechannel/hd',
    'https://a89829b8dca2471ab52ea9a57bc28a35.mediatailor.us-east-1.amazonaws.com/v1/master/0fb304b2320b25f067414d481a779b77db81760d/canelatv_sonycanalnovelas/playlist.m3u8',
    'http://190.2.212.209:8050/play/a0q3',
    'https://2-fss-2.streamhoster.com/pl_138/201950-5317556-1/playlist.m3u8',
    'https://dbrb49pjoymg4.cloudfront.net/10001/99991745/hls/master.m3u8?ads.xumo_channelid=99991745',
    # Music
    'https://59d39900ebfb8.streamlock.net/saintlouisltv/saintlouisltv/playlist.m3u8',
    'https://livechannel.mdc.akamaized.net/stitch/livechannel/1341/master1400000.m3u8;session=live_stream_1341',
    'https://server40.servistreaming.com:3477/stream/play.m3u8',
    'https://59d39900ebfb8.streamlock.net/radiotelekajou/radiotelekajou/playlist.m3u8',
    'https://1826200335.rsc.cdn77.org/1826200335/index.m3u8',
    'https://d39g1vxj2ef6in.cloudfront.net/v1/manifest/3fec3e5cac39a52b2132f9c66c83dae043dc17d4/prod-rakuten-stitched/54947915-6504-4548-aaef-eabd451f8607/1.m3u8',
    'https://d284aawtm5vi48.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-fjdfi2br1jtq7/xite_90s_throwback.m3u8',
    # News
    'https://pubads.g.doubleclick.net/ssai/event/tqd6w9ojqvoodbcyv3dammw/master.m3u8',
    'https://aegis-cloudfront-1.tubi.video/bc9ff1c7-4dc1-4e36-9ef0-25b28c595ada/playlist.m3u8',
    'https://cdn61.liveonlineservices.com/hls/humraaz.m3u8',
    'https://d1si3n1st4nkgb.cloudfront.net/10502/88896001/hls/master.m3u8?ads.xumo_channelid=88896001',
    'https://streamspace.live/hls/tempoafrictv/livestream.m3u8',
    'https://tyt-xumo-us.amagi.tv/hls/amagi_hls_data_tytnetwor-tyt-xumo/cdn/master.m3u8',
    'https://voa-ingest.akamaized.net/hls/live/2033874/tvmc06/playlist.m3u8',
    # Outdoor
    'https://0b73ace69ebb45eaa249bb87837cb958.mediatailor.us-west-2.amazonaws.com/v1/master/ba62fe743df0fe93366eba3a257d792884136c7f/linear-644-worbusenfast-lg_us/644/lgtv/hls/master/playlist.m3u8',
    # Religious
    'https://3abn.bozztv.com/3abn2/3abn_live/smil:3abn_live.smil/playlist.m3u8',
    'http://144.217.14.88/hls/hope4life.m3u8',
    'https://live.relentlessinnovations.net:1936/imantv/imantv/index.m3u8',
    'https://telered.live:1936/jrestv/jrestv/playlist.m3u8',
    'https://cdn-unified-hls.streamspot.com/ingest1/0b5c0f18e9/playlist.m3u8?origin=1',
    'https://live.relentlessinnovations.net:1936/rspe-tv/rspe-tv/index.m3u8',
    'https://59d39900ebfb8.streamlock.net/daniel/daniel/playlist.m3u8',
    'https://live.relentlessinnovations.net:1936/sadaehaq/sadaehaq/index.m3u8',
    'https://livestreamcdn.net:444/shalomtv/shalomtv/playlist.m3u8',
    'https://fuel-streaming-prod01.fuelmedia.io/v1/sem/cb165faa-41c9-42ad-83ee-ad5ca9fb927c.m3u8',
    'https://fuel-streaming-prod01.fuelmedia.io/v1/sem/b29d27bb-88af-42d1-937a-5bdf76b71c17.m3u8',
    'https://edge66.magictvbox.com/liveapple/trinity/tracks-v1a1/mono.m3u8',
    # Series
    'https://dai.google.com/linear/hls/event/jur94wl2qaivpgnhy5n5da/master.m3u8',
    'https://tvpass.org/live/hallmarkdrama/hd',
    'https://3238c44f.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/um9ydv9maxvybmx5ugfsyw9itfs/playlist.m3u8',
    'https://stream.ads.ottera.tv/playlist.m3u8?network_id=2380',
    'https://bobross-xumous.cinedigm.com/midroll/amagi_hls_data_xumo-host-bobross-xumo/cdn/master.m3u8',
    'https://6df6888a.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/um9ydv9uaW55sg91c2VOYXRpb25fsExT/playlist.m3u8',
}

def consolidate_group(g):
    if not g: return 'General'
    p = g.split(';')[0].strip()
    if not p or p.lower() == 'undefined': return 'General'
    pl = p.lower()
    if pl in {'auto','cooking','travel','shop','relax','science','weather','animation','family','classic','legislative'}: return None
    KEEP={'general','local news','local news | pnw','sports','entertainment','movies','series','news','kids','religious','lifestyle','education','music','documentary','comedy','culture','business','outdoor','pluto tv','plex','roku channel','samsung tv plus','tubi','pbs','pbs kids'}
    if pl not in KEEP: return 'International'
    CONS={'auto':'Lifestyle','cooking':'Lifestyle','travel':'Lifestyle','shop':'Lifestyle','relax':'Lifestyle','science':'Education','weather':'News','animation':'Kids','family':'Kids','classic':'Entertainment','legislative':'General'}
    return CONS.get(pl, p.title())

# Dead domains — 100% failure rate from US validation
REJECT_DOMAINS = {
    'tvpass.org',
    'streamhoster.com',
    'cablecast.tv',
    'scientology.org',
    'streamspot.com',
    '5centscdn.com',
    'persiana.live',
    'fuel-streaming-prod01.fuelmedia.io',
    'relentlessinnovations.net',
    'bozztv.com',
    'magictvbox.com',
    'telered.live',
    'servistreaming.com',
    'kazmazpaz.ru',
    'jlahozconsulting.com',
    'rsc.cdn77.org',
    'boo.tv',
    'dai.google.com',
}


def is_english(ch):
    n = ch['name']
    if any(ord(c) > 0x3000 for c in n): return False
    if any(0x0590 <= ord(c) < 0x0780 for c in n): return False
    if any(0x0400 <= ord(c) < 0x0500 for c in n): return False
    if any(0x0370 <= ord(c) < 0x0400 for c in n): return False
    nl = n.lower()
    for kw in REJECT_NAME:
        if kw in nl: return False
    if ch['url'].lower() in REJECT_URLS: return False
    if any(d in ch['url'].lower() for d in REJECT_DOMAINS): return False
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
kept=[]
for c in deduped:
    if is_english(c): kept.append(c)
deduped=kept
print(f"After filter: {n1} -> {len(deduped)}")

# Remove International group
before_intl = len(deduped)
deduped = [c for c in deduped if c['group'] != 'International']
print(f"Removed International: {before_intl - len(deduped)}")

eu={c['url'] for c in deduped}
for ec in [{'name':'KGW 8 News Portland','id':'KGWDT1.us','logo':'','group':'Local News | PNW','url':'https://livevideo01.kgw.com/hls/live/2015506/elvs/live.m3u8'},
           {'name':'KATU News Portland','id':'KATUDT1.us','logo':'','group':'Local News | PNW','url':'https://linear-710.frequency.stream/dist/stirr/710/hls/master/playlist.m3u8'},
           {'name':'KIRO 7 News Seattle','id':'KIRODT1.us','logo':'','group':'Local News | PNW','url':'https://cdn-ue1-prod.tsv2.amagi.tv/linear/amg00327-coxmediagroup-kirobreaking-ono/playlist.m3u8'}]:
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
