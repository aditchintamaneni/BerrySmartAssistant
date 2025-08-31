import threading
import time
import numpy as np
import pyaudio
import platform
import os
import openwakeword.utils as oww_utils
import openwakeword.model as oww_model
from src.config import (
    WAKE_WORD, WAKE_SENSITIVITY, WAKE_COOLDOWN, 
    SAMPLE_RATE, CHUNK_SIZE, SPEECH_PAUSE_DELAY, 
    MONITOR_CHECK_INTERVAL, THREAD_JOIN_TIMEOUT
)

class WakeWordDetector:
    def __init__(self, audio_interface,wake_word=WAKE_WORD, sensitivity=WAKE_SENSITIVITY):
        """Initialize OpenWakeWord detector"""
        self.wake_word = wake_word
        self.sensitivity = sensitivity  
        self.model = None
        self.pa = None
        self.audio_stream = None
        self.listening = False
        self.thread = None
        self.callback = None
        self.last_detection = 0
        self.shared_audio = audio_interface  # shared PyAudio
        try:
            print(f"Loading OpenWakeWord model: {wake_word}")
            oww_utils.download_models(model_names=[WAKE_WORD])
            self.model = oww_model.Model(
                wakeword_models=[WAKE_WORD],  
            )
            self.pa = self.shared_audio.audio
            self.model_name = list(self.model.models.keys())[0]
        except Exception as e:
            print(f"Failed to initialize wake word detector: {e}")
            raise

    def start_listening(self, callback):
        """start listening for wake word in background thread"""
        if self.listening:
            return
        self.callback = callback
        self.listening = True
        # stop any recording on the shared audio stream
        if self.shared_audio and hasattr(self.shared_audio, 'stream') and self.shared_audio.stream:
            self.shared_audio.stop_recording()
            time.sleep(0.1)
        self.open_stream()
        self.thread = threading.Thread(target=self.listening_loop, daemon=True)
        self.thread.start()
        print(f"Listening for wake word: '{self.wake_word}'...")
        print(f"Sensitivity: {self.sensitivity} (lower = more sensitive)")
    
    def listening_loop(self):
        """the main listening loop (runs in background thread)"""        
        while self.listening:
            try:
                if not self.audio_stream:
                    print("No audio stream, exiting listening loop")
                    break
                audio_data = self.audio_stream.read(CHUNK_SIZE)
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                prediction = self.model.predict(audio_np)
                if prediction:
                    score = prediction.get(self.model_name, 0)
                    if score > self.sensitivity:
                        current_time = time.time()
                        if current_time - self.last_detection > WAKE_COOLDOWN:
                            self.last_detection = current_time
                            print(f"**WAKE WORD DETECTED** ({self.wake_word}: {score:.2f})")
                            self.model.reset()
                            self.close_stream()
                            time.sleep(0.05)
                            try:
                                should_continue = self.callback()
                                if not should_continue:
                                    self.listening = False
                                    break
                            except Exception as e:
                                print(f"Error in single_conversation: {e}")
                            if self.listening:
                                time.sleep(0.1)
                                self.open_stream()
                                print(f"Listening for wake word: '{self.wake_word}'...")
            except Exception as e:
                if self.listening:
                    print(f"Error in listening loop: {e}")
                    break
    
    def open_stream(self):
        """open the audio stream"""
        if self.audio_stream:
            self.close_stream()
        try:
            self.audio_stream = self.pa.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE,  
                input_device_index=None  
            )
            print(f"Audio stream opened")
        except Exception as e:
            print(f"Failed to open audio stream: {e}")
            raise
    
    def close_stream(self):
        """close audio stream cleanly"""
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception as e:
                print(f"Failed to close audio stream: {e}")
            self.audio_stream = None
    
    def stop_listening(self):
        """stop listening and cleanup"""
        self.listening = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.close_stream()
        self.model = None
  