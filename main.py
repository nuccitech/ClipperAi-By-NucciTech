import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from downloader import download_video
from transcriber import extract_audio, get_transcript
from analyzer import find_viral_hooks
from editor import cut_and_crop_video, PLATFORMS
from cache import get_cached_transcript, save_transcript, get_cached_analysis, save_analysis


HARD_CAP = 90  # absolute safety fallback — never export more than this


def _smart_boundaries(segments, gpt_start, gpt_end, dur_min, dur_max):
    def _is_sent_end(text):
        return text.strip().endswith(('.', '?', '!'))

    # Layer 1 — snap start to nearest segment boundary (±3s before, ±2s after)
    start_cands = [s for s in segments if gpt_start - 3.0 <= s['start'] <= gpt_start + 2.0]
    if start_cands:
        snap_seg = min(start_cands, key=lambda s: abs(s['start'] - gpt_start))
    else:
        after = [s for s in segments if s['start'] >= gpt_start]
        snap_seg = after[0] if after else None
    snapped_start = snap_seg['start'] if snap_seg else gpt_start

    # Layer 2 — find sentence-ending segment within ±15s of gpt_end
    window_sents = [s for s in segments
                    if gpt_end - 15.0 <= s['end'] <= gpt_end + 15.0
                    and _is_sent_end(s['text'])
                    and s['end'] > snapped_start]
    best_end = min(window_sents, key=lambda s: abs(s['end'] - gpt_end))['end'] if window_sents else None

    # Layer 3 — enforce dur_min: scan forward if still too short
    if best_end is None or (best_end - snapped_start) < dur_min:
        target = snapped_start + dur_min
        cap    = snapped_start + dur_max
        forward_sents = [s for s in segments
                         if s['end'] >= target and s['end'] <= cap and _is_sent_end(s['text'])]
        if forward_sents:
            best_end = forward_sents[0]['end']
        else:
            forward_any = [s for s in segments if s['end'] >= target and s['end'] <= cap]
            if forward_any:
                best_end = forward_any[0]['end']

    # Layer 4 — enforce dur_max: backtrack if too long
    if best_end is not None and (best_end - snapped_start) > dur_max:
        cap_time = snapped_start + dur_max
        before_cap = [s for s in segments
                      if s['end'] <= cap_time and s['end'] > snapped_start and _is_sent_end(s['text'])]
        best_end = before_cap[-1]['end'] if before_cap else cap_time

    # Layer 5 — absolute fallback
    if best_end is None or best_end <= snapped_start:
        best_end = min(gpt_end, snapped_start + HARD_CAP)

    return snapped_start, best_end


