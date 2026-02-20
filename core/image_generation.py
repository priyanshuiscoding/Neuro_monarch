import os
import time
import base64
from io import BytesIO
from pathlib import Path
from contextlib import contextmanager

import requests
from PIL import Image, ImageStat
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

HF_DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
NVIDIA_DEFAULT_ENDPOINT = "https://ai.api.nvidia.com/v1/genai/{model}"
NVIDIA_DEFAULT_MODEL = "stabilityai/stable-diffusion-xl"


@contextmanager
def _proxy_env_disabled(disable: bool):
    if not disable:
        yield
        return

    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    previous = {k: os.environ.get(k) for k in proxy_keys}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value


def _extract_base64_image(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0] or {}
        b64 = first.get("b64_json") or first.get("base64")
        if b64:
            return b64

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        first = artifacts[0] or {}
        finish_reason = first.get("finishReason") or first.get("finish_reason")
        if isinstance(finish_reason, str) and "FILTER" in finish_reason.upper():
            raise RuntimeError(f"NVIDIA generation filtered the prompt ({finish_reason}).")
        b64 = first.get("base64")
        if b64:
            return b64

    image = payload.get("image")
    if isinstance(image, str) and image.strip():
        return image

    raise RuntimeError("NVIDIA response did not include a base64 image payload.")


def _resolve_nvidia_endpoint(endpoint_template: str, model: str) -> str:
    if "{model}" in endpoint_template:
        return endpoint_template.format(model=model)
    return endpoint_template


def _is_blank_image(image: Image.Image) -> bool:
    rgb = image.convert("RGB")
    extrema = rgb.getextrema()
    # Pure black/flat image check.
    if all(lo == hi for lo, hi in extrema):
        return True
    stats = ImageStat.Stat(rgb)
    return max(stats.stddev) < 2.0


def _save_nvidia_response(response: requests.Response, output: Path) -> Path:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "image/" in content_type:
        image = Image.open(BytesIO(response.content)).convert("RGBA")
        if _is_blank_image(image):
            raise RuntimeError("NVIDIA returned a blank image; try a different prompt/model.")
        image.save(output)
        return output

    body = response.json()
    b64_image = _extract_base64_image(body)
    image_bytes = base64.b64decode(b64_image)
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    if _is_blank_image(image):
        raise RuntimeError("NVIDIA returned a blank image; try a different prompt/model.")
    image.save(output)
    return output


