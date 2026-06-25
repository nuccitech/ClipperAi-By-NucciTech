import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
from moviepy.editor import VideoFileClip

def extract_audio(video_filepath, audio_filepath="temp_audio.mp3"):
    if not os.path.exists(video_filepath):
        print(f"ERROR: Could not find {video_filepath}.")
        return None

    print(f"Extracting audio from {video_filepath}...")
    try:
        video = VideoFileClip(video_filepath)
        video.audio.write_audiofile(audio_filepath, logger=None)
        video.close()
        return audio_filepath
    except Exception as e:
        print(f"ERROR extracting audio: {e}")
        return None


class _Segment:
    """Matches the pipeline's expected segment interface."""
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _MergedTranscript:
    """Matches the pipeline's expected transcript interface."""
    def __init__(self, text, segments):
        self.text = text
        self.segments = segments


def get_transcript(audio_filepath):
    if not os.path.exists(audio_filepath):
        print(f"\nERROR: Audio file {audio_filepath} not found!")
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_key_here":
        print("\nERROR: Missing GROQ_API_KEY in .env file.")
        return None

    print("\nSending audio to Groq Cloud (whisper-large-v3)...")
    try:
        client = Groq(api_key=api_key)
        
        with open(audio_filepath, "rb") as file:
            transcription = client.audio.transcriptions.create(
              file=(os.path.basename(audio_filepath), file.read()),
              model="whisper-large-v3",
              response_format="verbose_json"
            )
            
        # The groq response is a pydantic model or dict. In python SDK, it returns an object.
        # However, verbose_json provides `.segments` directly.
        all_segments = []
        if hasattr(transcription, "segments"):
            for seg in transcription.segments:
                all_segments.append(_Segment(
                    start=seg.get("start") if isinstance(seg, dict) else seg.start,
                    end=seg.get("end") if isinstance(seg, dict) else seg.end,
                    text=seg.get("text") if isinstance(seg, dict) else seg.text
                ))
        
        # If text is available at top level
        full_text = transcription.text if hasattr(transcription, "text") else ""
            
        print("SUCCESS! Transcription complete in seconds via Groq.")
        return _MergedTranscript(full_text, all_segments)
        
    except Exception as e:
        print(f"\nCRITICAL ERROR during Groq transcription: {e}")
        return None


# --- TESTING AREA ---
if __name__ == "__main__":
    test_video = "test_video.mp4"
    audio_path = extract_audio(test_video)
    if audio_path:
        transcript_data = get_transcript(audio_path)
        if transcript_data:
            print(f"\nTranscript Preview: {transcript_data.text[:150]}...")
