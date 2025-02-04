import os
import subprocess

class StegAnalyzer:
    def __init__(self, path):
        self.path = path
        self.image_files = self._get_images()

    def _get_images(self):
        """Retrieve image files if a directory is provided."""
        if os.path.isdir(self.path):
            return [
                os.path.join(self.path, f) for f in os.listdir(self.path)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif"))
            ]
        elif os.path.isfile(self.path):
            return [self.path]
        else:
            return []

    def check_steghide(self, image_path):
        """Check if steghide detects hidden data."""
        result = subprocess.run(
            ["steghide", "info", image_path], capture_output=True, text=True
        )
        return "not embedded" not in result.stdout

    def check_stegdetect(self, image_path):
        """Check if stegdetect finds steganography."""
        result = subprocess.run(["stegdetect", "-s", "10", image_path], capture_output=True, text=True)
        return bool(result.stdout.strip())

    def check_stegexpose(self, image_path):
        """Check for hidden data using StegExpose."""
        result = subprocess.run(
            ["java", "-cp", "StegExpose", "StegExpose", image_path], capture_output=True, text=True
        )
        return bool(result.stdout.strip())

    def analyze(self):
        """Run analysis on all detected images."""
        if not self.image_files:
            print("[*] No valid image files found.")
            return []

        detected_files = []
        for image in self.image_files:
            print(f"\n[*] Analyzing {image}...\n")
            if self.check_steghide(image) or self.check_stegdetect(image) or self.check_stegexpose(image):
                print("[*] Hidden data detected!")
                detected_files.append(image)
            else:
                print("[*] No hidden data found.")

        return detected_files
