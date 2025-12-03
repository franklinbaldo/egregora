
import duckdb
import ibis
import tempfile
import os

def test_ibis_connect_shared():
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as tmp:
        db_path = tmp.name
    os.remove(db_path) # DuckDB will create it
    
    try:
        print(f"DB Path: {db_path}")
        try:
            # Connect via ibis first
            ibis_con = ibis.connect(db_path)
            print("ibis.connect(path) SUCCESS")
            
            # Get underlying connection
            con = ibis_con.con
            print(f"Got underlying connection: {con}")
            
            # 1. Create sequence
            con.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 100")
            con.commit()
            
            # 2. Get sequence state
            row = con.execute("SELECT * FROM duckdb_sequences() WHERE sequence_name = 'test_seq'").fetchone()
            print(f"Sequence state: {row}")
            
            # 3. Create table
            con.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value VARCHAR)")
            
            # 4. Set default
            con.execute("ALTER TABLE test_table ALTER COLUMN id SET DEFAULT nextval('test_seq')")
            con.commit()
            
            # 5. Next value
            cursor = con.execute("SELECT nextval('test_seq')")
            val = cursor.fetchone()[0]
            print(f"Next value: {val}")
            con.commit()
            
        except Exception as e:
            print(f"ibis shared connection FAILED: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # ibis backend might need closing?
            pass
            
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    test_ibis_connect_shared()
