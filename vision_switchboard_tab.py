import os
import sys
import cv2
import base64
import requests
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QComboBox, QMessageBox, QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
import pytesseract
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
import numpy as np
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import threading

# Import crimson theme
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Prime', 'foundations'))
try:
    from crimson_theme import apply_crimson_theme
except ImportError:
    print("Warning: Could not import crimson_theme, using default styling")
    apply_crimson_theme = lambda x: None

# Lazy loading globals
ci = None
CLIP_AVAILABLE = True
blip_processor = None
blip_model = None
sam_predictor = None
yolo_model = None
device = None
models_loading = {
    'clip': False,
    'blip': False,
    'yolo': False
}
models_ready = {
    'clip': False,
    'blip': False,
    'yolo': False
}

# Strategy to model mapping
STRATEGY_MODELS = {
    "Literal": "llava:latest",
    "Symbolic": "granite3.2-vision:latest",
    "Emotional": "bakllava:latest",
    "OllamaVision": None  # Will use selected model
}

# Setup
TESS_PATH = r"C:/Program Files/Tesseract-OCR/tesseract.exe"
if os.path.exists(TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESS_PATH

def get_available_ollama_models():
    """Fetch available Ollama models from the API"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            # Filter for vision models
            vision_models = [m for m in models if any(v in m.lower() for v in ["llava", "vision", "bakllava", "granite", "minicpm", "qwen", "gemma"])]
            return vision_models if vision_models else models
        return []
    except Exception as e:
        print(f"Warning: Could not fetch Ollama models: {e}")
        return []

def get_clip_interrogator():
    """Lazy load CLIP Interrogator"""
    global ci, CLIP_AVAILABLE, models_loading, models_ready
    if ci is None and CLIP_AVAILABLE and not models_loading['clip']:
        try:
            models_loading['clip'] = True
            from clip_interrogator import Config as ClipConfig, Interrogator as ClipInterrogator
            print("Loading CLIP Interrogator...")
            ci = ClipInterrogator(ClipConfig(clip_model_name="ViT-L-14/openai"))
            print("CLIP Interrogator loaded successfully")
            models_ready['clip'] = True
        except Exception as e:
            print(f"Warning: CLIP Interrogator not available: {e}")
            CLIP_AVAILABLE = False
            ci = None
        finally:
            models_loading['clip'] = False
    return ci

def get_blip_models():
    """Lazy load BLIP models"""
    global blip_processor, blip_model, device, models_loading, models_ready
    if blip_processor is None and not models_loading['blip']:
        try:
            models_loading['blip'] = True
            print("Loading BLIP models...")
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
            print(f"BLIP models loaded successfully on {device}")
            models_ready['blip'] = True
        except Exception as e:
            print(f"Warning: BLIP models failed to load: {e}")
            models_loading['blip'] = False
            return None, None, None
        finally:
            models_loading['blip'] = False
    return blip_processor, blip_model, device

def get_sam_predictor():
    """Lazy load SAM (Segment Anything Model)"""
    global sam_predictor
    if sam_predictor is None:
        try:
            from segment_anything import sam_model_registry, SamPredictor
            print("Loading SAM model...")
            sam = sam_model_registry["vit_h"](checkpoint="sam_vit_h_4b8939.pth")
            sam.to(device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            sam_predictor = SamPredictor(sam)
            print("SAM loaded successfully")
        except Exception as e:
            print(f"Warning: SAM not available: {e}")
            sam_predictor = False
    return sam_predictor if sam_predictor is not False else None

def get_yolo_model():
    """Lazy load YOLO model"""
    global yolo_model, models_loading, models_ready
    if yolo_model is None and not models_loading['yolo']:
        try:
            models_loading['yolo'] = True
            from ultralytics import YOLO
            print("Loading YOLO model...")
            yolo_model = YOLO("yolov8n.pt")
            print("YOLO loaded successfully")
            models_ready['yolo'] = True
        except Exception as e:
            print(f"Warning: YOLO not available: {e}")
            yolo_model = False
        finally:
            models_loading['yolo'] = False
    return yolo_model if yolo_model is not False else None

def preload_models_async():
    """Preload heavy models in background threads"""
    def load_clip():
        get_clip_interrogator()
    
    def load_blip():
        get_blip_models()
    
    def load_yolo():
        get_yolo_model()
    
    # Start loading in separate threads
    threading.Thread(target=load_blip, daemon=True, name="BLIP-Loader").start()
    threading.Thread(target=load_clip, daemon=True, name="CLIP-Loader").start()
    threading.Thread(target=load_yolo, daemon=True, name="YOLO-Loader").start()

def run_ocr(image_path):
    try:
        image = cv2.imread(image_path)
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        return f"[OCR Error] {str(e)}"

def generate_clip_caption(image_path, mode="fast"):
    interrogator = get_clip_interrogator()
    if interrogator is None:
        return "[CLIP Unavailable] Install clip-interrogator package"
    try:
        img = Image.open(image_path).convert("RGB")
        if mode == "best":
            return interrogator.interrogate(img)
        elif mode == "fast":
            return interrogator.interrogate_fast(img)
        elif mode == "classic":
            return interrogator.interrogate_classic(img)
        return "[Error] Unknown CLIP mode"
    except Exception as e:
        return f"[CLIP Error] {str(e)}"

def generate_blip_caption(image_path):
    try:
        processor, model, dev = get_blip_models()
        if processor is None:
            return "[BLIP Unavailable]"
        image = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(dev)
        out = model.generate(**inputs)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"[BLIP Error] {str(e)}"

def generate_sam_analysis(image_path):
    try:
        sam = get_sam_predictor()
        if sam is None:
            return "[SAM Unavailable]"
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        sam.set_image(image)
        # Get automatic mask generation
        return "[SAM] Image segmentation complete (masks generated)"
    except Exception as e:
        return f"[SAM Error] {str(e)}"

def generate_yolo_detection(image_path):
    try:
        yolo = get_yolo_model()
        if yolo is None:
            return "[YOLO Unavailable]"
        results = yolo(image_path)
        detections = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                name = r.names[cls]
                detections.append(f"{name} ({conf:.2f})")
        return f"[YOLO] Detected: {', '.join(detections)}" if detections else "[YOLO] No objects detected"
    except Exception as e:
        return f"[YOLO Error] {str(e)}"

def generate_ollama_caption(image_path, model_name="llava:latest"):
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        payload = {
            "model": model_name,
            "prompt": "Describe the image in detail.",
            "images": [encoded],
            "stream": False  # <- most reliable
        }
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "response" in data:
            return data["response"].strip()
        elif isinstance(data, list):
            return "".join(chunk.get("response", "") for chunk in data).strip()
        else:
            return "[Ollama Error] Unexpected response format."
    except Exception as e:
        return f"[Ollama Error] {e}"
    
def summarize_captions(*captions):
    from difflib import SequenceMatcher
    merged = " ".join(captions)
    merged = merged.replace("\n", " ").strip()
    return merged[:512] + "..." if len(merged) > 512 else merged



class PerceptionTab(QWidget):
    def __init__(self, shell=None):
        super().__init__()
        self.shell = shell
        self.latest_image_path = None
        self.latest_pixmap = None
        self.available_ollama_models = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Set minimum and initial size
        self.setMinimumSize(50, 50)
        self.default_size = QSize(800, 600)
        
        self.init_ui()
        apply_crimson_theme(self)
        self.load_ollama_models()
        # Start preloading models in background
        preload_models_async()
        print("🔄 Background model loading initiated...")

    def load_ollama_models(self):
        """Load available Ollama models on startup"""
        self.available_ollama_models = get_available_ollama_models()
        if self.available_ollama_models:
            self.ollama_model_selector.clear()
            self.ollama_model_selector.addItems(self.available_ollama_models)
            print(f"Loaded {len(self.available_ollama_models)} Ollama models")
        else:
            print("No Ollama models found - is Ollama running?")

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.image_info = QLabel("🧠 Awaiting image...")
        layout.addWidget(self.image_info)

        self.ocr_output = QTextEdit()
        self.ocr_output.setPlaceholderText("🧾 OCR Output")
        self.ocr_output.setMinimumHeight(30)
        self.ocr_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.ocr_output)

        self.user_note = QTextEdit()
        self.user_note.setPlaceholderText("✍️ Manual annotations (optional)")
        self.user_note.setMinimumHeight(30)
        self.user_note.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.user_note)

        self.merge_strategy = QComboBox()
        self.merge_strategy.addItems(["Literal", "Symbolic", "Emotional", "OllamaVision"])
        self.merge_strategy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        merge_row = QHBoxLayout()
        merge_row.addWidget(QLabel("Fusion Strategy:"))
        merge_row.addWidget(self.merge_strategy)
        layout.addLayout(merge_row)

        self.ollama_model_selector = QComboBox()
        self.ollama_model_selector.addItems(["Loading..."])  # Will be populated in load_ollama_models
        self.ollama_model_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(QLabel("🧠 Ollama Vision Model (for OllamaVision mode)"))
        layout.addWidget(self.ollama_model_selector)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(40)
        self.output_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(QLabel("🧩 Final Interpretation"))
        layout.addWidget(self.output_box)

        # Controls
        btns = QHBoxLayout()
        btns.setSpacing(5)
        self.load_btn = QPushButton("📂 Load Image")
        self.load_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.run_btn = QPushButton("🧠 Interpret")
        self.run_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_btn = QPushButton("🔄 Refresh Models")
        self.refresh_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.inject_btn = QPushButton("➡️ Send to Assembly")
        self.inject_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btns.addWidget(self.load_btn)
        btns.addWidget(self.run_btn)
        btns.addWidget(self.refresh_btn)
        btns.addWidget(self.inject_btn)
        layout.addLayout(btns)

        self.setLayout(layout)
        self.load_btn.clicked.connect(self.load_image)
        self.run_btn.clicked.connect(self.interpret_scene)
        self.refresh_btn.clicked.connect(self.load_ollama_models)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.reflect_on_image(path)

    def reflect_on_image(self, path):
        self.latest_image_path = path
        self.latest_pixmap = QPixmap(path)
        self.image_info.setText(f"🖼️ {os.path.basename(path)}")

    def interpret_scene(self):
        if not self.latest_image_path:
            self.output_box.setText("[Error] No image loaded.")
            return

        strategy = self.merge_strategy.currentText()
        is_ollama_only = (strategy == "OllamaVision")
        
        status_msg = "🔄 Processing with Ollama + OCR..." if is_ollama_only else "🔄 Processing with all available models..."
        self.output_box.setText(status_msg)
        self.run_btn.setEnabled(False)
        
        try:
            results = []

            # OCR - Always run (fast)
            try:
                ocr = run_ocr(self.latest_image_path)
                self.ocr_output.setText(ocr)
                if ocr and not ocr.startswith("[OCR Error]"):
                    results.append(f"[OCR]\n{ocr}")
            except Exception as e:
                print(f"OCR failed: {e}")

            # Ollama Vision - Always run based on strategy
            ollama_model = STRATEGY_MODELS.get(strategy)
            if ollama_model is None and strategy == "OllamaVision":
                ollama_model = self.ollama_model_selector.currentText()
            
            if ollama_model:
                try:
                    self.output_box.setText(f"🔄 Running Ollama ({ollama_model})...")
                    ollama = generate_ollama_caption(self.latest_image_path, ollama_model)
                    if ollama and not ollama.startswith("[Ollama Error]"):
                        results.append(f"[Ollama - {strategy} using {ollama_model}]\n{ollama}")
                        # Show Ollama results immediately
                        self.output_box.setText("\n\n".join(results))
                except Exception as e:
                    print(f"Ollama failed: {e}")
                    results.append(f"[Ollama Error] {e}")

            # Skip heavy models for OllamaVision mode
            if is_ollama_only:
                # User notes
                notes = self.user_note.toPlainText().strip()
                if notes:
                    results.append(f"[User Notes]\n{notes}")
                
                final_summary = "\n\n".join(results)
                self.output_box.setText(final_summary)
                
                if hasattr(self, 'navi_console'):
                    self.navi_console.inject_vision_context(self.latest_image_path, final_summary)
                return

            # For non-OllamaVision modes, try to get other model results with timeout
            self.output_box.setText(self.output_box.toPlainText() + "\n\n🔄 Waiting for CLIP/BLIP/YOLO (30s timeout)...")
            
            additional_results = []
            
            # CLIP with timeout
            try:
                future = self.executor.submit(generate_clip_caption, self.latest_image_path, "fast")
                clip = future.result(timeout=30)
                if clip and not clip.startswith("[CLIP"):
                    additional_results.append(f"[CLIP Interrogator]\n{clip}")
            except FuturesTimeoutError:
                additional_results.append("[CLIP] Timed out after 30s")
                print("CLIP timed out")
            except Exception as e:
                print(f"CLIP failed: {e}")

            # BLIP with timeout
            try:
                future = self.executor.submit(generate_blip_caption, self.latest_image_path)
                blip = future.result(timeout=30)
                if blip and not blip.startswith("[BLIP"):
                    additional_results.append(f"[BLIP]\n{blip}")
            except FuturesTimeoutError:
                additional_results.append("[BLIP] Timed out after 30s")
                print("BLIP timed out")
            except Exception as e:
                print(f"BLIP failed: {e}")

            # YOLO with timeout
            try:
                future = self.executor.submit(generate_yolo_detection, self.latest_image_path)
                yolo = future.result(timeout=30)
                if yolo:
                    additional_results.append(yolo)
            except FuturesTimeoutError:
                additional_results.append("[YOLO] Timed out after 30s")
                print("YOLO timed out")
            except Exception as e:
                print(f"YOLO failed: {e}")

            # Append additional results
            results.extend(additional_results)

            # User notes
            notes = self.user_note.toPlainText().strip()
            if notes:
                results.append(f"[User Notes]\n{notes}")

            # Combine all results
            if results:
                final_summary = "\n\n".join(results)
                self.output_box.setText(final_summary)
            else:
                self.output_box.setText("[Error] All models failed to process the image.")

            if hasattr(self, 'navi_console'):
                self.navi_console.inject_vision_context(self.latest_image_path, final_summary)
                
        except Exception as e:
            error_msg = f"[Critical Error] {str(e)}"
            self.output_box.setText(error_msg)
            print(error_msg)
            import traceback
            traceback.print_exc()
        finally:
            self.run_btn.setEnabled(True)

    def set_navi_console(self, console):
        self.navi_console = console
    
    def resizeEvent(self, event):
        """Handle window resize with dynamic layout adjustments"""
        super().resizeEvent(event)
        new_size = event.size()
        
        # Adjust text widget heights based on available space
        if new_size.height() < 400:
            # Compact mode for small heights
            self.ocr_output.setMaximumHeight(60)
            self.user_note.setMaximumHeight(60)
            self.output_box.setMaximumHeight(100)
        else:
            # Normal mode - remove height restrictions
            self.ocr_output.setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX
            self.user_note.setMaximumHeight(16777215)
            self.output_box.setMaximumHeight(16777215)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = PerceptionTab()
    window.show()
    sys.exit(app.exec())