def _generate_with_nvidia(prompt: str, output: Path, retries: int, negative_prompt: str | None = None) -> Path:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("Set NVIDIA_API_KEY in your environment.")

    endpoint_template = os.getenv("NVIDIA_IMAGE_ENDPOINT", NVIDIA_DEFAULT_ENDPOINT)
    model = os.getenv("NVIDIA_IMAGE_MODEL", NVIDIA_DEFAULT_MODEL)
    endpoint = _resolve_nvidia_endpoint(endpoint_template, model)
    width = int(os.getenv("NVIDIA_IMAGE_WIDTH", "1024"))
    height = int(os.getenv("NVIDIA_IMAGE_HEIGHT", "1024"))
    steps = int(os.getenv("NVIDIA_IMAGE_STEPS", "30"))
    guidance = float(os.getenv("NVIDIA_IMAGE_GUIDANCE", "7.0"))
    n_prompt = negative_prompt or os.getenv(
        "NVIDIA_IMAGE_NEGATIVE_PROMPT",
        "low quality, blurry, distorted, watermark, text",
    )

    payloads = [
        {
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
                {"text": n_prompt, "weight": -1.0},
            ],
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": guidance,
            "samples": 1,
        },
        {
            "text_prompts": [{"text": prompt, "weight": 1.0}],
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": guidance,
            "samples": 1,
        },
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, image/*",
    }
    use_system_proxy = os.getenv("NVIDIA_USE_SYSTEM_PROXY", "false").lower() in {"1", "true", "yes"}
    disable_proxy_env = not use_system_proxy

    last_error = "Unknown NVIDIA image generation error"
    for _ in range(max(retries, 1)):
        try:
            with _proxy_env_disabled(disable_proxy_env):
                for payload in payloads:
                    response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
                    if response.status_code in {429, 503}:
                        last_error = f"{response.status_code} {response.text}"
                        time.sleep(2)
                        continue
                    if response.status_code == 400:
                        last_error = f"{response.status_code} {response.text}"
                        continue
                    response.raise_for_status()
                    return _save_nvidia_response(response, output)
            time.sleep(1)
        except requests.HTTPError as exc:
            last_error = f"{exc} | body={getattr(exc.response, 'text', '')}"
            break
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
            continue

    raise RuntimeError(last_error)


def _generate_with_huggingface(
    prompt: str, output: Path, retries: int, negative_prompt: str | None = None
) -> Path:
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError("Set HUGGINGFACE_API_KEY in your environment.")

    model = os.getenv("HF_IMAGE_MODEL", HF_DEFAULT_MODEL)
    width = int(os.getenv("HF_IMAGE_WIDTH", "1024"))
    height = int(os.getenv("HF_IMAGE_HEIGHT", "1024"))
    steps = int(os.getenv("HF_IMAGE_STEPS", "50"))
    guidance = float(os.getenv("HF_IMAGE_GUIDANCE", "8.0"))

    last_error = "Unknown Hugging Face error"
    use_system_proxy = os.getenv("HF_USE_SYSTEM_PROXY", "false").lower() in {"1", "true", "yes"}
    disable_proxy_env = not use_system_proxy
    proxies = None if use_system_proxy else {"http": "", "https": ""}

    n_prompt = negative_prompt or "low quality, blurry, distorted, watermark, text"
    for _ in range(max(retries, 1)):
        try:
            with _proxy_env_disabled(disable_proxy_env):
                client = InferenceClient(
                    provider="hf-inference",
                    api_key=api_key,
                    model=model,
                    timeout=120,
                    proxies=proxies,
                )
                image = client.text_to_image(
                    prompt=prompt,
                    negative_prompt=n_prompt,
                    width=width,
                    height=height,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                )
            image.save(output)
            return output
        except HfHubHTTPError as exc:
            last_error = str(exc)
            if exc.response is not None and exc.response.status_code in {429, 503}:
                time.sleep(2)
                continue
            break
        except Exception as exc:
            last_error = (
                f"Network error while contacting Hugging Face: {exc}. "
                "If you require a corporate proxy, set HF_USE_SYSTEM_PROXY=true."
            )
            time.sleep(2)
            continue

    raise RuntimeError(last_error)


def generate_image_from_prompt(
    prompt: str,
    output_path: str | Path,
    retries: int = 3,
    negative_prompt: str | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    backend = os.getenv("IMAGE_BACKEND", "").strip().lower()
    has_nvidia = bool(os.getenv("NVIDIA_API_KEY"))
    has_hf = bool(os.getenv("HUGGINGFACE_API_KEY"))

    if backend in {"nvidia", "nv"}:
        return _generate_with_nvidia(
            prompt=prompt, output=output, retries=retries, negative_prompt=negative_prompt
        )
    if backend in {"huggingface", "hf"}:
        return _generate_with_huggingface(
            prompt=prompt, output=output, retries=retries, negative_prompt=negative_prompt
        )
    if has_nvidia:
        return _generate_with_nvidia(
            prompt=prompt, output=output, retries=retries, negative_prompt=negative_prompt
        )
    if has_hf:
        return _generate_with_huggingface(
            prompt=prompt, output=output, retries=retries, negative_prompt=negative_prompt
        )

    raise RuntimeError(
        "No image backend key found. Set NVIDIA_API_KEY (preferred) or HUGGINGFACE_API_KEY."
    )
