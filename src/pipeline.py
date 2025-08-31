import threading
import time
import numpy as np
from src.models import Models
from src.audio import AudioInterface
from src.timing import timer
from src.context import ContextManager
from src.functions import Functions
from src.config import INTERRUPT_POLL_INTERVAL, CHUNK_SIZE, VAD_THRESHOLD

class Jarvis:
    def __init__(self, chunk_size=CHUNK_SIZE, vad_threshold=VAD_THRESHOLD):
        self.models = Models()
        self.audio = AudioInterface()
        self.context = ContextManager()
        self.functions = Functions(self.models)
        self.chunk_size = chunk_size
        self.vad_threshold = vad_threshold
        self.wake_mode = False
        self.wake_detector = None
        self.conversation_active = False
        
        # using threading.Event objects to prevent race conditions
        self.speaking_event = threading.Event() # flag for if TTS is playing
        self.interrupt_event = threading.Event() # flag for if interrupt is detected
        self.shutdown_event = threading.Event() # flag for shutdown
        
    def initialize(self):
        self.models.load()
    
    def detect_interrupt(self):
        """used to monitor interrupts while speaking"""
        # sample baseline noise based on TTS playback + background noise
        baseline_samples = []
        for i in range(3):
            try: 
                if not self.audio.stream:
                    print("Audio stream not open")
                    break
                data = self.audio.stream.read(self.chunk_size, exception_on_overflow=False)
                volume = np.abs(np.frombuffer(data, dtype=np.int16)).mean()
                baseline_samples.append(volume)
                time.sleep(0.05)
            except OSError as e:
                print(f"Audio read error during baseline sampling: {e}")
            except Exception as e:
                print(f"Unexpected error during baseline sampling: {e}")

        if baseline_samples:
            baseline = np.mean(baseline_samples)
            threshold = max(baseline * 2.5, self.vad_threshold * 1000)
        else:
            threshold = self.vad_threshold * 1000
        
        # monitor for interrupts above threshold
        while self.speaking_event.is_set() and not self.shutdown_event.is_set():
            try:
                if not self.audio.stream:
                    print("Audio stream not open")
                    break
                data = self.audio.stream.read(self.chunk_size, exception_on_overflow=False)
                volume = np.abs(np.frombuffer(data, dtype=np.int16)).mean()
                if volume > threshold:
                    print(f"\n**INTERRUPT OCCURRED {volume:.0f} > {threshold:.0f}**")
                    self.interrupt_event.set()
                    self.models.stop_speaking()
                    return True
            except OSError as e:
                print(f"Audio read error in interrupt: {e}")
                break
            except Exception as e:
                print(f"Unexpected error in interrupt: {e}")
                break          
            time.sleep(INTERRUPT_POLL_INTERVAL)
        return False

    def speak_with_interrupts(self, text):
        """run both TTS and interrupt monitoring in parallel"""
        if not text:
            return
    
        # main speaking portion
        self.speaking_event.set() 
        self.interrupt_event.clear()
        self.audio.start_recording()

        interrupt_thread = threading.Thread(target=self.detect_interrupt, daemon=True)
        interrupt_thread.start()

        self.models.speak(text, wait = False) # run TTS in the background
        while self.models.is_speaking():
            if self.interrupt_event.is_set():
                self.models.stop_speaking()
                break
            time.sleep(0.02) # check every 20ms

        self.speaking_event.clear()

        # wait for interrupt thread to finish
        interrupt_thread.join(timeout=0.5) 
        if interrupt_thread.is_alive():
            self.shutdown_event.set()
            interrupt_thread.join(timeout=0.1)
        self.audio.stop_recording()
  
    
    def run_conversation_loop(self):
        """the full conversation loop"""
        print("\n**JARVIS STARTED**")
        while not self.shutdown_event.is_set():
            try:
                print("\nListening...")
                audio_data = self.audio.record_until_silence()
                with timer.section("transcription"):
                    prompt = self.models.transcribe(audio_data)
                    print(f"\nYou: {prompt}")
                    if not prompt:
                        print("No speech detected, not running SLM and Piper")
                        continue
                    if "shut down" in prompt.lower():
                        print('Shutting down. Goodbye.')
                        break
                with timer.section("full_response"):
                    self.stream_and_speak(prompt)
                timer.report()
            except Exception as e:
                print(f"pipeline error: {e}")
                continue
        self.shutdown()
    
    def stream_and_speak(self, prompt):
        "stream tokens from the SLM and speak it in sentence-wise chunks"
        is_function, response = self.functions.parse(prompt)
        if is_function:
            print(f"Assistant: {response}")
            self.speak_with_interrupts(response)
            return
        print("Assistant: ", end="")
        buffer = []
        full_response = []
        word_count = 0
        sentence_pauses = {'.', '!', '?', ';'}
        prompt_w_context = self.context.build_prompt(prompt)

        with timer.section("slm_stream"):
            for token in self.models.generate_stream(prompt_w_context):
                print(token, end="", flush=True) # continuously print tokens on the same line
                buffer.append(token)
                full_response.append(token)
                curr_response = ''.join(buffer)
                words = curr_response.split()
                should_speak = False
                if curr_response.rstrip() and curr_response.rstrip()[-1] in sentence_pauses: 
                    should_speak = True
                elif len(words) - word_count > 10:
                    should_speak = True
                if should_speak and len(curr_response.strip()) > 0:
                    self.speak_with_interrupts(curr_response.strip())
                    buffer = []
                    word_count += len(words)
                    if self.interrupt_event.is_set():
                        print("Stopped SLM generation due to interrupt")
                        break
        full_response = ''.join(full_response)
        self.context.add_interaction(prompt, full_response)

        if not self.interrupt_event.is_set():
            # speak any remaining words
            remaining_words = ''.join(buffer).strip()
            if remaining_words:
                self.speak_with_interrupts(remaining_words)
    
    def single_conversation(self):
        """ 
        run a single conversation cycle (for wake word mode)
        returns True if should continue listening, False if user said 'shutdown'
        """
        self.conversation_active = True

        try:
            with timer.section("recording"):
                print("\nListening...")
                audio_data = self.audio.record_until_silence()   
            with timer.section("transcription"):
                prompt = self.models.transcribe(audio_data)
                print(f"You: {prompt}")
            if not prompt:
                print("No speech detected, not running SLM and Piper")
                self.conversation_active = False
                return True
            if "shut down" in prompt.lower():
                print('Shutting down. Goodbye.')
                self.shutdown_event.set()
                return False
            with timer.section("response"):
                self.stream_and_speak(prompt)
            timer.report()
        except Exception as e:
            print(f"Error in conversation: {e}")
        finally:
            self.conversation_active = False   
        return True  

    def run_with_wake_word(self):
        """Run Jarvis with wake word detection"""
        from src.wake import WakeWordDetector
        print("**JARVIS STARTED (WAKE WORD MODE)**")
        self.wake_mode = True
        try:
            self.wake_detector = WakeWordDetector(audio_interface=self.audio)
            # start listening with single_conversation as callback
            self.wake_detector.start_listening(callback=self.single_conversation)
            while not self.shutdown_event.is_set():
                time.sleep(0.5)
        except Exception as e:
            print(f"Error in wake word mode: {e}")
        finally:
            if self.wake_detector:
                self.wake_detector.stop_listening()
            self.shutdown()


        
    def shutdown(self):
        self.shutdown_event.set()
        self.functions.shutdown()
        if self.wake_detector:
            self.wake_detector.stop_listening()
            self.wake_detector = None
        # give threads time to notice shutdown event
        time.sleep(0.1)  
        self.audio.shutdown()
    