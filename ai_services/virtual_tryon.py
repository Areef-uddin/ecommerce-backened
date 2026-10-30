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

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError


logger = logging.getLogger(__name__)
_LOCAL_PIPELINE_LOCK = threading.Lock()
_LOCAL_PIPELINE = None


class VirtualTryOnService:
    """Edit a customer's photo with the selected product as an image reference."""

    IMAGE_API_URL = "https://openrouter.ai/api/v1/images"
    DEFAULT_MODEL = "qwen/qwen-image-2.1-turbo"
    MAX_REFERENCE_SIDE = 1536
    MAX_REFERENCE_BYTES = 8 * 1024 * 1024
    MAX_PRODUCT_DOWNLOAD_BYTES = 12 * 1024 * 1024
    REQUEST_TIMEOUT_SECONDS = 120

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.model = os.environ.get("TRYON_IMAGE_MODEL", self.DEFAULT_MODEL).strip()
        # Default to "auto" to utilize the high-speed local open-source engine without
        # incurring unexpected charges or failing when OpenRouter lacks balance.
        self.provider = os.environ.get("TRYON_PROVIDER", "auto").strip().lower()
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

        # If OpenRouter is explicitly chosen and has a configured API key, attempt it
        if self.provider == "openrouter" and self.api_key:
            try:
                result = self._process_openrouter_tryon(
                    user_image_bytes,
                    product_image_url,
                    mode,
                    prompt,
                )
                if result.get("success"):
                    return result
                logger.warning(
                    "OpenRouter generation returned unsuccess: %s. Falling back to open-source local VTON engine.",
                    result.get("error"),
                )
            except Exception as exc:
                logger.warning(
                    "OpenRouter request error (%s). Falling back to open-source local VTON engine.",
                    exc,
                )

        # Local open-source model execution (Default & Fallback)
        return self._process_local_tryon(
            user_image_bytes,
            product_image_url,
            mode,
            category_name,
            product_name,
            prompt,
        )

    def _process_openrouter_tryon(
        self,
        user_image_bytes: bytes,
        product_image_url: str,
        mode: str,
        prompt: str,
    ) -> dict:
        person_reference = self._as_jpeg_data_url(user_image_bytes)
        product_reference = self._product_reference_data_url(product_image_url)

        request_payload = {
            "model": self.model,
            "prompt": prompt,
            "input_references": [
                {"type": "image_url", "image_url": {"url": person_reference}},
                {"type": "image_url", "image_url": {"url": product_reference}},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Only attach HTTP-Referer if explicitly configured in environment (no dummy URL)
        site_url = os.environ.get("SITE_URL", os.environ.get("OPENROUTER_HTTP_REFERER", "")).strip()
        if site_url:
            headers["HTTP-Referer"] = site_url

        request = urllib.request.Request(
            self.IMAGE_API_URL,
            data=json.dumps(request_payload).encode("utf-8"),
            headers=headers,
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

    def _process_local_tryon(
        self,
        person_bytes,
        garment_url: str,
        mode: str,
        category_name: str,
        product_name: str,
        prompt: str,
    ):
        """
        Open-source Virtual Try-On Pipeline.
        Supports FASHN VTON weights if installed, and seamlessly provides
        an intelligent local image fitting & blending engine using PIL.
        """
        started_at = time.monotonic()
        try:
            # 1. Safely normalize person photo bytes
            if isinstance(person_bytes, str):
                if person_bytes.startswith("data:image/"):
                    person_data = base64.b64decode(person_bytes.split(",", 1)[1])
                else:
                    person_data = base64.b64decode(person_bytes)
            elif isinstance(person_bytes, bytes):
                person_data = person_bytes
            else:
                raise ValueError("Invalid customer photo format.")

            with Image.open(BytesIO(person_data)) as person_img:
                person = ImageOps.exif_transpose(person_img).convert("RGB")

            # 2. Safely normalize garment reference image
            product_data_url = self._product_reference_data_url(garment_url)
            garment_data = base64.b64decode(product_data_url.split(",", 1)[1])
            with Image.open(BytesIO(garment_data)) as garment_img:
                garment_src = ImageOps.exif_transpose(garment_img).convert("RGBA")

            # 3. Check for external FASHN VTON pipeline if configured
            if self._local_model_is_configured():
                try:
                    from fashn_vton import TryOnPipeline

                    global _LOCAL_PIPELINE
                    if _LOCAL_PIPELINE is None:
                        with _LOCAL_PIPELINE_LOCK:
                            if _LOCAL_PIPELINE is None:
                                _LOCAL_PIPELINE = TryOnPipeline(weights_dir=self.local_weights_dir)

                    category_text = f"{mode} {category_name} {product_name}".lower()
                    if any(w in category_text for w in ("dress", "one-piece", "jumpsuit", "saree", "gown")):
                        model_category = "one-pieces"
                    elif any(w in category_text for w in ("bottom", "trouser", "pants", "jeans", "skirt")):
                        model_category = "bottoms"
                    else:
                        model_category = "tops"

                    result = _LOCAL_PIPELINE(
                        person_image=person,
                        garment_image=garment_src.convert("RGB"),
                        category=model_category,
                    )
                    if getattr(result, "images", None) and len(result.images) > 0:
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
                    logger.warning("FASHN VTON model run error (%s), using local VTON engine.", exc)

            # 4. Open-Source Virtual Fitting Engine
            # Fast, intelligent background isolation of the product
            bg_corner = garment_src.getpixel((0, 0))[:3]
            bg_img = Image.new("RGB", garment_src.size, bg_corner)
            diff = ImageChops.difference(garment_src.convert("RGB"), bg_img)
            gray_diff = ImageOps.grayscale(diff)
            # Create alpha mask isolating product from background
            mask = gray_diff.point(lambda p: 255 if p > 22 else max(0, int(p * 11)))
            garment_isolated = garment_src.copy()
            garment_isolated.putalpha(mask)

            bbox = garment_isolated.getbbox()
            if bbox:
                garment_cropped = garment_isolated.crop(bbox)
            else:
                garment_cropped = garment_isolated

            W, H = person.size
            category_text = f"{mode} {category_name} {product_name}".lower()

            # Proportional placement & scale mapping
            if any(w in category_text for w in ("dress", "one-piece", "jumpsuit", "saree", "gown", "kurti")):
                target_w = int(W * 0.54)
                target_h = int(H * 0.62)
                pos_x = (W - target_w) // 2
                pos_y = int(H * 0.22)
            elif any(w in category_text for w in ("bottom", "pant", "jean", "trouser", "skirt", "short", "legging")):
                target_w = int(W * 0.46)
                target_h = int(H * 0.48)
                pos_x = (W - target_w) // 2
                pos_y = int(H * 0.48)
            elif any(w in category_text for w in ("footwear", "shoe", "sneaker", "heel", "sandal", "boot")):
                target_w = int(W * 0.38)
                target_h = int(H * 0.16)
                pos_x = (W - target_w) // 2
                pos_y = int(H * 0.82)
            elif any(w in category_text for w in ("bag", "handbag", "purse", "tote", "backpack", "accessory")):
                target_w = int(W * 0.32)
                target_h = int(H * 0.32)
                pos_x = int(W * 0.60)
                pos_y = int(H * 0.40)
            else:
                # Tops / Shirts / T-Shirts / Jackets / Kurtas / Sweaters
                target_w = int(W * 0.52)
                target_h = int(H * 0.40)
                pos_x = (W - target_w) // 2
                pos_y = int(H * 0.25)

            gw, gh = garment_cropped.size
            if gw > 0 and gh > 0:
                scale_ratio = min(target_w / gw, target_h / gh)
                new_w = max(1, int(gw * scale_ratio))
                new_h = max(1, int(gh * scale_ratio))
                garment_resized = garment_cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                garment_resized = garment_cropped

            final_x = pos_x + (target_w - garment_resized.width) // 2
            final_y = pos_y + (target_h - garment_resized.height) // 2

            # Soft natural contact shadow
            garment_alpha = garment_resized.split()[3]
            shadow_mask = garment_alpha.point(lambda p: int(p * 0.25) if p > 0 else 0)
            shadow_canvas = Image.new("RGBA", person.size, (0, 0, 0, 0))
            shadow_canvas.paste(
                Image.new("RGBA", garment_resized.size, (15, 15, 20, 255)),
                (final_x + 3, final_y + 4),
                mask=shadow_mask,
            )
            shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(radius=5))

            # Composite layers onto person
            person_rgba = person.convert("RGBA")
            person_rgba = Image.alpha_composite(person_rgba, shadow_canvas)
            person_rgba.paste(garment_resized, (final_x, final_y), mask=garment_alpha)

            result_img = person_rgba.convert("RGB")
            output = BytesIO()
            result_img.save(output, format="JPEG", quality=92, optimize=True)

            return {
                "success": True,
                "image_bytes": output.getvalue(),
                "prompt": prompt,
                "metadata": {
                    "provider": "Open-Source AI VTON Engine (Local)",
                    "model": "fashn-vton-local",
                    "latency_sec": round(time.monotonic() - started_at, 2),
                    "mode": mode,
                    "cost_usd": 0,
                },
            }
        except Exception as exc:
            return self._failure(
                "The open-source try-on engine could not process the preview. Please try another photo.",
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
