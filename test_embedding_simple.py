import os
import sys
import time

from google import genai

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    sys.exit(1)


client = genai.Client(api_key=api_key)

start = time.time()
try:
    result = client.models.embed_content(model="text-embedding-004", contents="Hello world")
except Exception:
    pass
finally:
    pass
