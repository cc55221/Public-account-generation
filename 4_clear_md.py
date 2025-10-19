# clean_md_sections.py
# 用法：
#   1) 直接运行：python clean_md_sections.py
#      （会自动选择当前文件夹里最近修改的 .md）
#   2) 指定文件：python clean_md_sections.py input.md [output.md]
#
# 功能：
#   - 仅保留以下 5 个子标题的内容，顺序按原文出现的顺序：
#       引用格式、摘要、引言与研究背景、文章的贡献点、结论
#   - 形如 “摘要（原文完整摘要的中文翻译）” / “摘要(……)” 等，统一规范为 “摘要”
#   - 删除 5 个子标题之外的所有内容（包括“---”“（完）”“(完)”等）
#   - 输出到当前目录：cleaned_<原文件名>.md

import sys
import re
from pathlib import Path

# 允许识别和归一化的 5 个目标标题（最终名称保持右侧值）
NORMAL_TITLES = {
    "引用格式": "引用格式",
    "摘要": "摘要",
    "引言与研究背景": "引言与研究背景",
    "文章的贡献点": "文章的贡献点",
    "结论": "结论",
}

# 匹配 Markdown 标题行：最多前三个空格 + 1~6 个 # + 标题文本
HDR_RE = re.compile(r'^\s{0,3}(#{1,6})\s*(.+?)\s*$')

# 去掉标题里的括号冗余（支持全角/半角）
PAREN_STRIP_RE = re.compile(r'[（(].*?[）)]')

# “完” 行/标记（全角与半角）或仅作分隔的横线
END_MARKERS = {
    "（完）", "(完)", "完", "---", "----", "___", "***"
}

def pick_latest_md_in_cwd():
    mds = list(Path(".").glob("*.md"))
    if not mds:
        return None
    mds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return mds[0]

def normalize_title(raw: str) -> str | None:
    """
    传入原始标题文本，去除括号冗余、收尾空白，然后
    如果能匹配 5 个目标标题之一，返回标准化标题；否则返回 None
    """
    # 去掉内联代码反引号包裹（少见但稳妥）
    t = raw.strip().strip('`').strip()
    # 去掉括号及其中内容
    t = PAREN_STRIP_RE.sub('', t).strip()

    # 有些人会写成 “【摘要】”“[摘要]”等，顺手剥一层
    t = t.strip('[]【】')

    # 直接全等
    if t in NORMAL_TITLES:
        return NORMAL_TITLES[t]

    # 宽松匹配：如果标题以目标关键字开头，也视为该标题
    for k, v in NORMAL_TITLES.items():
        if t.startswith(k):
            return v

    return None

def clean_markdown(in_path: Path, out_path: Path):
    lines = in_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    # 扫描一遍，抽取 5 个标题对应的内容块
    keep_titles = set(NORMAL_TITLES.values())
    current_keep_title = None
    current_hashes = None  # 记录当前标题的 # 层级，遇到同级或更高层级时关闭
    out_blocks = {t: [] for t in keep_titles}  # 每个标题单独一个列表

    for i, line in enumerate(lines):
        m = HDR_RE.match(line)
        if m:
            hashes, title_text = m.group(1), m.group(2)
            level = len(hashes)
            norm = normalize_title(title_text)

            # 遇到新标题时，判断是否是 5 个标题之一
            if norm:
                # 进入新的 keep 区段
                current_keep_title = norm
                current_hashes = level
                # 写入规范化后的标题行（统一用一级二级都行，这里保持原级别）
                out_blocks[current_keep_title].append(f"{hashes} {current_keep_title}")
            else:
                # 非目标标题，关闭当前 keep 区段
                current_keep_title = None
                current_hashes = None
            continue

        # 非标题行
        # 如果当前在目标标题的区段内，则保留；并过滤“完”或纯分隔线
        if current_keep_title is not None:
            stripped = line.strip()
            # 跳过“完”标记或横线分隔（这些都不要）
            if stripped in END_MARKERS:
                continue
            # 常见“---”形式的分隔线也跳过（更稳妥）
            if set(stripped) <= {"-", "_", "*"} and len(stripped) >= 3:
                continue
            out_blocks[current_keep_title].append(line)

    # 组装输出内容：仅拼接实际出现过的 5 个标题（保持文件中出现的顺序）
    # 我们再扫一次原文，按实际出现顺序输出对应块
    appeared_order = []
    for line in lines:
        m = HDR_RE.match(line)
        if m:
            norm = normalize_title(m.group(2))
            if norm and norm not in appeared_order:
                appeared_order.append(norm)

    # 若文件里没有任何一个目标标题，就直接空输出（或保守地原样复制）
    if not appeared_order:
        # 这里选择空输出，以免把错误内容带过去
        out_path.write_text("", encoding="utf-8")
        return

    # 拼接：标题块之间空一行
    out_lines = []
    first = True
    for t in appeared_order:
        block = out_blocks.get(t, [])
        if not block:
            continue
        if not first:
            out_lines.append("")  # 空行分隔
        first = False
        # 去掉块尾部多余空行
        while block and block[-1].strip() == "":
            block.pop()
        out_lines.extend(block)

    out_text = "\n".join(out_lines) + "\n"
    out_path.write_text(out_text, encoding="utf-8")

def main():
    if len(sys.argv) >= 2:
        in_path = Path(sys.argv[1])
        if not in_path.exists():
            print(f"[错误] 找不到文件：{in_path}")
            sys.exit(1)
        if len(sys.argv) >= 3:
            out_path = Path(sys.argv[2])
        else:
            out_path = in_path.with_name(f"cleaned_{in_path.name}")
    else:
        latest = pick_latest_md_in_cwd()
        if latest is None:
            print("[错误] 当前文件夹没有 .md 文件，也未指定输入路径。")
            sys.exit(1)
        in_path = latest
        out_path = in_path.with_name(f"cleaned_{in_path.name}")

    clean_markdown(in_path, out_path)
    print(f"[完成] 已生成：{out_path}")

if __name__ == "__main__":
    main()
