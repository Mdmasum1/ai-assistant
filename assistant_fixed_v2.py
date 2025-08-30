import base64
import time
import threading
import signal
import sys
import numpy
import cv2
import openai
import os
from PIL import ImageGrab
from cv2 import imencode, VideoWriter, VideoWriter_fourcc
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.messages import SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from pyaudio import PyAudio, paInt16
from speech_recognition import Recognizer, Microphone, UnknownValueError

load_dotenv()

# ==== Global Variables ====
running = True
current_mode = "desktop"  # "desktop", "camera", or "both"
active_mode = "desktop"   # Currently active mode for "both" mode
desktop_recorder = None
camera_recorder = None
assistant = None
stop_listening = None
mode_monitor_thread = None

# ==== Graceful Exit Handler ====
def graceful_exit(signum=None, frame=None):
    print("\n🔌 Gracefully shutting down...")
    global running
    running = False
    cv2.destroyAllWindows()
    
    if desktop_recorder:
        desktop_recorder.stop()
    if camera_recorder:
        camera_recorder.stop()
    if stop_listening:
        stop_listening(wait_for_stop=False)
    
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

# ==== Enhanced Desktop Recorder ====
class DesktopRecorder:
    def __init__(self, output_file="desktop_output.mp4", fps=10.0):
        self.screenshot = None
        self.running = False
        self.lock = threading.Lock()
        self.fps = fps
        self.output_file = output_file
        self.video_writer = None
        self.last_capture_time = 0
        self.is_healthy = True

    def start(self):
        if self.running:
            return self
        self.running = True
        self.is_healthy = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
        return self

    def update(self):
        while self.running:
            try:
                screenshot = ImageGrab.grab()
                frame = cv2.cvtColor(numpy.array(screenshot), cv2.COLOR_RGB2BGR)

                h, w, _ = frame.shape
                if self.video_writer is None:
                    fourcc = VideoWriter_fourcc(*"mp4v")
                    self.video_writer = VideoWriter(self.output_file, fourcc, self.fps, (w, h))

                with self.lock:
                    self.screenshot = frame
                    self.last_capture_time = time.time()
                    self.is_healthy = True
                    if self.video_writer:
                        self.video_writer.write(frame)

                time.sleep(1 / self.fps)
            except Exception as e:
                print(f"Desktop recorder error: {e}")
                self.is_healthy = False
                time.sleep(1)

    def read(self, encode=False):
        with self.lock:
            if self.screenshot is None:
                return None
            frame = self.screenshot.copy()

        if encode:
            _, buffer = imencode(".jpeg", frame)
            return base64.b64encode(buffer)

        return frame

    def is_available(self):
        """Check if desktop recorder is available and healthy"""
        return (self.running and 
                self.is_healthy and 
                time.time() - self.last_capture_time < 5.0)

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join()
        if self.video_writer:
            self.video_writer.release()

