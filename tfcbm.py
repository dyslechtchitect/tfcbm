import subprocess
import time
from datetime import datetime

history = []  # list of {"type": "text"/"image", "content": <data>, "timestamp": ...}


def get_clipboard():
    """Get clipboard content without blocking"""
    try:
        result = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=0.1)
        if result.returncode == 0:
            return result.stdout
    except BaseException:
        pass
    return None


def check_clipboard():
    """Check if clipboard has changed"""
    text = get_clipboard()

    if text:
        # Check if it's actually new
        is_new = not history or history[-1].get("type") != "text" or history[-1].get("content") != text

        if is_new:
            history.append(
                {
                    "type": "text",
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            # Print what was copied
            if len(text) > 100:
                print(f"✓ Copied: {text[:100]}...")
            else:
                print(f"✓ Copied: {text}")
            print(f"  (History: {len(history)} items)\n")


if __name__ == "__main__":
    print("Watching clipboard for changes...")
    print("(Polling every 2 seconds)\n")

    try:
        while True:
            check_clipboard()
            time.sleep(2)  # Check every 2 seconds to avoid interference
    except KeyboardInterrupt:
        print("\nStopping clipboard monitor...")
        print(f"Total items saved: {len(history)}")
