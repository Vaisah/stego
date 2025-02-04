
import subprocess

class WordlistGenerator:
    @staticmethod
    def generate_with_cupp():
        """Generate a wordlist using cupp."""
        subprocess.run(["cupp", "-i"])

    @staticmethod
    def select_wordlist():
        """Prompt user to select an existing wordlist."""
        wordlist_path = input("[*] Enter the path to your wordlist (or type 'cupp' to generate one): ").strip()

        if wordlist_path.lower() == "cupp":
            WordlistGenerator.generate_with_cupp()
            return "cupp-generated.txt"  # Assuming cupp saves to this file
        return wordlist_path
