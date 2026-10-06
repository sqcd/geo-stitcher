// =========================
// Get DOM Elements
// =========================

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const filenameDisplay = document.getElementById("filename");

const conversionArea =
    document.getElementById("conversion-area");

const progressText =
    document.getElementById("progress-text");

const progressBar =
    document.getElementById("progress-bar");

const progressPercentage =
    document.getElementById("progress-percentage");

const convertButton =
    document.getElementById("convert-button");

const status =
    document.getElementById("status");

const statusText =
    document.getElementById("status-text");

const finishedArea =
    document.getElementById("finished-area");

const downloadButton =
    document.getElementById("download-button");

const startOverButton =
    document.getElementById("start-over-button");


// =========================
// State
// =========================

let selectedFile = null;
let currentJobId = null;
let pollingInterval = null;


// =========================
// File Selection
// =========================

fileInput.addEventListener("change", function () {

    if (fileInput.files.length === 0) {
        return;
    }

    handleFile(fileInput.files[0]);
});


// =========================
// Handle File
// =========================

function handleFile(file) {

    // Make sure it is a PPTX
    if (!file.name.toLowerCase().endsWith(".pptx")) {

        showError(
            "Please select a PowerPoint (.pptx) file."
        );

        return;
    }

    selectedFile = file;

    filenameDisplay.textContent = file.name;

    convertButton.disabled = false;

    hideStatus();

    finishedArea.classList.add("hidden");

    conversionArea.classList.add("hidden");
}


// =========================
// Drag and Drop
// =========================

dropZone.addEventListener(
    "dragover",
    function (event) {

        event.preventDefault();

        dropZone.classList.add("dragover");
    }
);


dropZone.addEventListener(
    "dragleave",
    function () {

        dropZone.classList.remove("dragover");
    }
);


dropZone.addEventListener(
    "drop",
    function (event) {

        event.preventDefault();

        dropZone.classList.remove("dragover");

        if (event.dataTransfer.files.length === 0) {
            return;
        }

        handleFile(
            event.dataTransfer.files[0]
        );
    }
);


// =========================
// Convert Button
// =========================

convertButton.addEventListener(
    "click",
    function () {

        if (!selectedFile) {
            return;
        }

        startConversion();
    }
);


// =========================
// Start Conversion
// =========================

async function startConversion() {

    // Disable the button while converting
    convertButton.disabled = true;

    // Show progress area
    conversionArea.classList.remove("hidden");

    // Hide previous messages
    hideStatus();

    finishedArea.classList.add("hidden");

    // Reset progress
    updateProgress(0, "Starting conversion...");

    // Create form data
    const formData = new FormData();

    formData.append(
        "pptx",
        selectedFile
    );


    try {

        // Send file to Flask
        const response = await fetch(
            "/convert",
            {
                method: "POST",
                body: formData
            }
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Failed to start conversion."
            );
        }


        // Save job ID
        currentJobId = data.job_id;


        // Begin checking progress
        startPolling();


    } catch (error) {

        console.error(error);

        showError(
            error.message ||
            "Something went wrong."
        );

        convertButton.disabled = false;
    }
}


// =========================
// Poll Conversion Status
// =========================

function startPolling() {

    // Prevent multiple polling loops
    stopPolling();


    pollingInterval = setInterval(
        checkStatus,
        500
    );

    // Check immediately instead of waiting 500ms
    checkStatus();
}

// =========================
// Send Heartbeat
// =========================

function sendHeartbeat() {
    fetch("/heartbeat", {
        method: "POST"
    }).catch(() => {});
}

sendHeartbeat();

setInterval(sendHeartbeat, 1000); // Every 30 seconds

// =========================
// Check Status
// =========================

