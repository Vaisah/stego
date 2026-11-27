from flask import Flask, request, render_template
import hashlib
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()

def calculate_md5(file_path):
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    result_table = ""
    overall_rate = ""

    if request.method == 'POST':
        original_files = request.files.getlist('original_folder')
        recovered_files = request.files.getlist('recovered_folder')

        original_map = {}
        recovered_map = {}

        # Save and hash original files
        for f in original_files:
            filename = os.path.basename(f.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'original_' + secure_filename(filename))
            f.save(save_path)
            original_map[filename] = calculate_md5(save_path)

        # Save and hash recovered files
        for f in recovered_files:
            filename = os.path.basename(f.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'recovered_' + secure_filename(filename))
            f.save(save_path)
            recovered_map[filename] = calculate_md5(save_path)

        matched = 0
        total = len(original_map)
        rows = ""

        for filename, orig_hash in original_map.items():
            rec_hash = recovered_map.get(filename, "Not Found")
            match_status = "100%" if orig_hash == rec_hash else "0%" if rec_hash != "Not Found" else "N/A"

            if match_status == "100%":
                matched += 1

            rows += f"""
            <tr>
                <td>{filename}</td>
                <td>{orig_hash}</td>
                <td>{rec_hash}</td>
                <td style="color:{'green' if match_status == '100%' else 'red'};">{match_status}</td>
            </tr>
            """

        rate = (matched / total) * 100 if total else 0
        overall_rate = f"<p style='font-weight:bold;'>Overall Recovery Rate: {rate:.2f}%</p>"

        result_table = f"""
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color:#f2f2f2;">
                <th>File Name</th>
                <th>Original MD5</th>
                <th>Recovered MD5</th>
                <th>Match</th>
            </tr>
            {rows}
        </table>
        """

    return render_template("integrity.html", result_table=result_table, overall_rate=overall_rate)

if __name__ == "__main__":
    app.run(debug=True)
