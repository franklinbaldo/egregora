
import ibis.expr.datatypes as dt
from egregora.database.ir_schema import _ibis_to_duckdb_type

def test_array_conversion():
    array_float = dt.Array(dt.float64)
    array_string = dt.Array(dt.string)
    
    print(f"Ibis type: {array_float}")
    print(f"Converted SQL: {_ibis_to_duckdb_type(array_float)}")
    
    print(f"Ibis type: {array_string}")
    print(f"Converted SQL: {_ibis_to_duckdb_type(array_string)}")

if __name__ == "__main__":
    test_array_conversion()
