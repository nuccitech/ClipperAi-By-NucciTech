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
        video.audio.write_audiofile(audio_filepath, bitrate="64k", logger=None)
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
        from moviepy.editor import AudioFileClip
        import math
        
        client = Groq(api_key=api_key)
        
        audio = AudioFileClip(audio_filepath)
        duration = audio.duration
        
        chunk_length = 1500 # 25 minutes
        num_chunks = math.ceil(duration / chunk_length)
        
        all_segments = []
        full_text = ""
        
        for i in range(num_chunks):
            start_t = i * chunk_length
            end_t = min((i + 1) * chunk_length, duration)
            
            chunk_path = f"{audio_filepath}_chunk_{i}.mp3"
            if num_chunks > 1:
                print(f"Audio exceeds 25m. Chunking: processing part {i+1} of {num_chunks}...")
                chunk_clip = audio.subclip(start_t, end_t)
                chunk_clip.write_audiofile(chunk_path, bitrate="64k", logger=None)
                target_file = chunk_path
            else:
                target_file = audio_filepath

            with open(target_file, "rb") as file:
                transcription = client.audio.transcriptions.create(
                  file=(os.path.basename(target_file), file.read()),
                  model="whisper-large-v3",
                  response_format="verbose_json"
                )
                
            if hasattr(transcription, "segments"):
                for seg in transcription.segments:
                    seg_start = (seg.get("start") if isinstance(seg, dict) else seg.start) + start_t
                    seg_end = (seg.get("end") if isinstance(seg, dict) else seg.end) + start_t
                    seg_text = seg.get("text") if isinstance(seg, dict) else seg.text
                    all_segments.append(_Segment(start=seg_start, end=seg_end, text=seg_text))
            
            if hasattr(transcription, "text"):
                full_text += transcription.text + " "
                
            # Cleanup chunk
            if num_chunks > 1 and os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except:
                    pass
                    
        audio.close()
            
        print("SUCCESS! Transcription complete via Groq.")
        return _MergedTranscript(full_text.strip(), all_segments)
        
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
