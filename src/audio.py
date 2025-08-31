import pyaudio
import numpy as np
import time
from src.config import SAMPLE_RATE, CHUNK_SIZE, CHANNELS, SILENCE_DURATION, VAD_THRESHOLD
from src.timing import timer

class AudioInterface:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def start_recording(self):
        """opens the microphone stream"""
        if self.stream:
            self.stop_recording()
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
    
    def stop_recording(self):
        """closes the microphone stream"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            finally:
                self.stream = None
    
    @timer.measure("recording")
    def record_until_silence(self, max_seconds=5):
        """
        records audio until the user stops speaking or for up to 5 seconds (whichever comes first)
        sends captured audio to Whisper
        """
        self.start_recording()
        frames = []
        num_cons_schunks = 0
        num_schunks_to_end_rec = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        max_chunks = int(max_seconds * SAMPLE_RATE / CHUNK_SIZE)
        any_speech_detected = False
        for i in range(max_chunks):
            try:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                # Check volume for VAD
                audio_chunk = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_chunk).mean()
                # Check if we ever detect speech
                if volume >= VAD_THRESHOLD * 1000:
                    any_speech_detected = True
                    num_cons_schunks = 0
                else:
                    num_cons_schunks += 1
                    if any_speech_detected and num_cons_schunks == num_schunks_to_end_rec:
                        print("Silence detected, ending recording")
                        break
            except Exception as e:
                print(f"Recording error: {e}")
                break  
        self.stop_recording()
        # Whisper requires a tensor of 32-bit fp numbers
        if not any_speech_detected:
            print("No speech detected - returning silence")
            return np.zeros(1600, dtype=np.float32)
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        return audio_data.astype(np.float32) / 32768.0
    
    def shutdown(self):
        self.stop_recording()
        self.audio.terminate()

# Test code
if __name__ == "__main__":
    audio = AudioInterface()
    try:
        print("Say something (stops on silence):")
        audio_data = audio.record_until_silence()
        print(f"Recorded {len(audio_data)/SAMPLE_RATE:.1f} seconds")
        timer.report()
    finally:
        audio.shutdown()