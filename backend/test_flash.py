import os
from google import genai
from google.genai import types
import cv2

client = genai.Client()
img = cv2.imread(r'..\storage\7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg')
_, buffer = cv2.imencode('.jpg', img)

try:
    res = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[types.Part.from_bytes(data=buffer.tobytes(), mime_type='image/jpeg'), "What is the price on this packet?"]
    )
    print("FLASH RESPONSE:", res.text)
except Exception as e:
    print("FLASH ERROR:", e)
