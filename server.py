from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fingerprint import AudioFingerprinter
from database import AudioDatabase
from pydub import AudioSegment
import os
import shutil
from collections import Counter
import static_ffmpeg
static_ffmpeg.add_paths()

app = FastAPI()

# --- 1. SETUP DATABASE & CORS ---
db = AudioDatabase()
fingerprinter = AudioFingerprinter()

@app.on_event("startup")
async def startup_event():
    print("🔄 STARTUP: Checking database tables...")
    try:
        db.create_tables()
        print("✅ SUCCESS: Database tables are ready.")
    except Exception as e:
        print(f"❌ ERROR: Could not create tables. {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AudioPrint Backend is Live!"}

# --- 2. THE NEW UPLOAD ROUTE (Use this to add songs!) ---
@app.post("/register")
async def register_endpoint(file: UploadFile = File(...), song_name: str = Form(...)):
    print(f"🎤 UPLOAD: Processing '{song_name}'...")
    raw_filename = f"temp_register_{file.filename}"
    clean_wav_filename = f"temp_register_clean.wav"

    try:
        # 1. Save and Convert
        with open(raw_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        audio = AudioSegment.from_file(raw_filename)
        audio = audio.set_channels(1).set_frame_rate(22050)
        audio.export(clean_wav_filename, format="wav")

        # 2. Fingerprint
        S = fingerprinter.file_to_spectrogram(clean_wav_filename)
        peaks = fingerprinter.find_peaks(S, amp_min=-40)
        hashes = fingerprinter.generate_hashes(peaks)
        print(f"DEBUG: Generated {len(hashes)} hashes for {song_name}")

        # 3. Save to Database
        song_id = db.add_song(song_name, "file_hash_placeholder")
        db.insert_fingerprints(song_id, hashes)
        
        return {"status": "success", "message": f"Successfully added {song_name}"}

    except Exception as e:
        print(f"Register Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp files
        if os.path.exists(raw_filename): os.remove(raw_filename)
        if os.path.exists(clean_wav_filename): os.remove(clean_wav_filename)


# --- 3. THE FIXED IDENTIFY ROUTE ---
@app.post("/identify")
async def identify_endpoint(file: UploadFile = File(...)):
    raw_filename = f"temp_upload_{file.filename}"
    clean_wav_filename = "temp_clean.wav"
    
    try:
        # 1. Save and Convert
        with open(raw_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio = AudioSegment.from_file(raw_filename)
        audio = audio.set_channels(1).set_frame_rate(22050)
        audio.export(clean_wav_filename, format="wav")

        # 2. Fingerprint
        S = fingerprinter.file_to_spectrogram(clean_wav_filename)
        peaks = fingerprinter.find_peaks(S, amp_min=-40)
        hashes = fingerprinter.generate_hashes(peaks)
        print(f"DEBUG: Generated {len(hashes)} hashes from recording.")

        # 3. Search Database
        matches = db.get_matches(hashes)
        print(f"DEBUG: Database returned {len(matches)} matches.")

        if not matches:
            return {"status": "fail", "message": "No matches found"}

        # 4. FIX: Count SONG NAMES, not raw tuples
        # matches structure: [(hash, song_name, offset), ...]
        song_names = [m[1] for m in matches]
        top_match = Counter(song_names).most_common(1)[0]
        
        best_song = top_match[0]
        score = top_match[1]

        print(f"🎶 IDENTIFIED: {best_song} (Score: {score})")

        return {
            "status": "success",
            "song": best_song,
            "confidence": score
        }

    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(raw_filename): os.remove(raw_filename)
        if os.path.exists(clean_wav_filename): os.remove(clean_wav_filename)