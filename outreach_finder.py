import os
import re
import json
import concurrent.futures
from urllib.parse import urlparse
import yt_dlp
try:
    from batch_run import QUEUE
except ImportError:
    QUEUE = []

OUTPUT_FILE = "outreach_contacts.json"
MARKDOWN_REPORT = "outreach_contacts.md"

# Common patterns
EMAIL_REGEX = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'

SOCIAL_PLATFORMS = {
    "instagram": ["instagram.com", "ig.me"],
    "twitter": ["twitter.com", "x.com"],
    "linkedin": ["linkedin.com"],
    "tiktok": ["tiktok.com"],
    "facebook": ["facebook.com", "fb.me", "fb.com"],
    "linktree": ["linktr.ee", "linktr.ee/"],
    "patreon": ["patreon.com"],
    "spotify": ["open.spotify.com", "spotify.com"],
    "discord": ["discord.gg", "discord.com"]
}

EXCLUDED_DOMAINS = [
    "youtube.com", "youtu.be", "google.com", "googlevideo.com", "ytimg.com",
    "doubleclick.net", "schema.org", "w3.org", "wikipedia.org"
]

def load_existing_results():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_results(results):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def extract_links(text):
    if not text:
        return []
    # Find all http/https links
    urls = re.findall(r'https?://[^\s\)\"\']+', text)
    cleaned = []
    for u in urls:
        # strip trailing punctuation commonly found in text descriptions
        u = re.sub(r'[\.,\)\"\'\]\<\>\:\;]+$', '', u)
        cleaned.append(u)
    return list(set(cleaned))

def categorize_links(links):
    categorized = {
        "instagram": "",
        "twitter": "",
        "linkedin": "",
        "tiktok": "",
        "facebook": "",
        "linktree": "",
        "patreon": "",
        "websites": []
    }
    
    for link in links:
        parsed = urlparse(link)
        domain = parsed.netloc.lower()
        
        # Check if domain belongs to a social platform
        matched = False
        for platform, patterns in SOCIAL_PLATFORMS.items():
            if any(pat in domain for pat in patterns):
                if platform in categorized:
                    # Keep the first matched link for the platform
                    if not categorized[platform]:
                        categorized[platform] = link
                matched = True
                break
        
        if not matched:
            # Check if domain should be excluded
            exclude = any(ex in domain for ex in EXCLUDED_DOMAINS)
            if not exclude:
                categorized["websites"].append(link)
                
    # Remove duplicates from websites
    categorized["websites"] = list(set(categorized["websites"]))
    return categorized

