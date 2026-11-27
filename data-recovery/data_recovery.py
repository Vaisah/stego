import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import hashlib
import os

def calculate_hash(filepath, hash_algo="sha256"):
    """Calculates the hash of a file."""
    hasher = hashlib.new(hash_algo)
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):  # Read in 8KB chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return "File Not Found"
    except Exception as e:
        return f"Error: {e}"

class DataIntegrityVerifier:
    def __init__(self, master):
        self.master = master
        master.title("Data Integrity Verifier")
        master.geometry("800x650") # Increased size for better layout
        master.resizable(False, False) # Prevent resizing

        self.original_file_path = ""
        self.recovered_file_path = ""
        self.original_folder_path = ""
        self.recovered_folder_path = ""

        self.hash_algorithm = tk.StringVar(value="sha256") # Default hash algorithm

        # --- Single File Comparison Section ---
        self.single_frame = tk.LabelFrame(master, text="Single File Integrity Check", padx=10, pady=10)
        self.single_frame.pack(pady=10, padx=10, fill="x")

        # Original File Selection
        tk.Label(self.single_frame, text="Original File:").grid(row=0, column=0, sticky="w", pady=2)
        self.original_file_entry = tk.Entry(self.single_frame, width=50)
        self.original_file_entry.grid(row=0, column=1, padx=5, pady=2)
        tk.Button(self.single_frame, text="Browse", command=self.browse_original_file).grid(row=0, column=2, pady=2)

        # Recovered File Selection
        tk.Label(self.single_frame, text="Recovered File:").grid(row=1, column=0, sticky="w", pady=2)
        self.recovered_file_entry = tk.Entry(self.single_frame, width=50)
        self.recovered_file_entry.grid(row=1, column=1, padx=5, pady=2)
        tk.Button(self.single_frame, text="Browse", command=self.browse_recovered_file).grid(row=1, column=2, pady=2)

        # Hash Algorithm Selection
        tk.Label(self.single_frame, text="Hash Algorithm:").grid(row=2, column=0, sticky="w", pady=2)
        tk.OptionMenu(self.single_frame, self.hash_algorithm, "md5", "sha1", "sha256", "sha512").grid(row=2, column=1, sticky="w", pady=2)

        # Check Integrity Button
        tk.Button(self.single_frame, text="Check Single File Integrity", command=self.check_single_file_integrity).grid(row=3, column=1, columnspan=2, pady=10)

        # Results Display for Single File
        tk.Label(self.single_frame, text="Integrity Result:").grid(row=4, column=0, sticky="w", pady=2)
        self.single_integrity_label = tk.Label(self.single_frame, text="", wraplength=400, justify="left", font=("Arial", 10, "bold"))
        self.single_integrity_label.grid(row=4, column=1, columnspan=2, sticky="w", pady=2)

        tk.Label(self.single_frame, text="Recovery Rate:").grid(row=5, column=0, sticky="w", pady=2)
        self.single_recovery_rate_label = tk.Label(self.single_frame, text="", font=("Arial", 12, "bold"))
        self.single_recovery_rate_label.grid(row=5, column=1, columnspan=2, sticky="w", pady=2)

        # --- Multiple File Comparison Section ---
        self.multi_frame = tk.LabelFrame(master, text="Multiple Files (Folder) Integrity Check", padx=10, pady=10)
        self.multi_frame.pack(pady=10, padx=10, fill="x")

        # Original Folder Selection
        tk.Label(self.multi_frame, text="Original Folder:").grid(row=0, column=0, sticky="w", pady=2)
        self.original_folder_entry = tk.Entry(self.multi_frame, width=50)
        self.original_folder_entry.grid(row=0, column=1, padx=5, pady=2)
        tk.Button(self.multi_frame, text="Browse", command=self.browse_original_folder).grid(row=0, column=2, pady=2)

        # Recovered Folder Selection
        tk.Label(self.multi_frame, text="Recovered Folder:").grid(row=1, column=0, sticky="w", pady=2)
        self.recovered_folder_entry = tk.Entry(self.multi_frame, width=50)
        self.recovered_folder_entry.grid(row=1, column=1, padx=5, pady=2)
        tk.Button(self.multi_frame, text="Browse", command=self.browse_recovered_folder).grid(row=1, column=2, pady=2)

        # Check Multiple Files Button
        tk.Button(self.multi_frame, text="Check Multiple Files Integrity", command=self.check_multiple_files_integrity).grid(row=2, column=1, columnspan=2, pady=10)

        # Results Display for Multiple Files
        self.multi_results_text = scrolledtext.ScrolledText(self.multi_frame, width=80, height=10, wrap=tk.WORD)
        self.multi_results_text.grid(row=3, column=0, columnspan=3, padx=5, pady=5)

        tk.Label(self.multi_frame, text="Overall Recovery Rate:").grid(row=4, column=0, sticky="w", pady=2)
        self.multi_recovery_rate_label = tk.Label(self.multi_frame, text="", font=("Arial", 12, "bold"))
        self.multi_recovery_rate_label.grid(row=4, column=1, columnspan=2, sticky="w", pady=2)

        # Initial background color (default)
        master.config(bg="lightgray") # A neutral starting color

    def browse_original_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.original_file_path = filepath
            self.original_file_entry.delete(0, tk.END)
            self.original_file_entry.insert(0, filepath)

    def browse_recovered_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.recovered_file_path = filepath
            self.recovered_file_entry.delete(0, tk.END)
            self.recovered_file_entry.insert(0, filepath)

    def browse_original_folder(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.original_folder_path = folderpath
            self.original_folder_entry.delete(0, tk.END)
            self.original_folder_entry.insert(0, folderpath)

    def browse_recovered_folder(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.recovered_folder_path = folderpath
            self.recovered_folder_entry.delete(0, tk.END)
            self.recovered_folder_entry.insert(0, folderpath)

    def set_background_color(self, recovery_rate):
        if recovery_rate >= 90:
            self.master.config(bg="lightgreen")
        else:
            self.master.config(bg="lightcoral") # Indicate lower rate with a different color

    def check_single_file_integrity(self):
        original_file = self.original_file_path
        recovered_file = self.recovered_file_path
        algo = self.hash_algorithm.get()

        if not original_file or not recovered_file:
            messagebox.showwarning("Input Error", "Please select both original and recovered files.")
            return

        original_hash = calculate_hash(original_file, algo)
        recovered_hash = calculate_hash(recovered_file, algo)

        result_text = f"Algorithm: {algo.upper()}\n\n"
        result_text += f"Original File Hash: {original_hash}\n"
        result_text += f"Recovered File Hash: {recovered_hash}\n\n"

        if original_hash == "File Not Found" or recovered_hash == "File Not Found":
            result_text += "Error: One or both files not found. Check paths.\n"
            integrity_percentage = 0
        elif original_hash == recovered_hash:
            result_text += "Integrity Check: MATCH! The files are identical.\n"
            integrity_percentage = 100
        else:
            result_text += "Integrity Check: MISMATCH! The files are different.\n"
            integrity_percentage = 0

        self.single_integrity_label.config(text=result_text)
        self.single_recovery_rate_label.config(text=f"{integrity_percentage:.2f}%")
        self.set_background_color(integrity_percentage)

    def check_multiple_files_integrity(self):
        original_folder = self.original_folder_path
        recovered_folder = self.recovered_folder_path
        algo = self.hash_algorithm.get()

        if not original_folder or not recovered_folder:
            messagebox.showwarning("Input Error", "Please select both original and recovered folders.")
            return

        original_files = {}
        for root, _, files in os.walk(original_folder):
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, original_folder)
                original_files[relative_path] = calculate_hash(full_path, algo)

        recovered_files = {}
        for root, _, files in os.walk(recovered_folder):
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, recovered_folder)
                recovered_files[relative_path] = calculate_hash(full_path, algo)

        self.multi_results_text.delete(1.0, tk.END) # Clear previous results
        self.multi_results_text.insert(tk.END, f"--- Multiple File Integrity Check ({algo.upper()}) ---\n\n")

        match_count = 0
        total_original_files = len(original_files)

        for relative_path, original_hash in original_files.items():
            recovered_hash = recovered_files.get(relative_path)

            self.multi_results_text.insert(tk.END, f"File: {relative_path}\n")
            self.multi_results_text.insert(tk.END, f"  Original Hash: {original_hash}\n")

            if recovered_hash:
                self.multi_results_text.insert(tk.END, f"  Recovered Hash: {recovered_hash}\n")
                if original_hash == recovered_hash:
                    self.multi_results_text.insert(tk.END, "  Integrity: MATCH (100%)\n\n")
                    match_count += 1
                else:
                    self.multi_results_text.insert(tk.END, "  Integrity: MISMATCH (0%)\n\n")
            else:
                self.multi_results_text.insert(tk.END, "  Recovered file not found in recovered folder.\n")
                self.multi_results_text.insert(tk.END, "  Integrity: N/A (File not recovered or path mismatch)\n\n")

        if total_original_files > 0:
            overall_recovery_rate = (match_count / total_original_files) * 100
        else:
            overall_recovery_rate = 0

        self.multi_results_text.insert(tk.END, f"--------------------------------------------------\n")
        self.multi_results_text.insert(tk.END, f"Total Original Files Checked: {total_original_files}\n")
        self.multi_results_text.insert(tk.END, f"Files with Matching Hashes: {match_count}\n")
        self.multi_results_text.insert(tk.END, f"Overall Recovery Rate (based on matching hashes): {overall_recovery_rate:.2f}%\n")

        self.multi_recovery_rate_label.config(text=f"{overall_recovery_rate:.2f}%")
        self.set_background_color(overall_recovery_rate)


# Create the main window
root = tk.Tk()
app = DataIntegrityVerifier(root)
root.mainloop()