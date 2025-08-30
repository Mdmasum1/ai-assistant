#!/usr/bin/env python3
"""
AI Voice Assistant - Desktop Mode Launcher
Launches the AI assistant in desktop screen capture mode
"""

import subprocess
import sys
import os

def main():
    print("🖥️ Launching AI Voice Assistant - Desktop Mode")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("assistant_desktop.py"):
        print("❌ Error: assistant_desktop.py not found!")
        print("Please run this script from the ai-voice-assistant directory.")
        sys.exit(1)
    
    # Check if .env file exists
    if not os.path.exists(".env"):
        print("⚠️  Warning: .env file not found!")
        print("Please create a .env file with your API keys:")
        print("OPENAI_API_KEY=your_key_here")
        print("GOOGLE_API_KEY=your_key_here")
        print()
    
    try:
        # Launch the desktop assistant
        subprocess.run([sys.executable, "assistant_desktop.py"], check=True)
    except KeyboardInterrupt:
        print("\n🔌 Desktop mode stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running desktop mode: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

