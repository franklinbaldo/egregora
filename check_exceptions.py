from google.api_core import exceptions as core_exceptions
from google.genai import errors as genai_errors


def check_inheritance() -> None:
    server_error = genai_errors.ServerError
    internal_error = core_exceptions.InternalServerError

    issubclass(server_error, internal_error)

    try:
        # Simulate raising the error
        raise genai_errors.ServerError(500, "Internal Error", None)
    except core_exceptions.InternalServerError:
        pass
    except Exception:
        pass


if __name__ == "__main__":
    check_inheritance()
