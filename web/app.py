#!/usr/bin/python3
# -*- encoding: utf-8 -*-

import glob
import hashlib
import json
import os
import re
import subprocess
from werkzeug.utils import secure_filename
import time
from flask import Flask, render_template, request, jsonify, \
    send_from_directory, redirect, url_for, make_response, Response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://xander:xander21@mongodb:27017/flaskdb?authSource=admin"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 Mb max
app.config['LANGUAGES'] = {
    'en': 'English',
    'fr': 'Français'
}


mongo = PyMongo(app)
db = mongo.db


mongo = PyMongo(app)
db = mongo.db

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

# Hash Algorithms and Tool Mappings
HASHCAT_MODES = {
    'MD5': '0',
    'SHA1': '100',
    'SHA256': '1400',
    'bcrypt': '3200',
}

JOHN_FORMATS = {
    'MD5': 'raw-md5',
    'SHA1': 'raw-sha1',
    'SHA256': 'raw-sha256',
    'bcrypt': 'bcrypt',
}

# Paths to tools (verify in your Docker container)
# JOHN_PATH = '/usr/bin/john'  # or '/usr/sbin/john'
# HASHCAT_PATH = '/usr/bin/hashcat'

def detect_hash_type(hash_sample):
    """Detect hash type using hashid."""
    try:
        output = subprocess.check_output(
            ['hashid', '-m', hash_sample],
            stderr=subprocess.PIPE,
            text=True
        )
        for line in output.splitlines():
            for algo in HASHCAT_MODES:
                if algo in line:
                    return algo
    except Exception as e:
        flash(f"Hash detection error: {e}", "error")
    return 'MD5'  # Default fallback

@app.route('/crack_hash', methods=['GET', 'POST'])
def crack_hash():
    result = None
    if request.method == 'POST':
        temp_dir = tempfile.mkdtemp()
        try:
            # Handle hash input (text or file)
            hash_text = request.form.get('hash_input', '').strip()
            hash_file = request.files.get('hash_file')
            hash_path = os.path.join(temp_dir, 'hash.txt')

            if hash_file:
                hash_file.save(hash_path)
            elif hash_text:
                with open(hash_path, 'w') as f:
                    f.write(hash_text + '\n')
            else:
                flash('No hash provided!', 'error')
                return redirect(request.url)

            # Handle wordlist (upload or default)
            wordlist_file = request.files.get('wordlist')
            wordlist_path = '/usr/share/wordlists/rockyou.txt'  # Default

            if wordlist_file and wordlist_file.filename:
                wordlist_path = os.path.join(temp_dir, secure_filename(wordlist_file.filename))
                wordlist_file.save(wordlist_path)
            elif not os.path.exists(wordlist_path):
                flash('Default wordlist not found!', 'error')
                return redirect(request.url)

            # Detect hash type
            with open(hash_path, 'r') as f:
                sample_hash = f.readline().strip()
            hash_type = detect_hash_type(sample_hash)
            john_fmt = JOHN_FORMATS.get(hash_type, 'raw-md5')
            hashcat_mode = HASHCAT_MODES.get(hash_type, '0')

            # Run John the Ripper
            try:
                subprocess.run(
                    ['john', f'--format={john_fmt}', f'--wordlist={wordlist_path}', hash_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                john_output = subprocess.check_output(
                    ['john', '--show', hash_path],
                    text=True
                ).strip()
            except subprocess.CalledProcessError as e:
                john_output = f"John failed: {e.stderr}"
            except Exception as e:
                john_output = f"John error: {str(e)}"

            # Run Hashcat
            try:
                hashcat_output = subprocess.check_output(
                    ['hashcat', '-m', hashcat_mode, hash_path, wordlist_path, '--quiet', '--show'],
                    text=True
                ).strip()
            except subprocess.CalledProcessError as e:
                hashcat_output = f"Hashcat failed: {e.stderr}"
            except Exception as e:
                hashcat_output = f"Hashcat error: {str(e)}"

            result = {
                'hash_type': hash_type,
                'john': john_output if john_output else "No results from John.",
                'hashcat': hashcat_output if hashcat_output else "No results from Hashcat."
            }

        except Exception as e:
            flash(f"Unexpected error: {str(e)}", "error")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)  # Cleanup

    return render_template('crack_hash.html', result=result)

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

# Add these imports at the top
from cryptography.fernet import Fernet
import hashlib, base64, os, struct

@app.route('/crypto')
def crypto_tool():
    return render_template('crypto.html', **load_i18n(request))

@app.route('/encrypt', methods=['POST'])
def encrypt_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    key = request.form.get('key', '').strip()
    use_random_key = request.form.get('use_random_key') == 'true'
    
    if use_random_key:
        key = Fernet.generate_key().decode()
    elif not key:
        return jsonify({"error": "No key provided"}), 400
    
    # Process the key like in EasyEnc.py
    _key = hashlib.md5(key.encode()).hexdigest()
    _key = base64.urlsafe_b64encode(_key.encode())
    
    # Save the file temporarily
    temp_dir = tempfile.mkdtemp()
    original_path = os.path.join(temp_dir, secure_filename(file.filename))
    encrypted_path = original_path + "_ENCRYPTED"
    file.save(original_path)
    
    try:
        # Encrypt the file
        fernet = Fernet(_key)
        with open(original_path, "rb") as f_in, open(encrypted_path, "wb") as f_out:
            while True:
                chunk = f_in.read(4096)
                if not chunk:
                    break
                encrypted_chunk = fernet.encrypt(chunk)
                f_out.write(struct.pack("<I", len(encrypted_chunk)))
                f_out.write(encrypted_chunk)
        
        # Return the encrypted file
        return send_file(
            encrypted_path,
            as_attachment=True,
            download_name=file.filename + "_ENCRYPTED",
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/decrypt', methods=['POST'])
def decrypt_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    key = request.form.get('key', '').strip()
    
    if not key:
        return jsonify({"error": "No key provided"}), 400
    
    # Process the key like in EasyEnc.py
    _key = hashlib.md5(key.encode()).hexdigest()
    _key = base64.urlsafe_b64encode(_key.encode())
    
    # Save the file temporarily
    temp_dir = tempfile.mkdtemp()
    encrypted_path = os.path.join(temp_dir, secure_filename(file.filename))
    decrypted_path = encrypted_path.replace("_ENCRYPTED", "_DECRYPTED")
    file.save(encrypted_path)
    
    try:
        # Decrypt the file
        fernet = Fernet(_key)
        with open(encrypted_path, "rb") as f_in, open(decrypted_path, "wb") as f_out:
            while True:
                data_size = f_in.read(4)
                if len(data_size) == 0:
                    break
                encrypted_chunk = f_in.read(struct.unpack("<I", data_size)[0])
                try:
                    decrypted_chunk = fernet.decrypt(encrypted_chunk)
                    f_out.write(decrypted_chunk)
                except:
                    return jsonify({"error": "Decryption failed - wrong key?"}), 400
        
        # Return the decrypted file
        return send_file(
            decrypted_path,
            as_attachment=True,
            download_name=file.filename.replace("_ENCRYPTED", "_DECRYPTED"),
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        
@app.route('/random_key')
def random_key():
    key = Fernet.generate_key().decode()
    return jsonify({"key": key})


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
