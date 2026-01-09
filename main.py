import os
import numpy as np
from collections import Counter
import sounddevice as sd
import scipy.io.wavfile as wav
from fingerprint import AudioFingerprinter
from database import AudioDatabase

# Initialize systems
fingerprinter = AudioFingerprinter()
db = AudioDatabase()

def register_song(file_path):
    """ Adds a full song to the database """
    song_name = os.path.basename(file_path)
    print(f"Processing: {song_name}")
    
    # 1. Get Spectrogram
    S = fingerprinter.file_to_spectrogram(file_path)
    
    # 2. Find Peaks
    peaks = fingerprinter.find_peaks(S)
    
    # 3. Generate Hashes
    hashes = fingerprinter.generate_hashes(peaks)
    
    # 4. Store in DB
    db.store_fingerprint(song_name, hashes)
    print("Done!")

def record_audio(duration=5, fs=22050):
    """ Records audio from microphone """
    print("Recording...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()  # Wait until recording is finished
    print("Finished recording.")
    
    # Save to temporary file to reuse existing load logic
    filename = "temp_query.wav"
    wav.write(filename, fs, (recording * 32767).astype(np.int16))
    return filename

def identify_song(file_path):
    # 1. Fingerprint the sample
    S = fingerprinter.file_to_spectrogram(file_path)
    peaks = fingerprinter.find_peaks(S, amp_min=-40) # Lower threshold for mic noise
    hashes = fingerprinter.generate_hashes(peaks)
    
    # 2. Find matches
    matches = db.find_matches(hashes)
    
    # 3. Analyze matches (The Histogram Method)
    # We want the (song, offset) that appears most frequently
    if not matches:
        print("No matches found.")
        return

    # Count occurrences of (song_name, offset)
    # Ideally, the correct song will have a huge spike at a specific offset
    most_common = Counter(matches).most_common(1)
    
    best_match = most_common[0]
    match_tuple = best_match[0] # (song_name, offset)
    count = best_match[1]       # How many hashes matched
    
    print(f"\n--- RESULT ---")
    print(f"Song: {match_tuple[0]}")
    print(f"Confidence (Matches): {count}")
    print(f"Offset: {match_tuple[1]}")

# --- CLI Menu ---
if __name__ == "__main__":
    while True:
        print("\n1. Add Song to Library")
        print("2. Listen & Identify (via Mic)")
        print("3. Identify from File")
        print("4. Exit")
        choice = input("Select: ")
        
        if choice == '1':
            path = input("Enter path to wav/mp3 file: ").strip('"')
            register_song(path)
        elif choice == '2':
            temp_file = record_audio()
            identify_song(temp_file)
        elif choice == '3':
            path = input("Enter path to sample file: ").strip('"')
            identify_song(path)
        elif choice == '4':
            break