# export_csv.py — 从两份腾讯文档导出最新 CSV（路径自适应，跨机器通用）
# 用法: python export_csv.py
# 设计：不再写死用户名路径；自动定位 WorkBuddy 的
#      - 隔离 Python 运行时（.workbuddy/binaries/python/versions/*/python.exe）
#      - 腾讯文档技能脚本（tencent-docs-plugin/*/skills/tencent-docs/tencentdocs.py）
import subprocess, json, sys, os, glob, shutil

def _home():
    return os.path.expanduser('~')

def find_python():
    # 1) 优先用 WorkBuddy 隔离运行时（与脚本开发环境一致）
    vers = sorted(glob.glob(os.path.join(
        _home(), '.workbuddy', 'binaries', 'python', 'versions', '*', 'python.exe')))
    if vers:
        return vers[-1]  # 取最高版本
    # 2) 退化为运行本脚本的 python
    if sys.executable:
        return sys.executable
    # 3) 最后退化为系统 python
    for c in ('python3', 'python'):
        if shutil.which(c):
            return c
    raise SystemExit('找不到可用的 Python 运行时')

def find_tdoc_py():
    base = os.path.join(_home(), '.workbuddy')
    patterns = [
        os.path.join(base, 'plugins', 'cache', 'workbuddy-builtin',
                     'tencent-docs-plugin', '*', 'skills', 'tencent-docs', 'tencentdocs.py'),
        os.path.join(base, 'plugins', 'workbuddy-builtin',
                     'tencent-docs-plugin', '*', 'skills', 'tencent-docs', 'tencentdocs.py'),
    ]
    for pat in patterns:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    # 递归兜底（限制深度，避免扫全盘）
    root0 = os.path.join(base, 'plugins')
    for root, dirs, files in os.walk(root0):
        if root[len(root0):].count(os.sep) > 6:
            dirs[:] = []
            continue
        if 'tencentdocs.py' in files:
            return os.path.join(root, 'tencentdocs.py')
    raise SystemExit('找不到 tencent-docs 技能的 tencentdocs.py，请确认已连接腾讯文档连接器')

PY_EXE = find_python()
DOC_PY = find_tdoc_py()
print(f'[auto-path] python = {PY_EXE}')
print(f'[auto-path] tdoc   = {DOC_PY}')

def call(file_id, sheet_id, end_row, end_col):
    args = json.dumps({
        "file_id": file_id, "sheet_id": sheet_id,
        "start_row": 0, "start_col": 0,
        "end_row": end_row, "end_col": end_col,
        "return_csv": True
    }, ensure_ascii=False)
    r = subprocess.run([PY_EXE, DOC_PY, "tdoc_call", "sheet-mcp", "get_cell_data", args],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("STDERR:", r.stderr[:2000]); sys.exit(1)
    outer = json.loads(r.stdout)
    text = outer["result"]["content"][0]["text"]
    obj = json.loads(text)
    return obj.get("csv_data", "")

def export(file_id, sheet_id, end_row, end_col, out):
    csv_data = call(file_id, sheet_id, end_row, end_col)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        f.write(csv_data)
    print(f"wrote {out}: {csv_data.count(chr(10))} lines, {len(csv_data)} chars")

if __name__ == "__main__":
    # 文档 ID / 工作表 ID 与机器无关，保持写死
    export("DSVBJdHNDQm1OaU1D", "sf85uj", 583, 28, "_proj.csv")
    export("DYUtWUU5UQ2NqYmNU", "000001", 254, 29, "_meet.csv")
