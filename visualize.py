import matplotlib.pyplot as plt
import librosa.display
import numpy as np
from fingerprint import AudioFingerprinter

# Initialize
fp = AudioFingerprinter()
file_path = "assets/Alone_-_Color_Out.mp3"

print("1. Loading 10 seconds of audio...")
# CRITICAL FIX: Only load 10 seconds. 
# This makes the plot readable and prevents the crash.
y, sr = librosa.load(file_path, sr=22050, duration=10)

print("2. Generating Spectrogram...")
# We manually do the steps from file_to_spectrogram here so we can use 'y'
D = librosa.stft(y, n_fft=4096, hop_length=2048)
S = librosa.amplitude_to_db(np.abs(D), ref=np.max)

print("3. Finding Peaks...")
# We use the same threshold as your main logic
peaks = fp.find_peaks(S, amp_min=-40)
print(f"Found {len(peaks)} peaks in this snippet.")

# --- PLOTTING ---
print("4. Plotting...")
plt.figure(figsize=(12, 8))

# Draw the Spectrogram
# We use y_axis='linear' because it is faster/safer for simple visualization than 'mel'
librosa.display.specshow(S, sr=22050, hop_length=2048, x_axis='time', y_axis='linear')
plt.colorbar(format='%+2.0f dB')
plt.title(f"Audio Constellation Map (10s Snippet)")

# Overlay the Peaks
if len(peaks) > 0:
    # Convert matrix indices to Time (x) and Frequency (y)
    time_idx = peaks[:, 1]
    freq_idx = peaks[:, 0]
    
    # Mathematical conversion so dots line up with the heat map
    times = librosa.frames_to_time(time_idx, sr=22050, hop_length=2048)
    freqs = librosa.fft_frequencies(sr=22050, n_fft=4096)[freq_idx]
    
    plt.scatter(times, freqs, color='#00ff00', s=10, marker='x', alpha=0.8, label='Constellation Points')

plt.legend(loc='upper right')
print("Showing plot...")
plt.show()