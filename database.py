import psycopg2
from psycopg2.extras import execute_values
import os

class AudioDatabase:
    def __init__(self):
                # Get DB URL from Environment (Render provides this)
                # Fallback to local config if not found
                db_url = os.getenv("DATABASE_URL")
                
                if db_url:
                    self.conn = psycopg2.connect(db_url)
                else:
                    # YOUR LOCAL CONFIG
                    self.conn = psycopg2.connect(
                        dbname="audioprint",
                        user="postgres", 
                        password="Sreethika@123", 
                        host="localhost"
                    )
                self.cur = self.conn.cursor()

    def create_tables(self):
            """Creates the necessary database tables if they are missing."""
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
                    hash VARCHAR(64) NOT NULL,
                    song_id INTEGER REFERENCES songs(song_id) ON DELETE CASCADE,
                    offset_val INTEGER NOT NULL
                )
                """,
                # Create an index to make searching faster
                "CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints(hash)"
            ]
            try:
                for command in commands:
                    self.cur.execute(command)
                self.conn.commit()
                print("DEBUG: Database tables checked/created successfully.")
            except Exception as e:
                print(f"Database Init Error: {e}")
                self.conn.rollback()

    def store_fingerprint(self, song_name, hashes):
        """
        1. Insert song name -> Get song_id
        2. Bulk insert hashes linked to that song_id
        """
        # 1. Insert Song
        self.cur.execute("""
            INSERT INTO songs (song_name) 
            VALUES (%s) 
            RETURNING song_id;
        """, (song_name,))
        
        song_id = self.cur.fetchone()[0]
        
        # 2. Prepare Data for Bulk Insert
        # We need a list of tuples: (hash, song_id, offset)
        data_to_insert = []
        for h, t_time in hashes:
            # h is the tuple (freq1, freq2, delta)
            hash_str = str(h) 
            
            # --- THE FIX IS HERE ---
            # t_time is a numpy.int64. We must cast it to a standard python int.
            offset = int(t_time) 
            
            data_to_insert.append((hash_str, song_id, offset))
            
        print(f"Pushing {len(data_to_insert)} hashes to Postgres...")
        
        # 3. Bulk Insert (Super Fast)
        query = "INSERT INTO fingerprints (hash_val, song_id, offset_val) VALUES %s"
        execute_values(self.cur, query, data_to_insert)
        
        self.conn.commit()

    def find_matches(self, sample_hashes):
        """
        1. Extract just the hash strings from the sample
        2. Query DB for all matching rows
        """
        # Prepare the list of hash strings to look for
        # sample_hashes is list of (hash_tuple, time_sample)
        hash_list = [str(h[0]) for h in sample_hashes]
        
        # Map specific hash strings to their sample times so we can calc offset later
        # Key: Hash_String, Value: Sample_Time
        # (Note: simpler implementation, assumes hash unique in sample for speed)
        sample_map = {str(h[0]): h[1] for h in sample_hashes}
        
        # SQL: Find all rows where hash_val is in our list
        # We cast the list to a tuple for the SQL IN clause
        if not hash_list:
            return []
            
        placeholders = ','.join(['%s'] * len(hash_list))
        query = f"""
            SELECT f.hash_val, s.song_name, f.offset_val
            FROM fingerprints f
            JOIN songs s ON f.song_id = s.song_id
            WHERE f.hash_val IN ({placeholders});
        """
        
        self.cur.execute(query, tuple(hash_list))
        results = self.cur.fetchall()
        
        matches = []
        for r in results:
            # r = (hash_val, song_name, db_offset)
            h_val, song_name, db_offset = r
            
            # Calculate the relative offset
            # offset = db_time - sample_time
            if h_val in sample_map:
                sample_time = sample_map[h_val]
                offset = db_offset - sample_time
                matches.append((song_name, offset))
                
        return matches