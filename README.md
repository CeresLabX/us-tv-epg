# US TV EPG

EPG (TV guide) for US IPTV streams, generated from the [iptv-org](https://github.com/iptv-org/iptv) open-source playlist.

**EPG URL:** `https://CeresLabX.github.io/us-tv-epg/epg.xml`

**Playlist URL:** `https://iptv-org.github.io/iptv/countries/us.m3u`

## Usage in TiMATE

1. Open TiMATE → Accounts → Add Playlist (M3U URL)
2. Paste: `https://iptv-org.github.io/iptv/countries/us.m3u`
3. Add EPG Source → paste: `https://CeresLabX.github.io/us-tv-epg/epg.xml`

## Auto-Update

The EPG regenerates every 12 hours via cron job on the host machine.

## Channel Count

Currently: **1322 channels** (from iptv-org US playlist).

## Note

Programme schedule data is placeholder (3-hour blocks repeating). This gives channel names and logos in TiMATE. Real programme schedules would require a separate EPG data source.
