# taixiu.py
# Flask Web Service Tài Xỉu auto update + pattern learning
# Hoạt động ổn định trên Python 3.14.x / Render.com
# Fix lỗi tiếng Việt & pattern ảo

import os
import json
import time
import threading
import requests
from flask import Flask, jsonify

# ------------------- CẤU HÌNH -------------------
API_URL = "https://api-agent.gowsazhjo.net/glms/v1/notify/taixiu?platform_id=b5&gid=0"
PATTERN_FILE = "pattern.json"
LAST_FILE = "last_session.json"
UPDATE_INTERVAL = 5  # giây
PORT = int(os.environ.get("PORT", 8080))  # Render sẽ tự set PORT

# ------------------- BIẾN TOÀN CỤC -------------------
app = Flask(__name__)
latest_result = {}
lock = threading.Lock()


# ------------------- HÀM TIỆN ÍCH -------------------
def safe_load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Lỗi đọc {path}: {e}")
    return default


def safe_save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Lỗi ghi {path}: {e}")


# ------------------- QUẢN LÝ PATTERN -------------------
def load_pattern():
    data = safe_load_json(PATTERN_FILE, {"pattern": ""})
    pat = data.get("pattern", "")
    return "".join(ch for ch in pat if ch in ("t", "x"))


def save_pattern(pattern):
    safe_save_json(PATTERN_FILE, {"pattern": pattern})


def append_pattern_if_new(phien, ket_qua):
    """Chỉ lưu pattern nếu phiên chưa xử lý."""
    last = safe_load_json(LAST_FILE, {"last_phien": None})
    last_phien = last.get("last_phien")
    if phien == last_phien:
        return False

    pattern = load_pattern()
    pattern += "t" if ket_qua == "Tài" else "x"
    pattern = pattern[-1000:]  # Giữ tối đa 1000 ký tự
    save_pattern(pattern)
    safe_save_json(LAST_FILE, {"last_phien": phien})
    return True


def predict_from_pattern(pattern):
    if not pattern:
        return "Tài", "50.0%"
    t_count = pattern.count("t")
    total = len(pattern)
    p_t = (t_count / total) * 100
    if p_t >= 50:
        return "Tài", f"{p_t:.1f}%"
    return "Xỉu", f"{100 - p_t:.1f}%"


# ------------------- PHÂN TÍCH DỮ LIỆU API -------------------
def fetch_api():
    try:
        res = requests.get(API_URL, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print("❌ Lỗi fetch API:", e)
        return None


def parse_api_data(data):
    if not data or "data" not in data:
        return None

    d1 = d2 = d3 = phien = None
    for item in data["data"]:
        cmd = item.get("cmd")
        if cmd == 1003:
            d1, d2, d3 = item.get("d1"), item.get("d2"), item.get("d3")
        elif cmd == 2007:
            phien = item.get("sid")

    if phien and all(isinstance(x, int) and 1 <= x <= 6 for x in [d1, d2, d3]):
        return {"Phien": phien, "d1": d1, "d2": d2, "d3": d3}
    return None


def analyze_result(d1, d2, d3):
    tong = d1 + d2 + d3
    ket_qua = "Tài" if tong >= 11 else "Xỉu"
    return tong, ket_qua


# ------------------- CẬP NHẬT TỰ ĐỘNG -------------------
def updater_loop():
    global latest_result
    while True:
        raw = fetch_api()
        parsed = parse_api_data(raw)
        if parsed:
            d1, d2, d3 = parsed["d1"], parsed["d2"], parsed["d3"]
            tong, ket_qua = analyze_result(d1, d2, d3)
            append_pattern_if_new(parsed["Phien"], ket_qua)
            pattern = load_pattern()
            du_doan, tin_cay = predict_from_pattern(pattern)
            with lock:
                latest_result = {
                    "id": "anhbantool1",
                    "Phien": parsed["Phien"],
                    "phien_hien_tai": parsed["Phien"] + 1,
                    "Xuc_xac_1": d1,
                    "Xuc_xac_2": d2,
                    "Xuc_xac_3": d3,
                    "Tong": tong,
                    "Ket_qua": ket_qua,
                    "Pattern": pattern,
                    "Du_doan": du_doan,
                    "Do_tin_cay": tin_cay,
                }
        time.sleep(UPDATE_INTERVAL)


# ------------------- ENDPOINT FLASK -------------------
@app.route("/b52", methods=["GET"])
def get_b52():
    """Endpoint chính"""
    with lock:
        if latest_result:
            return jsonify(latest_result)
        else:
            return jsonify({"status": "Đang chờ dữ liệu..."})


@app.route("/health")
def health():
    return jsonify({"status": "alive", "time": time.strftime("%H:%M:%S")})


# ------------------- KEEPALIVE GIẢ -------------------
def keep_alive():
    """Giữ tiến trình sống bằng cách mở cổng nội bộ"""
    import socket
    s = socket.socket()
    try:
        s.bind(("0.0.0.0", 65500))
        s.listen(1)
        while True:
            time.sleep(60)
    except Exception:
        pass


# ------------------- MAIN -------------------
if __name__ == "__main__":
    threading.Thread(target=updater_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    print(f"✅ API Tài Xỉu đang chạy tại http://localhost:{PORT}/b52")
    app.run(host="0.0.0.0", port=PORT, debug=False)