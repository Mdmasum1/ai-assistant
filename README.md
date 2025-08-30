# AI Voice Assistant - Desktop & Camera Copilot

An intelligent AI voice assistant that can see your desktop, capture camera feed, listen to your voice, and provide context-aware assistance. This revolutionary tool transforms your workspace into an intelligent environment by combining real-time screen capture, camera capture, and advanced AI capabilities.

## Features

- **Screen-Aware Intelligence**: Sees and understands everything on your desktop in real-time
- **Camera Vision**: Analyzes your camera feed for visual context and assistance
- **Natural Voice Interaction**: Advanced speech recognition with human-like conversation
- **Context-Aware Responses**: Powered by GPT-4o for intelligent, contextual assistance
- **Dual Mode Operation**: Choose between desktop screen capture or camera capture
- **Real-Time Processing**: Instant responses with no delays
- **Privacy First**: All processing happens locally on your machine
- **Easy Setup**: Install and start using in minutes
- **Web Demo**: Interactive landing page with demo functionality

## System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux Ubuntu 18.04+
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: 2GB free space
- **Hardware**: Microphone, speakers/headphones, camera (for camera mode)
- **Internet**: Required for AI processing

## Installation

### Prerequisites

You need an `OPENAI_API_KEY` and a `GOOGLE_API_KEY` to run this code. Store them in a `.env` file in the root directory of the project, or set them as environment variables.

### For Apple Silicon (macOS)

If you are running the code on Apple Silicon, run the following command:

```bash
brew install portaudio
```

### Setup Instructions

1.  **Clone or download the project**
2.  **Install Python:** If you don't have Python installed, download the latest version from the official Python website (python.org) and make sure to check the option "Add Python to PATH" during installation.
3.  **Install Git:** Download and install Git for Windows from git-scm.com/download/win.
4.  **Install System Dependencies (for desktop AI assistant):**
    *   **PortAudio:** Required for `pyaudio`. On macOS, use `brew install portaudio`. On Linux (Ubuntu), use `sudo apt-get install portaudio19-dev`. On Windows, you might need to install pre-compiled wheels or use `pipwin` (see step 5 for details).
    *   **FFmpeg:** Required for `openai-whisper`. On macOS, use `brew install ffmpeg`. On Linux (Ubuntu), use `sudo apt-get install ffmpeg`. On Windows, download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

5.  **Create a virtual environment and install dependencies**:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Linux/macOS)
source .venv/bin/activate

