# US TV Playlist & EPG

Filtered to US-accessible, English-language channels only. Validated streams, single group per channel.

**Playlist URL:** `https://CeresLabX.github.io/us-tv/playlist.m3u`

**EPG URL:** `https://CeresLabX.github.io/us-tv/epg.xml`

**Channel count:** ~1,400 channels

---

## Sources

- **iptv-org US** — US-based channels from the iptv-org community database
- **iptv-org English** — Global English-language channels (BBC, Sky News, Euronews, etc.)
- **Free-TV/IPTV** — Supplemental international channels (filtered to recognized categories)

---

## Groups

General, News, Sports, Entertainment, Movies, Series, Kids, Religious, Lifestyle, Music, Documentary, Comedy, Culture, Business, Education, Outdoor, Local News, + Pluto TV, Plex, Roku Channel, Samsung TV Plus, Tubi, PBS, PBS Kids (when available from sources)

---

## Usage in TiMATE

1. Add playlist: `https://CeresLabX.github.io/us-tv/playlist.m3u`
2. Add EPG: `https://CeresLabX.github.io/us-tv/epg.xml`

---

## Auto-Update

Playlist and EPG regenerate every 12 hours via GitHub Actions. Streams are validated (parallel HEAD requests). Only validated, accessible streams are included.

---

## Note

- Programme schedules are placeholder (3-hour blocks). This gives channel names, logos, and categories in TiMATE.
- KGW 8 News Portland is hardcoded to survive auto-refresh.
- Pluto TV, Plex, Roku Channel, Samsung TV Plus, Tubi, PBS, PBS Kids playlists were removed from public hosts (DMCA). Channels from these platforms appear in the playlist when included in iptv-org or Free-TV sources.
