import os
import psycopg2
from psycopg2.extras import execute_values
from urllib.parse import urlparse

class AudioDatabase:
    def __init__(self):
        # 1. Connect to Database (Render or Local)
        db_url = os.getenv("DATABASE_URL")
        
        try:
            if db_url:
                self.conn = psycopg2.connect(db_url)
            else:
                self.conn = psycopg2.connect(
                    dbname="audioprint",
                    user="postgres",
                    password="password", 
                    host="localhost"
                )
            self.cur = self.conn.cursor()
        except Exception as e:
            print(f"CRITICAL: Could not connect to DB. {e}")
            raise e
            
        # 2. Force table creation on startup
        self.create_tables()

    def create_tables(self):
        """Creates tables if they are missing."""
        commands = [
            """
            CREATE TABLE IF NOT EXISTS songs (
                song_id SERIAL PRIMARY KEY,
                song_name VARCHAR(255) NOT NULL,
                file_hash VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fingerprints (
                hash VARCHAR(255) NOT NULL, 
                song_id INTEGER REFERENCES songs(song_id) ON DELETE CASCADE,
                offset_val INTEGER NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints(hash)"
        ]
        try:
            for command in commands:
                self.cur.execute(command)
            self.conn.commit()
            print("DEBUG: Database tables checked/created.")
        except Exception as e:
            print(f"Database Init Error: {e}")
            self.conn.rollback()

    def get_matches(self, hashes):
        """
        Search for matching fingerprints.
        Fixes the 'hash_val' error and cleans up numpy data types.
        """
        # 1. Convert all hashes to pure strings to avoid 'np.int64' errors
        hash_list = [str(h) for h in hashes.keys()]
        
        if not hash_list:
            return []

        # 2. Use the correct column name 'hash' (not hash_val)
        # 3. Use ANY(%s) for safer, faster querying
        query = """
            SELECT f.hash, s.song_name, f.offset_val
            FROM fingerprints f
            JOIN songs s ON f.song_id = s.song_id
            WHERE f.hash = ANY(%s)
        """
        
        try:
            self.cur.execute(query, (hash_list,))
            return self.cur.fetchall()
        except Exception as e:
            print(f"Search Error: {e}")
            self.conn.rollback()
            return []

    def insert_fingerprints(self, song_id, hashes):
        """
        Batch insert hashes.
        hashes: list of (hash_tuple, offset)
        """
        if not hashes:
            return
            
        # Clean data: Convert hash tuple to string, ensure offset is int
        data_to_insert = [(str(h), song_id, int(o)) for (h, o) in hashes]
        
        query = "INSERT INTO fingerprints (hash, song_id, offset_val) VALUES %s"
        
        try:
            execute_values(self.cur, query, data_to_insert)
            self.conn.commit()
            print(f"DEBUG: Inserted {len(hashes)} fingerprints.")
        except Exception as e:
            print(f"Insert Error: {e}")
            self.conn.rollback()

    def add_song(self, song_name, file_hash):
        """Registers a song and returns its ID."""
        try:
            self.cur.execute(
                "INSERT INTO songs (song_name, file_hash) VALUES (%s, %s) RETURNING song_id",
                (song_name, file_hash)
            )
            song_id = self.cur.fetchone()[0]
            self.conn.commit()
            return song_id
        except Exception as e:
            print(f"Add Song Error: {e}")
            self.conn.rollback()
            return None