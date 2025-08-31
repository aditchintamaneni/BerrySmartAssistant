from faster_whisper import WhisperModel
import os
import subprocess
import requests
import json
import numpy as np
from src.timing import timer
from src.config import WHISPER_MODEL, OLLAMA_MODEL
import threading
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

class Models:
    def __init__(self):
        self.whisper = None
        self.ollama_url = "http://localhost:11434/api/generate" 
        self.speak_lock = threading.Lock()
        pygame.mixer.init(frequency=16000, size=-16, channels=1, buffer=512)
        
    def load(self):
        """load models into memory (just faster-whisper now)"""
        with timer.section("model_load"):
            self.whisper = WhisperModel(
                WHISPER_MODEL, 
                device="cpu",  
                compute_type="int8",
                cpu_threads=2  
            )
    
    @timer.measure("STT")
    def transcribe(self, audio_data):
        """use whisper for STT"""
        if self.whisper is None:
            self.load()
        segments, info = self.whisper.transcribe(
            audio_data, 
            beam_size=1,           
            best_of=1,             
            temperature=0.0,      
            condition_on_previous_text=False  
        )
        text = ""
        for segment in segments:
            text += segment.text
            
        return text.strip()
    
    @timer.measure("slm")  
    def generate(self, prompt):
        """generate full SLM response (no streaming)"""
        try:
            data = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False, 
                "options": {
                    "num_predict": 100,
                    "temperature": 0.7
                }
            }
            response = requests.post(self.ollama_url, json=data, timeout=30)
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            print(f"LLM generation error: {e}")
            return "Sorry, I had trouble processing that."

    def generate_stream(self, prompt):
        """stream tokens as SLM generates"""
        try:
            data = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": 100,
                    "temperature": 0.7
                }
            }
            with requests.post(self.ollama_url, json=data, stream=True, timeout=30) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk and not chunk.get('done'):
                                yield chunk['response']
                        except json.JSONDecodeError:
                            continue    
        except Exception as e:
            print(f"Streaming generation error: {e}")
            yield "Sorry, I had trouble processing that."

    @timer.measure("TTS")
    def speak(self, text, wait=True):
        """use Piper for TTS"""
        if not text:
            return
        with self.speak_lock:
            try:
                pygame.mixer.music.stop()
                process = subprocess.Popen(
                    ['piper', '--model', 'voices/en_US-amy-low.onnx', '--output-raw'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                audio_data, _ = process.communicate(input=text.encode())
                
                # Convert raw audio to pygame format
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                sound = pygame.sndarray.make_sound(audio_array)
                
                channel = sound.play()
                
                if wait and channel:
                    while channel.get_busy():
                        pygame.time.wait(10)     
            except Exception as e:
                print(f"TTS error: {e}")
    
    def stop_speaking(self):
        """stops speech immediately"""
        with self.speak_lock:
            pygame.mixer.stop()
    
    def is_speaking(self):
        """checks if currently speaking"""
        return pygame.mixer.get_busy()

# testing
if __name__ == "__main__":
    models = Models()
    models.load()
    models.speak("Hello, testing Piper Text-to-Speech")
    response = models.generate("Say 'Hello, this is Piper Text-to-Speech' and nothing else")
    print(f"SLM said: {response}")
    timer.report()