# -*- coding: utf-8 -*-
"""
一键生成公众号推文：PDF -> DeepSeek API -> 完整Markdown
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List
import requests
from pdfminer.high_level import extract_text

# =========================
# 配置
# =========================
API_BASE = "https://api.deepseek.com/v1"
CHAT_URL = f"{API_BASE}/chat/completions"
MODEL = "deepseek-chat"

# 从环境变量或文件读取API密钥
API_KEY = os.getenv("your_deepseek_api_key")
if not API_KEY:
    try:
        with open("api_key.txt", "r") as f:
            API_KEY = f.read().strip()
    except:
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY 或创建 api_key.txt 文件")
        exit(1)

PDF_FILE = "Physics-Informed_Neural_Networks_for_Bio-Nano_Digital_Twins_A_Multi-Model_Framework_with_IoBNT_Integration.pdf"  # 留空自动选择最新PDF
OUTPUT_MD_FILE = "公众号推文.md"

# =========================
# 辅助函数
# =========================
def pick_latest_pdf_in_cwd() -> str:
    pdfs = list(Path(".").glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError("当前文件夹没有找到任何 PDF 文件")
    pdfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(pdfs[0])

def post_chat(messages: List[Dict], temperature: float = 0.2, max_tokens: int = 4000) -> str:
    """调用 DeepSeek API"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    
    try:
        resp = requests.post(CHAT_URL, headers=headers, data=json.dumps(payload), timeout=180)
        
        if resp.status_code != 200:
            error_msg = f"API错误 {resp.status_code}: {resp.text[:500]}"
            raise RuntimeError(error_msg)
            
        data = resp.json()
        return data["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        raise RuntimeError("API请求超时")
    except Exception as e:
        raise RuntimeError(f"API调用失败: {str(e)}")

def extract_text_local(pdf_path: str) -> str:
    """PDF文本提取"""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"未找到PDF文件：{pdf_path}")
    
    try:
        text = extract_text(pdf_path)
        if not text or len(text.strip()) < 100:
            raise ValueError("提取的文本过短，可能PDF是扫描件或加密")
        return text
    except Exception as e:
        raise RuntimeError(f"PDF文本提取失败: {e}")

def slice_sections(raw_text: str) -> Dict[str, str]:
    """提取论文章节"""
    patterns = {
        "title": r"^(.*?)(?=\n\s*(abstract|摘要|abstract:))",
        "abstract": r"(?is)(abstract|摘要)\s*(.*?)(?=\n\s*(keywords?|index terms?|introduction|1\.\s|Ⅰ\.|I\.\s))",
        "introduction": r"(?is)(1\.\s*introduction|introduction|Ⅰ\.|I\.\s*introduction)\s*(.*?)(?=\n\s*(2\.|Ⅱ\.|related work|method|system model))",
        "conclusion": r"(?is)(conclusion|conclusions|结论)\s*(.*?)(?=\n\s*(references|bibliography|致谢|acknowledgment))",
    }
    
    def extract_section(pattern, text, group=1):
        match = re.search(pattern, text)
        return match.group(group).strip() if match else ""
    
    title = extract_section(patterns["title"], raw_text, 1)
    abstract = extract_section(patterns["abstract"], raw_text, 2)  
    introduction = extract_section(patterns["introduction"], raw_text, 2)
    conclusion = extract_section(patterns["conclusion"], raw_text, 2)
    
    # 如果正则没匹配到，尝试简单提取
    if not title:
        title = "\n".join([line.strip() for line in raw_text.split('\n')[:3] if line.strip()])
    
    return {
        "title": title[:300] if title else "未识别标题",
        "abstract": abstract,
        "introduction": introduction, 
        "conclusion": conclusion,
        "full_text": raw_text[:15000],  # 限制全文长度用于贡献点提取
    }

def generate_article_with_llm(sections: Dict[str, str]) -> str:
    """使用LLM一次性生成完整的公众号推文"""
    
    prompt = f"""请基于以下学术论文内容，生成一篇适合微信公众号发布的专业推文。

论文标题：{sections['title']}

论文摘要（英文）：
{sections['abstract']}

论文引言和研究背景（英文）：
{sections['introduction']}

论文结论（英文）：
{sections['conclusion']}

请按照以下格式和要求生成中文推文：

1. 生成一个吸引人的中文标题（不要使用表情符号）

2. 内容结构：
## 引用格式
（这里请基于论文内容推断可能的引用信息，参考IEEE格式，包括作者、期刊/会议、年份等，用英文）

## 摘要
将英文摘要完整翻译为中文，保持学术严谨性

## 引言与研究背景  
将英文引言完整翻译为中文，清晰阐述研究背景和问题

## 文章的贡献点
从论文内容中提取3-5个主要贡献点，用有序列表形式呈现

## 结论
将英文结论完整翻译为中文，完整呈现研究发现

要求：
- 语言专业流畅，适合学术公众号
- 保持原文的学术严谨性
- 不要添加表情符号
- 不要添加额外评论或总结
- 确保翻译完整准确"""

    messages = [
        {
            "role": "system", 
            "content": "你是专业的学术内容编辑，擅长将英文学术论文转化为高质量的中文公众号推文。"
        },
        {
            "role": "user", 
            "content": prompt
        },
    ]
    
    print("📝 正在生成公众号推文...")
    return post_chat(messages, temperature=0.1, max_tokens=6000)

# =========================
# 主流程
# =========================
def main():
    try:
        print("🚀 开始处理PDF论文...")
        
        # 1. 选择PDF
        pdf_path = PDF_FILE or pick_latest_pdf_in_cwd()
        print(f"📄 选择的PDF: {pdf_path}")
        
        # 2. 提取文本
        raw_text = extract_text_local(pdf_path)
        print(f"✅ 文本提取完成，共 {len(raw_text)} 字符")
        
        # 3. 分割章节
        sections = slice_sections(raw_text)
        print("📑 章节提取完成")
        
        # 4. 一次性生成完整推文
        article_content = generate_article_with_llm(sections)
        
        # 5. 保存结果
        with open(OUTPUT_MD_FILE, "w", encoding="utf-8") as f:
            f.write(article_content)
            
        print(f"✅ 完成！生成文件: {OUTPUT_MD_FILE}")
        print("📊 推文已按照公众号格式生成")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")

if __name__ == "__main__":
    main()