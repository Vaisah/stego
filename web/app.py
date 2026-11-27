#!/usr/bin/python3
# -*- encoding: utf-8 -*-

import glob
import hashlib
import json
import os
import re
import secrets
import subprocess
from werkzeug.utils import secure_filename
import time
from flask import Flask, render_template, request, jsonify, \
    send_from_directory, redirect, url_for, make_response, Response, \
    send_file, stream_with_context
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import crypto_utils

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://xander:xander21@mongodb:27017/flaskdb?authSource=admin"
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 Mb max (allows file encryption)
app.config['LANGUAGES'] = {
    'en': 'English',
    'fr': 'Français'
}

mongo = PyMongo(app)
db = mongo.db

# Rate limiter (in-memory storage; fine for the single-process dev server).
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[])

# Shared volume with the backend worker for custom-wordlist hand-off.
HASHJOBS_DIR = os.environ.get("HASHJOBS_DIR", "/app/hashjobs")

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = ["jpeg", "png", "bmp",
                      "gif", "tiff", "jpg", "jfif", "jpe", "tif"]


def load_i18n(request):
    """Load languages from language folder and session."""
    languages = {}
    language_list = glob.glob("language/*.json")
    for lang in language_list:
        lang_code = lang.split('/')[1].split('.')[0]
        with open(lang) as file:
            languages[lang_code] = json.load(file)
    cookie_lang = request.cookies.get('lang')
    lang_keys = app.config['LANGUAGES'].keys()
    if cookie_lang in lang_keys:
        return languages[cookie_lang]
    header_lang = request.accept_languages.best_match(lang_keys)
    if header_lang in lang_keys:
        return languages[header_lang]
    return languages["en"]


def mencoder(o):
    if type(o) == ObjectId:
        return str(o)
    return o.__str__


@app.route('/')
def home():
    return render_template('index.html', **load_i18n(request))


@app.route('/upload', methods=['POST'])
def upload_image():
    """
        @file : file
        @zsteg_ext : bool
        @zsteg_all : bool
        @use_password : bool
        @password : str
    """

    # Handle Errors
    if "file" not in request.files:
        return jsonify({"Error": "File not found."})

    file = request.files["file"]  # uploaded file
    ext = str(os.path.splitext(file.filename)[1].lower().lstrip("."))
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"Error": f"Invalid extension: {ext}"})

    # Read file content once
    file_content = file.read()
    
    # Compute informations
    hash_file = str(hashlib.md5(file_content).hexdigest())
    hash_full = hash_file
    original_name = str(file.filename)
    use_password = bool("use_password" in request.form and
                        request.form["use_password"] == "true")
    password = None
    zext_bool = bool("zsteg_ext" in request.form and
                     request.form["zsteg_ext"] == "true")
    zall_bool = bool("zsteg_all" in request.form and
                     request.form["zsteg_all"] == "true")
    if "password" in request.form:
        password = str(request.form["password"])
    if use_password:
        pwd = password.encode("utf-8")
        salt = pwd+str(zext_bool).encode("utf-8")
        salt += str(zall_bool).encode("utf-8")
        hash_full = str(hashlib.md5(file_content+salt).hexdigest())
    
    size = len(file_content)
    t = time.time()
    json_config = {
        "original_name": original_name,
        "submit_date": t,
        "last_submit_date": t,
        "source_ip": request.remote_addr,
        "status": {},
        "image": f"image.{ext}",
        "size": size,
        "md5_image": hash_file,
        "md5_full": hash_full,
        "zsteg_all": zall_bool,
        "zsteg_ext": zext_bool,
        "use_password": use_password,
        "password": password
    }

    # Create image if doesnt exist
    folder = f"{UPLOAD_FOLDER}/{hash_full}"
    if not os.path.isdir(folder):  # create folder / file if doesnt exist
        os.mkdir(folder)
        # Save the file content directly
        with open(f"{folder}/image.{ext}", "wb") as f:
            f.write(file_content)

    # Insert in DB
    db.uploads.insert_one(json_config)

    # If image did not get upload in the past
    data = list(db.status.find({"md5_full": hash_full}))
    if not len(data):
        status = {
            "md5_full": hash_full,
            "md5_image": hash_file,
            "status": {
                "foremost": None,
                "view": None,
                "exiftool": None,
                "binwalk": None,
                "zsteg": None,
                "strings": None,
                "steghide": None,
                "outguess": None
            },
            "image": f"image.{ext}",
            "zsteg_all": zall_bool,
            "zsteg_ext": zext_bool,
            "password": password
        }
        db.status.insert_one(status)

    return jsonify({"File": hash_full})

