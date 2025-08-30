"""
AI Voice Assistant API Module
Provides web API endpoints for the AI Voice Assistant functionality
"""

import base64
import io
import json
import threading
import time
from flask import Blueprint, request, jsonify, Response
from PIL import ImageGrab
import cv2
import numpy as np
import openai
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.messages import SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

load_dotenv()

# Create Blueprint for assistant API
assistant_bp = Blueprint('assistant', __name__)

class WebAssistant:
    """Web-based version of the AI Assistant"""
    
    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o")
        self.chain = self._create_inference_chain()
        self.is_active = False
        
    def _create_inference_chain(self):
        """Create the LangChain inference chain"""
        SYSTEM_PROMPT = """
        You are a witty assistant that will use the chat history and the image 
        provided by the user to answer its questions.

        Use few words on your answers. Go straight to the point. Do not use any
        emoticons or emojis. Do not ask the user any questions.

        Be friendly and helpful. Show some personality. Do not be too formal.
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

        chain = prompt_template | self.model | StrOutputParser()
        chat_message_history = ChatMessageHistory()

        return RunnableWithMessageHistory(
            chain,
            lambda _: chat_message_history,
            input_messages_key="prompt",
            history_messages_key="chat_history",
        )
    
    def capture_screen(self):
        """Capture current screen and return as base64 encoded image"""
        # Placeholder for web demo. In a real desktop app, this would capture the actual screen.
        # For web demo, we can return a static image or a blank image.
        try:
            # Create a blank image for demonstration purposes
            width, height = 800, 600
            blank_image = np.zeros((height, width, 3), np.uint8)
            cv2.putText(blank_image, "SCREEN CAPTURE DISABLED IN WEB DEMO", (50, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            _, buffer = cv2.imencode(".jpeg", blank_image)
            return base64.b64encode(buffer).decode()
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None
    
    def process_query(self, prompt, image_base64=None):
        """Process a text query with optional image"""
        try:
            if not image_base64:
                image_base64 = self.capture_screen()
            
            if not image_base64:
                return {"error": "Failed to capture screen"}
            
            response = self.chain.invoke(
                {"prompt": prompt, "image_base64": image_base64},
                config={"configurable": {"session_id": "web_session"}},
            ).strip()
            
            return {
                "success": True,
                "response": response,
                "timestamp": time.time()
            }
        except Exception as e:
            return {"error": str(e)}

# Initialize the web assistant
web_assistant = WebAssistant()

@assistant_bp.route('/api/assistant/status', methods=['GET'])
def get_status():
    """Get assistant status"""
    return jsonify({
        "status": "active" if web_assistant.is_active else "inactive",
        "model": "gpt-4o",
        "capabilities": [
            "screen_analysis",
            "voice_recognition", 
            "text_to_speech",
            "context_awareness"
        ]
    })

@assistant_bp.route('/api/assistant/query', methods=['POST'])
def process_query():
    """Process a text query with screen context"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        result = web_assistant.process_query(prompt)
        
        if "error" in result:
            return jsonify(result), 500
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@assistant_bp.route('/api/assistant/screenshot', methods=['GET'])
def get_screenshot():
    """Get current screen screenshot"""
    try:
        image_base64 = web_assistant.capture_screen()
        
        if not image_base64:
            return jsonify({"error": "Failed to capture screen"}), 500
        
        return jsonify({
            "success": True,
            "image": image_base64,
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@assistant_bp.route('/api/assistant/activate', methods=['POST'])
def activate_assistant():
    """Activate the assistant"""
    web_assistant.is_active = True
    return jsonify({
        "success": True,
        "message": "Assistant activated",
        "status": "active"
    })

@assistant_bp.route('/api/assistant/deactivate', methods=['POST'])
def deactivate_assistant():
    """Deactivate the assistant"""
    web_assistant.is_active = False
    return jsonify({
        "success": True,
        "message": "Assistant deactivated", 
        "status": "inactive"
    })

@assistant_bp.route('/api/assistant/demo', methods=['POST'])
def demo_query():
    """Demo endpoint that works without requiring actual screen capture"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', 'What can you help me with?')
        mode = data.get('mode', 'desktop')  # 'desktop' or 'camera'

        # Create intelligent demo responses based on the prompt
        prompt_lower = prompt.lower()

        if 'help' in prompt_lower or 'what' in prompt_lower:
            if mode == 'camera':
                demo_response = """📷 <strong>Camera Mode Demo</strong><br><br>
                I can help you with:<br>
                • <strong>Visual Recognition:</strong> Identify objects, people, text in your camera view<br>
                • <strong>Real-time Analysis:</strong> Describe what I see through your camera<br>
                • <strong>Interactive Assistance:</strong> Answer questions about your physical environment<br>
                • <strong>Voice Commands:</strong> Respond to natural speech while watching your camera<br><br>
                <em>Try asking: "What do you see?" or "Describe my surroundings"</em>"""
            else:
                demo_response = """🖥️ <strong>Desktop Mode Demo</strong><br><br>
                I can help you with:<br>
                • <strong>Screen Analysis:</strong> Understand what's on your screen right now<br>
                • <strong>App Assistance:</strong> Help with software you're currently using<br>
                • <strong>Context-Aware Help:</strong> Provide relevant assistance based on your current task<br>
                • <strong>Voice Control:</strong> Execute commands while seeing your desktop<br><br>
                <em>Try asking: "What's on my screen?" or "Help me with this application"</em>"""

        elif 'screen' in prompt_lower or 'desktop' in prompt_lower:
            demo_response = f"""🖥️ <strong>Screen Analysis Demo</strong><br><br>
            You asked: "<em>{prompt}</em>"<br><br>
            In the full version, I would analyze your current screen and provide specific help with:
            • Applications you're using
            • Documents you're working on
            • Websites you're browsing
            • Any visible content or interface elements<br><br>
            <strong>This is a web demo</strong> - the desktop app provides real screen analysis!"""

        elif 'camera' in prompt_lower or 'see' in prompt_lower:
            demo_response = f"""📷 <strong>Camera Analysis Demo</strong><br><br>
            You asked: "<em>{prompt}</em>"<br><br>
            In the full version, I would analyze your camera feed and help with:
            • Identifying objects and people
            • Reading text in your environment
            • Describing your surroundings
            • Providing contextual assistance<br><br>
            <strong>This is a web demo</strong> - the desktop app provides real camera analysis!"""

        else:
            # Generic intelligent response
            if mode == 'camera':
                demo_response = f"""📷 <strong>Camera Mode Response</strong><br><br>
                You asked: "<em>{prompt}</em>"<br><br>
                I understand your question! In camera mode, I would analyze your live camera feed and provide intelligent responses based on what I see. The full desktop application combines computer vision with AI to give you contextual assistance.<br><br>
                <em>This demo shows the interface - download the full app for real-time camera analysis!</em>"""
            else:
                demo_response = f"""🖥️ <strong>Desktop Mode Response</strong><br><br>
                You asked: "<em>{prompt}</em>"<br><br>
                I understand your question! In desktop mode, I would analyze your current screen and provide intelligent responses based on what you're working on. The full application combines screen capture with AI to give you contextual assistance.<br><br>
                <em>This demo shows the interface - download the full app for real-time screen analysis!</em>"""

        return jsonify({
            "success": True,
            "response": demo_response,
            "mode": mode,
            "demo_mode": True,
            "timestamp": time.time()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@assistant_bp.route('/api/purchase/track', methods=['POST'])
def track_purchase():
    """Track purchase analytics for Gumroad integration"""
    try:
        data = request.get_json()
        plan = data.get('plan', 'basic')
        action = data.get('action', 'unknown')

        # Log purchase tracking (in production, save to database/analytics)
        print(f"Purchase tracking: {action} for {plan} plan")

        # In production, you might:
        # 1. Save to analytics database
        # 2. Send to Google Analytics
        # 3. Track conversion funnels
        # 4. Update marketing metrics

        return jsonify({
            "success": True,
            "tracked": True,
            "plan": plan,
            "action": action
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@assistant_bp.route('/api/gumroad/products', methods=['GET'])
def get_gumroad_products():
    """Get Gumroad product information"""
    try:
        products = {
            "basic": {
                "name": "AI Voice Assistant - Basic License",
                "price": "$29",
                "gumroad_url": "https://gumroad.com/l/ai-voice-assistant-basic",
                "features": [
                    "Complete AI Voice Assistant software",
                    "Installation guide for all platforms",
                    "Basic tutorial videos",
                    "Email support",
                    "30-day money-back guarantee"
                ],
                "perfect_for": [
                    "Students and personal users",
                    "Basic productivity enhancement",
                    "Learning AI-powered workflows"
                ]
            },
            "professional": {
                "name": "AI Voice Assistant - Professional License",
                "price": "$59",
                "gumroad_url": "https://gumroad.com/l/ai-voice-assistant-pro",
                "badge": "Most Popular",
                "features": [
                    "ALL features unlocked",
                    "Commercial use rights",
                    "Priority email support",
                    "Lifetime updates guaranteed",
                    "Advanced tutorial series",
                    "Productivity optimization guide"
                ],
                "perfect_for": [
                    "Working professionals and freelancers",
                    "Small business owners",
                    "Content creators and designers"
                ]
            },
            "developer": {
                "name": "AI Voice Assistant - Developer License",
                "price": "$99",
                "gumroad_url": "https://gumroad.com/l/ai-voice-assistant-dev",
                "features": [
                    "Multi-user license (5 users)",
                    "Full source code access",
                    "API documentation & examples",
                    "Commercial redistribution rights",
                    "Dedicated developer support",
                    "Custom integration assistance"
                ],
                "perfect_for": [
                    "Development teams and agencies",
                    "Technical professionals",
                    "Companies wanting custom integrations"
                ]
            }
        }

        return jsonify({
            "success": True,
            "products": products,
            "currency": "USD",
            "guarantee": "30-day money-back guarantee"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@assistant_bp.route('/api/download/package', methods=['GET'])
def download_package():
    """Provide download information"""
    try:
        user_agent = request.headers.get('User-Agent', '')

        # Detect platform
        if 'Mac' in user_agent:
            platform = 'macOS'
            filename = 'AI-Voice-Assistant-macOS.zip'
        elif 'Linux' in user_agent:
            platform = 'Linux'
            filename = 'AI-Voice-Assistant-Linux.tar.gz'
        else:
            platform = 'Windows'
            filename = 'AI-Voice-Assistant-Windows.zip'

        return jsonify({
            "success": True,
            "platform": platform,
            "filename": filename,
            "download_url": f"/downloads/{filename}",
            "size": "15.2 MB",
            "version": "1.0.0",
            "requirements": [
                "Python 3.8+",
                "OpenAI API key",
                "Microphone access",
                "Screen recording permission"
            ],
            "installation_steps": [
                "1. Extract the downloaded file",
                "2. Install requirements: pip install -r requirements.txt",
                "3. Set up your OpenAI API key in .env file",
                "4. Run: python assistant.py",
                "5. Choose your preferred mode (Desktop/Camera/Both)"
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

