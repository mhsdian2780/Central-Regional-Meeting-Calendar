# refresh_data.py — 从两份腾讯文档 CSV 重新生成 data.json
# 用法: python refresh_data.py <项目明细表.csv> <会议明细.csv> [输出data.json]
#      [--proj-header N] [--meet-header N]   指定真实表头所在行(0-based)
# 设计：列名按关键词匹配，容错表头微调；只保留 9 月；中央市场 region 强制=中央。
import sys, re, json, csv, os, argparse

def find_col(header, *keys):
    for h in header:
        for k in keys:
            if k in (h or ''):
                return h
    return None

def month_of(text):
    if not text: return None
    m = re.search(r'(\d{1,2})\s*月', text)          # 中文: 9月 / 2026年9月3日
    if m: return int(m.group(1))
    m = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)  # 斜杠/横杠: 2026/9/25
    if m: return int(m.group(2))
    return None

def day_of(text):
    if not text: return None
    m = re.search(r'(\d{1,2})\s*日', text)          # 中文: 3日
    if m: return int(m.group(1))
    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)  # 中文: 9月3日
    if m: return int(m.group(2))
    m = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)  # 斜杠/横杠: 2026/9/25
    if m: return int(m.group(3))
    return None

def norm(v):
    return (v or '').strip()

def build(proj_csv, meeting_csv, proj_header=0, meet_header=0):
    calendar = {}
    pending = []
    mismatch = []

    def ingest(path, typ, force_region=None, header_row=0):
        with open(path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
        if not rows: return
        header = rows[header_row]
        c_month  = find_col(header, '月份')
        c_time   = find_col(header, '活动时间')
        c_filler = find_col(header, '填写人')
        c_line   = find_col(header, '肺肿线', '肺种线')
        c_zhanyi = find_col(header, '战役')
        c_name   = find_col(header, '活动名称')
        c_place  = find_col(header, '活动地点')
        c_form   = find_col(header, '活动形式')
        c_region = find_col(header, '区域')
        for r in rows[header_row + 1:]:
            rec = dict(zip(header, r))
            g = lambda k: norm(rec.get(k, ''))
            if not g(c_name) and not g(c_zhanyi) and not g(c_time):
                continue  # 跳过空行
            month = month_of(g(c_month)) if c_month else None
            time = g(c_time)
            tmonth = month_of(time)
            target = month if month else tmonth
            if target is not None and target != 9:
                continue  # 只保留 9 月
            item = {
                'line': g(c_line),
                'region': force_region if force_region else (g(c_region) if c_region else '—'),
                'zhanyi': g(c_zhanyi),
                'name': g(c_name),
                'time': time,
                'place': g(c_place),
                'form': g(c_form),
                'filler': g(c_filler),
                'type': typ,
            }
            if target == 9 and tmonth is not None and tmonth != 9:
                mismatch.append(item); continue
            d = day_of(time)
            if d is None:
                pending.append(item); continue
            calendar.setdefault(str(d), []).append(item)

    ingest(proj_csv, '中央配套', header_row=proj_header)
    if meeting_csv and os.path.exists(meeting_csv):
        ingest(meeting_csv, '中央市场', force_region='中央', header_row=meet_header)

    total = sum(len(v) for v in calendar.values())
    return {'calendar': calendar, 'pending': pending, 'mismatch': mismatch, 'total': total}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('proj')
    ap.add_argument('meet')
    ap.add_argument('out', nargs='?', default=os.path.join(os.path.dirname(__file__), 'data.json'))
    ap.add_argument('--proj-header', type=int, default=0)
    ap.add_argument('--meet-header', type=int, default=0)
    a = ap.parse_args()
    data = build(a.proj, a.meet, a.proj_header, a.meet_header)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print('OK total=%d days=%d pending=%d mismatch=%d -> %s' % (
        data['total'], len(data['calendar']), len(data['pending']), len(data['mismatch']), a.out))
