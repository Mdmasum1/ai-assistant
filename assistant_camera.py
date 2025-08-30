import base64
import time
import threading
import signal
import sys
import numpy
import cv2
import openai
import os
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

# ==== Graceful Exit Handler ====
def graceful_exit(signum=None, frame=None):
    print("\n🔌 Gracefully shutting down...")
    global running
    running = False
    cv2.destroyAllWindows()
    if recorder:
        recorder.stop()
    if stop_listening:
        stop_listening(wait_for_stop=False)
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

# ==== Camera Recorder ====
class CameraRecorder:
    def __init__(self, output_file="camera_output.mp4", fps=10.0):
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.fps = fps
        self.output_file = output_file
        self.video_writer = None
        self.cap = cv2.VideoCapture(0)

    def start(self):
        if self.running:
            return self
        self.running = True
        self.thread = threading.Thread(target=self.update)
        self.thread.start()
        return self

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            h, w, _ = frame.shape
            if self.video_writer is None:
                fourcc = VideoWriter_fourcc(*"mp4v")
                self.video_writer = VideoWriter(self.output_file, fourcc, self.fps, (w, h))

            with self.lock:
                self.frame = frame
                self.video_writer.write(frame)

            time.sleep(1 / self.fps)

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

# ==== Assistant ====
class Assistant:
    def __init__(self, model):
        self.chain = self._create_inference_chain(model)

    def answer(self, prompt, image):
        if not prompt:
            return

        print("Prompt:", prompt)
        response = self.chain.invoke(
            {"prompt": prompt, "image_base64": image.decode()},
            config={"configurable": {"session_id": "camera_session"}},
        ).strip()

        print("Response:", response)
        if response:
            self._tts(response)
        return response

    def _tts(self, response):
        player = PyAudio().open(format=paInt16, channels=1, rate=24000, output=True)
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="shimmer",
            response_format="pcm",
            input=response,
        ) as stream:
            for chunk in stream.iter_bytes(chunk_size=1024):
                player.write(chunk)

    def _create_inference_chain(self, model):
        SYSTEM_PROMPT = """
        You are a witty assistant that will use the chat history and the camera feed image 
        provided by the user to answer its questions.

        Use few words on your answers. Go straight to the point. Do not use any
        emoticons or emojis. Do not ask the user any questions.

        Be friendly and helpful. Show some personality. Do not be too formal.
        
        You can see what the user's camera is capturing in real-time, so provide context-aware assistance
        based on what's currently visible in the camera feed.
        """

        prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                (
                    "human",
                    [
                        {"type": "text", "text": "{prompt}"},
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
    try:
        prompt = recognizer.recognize_whisper(audio, model="base", language="en")
        image = recorder.read(encode=True)
        if image:
            assistant.answer(prompt, image)
    except UnknownValueError:
        print("⚠️ Could not understand.")
    except Exception as e:
        print(f"[Audio Error]: {e}")

# ==== Init ====
print("📷 Starting AI Voice Assistant - Camera Mode")
print("This mode captures and analyzes your camera feed in real-time.")
print("Press 'q' or ESC to quit, or Ctrl+C to stop.")

model = ChatOpenAI(model="gpt-4o")
assistant = Assistant(model)
recorder = CameraRecorder().start()

recognizer = Recognizer()
microphone = Microphone()
with microphone as source:
    recognizer.adjust_for_ambient_noise(source)

stop_listening = recognizer.listen_in_background(microphone, audio_callback)
running = True

# ==== Main Loop ====
try:
    while running:
        frame = recorder.read()
        if frame is not None:
            preview = cv2.resize(frame, (1280, 720))
            cv2.imshow("Camera AI Assistant", preview)

        if cv2.waitKey(1) in [27, ord("q")]:  # Esc or "q"
            graceful_exit()
except KeyboardInterrupt:
    graceful_exit()
except Exception as e:
    print(f"💥 Unexpected error: {e}")
    graceful_exit()

