import numpy as np
import librosa
from scipy.ndimage import maximum_filter
from pydub import AudioSegment
import os

class AudioFingerprinter:
    def __init__(self):
        # Constants for DSP
        self.sampling_rate = 22050  # Standard for audio analysis
        self.n_fft = 4096           # Window size for FFT
        self.hop_length = 2048      # Overlap between windows
        self.fan_value = 40         # How many neighbors to pair with each peak
    
    def _convert_to_wav(self, file_path):
        """
        Helper: Converts any audio (mp3, m4a) to a temp wav file
        so librosa can read it reliably.
        """
        # If it's already wav, just return it
        if file_path.endswith('.wav'):
            return file_path

        print(f"Converting {file_path} to WAV for processing...")
        audio = AudioSegment.from_file(file_path)
        temp_path = "temp_convert.wav"
        audio.export(temp_path, format="wav")
        return temp_path
    
    def file_to_spectrogram(self, file_path):
        # Load audio
        y, sr = librosa.load(file_path, sr=self.sampling_rate)
        
        # DEBUG: Check if audio loaded correctly
        print(f"DEBUG: Loaded Audio. Shape: {y.shape}, Max Value: {np.max(y)}")
        if np.max(np.abs(y)) == 0:
            print("ERROR: Audio loaded as pure silence! Check file or FFmpeg.")
            return np.zeros((10, 10)) # Return dummy data to avoid crash

        # Calculate Spectrogram
        D = librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length)
        S = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        
        # DEBUG: Check Spectrogram values
        print(f"DEBUG: Spectrogram stats - Max: {np.max(S):.2f}, Min: {np.min(S):.2f}")
        
        return S

    def find_peaks(self, S, amp_min=-40):
        """
        Finds local maxima (peaks) in the spectrogram.
        These are the 'stars' in our constellation.
        """
        # Define a neighborhood to look for peaks (connects close points)
        # This structure defines the "local" area
        struct = np.ones((10, 10)) 
        
        # Apply the maximum filter: Replaces each pixel with the max value in its neighborhood
        local_max = maximum_filter(S, footprint=struct)
        
        # Boolean mask: True where the original pixel equals the local max
        background = (S == local_max)
        
        # Additional mask: Ignore silence (amplitude must be > amp_min)
        eroded_background = background & (S > amp_min)
        
        # Get indices of the peaks
        peaks = np.argwhere(eroded_background)
        
        # peaks is an array of [frequency_index, time_index]
        return peaks

    def generate_hashes(self, peaks):
        """
        Combinatorial Hashing (The Shazam Secret):
        Don't just store peaks. Store relationships between peaks.
        Hash = (freq_anchor, freq_target, time_difference)
        """
        hashes = []
        
        # Sort peaks by time to process sequentially
        peaks = sorted(peaks, key=lambda x: x[1])
        
        for i in range(len(peaks)):
            anchor = peaks[i] # [freq, time]
            
            # Look at the next 'fan_value' peaks to create pairs
            for j in range(1, self.fan_value):
                if (i + j) < len(peaks):
                    target = peaks[i + j]
                    
                    freq_anchor = anchor[0]
                    freq_target = target[0]
                    time_anchor = anchor[1]
                    time_target = target[1]
                    
                    # Calculate time delta
                    delta_t = time_target - time_anchor
                    
                    # Constraint: Target must be within a certain time window
                    # (e.g., within 5 seconds) to be a valid pair
                    if 0 < delta_t < 200: 
                        # Create the Hash
                        # We use a tuple or a string combination
                        h = (freq_anchor, freq_target, delta_t)
                        
                        # We store: (Hash, Absolute_Time_Of_Anchor)
                        hashes.append((h, time_anchor))
                        
        return hashes