def get_channel_about_desc(uploader_url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(uploader_url, download=False)
            return info.get("description", "")
        except Exception as e:
            print(f"  [Warning] Failed to fetch channel description for {uploader_url}: {e}")
            return ""

def process_single_creator(url, profile, platform):
    print(f"Processing: {profile} ({url})...")
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': False,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_info = ydl.extract_info(url, download=False)
            
        uploader = video_info.get("uploader", profile)
        uploader_id = video_info.get("uploader_id", "")
        uploader_url = video_info.get("uploader_url", f"https://www.youtube.com/{uploader_id}" if uploader_id else "")
        video_desc = video_info.get("description", "")
        
        # Get channel about description
        channel_desc = ""
        if uploader_url:
            channel_desc = get_channel_about_desc(uploader_url)
            
        combined_text = video_desc + "\n" + channel_desc
        
        # Extract emails
        emails = list(set(re.findall(EMAIL_REGEX, combined_text)))
        # Filter out common false positives or placeholder emails
        emails = [email for email in emails if not email.endswith('.png') and not email.endswith('.jpg') and not email.startswith('your_')]
        
        # Extract links
        all_links = extract_links(combined_text)
        links_cat = categorize_links(all_links)
        
        # Combine the results
        result = {
            "profile": profile,
            "target_platform": platform,
            "channel_name": uploader,
            "channel_handle": uploader_id,
            "channel_url": uploader_url,
            "video_url": url,
            "emails": emails,
            "socials": {
                "instagram": links_cat["instagram"],
                "twitter": links_cat["twitter"],
                "linkedin": links_cat["linkedin"],
                "tiktok": links_cat["tiktok"],
                "facebook": links_cat["facebook"],
                "linktree": links_cat["linktree"],
                "patreon": links_cat["patreon"],
            },
            "websites": links_cat["websites"]
        }
        
        print(f"  Done: {profile} - Emails: {emails}")
        return url, result
        
    except Exception as e:
        print(f"  [Error] Failed to process {profile} ({url}): {e}")
        return url, {
            "profile": profile,
            "target_platform": platform,
            "channel_name": profile,
            "channel_handle": "",
            "channel_url": "",
            "video_url": url,
            "emails": [],
            "socials": {p: "" for p in SOCIAL_PLATFORMS.keys() if p in ["instagram", "twitter", "linkedin", "tiktok", "facebook", "linktree", "patreon"]},
            "websites": [],
            "error": str(e)
        }

def write_markdown_report(results):
    # Also write to local workspace md
    with open(MARKDOWN_REPORT, "w", encoding="utf-8") as f:
        f.write("# Creator Outreach Contact List\n\n")
        f.write("This document summarizes the contact details, social links, and websites discovered for the creators in your prospecting queue.\n\n")
        
        # Summary metrics
        total = len(results)
        with_emails = sum(1 for r in results.values() if r.get("emails"))
        with_socials = sum(1 for r in results.values() if any(r.get("socials", {}).values()))
        
        f.write("## Summary Metrics\n")
        f.write(f"- **Total Creators Processed**: {total}\n")
        f.write(f"- **Creators with Business Emails**: {with_emails} ({with_emails/total*100:.1f}%)\n")
        f.write(f"- **Creators with Social Links**: {with_socials} ({with_socials/total*100:.1f}%)\n\n")
        
        f.write("## Contact Directory\n\n")
        f.write("| Profile | Channel | Emails | Instagram | LinkedIn | Twitter/X | Linktree / Website | Video Link |\n")
        f.write("|---------|---------|--------|-----------|----------|-----------|-------------------|------------|\n")
        
        for url, r in sorted(results.items(), key=lambda x: x[1]['profile']):
            profile = r.get("profile", "")
            channel_name = r.get("channel_name", "")
            emails = ", ".join(r.get("emails", [])) or "None found"
            
            socials = r.get("socials", {})
            ig = f"[IG]({socials.get('instagram')})" if socials.get('instagram') else "-"
            li = f"[LI]({socials.get('linkedin')})" if socials.get('linkedin') else "-"
            tw = f"[X]({socials.get('twitter')})" if socials.get('twitter') else "-"
            
            # Website / Linktree column
            web_links = []
            if socials.get('linktree'):
                web_links.append(f"[Linktree]({socials.get('linktree')})")
            for web in r.get("websites", [])[:2]:
                domain = urlparse(web).netloc
                web_links.append(f"[{domain}]({web})")
            web_col = ", ".join(web_links) if web_links else "-"
            
            video_link = f"[Watch]({url})"
            
            f.write(f"| **{profile}** | {channel_name} | {emails} | {ig} | {li} | {tw} | {web_col} | {video_link} |\n")
            
        f.write("\n\n*Generated automatically by Antigravity outreach_finder.py.*\n")

def main():
    results = load_existing_results()
    
    # Filter queue to only process ones we haven't processed yet or had errors on
    remaining_queue = []
    for item in QUEUE:
        url = item[0]
        if url not in results or "error" in results[url]:
            remaining_queue.append(item)
            
    print(f"Total creators in queue: {len(QUEUE)}")
    print(f"Already processed: {len(QUEUE) - len(remaining_queue)}")
    print(f"Remaining to process: {len(remaining_queue)}\n")
    
    if remaining_queue:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_creator = {
                executor.submit(process_single_creator, url, profile, platform): url
                for url, profile, platform in remaining_queue
            }
            
            for future in concurrent.futures.as_completed(future_to_creator):
                url = future_to_creator[future]
                try:
                    url, result = future.result()
                    results[url] = result
                    save_results(results)
                except Exception as exc:
                    print(f"URL {url} generated an exception: {exc}")
                    
    write_markdown_report(results)
    print(f"\nDone! Contact directory saved to {OUTPUT_FILE} and report written to {MARKDOWN_REPORT}.")

if __name__ == "__main__":
    main()
