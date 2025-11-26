
from google.genai import errors as genai_errors
from google.api_core import exceptions as core_exceptions

def check_inheritance():
    server_error = genai_errors.ServerError
    internal_error = core_exceptions.InternalServerError
    
    print(f"genai.ServerError: {server_error}")
    print(f"api_core.InternalServerError: {internal_error}")
    
    is_subclass = issubclass(server_error, internal_error)
    print(f"Is genai.ServerError a subclass of api_core.InternalServerError? {is_subclass}")

    try:
        # Simulate raising the error
        raise genai_errors.ServerError(500, "Internal Error", None)
    except core_exceptions.InternalServerError:
        print("Caught as api_core.InternalServerError")
    except Exception as e:
        print(f"Caught as {type(e)}")

if __name__ == "__main__":
    check_inheritance()
