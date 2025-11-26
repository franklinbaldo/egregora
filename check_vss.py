
import duckdb

def check_vss():
    conn = duckdb.connect(":memory:")
    
    try:
        conn.execute("INSTALL vss; LOAD vss;")
        print("VSS extension loaded.")
    except Exception as e:
        print(f"Failed to load VSS: {e}")
        return

    print("\nAvailable VSS functions:")
    result = conn.execute("SELECT function_name FROM duckdb_functions() WHERE function_name LIKE 'vss_%'").fetchall()
    for row in result:
        print(f"- {row[0]}")

    print("\nTesting vss_match...")
    try:
        # Create dummy table
        conn.execute("CREATE TABLE items (id INT, embedding FLOAT[3])")
        conn.execute("INSERT INTO items VALUES (1, [1.0, 0.0, 0.0]), (2, [0.0, 1.0, 0.0])")
        
        # Try vss_match (if it exists)
        try:
            conn.execute("SELECT * FROM vss_match('items', 'embedding', [1.0, 0.0, 0.0]::FLOAT[3], 1)")
            print("vss_match executed successfully.")
        except Exception as e:
            print(f"vss_match failed: {e}")

    except Exception as e:
        print(f"Setup failed: {e}")

if __name__ == "__main__":
    check_vss()