# ==== Enhanced Camera Recorder ====
class CameraRecorder:
    def __init__(self, output_file="camera_output.mp4", fps=10.0, camera_index=0):
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.fps = fps
        self.output_file = output_file
        self.video_writer = None
        self.camera_index = camera_index
        self.cap = None
        self.last_capture_time = 0
        self.is_healthy = True
        self.initialization_attempts = 0
        self.max_initialization_attempts = 5

    def start(self):
        if self.running:
            return self
        
        return self._initialize_camera()

    def _initialize_camera(self):
        """Enhanced camera initialization with better error handling"""
        self.initialization_attempts += 1
        print(f"🔄 Camera initialization attempt {self.initialization_attempts}/{self.max_initialization_attempts}")
        
        # Progressive delay between attempts
        if self.initialization_attempts > 1:
            delay = min(self.initialization_attempts * 2, 10)  # Max 10 second delay
            print(f"⏳ Waiting {delay} seconds before camera initialization...")
            time.sleep(delay)
        
        # Try multiple camera indices
        camera_indices = [0, 1, 2, 3, 4]  # Common camera indices
        
        for idx in camera_indices:
            try:
                print(f"🔍 Trying camera index {idx}...")
                self.cap = cv2.VideoCapture(idx)
                
                if not self.cap.isOpened():
                    self.cap.release()
                    continue
                
                # Configure camera settings
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                
                # Test frame capture
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    print(f"✅ Camera {idx} initialized successfully")
                    self.camera_index = idx
                    self.running = True
                    self.is_healthy = True
                    self.thread = threading.Thread(target=self.update, daemon=True)
                    self.thread.start()
                    return self
                else:
                    print(f"⚠️ Camera {idx} opened but cannot read frames")
                    self.cap.release()
                    
            except Exception as e:
                print(f"❌ Error with camera {idx}: {e}")
                if self.cap:
                    self.cap.release()
                continue
        
        print("❌ No working camera found")
        return self

    def update(self):
        consecutive_failures = 0
        max_consecutive_failures = 30  # Allow 3 seconds of failures at 10fps
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        print("⚠️ Camera connection lost - too many consecutive failures")
                        self.is_healthy = False
                    time.sleep(0.1)
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                h, w, _ = frame.shape
                if self.video_writer is None:
                    fourcc = VideoWriter_fourcc(*"mp4v")
                    self.video_writer = VideoWriter(self.output_file, fourcc, self.fps, (w, h))

                with self.lock:
                    self.frame = frame
                    self.last_capture_time = time.time()
                    self.is_healthy = True
                    if self.video_writer:
                        self.video_writer.write(frame)

                time.sleep(1 / self.fps)
            except Exception as e:
                print(f"Camera recorder error: {e}")
                self.is_healthy = False
                consecutive_failures += 1
                time.sleep(1)

    def read(self, encode=False):
        with self.lock:
            if self.frame is None:
                return None
            frame = self.frame.copy()

        if encode:
            _, buffer = imencode(".jpeg", frame)
            return base64.b64encode(buffer)

        return frame

    def is_available(self):
        """Check if camera is available and healthy"""
        return (self.running and 
                self.is_healthy and 
                self.cap and 
                self.cap.isOpened() and
                time.time() - self.last_capture_time < 5.0)

    def reconnect(self):
        """Attempt to reconnect the camera"""
        if self.initialization_attempts < self.max_initialization_attempts:
            print("🔄 Attempting camera reconnection...")
            self.stop()
            time.sleep(2)
            return self._initialize_camera()
        else:
            print("❌ Maximum camera reconnection attempts reached")
            return self

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join()
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()

# ==== Mode Monitor for "Both" Mode ====
def mode_monitor():
    """Continuously monitor and update active mode for 'both' mode"""
    global active_mode, desktop_recorder, camera_recorder, current_mode
    
    last_status_print = 0
    status_print_interval = 30  # Print status every 30 seconds
    
    while running and current_mode == "both":
        try:
            desktop_available = desktop_recorder and desktop_recorder.is_available()
            camera_available = camera_recorder and camera_recorder.is_available()
            
            # Determine the best active mode
            new_active_mode = None
            
            if camera_available and desktop_available:
                # Both available - prioritize camera (more interactive)
                new_active_mode = "camera"
                status_msg = "📹 Both sources available - using camera mode"
            elif camera_available:
                # Only camera available
                new_active_mode = "camera"
                status_msg = "📷 Using camera mode (desktop unavailable)"
            elif desktop_available:
                # Only desktop available
                new_active_mode = "desktop"
                status_msg = "🖥️ Using desktop mode (camera unavailable)"
            else:
                # Neither available - keep current mode but warn
                status_msg = "⚠️ No sources available - check permissions"
            
            # Update active mode if changed
            if new_active_mode and new_active_mode != active_mode:
                active_mode = new_active_mode
                print(f"🔄 Auto-detection: Switched to {active_mode} mode")
            
            # Attempt camera reconnection if needed
            if not camera_available and camera_recorder and not camera_recorder.is_available():
                if camera_recorder.initialization_attempts < camera_recorder.max_initialization_attempts:
                    print("🔄 Attempting automatic camera reconnection...")
                    camera_recorder = camera_recorder.reconnect()
            
            # Periodic status update
            current_time = time.time()
            if current_time - last_status_print > status_print_interval:
                print(f"📊 Auto-detection status: {status_msg}")
                last_status_print = current_time
            
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            print(f"Mode monitor error: {e}")
            time.sleep(5)

