import os
import sys
import glob
import json
import urllib.parse
import threading
import queue
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
import boto3

# Load credentials from .env
load_dotenv()

# Try to import clipping logic
try:
    from main import run_automated_factory, api_analyze_video, api_render_clip
    from editor import PLATFORMS
    from scout import scan_channel_for_shorts, discover_competitors
except ImportError:
    run_automated_factory = None
    scan_channel_for_shorts = None
    PLATFORMS = {"tiktok": {}}

log_queue = queue.Queue()
pipeline_running = False
_pipeline_lock = threading.Lock()

class _QueueStream:
    def __init__(self, q):
        self._q = q
    def write(self, text):
        if text:
            self._q.put(text)
    def flush(self):
        pass

PORT = 8000
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")
CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach_contacts_verified.json")
TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach_tracker.json")

# Ensure dashboard directory exists
os.makedirs(DASHBOARD_DIR, exist_ok=True)

class DashboardRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(status=200)

    def do_GET(self):
        # API Routes
        if self.path == "/api/contacts":
            self.handle_get_contacts()
        elif self.path == "/api/tracker":
            self.handle_get_tracker()
        elif self.path == "/api/profiles":
            self.handle_get_profiles()
        elif self.path == "/api/logs":
            self.handle_get_logs()
        else:
            # Static file serving
            self.handle_serve_static()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode('utf-8'))
            return

        if self.path == "/api/tracker":
            self.handle_post_tracker(data)
        elif self.path == "/api/contacts":
            self.handle_post_contacts(data)
        elif self.path == "/api/generate_strategy":
            self.handle_post_generate_strategy(data)
        elif self.path == "/api/run_pipeline":
            self.handle_post_run_pipeline(data)
        elif self.path == '/api/gatekeeper':
            self.handle_post_gatekeeper()
        elif self.path == '/api/scout':
            self.handle_post_scout(data)
        elif self.path == "/api/train":
            self.handle_post_train(data)
        elif self.path == "/api/update_profile":
            self.handle_post_update_profile(data)
        elif self.path == "/api/pipeline/analyze":
            self.handle_post_pipeline_analyze(data)
        elif self.path == "/api/pipeline/render":
            self.handle_post_pipeline_render(data)
        elif self.path == "/api/pipeline/batch_render":
            self.handle_post_pipeline_batch_render(data)
        else:
            self._set_headers(status=404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def handle_post_pipeline_batch_render(self, data):
        def _run_batch():
            global pipeline_running
            with _pipeline_lock:
                if pipeline_running: return
                pipeline_running = True
            old_stdout = sys.stdout
            sys.stdout = _QueueStream(log_queue)
            try:
                import main
                main.api_batch_render_clips(data)
            except Exception as e:
                print(f"Pipeline batch error: {e}")
            finally:
                sys.stdout = old_stdout
                with _pipeline_lock:
                    pipeline_running = False

        import threading
        threading.Thread(target=_run_batch, daemon=True).start()
        self._set_headers()
        self.wfile.write(json.dumps({"success": True, "message": "Batch pipeline started"}).encode('utf-8'))



    def handle_post_update_profile(self, data):
        profile = data.get("profile")
        crop_strategy = data.get("crop_strategy")
        if not profile:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing profile"}).encode('utf-8'))
            return
            
        path = os.path.join("profiles", f"{profile}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                prof_data = json.load(f)
            prof_data["crop_strategy"] = crop_strategy
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prof_data, f, indent=4)
            self._set_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        else:
            self._set_headers(status=404)
            self.wfile.write(json.dumps({"error": "Profile not found"}).encode('utf-8'))

    def handle_post_pipeline_analyze(self, data):
        youtube_url = data.get("youtube_url")
        profile = data.get("profile", "default")
        platform = data.get("platform", "tiktok")
        if not youtube_url:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing youtube_url"}).encode('utf-8'))
            return
            
        def _run_analyze():
            global pipeline_running
            with _pipeline_lock:
                if pipeline_running: return
                pipeline_running = True
            
            # Redirect stdout to logs temporarily
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = _QueueStream(log_queue)
            sys.stderr = _QueueStream(log_queue)
            
            try:
                print(f"\n--- STARTING ANALYSIS FOR: {youtube_url} ---")
                res = api_analyze_video(youtube_url, profile, platform)
                # Send a special JSON flag to the logs so the frontend can catch it
                print(f"__ANALYZE_RESULT__={json.dumps(res)}")
                print("\n--- ANALYSIS COMPLETE ---")
            except Exception as e:
                print(f"\nERROR in analysis: {e}")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                with _pipeline_lock:
                    pipeline_running = False

        threading.Thread(target=_run_analyze).start()
        self._set_headers()
        self.wfile.write(json.dumps({"status": "started"}).encode('utf-8'))

    def handle_post_pipeline_render(self, data):
        video_id = data.get("video_id")
        video_filepath = data.get("video_filepath")
        clip_data = data.get("clip_data")
        profile_name = data.get("profile_name")
        platform = data.get("platform")
        style_overrides = data.get("style_overrides", {})
        
        if not all([video_id, video_filepath, clip_data, profile_name, platform]):
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing required fields"}).encode('utf-8'))
            return
            
        def _run_render():
            global pipeline_running
            with _pipeline_lock:
                if pipeline_running: return
                pipeline_running = True
            
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = _QueueStream(log_queue)
            sys.stderr = _QueueStream(log_queue)
            
            try:
                print(f"\n--- STARTING RENDER FOR {video_id} ---")
                res = api_render_clip(video_id, video_filepath, clip_data, profile_name, platform, style_overrides)
                if "error" in res:
                    print(f"Render Error: {res['error']}")
                else:
                    print(f"\nSUCCESS! Video saved as: {res['file']}")
            except Exception as e:
                print(f"\nERROR in rendering: {e}")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                with _pipeline_lock:
                    pipeline_running = False

        threading.Thread(target=_run_render).start()
        self._set_headers()
        self.wfile.write(json.dumps({"status": "started"}).encode('utf-8'))

    def handle_get_contacts(self):
        if os.path.exists(CONTACTS_FILE):
            with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            self._set_headers()
            self.wfile.write(content.encode('utf-8'))
        else:
            self._set_headers(status=404)
            self.wfile.write(json.dumps({"error": "Contacts file not found. Run finder first."}).encode('utf-8'))

    def handle_get_tracker(self):
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            self._set_headers()
            self.wfile.write(content.encode('utf-8'))
        else:
            self._set_headers()
            self.wfile.write(json.dumps({}).encode('utf-8'))

    def handle_get_profiles(self):
        paths = glob.glob("profiles/*.json")
        profiles = []
        profile_styles = {}
        for p in sorted(paths):
            name = os.path.splitext(os.path.basename(p))[0]
            profiles.append(name)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    profile_styles[name] = data.get("crop_strategy", "auto")
            except:
                profile_styles[name] = "auto"
                
        platforms = list(PLATFORMS.keys())
        self._set_headers()
        self.wfile.write(json.dumps({
            "profiles": profiles, 
            "platforms": platforms,
            "profile_styles": profile_styles
        }).encode('utf-8'))

    def handle_get_logs(self):
        global pipeline_running
        logs = []
        try:
            while True:
                logs.append(log_queue.get_nowait())
        except queue.Empty:
            pass
        self._set_headers()
        self.wfile.write(json.dumps({"logs": "".join(logs), "running": pipeline_running}).encode('utf-8'))

    def handle_post_run_pipeline(self, data):
        global pipeline_running
        url = data.get("url")
        profile = data.get("profile", "default")
        platform = data.get("platform", "tiktok")

        if not url:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing URL"}).encode('utf-8'))
            return

        with _pipeline_lock:
            if pipeline_running:
                self._set_headers(status=400)
                self.wfile.write(json.dumps({"error": "Pipeline already running"}).encode('utf-8'))
                return
            pipeline_running = True
        log_queue.put(f"\n{'='*50}\nStarting pipeline for {url}\nProfile: {profile} | Platform: {platform}\n\n")

        def worker():
            global pipeline_running
            old_stdout = sys.stdout
            sys.stdout = _QueueStream(log_queue)
            try:
                if run_automated_factory:
                    run_automated_factory(url, profile_name=profile, platform=platform)
                else:
                    print("ERROR: Could not import clipping modules.")
            except Exception as e:
                print(f"\nFATAL ERROR: {e}\n")
            finally:
                sys.stdout = old_stdout
                with _pipeline_lock:
                    pipeline_running = False
                log_queue.put("\n--- Pipeline Finished ---\n")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        self._set_headers()
        self.wfile.write(json.dumps({"status": "started"}).encode('utf-8'))

    def handle_post_train(self, data):
        global pipeline_running
        short_url = data.get("short_url")
        source_url = data.get("source_url")

        if not short_url or not source_url:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing short_url or source_url"}).encode('utf-8'))
            return

        with _pipeline_lock:
            if pipeline_running:
                self._set_headers(status=400)
                self.wfile.write(json.dumps({"error": "Pipeline already running"}).encode('utf-8'))
                return
            pipeline_running = True
        log_queue.put(f"\n{'='*50}\nStarting Clone & Train Pipeline...\nViral Short: {short_url}\nSource Podcast: {source_url}\n\n")

        def worker():
            global pipeline_running
            old_stdout = sys.stdout
            sys.stdout = _QueueStream(log_queue)
            sys.stderr = sys.stdout
            try:
                import time
                import subprocess
                timestamp = int(time.time())
                out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "training_data", str(timestamp))
                os.makedirs(out_dir, exist_ok=True)
                
                print(f"[{timestamp}] Building dataset in {out_dir}")
                
                meta_path = os.path.join(out_dir, "metadata.json")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump({"short_url": short_url, "source_url": source_url, "timestamp": timestamp}, f, indent=2)
                
                print(f"\n--- Downloading Viral Short (High Quality) ---")
                subprocess.run(["yt-dlp", "-f", "bestvideo[height<=1080]+bestaudio/best", "-o", os.path.join(out_dir, "viral_short.%(ext)s"), short_url], check=True)
                
                print(f"\n--- Downloading Source Podcast (720p to save space) ---")
                subprocess.run(["yt-dlp", "-f", "bestvideo[height<=720]+bestaudio/best", "-o", os.path.join(out_dir, "source_podcast.%(ext)s"), source_url], check=True)
                
                print(f"\n\n{'='*50}\nSUCCESS: Training data saved to {out_dir}\nReady for AI processing!\n")
            except Exception as e:
                print(f"ERROR in Clone & Train: {e}")
            finally:
                sys.stdout = old_stdout
                sys.stderr = sys.__stderr__
                with _pipeline_lock:
                    pipeline_running = False

        threading.Thread(target=worker, daemon=True).start()
        self._set_headers()
        self.wfile.write(json.dumps({"success": True, "status": "started"}).encode('utf-8'))

    def handle_post_gatekeeper(self):
        """Mock gatekeeper search using simulated LinkedIn scraping"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        channel_name = data.get('channel_name', 'Unknown')
        
        # Load the user's LinkedIn cookies to bypass authwall
        results = []
        try:
            import http.cookiejar
            import urllib.request
            import urllib.parse
            import re
            import os
            
            cookie_file = os.path.join(os.path.dirname(__file__), "www.linkedin.com_cookies.txt")
            if os.path.exists(cookie_file):
                print(f"[Gatekeeper] Using exported LinkedIn cookies from {cookie_file}...")
                cj = http.cookiejar.MozillaCookieJar(cookie_file)
                cj.load(ignore_discard=True, ignore_expires=True)
                
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                opener.addheaders = [
                    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36')
                ]
                
                query = urllib.parse.quote(f"{channel_name} Editor OR Producer OR Manager")
                url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
                response = opener.open(url)
                html = response.read().decode('utf-8')
                
                # Simple regex fallback to find names in LinkedIn's JSON payload
                # Looking for: "title":{"text":"Jamie Vernon"}
                matches = re.findall(r'"title":\{"text":"([^"]+)"\}', html)
                
                # Filter out generic UI elements
                valid_names = [m for m in matches if m not in ["LinkedIn", "Search", "Messaging", "Notifications", "Me", "Work", "Home"]]
                
                for name in list(set(valid_names))[:3]:
                    results.append({
                        "name": f"{name} (Extracted via Cookie)", 
                        "url": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(name)}"
                    })
        except Exception as e:
            print(f"[Gatekeeper] Cookie scraping failed: {e}")
            
        # Fallback to mock data if cookie scraping fails or returns empty
        if not results:
            results = [
                {"name": f"Lead Editor @ {channel_name}", "url": "https://linkedin.com/in/demo-editor"},
                {"name": f"Content Manager | {channel_name}", "url": "https://linkedin.com/in/demo-manager"}
            ]
            
            if "rogan" in channel_name.lower() or "powerful" in channel_name.lower():
                results.insert(0, {"name": "Jamie Vernon - Producer & Editor at JRE", "url": "https://linkedin.com/in/jamievernon"})
            
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "gatekeepers": results}).encode('utf-8'))

    def handle_post_scout(self, data):
        query = data.get("url") or data.get("query")
        mode = data.get("mode", "channel")
        
        if not query:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing query or URL"}).encode('utf-8'))
            return

        if not scan_channel_for_shorts:
            self._set_headers(status=500)
            self.wfile.write(json.dumps({"error": "Scout module not loaded"}).encode('utf-8'))
            return
            
        debug_log = {"query": query, "mode": mode}
        
        if mode == "search" and discover_competitors:
            results = discover_competitors(query, max_videos=20)
            debug_log["competitors_count"] = len(results)
            with open("scout_debug.json", "w") as f:
                json.dump(debug_log, f)
            print(f"DEBUG: discover_competitors returned {len(results)} items")
            self._set_headers()
            self.wfile.write(json.dumps({"competitors": results}).encode('utf-8'))
            return
            
        shorts = scan_channel_for_shorts(query, max_videos=20)
        debug_log["shorts_count"] = len(shorts)
        with open("scout_debug.json", "w") as f:
            json.dump(debug_log, f)
        print(f"DEBUG: scan_channel_for_shorts returned {len(shorts)} items")
        self._set_headers()
        self.wfile.write(json.dumps({"shorts": shorts}).encode('utf-8'))

    def handle_post_tracker(self, data):
        tracker_data = {}
        if os.path.exists(TRACKER_FILE):
            try:
                with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                    tracker_data = json.load(f)
            except Exception:
                pass
        
        url = data.get("url")
        if not url:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing URL"}).encode('utf-8'))
            return
            
        tracker_data[url] = {
            "contacted": data.get("contacted", False),
            "contacted_date": data.get("contacted_date"),
            "outreach_channel": data.get("outreach_channel", ""),
            "notes": data.get("notes", ""),
            "custom_strategy": data.get("custom_strategy", ""),
            "follow_up_date": data.get("follow_up_date", "")
        }
        
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker_data, f, indent=2, ensure_ascii=False)
            
        self._set_headers()
        self.wfile.write(json.dumps({"status": "success", "data": tracker_data[url]}).encode('utf-8'))

    def handle_post_generate_strategy(self, data):
        url = data.get("url")
        profile = data.get("profile", "")
        
        if not profile:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing profile name"}).encode('utf-8'))
            return

        try:
            print(f"[AWS Bedrock] Calling Custom Model for {profile}...")
            
            # Setup Boto3 Client (automatically uses the credentials loaded from .env)
            client = boto3.client("bedrock-runtime", region_name="us-east-1")
            
            # The custom model ARN provided by the user
            model_arn = os.getenv("BEDROCK_MODEL_ARN")
            if not model_arn:
                raise ValueError("Missing BEDROCK_MODEL_ARN in .env")
            
            # Create the prompt instructing the custom model
            prompt = f"Write a frictionless 3-sentence outreach pitch for the YouTube creator: {profile}. Mention that we generated 3 free polished shorts for them using our AI system and include a placeholder for a [Free Sample Link]. Keep it highly converting and brief."
            
            # Invoke the custom model using the converse API
            response = client.converse(
                modelId=model_arn,
                messages=[{"role": "user", "content": [{"text": prompt}]}]
            )
            
            # Extract the AI's response text
            generated_text = response['output']['message']['content'][0]['text']
            
            strategy = {
                "outreach_angle": "Custom AWS Model Strategy",
                "pitch_script": generated_text.strip(),
                "next_steps": ["If no reply in 72 hours, send the 1-line bump email."]
            }

            tracker_data = {}
            if os.path.exists(TRACKER_FILE):
                try:
                    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                        tracker_data = json.load(f)
                except Exception:
                    pass
            
            if url not in tracker_data:
                tracker_data[url] = {}
            
            tracker_data[url]["custom_strategy"] = strategy
            
            with open(TRACKER_FILE, "w", encoding="utf-8") as f:
                json.dump(tracker_data, f, indent=2, ensure_ascii=False)
                
            self._set_headers()
            self.wfile.write(json.dumps(strategy).encode('utf-8'))
            
        except Exception as e:
            print(f"[AWS Error] {e}")
            self._set_headers(status=500)
            self.wfile.write(json.dumps({"error": f"AWS Custom Model failed: {str(e)}"}).encode('utf-8'))

    def handle_post_contacts(self, data):
        channel_name = data.get("channel_name")
        channel_url = data.get("channel_url")
        
        if not channel_name or not channel_url:
            self._set_headers(status=400)
            self.wfile.write(json.dumps({"error": "Missing name or url"}).encode('utf-8'))
            return

        contacts = {}
        if os.path.exists(CONTACTS_FILE):
            try:
                with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                    contacts = json.load(f)
            except:
                pass
                
        if channel_url not in contacts:
            contacts[channel_url] = {
                "profile": "scout_lead",
                "target_platform": "shorts",
                "channel_name": channel_name,
                "channel_url": channel_url,
                "emails": [],
                "socials": {
                    "instagram": "", "twitter": "", "linkedin": "", "tiktok": "", "facebook": "", "linktree": "", "patreon": ""
                },
                "websites": [],
                "verified_emails": [],
                "invalid_emails": []
            }
            with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=2)
                
        self._set_headers()
        self.wfile.write(json.dumps({"success": True}).encode('utf-8'))

    def handle_serve_static(self):
        # Default to index.html
        path = self.path.split('?')[0]
        if path == "/":
            path = "/index.html"
            
        file_path = os.path.join(DASHBOARD_DIR, path.lstrip("/"))
        
        # Verify file is inside the dashboard directory to prevent traversal attacks
        real_file_path = os.path.realpath(file_path)
        real_dashboard_dir = os.path.realpath(DASHBOARD_DIR)
        
        if not real_file_path.startswith(real_dashboard_dir):
            self._set_headers(content_type="text/plain", status=403)
            self.wfile.write(b"Forbidden")
            return
            
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Guess content type
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml"
            }
            content_type = content_types.get(ext, "application/octet-stream")
            
            with open(file_path, "rb") as f:
                content = f.read()
                
            self._set_headers(content_type=content_type)
            self.wfile.write(content)
        else:
            self._set_headers(content_type="text/plain", status=404)
            self.wfile.write(b"Not Found")

def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, DashboardRequestHandler)
    print(f"Dashboard server running locally at: http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run()
