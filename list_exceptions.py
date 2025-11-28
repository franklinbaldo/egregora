from google.genai import errors as genai_errors


def list_exceptions() -> None:
    for name in dir(genai_errors):
        if not name.startswith("_"):
            obj = getattr(genai_errors, name)
            if isinstance(obj, type) and issubclass(obj, Exception):
                pass


if __name__ == "__main__":
    list_exceptions()
