import subprocess

class StegExtractor:
    def __init__(self, file_path):
        self.file_path = file_path

    def extract(self, password=""):
        output_file = self.file_path + "_extracted.txt"
        result = subprocess.run(
            ["steghide", "extract", "-sf", self.file_path, "-xf", output_file, "p", password],
            capture_output=True, text=True
        )

        if "could not extract" in result.stderr.lower():
            print("[*] Extraction failed, likely due to incorrect password.")
            return False
        elif "wrote extracted data" in result.stdout.lower():
            print(f"[*] Data extracted to {output_file}")
            return True
        else:
            print("[*] Unexpected error during extraction.")
            return False
