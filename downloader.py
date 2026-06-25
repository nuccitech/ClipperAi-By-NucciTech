import yt_dlp
import os

def download_video(url):
    # GUARD 1: Check if the URL is valid before wasting processing power
    if not url.startswith("http"):
        print("ERROR: Invalid URL provided. It must start with 'http'.")
        return None, None

    print(f"Starting download for: {url}")

    # Extract the video ID first so we can name the file after it
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id', 'unknown')
    except Exception as e:
        print(f"\nCRITICAL ERROR extracting video info: {e}")
        return None, None

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]',
        'outtmpl': f'{video_id}.%(ext)s',
        'quiet': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        file_path = f"{video_id}.mp4"
        if os.path.exists(file_path):
            print(f"\nSUCCESS! Video saved as: {file_path}")
            return video_id, file_path
        else:
            print("\nERROR: The download finished, but the file could not be found.")
            return None, None

    except Exception as e:
        print(f"\nCRITICAL ERROR downloading video: {e}")
        return None, None

# --- TESTING AREA ---
# This block only runs if you execute this specific file directly.
if __name__ == "__main__":
    # We will use the very first YouTube video ever uploaded as a safe, 19-second test clip.
    test_url = "https://vimeo.com/503166067"
    
    # Trigger the function
    download_video(test_url)