# ==== Enhanced Assistant ====
class EnhancedAssistant:
    def __init__(self, model):
        self.chain = self._create_inference_chain(model)

    def answer(self, prompt, desktop_image=None, camera_image=None, mode="desktop"):
        if not prompt:
            return

        print(f"[{mode.upper()}] Prompt:", prompt)
        
        # Debug: Show what images are available
        print(f"Debug - Desktop image available: {desktop_image is not None}")
        print(f"Debug - Camera image available: {camera_image is not None}")
        
        # Determine which image to use based on mode
        if mode == "desktop" and desktop_image:
            image_data = desktop_image
            context = "desktop screen"
        elif mode == "camera" and camera_image:
            image_data = camera_image
            context = "camera feed"
        elif mode == "both":
            # For "both" mode, intelligently choose the best image
            if desktop_image and camera_image:
                # Both available - use the active mode preference
                if active_mode == "camera":
                    image_data = camera_image
                    context = "camera feed (desktop also available)"
                    print("📊 Both mode: Using camera image (active mode)")
                else:
                    image_data = desktop_image
                    context = "desktop screen (camera also available)"
                    print("📊 Both mode: Using desktop image (active mode)")
            elif desktop_image:
                image_data = desktop_image
                context = "desktop screen (camera unavailable)"
                print("📊 Both mode: Using desktop image only")
            elif camera_image:
                image_data = camera_image
                context = "camera feed (desktop unavailable)"
                print("📊 Both mode: Using camera image only")
            else:
                print("⚠️ Both mode: No image sources available")
                return
        else:
            print("⚠️ No image data available for current mode")
            return

        if not image_data:
            print("⚠️ No image data to process")
            return

        try:
            response = self.chain.invoke(
                {
                    "prompt": prompt, 
                    "image_base64": image_data.decode(),
                    "context": context,
                    "mode": mode
                },
                config={"configurable": {"session_id": f"{mode}_session"}},
            ).strip()

            print(f"[{mode.upper()}] Response:", response)
            if response:
                self._tts(response)
            return response
        except Exception as e:
            print(f"Assistant error: {e}")
            return None

    def _tts(self, response):
        try:
            player = PyAudio().open(format=paInt16, channels=1, rate=24000, output=True)
            with openai.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="shimmer",
                response_format="pcm",
                input=response,
            ) as stream:
                for chunk in stream.iter_bytes(chunk_size=1024):
                    player.write(chunk)
        except Exception as e:
            print(f"TTS error: {e}")

    def _create_inference_chain(self, model):
        SYSTEM_PROMPT = """
        You are a witty AI assistant that can analyze both desktop screens and camera feeds to provide context-aware assistance.

        Based on the mode and context provided:
        - For "desktop" mode: Focus on what's displayed on the user's screen
        - For "camera" mode: Focus on what the camera is capturing
        - For "both" mode: The system automatically selects the best available source

        Use few words in your answers. Go straight to the point. Do not use emoticons or emojis. 
        Do not ask the user questions. Be friendly and helpful with personality, but not too formal.
        
        Provide intelligent, context-aware assistance based on the visual information available.
        """

        prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                (
                    "human",
                    [
                        {"type": "text", "text": "Mode: {mode}, Context: {context}, Prompt: {prompt}"},
                        {
                            "type": "image_url",
                            "image_url": "data:image/jpeg;base64,{image_base64}",
                        },
                    ],
                ),
            ]
        )

        chain = prompt_template | model | StrOutputParser()
        chat_message_history = ChatMessageHistory()

        return RunnableWithMessageHistory(
            chain,
            lambda _: chat_message_history,
            input_messages_key="prompt",
            history_messages_key="chat_history",
        )

