import os
import pyfiglet
#from analyzer import StegAnalyzer
from extractor import StegExtractor
from cracker import StegCracker
from utils import WordlistGenerator
from directory_analyzer import StegAnalyzer

def get_valid_path():
    #Prompt the user for a valid image or directory path.
    while True:
        path = input("[*] Enter the path of the image or directory to analyze: ").strip()
        if os.path.exists(path):
            return path
        print("[*] File or directory not found! Please try again.")

def main():
    print(pyfiglet.figlet_format("AutoSteg Extractor"))

    while True:
        path = get_valid_path()

        # Analyze images
        analyzer = StegAnalyzer(path)
        detected_images = analyzer.analyze()

        if not detected_images:
            print("[*] No images with hidden data found.")
        else:
            for image in detected_images:
                extract_choice = input(f"\n[*] Hidden data found in {image}! Do you want to extract it? (y/n): ").strip().lower()

                if extract_choice == "y":
                    extractor = StegExtractor(image)
                    if extractor.extract():
                        print(f"[*] Data successfully extracted from {image}!")
                        continue

                    print("[*] Extraction failed. Likely password protected.")

                    crack_choice = input("[*] Do you want to crack the password? (y/n): ").strip().lower()
                    if crack_choice == "y":
                        wordlist = WordlistGenerator.select_wordlist()
                        cracker = StegCracker(image, wordlist)
                        password = cracker.crack_password()

                        if password:
                            print(f"[*] Trying extraction again on {image} with cracked password...")
                            if extractor.extract(password):
                                print(f"[*] Data successfully extracted from {image} using cracked password!")
                            else:
                                print("[*] Extraction failed, even with cracked password.")
                        else:
                            print("[*] Password cracking unsuccessful.")

        # Ask if the user wants to analyze another file or exit
        retry = input("\n[*] Do you want to analyze another file? (y/n): ").strip().lower()
        if retry != "y":
            print("[*] Exiting AutoSteg Extractor.")
            break

if __name__ == "__main__":
    main()
