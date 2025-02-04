import subprocess



class StegAnalyzer:
    def __init__(self,file_path):
        self.file_path = file_path

    def check_steghide(self):
        #check for hidden data with steghide
        result = subprocess.run(
            ["steghide" ,"info", self.file_path], capture_output=True, text=True
        )
        if "not embedded" in result.stdout:
            return False
        return True

    #check stegdetect
    def check_stegdetect(self):
        result = subprocess.run(
            ["stegdetect", "-s", "10", self.file_path],

            capture_output=True, text=True
        )
        return bool(result.stdout.strip())

    def check_stegexpose(self):
        result = subprocess.run(
            ["java", "-cp", "StegExpose", self.file_path],
            capture_output=True, text=True
        )
        return bool(result.stdout.strip())

    #Run all the  functions to analyze
    def analyze(self):
        print(f"[*] Analyzing {self.file_path} ...\n")
        steghide_found = self.check_steghide()
        stegdetetct_found = self.check_stegdetect()
        stegexpose_found = self.check_stegexpose()

        if steghide_found or stegdetetct_found or stegexpose_found:
            print("[*] Hidden data detected")
            return True
        else:
            print("[*] No hidden data found.")
            return False
