import subprocess, json, sys

PY_EXE = r'C:/Users/MyGo！！！！！/.workbuddy/binaries/python/versions/3.13.12/python.exe'
DOC_PY = r'C:/Users/MyGo！！！！！/.workbuddy/plugins/cache/workbuddy-builtin/tencent-docs-plugin/1.0.0/skills/tencent-docs/tencentdocs.py'

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
    export("DSVBJdHNDQm1OaU1D", "sf85uj", 583, 28, "_proj.csv")
    export("DYUtWUU5UQ2NqYmNU", "000001", 254, 29, "_meet.csv")
