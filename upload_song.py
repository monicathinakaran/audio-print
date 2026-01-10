import requests

# 1. Your Render URL (Make sure this is correct)
# IMPORTANT: Check your server.py to see if the route is "/register" or "/upload"
URL = "http://127.0.0.1:8000/register" 

# 2. The song you want to upload (put an mp3 in the same folder)
file_path = "D:\\Projects\\AudioPrint\\assets\\test_song.wav" 
song_name = "Girls Like you - Maroon 5"

# 3. Send it to the server
with open(file_path, "rb") as f:
    print(f"Uploading {song_name}...")
    response = requests.post(URL, files={"file": f}, data={"song_name": song_name})

print("Server Response:", response.text)