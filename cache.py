import os
import json

CACHE_DIR = "cache"


def _transcript_path(video_id):
    return os.path.join(CACHE_DIR, video_id, "transcript.json")


def _analysis_path(video_id, profile_name, platform="tiktok"):
    return os.path.join(CACHE_DIR, video_id, f"{profile_name}_{platform}_analysis.json")


def get_cached_transcript(video_id):
    path = _transcript_path(video_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_transcript(video_id, segments):
    path = _transcript_path(video_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(segments, f, indent=2)
    print(f"Transcript cached for video: {video_id}")


def get_cached_analysis(video_id, profile_name, platform="tiktok"):
    path = _analysis_path(video_id, profile_name, platform)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_analysis(video_id, profile_name, platform, hook_data):
    path = _analysis_path(video_id, profile_name, platform)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(hook_data, f, indent=2)
    print(f"Analysis cached for video: {video_id} / profile: {profile_name} / platform: {platform}")