@app.route('/install.sh')
def install():
    return send_from_directory('static', 'install.sh')


@app.route('/cheatsheet')
def cheatsheet():
    return render_template('cheatsheet.html', **load_i18n(request))


@app.route('/show')
def show():
    folder = f"{UPLOAD_FOLDER}/"
    dirs = os.listdir(folder)
    return render_template('show.html', dirs=dirs, **load_i18n(request))


@app.route('/<md5_file>')
def result_file(md5_file):
    if re.findall(r"\b([a-f\d]{32}|[A-F\d]{32})\b", md5_file):
        return render_template('result.html', **load_i18n(request),
                               md5=md5_file)
    return redirect(url_for('home'))


@app.route('/info/<file>')
@app.route('/info')
def info(file=None):
    if file is not None and \
       not re.findall(r"\b([a-f\d]{32}|[A-F\d]{32})\b", file):
        return redirect(url_for('home'))
    if file is None:
        data = list(db.uploads.find())
    else:
        data = list(db.uploads.find({"md5_image": file}))
    for d in data:
        d["source_ip"] = "**redaclanguagested**"
    return Response(response=json.dumps(data, default=mencoder),
                    status=200,
                    mimetype="application/json")


@app.route('/stats')
def stats():
    data = list(db.uploads.find())
    stats, pwds, names, uploads = {}, {}, {}, {}
    n = len(data)
    for d in data:
        d["source_ip"] = "**redacted**"
        pwds[d["password"]] = pwds.get(d["password"], 0) + 1
        names[d["original_name"]] = names.get(d["original_name"], 0) + 1
        uploads[d["submit_date"]] = uploads.get(d["submit_date"], 0) + 1

    stats["total_submit"] = n
    if "" not in pwds:
        pwds[""] = 0
    stats["nb_no_passwords"] = pwds[""]
    stats["nb_passwords"] = n - stats["nb_no_passwords"]
    del pwds[""]
    stats["passwords"] = pwds
    stats["names"] = names
    stats["first_submit"] = min(uploads.keys(), default=0)
    stats["last_submit"] = max(uploads.keys(), default=0)

    return Response(response=json.dumps(stats, default=mencoder),
                    status=200,
                    mimetype="application/json")


@app.route('/stats/<file>')
def stats_file(file=None):
    if file is None or \
       not re.findall(r"\b([a-f\d]{32}|[A-F\d]{32})\b", file):
        return redirect(url_for('home'))
    data = list(db.uploads.find({"md5_full": file}))
    if not len(data):
        return redirect(url_for('home'))

    data_image = list(db.uploads.find({"md5_image": data[0]["md5_image"]}))
    data_status = list(db.status.find({"md5_full": file}))[0]

    stats, pwds, names, uploads = {}, {}, {}, {}
    n = len(data_image)
    for d in data_image:
        d["source_ip"] = "**redacted**"
        pwds[d["password"]] = pwds.get(d["password"], 0) + 1
        names[d["original_name"]] = names.get(d["original_name"], 0) + 1
        uploads[d["submit_date"]] = uploads.get(d["submit_date"], 0) + 1

    stats["size"] = d["size"]
    stats["status"] = data_status["status"]
    stats["total_submit"] = n
    if "" not in pwds:
        pwds[""] = 0
    stats["nb_no_passwords"] = pwds[""]
    stats["nb_passwords"] = n - stats["nb_no_passwords"]
    del pwds[""]
    stats["passwords"] = pwds
    stats["names"] = names
    stats["image"] = data_status["image"]
    stats["md5_image"] = data[0]["md5_image"]
    stats["first_submit"] = min(uploads.keys(), default=0)
    stats["last_submit"] = max(uploads.keys(), default=0)

    return Response(response=json.dumps(stats, default=mencoder),
                    status=200,
                    mimetype="application/json")

