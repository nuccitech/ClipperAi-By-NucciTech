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
