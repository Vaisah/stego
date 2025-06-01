from flask import Flask, request
import hashlib
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB limit

def calculate_hash(file_path, algo="sha256"):
    hasher = hashlib.new(algo)
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        return f"Error: {e}"

@app.route("/", methods=["GET", "POST"])
def index():
    result_html = ""
    overall_rate = ""
    if request.method == "POST":
        algo = request.form.get("algo", "sha256")

        original_files = request.files.getlist("original_files")
        recovered_files = request.files.getlist("recovered_files")

        orig_temp_dir = tempfile.mkdtemp()
        rec_temp_dir = tempfile.mkdtemp()

        # Save uploaded files
        orig_paths = {}
        for f in original_files:
            filename = secure_filename(f.filename)
            full_path = os.path.join(orig_temp_dir, filename)
            f.save(full_path)
            orig_paths[filename] = full_path

        rec_paths = {}
        for f in recovered_files:
            filename = secure_filename(f.filename)
            full_path = os.path.join(rec_temp_dir, filename)
            f.save(full_path)
            rec_paths[filename] = full_path

        # Compare hashes and build HTML table
        rows = ""
        match_count = 0

        for filename, orig_path in orig_paths.items():
            orig_hash = calculate_hash(orig_path, algo)
            rec_path = rec_paths.get(filename)
            rec_hash = calculate_hash(rec_path, algo) if rec_path else "Missing"

            match = "100%" if orig_hash == rec_hash else "0%" if rec_path else "N/A"
            if match == "100%":
                match_count += 1

            rows += f"""
                <tr>
                    <td>{filename}</td>
                    <td>{orig_hash}</td>
                    <td>{rec_hash}</td>
                    <td style='color:{"green" if match=="100%" else "red"};'>{match}</td>
                </tr>
            """

        total = len(orig_paths)
        rate = (match_count / total * 100) if total > 0 else 0
        overall_rate = f"<p style='font-weight:bold;'>Overall Recovery Rate: {rate:.2f}%</p>"

        result_html = f"""
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color:#f2f2f2;">
                    <th>File Name</th>
                    <th>Original File Hash</th>
                    <th>Recovered File Hash</th>
                    <th>Match (%)</th>
                </tr>
                {rows}
            </table>
        """

    return f"""
    <html>
    <head><title>File Integrity Checker</title></head>
    <body style="font-family:Arial;padding:40px;background-color:#f9f9f9;">
        <h2>File Integrity Checker</h2>
        <form method="POST" enctype="multipart/form-data" style="margin-bottom:30px;">
            <label>Original Files (multiple):</label><br>
            <input type="file" name="original_files" multiple required><br><br>

            <label>Recovered Files (multiple):</label><br>
            <input type="file" name="recovered_files" multiple required><br><br>

            <label>Hash Algorithm:</label><br>
            <select name="algo">
                <option value="sha256">SHA-256</option>
                <option value="md5">MD5</option>
                <option value="sha1">SHA-1</option>
                <option value="sha512">SHA-512</option>
            </select><br><br>

            <button type="submit" style="padding:10px 20px;">Check Integrity</button>
        </form>

        {result_html}
        {overall_rate}
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)
