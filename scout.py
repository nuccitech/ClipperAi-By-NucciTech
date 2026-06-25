import yt_dlp
import traceback

def scan_channel_for_shorts(channel_url, max_videos=50):
    """
    Scrapes the channel for videos, filters out shorts (usually under 60s, or specified via URL if possible),
    and sorts them by view count to return the top 10 viral shorts.
    """
    
    # If the user didn't specify /shorts, append it if it's a channel URL to ensure we hit the shorts feed
    if "/@" in channel_url and not channel_url.endswith("/shorts") and "/watch" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/shorts"
        
    print(f"Scouting channel: {channel_url}")
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'playlistend': max_videos,
        'cookiefile': 'youtube.com_cookies.txt',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            entries = info.get('entries', [])
            
            shorts = []
            for entry in entries:
                if not entry:
                    continue
                # yt-dlp flat extract usually provides view_count.
                # If duration is missing but it came from /shorts, we assume it's a short.
                views = entry.get('view_count', 0)
                if views is None:
                    views = 0
                    
                # Format views beautifully
                if views >= 1000000:
                    formatted_views = f"{views / 1000000:.1f}M"
                elif views >= 1000:
                    formatted_views = f"{views / 1000:.1f}K"
                else:
                    formatted_views = str(views)
                
                thumbnail = ""
                if entry.get('thumbnails'):
                    thumbnail = entry['thumbnails'][-1]['url'] # Get best quality
                    
                shorts.append({
                    "id": entry.get('id'),
                    "title": entry.get('title', 'Unknown Title'),
                    "url": entry.get('url'),
                    "view_count": views,
                    "formatted_views": formatted_views,
                    "thumbnail": thumbnail
                })
                
            # Sort by view count descending
            shorts.sort(key=lambda x: x['view_count'], reverse=True)
            
            # Return Top 12 shorts
            return shorts[:12]
            
    except Exception as e:
        print(f"Error scouting channel: {e}")
        traceback.print_exc()
        return []

def discover_competitors(keyword, max_videos=50):
    """
    Searches YouTube for a keyword, aggregates the results by channel,
    and returns a ranked list of the top competitor channels.
    """
    print(f"Discovering competitors for: {keyword}")
    
    search_query = f"ytsearch{max_videos}:{keyword} shorts"
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'cookiefile': 'youtube.com_cookies.txt',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            
            channels = {}
            
            for entry in entries:
                if not entry:
                    continue
                    
                views = entry.get('view_count', 0)
                if views is None:
                    views = 0
                    
                channel_name = entry.get('channel', entry.get('uploader', 'Unknown Channel'))
                channel_url = entry.get('uploader_url', '')
                
                if not channel_url or channel_name == 'Unknown Channel':
                    continue
                    
                if channel_name not in channels:
                    channels[channel_name] = {
                        "name": channel_name,
                        "url": channel_url,
                        "total_views": 0,
                        "hit_count": 0,
                        "top_short_title": entry.get('title', 'Unknown Title'),
                        "top_short_url": entry.get('url', '')
                    }
                    
                channels[channel_name]["total_views"] += views
                channels[channel_name]["hit_count"] += 1
                
            # Convert to list and sort by total views
            competitors = list(channels.values())
            competitors.sort(key=lambda x: x['total_views'], reverse=True)
            
            # Format view counts
            for comp in competitors:
                v = comp["total_views"]
                if v >= 1000000:
                    comp["formatted_views"] = f"{v / 1000000:.1f}M"
                elif v >= 1000:
                    comp["formatted_views"] = f"{v / 1000:.1f}K"
                else:
                    comp["formatted_views"] = str(v)
            
            return competitors[:5]
            
    except Exception as e:
        print(f"Error discovering competitors: {e}")
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # Test
    res = discover_competitors("podcast clips", 20)
    for c in res:
        print(f"{c['formatted_views']} views across {c['hit_count']} shorts - {c['name']}")
