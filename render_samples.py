# -*- coding: utf-8 -*-
"""render_samples.py · 读取 output_src/*.json 用三套主题渲染 HTML 样本。

用法:
    python render_samples.py                    # 渲染三套主题到默认输出目录
    python render_samples.py --theme atelier-dark  # 只渲染指定主题
    python render_samples.py --outdir rendered_samples  # 自定义输出目录
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_SRC = ROOT / "output_src"


def render_all(theme: str = None, outdir: str = None) -> list[dict]:
    """读取所有 output_src/*.json,用指定(或多套)主题渲染 HTML。

    Args:
        theme: 主题机器名,或 None 表示渲染所有三套主题
        outdir: 输出根目录,缺省为 ROOT / "rendered_samples"

    Returns:
        [{"theme": "...", "slug": "...", "path": "...", "size": N}, ...]
    """
    if not OUTPUT_SRC.exists():
        print(f"目录不存在: {OUTPUT_SRC}")
        return []

    json_files = sorted(OUTPUT_SRC.glob("*.json"))
    if not json_files:
        print(f"output_src/ 中没有 JSON 文件。")
        return []

    from lib import preview, themes as themes_mod

    # 确定主题列表
    if theme:
        theme_list = [(theme, themes_mod.resolve_name(theme))]
    else:
        theme_list = [
            ("datasheet-editorial", "datasheet-editorial"),
            ("atelier-dark", "atelier-dark"),
            ("technical-blueprint", "technical-blueprint"),
        ]

    # 输出基目录
    base_out = Path(outdir) if outdir else (ROOT / "rendered_samples")
    base_out.mkdir(parents=True, exist_ok=True)

    results = []

    for alias, machine_name in theme_list:
        theme_dir = base_out / machine_name
        theme_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  读取 {jf.name} 失败: {e}")
                continue

            slug = jf.stem
            page = {
                "slug": slug,
                "type": data.get("type", "guide"),
                "title": data.get("title", slug),
                "target_keyword": data.get("target_keyword", slug),
                "nav_label": data.get("nav_label", slug),
            }
            content = {
                "title": data.get("title", ""),
                "meta_description": data.get("meta_description", ""),
                "html": data.get("html", ""),
                "image_query": data.get("image_query", ""),
            }
            pages.append({"page": page, "content": content})

        if not pages:
            continue

        # 构造 site info
        site_url = "https://demo-leather.example.com"
        all_page_dicts = [p["page"] for p in pages]

        for entry in pages:
            page = entry["page"]
            content = entry["content"]

            try:
                # 注入主题信息到 page
                page["_industry"] = {"theme": machine_name}

                html = preview.render_html(
                    page, content,
                    site=site_url,
                    all_pages=all_page_dicts,
                )
                out_path = theme_dir / f"{page['slug']}.html"
                out_path.write_text(html, encoding="utf-8")
                results.append({
                    "theme": machine_name,
                    "slug": page["slug"],
                    "path": str(out_path),
                    "size": len(html),
                })
            except Exception as e:
                print(f"  渲染 {machine_name}/{page['slug']} 失败: {e}")

        # 写 index
        try:
            preview.write_index(all_page_dicts, str(theme_dir))
            results.append({
                "theme": machine_name,
                "slug": "index",
                "path": str(theme_dir / "index.html"),
                "size": (theme_dir / "index.html").stat().st_size if (theme_dir / "index.html").exists() else 0,
            })
        except Exception as e:
            print(f"  写 index {machine_name} 失败: {e}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="渲染 output_src/*.json 为 HTML 样本")
    parser.add_argument("--theme", type=str, default=None,
                       help="主题机器名(缺省三套全渲染)")
    parser.add_argument("--outdir", type=str, default=None,
                       help="输出目录(缺省 rendered_samples/)")
    args = parser.parse_args()

    print(f"源目录: {OUTPUT_SRC}")
    results = render_all(theme=args.theme, outdir=args.outdir)

    if results:
        themes_seen = set()
        for r in results:
            if r["theme"] not in themes_seen:
                print(f"\n主题: {r['theme']}")
                themes_seen.add(r["theme"])
            print(f"  {r['slug']} → {r['path']} ({r['size']:,} bytes)")
    else:
        print("未生成任何文件。")


if __name__ == "__main__":
    main()
