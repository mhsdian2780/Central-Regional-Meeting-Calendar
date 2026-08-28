#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 GitHub Pages 用的 index.html：
将 data.json 注入 template.html 的 /*__DATA__*/ 占位符，生成自包含、零依赖的单文件页面。
用法：python build_index.py
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    tpl_path = os.path.join(BASE, "template.html")
    data_path = os.path.join(BASE, "data.json")
    out_path = os.path.join(BASE, "index.html")

    tpl = open(tpl_path, encoding="utf-8").read()
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    # 紧凑但可读的 JSON，保留中文（ensure_ascii=False）
    data_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "/*__DATA__*/" not in tpl:
        raise SystemExit("ERROR: template.html 中未找到 /*__DATA__*/ 占位符")

    out = tpl.replace("/*__DATA__*/", data_str)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)

    size = os.path.getsize(out_path)
    total = data.get("total")
    days = len(data.get("calendar", {}))
    print(f"OK 生成 index.html ({size} bytes) | total={total} 活动天数={days}")


if __name__ == "__main__":
    main()
