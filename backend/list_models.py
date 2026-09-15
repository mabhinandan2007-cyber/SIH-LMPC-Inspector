from google import genai
import os

client = genai.Client()
for m in client.models.list():
    if 'gemini' in m.name:
        print(m.name)
