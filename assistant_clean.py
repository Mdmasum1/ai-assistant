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
current_mode = "desktop"
active_mode = "desktop"
desktop_recorder = None
camera_recorder = None
assistant = None
stop_listening = None
mode_monitor_thread = None

# ==== Simple Exit Handler ====
def graceful_exit(signum=None, frame=None):
    print("\nShutting down...")
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
        return (self.running and 
                self.is_healthy and 
                time.time() - self.last_capture_time < 5.0)

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join(timeout=3)
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
        self.last_capture_time = 0
        self.is_healthy = True

    def start(self):
        if self.running:
            return self
        
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("Camera not available")
                return self
                
            self.running = True
            self.is_healthy = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            return self
        except Exception as e:
            print(f"Camera error: {e}")
            return self

    def update(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue
                
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
        return (self.running and 
                self.is_healthy and 
                self.cap and 
                self.cap.isOpened() and
                time.time() - self.last_capture_time < 5.0)

    def stop(self):
        self.running = False
        if hasattr(self, "thread") and self.thread.is_alive():
            self.thread.join(timeout=3)
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()

# ==== Mode Monitor ====
def mode_monitor():
    global active_mode, desktop_recorder, camera_recorder, current_mode
    
    while running and current_mode == "both":
        try:
            desktop_available = desktop_recorder and desktop_recorder.is_available()
            camera_available = camera_recorder and camera_recorder.is_available()
            
            if camera_available and desktop_available:
                new_active_mode = "camera"
            elif camera_available:
                new_active_mode = "camera"
            elif desktop_available:
                new_active_mode = "desktop"
            else:
                new_active_mode = active_mode
            
            if new_active_mode != active_mode:
                active_mode = new_active_mode
                print(f"Switched to {active_mode} mode")
            
            time.sleep(2)
            
        except Exception as e:
            print(f"Mode monitor error: {e}")
            time.sleep(5)

# ==== Assistant ====
class EnhancedAssistant:
    def __init__(self, model):
        self.chain = self._create_inference_chain(model)

    def answer(self, prompt, desktop_image=None, camera_image=None, mode="desktop"):
        if not prompt:
            return

        print(f"[{mode.upper()}] Prompt:", prompt)
        
        # Determine which image to use
        if mode == "desktop" and desktop_image:
            image_data = desktop_image
            context = "desktop screen"
        elif mode == "camera" and camera_image:
            image_data = camera_image
            context = "camera feed"
        elif mode == "both":
            if desktop_image and camera_image:
                if active_mode == "camera":
                    image_data = camera_image
                    context = "camera feed"
                else:
                    image_data = desktop_image
                    context = "desktop screen"
            elif desktop_image:
                image_data = desktop_image
                context = "desktop screen"
            elif camera_image:
                image_data = camera_image
                context = "camera feed"
            else:
                print("No image sources available")
                return
        else:
            print("No image data available")
            return

        if not image_data:
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
        You are a helpful AI assistant that can analyze both desktop screens and camera feeds.
        Use few words in your answers. Go straight to the point. Be friendly and helpful.
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
    global current_mode, active_mode, desktop_recorder, camera_recorder, assistant, running

    if not running:
        return

    try:
        prompt = recognizer.recognize_whisper(audio, model="base", language="en")

        print(f"\nVoice command: '{prompt}'")
        print(f"Current mode: {current_mode}")

        desktop_image = None
        camera_image = None

        if current_mode == "both":
            if desktop_recorder and desktop_recorder.is_available():
                desktop_image = desktop_recorder.read(encode=True)
            if camera_recorder and camera_recorder.is_available():
                camera_image = camera_recorder.read(encode=True)
            assistant.answer(prompt, desktop_image, camera_image, "both")

        else:
            if current_mode == "desktop" and desktop_recorder and desktop_recorder.is_available():
                desktop_image = desktop_recorder.read(encode=True)

            if current_mode == "camera" and camera_recorder and camera_recorder.is_available():
                camera_image = camera_recorder.read(encode=True)

            if desktop_image or camera_image:
                assistant.answer(prompt, desktop_image, camera_image, current_mode)
            else:
                print("No image sources available")

    except UnknownValueError:
        print("Could not understand.")
    except Exception as e:
        print(f"Audio Error: {e}")

# ==== Main Function ====
def main():
    global current_mode, active_mode, desktop_recorder, camera_recorder, assistant, stop_listening, mode_monitor_thread, running

    print("AI Voice Assistant - Clean Version")
    print("=" * 50)

    print("Select mode:")
    print("1. Desktop only")
    print("2. Camera only")
    print("3. Both (auto-switch)")

    try:
        choice = input("Enter choice (1-3): ").strip()

        if choice == "1":
            current_mode = "desktop"
        elif choice == "2":
            current_mode = "camera"
        elif choice == "3":
            current_mode = "both"
            active_mode = "desktop"
        else:
            print("Invalid choice, using desktop mode")
            current_mode = "desktop"

    except KeyboardInterrupt:
        print("\nExiting...")
        return

    print(f"\nStarting in {current_mode.upper()} mode...")

    # Initialize AI
    model = ChatOpenAI(model="gpt-4o")
    assistant = EnhancedAssistant(model)

    # Start recorders
    if current_mode in ["desktop", "both"]:
        print("Starting desktop recorder...")
        desktop_recorder = DesktopRecorder().start()
        time.sleep(1)

    if current_mode in ["camera", "both"]:
        print("Starting camera recorder...")
        camera_recorder = CameraRecorder().start()
        time.sleep(1)

    # Start mode monitor for "both" mode
    if current_mode == "both":
        mode_monitor_thread = threading.Thread(target=mode_monitor, daemon=True)
        mode_monitor_thread.start()

    # Initialize voice recognition
    print("Initializing voice recognition...")
    recognizer = Recognizer()
    microphone = Microphone()

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)

    stop_listening = recognizer.listen_in_background(microphone, audio_callback)

    print("\nAI Voice Assistant is ready!")
    print("- Speak naturally for assistance")
    print("- Press Ctrl+C to quit")
    print("- Press ESC in preview window to quit")

    # Main loop
    try:
        while running:
            if current_mode in ["desktop", "both"] and desktop_recorder and desktop_recorder.is_available():
                desktop_frame = desktop_recorder.read()
                if desktop_frame is not None:
                    preview = cv2.resize(desktop_frame, (640, 360))
                    cv2.imshow("Desktop Preview", preview)

            if current_mode in ["camera", "both"] and camera_recorder and camera_recorder.is_available():
                camera_frame = camera_recorder.read()
                if camera_frame is not None:
                    preview = cv2.resize(camera_frame, (640, 360))
                    cv2.imshow("Camera Preview", preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC key
                graceful_exit()

            time.sleep(0.1)

    except KeyboardInterrupt:
        graceful_exit()
    except Exception as e:
        print(f"Error: {e}")
        graceful_exit()

if __name__ == "__main__":
    main()
