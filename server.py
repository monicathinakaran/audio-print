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
        
        # --- THE FIX: TRIM TO FIRST 60 SECONDS ---
        # Free servers are too slow for full songs. 
        # 60 seconds is PLENTY for identification.
        audio = audio[:60000] 
        # -----------------------------------------

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
from collections import defaultdict

@app.post("/identify")
async def identify_endpoint(file: UploadFile = File(...)):
    raw_filename = f"temp_upload_{file.filename}"
    clean_wav_filename = "temp_clean.wav"
    
    try:
        # 1. Save and Convert (Keep the 60s trim for speed!)
        with open(raw_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        audio = AudioSegment.from_file(raw_filename)
        audio = audio[:60000] # Trim to 60s
        audio = audio.set_channels(1).set_frame_rate(22050)
        audio.export(clean_wav_filename, format="wav")

        # 2. Fingerprint
        S = fingerprinter.file_to_spectrogram(clean_wav_filename)
        peaks = fingerprinter.find_peaks(S, amp_min=-40)
        hashes = fingerprinter.generate_hashes(peaks)
        print(f"DEBUG: Generated {len(hashes)} hashes.")

        # 3. Search Database
        matches = db.get_matches(hashes)
        print(f"DEBUG: Database returned {len(matches)} matches.")

        if not matches:
            return {"status": "fail", "message": "No matches found"}

        # --- 4. ALIGNMENT LOGIC (Calculates the Offset) ---
        # Map input hashes to their time offsets
        # hashes = [(hash_val, time_offset), ...]
        input_mapper = {str(h): t for h, t in hashes}
        
        song_scores = Counter()
        song_offsets = defaultdict(list)
        
        # match = (hash_val, song_name, db_offset)
        for h, name, db_offset in matches:
            song_scores[name] += 1
            
            # Calculate the true start time: (DB Time - Sample Time)
            if h in input_mapper:
                sample_offset = input_mapper[h]
                true_offset = db_offset - sample_offset
                song_offsets[name].append(true_offset)

        # Find the best song
        best_song, score = song_scores.most_common(1)[0]
        
        # Find the most common time offset for this song
        # This filters out random noise matches
        best_offset_val = Counter(song_offsets[best_song]).most_common(1)[0][0]
        
        # Convert to seconds (Standard logic: Offset * Hop / Rate)
        seconds = (best_offset_val * 2048) / 22050

        print(f"🎶 IDENTIFIED: {best_song} (Score: {score})")

        return {
            "status": "success",
            "song": best_song,
            "confidence": score,
            "offset_seconds": round(seconds, 2) # <--- This fixes the 's' bug!
        }

    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(raw_filename): os.remove(raw_filename)
        if os.path.exists(clean_wav_filename): os.remove(clean_wav_filename)