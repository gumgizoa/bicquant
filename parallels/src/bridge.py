# bridge.py — run this ONCE in an interactive CMD window on the Windows VM.
#
# How to start:
#   (after activating virtual env) C:\Users\cho-eungi\eungizoa\bicquant\parallels\bridge.py
#
# Keep this window open while using crawl_hts.py from Mac.
# It watches for a trigger file written by the Mac-side SSH session and
# executes hts_automation.py in THIS interactive session (full desktop access).

import os
import subprocess
import time

TRIGGER = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_trigger.txt"
PYTHON = r"C:\Users\cho-eungi\eungizoa\bicquant\Scripts\python.exe"
SCRIPT = r"C:\Users\cho-eungi\AppData\Local\Temp\hts_automation.py"

print("Bridge ready. Watching for trigger file...", flush=True)
print(f"  Trigger path: {TRIGGER}", flush=True)

while True:
    if os.path.exists(TRIGGER):
        os.remove(TRIGGER)
        print("\nTriggered! Starting automation...", flush=True)
        result = subprocess.run([PYTHON, SCRIPT])
        print(
            f"Automation exited (code={result.returncode}). Watching for next trigger...\n",
            flush=True,
        )
    time.sleep(0.5)
