#!/usr/bin/env python3
"""
HTTP server with range request support for large video files.
"""
import os
import re
import logging
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from functools import partial

# ============================================
# LOGGING CONFIGURATION
# ============================================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Create logger
logger = logging.getLogger('360server')
logger.setLevel(logging.DEBUG)

# File handler - detailed logs with rotation by date
log_file = os.path.join(LOG_DIR, f'server_{datetime.now().strftime("%Y%m%d")}.log')
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Console handler - info and above
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)-8s | %(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class RangeRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler that supports Range requests for video streaming."""

    def guess_type(self, path):
        """Override to add HLS MIME types."""
        if path.endswith('.m3u8'):
            return 'application/vnd.apple.mpegurl'
        elif path.endswith('.ts'):
            return 'video/mp2t'
        return super().guess_type(path)

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")

    def log_error(self, format, *args):
        """Override to use our logger for errors."""
        logger.error(f"{self.address_string()} - {format % args}")

    def handle(self):
        """Handle requests with connection error suppression."""
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            # Normal for video streaming - browser cancels initial request to switch to range requests
            logger.debug(f"Connection closed by client: {type(e).__name__}")

    def send_head(self):
        """Handle HEAD requests and Range headers."""
        path = self.translate_path(self.path)

        logger.debug(f"Request: {self.command} {self.path}")

        if os.path.isdir(path):
            return super().send_head()

        if not os.path.exists(path):
            logger.warning(f"File not found: {path}")
            self.send_error(404, "File not found")
            return None

        # Get file size
        file_size = os.path.getsize(path)

        # Check for Range header
        range_header = self.headers.get('Range')

        if range_header:
            # Parse range header
            range_match = re.match(r'bytes=(\d*)-(\d*)', range_header)
            if range_match:
                start = range_match.group(1)
                end = range_match.group(2)

                start = int(start) if start else 0
                end = int(end) if end else file_size - 1

                if start >= file_size:
                    logger.warning(f"Range not satisfiable: {start}-{end}/{file_size} for {self.path}")
                    self.send_error(416, "Range not satisfiable")
                    return None

                end = min(end, file_size - 1)
                content_length = end - start + 1

                logger.debug(f"Range request: bytes {start}-{end}/{file_size} ({content_length} bytes) for {os.path.basename(path)}")

                # Send partial content response
                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Content-Length", str(content_length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Return file object positioned at start
                f = open(path, 'rb')
                f.seek(start)
                return _RangeFile(f, content_length)

        # No range header - send full file
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        return open(path, 'rb')

class _RangeFile:
    """Wrapper to read only a portion of a file."""
    def __init__(self, f, length):
        self.f = f
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b''
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.f.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrent video streaming."""
    daemon_threads = True


def run(port=8080, directory=None):
    if directory:
        os.chdir(directory)

    handler = RangeRequestHandler

    # Check if port is already in use (Windows SO_REUSEADDR allows silent double-bind)
    import socket
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"\nERROR: Port {port} is already in use.")
            print(f"  - Close the other program using port {port}, or")
            print(f"  - Use a different port: python server.py {port + 1}")
            sys.exit(1)
    finally:
        test_sock.close()

    server = ThreadedHTTPServer(('', port), handler)

    # Startup banner
    banner = f"""
{'='*50}
  360 Video Server - Range Request Support
{'='*50}

  Serving: {os.getcwd()}
  URL: http://localhost:{port}/viewer/multi-view.html

  Logs: {log_file}

  Press Ctrl+C to stop
"""
    print(banner)
    logger.info(f"Server started on port {port}")
    logger.info(f"Serving directory: {os.getcwd()}")
    logger.info(f"Log file: {log_file}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        print("\nShutting down...")
        server.shutdown()
    except Exception as e:
        logger.exception(f"Server error: {e}")
        raise

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
