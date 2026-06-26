# ClipperAi By NucciTech

An end-to-end AI-powered viral short-form video clipping engine. 

## Features
- **Intelligent Hook Analysis**: Uses OpenAI to transcribe long-form videos and extract high-retention viral hooks based on dynamic emotional profiling.
- **Infinite Audio Chunking**: Automatically slices infinite-length audio streams into 25-minute segments for parallel Whisper API transcription, completely bypassing payload constraints.
- **V2 MediaPipe 3D Face Tracking**: Replaced legacy Haar Cascades with Google's MediaPipe FaceDetection, utilizing a 468-point 3D mesh for flawless tracking.
- **Cinematic Gimbal Smoothing**: Custom Exponential Moving Average (EMA) algorithm simulating a professional camera operator's ease-in/ease-out pan dynamics.
- **True 50/50 Split-Screen Rendering**: Automatically composites retention footage (e.g. GTA/Minecraft) natively to 9:16 layout without graphics clipping.
- **Batch Processing Dashboard**: Real-time web UI dashboard with AJAX progress bar polling and multi-clip batch rendering.
- **Creator Outreach Pipeline**: Automatically scouts, scrapes, and verifies valid emails for creators to pitch the service.

## Architecture
- `main.py` & `server.py`: Flask-based API backend routing and core execution loop.
- `editor.py`: MoviePy + OpenCV rendering engine.
- `analyzer.py`: LLM Transcript analysis.
- `dashboard/`: Web UI for monitoring clips.

*Note: Data, caches, and secret keys are stripped from this public repository.*

## Getting Started

**1. Clone and install dependencies**
```bash
git clone https://github.com/nuccitech/clipperai-by-nuccitech.git
cd clipperai-by-nuccitech
pip install -r requirements.txt
```

**2. Configure environment variables**
```bash
cp .env.example .env
# Fill in your API keys in .env
```

**3. Run the pipeline**
```bash
# From a YouTube URL
python main.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --profile SampleCreator --platform tiktok

# From a local file
python main.py /path/to/video.mp4 --profile SampleCreator --platform reels
```

**4. (Optional) Launch the web dashboard**
```bash
python server.py
# Open dashboard/index.html in your browser
```

Clips are exported to `output/<profile_name>/`. A report and full transcript are saved alongside each batch.

## Creator Profiles

Profiles live in `profiles/` as JSON files and control clip style, duration, caption font, and the AI's analysis persona. See `profiles/SampleCreator.json` for a reference template.
