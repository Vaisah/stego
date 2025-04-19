#!/usr/bin/python3
# -*- encoding: utf-8 -*-

import os
import sys
import time
from shlex import quote
sys.path.append('../')
from config import DELAY_CHECK, UPLOAD_FOLDER  # noqa: E402
from module import Module  # noqa: E402
from utils import cmd  # noqa: E402

RUNNING = []

class StegExpose(Module):
    def __init__(self, md5):
        Module.__init__(self, md5)

    def run(self):
        self.set_config_status("stegexpose", "running")
        folder = self.folder
        image = self.config["image"]
        c_input = f"{folder}/{image}"
        output_dir = f"{folder}/stegexpose"
        result_csv = f"{output_dir}/result.csv"

        cmd(f"mkdir -p {output_dir}")
        # Run stegexpose on the file
        output = cmd(f"cd {output_dir} && stegexpose '{c_input}' -csv '{result_csv}' 2>&1")
        
        # Optionally zip the results
        cmd(f"7z a {folder}/stegexpose.7z {output_dir}/*")
        cmd(f"rm -r {output_dir}")
        
        # Save stdout from stegexpose run
        with open(f"{folder}/stegexpose.txt", "w") as f:
            f.write(output)

        global RUNNING
        RUNNING.remove(self.md5)
        self.set_config_status("stegexpose", "finished")


if __name__ == "__main__":
    while True:
        dirs = os.listdir(UPLOAD_FOLDER)
        for d in dirs:
            try:
                folder = f"{UPLOAD_FOLDER}/{d}"
                if d in RUNNING or not os.path.isdir(folder):
                    continue
                m = StegExpose(d)
                status = m.get_config_status(d)
                if status is None or status.get("stegexpose") is None:
                    RUNNING.append(d)
                    m.start()
            except Exception as e:
                print(e)
                continue
        time.sleep(DELAY_CHECK)
