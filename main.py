from src.pipeline import Jarvis
from src.timing import timer
import argparse

def main():
    "this is the main entry point for running Jarvis"
    print("""Jarvis, the Berry Smart Assistant :D""")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--wake-word', 
        action='store_true',
        help='Enable wake word detection mode (say "Hey Jarvis" to activate)'
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        default=True,
        help='Run in continuous conversation mode (default)'
    )
    args = parser.parse_args()

    assistant = Jarvis()
    with timer.section("startup"):
        assistant.initialize()
    timer.report()
    if args.wake_word:
        assistant.run_with_wake_word()
    else:
        assistant.run_conversation_loop()
    print(f"Startup took {timer.measurements['startup']:.0f}ms")
    try:
        assistant.run_conversation_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nFatal error: {e}")
    finally:
        assistant.shutdown()
        print("Shutdown complete")

if __name__ == "__main__":
    main()
