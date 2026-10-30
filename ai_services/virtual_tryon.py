import base64
import functools
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


logger = logging.getLogger(__name__)
_LOCAL_PIPELINE_LOCK = threading.Lock()
_LOCAL_PIPELINE = None


class VirtualTryOnService:
    """Edit a customer's photo with the selected product as an image reference."""

    IMAGE_API_URL = "https://openrouter.ai/api/v1/images"
    # Reference-image editor with much lower per-image cost than the old default.
    DEFAULT_MODEL = "qwen/qwen-image-2.1-turbo"
    MAX_REFERENCE_SIDE = 1536
    MAX_REFERENCE_BYTES = 8 * 1024 * 1024
    MAX_PRODUCT_DOWNLOAD_BYTES = 12 * 1024 * 1024
    REQUEST_TIMEOUT_SECONDS = 120

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.model = os.environ.get("TRYON_IMAGE_MODEL", self.DEFAULT_MODEL).strip()
        # Prefer offline inference by default so a configured API key is never
        # charged unexpectedly. Set TRYON_PROVIDER=openrouter to opt in.
        self.provider = os.environ.get("TRYON_PROVIDER", "local").strip().lower()
        self.local_weights_dir = os.environ.get("FASHN_VTON_WEIGHTS_DIR", "").strip()

    def get_category_prompt(
        self,
        mode: str,
        product_name: str,
        category_name: str,
        product_description: str = "",
    ) -> str:
        mode_lower = (mode or "clothing").lower()
        category_lower = (category_name or "").lower()
        details = (product_description or "").strip()

        preserve_person = (
            "REFERENCE 1 is the customer's photo and is the base image. Preserve this exact person: "
            "face, identity, age, skin tone, hairstyle, body shape, pose, expression, and gender presentation. "
            "Keep the same camera angle, crop, lighting, and background. Do not replace the person, add another person, "
            "beautify their face, or change anything unrelated to the product. REFERENCE 2 is the exact product to use. "
            "Use its real colour, silhouette, material, pattern, trim, and hardware; do not invent a substitute. "
            "Make one natural, photorealistic customer preview with realistic fit, perspective, shadows, and occlusion."
        )

        if any(word in mode_lower or word in category_lower for word in ("furniture", "furnishing", "space", "home", "decor")):
            action = (
                f"Place the exact selected home product, {product_name}, into the customer's room photo. "
                "Set it on a physically plausible surface or floor, at a believable scale and perspective, with contact shadow. "
                "Preserve the room layout and all existing furniture."
            )
        elif any(word in mode_lower or word in category_lower for word in ("footwear", "foot", "shoe", "sneaker", "heel")):
            action = (
                f"Show the selected footwear, {product_name}, being worn on the customer's visible feet. "
                "Fit each shoe to the correct foot and angle, preserve the legs and pose, and match the ground perspective. "
                "If the feet are not visible, do not fabricate a body or feet; return a natural product preview beside the person."
            )
        elif any(word in mode_lower or word in category_lower for word in ("accessory", "accessories", "bag", "handbag", "purse")):
            action = (
                f"Add the exact accessory, {product_name}, to the customer in a natural way. "
                "For a bag or handbag, inspect the customer's pose and visible hands, then place it in the nearest free hand "
                "with a believable grip and strap, or over the shoulder if that is more natural. Keep the bag at realistic scale; "
                "show hand-to-handle contact, correct perspective, and a soft contact shadow. Do not cover the face. "
                "For a watch or jewellery, place it on the appropriate visible wrist or body area."
            )
        else:
            action = (
                f"Dress the customer in the exact selected garment, {product_name}. Fit it to the person's visible body and pose, "
                "preserving their identity and proportions. Adapt the garment naturally to the person shown; never infer or change "
                "the person's gender from the product category. Reproduce the garment's real cut, neckline, sleeves, length, "
                "pattern, colour, and fabric from REFERENCE 2. Do not paste a flat product photo over the person's face or body."
            )

        product_details = f" Product details: {details}" if details else ""
        return f"{preserve_person} {action}{product_details} Return only the finished edited image."

    def process_tryon(
        self,
        user_image_path: str = None,
        product_image_url: str = "",
        mode: str = "clothing",
        product_name: str = "",
        category_name: str = "",
        product_description: str = "",
        user_image_bytes: bytes = None,
    ) -> dict:
        prompt = self.get_category_prompt(mode, product_name, category_name, product_description)

        if not user_image_bytes and user_image_path:
            try:
                with open(user_image_path, "rb") as photo_file:
                    user_image_bytes = photo_file.read(self.MAX_REFERENCE_BYTES + 1)
            except OSError as exc:
                return self._failure("Could not read the customer's photo.", prompt, exc)

        if not user_image_bytes:
            return {"success": False, "error": "Upload a clear photo before starting the try-on.", "prompt": prompt}
        if len(user_image_bytes) > self.MAX_REFERENCE_BYTES:
            return {"success": False, "error": "The customer's photo is too large. Upload a photo under 10MB.", "prompt": prompt}
        local_model_ready = self._local_model_is_configured()
        use_local_model = self.provider == "local" or (
            self.provider == "auto" and local_model_ready
        )
        if use_local_model:
            if not local_model_ready:
                return {
                    "success": False,
                    "error": (
                        "The free local FASHN VTON model is not installed. Install the optional "
                        "local try-on dependencies, download its weights, and set "
                        "FASHN_VTON_WEIGHTS_DIR. No API key is required."
                    ),
                    "prompt": prompt,
                }
            return self._process_local_tryon(
                user_image_bytes,
                product_image_url,
                mode,
                category_name,
                product_name,
                prompt,
            )

        if not self.api_key:
            return {
                "success": False,
                "error": (
                    "No image model is configured. For free, key-free clothing try-on, install the "
                    "FASHN VTON local model and set FASHN_VTON_WEIGHTS_DIR. For footwear, accessories, "
                    "or room previews, configure an image-editing provider."
                ),
                "prompt": prompt,
            }

        try:
            person_reference = self._as_jpeg_data_url(user_image_bytes)
            product_reference = self._product_reference_data_url(product_image_url)
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            return self._failure("One of the reference photos could not be read. Try a clear JPG or PNG image.", prompt, exc)

        request_payload = {
            "model": self.model,
            "prompt": prompt,
            "input_references": [
                {"type": "image_url", "image_url": {"url": person_reference}},
                {"type": "image_url", "image_url": {"url": product_reference}},
            ],
        }
        request = urllib.request.Request(
            self.IMAGE_API_URL,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://stylehub.com",
                "X-Title": "StyleHub Virtual Try-On",
            },
            method="POST",
        )

        started_at = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            response_text = exc.read(16_384).decode("utf-8", errors="replace")
            return self._failure(self._provider_error(exc.code, response_text), prompt, exc)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return self._failure(
                "The AI image service could not be reached. Please retry in a moment.", prompt, exc
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return self._failure("The AI image service returned an unreadable response. Please retry.", prompt, exc)

        try:
            image_data = response_data.get("data") or []
            if not image_data:
                raise ValueError("The AI image service returned no generated image.")
            image_bytes = self._decode_generated_image(image_data[0])
            image_bytes = self._normalize_generated_image(image_bytes)
        except (KeyError, TypeError, ValueError, OSError, UnidentifiedImageError) as exc:
            return self._failure(
                "The AI image service did not return a usable preview. Please try another photo.", prompt, exc
            )

        usage = response_data.get("usage") or {}
        return {
            "success": True,
            "image_bytes": image_bytes,
            "prompt": prompt,
            "metadata": {
                "provider": "OpenRouter Image API",
                "model": self.model,
                "latency_sec": round(time.monotonic() - started_at, 2),
                "mode": mode,
                "cost_usd": usage.get("cost"),
            },
        }

    def _local_model_is_configured(self):
        if not self.local_weights_dir:
            return False
        return os.path.isdir(self.local_weights_dir) and any(
            name.endswith((".safetensors", ".pt", ".pth"))
            for name in os.listdir(self.local_weights_dir)
        )

    def _process_local_tryon(self, person_bytes, garment_url, mode, category_name, product_name, prompt):
        if any(word in f"{mode} {category_name}".lower() for word in (
            "footwear", "shoe", "sneaker", "heel", "accessory", "accessories",
            "bag", "handbag", "purse", "furniture", "space", "home",
        )):
            return {
                "success": False,
                "error": (
                    "The free local FASHN VTON model supports clothing try-on only. "
                    "Choose clothing, or configure an image-editing provider for this product type."
                ),
                "prompt": prompt,
            }

        try:
            from fashn_vton import TryOnPipeline

            product_data_url = self._product_reference_data_url(garment_url)
            person_data = base64.b64decode(person_bytes)
            garment_data = base64.b64decode(product_data_url.split(",", 1)[1])
            with Image.open(BytesIO(person_data)) as person_image:
                person = ImageOps.exif_transpose(person_image).convert("RGB")
            with Image.open(BytesIO(garment_data)) as garment_image:
                garment = ImageOps.exif_transpose(garment_image).convert("RGB")

            global _LOCAL_PIPELINE
            if _LOCAL_PIPELINE is None:
                with _LOCAL_PIPELINE_LOCK:
                    if _LOCAL_PIPELINE is None:
                        _LOCAL_PIPELINE = TryOnPipeline(weights_dir=self.local_weights_dir)

            category_text = f"{mode} {category_name} {product_name}".lower()
            if any(word in category_text for word in ("dress", "one-piece", "jumpsuit")):
                model_category = "one-pieces"
            elif any(word in category_text for word in ("bottom", "trouser", "pants", "jeans", "skirt")):
                model_category = "bottoms"
            else:
                model_category = "tops"

            started_at = time.monotonic()
            result = _LOCAL_PIPELINE(
                person_image=person,
                garment_image=garment,
                category=model_category,
            )
            if not getattr(result, "images", None):
                raise ValueError("The local model did not return an image.")
            output = BytesIO()
            result.images[0].convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
            return {
                "success": True,
                "image_bytes": output.getvalue(),
                "prompt": prompt,
                "metadata": {
                    "provider": "FASHN VTON local open-source model",
                    "model": "fashn-vton-1.5",
                    "latency_sec": round(time.monotonic() - started_at, 2),
                    "mode": mode,
                    "cost_usd": 0,
                },
            }
        except Exception as exc:
            return self._failure(
                "The local FASHN VTON model could not generate a preview. Check its weights, dependencies, and available memory.",
                prompt,
                exc,
            )

    def _product_reference_data_url(self, image_url: str) -> str:
        if not image_url:
            raise ValueError("The selected product has no reference image.")

        if image_url.startswith("data:image/"):
            encoded = image_url.split(",", 1)[-1]
            image_bytes = base64.b64decode(encoded, validate=True)
        elif image_url.startswith(("https://", "http://")):
            request = urllib.request.Request(image_url, headers={"User-Agent": "StyleHub-TryOn/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                image_bytes = response.read(self.MAX_PRODUCT_DOWNLOAD_BYTES + 1)
        else:
            raise ValueError("The selected product image URL is invalid.")

        if not image_bytes or len(image_bytes) > self.MAX_PRODUCT_DOWNLOAD_BYTES:
            raise ValueError("The selected product photo is empty or too large.")
        return self._as_jpeg_data_url(image_bytes)

    def _as_jpeg_data_url(self, image_bytes: bytes) -> str:
        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((self.MAX_REFERENCE_SIDE, self.MAX_REFERENCE_SIDE), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)

        normalized = buffer.getvalue()
        if len(normalized) > self.MAX_REFERENCE_BYTES:
            raise ValueError("A reference photo is too large after compression.")
        encoded = base64.b64encode(normalized).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def _decode_generated_image(item: dict) -> bytes:
        if not isinstance(item, dict):
            raise TypeError("The generated image record is invalid.")

        encoded = item.get("b64_json")
        if encoded:
            return base64.b64decode(encoded, validate=True)

        image_url = item.get("url")
        if isinstance(image_url, str) and image_url.startswith("data:image/"):
            return base64.b64decode(image_url.split(",", 1)[1], validate=True)

        raise ValueError("The AI response did not contain image bytes.")

    @staticmethod
    def _normalize_generated_image(image_bytes: bytes) -> bytes:
        if not image_bytes:
            raise ValueError("The generated image is empty.")
        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue()

    @staticmethod
    def _provider_error(status_code: int, response_text: str) -> str:
        try:
            payload = json.loads(response_text)
            error = payload.get("error") or payload.get("detail") or payload
            if isinstance(error, dict):
                message = error.get("message") or error.get("detail") or str(error)
            else:
                message = str(error)
        except (json.JSONDecodeError, TypeError):
            message = response_text.strip()

        message = " ".join(message.split())[:400]
        if status_code == 402:
            return (
                "OpenRouter currently has no free image-editing models. This account also needs a balance above $1 "
                "before image requests; add credits or configure another image provider, then retry. "
                "The selected low-cost model is Qwen Image 2.1 Turbo."
            )
        if status_code == 429:
            return "The AI image service is busy. Please wait a moment and retry."
        if "image" in message.lower() and ("reference" in message.lower() or "match" in message.lower()):
            return "The AI model could not match the two reference photos. Try a clearer person photo and product photo."
        return f"AI image generation failed (HTTP {status_code}). {message or 'Please retry with another photo.'}"

    @staticmethod
    def _failure(message: str, prompt: str, exc: Exception) -> dict:
        logger.warning("Virtual try-on failed: %s", exc)
        return {"success": False, "error": message, "prompt": prompt}
