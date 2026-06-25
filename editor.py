import os
import cv2
import numpy as np
import textwrap
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip

PLATFORMS = {
    "tiktok":   {"aspect_w": 9,  "aspect_h": 16, "max_duration": 60,  "title_y": 80},
    "reels":    {"aspect_w": 9,  "aspect_h": 16, "max_duration": 90,  "title_y": 80},
    "shorts":   {"aspect_w": 9,  "aspect_h": 16, "max_duration": 60,  "title_y": 60},
    "twitter":  {"aspect_w": 16, "aspect_h": 9,  "max_duration": 140, "title_y": 40},
    "linkedin": {"aspect_w": 1,  "aspect_h": 1,  "max_duration": 600, "title_y": 40},
}


def _detect_face_positions(video_path, start_time, end_time, fps):
    """Sample one frame per second and return {clip_frame_idx: face_center_x}."""
    cap = cv2.VideoCapture(video_path)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    sample_step = max(1, int(fps))
    frame_start = int(start_time * fps)
    frame_end = int(end_time * fps)

    positions = {}
    f = frame_start
    while f <= frame_end:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
        if len(faces) > 0:
            largest = max(faces, key=lambda fc: fc[2] * fc[3])
            x, y, w, h = largest
            positions[f - frame_start] = x + w // 2
        f += sample_step

    cap.release()
    return positions


