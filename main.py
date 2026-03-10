from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import subprocess, json, os, re, glob

app = Flask(__name__)
CORS(app)

def run_ytdlp(args):
    try:
        r = subprocess.run(["yt-dlp"]+args, capture_output=True, text=True, timeout=30)
        return r if r.returncode == 0 else None
    except: return None

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    url = data.get("url","").strip()
    if not url or not url.startswith("http"):
        return jsonify({"error":"رابط غير صالح"}), 400
    result = run_ytdlp(["--dump-json","--no-playlist", url])
    if not result: return jsonify({"error":"تعذر تحليل الرابط"}), 400
    info = json.loads(result.stdout)
    formats = info.get("formats",[])
    qualities, seen = [], set()
    for f in reversed(formats):
        h, ext = f.get("height"), f.get("ext","mp4")
        if h and h not in seen and ext in ("mp4","webm"):
            seen.add(h)
            qualities.append({"id":f.get("format_id"),"label":f"{h}p","height":h})
    qualities.sort(key=lambda x: x["height"], reverse=True)
    return jsonify({"title":info.get("title","بدون عنوان"),"duration":info.get("duration_string",""),"thumbnail":info.get("thumbnail"),"platform":info.get("extractor_key",""),"uploader":info.get("uploader",""),"qualities":qualities[:6]})

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url","").strip()
    fmt = data.get("format_id","") or "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if not url: return jsonify({"error":"الرابط مفقود"}), 400
    result = run_ytdlp(["-f",fmt,"--merge-output-format","mp4","--no-playlist","-o","/tmp/vidshare_%(id)s.%(ext)s","--print","filename",url])
    if not result: return jsonify({"error":"فشل التحميل"}), 500
    filepath = result.stdout.strip().split("\n")[-1]
    if not os.path.exists(filepath):
        matches = glob.glob("/tmp/vidshare_*")
        if not matches: return jsonify({"error":"الملف غير موجود"}), 500
        filepath = max(matches, key=os.path.getctime)
    safe_name = re.sub(r"[^\w\-_. ]","_", os.path.basename(filepath))
    def generate():
        with open(filepath,"rb") as f:
            while chunk := f.read(1024*1024): yield chunk
        os.remove(filepath)
    return Response(generate(), headers={"Content-Disposition":f'attachment; filename="{safe_name}"', "Content-Type":"video/mp4"})

@app.route("/", methods=["GET"])
def health():
    try:
        return open("index.html").read(), 200, {"Content-Type": "text/html"}
    except:
        return jsonify({"status":"ok","message":"VidShare API running"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)))
