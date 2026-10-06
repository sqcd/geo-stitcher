from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)

from werkzeug.utils import secure_filename
from werkzeug.serving import make_server

from audio import (
    extract_and_stitch_audio,
    get_slide_count
)

import os
import sys
import tempfile
import threading
import time
import subprocess
import webbrowser
import uuid


# ============================================================
# Flask application
# ============================================================

app = Flask(__name__)

ALLOWED_EXTENSIONS = {"pptx"}

jobs = {}


# ============================================================
# Desktop application settings
# ============================================================

HOST = "127.0.0.1"
PORT = 5000

APP_URL = f"http://{HOST}:{PORT}"

# How long the server waits after the browser stops
# sending heartbeats before shutting down.
HEARTBEAT_TIMEOUT = 5

# The browser only needs to send a heartbeat every second.
HEARTBEAT_INTERVAL = 1


# ============================================================
# Desktop application state
# ============================================================

server = None

server_started = threading.Event()
shutdown_requested = threading.Event()

# This becomes True after the browser has successfully
# loaded the application and sent its first heartbeat.
browser_connected = threading.Event()

last_heartbeat = None

heartbeat_lock = threading.Lock()


# ============================================================
# Utility functions
# ============================================================

def allowed_file(filename):
    return (
        "."
        in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ============================================================
# Audio conversion
# ============================================================

def convert_file(
    job_id,
    input_path,
    output_path,
    original_filename
):
    try:
        total_slides = get_slide_count(
            input_path
        )

        jobs[job_id]["total_slides"] = (
            total_slides
        )

        def update_progress(
            current_slide,
            total_slides,
            stage="converting"
        ):
            jobs[job_id][
                "current_slide"
            ] = current_slide

            jobs[job_id][
                "total_slides"
            ] = total_slides

            jobs[job_id][
                "stage"
            ] = stage

        extract_and_stitch_audio(
            input_path,
            output_path,
            progress_callback=update_progress
        )

        jobs[job_id][
            "current_slide"
        ] = total_slides

        jobs[job_id][
            "total_slides"
        ] = total_slides

        jobs[job_id][
            "status"
        ] = "complete"

        jobs[job_id][
            "stage"
        ] = "complete"

    except Exception as e:
        print(
            f"Conversion error: {e}"
        )

        jobs[job_id][
            "status"
        ] = "error"

        jobs[job_id][
            "stage"
        ] = "error"

        jobs[job_id][
            "error"
        ] = str(e)


# ============================================================
# Flask routes
# ============================================================

@app.route("/")
def index():
    return render_template(
        "index.html"
    )


@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    if "pptx" not in request.files:
        return jsonify({
            "error":
                "No file was uploaded."
        }), 400

    file = request.files["pptx"]

    if file.filename == "":
        return jsonify({
            "error":
                "No file was selected."
        }), 400

    if not allowed_file(
        file.filename
    ):
        return jsonify({
            "error":
                "Please upload a .pptx file."
        }), 400

    original_filename = (
        secure_filename(
            file.filename
        )
    )

    presentation_name = (
        os.path.splitext(
            original_filename
        )[0]
    )

    output_filename = (
        f"combined_"
        f"{presentation_name}"
        f".mp3"
    )

    temp_dir = tempfile.mkdtemp()

    input_path = os.path.join(
        temp_dir,
        original_filename
    )

    output_path = os.path.join(
        temp_dir,
        output_filename
    )

    file.save(
        input_path
    )

    job_id = str(
        uuid.uuid4()
    )

    jobs[job_id] = {
        "status":
            "processing",

        "stage":
            "starting",

        "current_slide":
            0,

        "total_slides":
            0,

        "output_path":
            output_path,

        "output_filename":
            output_filename,

        "input_path":
            input_path,
    }

    thread = threading.Thread(
        target=convert_file,
        args=(
            job_id,
            input_path,
            output_path,
            original_filename
        ),
        daemon=True
    )

    thread.start()

    return jsonify({
        "job_id": job_id
    })


@app.route(
    "/status/<job_id>"
)
def status(job_id):

    job = jobs.get(
        job_id
    )

    if job is None:
        return jsonify({
            "error":
                "Job not found."
        }), 404

    return jsonify({
        "status":
            job["status"],

        "stage":
            job.get(
                "stage"
            ),

        "current_slide":
            job.get(
                "current_slide",
                0
            ),

        "total_slides":
            job.get(
                "total_slides",
                0
            ),

        "error":
            job.get(
                "error"
            )
    })


@app.route(
    "/download/<job_id>"
)
def download(job_id):

    job = jobs.get(
        job_id
    )

    if job is None:
        return jsonify({
            "error":
                "Job not found."
        }), 404

    if job["status"] != "complete":
        return jsonify({
            "error":
                "Conversion is not complete."
        }), 400

    return send_file(
        job["output_path"],
        as_attachment=True,
        download_name=
            job["output_filename"],
        mimetype="audio/mpeg"
    )


# ============================================================
# Browser heartbeat
# ============================================================

@app.route(
    "/heartbeat",
    methods=["POST"]
)
def heartbeat():

    global last_heartbeat

    with heartbeat_lock:
        last_heartbeat = time.monotonic()

    # The first heartbeat means the browser successfully
    # loaded the application.
    browser_connected.set()

    return jsonify({
        "status": "ok"
    })


# ============================================================
# Browser startup
# ============================================================

def find_browser():
    """
    Find Microsoft Edge or Google Chrome.

    Returning None means that the system's default browser
    will be used instead.
    """

    program_files = os.environ.get(
        "PROGRAMFILES",
        ""
    )

    program_files_x86 = os.environ.get(
        "PROGRAMFILES(X86)",
        ""
    )

    local_app_data = os.environ.get(
        "LOCALAPPDATA",
        ""
    )

    possible_browsers = [

        # Microsoft Edge
        os.path.join(
            program_files,
            "Microsoft",
            "Edge",
            "Application",
            "msedge.exe"
        ),

        os.path.join(
            program_files_x86,
            "Microsoft",
            "Edge",
            "Application",
            "msedge.exe"
        ),

        os.path.join(
            local_app_data,
            "Microsoft",
            "Edge",
            "Application",
            "msedge.exe"
        ),

        # Google Chrome
        os.path.join(
            program_files,
            "Google",
            "Chrome",
            "Application",
            "chrome.exe"
        ),

        os.path.join(
            program_files_x86,
            "Google",
            "Chrome",
            "Application",
            "chrome.exe"
        ),

        os.path.join(
            local_app_data,
            "Google",
            "Chrome",
            "Application",
            "chrome.exe"
        ),
    ]

    for browser in possible_browsers:

        if os.path.isfile(browser):
            return browser

    return None


def open_browser():
    """
    Open the application in a dedicated browser-style window.

    Edge/Chrome are launched with --app so the user sees
    an application window rather than a normal browser tab.
    """

    # Wait for Flask to start.
    server_started.wait()

    # Give the server a small amount of time to begin
    # accepting requests.
    time.sleep(0.5)

    browser = find_browser()

    if browser:

        try:
            app_data_dir = os.path.join(
                tempfile.gettempdir(),
                "geostitcher_browser_data"
            )

            os.makedirs(
                app_data_dir,
                exist_ok=True
            )

            subprocess.Popen([
                browser,
                f"--app={APP_URL}",
                "--window-size=600,600",
                f"--user-data-dir={app_data_dir}",
                "--no-first-run",
                "--no-default-browser-check"
                "--disable-extensions",
            ])

            print(
                f"Opened application at {APP_URL}"
            )

            return

        except Exception as e:

            print(
                f"Could not launch browser: {e}"
            )

    # Fallback to the user's default browser.
    try:

        webbrowser.open_new(
            APP_URL
        )

        print(
            f"Opened application at {APP_URL}"
        )

    except Exception as e:

        print(
            f"Could not open browser: {e}"
        )


# ============================================================
# Browser monitoring
# ============================================================

def monitor_browser():
    """
    Shut down the application when the browser page closes.

    The browser sends a heartbeat every second through
    JavaScript in index.html.

    We only begin monitoring after receiving the first
    heartbeat. This prevents the server from shutting down
    while the browser is still starting.
    """

    print(
        "Waiting for browser connection..."
    )

    browser_connected.wait()

    print(
        "Browser connected."
    )

    while not shutdown_requested.is_set():

        time.sleep(
            HEARTBEAT_INTERVAL
        )

        with heartbeat_lock:

            heartbeat = last_heartbeat

        if heartbeat is None:
            continue

        elapsed = (
            time.monotonic()
            - heartbeat
        )

        if elapsed > HEARTBEAT_TIMEOUT:

            print(
                "Browser closed. "
                "Shutting down application..."
            )

            shutdown_requested.set()

            if server is not None:

                try:
                    server.shutdown()

                except Exception:
                    pass

            break


# ============================================================
# Flask server
# ============================================================

def run_server():
    """
    Run Flask through Werkzeug directly.

    This avoids Flask's development reloader and gives us
    direct control over server.shutdown().
    """

    global server

    server = make_server(
        HOST,
        PORT,
        app,
        threaded=True
    )

    server_started.set()

    print(
        f"Server running at {APP_URL}"
    )

    try:

        server.serve_forever()

    finally:

        print(
            "Server stopped."
        )


# ============================================================
# Main application
# ============================================================

def main():
    """
    Start the complete desktop application.
    """

    # Start Flask.
    server_thread = threading.Thread(
        target=run_server,
        daemon=True
    )

    server_thread.start()

    # Start browser.
    browser_thread = threading.Thread(
        target=open_browser,
        daemon=True
    )

    browser_thread.start()

    # Monitor the browser.
    monitor_thread = threading.Thread(
        target=monitor_browser,
        daemon=True
    )

    monitor_thread.start()

    # Wait until shutdown has been requested.
    shutdown_requested.wait()

    print(
        "PPTX Audio Stitcher shutting down..."
    )

    # Make sure the server is stopped.
    if server is not None:

        try:
            server.shutdown()

        except Exception:
            pass

    server_thread.join(
        timeout=3
    )

    print(
        "PPTX Audio Stitcher closed."
    )


if __name__ == "__main__":
    main()