@app.route("/top")
def top():
    data = list(db.uploads.aggregate([
        {"$group": {"_id": "$md5_full", "count": {"$sum": 1}}}
    ]))
    stats = {}
    for d in data:
        stats[d["_id"]] = d["count"]
    sorted_stats = dict(sorted(stats.items(),
                        key=lambda item: str(item[1])+item[0],
                        reverse=True))

    return Response(response=json.dumps(sorted_stats, default=mencoder),
                    status=200,
                    mimetype="application/json")


@app.route('/lang/<lang>')
def change_lang(lang=None):
    lang_keys = app.config['LANGUAGES'].keys()
    if lang in lang_keys:
        response = make_response(redirect(request.referrer))
        response.set_cookie('lang', lang)
        return response
    return redirect(url_for('home'))


@app.route('/static/<path:path>')
def send_js(path):
    return send_from_directory('static', path)
import os
import base64
from io import BytesIO
from flask import render_template, request, flash, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import piexif


@app.route('/metadata_hide', methods=['GET', 'POST'])
def metadata_hide():
    if request.method == 'POST':
        img_file = request.files.get('image')
        payload_file = request.files.get('payload')
        field = request.form.get('field', 'Comment')  # EXIF tag name

        if not img_file or not payload_file:
            flash("Both image and payload files are required.", "error")
            return redirect(url_for('metadata_hide'))

        # Read payload and Base64-encode
        payload_bytes = payload_file.read()
        b64_text = base64.b64encode(payload_bytes).decode('ascii')

        # Load image into Pillow
        img = Image.open(img_file.stream)

        # Prepare or extract existing EXIF data
        exif_dict = {}
        if 'exif' in img.info:
            exif_dict = piexif.load(img.info['exif'])
        else:
            # Initialize an empty EXIF structure
            exif_dict = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "Interop":{}}

        # Map form field to piexif tag
        tag_map = {
            'Comment': piexif.ImageIFD.ImageDescription,
            'UserComment': piexif.ExifIFD.UserComment,
            'ImageDescription': piexif.ImageIFD.ImageDescription
        }
        tag = tag_map.get(field)
        if not tag:
            flash(f"Unsupported field: {field}", "error")
            return redirect(url_for('metadata_hide'))

        # Insert Base64 into the chosen tag
        if field == 'UserComment':
            # UserComment expects a special header, but piexif handles it for us if we prefix with ASCII\0\0\0
            exif_dict['Exif'][tag] = b'' + b64_text.encode('utf-8')
        else:
            exif_dict['0th'][tag] = b64_text.encode('utf-8')

        # Dump back to bytes and save into an in-memory buffer
        exif_bytes = piexif.dump(exif_dict)
        out_buf = BytesIO()
        img.save(out_buf, format=img.format, exif=exif_bytes)
        out_buf.seek(0)

        # Send the modified image back
        filename = f"stego_{secure_filename(img_file.filename)}"
        return send_file(
            out_buf,
            as_attachment=True,
            download_name=filename,
            mimetype=img_file.mimetype
        )
    return render_template('metadata_hide.html')


import os
import tempfile
import shutil
import subprocess
from flask import Flask, request, render_template, flash, redirect
from werkzeug.utils import secure_filename

# --- Hash cracking: dispatch to the backend worker (the "steganography way") ---
# John/Hashcat run in the backend container (they are not installed in the web
# image). The web tier only enqueues jobs in Mongo and streams progress/results
# back. See backend/modules/hashcrack.py for the worker.