# ==== FIXED Audio Callback ====
def audio_callback(recognizer, audio):
    global current_mode, active_mode, desktop_recorder, camera_recorder, assistant
    
    try:
        prompt = recognizer.recognize_whisper(audio, model="base", language="en")
        
        print(f"\n🎤 Voice command received: '{prompt}'")
        print(f"Current mode: {current_mode}")
        if current_mode == "both":
            print(f"Active mode: {active_mode}")
        
        # Get images based on current/active mode
        desktop_image = None
        camera_image = None
        
        # For 'both' mode, get both images and let assistant decide
        if current_mode == "both":
            # Check desktop recorder
            if desktop_recorder and desktop_recorder.is_available():
                print("📸 Attempting to capture desktop image...")
                desktop_image = desktop_recorder.read(encode=True)
                print(f"Desktop capture: {'✅ Success' if desktop_image else '❌ Failed'}")
            
            # Check camera recorder
            if camera_recorder and camera_recorder.is_available():
                print("📷 Attempting to capture camera image...")
                camera_image = camera_recorder.read(encode=True)
                print(f"Camera capture: {'✅ Success' if camera_image else '❌ Failed'}")
            
            # Show what's available
            if desktop_image and camera_image:
                print(f"🔄 Both sources available - will use {active_mode} mode preference")
            elif desktop_image:
                print("🔄 Only desktop available")
            elif camera_image:
                print("🔄 Only camera available")
            else:
                print("⚠️ No image sources available")
                return
            
            # Process with assistant using "both" mode
            assistant.answer(prompt, desktop_image, camera_image, "both")
            
        else:
            # Single mode operation
            if current_mode == "desktop" and desktop_recorder and desktop_recorder.is_available():
                print("📸 Attempting to capture desktop image...")
                desktop_image = desktop_recorder.read(encode=True)
                print(f"Desktop capture: {'✅ Success' if desktop_image else '❌ Failed'}")
            
            if current_mode == "camera" and camera_recorder and camera_recorder.is_available():
                print("📷 Attempting to capture camera image...")
                camera_image = camera_recorder.read(encode=True)
                print(f"Camera capture: {'✅ Success' if camera_image else '❌ Failed'}")
            
            # Process with assistant
            if desktop_image or camera_image:
                assistant.answer(prompt, desktop_image, camera_image, current_mode)
            else:
                print("⚠️ No image sources available - check permissions")
            
    except UnknownValueError:
        print("⚠️ Could not understand.")
    except Exception as e:
        print(f"[Audio Error]: {e}")
        import traceback
        traceback.print_exc()

