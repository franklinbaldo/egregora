
import duckdb
import ibis
import ibis.expr.datatypes as dt
from egregora.database.ir_schema import RAG_CHUNKS_SCHEMA, _ibis_to_duckdb_type, quote_identifier

def test_create_full_table():
    conn = duckdb.connect(":memory:")
    
    table_name = "rag_chunks"
    schema = RAG_CHUNKS_SCHEMA
    
    column_defs = []
    for name, dtype in schema.items():
        sql_type = _ibis_to_duckdb_type(dtype)
        column_defs.append(f"{quote_identifier(name)} {sql_type}")

    columns_sql = ", ".join(column_defs)
    create_sql = f"CREATE TABLE IF NOT EXISTS {quote_identifier(table_name)} ({columns_sql})"
    
    print(f"Executing SQL: {create_sql}")
    
    try:
        conn.execute(create_sql)
        print("Success.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_create_full_table()
