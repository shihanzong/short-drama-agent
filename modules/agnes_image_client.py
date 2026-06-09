"""Agnes AI 图片生成模块

对接 Agnes AI 的图像生成 API，替代/补充 ComfyUI 本地出图。
适用于没有 GPU 或不想部署 ComfyUI 的场景。
"""

import os
import base64
import time
from typing import Optional, List, Dict, Tuple
from pathlib import Path


class AgnesImageClient:
    """Agnes AI 图像生成客户端"""

    # Agnes AI 图片生成 API 端点
    BASE_URL = "https://apihub.agnes-ai.com/v1"
    ENDPOINT = "/images/generations"

    # 支持的图片尺寸
    SUPPORTED_SIZES = {
        "portrait": (576, 1024),      # 9:16 竖屏（短剧默认）
        "square": (768, 768),         # 1:1 方形
        "landscape": (1024, 576),     # 16:9 横屏
        "hd_portrait": (576, 1024),   # 高清竖屏
    }

    # 模型列表
    MODELS = [
        "agnes-image-2.1-flash",
        "agnes-image-flash",
        "agnes-image-pro",
    ]

    def __init__(self, api_key: Optional[str] = None, model: str = "agnes-image-2.1-flash"):
        """
        Args:
            api_key: Agnes AI API Key（也可从环境变量 AGNES_IMAGE_API_KEY 读取）
            model: 使用的模型
        """
        import httpx

        self.api_key = api_key or os.getenv("AGNES_IMAGE_API_KEY", "")
        self.model = model
        self._http = httpx.Client(
            base_url=self.BASE_URL,
            timeout=120,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        size: str = "portrait",
        steps: int = 20,
        cfg_scale: float = 7.0,
        output_dir: Optional[str] = None,
        batch_count: int = 1,
    ) -> List[str]:
        """
        生成图片。
        
        Args:
            prompt: 正向提示词
            negative_prompt: 反向提示词
            size: 尺寸预设（portrait/square/landscape）
            steps: 生成步数
            cfg_scale: 提示词引导系数
            output_dir: 输出目录
            batch_count: 生成数量

        Returns:
            生成的图片文件路径列表
        """
        width, height = self.SUPPORTED_SIZES.get(size, self.SUPPORTED_SIZES["portrait"])

        payload = {
            "model": self.model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "batch_size": batch_count,
        }

        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        try:
            response = self._http.post(
                self.ENDPOINT,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            images = []
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # 处理返回的图片（base64 或 URL）
            image_data = data.get("data", data.get("images", []))
            for i, img in enumerate(image_data[:batch_count]):
                if output_dir:
                    filename = f"generated_{int(time.time())}_{i}.png"
                    filepath = os.path.join(output_dir, filename)
                else:
                    filepath = None

                if "b64_json" in img:
                    # base64 数据
                    img_bytes = base64.b64decode(img["b64_json"])
                    if filepath:
                        with open(filepath, "wb") as f:
                            f.write(img_bytes)
                    images.append(filepath)
                elif "url" in img:
                    # URL 地址
                    if filepath:
                        img_resp = self._http.get(img["url"])
                        img_resp.raise_for_status()
                        with open(filepath, "wb") as f:
                            f.write(img_resp.content)
                    images.append(img.get("url", ""))

            print(f"[AgnesImage] 生成完成: {len(images)} 张图片")
            return images

        except Exception as e:
            print(f"[AgnesImage] 生成失败: {e}")
            return []

    def generate_storyboard_images(
        self,
        storyboard: List[Dict],
        character_cards: List[Dict],
        style: str = "cinematic_realistic",
        output_dir: str = "output/images",
        max_images: int = 5,
    ) -> List[str]:
        """
        从分镜脚本批量生成图片。
        
        Args:
            storyboard: 分镜列表，每个包含 "prompt" 和 "negative_prompt"
            character_cards: 角色卡片
            style: 视觉风格预设
            output_dir: 输出目录
            max_images: 最大生成数量

        Returns:
            图片文件路径列表
        """
        # 加载风格预设
        from modules.style_manager import StyleManager
        style_mgr = StyleManager()
        preset = style_mgr.get_preset(style)

        # 构建完整提示词
        enhanced_prompts = []
        for shot in storyboard[:max_images]:
            base_prompt = shot.get("prompt", "")
            neg_prompt = shot.get("negative_prompt", "")

            # 添加风格标签
            enhanced = f"{base_prompt}, {preset.get('style_tags', '')}"
            enhanced_prompts.append((enhanced, neg_prompt))

        # 批量生成
        prompts = [p[0] for p in enhanced_prompts]
        negatives = [p[1] for p in enhanced_prompts]

        all_images = []
        for i, (prompt, neg) in enumerate(enhanced_prompts):
            img_path = self.generate(
                prompt=prompt,
                negative_prompt=neg,
                size="portrait",
                output_dir=output_dir,
                batch_count=1,
            )
            all_images.extend(img_path)

        return all_images

    def health_check(self) -> bool:
        """检查 API 是否可用"""
        try:
            response = self._http.get("/models", timeout=10)
            return response.status_code in (200, 404)  # 404 也说明 API 可达
        except Exception:
            return False

    def close(self):
        """关闭 HTTP 连接"""
        if self._http:
            self._http.close()

    def __del__(self):
        self.close()


# ===== 便捷函数 =====

def generate_image(
    prompt: str,
    output_path: Optional[str] = None,
    model: str = "agnes-image-2.1-flash",
) -> Optional[str]:
    """
    快速生成一张图片。
    
    Args:
        prompt: 提示词
        output_path: 输出路径
        model: 模型名称
    
    Returns:
        生成的图片路径，失败返回 None
    """
    client = AgnesImageClient()
    try:
        output_dir = os.path.dirname(output_path) if output_path else "output/images"
        images = client.generate(
            prompt=prompt,
            output_dir=output_dir,
        )
        return images[0] if images else None
    finally:
        client.close()


if __name__ == "__main__":
    # 快速测试
    print("=" * 50)
    print("  AgnesImage 模块测试")
    print("=" * 50)
    
    client = AgnesImageClient()
    health = client.health_check()
    print(f"  API 连通性: {'✅ OK' if health else '❌ 不可用'}")
    
    if health:
        print(f"  可用模型: {client.MODELS}")
    else:
        print("  提示: 请检查 AGNES_IMAGE_API_KEY 环境变量")
        print("  或设置: os.environ['AGNES_IMAGE_API_KEY'] = 'your-key'")