# ==== Enhanced Status Display ====
def display_status():
    global current_mode, active_mode, desktop_recorder, camera_recorder
    
    print("\n" + "="*60)
    print("📊 AI VOICE ASSISTANT STATUS - FIXED V2")
    print("="*60)
    print(f"Current Mode: {current_mode.upper()}")
    
    if current_mode == "both":
        print(f"Active Mode: {active_mode.upper()}")
        print("\n🔄 AUTO-DETECTION MODE (FIXED):")
        print("  - Continuously monitors source availability")
        print("  - Automatically switches between desktop and camera")
        print("  - Uses active mode preference when both available")
        print("  - Automatic camera reconnection")
        print("  - Real-time health monitoring")
    
    print(f"\n🖥️ Desktop Recorder:")
    if desktop_recorder:
        status = "✅ Active" if desktop_recorder.is_available() else "❌ Inactive"
        print(f"  Status: {status}")
        if desktop_recorder.running:
            print(f"  Last capture: {time.time() - desktop_recorder.last_capture_time:.1f}s ago")
        print(f"  Can capture frames: {'✅ Yes' if desktop_recorder.read() is not None else '❌ No'}")
    else:
        print("  Status: ❌ Not initialized")
    
    print(f"\n📷 Camera Recorder:")
    if camera_recorder:
        status = "✅ Active" if camera_recorder.is_available() else "❌ Inactive"
        print(f"  Status: {status}")
        print(f"  Camera index: {camera_recorder.camera_index}")
        print(f"  Initialization attempts: {camera_recorder.initialization_attempts}/{camera_recorder.max_initialization_attempts}")
        if camera_recorder.running:
            print(f"  Last capture: {time.time() - camera_recorder.last_capture_time:.1f}s ago")
        device_status = "✅ Connected" if (camera_recorder.cap and camera_recorder.cap.isOpened()) else "❌ Disconnected"
        print(f"  Camera device: {device_status}")
        print(f"  Can capture frames: {'✅ Yes' if camera_recorder.read() is not None else '❌ No'}")
    else:
        print("  Status: ❌ Not initialized")
    
    print(f"\n🎤 Voice Recognition: {'✅ Active' if stop_listening else '❌ Inactive'}")
    print(f"🤖 AI Assistant: {'✅ Ready' if assistant else '❌ Not initialized'}")
    
    if current_mode == "both":
        print(f"\n🔍 Mode Monitor: {'✅ Running' if mode_monitor_thread and mode_monitor_thread.is_alive() else '❌ Stopped'}")
        
        # Enhanced status for both mode
        desktop_ok = desktop_recorder and desktop_recorder.is_available()
        camera_ok = camera_recorder and camera_recorder.is_available()
        
        print(f"\n📋 Both Mode Status:")
        if desktop_ok and camera_ok:
            print(f"  Status: ✅ Fully operational (using {active_mode} preference)")
        elif desktop_ok or camera_ok:
            print("  Status: ⚠️ Partially operational (one source available)")
        else:
            print("  Status: ❌ Not operational (no sources available)")
    
    print("\n🎮 Controls:")
    print("  - Speak naturally for AI assistance")
    if current_mode == "both":
        print("  - System automatically detects and switches between modes")
        print("  - Desktop and camera both work in 'both' mode")
    print("  - Press 's' + Enter: Show this detailed status")
    print("  - Press 'q' + Enter or Ctrl+C: Quit")
    print("="*60)