CRACK_RULES = {"", "best64", "toggles", "dive"}
MAX_HASHES_PER_JOB = 1000


def _parse_hash_lines(text):
    return [s.strip() for s in (text or "").splitlines() if s.strip()]


def _wordlist_warning():
    """Return a warning string if the backend reports no default wordlist."""
    try:
        health = db.hash_meta.find_one({"_id": "health"})
    except Exception:
        return None
    if health and not health.get("wordlist_present", True):
        return (f"Default wordlist missing in the backend "
                f"({health.get('wordlist')}). Upload a wordlist or jobs will error.")
    return None


@app.route('/crack_hash', methods=['GET', 'POST'])
@limiter.limit("5 per minute", exempt_when=lambda: request.method != "POST")
def crack_hash():
    if request.method == 'GET':
        return render_template('crack_hash.html',
                               wordlist_warning=_wordlist_warning())

    # --- POST: dispatch a job (consumed by crack_hash.html via fetch) ---
    hash_text = request.form.get('hash_input', '')
    hash_file = request.files.get('hash_file')
    if hash_file and hash_file.filename:
        try:
            hash_text = hash_file.read().decode('utf-8', 'replace')
        except Exception:
            return jsonify({"error": "Could not read hash file"}), 400

    hashes = _parse_hash_lines(hash_text)
    if not hashes:
        return jsonify({"error": "No hash provided"}), 400
    if len(hashes) > MAX_HASHES_PER_JOB:
        return jsonify({"error": f"Too many hashes (max {MAX_HASHES_PER_JOB})"}), 400

    rule = (request.form.get('rule') or '').strip().lower()
    if rule not in CRACK_RULES:
        rule = ''

    # Cache check: if every hash is already cracked, return immediately (<100 ms).
    cached = {}
    for h in hashes:
        doc = db.hash_cache.find_one(
            {"_id": hashlib.sha256(h.encode()).hexdigest()})
        if doc:
            cached[h] = doc
    if len(cached) == len(hashes):
        return jsonify({
            "cached": True,
            "results": [{
                "line": h,
                "hash_type": cached[h].get("hash_type"),
                "cracked": cached[h].get("plaintext"),
                "via": cached[h].get("via"),
            } for h in hashes],
        })

    entries = [{"line": h, "hash_type": None, "cracked": None, "via": None}
               for h in hashes]
    job = {
        "created": time.time(),
        "source_ip": request.remote_addr,
        "status": "queued",
        "hashes": entries,
        "rules": rule,
        "progress": {"log": []},
        "wordlist_name": None,
        "wordlist_path": None,
    }
    job_id = db.hash_jobs.insert_one(job).inserted_id

    # Optional custom wordlist -> hand off to the backend via the shared volume.
    wordlist_file = request.files.get('wordlist')
    if wordlist_file and wordlist_file.filename:
        job_dir = os.path.join(HASHJOBS_DIR, str(job_id))
        try:
            os.makedirs(job_dir, exist_ok=True)
            wl_path = os.path.join(job_dir, "wordlist.txt")
            wordlist_file.save(wl_path)
            db.hash_jobs.update_one({"_id": job_id}, {"$set": {
                "wordlist_path": wl_path,
                "wordlist_name": secure_filename(wordlist_file.filename)}})
        except Exception as e:
            db.hash_jobs.update_one({"_id": job_id}, {"$set": {
                "status": "error", "error": f"Wordlist save failed: {e}"}})
            return jsonify({"error": "Could not store wordlist"}), 500

    return jsonify({"job_id": str(job_id)})


def _crack_results(job):
    return [{
        "line": e["line"],
        "hash_type": e.get("hash_type"),
        "cracked": e.get("cracked"),
        "via": e.get("via"),
    } for e in job.get("hashes", [])]


@app.route('/crack_status/<job_id>')
def crack_status(job_id):
    try:
        oid = ObjectId(job_id)
    except (InvalidId, TypeError):
        return jsonify({"error": "Unknown job"}), 404
    job = db.hash_jobs.find_one({"_id": oid})
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    return jsonify({
        "status": job.get("status"),
        "error": job.get("error"),
        "results": _crack_results(job),
        "log": [l.get("line") for l in job.get("progress", {}).get("log", [])],
    })


