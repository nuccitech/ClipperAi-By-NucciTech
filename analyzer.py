import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

PLATFORM_DYNAMICS = {
    "tiktok": {
        "duration": "21–34 seconds",
        "style": "Ruthless cut. Start at the exact moment the controversial or high-energy statement begins. End the clip the instant the punchline or core point lands. No wasted setup.",
    },
    "reels": {
        "duration": "30–60 seconds",
        "style": "Polished, shareable, self-contained thought. The clip must feel complete on its own — something the audience would share to their Stories.",
    },
    "shorts": {
        "duration": "20–45 seconds",
        "style": "Structured narrative: Hook → Context → Payoff. Viewers tolerate a slightly longer setup only if there is a clear payoff at the end.",
    },
    "twitter": {
        "duration": "20–45 seconds",
        "style": "Punchy and direct. Start strong, no wasted seconds. The core point must land within the first 10 seconds.",
    },
    "linkedin": {
        "duration": "45–90 seconds",
        "style": "Professional insight with full setup and conclusion. Audience will invest more time if the value signal is clear from the first sentence.",
    },
}

HYPE_LEVELS = """
Classify each clip into one of three Hype Levels based on emotional intensity:

Level 1 — High Energy (Reactions, Rants, Heated Debates)
  Select when: high-volume peaks, interruptions, aggressive statements, or strong opinions delivered with force.
  Editing directive: Fast, aggressive pacing. Tight framing on the speaker's face. End abruptly on the mic-drop moment.

Level 2 — Medium Tension (Reveals, Bold Claims, Storytime)
  Select when: an open loop is established — a mystery or bold claim is set up and slowly resolved.
  Editing directive: Moderate pacing. Preserve slight pauses before major reveals. Medium-close up showing speaker's gestures.

Level 3 — Deep Value (Educational, Philosophical, Vulnerable)
  Select when: profound insights, step-by-step explanations, or deep emotional vulnerability.
  Editing directive: Steady, relaxed pacing. Do not rush the speaker's natural pauses. Wider frame with a very slow zoom-in as the point builds.
"""


import boto3

def find_viral_hooks(transcript_text, profile_name="default", platform="tiktok", platform_max_duration=None):
    if not transcript_text:
        print("\nERROR: The transcript provided is empty.")
        return None

    profile_path = f"profiles/{profile_name}.json"
    if os.path.exists(profile_path):
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    else:
        print(f"Warning: Profile '{profile_name}' not found. Using default.")
        profile = {
            "name": "General Creator",
            "clip_duration_min": 30,
            "clip_duration_max": 60,
            "style_notes": "Fast-paced, engaging content.",
            "analysis_instruction": "Find the most viral, interesting, or controversial segment."
        }

    if platform_max_duration is not None:
        profile["clip_duration_max"] = min(profile["clip_duration_max"], platform_max_duration)

    default_priority = ["open_loop", "emotional_peak", "story_start", "shock_moment"]
    hook_priority = profile.get("hook_priority", default_priority)
    priority_lines = "\n".join(
        f"    {i+1}. {h.replace('_', ' ').title()} — "
        + {
            "open_loop":      "a question is posed, a story starts, or a reveal is teased but not yet given",
            "emotional_peak": "visible emotional reaction, heated moment, or strong opinion stated",
            "story_start":    "beginning of a compelling narrative arc with clear stakes",
            "shock_moment":   "surprise fact, unexpected outcome, or pattern interrupt",
        }.get(h, h)
        for i, h in enumerate(hook_priority)
    )

    platform_info = PLATFORM_DYNAMICS.get(platform, PLATFORM_DYNAMICS["tiktok"])

    system_instruction = f"""
You are an elite short-form content strategist and master video editor working for {profile['name']}.
Creator style: {profile['style_notes']}

=== TARGET PLATFORM: {platform.upper()} ===
Ideal duration: {platform_info['duration']}
Editing approach: {platform_info['style']}
Hard duration rule: Every clip MUST be between {profile['clip_duration_min']} and {profile['clip_duration_max']} seconds.
- Include setup BEFORE the key moment and payoff AFTER it.
- End at a complete sentence or thought — never mid-sentence or mid-thought.
- Calculate (end - start). If it is less than {profile['clip_duration_min']} seconds, extend "end" further.

=== HYPE LEVEL FRAMEWORK ===
{HYPE_LEVELS}

=== HOOK PRIORITY (ranked for this creator) ===
{priority_lines}

=== CREATOR INSTRUCTION ===
{profile['analysis_instruction']}

=== OUTPUT ===
Return exactly 3 non-overlapping clips as a JSON object, ranked best to worst by score.
"start" and "end" MUST be exact timestamps copied from the provided segment lines — do not invent values.
You MUST choose an "emotion" string from exactly this list: {list(profile.get('emotion_titles', dict()).keys())}. Do not use any other words.
Return ONLY valid JSON. Do not use markdown blocks like ```json.

{{
    "clips": [
        {{
            "start": 0.0,
            "end": 35.0,
            "score": 9,
            "emotion": "Shock",
            "hook_type": "shock_moment",
            "hype_level": "Level 1",
            "editing_directive": "Punch in tight on face, cut aggressively, end abruptly on the mic-drop line.",
            "target_platform": "tiktok",
            "reason": "Explain exactly why this moment works for {profile['name']}'s audience."
        }}
    ]
}}
"""

    print(f"\nSending transcript to OpenRouter Analyzer (profile: {profile['name']} | platform: {platform})...")

    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key == "your_key_here":
            print("ERROR: Missing OPENROUTER_API_KEY in .env file.")
            return None
            
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": transcript_text}
            ],
            temperature=0.3
        )

        result_string = response.choices[0].message.content
        
        # Clean up markdown if the model outputs it
        if result_string.strip().startswith("```json"):
            result_string = result_string.strip().replace("```json", "", 1).replace("```", "").strip()
        elif result_string.strip().startswith("```"):
            result_string = result_string.strip().replace("```", "", 1).replace("```", "").strip()

        hook_data = json.loads(result_string)

        clips = hook_data.get("clips", [])
        print(f"SUCCESS! AWS AI found {len(clips)} clip(s):")
        for i, clip in enumerate(clips, 1):
            duration = clip['end'] - clip['start']
            print(f"  Clip {i}: {clip['start']}s–{clip['end']}s ({duration:.1f}s) | "
                  f"Score: {clip.get('score','N/A')}/10 | "
                  f"{clip.get('hype_level','N/A')} | "
                  f"{clip.get('emotion','N/A')} | "
                  f"{clip.get('hook_type','N/A')}")

        return hook_data

    except Exception as e:
        print(f"\nCRITICAL ERROR during OpenRouter analysis: {e}")
        return None


# --- TESTING AREA ---
if __name__ == "__main__":
    fake_transcript = "Welcome to the video. Today we are going to learn how to wire a dual-battery balancer..."
    find_viral_hooks(fake_transcript, profile_name="stevewilldoit", platform="tiktok")
