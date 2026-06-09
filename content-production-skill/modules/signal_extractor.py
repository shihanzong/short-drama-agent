#!/usr/bin/env python3
"""
内容信号提取器 - Content Signal Extractor

从长文本素材中提取内容信号：
- 核心观点
- 关键案例
- 金句
- 冲突点
- 数字/数据
- 教程步骤
- 情绪点
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import Optional


SKILL_ROOT = Path(__file__).parent.parent


class ContentSignalExtractor:
    """内容信号提取器
    
    使用LLM从长文本中提取结构化内容信号。
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def extract(self, text: str, topic: str = "", source: str = "") -> dict:
        """从文本中提取内容信号"""
        if not text or len(text.strip()) < 100:
            return {
                "error": "文本太短，无法提取有意义的内容信号",
                "core_viewpoints": [],
                "key_cases": [],
                "golden_quotes": [],
                "conflict_points": [],
                "key_numbers": [],
                "tutorial_steps": [],
                "emotional_points": [],
                "summary": ""
            }
        
        prompt = self._build_prompt(text[:15000], topic, source)
        
        try:
            if self.llm_client:
                response = self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
            else:
                response = self._fallback_response()
            
            result = self._parse_json(response)
            result["meta"] = {
                "topic": topic,
                "source": source,
                "input_length": len(text),
                "signal_count": self._count_signals(result)
            }
            return result
            
        except Exception as e:
            return {
                "error": f"提取失败：{str(e)}",
                "core_viewpoints": [], "key_cases": [], "golden_quotes": [],
                "conflict_points": [], "key_numbers": [],
                "tutorial_steps": [], "emotional_points": [], "summary": ""
            }
    
    def _build_prompt(self, text: str, topic: str, source: str) -> str:
        return f"""从以下长文本中提取内容信号：

主题：{topic or '未指定'}
来源：{source or '未指定'}

提取类型：
1. 核心观点（3-5个，每个一句话概括，不超过30字）
2. 关键案例（2-3个，包含主题、描述、支撑的观点）
3. 金句（1-2句，原文）
4. 冲突点（1-2个，反常识或有讨论价值的）
5. 数字/数据（2-3个，包含数据、上下文、传播价值）
6. 教程步骤（如有，按顺序列出）
7. 情绪点（1-2个，能引发共鸣的）

输出JSON格式：
{{
  "core_viewpoints": ["观点1", "观点2"],
  "key_cases": [{{"topic": "...", "description": "...", "supports": "..."}}],
  "golden_quotes": ["金句1"],
  "conflict_points": ["冲突1"],
  "key_numbers": [{{"number": "...", "context": "...", "impact": "..."}}],
  "tutorial_steps": ["步骤1"],
  "emotional_points": ["情绪点1"],
  "summary": "内容概述100字"
}}

约束：
- 每条信号必须来自原文，不得编造
- 不确定的标注"不确定"
- 至少提取15条信号

文本内容：
{text}"""
    
    def _parse_json(self, response: str) -> dict:
        """解析JSON响应"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        match = re.search(r'\{[^{}]*"core_viewpoints"[^{}]*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法解析响应为JSON: {response[:200]}")
    
    def _fallback_response(self) -> str:
        """无LLM时的回退"""
        skill_root = SKILL_ROOT.parent
        client_file = skill_root / 'modules' / 'llm_client.py'
        if client_file.exists():
            sys.path.insert(0, str(skill_root))
            try:
                from modules.llm_client import LLMClient
                client = LLMClient()
                return client.generate(
                    messages=[{"role": "user", "content": "test"}],
                    response_format="json_object"
                )
            except Exception:
                pass
        
        return json.dumps({
            "core_viewpoints": ["（需要LLM支持才能提取）"],
            "key_cases": [], "golden_quotes": [],
            "conflict_points": [], "key_numbers": [],
            "tutorial_steps": [], "emotional_points": [],
            "summary": "当前环境无LLM客户端，无法自动提取。"
        })
    
    def _count_signals(self, result: dict) -> int:
        count = 0
        for key in ['core_viewpoints', 'key_cases', 'golden_quotes',
                     'conflict_points', 'key_numbers', 'tutorial_steps',
                     'emotional_points']:
            if key in result and isinstance(result[key], list):
                count += len(result[key])
        return count
    
    def save_results(self, result: dict, output_dir: str = None) -> str:
        """保存提取结果到文件"""
        if output_dir is None:
            output_dir = SKILL_ROOT / 'outputs'
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"signals_{timestamp}.json"
        filepath = output_dir / filename
        filepath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(filepath)


def extract_signals(text: str, topic: str = "", source: str = "",
                    llm_client=None, output_dir: str = None) -> dict:
    """便捷函数：从文本提取内容信号"""
    extractor = ContentSignalExtractor(llm_client=llm_client)
    result = extractor.extract(text, topic=topic, source=source)
    if output_dir:
        extractor.save_results(result, output_dir=output_dir)
    return result
