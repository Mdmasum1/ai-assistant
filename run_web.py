#!/usr/bin/env python3
"""
AI Voice Assistant - Web Mode Launcher
Production-ready for GitHub → Render → Gumroad deployment
"""

import subprocess
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Get port from environment (Render sets this automatically)
    port = int(os.environ.get("PORT", 5000))

    # Determine if we're in production
    is_production = os.environ.get("FLASK_ENV") == "production"

    print("🌐 Launching AI Voice Assistant - Web Mode")
    print("=" * 50)
    print(f"📍 Environment: {'Production (Render)' if is_production else 'Development'}")
    print(f"🌐 Port: {port}")

    if is_production:
        print("🔗 Gumroad integration: ENABLED")
        print("💳 Payment processing: Ready")
        print("📊 Analytics tracking: Active")
        print("🚀 Production deployment: LIVE")

    # Check if we're in the right directory
    if not os.path.exists("src/main.py"):
        print("❌ Error: src/main.py not found!")
        print("Please run this script from the ai-voice-assistant directory.")
        sys.exit(1)

    # Check environment variables for production
    if is_production:
        required_vars = ["OPENAI_API_KEY", "SECRET_KEY"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]

        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set these in your Render dashboard.")
            sys.exit(1)
        else:
            print("✅ All required environment variables are set")
    else:
        # Development mode - check .env file
        if not os.path.exists(".env"):
            print("⚠️  Warning: .env file not found!")
            print("Please create a .env file with your API keys:")
            print("OPENAI_API_KEY=your_key_here")
            print()

    if not is_production:
        print("🚀 Starting Flask web server...")
        print(f"📱 Landing page: http://localhost:{port}")
        print(f"🤖 Demo: http://localhost:{port}#demo")
        print("Press Ctrl+C to stop the server")
    else:
        print("🚀 Starting production Flask server...")
        print("🌍 Public URL will be provided by Render")

    print()

    try:
        # Set environment variables for the subprocess
        env = os.environ.copy()
        env["PORT"] = str(port)

        # Launch the Flask web application
        subprocess.run([sys.executable, "src/main.py"], check=True, env=env)
    except KeyboardInterrupt:
        print("\n🔌 Web server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running web server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

