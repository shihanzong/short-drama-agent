"""ComfyUI Client - REST + WebSocket interface for image/video generation."""

import os
import json
import time
import httpx
from typing import Optional, List, Dict, Any
from tqdm import tqdm


class ComfyUIClient:
    """Client for interacting with ComfyUI via REST API and WebSocket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: int = 900):
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def health_check(self) -> bool:
        """Check if ComfyUI server is running."""
        try:
            resp = self._client.get("/system_stats")
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict]:
        """List available checkpoints/models."""
        try:
            resp = self._client.get("/experiment/models/checkpoints")
            if resp.status_code == 200:
                data = resp.json()
                return [{"name": m} for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def list_nodes(self) -> Dict[str, Any]:
        """List available custom nodes."""
        try:
            resp = self._client.get("/object_info")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def submit_workflow(
        self,
        workflow: Dict[str, Any],
        inputs: Optional[Dict[str, Any]] = None,
        input_images: Optional[Dict[str, str]] = None,
        prompt_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a workflow for execution.

        Args:
            workflow: API-format workflow JSON with nodes.
            inputs: Parameter overrides (prompt, seed, steps, cfg, etc.).
            input_images: Mapping of param_name -> local file path for uploads.
            prompt_id: Optional client_id for WebSocket tracking.

        Returns:
            Dict with prompt_id, status, and output files.
        """
        client_id = prompt_id or str(int(time.time() * 1000))

        # Upload images if provided
        if input_images:
            for param_name, file_path in input_images.items():
                self._upload_image(file_path, param_name)

        # Inject inputs into workflow
        processed_workflow = self._inject_inputs(workflow, inputs or {})

        # Submit
        resp = self._client.post(
            "/prompt",
            json={"prompt": processed_workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        result = resp.json()
        prompt_id = result.get("prompt_id")

        # Monitor via REST polling (simpler than WS for most cases)
        outputs = self._monitor_completion(prompt_id, client_id)

        return {
            "prompt_id": prompt_id,
            "status": "completed" if outputs else "failed",
            "outputs": outputs,
        }

    def _upload_image(self, file_path: str, param_name: str):
        """Upload an image for img2img workflows."""
        if not os.path.exists(file_path):
            return
        with open(file_path, "rb") as f:
            resp = self._client.post(
                "/upload/image",
                files={
                    "image": (os.path.basename(file_path), f, "image/png"),
                },
                data={"type": "input", "overwrite": "true"},
            )

    def _inject_inputs(self, workflow: Dict, inputs: Dict) -> Dict:
        """Inject user inputs into workflow nodes by matching parameter names."""
        import copy
        wf = copy.deepcopy(workflow)
        for param_name, value in inputs.items():
            # Search all nodes for matching parameter names
            if "nodes" not in wf:
                continue
            for node in wf["nodes"]:
                inputs_data = node.get("inputs", {})
                if param_name in inputs_data:
                    node["inputs"][param_name] = value
        return wf

    def _monitor_completion(self, prompt_id: str, client_id: str, poll_interval: float = 2.0) -> List[str]:
        """Poll /history until prompt completes, return output file paths."""
        while True:
            try:
                resp = self._client.get(f"/history/{prompt_id}")
                resp.raise_for_status()
                history = resp.json()
                if prompt_id in history:
                    # Done
                    outputs = []
                    for node_id, node_result in history[prompt_id].get("outputs", {}).items():
                        for img_key in ["images", "gifs"]:
                            if img_key in node_result:
                                for img_info in node_result[img_key]:
                                    filename = img_info.get("filename", "")
                                    subfolder = img_info.get("subfolder", "")
                                    img_type = img_info.get("type", "")
                                    url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={img_type}"
                                    outputs.append(url)
                    return outputs
            except Exception:
                pass
            time.sleep(poll_interval)

    def generate_from_prompt(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = "",
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = -1,
        width: int = 576,
        height: int = 1024,
        workflow_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        """Convenience method: load a workflow, inject params, run, download."""
        if workflow_path and os.path.exists(workflow_path):
            with open(workflow_path, "r") as f:
                workflow = json.load(f)
        else:
            # Minimal text2img workflow
            workflow = self._create_minimal_txt2img(
                model=model, steps=steps, cfg=cfg, seed=seed,
                width=width, height=height,
            )

        inputs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "cfg": cfg,
            "seed": seed,
            "width": width,
            "height": height,
        }

        result = self.submit_workflow(workflow=workflow, inputs=inputs)

        # Download output images
        downloaded = []
        if result.get("outputs"):
            for url in result["outputs"]:
                out_path = self._download_image(url, output_dir)
                if out_path:
                    downloaded.append(out_path)

        return downloaded[0] if downloaded else ""

    def _create_minimal_txt2img(self, model, steps, cfg, seed, width, height):
        """Create a minimal Flux text2img workflow skeleton."""
        return {
            "3": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model or "flux1-dev-fp8.safetensors"}
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "prompt_placeholder", "clip": ["3", 1]}
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "width": width, "height": height}
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "steps": steps, "cfg": cfg, "seed": seed,
                    "model": ["3", 0], "positive": ["4", 0],
                    "negative": ["7", 0], "latent_image": ["5", 0]
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "negative_placeholder", "clip": ["3", 1]}
            },
            "8": {
                "class_type": "DecodeLatentToRGB",
                "inputs": {"latent": ["6", 0]}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"images": ["8", 0], "filename_prefix": "short_drama"}
            }
        }

    def _download_image(self, url: str, output_dir: Optional[str] = None) -> Optional[str]:
        """Download an image from ComfyUI URL."""
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            if not output_dir:
                output_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "output", "images"
                )
            os.makedirs(output_dir, exist_ok=True)
            filename = f"generated_{int(time.time())}.png"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            return None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