# Activate virtual environment (Windows Command Prompt)
.venv\Scripts\activate.bat

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Update pip and install requirements
pip install -U pip
pip install -r requirements.txt
```

    *Note for Windows users regarding `pyaudio` and `soundfile`: If `pip install pyaudio` or `pip install soundfile` fails, you might need to install pre-compiled wheels. Visit [Unofficial Windows Binaries for Python Extension Packages](https://www.lfd.uci.edu/~gohlke/pythonlibs/) and download the appropriate `.whl` files for `PyAudio` and `SoundFile` for your Python version. Then install them manually using `pip install path\to\your\PyAudio-*.whl` and `pip install path\to\your\SoundFile-*.whl`.*

6.  **Create environment file**:
Create a `.env` file in the root directory with your API keys:

```
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
```

7.  **Run the assistant**:

```bash
python assistant.py
```

## How It Works

This AI Assistant combines several advanced technologies:

1. **Desktop Recording**: Captures your screen in real-time using PIL and OpenCV
2. **Voice Recognition**: Uses OpenAI Whisper for accurate speech-to-text conversion
3. **AI Processing**: Leverages GPT-4o to understand both visual and audio context
4. **Text-to-Speech**: Converts AI responses back to natural speech
5. **Continuous Monitoring**: Runs in the background, always ready to help

## Usage

### Unified Multi-Mode Assistant (Recommended)
1. **Start the application**: Run `python assistant.py` in your VSCode terminal
2. **Select initial mode**: Choose from Desktop (1), Camera (2), or Both (3)
3. **Grant permissions**: Allow appropriate access (screen/camera and microphone)
4. **Begin interaction**: Start speaking for AI assistance
5. **Automatic detection** (Both mode): System automatically detects and switches between desktop/camera
6. **Monitor status**: Press 's' to see current system status
7. **Exit**: Press 'q', ESC, or Ctrl+C to quit

### Automatic Mode Detection (Option 3 - Both)
When you select "Both" mode, the system provides intelligent automatic switching:

- **Camera Priority**: When both sources are available, camera mode is prioritized (more interactive)
- **Automatic Fallback**: Seamlessly switches to desktop when camera becomes unavailable
- **Dynamic Detection**: Switches to camera when desktop becomes unavailable
- **Real-time Feedback**: Console shows which mode is automatically detected
- **No Manual Intervention**: System handles everything automatically

**Example Console Output:**
```
🔄 Auto-detected: Using camera mode (both sources available)
🔄 Auto-detected: Using desktop mode (camera unavailable)
🔄 Auto-detected: Using camera mode (desktop unavailable)
```

### Individual Mode Launchers (Alternative)
- **Desktop Mode**: Run `python assistant_desktop.py` or `python run_desktop.py`
- **Camera Mode**: Run `python assistant_camera.py` or `python run_camera.py`
- **Web Demo**: Run `python run_web.py` for landing page and demo

### Runtime Controls (Unified Assistant)
- **Voice Commands**: Speak naturally for AI assistance
- **Automatic Mode Detection**: System intelligently switches between desktop/camera in "Both" mode
- **'s' key**: Display current system status and auto-detection information
- **'q' key or ESC**: Quit application
- **Ctrl+C**: Graceful shutdown

## Troubleshooting

### Both Mode (Option 3) Issues
If "Both" mode is not working properly, especially for the camera:

**Note**: The latest version includes resource conflict fixes that should resolve most "Both" mode issues. The system now:
- Starts desktop recorder first and allows it to stabilize
- Adds proper delays before camera initialization
- Implements retry logic with up to 3 attempts for camera in "Both" mode
- Optimizes camera settings to reduce resource usage

1.  **Check Status (`s` key)**: Press `s` (and then Enter) in the terminal to get a detailed status report. Look at the "Camera Recorder" section:
    *   `Camera Recorder: ✅ Active` and `Can capture frames: ✅ Yes`: This is ideal.
    *   `Camera device: ✅ Connected`: Indicates the camera is recognized by OpenCV.
    *   If you see `❌ Inactive`, `❌ No` for frame capture, or `❌ Disconnected` for the device, this indicates a problem.

2.  **Observe Initialization Output**: When you start `assistant.py` and select option 3, you should now see:
    *   `⏳ Waiting for desktop recorder to stabilize before starting camera...`
    *   Multiple camera initialization attempts if needed
    *   `✅ Camera recorder started successfully` when working properly

3.  **Camera Permissions**: Ensure your operating system (Windows, macOS, Linux) has granted VSCode, your terminal, or Python itself permission to access the camera. This is a very common cause.

4.  **Camera in Use**: Close all other applications that might be accessing the camera (e.g., Zoom, Teams, OBS, browser tabs, etc.). Only one application can typically use the camera at a time.

5.  **Driver Issues**: Ensure your camera drivers are up to date.

6.  **Multiple Cameras**: If you have multiple cameras, the code tries indices 0-4. It might be picking the wrong one or one that is not fully functional.

7.  **Virtual Cameras**: If you have virtual camera software installed, it might interfere.

8.  **Hardware Malfunction**: The camera itself might have an issue.

## Use Cases

### Desktop Mode
- **Developers**: Code review assistance, debugging help, documentation lookup
- **Designers**: Design feedback, color palette suggestions, layout advice
- **Content Creators**: Real-time editing assistance, content optimization
- **Professionals**: Meeting notes, document analysis, task automation
- **Students**: Research assistance, learning support, note-taking help

### Camera Mode
- **Video Calls**: Real-time assistance during meetings and presentations
- **Learning**: Visual learning support, object recognition, reading assistance
- **Accessibility**: Visual assistance for users with visual impairments
- **Security**: Monitoring and analysis of physical environments
- **Creative Work**: Art critique, composition suggestions, color analysis

## Privacy & Security

- All screen capture processing happens locally on your machine
- Only anonymized queries are sent to AI services
- No personal data or screen content is stored on external servers
- Your privacy is our top priority

## Troubleshooting

### Common Issues

1. **Microphone not working**: Check system permissions and microphone settings
2. **Screen capture fails**: Ensure screen recording permissions are granted
3. **API errors**: Verify your API keys are correctly set in the `.env` file
4. **Performance issues**: Close unnecessary applications to free up system resources

### Getting Help

- Check the FAQ section on our website
- Contact support via email
- Join our Discord community
- Report bugs on GitHub

## License

This project is available under multiple license options:

- **Basic License** ($29): Personal use, core features
- **Professional License** ($59): Commercial use, all features, lifetime updates
- **Developer License** ($99): Multi-user, source code access, redistribution rights

## Contributing

We welcome contributions! Please read our contributing guidelines and submit pull requests for any improvements.

## Changelog

### Version 1.0.0
- Initial release
- Core AI voice assistant functionality
- Real-time screen capture and analysis
- GPT-4o integration
- Cross-platform support

## Support

For technical support, feature requests, or general questions:

- Email: support@aivoiceassistant.com
- Documentation: [docs.aivoiceassistant.com](https://docs.aivoiceassistant.com)
- Discord: [Join our community](https://discord.gg/aivoiceassistant)

---

**Transform your desktop experience with AI-powered intelligence. Download now and experience the future of human-computer interaction!**



## File Structure

```
ai-voice-assistant/
├── assistant.py              # Main assistant with mode selection
├── assistant_desktop.py      # Desktop-only mode
├── assistant_camera.py       # Camera-only mode
├── run_desktop.py           # Desktop mode launcher
├── run_camera.py            # Camera mode launcher  
├── run_web.py               # Web server launcher
├── src/                     # Flask web application
│   ├── main.py              # Flask app entry point
│   ├── assistant_api.py     # Web API for assistant
│   ├── static/              # Static web files
│   │   └── index.html       # Landing page with demo
│   ├── models/              # Database models
│   └── routes/              # API routes
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── render.yaml             # Render.com deployment config
├── Procfile                # Process configuration
├── runtime.txt             # Python version
└── README.md               # This file
```

## Quick Start Commands

```bash
# Unified multi-mode assistant (RECOMMENDED)
python assistant.py

# Individual mode launchers
python run_desktop.py    # Desktop screen capture only
python run_camera.py     # Camera capture only
python run_web.py        # Web demo and landing page

# Direct execution (alternative)
python assistant_desktop.py  # Desktop mode directly
python assistant_camera.py   # Camera mode directly
```

