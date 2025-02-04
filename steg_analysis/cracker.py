
import subprocess

class StegCracker:
    def __init__(self, image_path, wordlist):
        self.image_path = image_path
        self.wordlist = wordlist

    def crack_password(self):
        """Try to crack steghide password using stegcrack."""
        result = subprocess.run(
            ["stegcracker", self.image_path, self.wordlist],
            capture_output=True, text=True
        )

        if "password found" in result.stdout.lower():
            password = result.stdout.split(":")[-1].strip()
            print(f"[*] Password cracked: {password}")
            return password
        else:
            print("[*] Password cracking failed.")
            return None
