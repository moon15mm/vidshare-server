from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, json, os, glob

app = Flask(__name__)
CORS(app)

def run_ytdlp(args):
    try:
        extra = ["--user-agent", "Mozilla/5.0 Chrome/120", "--no-check-certificates"]
        for p in ["/app/cookies.txt", "cookies.txt"]:
            if os.path.exists(p):
                extra += ["--cookies", p]
                break
        r = subprocess.run(["yt-dlp"]+extra+args, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print("ERR:", r.stderr[-300:])
            return None
        return r
    except Exception as e:
        print(e)
        return None

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    url = data.get("url","").strip()
    if not url: return jsonify({"error":"invalid url"}), 400
    result = run_ytdlp(["--dump-json","--no-playlist",url])
    if not result: return jsonify({"error":"failed to analyze"}), 400
    info = json.loads(result.stdout)
    qualities, seen = [], set()
    for f in reversed(info.get("formats",[])):
        h, ext = f.get("height"), f.get("ext","mp4")
        if h and h not in seen and ext in ("mp4","webm"):
            seen.add(h)
            qualities.append({"id":f.get("format_id"),"label":f"{h}p","height":h})
    qualities.sort(key=lambda x:x["height"],reverse=True)
    return jsonify({"title":info.get("title",""),"duration":info.get("duration_string",""),"thumbnail":info.get("thumbnail"),"platform":info.get("extractor_key",""),"uploader":info.get("uploader",""),"qualities":qualities[:6]})

@app.route("/dl", methods=["GET"])
def dl():
    url = request.args.get("url","").strip()
    fmt = request.args.get("fmt","") or "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if not url: return jsonify({"error":"missing url"}), 400
    result = run_ytdlp(["-f",fmt,"--merge-output-format","mp4","--no-playlist","-o","/tmp/vs_%(id)s.%(ext)s",url])
    if not result: return jsonify({"error":"download failed"}), 500
    matches = sorted(glob.glob("/tmp/vs_*"), key=os.path.getctime, reverse=True)
    if not matches: return jsonify({"error":"file not found"}), 500
    return send_file(matches[0], mimetype="video/mp4", as_attachment=True, download_name="video.mp4")

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url","").strip()
    fmt = data.get("format_id","") or "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if not url: return jsonify({"error":"missing url"}), 400
    result = run_ytdlp(["-f",fmt,"--merge-output-format","mp4","--no-playlist","-o","/tmp/vs_%(id)s.%(ext)s",url])
    if not result: return jsonify({"error":"download failed"}), 500
    matches = sorted(glob.glob("/tmp/vs_*"), key=os.path.getctime, reverse=True)
    if not matches: return jsonify({"error":"file not found"}), 500
    return send_file(matches[0], mimetype="video/mp4", as_attachment=True, download_name="video.mp4")

@app.route("/", methods=["GET"])
def index():
    for p in ["/app/index.html","index.html"]:
        if os.path.exists(p):
            return open(p).read(), 200, {"Content-Type":"text/html"}
    return jsonify({"status":"ok"})


@app.route("/debug", methods=["GET"])
def debug():
    import subprocess
    url = request.args.get("url","https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    r = subprocess.run(["yt-dlp","--version"], capture_output=True, text=True)
    ver = r.stdout.strip()
    r2 = subprocess.run(["yt-dlp","--dump-json","--no-playlist",url], capture_output=True, text=True, timeout=60)
    return jsonify({"yt_dlp_version":ver,"returncode":r2.returncode,"stdout":r2.stdout[:500],"stderr":r2.stderr[:1000]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