def run_automated_factory(target_input, profile_name="default", platform="tiktok", max_clips=None):
    print(f"==================================================")
    print(f"STARTING AUTOMATED PIPELINE (Profile: {profile_name} | Platform: {platform})")
    print(f"==================================================\n")

    # ---------------------------------------------------------
    # STEP 0: DOWNLOAD
    # ---------------------------------------------------------
    if "youtube.com" in target_input or "youtu.be" in target_input:
        print(">>> STAGE 0: DOWNLOADING YOUTUBE VIDEO")
        video_id, video_filepath = download_video(target_input)
        if not video_filepath:
            print("Pipeline Failed at Stage 0 (Download).")
            return
    else:
        video_filepath = target_input
        video_id = os.path.splitext(os.path.basename(target_input))[0]

    # ---------------------------------------------------------
    # STEP 1: TRANSCRIBE (with cache)
    # ---------------------------------------------------------
    print("\n>>> STAGE 1: AUDIO EXTRACTION & TRANSCRIPTION")
    audio_path = None
    cached_segments = get_cached_transcript(video_id)

    if cached_segments:
        print("Cache hit: skipping Whisper transcription.")
        segments = cached_segments
    else:
        audio_path = extract_audio(video_filepath, f"temp_audio_{video_id}.mp3")
        if not audio_path:
            print("Pipeline Failed at Stage 1 (Audio Extraction).")
            return

        transcript_data = get_transcript(audio_path)
        if not transcript_data:
            print("Pipeline Failed at Stage 1 (Transcription).")
            return

        segments = [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in transcript_data.segments
        ]
        save_transcript(video_id, segments)

    segments_text = "\n".join(
        f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text'].strip()}"
        for seg in segments
    )

    # ---------------------------------------------------------
    # STEP 2: ANALYZE (with cache)
    # ---------------------------------------------------------
    print(f"\n>>> STAGE 2: AI HOOK ANALYSIS (Persona: {profile_name})")
    cached_hook = get_cached_analysis(video_id, profile_name, platform)

    if cached_hook:
        print(f"Cache hit: skipping GPT analysis.")
        hook_data = cached_hook
    else:
        platform_max = PLATFORMS.get(platform, {}).get("max_duration")
        hook_data = find_viral_hooks(segments_text, profile_name=profile_name,
                                     platform=platform, platform_max_duration=platform_max)
        if not hook_data:
            print("Pipeline Failed at Stage 2 (Analysis).")
            return
        save_analysis(video_id, profile_name, platform, hook_data)

    clips = hook_data.get("clips", [])
    if not clips:
        print("Pipeline Failed at Stage 2 (no clips returned).")
        return

    # Load profile for title lookup, style injection, and clip duration limits
    style = {}
    emotion_titles = {}
    clip_duration_min = 30
    clip_duration_max = 60
    profile_path = f"profiles/{profile_name}.json"
    if os.path.exists(profile_path):
        with open(profile_path) as f:
            profile_data = json.load(f)
        emotion_titles = profile_data.get('emotion_titles', {})
        clip_duration_min = profile_data.get('clip_duration_min', clip_duration_min)
        clip_duration_max = profile_data.get('clip_duration_max', clip_duration_max)
        style = {
            'caption_font':         profile_data.get('caption_font'),
            'caption_font_size':    profile_data.get('caption_font_size', 55),
            'caption_color':        profile_data.get('caption_color', [255, 255, 255]),
            'caption_stroke_color': profile_data.get('caption_stroke_color', [0, 0, 0]),
            'logo_path':            profile_data.get('logo_path'),
            'logo_position':        profile_data.get('logo_position', 'top-right'),
            'crop_strategy':        profile_data.get('crop_strategy', 'auto'),
        }
    platform_max = PLATFORMS.get(platform, {}).get('max_duration', HARD_CAP)
    clip_duration_max = min(clip_duration_max, platform_max)

    # ---------------------------------------------------------
    # STEP 3: EDIT — one export per clip that passes the score gate
    # ---------------------------------------------------------
    print("\n>>> STAGE 3: CUTTING & CROPPING")
    output_dir = os.path.join("output", profile_name)
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported = []
    exported_clips = []  # (filename, clip_dict, title_text) for report

    for i, clip in enumerate(clips, 1):
        if max_clips is not None and len(exported) >= max_clips:
            print(f"\nMax clips reached ({max_clips}). Stopping export.")
            break
            
        score = clip.get('score', 0)
        if score < 7:
            print(f"\nClip {i}: score {score}/10 is below threshold — skipping.")
            continue

        gpt_start_orig, gpt_end_orig = clip['start'], clip['end']
        clip['start'], clip['end'] = _smart_boundaries(
            segments, gpt_start_orig, gpt_end_orig,
            clip_duration_min, clip_duration_max
        )
        print(f"  Boundaries: GPT {gpt_start_orig:.1f}s–{gpt_end_orig:.1f}s "
              f"({gpt_end_orig - gpt_start_orig:.1f}s) "
              f"→ smart {clip['start']:.1f}s–{clip['end']:.1f}s "
              f"({clip['end'] - clip['start']:.1f}s)")

        title_text = emotion_titles.get(clip.get('emotion', ''), '')
        safe_profile = profile_name.replace(" ", "")
        emotion_label = clip.get('emotion', 'Viral').replace(" ", "")
        output_filename = os.path.join(output_dir, f"{safe_profile}_{platform}_Clip{i}_{emotion_label}.mp4")

        print(f"\n--- Clip {i} of {len(clips)} | Score: {score}/10 | {clip.get('hook_type','N/A')} ---")
        result = cut_and_crop_video(
            video_filepath=video_filepath,
            start_time=clip['start'],
            end_time=clip['end'],
            output_filename=output_filename,
            title_text=title_text,
            style=style,
            platform=platform,
            transcript=segments,
        )
        if result:
            exported.append(result)
            exported_clips.append((result, clip, title_text))

    # ---------------------------------------------------------
    # STEP 4: CLIP REPORT
    # ---------------------------------------------------------
    if exported_clips:
        report_path = os.path.join(output_dir, f"{video_id}_{platform}_{timestamp}_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"CLIPER REPORT — {profile_name} | {platform} | {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("=" * 60 + "\n\n")
            for i, (filename, clip, title) in enumerate(exported_clips, 1):
                mins = int(clip['start']) // 60
                secs = int(clip['start']) % 60
                duration = clip['end'] - clip['start']
                f.write(f"CLIP {i} — Score: {clip.get('score', 'N/A')}/10 | {clip.get('hook_type', '').replace('_', ' ').title()} | {clip.get('hype_level', 'N/A')}\n")
                f.write(f"Timestamp: {mins}:{secs:02d} | Duration: {duration:.1f}s\n")
                f.write(f"Emotion: {clip.get('emotion', 'N/A')} | Target Platform: {clip.get('target_platform', 'N/A')}\n")
                if clip.get('editing_directive'):
                    f.write(f"Editing directive: {clip['editing_directive']}\n")
                if title:
                    f.write(f"Suggested caption: \"{title}\"\n")
                f.write(f"Why it works: {clip.get('reason', 'N/A')}\n")
                f.write(f"File: {os.path.basename(filename)}\n\n")
        print(f"Report generated: {report_path}")

    # --- DATASET GATHERING ---
    # Save the full transcript so we can use it as training data for the custom AI Editor model later
    transcript_path = os.path.join(output_dir, f"{video_id}_{platform}_{timestamp}_transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(segments_text)
    print(f"Full transcript saved for future AI training: {transcript_path}")

    # ---------------------------------------------------------
    # STEP 5: CLEANUP
    # ---------------------------------------------------------
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)
        print("\nCleaned up temporary audio files.")

    print(f"\n==================================================")
    if exported:
        print(f"✅ PIPELINE COMPLETE! {len(exported)} clip(s) exported:")
        for path in exported:
            print(f"   • {path}")
    else:
        print("⚠️  No clips met the score threshold. Nothing exported.")
    print(f"==================================================")

def api_analyze_video(youtube_url, profile_name="default", platform="tiktok"):
    """API endpoint 1: Download, Transcribe, and Analyze hooks."""
    print("\n" + "="*50)
    print("API ANALYZE REQUEST")
    print(f"URL: {youtube_url} | Profile: {profile_name} | Platform: {platform}")
    print("="*50)
    
    video_id, video_filepath = download_video(youtube_url)
    if not video_filepath: return {"error": "Download failed"}

    audio_filepath = f"{video_id}_temp_audio.mp3"
    if not os.path.exists(audio_filepath):
        extract_audio(video_filepath, audio_filepath)

    cached_transcript = get_cached_transcript(video_id)
    if cached_transcript:
        segments = cached_transcript
    else:
        transcript_data = get_transcript(audio_filepath)
        if not transcript_data: return {"error": "Transcription failed"}
        segments = [{"start": s.start, "end": s.end, "text": s.text} for s in transcript_data.segments]
        save_transcript(video_id, segments)
    segments_text = "\n".join([f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments])

    cached_hook = get_cached_analysis(video_id, profile_name, platform)
    if cached_hook:
        hook_data = cached_hook
    else:
        platform_max = PLATFORMS.get(platform, {}).get("max_duration")
        hook_data = find_viral_hooks(segments_text, profile_name=profile_name, platform=platform, platform_max_duration=platform_max)
        if not hook_data: return {"error": "Analysis failed"}
        save_analysis(video_id, profile_name, platform, hook_data)
        
    return {
        "video_id": video_id,
        "video_filepath": video_filepath,
        "clips": hook_data.get("clips", []),
        "profile_name": profile_name,
        "platform": platform
    }

def api_render_clip(video_id, video_filepath, clip_data, profile_name, platform, style_overrides):
    """API endpoint 2: Render a specific clip with specific settings."""
    cached_transcript = get_cached_transcript(video_id)
    if not cached_transcript:
        return {"error": "Transcript not found in cache"}
        
    segments = cached_transcript
    
    style = {}
    emotion_titles = {}
    clip_duration_min = 30
    clip_duration_max = 60
    profile_path = f"profiles/{profile_name}.json"
    if os.path.exists(profile_path):
        with open(profile_path) as f:
            profile_data = json.load(f)
        emotion_titles = profile_data.get('emotion_titles', {})
        clip_duration_min = profile_data.get('clip_duration_min', clip_duration_min)
        clip_duration_max = profile_data.get('clip_duration_max', clip_duration_max)
        style = {
            'caption_font':         profile_data.get('caption_font'),
            'caption_font_size':    profile_data.get('caption_font_size', 55),
            'caption_color':        profile_data.get('caption_color', [255, 255, 255]),
            'caption_stroke_color': profile_data.get('caption_stroke_color', [0, 0, 0]),
            'logo_path':            profile_data.get('logo_path'),
            'logo_position':        profile_data.get('logo_position', 'top-right'),
            'crop_strategy':        profile_data.get('crop_strategy', 'auto'),
            'use_subtitles':        profile_data.get('use_subtitles', True),
            'use_watermark':        profile_data.get('use_watermark', True),
        }
        
    if 'crop_strategy' in style_overrides:
        style['crop_strategy'] = style_overrides['crop_strategy']
    if 'use_subtitles' in style_overrides:
        style['use_subtitles'] = style_overrides['use_subtitles']
    if 'use_watermark' in style_overrides:
        style['use_watermark'] = style_overrides['use_watermark']
        
    platform_max = PLATFORMS.get(platform, {}).get('max_duration', HARD_CAP)
    clip_duration_max = min(clip_duration_max, platform_max)
    
    final_start, final_end = _smart_boundaries(
        segments, clip_data['start'], clip_data['end'], clip_duration_min, clip_duration_max
    )
    clip_data['start'] = final_start
    clip_data['end'] = final_end
    
    title_text = emotion_titles.get(clip_data.get('emotion', ''), '')
    safe_profile = profile_name.replace(" ", "")
    emotion_label = clip_data.get('emotion', 'Viral').replace(" ", "")
    
    output_dir = os.path.join("output", profile_name)
    os.makedirs(output_dir, exist_ok=True)
    
    strategy_label = style['crop_strategy']
    subs_label = "Subs" if style['use_subtitles'] else "NoSubs"
    wm_label = "WM" if style.get('use_watermark', True) else "NoWM"
    safe_start = int(clip_data['start'])
    output_filename = os.path.join(output_dir, f"{safe_profile}_{platform}_{emotion_label}_{safe_start}s_{strategy_label}_{subs_label}_{wm_label}.mp4")
    
    print(f"\n>>> RENDERING CUSTOM CLIP: {output_filename}")
    result = cut_and_crop_video(
        video_filepath=video_filepath,
        start_time=clip_data['start'],
        end_time=clip_data['end'],
        output_filename=output_filename,
        title_text=title_text,
        style=style,
        platform=platform,
        transcript=segments,
    )
    
    if result:
        return {"success": True, "file": output_filename}
    return {"error": "Render failed"}

def api_batch_render_clips(data):
    video_id = data.get('video_id')
    video_filepath = data.get('video_filepath')
    profile_name = data.get('profile_name')
    platform = data.get('platform')
    clips = data.get('clips', [])
    
    print(f"\n--- BATCH RENDER STARTED FOR {video_id} ({len(clips)} clips) ---")
    
    for i, clip_info in enumerate(clips):
        clip_data = clip_info.get('clip_data')
        style_overrides = clip_info.get('style_overrides', {})
        print(f"\n>> Rendering Clip {i+1} of {len(clips)}...")
        try:
            api_render_clip(video_id, video_filepath, clip_data, profile_name, platform, style_overrides)
        except Exception as e:
            print(f"Error rendering clip {i+1}: {e}")
            
    print(f"\n--- BATCH RENDER COMPLETE ---")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cliper — automated short-form video pipeline")
    parser.add_argument("url", help="YouTube URL or local video file path")
    parser.add_argument("--profile", default="test", help="Creator profile name (default: test)")
    parser.add_argument("--platform", default="tiktok",
                        choices=["tiktok", "reels", "shorts", "twitter", "linkedin"],
                        help="Target platform (default: tiktok)")
    args = parser.parse_args()
    run_automated_factory(args.url, profile_name=args.profile, platform=args.platform)