@app.route('/crack_progress/<job_id>')
def crack_progress(job_id):
    """Server-Sent Events stream of the job log until it finishes."""
    try:
        oid = ObjectId(job_id)
    except (InvalidId, TypeError):
        return jsonify({"error": "Unknown job"}), 404

    @stream_with_context
    def generate():
        sent = 0
        deadline = time.time() + 1800  # 30 min hard cap
        while time.time() < deadline:
            job = db.hash_jobs.find_one({"_id": oid})
            if not job:
                yield "event: error\ndata: \"unknown job\"\n\n"
                return
            log = job.get("progress", {}).get("log", [])
            while sent < len(log):
                yield f"data: {json.dumps(log[sent].get('line', ''))}\n\n"
                sent += 1
            status = job.get("status")
            if status in ("done", "error"):
                yield f"event: {status}\ndata: {json.dumps(status)}\n\n"
                return
            time.sleep(1)
        yield "event: timeout\ndata: \"timeout\"\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})

# --- Add countermeasures ---
from PIL import Image
import os, io, tempfile, subprocess
from flask import request, flash, redirect, url_for, send_file, render_template
from werkzeug.utils import secure_filename

def clear_lsb(img):
    """Zero out the LSBs of all channels (simple LSB scrubbing)."""
    if img.mode != 'RGB':
        img = img.convert('RGB')
    pixels = list(img.getdata())
    new_pixels = []
    for pixel in pixels:
        new_pixel = tuple((channel & ~1) for channel in pixel)
        new_pixels.append(new_pixel)
    cleaned = Image.new('RGB', img.size)
    cleaned.putdata(new_pixels)
    return cleaned