def _build_crop_func(positions, clip_width, target_width, clip_fps, total_frames):
    """Return a per-frame crop function with smoothed face tracking for clip.fl()."""
    center = clip_width // 2
    half = target_width // 2

    # Fill gaps forward with last known position, defaulting to center
    filled = {}
    last = center
    for i in range(total_frames):
        if i in positions:
            last = int(positions[i])
        filled[i] = last

    # 1-second moving average to remove jitter
    window = max(1, int(clip_fps))
    smoothed = {}
    for i in range(total_frames):
        s = max(0, i - window // 2)
        e = min(total_frames - 1, i + window // 2)
        smoothed[i] = int(sum(filled[j] for j in range(s, e + 1)) / (e - s + 1))

    def crop_frame(get_frame, t):
        frame = get_frame(t)
        idx = min(int(t * clip_fps), total_frames - 1)
        cx = max(half, min(clip_width - half, smoothed.get(idx, center)))
        x1 = cx - half
        return frame[:, x1: x1 + target_width]

    return crop_frame


def _make_title_clip(text, clip_width, duration, font_path=None, font_size=55,
                     text_color=(255, 255, 255), stroke_color=(0, 0, 0), y_offset=50, anchor_mode='top'):
    max_text_width = clip_width - 24

    if not font_path:
        for path in ['C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf']:
            try:
                ImageFont.truetype(path, 10)
                font_path = path
                break
            except OSError:
                pass

    if font_path:
        font = ImageFont.truetype(font_path, font_size)
        while font_size > 16:
            bbox = font.getbbox(text)
            if (bbox[2] - bbox[0]) <= max_text_width:
                break
            font_size -= 2
            font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    bar_height = font_size + 50
    img = Image.new('RGBA', (clip_width, bar_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    tc = tuple(text_color) + (255,)
    sc = tuple(stroke_color) + (255,)
    cx, cy = clip_width // 2, bar_height // 2
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)]:
        draw.text((cx + dx, cy + dy), text, font=font, fill=sc, anchor='mm')
    draw.text((cx, cy), text, font=font, fill=tc, anchor='mm')

    if anchor_mode == 'bottom':
        actual_y = y_offset - bar_height
    else:
        actual_y = y_offset

    return (
        ImageClip(np.array(img), ismask=False)
        .set_position(('center', actual_y))
        .set_duration(duration)
    )

def _make_subtitle_clip(text, clip_width, duration, font_path=None, font_size=40,
                        text_color=(255, 255, 0), stroke_color=(0, 0, 0), y_offset=800):
    if not font_path:
        for path in ['C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf']:
            try:
                ImageFont.truetype(path, 10)
                font_path = path
                break
            except OSError:
                pass

    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    
    char_width = font_size * 0.55
    max_chars = max(10, int((clip_width * 0.85) / char_width))
    wrapped_text = textwrap.fill(text, width=max_chars)
    lines = wrapped_text.split('\n')
    
    line_height = font_size * 1.2
    img_height = int(len(lines) * line_height) + 20
    
    img = Image.new('RGBA', (clip_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    tc = tuple(text_color) + (255,)
    sc = tuple(stroke_color) + (255,)
    cx = clip_width // 2
    
    for i, line in enumerate(lines):
        cy = int(10 + i * line_height + font_size / 2)
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)]:
            draw.text((cx + dx, cy + dy), line, font=font, fill=sc, anchor='mm')
        draw.text((cx, cy), line, font=font, fill=tc, anchor='mm')
        
    actual_y = y_offset - img_height
    return (
        ImageClip(np.array(img), ismask=False)
        .set_duration(duration)
        .set_position(('center', actual_y))
    )


def _add_logo(clip, logo_path, position='top-right', padding=20):
    if not logo_path or not os.path.exists(logo_path):
        return clip
    try:
        logo_img = Image.open(logo_path).convert('RGBA')
        cw, ch = clip.size
        max_w = int(cw * 0.20)
        if logo_img.width > max_w:
            ratio = max_w / logo_img.width
            logo_img = logo_img.resize((max_w, int(logo_img.height * ratio)), Image.LANCZOS)
        lw, lh = logo_img.size
        pos_map = {
            'top-left':     (padding, padding),
            'top-right':    (cw - lw - padding, padding),
            'bottom-left':  (padding, ch - lh - padding),
            'bottom-right': (cw - lw - padding, ch - lh - padding),
        }
        logo_clip = (
            ImageClip(np.array(logo_img), ismask=False)
            .set_position(pos_map.get(position, pos_map['top-right']))
            .set_duration(clip.duration)
        )
        return CompositeVideoClip([clip, logo_clip])
    except Exception as e:
        print(f"Warning: Could not apply logo ({e}). Continuing without it.")
        return clip


def cut_and_crop_video(video_filepath, start_time, end_time, output_filename="final_clip.mp4",
                       title_text="", style=None, platform="tiktok", transcript=None):
    if style is None:
        style = {}

    spec = PLATFORMS.get(platform, PLATFORMS["tiktok"])
    aspect_w, aspect_h = spec["aspect_w"], spec["aspect_h"]
    title_y = spec["title_y"]
    print(f"Platform: {platform} ({aspect_w}:{aspect_h})")

    if not os.path.exists(video_filepath):
        print(f"ERROR: Could not find video file: {video_filepath}")
        return None

    if start_time >= end_time:
        print("ERROR: Start time must be before end time.")
        return None

    print(f"\nLoading {video_filepath} to cut from {start_time}s to {end_time}s...")

    try:
        video = VideoFileClip(video_filepath)

        if end_time > video.duration:
            print(f"Warning: End time ({end_time}) exceeds video length ({video.duration}). Adjusting...")
            end_time = video.duration

        clip = video.subclip(start_time, end_time)
        w, h = clip.size
        target_width = min(int(h * aspect_w / aspect_h), w)
        if target_width % 2 != 0:
            target_width += 1

        # Dynamic face-following crop
        crop_strategy = style.get('crop_strategy', 'auto')
        positions = []
        
        if crop_strategy not in ['letterbox', 'split_screen', 'blur_bg']:
            print("Detecting faces for dynamic framing...")
            positions = _detect_face_positions(video_filepath, start_time, end_time, video.fps)

        if positions:
            print(f"Face tracking: {len(positions)} sample(s) found. Applying dynamic crop...")
            total_frames = int(clip.duration * clip.fps) + 1
            crop_fn = _build_crop_func(positions, w, target_width, clip.fps, total_frames)
            vertical_clip = clip.fl(crop_fn)
        elif crop_strategy == 'split_screen':
            print("Applying stacked 16:9 split-screen format...")
            from moviepy.editor import ColorClip
            import moviepy.video.fx.all as vfx
            import random
            
            bg_clip = ColorClip(size=(target_width, h), color=(0, 0, 0), duration=clip.duration)
            top_clip = clip.resize(width=target_width)
            
            # --- 2. BOTTOM CLIP (Retention Video) ---
            category = style.get('retention_category', 'high_stimulus')
            category_dir = os.path.join("resources", "retention", category)
            
            retention_path = None
            if os.path.exists(category_dir):
                videos = [f for f in os.listdir(category_dir) if f.endswith('.mp4')]
                if videos:
                    chosen_video = random.choice(videos)
                    retention_path = os.path.join(category_dir, chosen_video)
            
            if not retention_path and os.path.exists("resources/retention.mp4"):
                retention_path = "resources/retention.mp4"
                
            if retention_path:
                print(f"Using retention footage: {retention_path}")
                ret_clip = VideoFileClip(retention_path).without_audio()
                
                # Loop or subclip retention video to match duration
                if ret_clip.duration < clip.duration:
                    ret_clip = ret_clip.fx(vfx.loop, duration=clip.duration)
                else:
                    max_start = max(0, ret_clip.duration - clip.duration)
                    start_t = random.uniform(0, max_start)
                    ret_clip = ret_clip.subclip(start_t, start_t + clip.duration)
                
                ret_clip = ret_clip.resize(width=target_width)
                
                # --- PRECISE SPACING MATH ---
                y_title_bottom = title_y + 110
                y_watermark_top = h - 100
                
                # Reserve space for subtitles if they are enabled
                if transcript and style.get('use_subtitles', True):
                    y_content_bottom = y_watermark_top - 150
                else:
                    y_content_bottom = y_watermark_top
                    
                avail_h = y_content_bottom - y_title_bottom
                
                stack_h = top_clip.h + ret_clip.h
                if stack_h > avail_h - 40:
                    ret_target_h = avail_h - 40 - top_clip.h
                    if ret_clip.h > ret_target_h:
                        y1 = max(0, (ret_clip.h - ret_target_h) // 2 - 50)
                        ret_clip = ret_clip.crop(y1=y1, y2=y1 + ret_target_h)
                    else:
                        ret_clip = ret_clip.resize(height=ret_target_h)
                    stack_h = top_clip.h + ret_clip.h
                
                y_main = y_title_bottom + (avail_h - stack_h) // 2
                y_ret = y_main + top_clip.h
                
                # Dynamically set subtitle_y so it perfectly centers in the space below the video
                bottom_of_video = y_ret + ret_clip.h
                style['subtitle_y'] = bottom_of_video + (y_watermark_top - bottom_of_video) // 2 + 50
                
                # --- 3. COMPOSITE ---
                vertical_clip = CompositeVideoClip([
                    bg_clip,
                    top_clip.set_position(("center", y_main)),
                    ret_clip.set_position(("center", y_ret))
                ], size=(target_width, h)).set_audio(clip.audio)
            else:
                print("Retention footage not found. Falling back to simple center crop.")
                vertical_clip = CompositeVideoClip([bg_clip, top_clip.set_position("center")], size=(target_width, h)).set_audio(clip.audio)
        elif crop_strategy == 'blur_bg':
            print("Applying blurred background format...")
            import cv2
            def fast_blur(image):
                return cv2.GaussianBlur(image, (71, 71), 0)
                
            resized_clip = clip.resize(width=target_width)
            
            bg_clip = clip.resize(height=h)
            x_center = bg_clip.w / 2
            bg_clip = bg_clip.crop(x1=x_center - target_width/2, y1=0, x2=x_center + target_width/2, y2=h)
            bg_clip = bg_clip.fl_image(fast_blur)
            
            vertical_clip = CompositeVideoClip([bg_clip, resized_clip.set_position("center")]).set_audio(clip.audio)
        else:
            print("No faces detected. Falling back to letterbox format to preserve graphics...")
            from moviepy.editor import ColorClip
            resized_clip = clip.resize(width=target_width)
            bg_clip = ColorClip(size=(target_width, h), color=(15, 15, 15), duration=clip.duration)
            vertical_clip = CompositeVideoClip([bg_clip, resized_clip.set_position("center")]).set_audio(clip.audio)

        # Title overlay
        if title_text:
            try:
                vw, _ = vertical_clip.size
                txt_clip = _make_title_clip(
                    title_text, vw, vertical_clip.duration,
                    font_path=style.get('caption_font'),
                    font_size=style.get('caption_font_size', 55),
                    text_color=style.get('caption_color', (255, 255, 255)),
                    stroke_color=style.get('caption_stroke_color', (0, 0, 0)),
                    y_offset=title_y,
                )
                vertical_clip = CompositeVideoClip([vertical_clip, txt_clip])
                print(f"Title overlay applied: \"{title_text}\"")
            except Exception as e:
                print(f"Warning: Could not apply title overlay ({e}). Continuing without it.")

        # Subtitle overlay
        if transcript and style.get('use_subtitles', True):
            print("Generating dynamic subtitles for clip...")
            sub_clips = []
            vw, vh = vertical_clip.size
            for seg in transcript:
                seg_s = max(0.0, seg['start'] - start_time)
                seg_e = min(clip.duration, seg['end'] - start_time)
                seg_dur = seg_e - seg_s
                
                if seg_dur > 0.1:
                    words = seg['text'].strip().split()
                    chunks = [' '.join(words[i:i+4]) for i in range(0, len(words), 4)]
                    if not chunks:
                        continue
                        
                    chunk_dur = seg_dur / len(chunks)
                    for i, chunk_text in enumerate(chunks):
                        txt_clip = _make_subtitle_clip(
                            chunk_text,
                            clip_width=vw,
                            duration=chunk_dur,
                            font_path=style.get('caption_font'),
                            font_size=style.get('subtitle_font_size', 35),
                            text_color=style.get('subtitle_color', (255, 255, 255)),
                            stroke_color=style.get('subtitle_stroke_color', (0, 0, 0)),
                            y_offset=style.get('subtitle_y', vh - 110)
                        )
                        txt_clip = txt_clip.set_start(seg_s + i * chunk_dur)
                        sub_clips.append(txt_clip)
                    
            if sub_clips:
                vertical_clip = CompositeVideoClip([vertical_clip] + sub_clips)

        # Bottom Watermark for NucciTech Samples
        if style.get('use_watermark', True):
            try:
                vw, vh = vertical_clip.size
                watermark_clip = _make_title_clip(
                    "Clips by NucciTech", vw, vertical_clip.duration,
                    font_path=style.get('caption_font'),
                    font_size=35,
                    text_color=(180, 180, 180),
                    stroke_color=(0, 0, 0),
                    y_offset=vh - 15,
                    anchor_mode='bottom'
                )
                vertical_clip = CompositeVideoClip([vertical_clip, watermark_clip])
            except Exception as e:
                pass

        # Logo overlay
        vertical_clip = _add_logo(
            vertical_clip,
            logo_path=style.get('logo_path'),
            position=style.get('logo_position', 'top-right'),
        )

        print(f"Exporting final clip to {output_filename}...")
        vertical_clip.write_videofile(
            output_filename,
            fps=clip.fps,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            ffmpeg_params=['-pix_fmt', 'yuv420p'],
            logger=None
        )

        # Export audio alongside video
        mp3_path = output_filename.replace('.mp4', '.mp3')
        try:
            vertical_clip.audio.write_audiofile(mp3_path, fps=44100, logger=None)
            print(f"Audio exported: {mp3_path}")
        except Exception as e:
            print(f"Warning: Could not export audio ({e}).")

        video.close()
        vertical_clip.close()

        print(f"\nSUCCESS! Vertical clip saved as: {output_filename}")
        return output_filename

    except Exception as e:
        print(f"\nCRITICAL ERROR during video editing: {e}")
        return None


# --- TESTING AREA ---
if __name__ == "__main__":
    test_video = "test_video.mp4"
    test_start = 0.0
    test_end = 5.0

    cut_and_crop_video(test_video, test_start, test_end)