# ==== Main Function ====
def main():
    global current_mode, active_mode, desktop_recorder, camera_recorder, assistant, stop_listening, mode_monitor_thread, running
    
    print("🤖 AI Voice Assistant - Enhanced Multi-Mode (FIXED V2)")
    print("=" * 60)
    print("Features: Desktop Screen Capture + Camera Feed + Voice Recognition")
    print("🔧 FIXED: Option 3 now properly detects BOTH desktop and camera")
    print()
    
    # Initial mode selection
    print("Select initial mode:")
    print("1. Desktop only (screen capture)")
    print("2. Camera only (camera feed)")
    print("3. Both (desktop + camera) - FIXED DESKTOP DETECTION")
    
    try:
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            current_mode = "desktop"
        elif choice == "2":
            current_mode = "camera"
        elif choice == "3":
            current_mode = "both"
            active_mode = "desktop"  # Default active mode
        else:
            print("Invalid choice, defaulting to desktop mode")
            current_mode = "desktop"
            
    except KeyboardInterrupt:
        print("\nExiting...")
        return
    
    print(f"\n🚀 Starting in {current_mode.upper()} mode...")
    
    # Initialize AI model and assistant
    model = ChatOpenAI(model="gpt-4o")
    assistant = EnhancedAssistant(model)
    
    # Start recorders based on mode with enhanced resource management
    if current_mode in ["desktop", "both"]:
        print("🖥️ Starting desktop recorder...")
        try:
            desktop_recorder = DesktopRecorder().start()
            time.sleep(2)  # Give it time to initialize
            if desktop_recorder.is_available():
                print("✅ Desktop recorder started successfully")
            else:
                print("❌ Desktop recorder failed to start")
        except Exception as e:
            print(f"❌ Desktop recorder error: {e}")
    
    # Enhanced camera initialization for 'both' mode
    if current_mode in ["camera", "both"]:
        if current_mode == "both":
            print("⏳ Waiting for desktop recorder to stabilize before starting camera...")
            time.sleep(3)  # Extra delay for 'both' mode
        
        print("📷 Starting camera recorder...")
        try:
            camera_recorder = CameraRecorder().start()
            time.sleep(2)  # Give camera time to initialize
            
            if camera_recorder.is_available():
                print("✅ Camera recorder started successfully")
            else:
                print("⚠️ Camera recorder failed to start. Will attempt reconnection automatically.")
                if current_mode == "both":
                    print("⚠️ Continuing with desktop mode available")
                    
        except Exception as e:
            print(f"❌ Camera recorder error: {e}")
            if current_mode == "both":
                print("⚠️ Continuing with desktop mode available")
    
    # Start mode monitor for "both" mode
    if current_mode == "both":
        print("🔍 Starting enhanced automatic mode detection monitor...")
        mode_monitor_thread = threading.Thread(target=mode_monitor, daemon=True)
        mode_monitor_thread.start()
    
    # Initialize voice recognition
    print("🎤 Initializing voice recognition...")
    recognizer = Recognizer()
    microphone = Microphone()
    
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
    
    stop_listening = recognizer.listen_in_background(microphone, audio_callback)
    
    print("\n✅ AI Voice Assistant is ready!")
    print("\nControls:")
    print("- Speak naturally for AI assistance")
    if current_mode == "both":
        print("- System automatically detects and switches between modes")
        print("- Desktop screen detection now works properly!")
        print("- Camera detection also works!")
    print("- Press 's' + Enter to show detailed status")
    print("- Press 'q' + Enter or Ctrl+C to quit")
    print("- Press ESC in any preview window to quit")
    
    # Main loop with enhanced preview
    try:
        while running:
            # Display preview windows with mode indicators
            if current_mode in ["desktop", "both"] and desktop_recorder and desktop_recorder.is_available():
                desktop_frame = desktop_recorder.read()
                if desktop_frame is not None:
                    preview = cv2.resize(desktop_frame, (640, 360))
                    
                    # Add mode indicator for "both" mode
                    if current_mode == "both":
                        color = (0, 255, 0) if active_mode == "desktop" else (0, 165, 255)
                        status_text = f"DESKTOP {'(ACTIVE)' if active_mode == 'desktop' else '(STANDBY)'}"
                        cv2.putText(preview, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    cv2.imshow("Desktop Preview", preview)
            
            if current_mode in ["camera", "both"] and camera_recorder and camera_recorder.is_available():
                camera_frame = camera_recorder.read()
                if camera_frame is not None:
                    preview = cv2.resize(camera_frame, (640, 360))
                    
                    # Add mode indicator for "both" mode
                    if current_mode == "both":
                        color = (0, 255, 0) if active_mode == "camera" else (0, 165, 255)
                        status_text = f"CAMERA {'(ACTIVE)' if active_mode == 'camera' else '(STANDBY)'}"
                        cv2.putText(preview, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    cv2.imshow("Camera Preview", preview)
            
            # Check for key presses
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC key
                graceful_exit()
            elif key == ord('s'):  # 's' key for status
                display_status()
            elif key == ord('q'):  # 'q' key for quit
                graceful_exit()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        graceful_exit()
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        graceful_exit()

if __name__ == "__main__":
    main()

