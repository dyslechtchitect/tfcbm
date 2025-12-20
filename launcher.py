#!/usr/bin/env python3
"""
TFCBM Launcher - Manages both server and UI processes
"""
import subprocess
import sys
import time
import socket
import logging
import signal
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - TFCBM.Launcher - %(levelname)s - %(message)s')

class TFCBMLauncher:
    def __init__(self):
        self.server_process = None
        self.ui_process = None
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.python_path = os.path.join(self.project_dir, '.venv', 'bin', 'python3')

    def is_port_open(self, port, host='127.0.0.1', timeout=1):
        """Check if a port is listening"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    def start_server(self):
        """Start the WebSocket server"""
        logging.info("Starting WebSocket server...")

        # Check if server is already running
        if self.is_port_open(8765):
            logging.info("Server already running on port 8765")
            return True

        # Start server process
        server_script = os.path.join(self.project_dir, 'tfcbm_server.py')
        server_log = '/tmp/tfcbm_server.log'

        try:
            with open(server_log, 'a') as log_file:
                self.server_process = subprocess.Popen(
                    [self.python_path, '-u', server_script],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True  # Detach from parent
                )

            logging.info(f"Server process started with PID: {self.server_process.pid}")

            # Wait for server to be ready (max 10 seconds)
            for i in range(20):
                if self.is_port_open(8765):
                    logging.info("✓ Server is ready and listening on port 8765")
                    return True
                time.sleep(0.5)

            logging.error("Server failed to start within timeout")
            return False

        except Exception as e:
            logging.error(f"Failed to start server: {e}")
            return False

    def start_ui(self):
        """Start the UI"""
        logging.info("Starting UI...")

        ui_script = os.path.join(self.project_dir, 'ui', 'main.py')
        ui_log = '/tmp/tfcbm_ui.log'

        try:
            # Get the actual server PID
            server_pid = None
            if self.server_process:
                server_pid = self.server_process.pid
            else:
                # Try to find existing server process
                result = subprocess.run(
                    ['pgrep', '-o', '-f', 'tfcbm_server.py'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    server_pid = int(result.stdout.strip())

            with open(ui_log, 'a') as log_file:
                cmd = [self.python_path, ui_script]
                if server_pid:
                    cmd.extend(['--server-pid', str(server_pid)])

                self.ui_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )

            logging.info(f"✓ UI process started with PID: {self.ui_process.pid}")
            return True

        except Exception as e:
            logging.error(f"Failed to start UI: {e}")
            return False

    def launch(self):
        """Launch both server and UI"""
        logging.info("=== TFCBM Launcher ===")

        # Start server
        if not self.start_server():
            logging.error("Failed to start server, aborting")
            return 1

        # Start UI
        if not self.start_ui():
            logging.error("Failed to start UI")
            return 1

        logging.info("=== TFCBM launched successfully ===")

        # Wait for UI to exit (but don't monitor server - let it run independently)
        if self.ui_process:
            self.ui_process.wait()

        return 0

def main():
    launcher = TFCBMLauncher()
    sys.exit(launcher.launch())

if __name__ == '__main__':
    main()
