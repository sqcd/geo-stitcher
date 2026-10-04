import os
import sys
import io
import zipfile

from pydub import AudioSegment
from pydub.utils import which

FORMATS = ['mp3', 'wav', 'm4a']
GAP = 1000

def main():
    pptx_path = input("Enter the path to the .pptx file: ")
    output_path = input("Enter the path for the output MP3 file: ")

    extract_and_stitch_audio(pptx_path, output_path)

def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

    bundled_ffmpeg = os.path.join(
        base_dir,
        "ffmpeg",
        "ffmpeg.exe"
    )

    if os.path.exists(bundled_ffmpeg):
        return bundled_ffmpeg

    system_ffmpeg = which("ffmpeg")

    if system_ffmpeg:
        return system_ffmpeg

    raise FileNotFoundError(
        "FFmpeg could not be found."
    )

def extract_and_stitch_audio(pptx_path, output_path, progress_callback=None):

    audio_files = []

    with zipfile.ZipFile(pptx_path, 'r') as pptx:
        for filename in pptx.namelist():
            if filename.startswith('ppt/media/') and filename.lower().endswith(tuple(FORMATS)):
                slide_number = int(filename.split('/')[2].split('.')[0][5:])  # Extract slide number from filename
                audio_files.append((slide_number, filename))

        audio_files.sort(key=lambda x: x[0])

        if not audio_files:
            raise ValueError("No audio files found in the .pptx file.")

        total_audio_files = len(audio_files)

        print(f"Found {total_audio_files} audio files. Starting extraction and stitching...")

        AudioSegment.converter = get_ffmpeg_path()

        combined_audio = AudioSegment.empty()

        for index, (slide_number, filename) in enumerate(audio_files, start=1):
            print(f"Extracting audio from slide {slide_number}: {filename}")

            audio_data = pptx.read(filename)
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format=filename.split('.')[-1])
            combined_audio += audio_segment

            if index < total_audio_files:
                combined_audio += AudioSegment.silent(duration=GAP)

            if progress_callback:
                progress_callback(index, total_audio_files, stage="converting")

        print(f"Exporting combined audio to {output_path}...")

        if progress_callback:
            progress_callback(total_audio_files, total_audio_files, stage="exporting")

        combined_audio.export(output_path, format="mp3", bitrate="192k")

        print("Audio extraction and stitching completed successfully.")

def get_slide_count(pptx_path):
    with zipfile.ZipFile(pptx_path, 'r') as pptx:
        slide_files = [f for f in pptx.namelist() if (f.startswith('ppt/slides/slide') and f.endswith('.xml'))]
        return len(slide_files)

if __name__ == "__main__":
    main()