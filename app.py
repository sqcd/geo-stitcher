import webbrowser

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)

from werkzeug.utils import secure_filename

import os
import tempfile
import threading
import uuid

from audio import (
    extract_and_stitch_audio,
    get_slide_count
)


app = Flask(__name__)

ALLOWED_EXTENSIONS = {"pptx"}


# =========================
# Conversion Jobs
# =========================

jobs = {}


# =========================
# Helper Functions
# =========================

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


# =========================
# Conversion Worker
# =========================

def convert_file(
    job_id,
    input_path,
    output_path,
    original_filename
):
    """
    Runs the conversion in a background thread.
    """

    try:

        # =========================
        # Get Slide Count
        # =========================

        total_slides = get_slide_count(
            input_path
        )

        jobs[job_id]["total_slides"] = (
            total_slides
        )


        # =========================
        # Progress Callback
        # =========================

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


        # =========================
        # Run Conversion
        # =========================

        extract_and_stitch_audio(
            input_path,
            output_path,
            progress_callback=update_progress
        )


        # =========================
        # Conversion Complete
        # =========================

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


# =========================
# Home Page
# =========================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================
# Start Conversion
# =========================

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    # -------------------------
    # Check File
    # -------------------------

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


    # -------------------------
    # Secure Filename
    # -------------------------

    original_filename = (
        secure_filename(
            file.filename
        )
    )


    # Remove .pptx
    presentation_name = (
        os.path.splitext(
            original_filename
        )[0]
    )


    # Default output name
    output_filename = (
        f"combined_"
        f"{presentation_name}"
        f".mp3"
    )


    # -------------------------
    # Temporary Directory
    # -------------------------

    temp_dir = tempfile.mkdtemp()


    input_path = os.path.join(
        temp_dir,
        original_filename
    )


    output_path = os.path.join(
        temp_dir,
        output_filename
    )


    # Save uploaded file
    file.save(
        input_path
    )


    # -------------------------
    # Create Job
    # -------------------------

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


    # -------------------------
    # Start Background Thread
    # -------------------------

    thread = threading.Thread(
        target=convert_file,

        args=(
            job_id,
            input_path,
            output_path,
            original_filename
        )
    )

    thread.start()


    return jsonify({
        "job_id": job_id
    })


# =========================
# Conversion Status
# =========================

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


# =========================
# Download MP3
# =========================

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


# =========================
# Run Application
# =========================

if __name__ == "__main__":
    webbrowser.open(
        "http://127.0.0.1:5000"
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )