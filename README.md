# Jarvis, the Berry Smart Assistant!

A high-performance voice AI assistant optimized for edge deployment on a Raspberry Pi 5 (4GB RAM). Achieves <2.5 second response latency through carefully engineered architecture. All interactions are processed fully on-device. 

## Features

### Core Capabilities
- **Wake Word Detection**: "Hey Jarvis" detection using OpenWakeWord.
- **Context-Aware Conversation**: Jarvis maintains up to 3 conversation turns per interaction.
- **Timers and Alarms**: Jarvis supports natural language input for setting timers and alarms. A background thread monitors and announces time-based events.
- **Interrupt Handling**: Real-time audio monitoring during Text-to-Speech (TTS) playback enables users to interrupt Jarvis mid-response.

## Key Technical Achievements
- **Streaming Responses**: SLM tokens are processed into complete sentences and spoken incrementally, significantly reducing perceived latency.
- **Multithreaded Architecture**: Thread-safe concurrent execution of main pipeline, wake word detection, timer monitoring, and interrupt detection.
- **Adaptive Interrupt Detection**: Dynamic threshold calculation based on ambient noise sampling during TTS playback. Suitable for varying acoustic environments. 
- **Robust NLP for Timers/Alarms**: Complex expressions (eg "1 hour and 30 minutes") and faster-whisper transcription inconsistencies are parsed and accounted for through regex.

## Performance Monitoring

Wrote a custom Timer class for granular performance profiling of each pipeline stage, enabling iterative performance analysis and optimization.

## Technical Stack
- **Speech-to-Text (STT)**: faster-whisper (optimized settings for Pi)
- **Small Language Model (SLM)**: Gemma3:1B (quantized)
- **Text-to-Speech (TTS)**: Piper TTS
- **Audio Processing**: PyAudio (16kHz mono capture)
- **Concurrency**: Python threading using Events and Locks for synchronization