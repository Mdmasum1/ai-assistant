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
desktop_recorder = None
camera_recorder = None
assistant = None
stop_listening = None

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

# ==== Desktop Recorder ====
class DesktopRecorder:
    def __init__(self, output_file="desktop_output.mp4", fps=10.0):
        self.screenshot = None
        self.running = False
        self.lock = threading.Lock()
        self.fps = fps
        self.output_file = output_file
        self.video_writer = None

    def start(self):
        if self.running:
            return self
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)  # Make thread daemon
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
                    if self.video_writer:
                        self.video_writer.write(frame)

                time.sleep(1 / self.fps)
            except Exception as e:
                print(f"Desktop recorder error: {e}")
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

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join()
        if self.video_writer:
            self.video_writer.release()

# ==== Camera Recorder ====
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

    def start(self):
        if self.running:
            return self
        
        print(f"Attempting to open camera at index {self.camera_index}...")
        
        # Add small delay to prevent resource conflicts when starting after desktop recorder
        time.sleep(0.5)
        
        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Set camera properties to ensure proper initialization
        if self.cap.isOpened():
            # Set buffer size to 1 to reduce latency and resource usage
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # Set reasonable resolution to reduce resource usage
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Set FPS to match our recording FPS
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open camera at index {self.camera_index}. Trying next available...")
            # Try other indices if 0 fails
            for i in range(1, 5): # Try indices 1 to 4
                time.sleep(0.5)  # Small delay between attempts
                self.cap = cv2.VideoCapture(i)
                if self.cap.isOpened():
                    self.camera_index = i
                    print(f"✅ Successfully opened camera at index {self.camera_index}")
                    # Set properties for the new camera
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                    break
            else:
                print("❌ No camera found or accessible at common indices (0-4).")
                return self # Return without starting thread if no camera found

        # Test if camera can read frames immediately
        ret, test_frame = self.cap.read()
        if not ret or test_frame is None:
            print(f"❌ Camera at index {self.camera_index} cannot read frames. It might be in use or corrupted.")
            self.cap.release()
            return self
        else:
            print(f"✅ Camera at index {self.camera_index} can read frames.")

        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)  # Make thread daemon
        self.thread.start()
        return self

    def update(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                h, w, _ = frame.shape
                if self.video_writer is None:
                    fourcc = VideoWriter_fourcc(*"mp4v")
                    self.video_writer = VideoWriter(self.output_file, fourcc, self.fps, (w, h))

                with self.lock:
                    self.frame = frame
                    if self.video_writer:
                        self.video_writer.write(frame)

                time.sleep(1 / self.fps)
            except Exception as e:
                print(f"Camera recorder error: {e}")
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

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join()
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()

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
            # For "both" mode, create a combined context and use available images
            if desktop_image and camera_image:
                # Both available - prioritize desktop but mention both
                image_data = desktop_image
                context = "both desktop screen and camera feed (analyzing desktop view)"
                print("📊 Both mode: Using desktop image with camera context awareness")
            elif desktop_image:
                image_data = desktop_image
                context = "desktop screen (camera feed unavailable)"
                print("📊 Both mode: Using desktop image only (camera unavailable)")
            elif camera_image:
                image_data = camera_image
                context = "camera feed (desktop capture unavailable)"
                print("📊 Both mode: Using camera image only (desktop unavailable)")
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
        - For "both" mode: Consider information from both sources when available

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

# ==== Audio Callback ====
def audio_callback(recognizer, audio):
    global current_mode, desktop_recorder, camera_recorder, assistant
    
    try:
        prompt = recognizer.recognize_whisper(audio, model="base", language="en")
        
        # Get images based on current mode with debug info
        desktop_image = None
        camera_image = None
        
        print(f"\n🎤 Voice command received: '{prompt}'")
        print(f"Current mode: {current_mode}")
        
        # For 'both' mode, automatically detect which sources are available and prioritize accordingly
        if current_mode == "both":
            # Check desktop recorder
            if desktop_recorder and desktop_recorder.running:
                print("📸 Attempting to capture desktop image...")
                desktop_image = desktop_recorder.read(encode=True)
                print(f"Desktop capture result: {'✅ Success' if desktop_image else '❌ Failed'}")
            
            # Check camera recorder
            if camera_recorder and camera_recorder.running:
                print("📷 Attempting to capture camera image...")
                camera_image = camera_recorder.read(encode=True)
                print(f"Camera capture result: {'✅ Success' if camera_image else '❌ Failed'}")
            
            # Automatic mode detection based on available sources
            if camera_image and desktop_image:
                # Both available - use camera as primary (more interactive)
                active_mode = "camera"
                primary_image = camera_image
                print("🔄 Auto-detected: Using camera mode (both sources available)")
            elif camera_image:
                # Only camera available
                active_mode = "camera"
                primary_image = camera_image
                print("🔄 Auto-detected: Using camera mode (desktop unavailable)")
            elif desktop_image:
                # Only desktop available
                active_mode = "desktop"
                primary_image = desktop_image
                print("🔄 Auto-detected: Using desktop mode (camera unavailable)")
            else:
                print("⚠️ Both mode: No image sources available")
                return
            
            # Process with the automatically detected mode
            assistant.answer(prompt, desktop_image, camera_image, active_mode)
            
        else:
            # Single mode operation (desktop or camera only)
            if current_mode == "desktop" and desktop_recorder:
                print("📸 Attempting to capture desktop image...")
                desktop_image = desktop_recorder.read(encode=True)
                print(f"Desktop capture result: {'✅ Success' if desktop_image else '❌ Failed'}")
            
            if current_mode == "camera" and camera_recorder:
                print("📷 Attempting to capture camera image...")
                camera_image = camera_recorder.read(encode=True)
                print(f"Camera capture result: {'✅ Success' if camera_image else '❌ Failed'}")
            
            # Process with assistant
            if desktop_image or camera_image:
                assistant.answer(prompt, desktop_image, camera_image, current_mode)
            else:
                print("⚠️ No image sources available - check camera/desktop permissions")
            
    except UnknownValueError:
        print("⚠️ Could not understand.")
    except Exception as e:
        print(f"[Audio Error]: {e}")
        import traceback
        traceback.print_exc()

# ==== Status Display ====
def display_status():
    global current_mode, desktop_recorder, camera_recorder
    
    print("\n" + "="*50)
    print("📊 AI VOICE ASSISTANT STATUS")
    print("="*50)
    print(f"Current Mode: {current_mode.upper()}")
    
    if current_mode == "both":
        print("\n🔄 AUTO-DETECTION MODE:")
        print("  - Automatically switches between desktop and camera")
        print("  - Prioritizes camera when both are available")
        print("  - Falls back gracefully when sources are unavailable")
    
    print(f"\n🖥️ Desktop Recorder:")
    if desktop_recorder:
        print(f"  Status: {'✅ Active' if desktop_recorder.running else '❌ Inactive'}")
        if desktop_recorder.running:
            test_frame = desktop_recorder.read()
            print(f"  Can capture frames: {'✅ Yes' if test_frame is not None else '❌ No'}")
    else:
        print("  Status: ❌ Not initialized")
    
    print(f"\n📷 Camera Recorder:")
    if camera_recorder:
        print(f"  Status: {'✅ Active' if camera_recorder.running else '❌ Inactive'}")
        if camera_recorder.running and camera_recorder.cap:
            print(f"  Camera device: {'✅ Connected' if camera_recorder.cap.isOpened() else '❌ Disconnected'}")
            if camera_recorder.cap.isOpened():
                test_frame = camera_recorder.read()
                print(f"  Can capture frames: {'✅ Yes' if test_frame is not None else '❌ No'}")
        else:
            print("  Camera device: ❌ Not available")
    else:
        print("  Status: ❌ Not initialized")
    
    print(f"\n🎤 Voice Recognition: ✅ Active")
    print(f"🤖 AI Assistant: ✅ Ready")
    
    if current_mode == "both":
        print(f"\n📋 Both Mode Requirements:")
        desktop_ok = desktop_recorder and desktop_recorder.running
        camera_ok = camera_recorder and camera_recorder.running and camera_recorder.cap and camera_recorder.cap.isOpened()
        
        if desktop_ok and camera_ok:
            print("  Status: ✅ Fully operational (both sources available)")
        elif desktop_ok or camera_ok:
            print("  Status: ⚠️ Partially operational (one source available)")
        else:
            print("  Status: ❌ Not operational (no sources available)")
    
    print("\n🎮 Controls:")
    print("  - Speak naturally for AI assistance")
    if current_mode == "both":
        print("  - System automatically detects best mode")
    print("  - Press 's' + Enter: Show this status")
    print("  - Press 'q' + Enter or Ctrl+C: Quit")
    print("="*50)

# ==== Main Function ====
def main():
    global current_mode, desktop_recorder, camera_recorder, assistant, stop_listening, running
    
    print("🤖 AI Voice Assistant - Enhanced Multi-Mode")
    print("=" * 50)
    print("Features: Desktop Screen Capture + Camera Feed + Voice Recognition")
    print()
    
    # Initial mode selection
    print("Select initial mode:")
    print("1. Desktop only (screen capture)")
    print("2. Camera only (camera feed)")
    print("3. Both (desktop + camera)")
    
    try:
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            current_mode = "desktop"
        elif choice == "2":
            current_mode = "camera"
        elif choice == "3":
            current_mode = "both"
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
    
    # Start recorders based on mode with proper resource management
    if current_mode in ["desktop", "both"]:
        print("🖥️ Starting desktop recorder...")
        try:
            desktop_recorder = DesktopRecorder().start()
            time.sleep(1)  # Give it time to initialize
            if desktop_recorder.running:
                print("✅ Desktop recorder started successfully")
            else:
                print("❌ Desktop recorder failed to start")
        except Exception as e:
            print(f"❌ Desktop recorder error: {e}")
    
    # For 'both' mode, add extra delay to prevent resource conflicts
    if current_mode == "both":
        print("⏳ Waiting for desktop recorder to stabilize before starting camera...")
        time.sleep(2)  # Extra delay for 'both' mode
    
    if current_mode in ["camera", "both"]:
        print("📷 Starting camera recorder...")
        try:
            # For 'both' mode, try multiple times with delays if camera fails
            max_attempts = 3 if current_mode == "both" else 1
            camera_started = False
            
            for attempt in range(max_attempts):
                if attempt > 0:
                    print(f"🔄 Camera initialization attempt {attempt + 1}/{max_attempts}...")
                    time.sleep(2)  # Wait between attempts
                
                camera_recorder = CameraRecorder().start()
                time.sleep(3)  # Give camera more time to initialize
                
                if camera_recorder.running and camera_recorder.cap and camera_recorder.cap.isOpened():
                    # Double-check by trying to read a frame
                    test_frame = camera_recorder.read()
                    if test_frame is not None:
                        print("✅ Camera recorder started successfully")
                        camera_started = True
                        break
                    else:
                        print(f"⚠️ Camera opened but cannot read frames (attempt {attempt + 1})")
                        camera_recorder.stop()
                        camera_recorder = None
                else:
                    print(f"⚠️ Camera failed to start (attempt {attempt + 1})")
                    if camera_recorder:
                        camera_recorder.stop()
                        camera_recorder = None
            
            if not camera_started:
                print("❌ Camera recorder failed to start after all attempts. Check permissions and if camera is in use.")
                if current_mode == "both":
                    print("⚠️ Continuing in desktop-only mode due to camera issues")
                    
        except Exception as e:
            print(f"❌ Camera recorder error: {e}")
            if current_mode == "both":
                print("⚠️ Continuing in desktop-only mode due to camera issues")
    
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
        print("- System automatically detects best mode (desktop/camera)")
    print("- Press 's' + Enter to show status")
    print("- Press 'q' + Enter or Ctrl+C to quit")
    print("- Press ESC in any preview window to quit")
    
    # Main loop
    try:
        while running:
            # Display preview windows
            if current_mode in ["desktop", "both"] and desktop_recorder:
                desktop_frame = desktop_recorder.read()
                if desktop_frame is not None:
                    preview = cv2.resize(desktop_frame, (640, 360))
                    cv2.imshow("Desktop Preview", preview)
            
            if current_mode in ["camera", "both"] and camera_recorder:
                camera_frame = camera_recorder.read()
                if camera_frame is not None:
                    preview = cv2.resize(camera_frame, (640, 360))
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