async function checkStatus() {

    if (!currentJobId) {
        return;
    }


    try {

        const response = await fetch(
            `/status/${currentJobId}`
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to check conversion status."
            );
        }


        // =========================
        // Processing
        // =========================

        if (data.status === "processing") {

            handleProcessingStatus(data);

            return;
        }


        // =========================
        // Complete
        // =========================

        if (data.status === "complete") {

            handleComplete();

            return;
        }


        // =========================
        // Error
        // =========================

        if (data.status === "error") {

            handleConversionError(
                data.error ||
                "Conversion failed."
            );

            return;
        }

    } catch (error) {

        console.error(
            "Status check failed:",
            error
        );

        stopPolling();

        showError(
            error.message ||
            "Lost connection to the server."
        );

        convertButton.disabled = false;
    }
}


// =========================
// Handle Processing Status
// =========================

function handleProcessingStatus(data) {

    const currentSlide =
        data.current_slide || 0;

    const totalSlides =
        data.total_slides || 0;

    const stage =
        data.stage || "converting";


    // -------------------------
    // Converting slides
    // -------------------------

    if (
        stage === "converting" &&
        totalSlides > 0
    ) {

        const percentage =
            Math.round(
                (currentSlide / totalSlides) * 99
            );


        updateProgress(
            percentage,
            `Converting slide ${currentSlide} of ${totalSlides}`
        );

        return;
    }


    // -------------------------
    // Starting
    // -------------------------

    if (stage === "starting") {

        updateProgress(
            0,
            "Preparing presentation..."
        );

        return;
    }


    // -------------------------
    // Exporting
    // -------------------------

    if (stage === "exporting") {

        updateProgress(
            99,
            "Combining audio and exporting MP3..."
        );

        return;
    }


    // -------------------------
    // Fallback
    // -------------------------

    updateProgress(
        0,
        "Processing presentation..."
    );
}


// =========================
// Update Progress Bar
// =========================

function updateProgress(
    percentage,
    message
) {

    // Keep percentage between 0 and 100
    percentage =
        Math.max(
            0,
            Math.min(
                100,
                percentage
            )
        );


    progressBar.style.width =
        `${percentage}%`;


    progressPercentage.textContent =
        `${percentage}%`;


    progressText.textContent =
        message;


    // Update accessibility information
    const progressTrack =
        document.querySelector(
            ".progress-track"
        );


    progressTrack.setAttribute(
        "aria-valuenow",
        percentage
    );
}


// =========================
// Conversion Complete
// =========================

function handleComplete() {

    stopPolling();

    updateProgress(
        100,
        "Conversion complete!"
    );


    // Show finished controls
    finishedArea.classList.remove(
        "hidden"
    );


    // Set download URL
    downloadButton.href =
        `/download/${currentJobId}`;


    // Change button text if desired
    downloadButton.textContent =
        "Download MP3";


    // Make sure Convert cannot be
    // accidentally clicked again
    convertButton.disabled = true;
}


// =========================
// Conversion Error
// =========================

function handleConversionError(
    message
) {

    stopPolling();

    showError(message);

    conversionArea.classList.add(
        "hidden"
    );

    convertButton.disabled = false;
}


// =========================
// Show Error
// =========================

function showError(message) {

    statusText.textContent = message;

    status.classList.remove(
        "hidden"
    );

    status.classList.add(
        "error"
    );
}


// =========================
// Hide Status
// =========================

function hideStatus() {

    status.classList.add(
        "hidden"
    );

    status.classList.remove(
        "error"
    );

    statusText.textContent = "";
}


// =========================
// Stop Polling
// =========================

function stopPolling() {

    if (pollingInterval !== null) {

        clearInterval(
            pollingInterval
        );

        pollingInterval = null;
    }
}


// =========================
// Start Over
// =========================

startOverButton.addEventListener(
    "click",
    function () {

        // Stop any existing polling
        stopPolling();


        // Reset application state
        selectedFile = null;

        currentJobId = null;


        // Reset file input
        fileInput.value = "";


        // Reset filename
        filenameDisplay.textContent = "";


        // Reset progress
        updateProgress(
            0,
            "Starting conversion..."
        );


        // Hide conversion area
        conversionArea.classList.add(
            "hidden"
        );


        // Hide finished area
        finishedArea.classList.add(
            "hidden"
        );


        // Hide status
        hideStatus();


        // Re-enable convert button,
        // but keep it disabled until
        // another file is selected
        convertButton.disabled = true;
    }
);