
from google.genai import errors as genai_errors

def list_exceptions():
    print("Available exceptions in google.genai.errors:")
    for name in dir(genai_errors):
        if not name.startswith("_"):
            obj = getattr(genai_errors, name)
            if isinstance(obj, type) and issubclass(obj, Exception):
                print(f"- {name}")

if __name__ == "__main__":
    list_exceptions()
