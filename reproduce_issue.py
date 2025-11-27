
import ibis.expr.datatypes as dt


def test_array_conversion() -> None:
    dt.Array(dt.float64)
    dt.Array(dt.string)



if __name__ == "__main__":
    test_array_conversion()
