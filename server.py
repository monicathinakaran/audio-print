from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fingerprint import AudioFingerprinter
from database import AudioDatabase
from pydub import AudioSegment  # <--- Import this
import os
import shutil
from collections import Counter
import static_ffmpeg  # <--- Add this
static_ffmpeg.add_paths() # <--- Add this

app = FastAPI()

# Initialize Database
db = AudioDatabase()

# --- ADD THIS BLOCK ---
@app.on_event("startup")
async def startup_event():
    print("🔄 STARTUP: Checking database tables...")
    try:
        # This forces the create_tables method to run immediately
        db.create_tables()
        print("✅ SUCCESS: Database tables are ready.")
    except Exception as e:
        print(f"❌ ERROR: Could not create tables. {e}")
        
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow Vercel to talk to Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fingerprinter = AudioFingerprinter()
db = AudioDatabase()

@app.get("/")
async def root():
    return {"message": "AudioPrint Backend is Live! Use POST /identify to search."}

@app.post("/identify")
async def identify_endpoint(file: UploadFile = File(...)):
    # 1. Save the uploaded raw file (likely WebM despite the name)
    raw_filename = f"temp_upload_{file.filename}"
    clean_wav_filename = "temp_clean.wav"
    
    try:
        # Save raw bytes
        with open(raw_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"DEBUG: Saved raw file {raw_filename} ({os.path.getsize(raw_filename)} bytes)")

        # 2. Convert to WAV using Pydub (The Fix)
        # This handles WebM, MP4, M4A automatically
        try:
            audio = AudioSegment.from_file(raw_filename)
            # Force mono and correct sample rate to match your fingerprinter
            audio = audio.set_channels(1).set_frame_rate(22050)
            audio.export(clean_wav_filename, format="wav")
            print("DEBUG: Converted to clean WAV format.")
        except Exception as e:
            print(f"Conversion Error: {e}")
            return {"status": "fail", "message": "Could not decode audio file"}

        # 3. Process the Clean WAV
        print("DEBUG: Generating Spectrogram...")
        S = fingerprinter.file_to_spectrogram(clean_wav_filename)
        
        # FIND PEAKS
        peaks = fingerprinter.find_peaks(S, amp_min=-40)
        print(f"DEBUG: Found {len(peaks)} peaks in recording.")  # <--- CRITICAL CHECK
        
        if len(peaks) == 0:
            print("DEBUG: FAILURE - No peaks found. Audio might be too quiet or threshold too high.")
        
        # GENERATE HASHES
        hashes = fingerprinter.generate_hashes(peaks)
        print(f"DEBUG: Generated {len(hashes)} hashes from peaks.") # <--- CRITICAL CHECK

        # SEARCH DB
        matches = db.find_matches(hashes)
        print(f"DEBUG: Database returned {len(matches)} matching hashes.")
        
        if not matches:
            print("DEBUG: No matches found.")
            return {"status": "fail", "message": "No matches found"}
            
        # --- THE DECISION LOGIC ---
        from collections import Counter
        
        # matches is a list of (SongName, Offset)
        # We want to find the most common (SongName, Offset) pair
        most_common = Counter(matches).most_common(1)
        
        best_match_tuple = most_common[0]  # e.g. (('Song A', 150), 500)
        
        song_identifier = best_match_tuple[0] # ('Song A', 150)
        match_score = best_match_tuple[1]     # 500
        
        song_name = song_identifier[0]
        offset_val = song_identifier[1]
        
        # --- PRINT THE VICTORY MESSAGE ---
        print(f"\n=======================================")
        print(f"🎶 IDENTIFIED: {song_name}")
        print(f"🔥 SCORE: {match_score} matches")
        print(f"=======================================\n")

        seconds = (offset_val * 2048) / 22050
        
        return {
            "status": "success",
            "song": song_name,
            "confidence": match_score,
            "offset_seconds": round(seconds, 2)
        }

    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup
        '''if os.path.exists(raw_filename):
            os.remove(raw_filename)
        if os.path.exists(clean_wav_filename):
            os.remove(clean_wav_filename)'''