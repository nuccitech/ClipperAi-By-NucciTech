# ClipperAi By NucciTech

An end-to-end AI-powered viral short-form video clipping engine. 

## Features
- **Intelligent Hook Analysis**: Uses OpenAI to transcribe long-form videos and extract high-retention viral hooks based on dynamic emotional profiling.
- **Dynamic Face Tracking OpenCV Engine**: Automatically frames the speaker using OpenCV Haar Cascades with intelligent smoothing for erratic movement.
- **True 50/50 Split-Screen Rendering**: Automatically composites retention footage (e.g. GTA/Minecraft) natively to 9:16 layout without graphics clipping.
- **Batch Processing Dashboard**: Real-time web UI dashboard with AJAX progress bar polling and multi-clip batch rendering.
- **Creator Outreach Pipeline**: Automatically scouts, scrapes, and verifies valid emails for creators to pitch the service.

## Architecture
- `main.py` & `server.py`: Flask-based API backend routing and core execution loop.
- `editor.py`: MoviePy + OpenCV rendering engine.
- `analyzer.py`: LLM Transcript analysis.
- `dashboard/`: Web UI for monitoring clips.

*Note: Data, caches, and secret keys are stripped from this public repository.*
