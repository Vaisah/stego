import os
from shlex import quote
from utils import cmd  # Your existing shell wrapper

class StegExpose:
    def __init__(self):
        pass

    def analyze_folder(self, folder_path: str, result_csv: str) -> str:
        # Run stegexpose on the entire folder
        command = f"cd {quote(folder_path)} && stegexpose -d . -csv {quote(result_csv)} 2>&1"
        return cmd(command)

    def archive_and_cleanup(self, folder_path: str, archive_path: str):
        # Archive results and delete folder
        cmd(f"7z a {quote(archive_path)} {quote(folder_path)}/*")
        cmd(f"rm -r {quote(folder_path)}")
