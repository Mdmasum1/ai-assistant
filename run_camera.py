#!/usr/bin/env python3
"""
AI Voice Assistant - Camera Mode Launcher
Launches the AI assistant in camera capture mode
"""

import subprocess
import sys
import os

def main():
    print("📷 Launching AI Voice Assistant - Camera Mode")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("assistant_camera.py"):
        print("❌ Error: assistant_camera.py not found!")
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
        # Launch the camera assistant
        subprocess.run([sys.executable, "assistant_camera.py"], check=True)
    except KeyboardInterrupt:
        print("\n🔌 Camera mode stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running camera mode: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