@app.route('/countermeasures', methods=['GET', 'POST'])
def apply_countermeasures():
    if request.method == 'POST':
        img_file = request.files.get('image')
        if not img_file:
            flash("Image file is required.", "error")
            return redirect(url_for('apply_countermeasures'))

        original_filename = secure_filename(img_file.filename)
        name, ext = os.path.splitext(original_filename)
        ext = ext.lower().lstrip('.')

        format_map = {
            'jpg': ('JPEG', 'image/jpeg'),
            'jpeg': ('JPEG', 'image/jpeg'),
            'png': ('PNG', 'image/png')
        }

        if ext not in format_map:
            flash("Unsupported image format. Only PNG and JPG are supported.", "error")
            return redirect(url_for('apply_countermeasures'))

        img_format, mimetype = format_map[ext]

        # Save temporarily
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, original_filename)
        img_file.save(temp_path)

        # Attempt to extract with zsteg (just to trigger detection/logs)
        if ext in ['png', 'bmp']:
            try:
                subprocess.run(['zsteg', temp_path, '--all'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

        # Attempt to extract with steghide (passwordless)
        try:
            subprocess.run(['steghide', 'extract', '-sf', temp_path, '-p', '', '-xf', os.path.join(temp_dir, 'extracted.txt')],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

        # Strip metadata + LSBs
        img = Image.open(temp_path).convert('RGB')
        img_cleaned = clear_lsb(img)

        buffer = io.BytesIO()
        img_cleaned.save(buffer, format=img_format, quality=85)
        buffer.seek(0)

        cleaned_filename = f"{name}-cleaned.{ext}"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=cleaned_filename,
            mimetype=mimetype
        )

    return render_template('countermeasures.html', **load_i18n(request))

# --- File encryption: streaming AEAD with a self-describing header ---
# Primitives live in crypto_utils.py (PBKDF2 + AES-256-GCM / ChaCha20-Poly1305 /
# Fernet, with a legacy Fernet-chunk fallback on decrypt). Files are streamed, so
# no plaintext temp file is ever written to disk.
from itertools import chain

ALGO_CHOICES = [
    ("aes-256-gcm", "AES-256-GCM (recommended)"),
    ("chacha20-poly1305", "ChaCha20-Poly1305 (mobile-friendly)"),
    ("fernet", "Fernet (easy)"),
]


@app.route('/crypto')
def crypto_tool():
    return render_template('crypto.html', algorithms=ALGO_CHOICES,
                           **load_i18n(request))


def _too_large():
    cl = request.content_length
    return cl is not None and cl > crypto_utils.MAX_FILE_SIZE


@app.route('/encrypt', methods=['POST'])
def encrypt_file():
    if 'file' not in request.files or not request.files['file'].filename:
        return jsonify({"error": "No file provided"}), 400
    if _too_large():
        return jsonify({"error": "File too large (max 100 MB)"}), 413

    file = request.files['file']
    key = request.form.get('key', '')
    if not key:
        return jsonify({"error": "No key provided"}), 400
    algo = crypto_utils.resolve_algo(request.form.get('algorithm'))

    name = secure_filename(file.filename) or "file"
    gen = crypto_utils.encrypt_generator(file.stream, key, algo, name)
    headers = {
        "Content-Disposition": f'attachment; filename="{name}.enc"',
        "X-Content-Type-Options": "nosniff",
    }
    return Response(stream_with_context(gen),
                    mimetype="application/octet-stream", headers=headers)


@app.route('/decrypt', methods=['POST'])
def decrypt_file():
    if 'file' not in request.files or not request.files['file'].filename:
        return jsonify({"error": "No file provided"}), 400
    if _too_large():
        return jsonify({"error": "File too large (max 100 MB)"}), 413

    file = request.files['file']
    key = request.form.get('key', '')
    if not key:
        return jsonify({"error": "No key provided"}), 400

    # Validate the key against the header + first chunk before streaming a 200.
    try:
        gen = crypto_utils.decrypt_dispatch(file.stream, key)
        first = next(gen)
    except StopIteration:
        first, gen = b"", iter(())
    except crypto_utils.DecryptError:
        return jsonify(
            {"error": "Decryption failed - wrong key or corrupt file"}), 400

    src = secure_filename(file.filename) or "file"
    for suffix in (".enc", "_ENCRYPTED"):
        if src.endswith(suffix):
            src = src[: -len(suffix)]
            break
    out_name = src or "decrypted.bin"
    headers = {
        "Content-Disposition": f'attachment; filename="{out_name}"',
        "X-Content-Type-Options": "nosniff",
    }
    return Response(stream_with_context(chain([first], gen)),
                    mimetype="application/octet-stream", headers=headers)


@app.route('/random_key')
def random_key():
    # A strong passphrase; the server derives the actual key via PBKDF2.
    return jsonify({"key": secrets.token_urlsafe(32)})


from flask import Flask, request, render_template_string
from PIL import Image, ImageChops
import os
from werkzeug.utils import secure_filename

app.config['UPLOAD_FOLDER'] = '/tmp'
@app.route('/check_integrity', methods=['GET', 'POST'])
def check_integrity():
    result = None
    if request.method == 'POST':
        orig_file = request.files['original']
        clean_file = request.files['cleaned']

        orig_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(orig_file.filename))
        clean_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(clean_file.filename))

        orig_file.save(orig_path)
        clean_file.save(clean_path)

        img1 = Image.open(orig_path).convert("RGB")
        img2 = Image.open(clean_path).convert("RGB")

        if img1.size != img2.size:
            result = {"match": False, "integrity": 0}
        else:
            diff = ImageChops.difference(img1, img2)
            pixels = img1.size[0] * img1.size[1]
            diff_pixels = sum(diff.convert("L").point(lambda x: 1 if x > 0 else 0).getdata())
            similarity = max(0, 100 - (diff_pixels / pixels * 100))
            result = {
                "match": diff_pixels == 0,
                "integrity": round(similarity, 2)
            }

    return render_template('check_integrity.html', result=result)



if __name__ == '__main__':
    app.run('0.0.0.0', port=5000)
    debug=True
