import platform

# Model settings
OLLAMA_MODEL = "gemma3:1b"
WHISPER_MODEL = "tiny.en"
WHISPER_DEVICE = "cpu"

# Wake word settings
WAKE_WORD = "hey_jarvis"  
WAKE_SENSITIVITY = 0.4 # lower = more sensitive
WAKE_COOLDOWN = 2.0 # cooldown period after wake word detection (seconds)

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280 # this is sample rate (16,000 samples per sec) x time window (80 ms)
CHANNELS = 1
RECORD_SECONDS = 5  # max recording time

# Mic settings
VAD_THRESHOLD = 0.5  
SILENCE_DURATION = 2  # seconds of silence needed to stop recording
INTERRUPT_POLL_INTERVAL = 0.05  # 50ms

# Timing delays (seconds)
SPEECH_PAUSE_DELAY = 0.1  # pause after stopping speech before new announcement
MONITOR_CHECK_INTERVAL = 1.0  # how often to check for expired timers
THREAD_JOIN_TIMEOUT = 2.0  # timeout for thread cleanup

# Functions settings
FUNCTION_CHECK_INTERVAL = 1.0
MAX_TIMER_DURATION = 3600
MAX_ALARMS = 5

# Paths
PIPER_VOICE_PATH = "/home/pi/voices/en_US-amy-low.onnx"

# TTS settings
TTS_RATE = 200  # Words per minute
TTS_VOLUME = 0.9
