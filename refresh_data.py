# refresh_data.py — 从两份腾讯文档 CSV 重新生成 data.json
# 用法: python refresh_data.py <项目明细表.csv> <会议明细.csv> [输出data.json]
# 设计：列名按关键词匹配，容错表头微调；只保留 9 月；中央市场 region 强制=中央。
import sys, re, json, csv, os

def find_col(header, *keys):
    for h in header:
        for k in keys:
            if k in (h or ''):
                return h
    return None

def month_of(text):
    if not text: return None
    m = re.search(r'(\d{1,2})\s*月', text)
    return int(m.group(1)) if m else None

def day_of(text):
    if not text: return None
    m = re.search(r'(\d{1,2})\s*日', text)
    if m: return int(m.group(1))
    # 形如 2026年9月3日
    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    return int(m.group(2)) if m else None

def norm(v):
    return (v or '').strip()

def build(proj_csv, meeting_csv):
    calendar = {}
    pending = []
    mismatch = []

    def ingest(rows, typ, force_region=None):
        if not rows: return
        header = rows[0]
        c_month  = find_col(header, '月份')
        c_time   = find_col(header, '活动时间')
        c_filler = find_col(header, '填写人')
        c_line   = find_col(header, '肺肿线', '肺种线')
        c_zhanyi = find_col(header, '战役')
        c_name   = find_col(header, '活动名称')
        c_place  = find_col(header, '活动地点')
        c_form   = find_col(header, '活动形式')
        c_region = find_col(header, '区域')
        for r in rows[1:]:
            rec = dict(zip(header, r))
            g = lambda k: norm(rec.get(k, ''))
            month = month_of(g(c_month)) if c_month else None
            time = g(c_time)
            tmonth = month_of(time)
            # 目标月份 = 表头月份，缺失时用活动时间月份
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
            # 月份标注9月但活动时间指向其他月份 -> 不一致
            if target == 9 and tmonth is not None and tmonth != 9:
                mismatch.append(item); continue
            d = day_of(time)
            if d is None:
                pending.append(item); continue
            calendar.setdefault(str(d), []).append(item)

    # 项目明细表 -> 中央配套
    with open(proj_csv, encoding='utf-8-sig', newline='') as f:
        ingest(list(csv.reader(f)), '中央配套')
    # 会议明细 -> 中央市场（region 强制 中央）
    if meeting_csv and os.path.exists(meeting_csv):
        with open(meeting_csv, encoding='utf-8-sig', newline='') as f:
            ingest(list(csv.reader(f)), '中央市场', force_region='中央')

    total = sum(len(v) for v in calendar.values())
    return {'calendar': calendar, 'pending': pending, 'mismatch': mismatch, 'total': total}

if __name__ == '__main__':
    proj = sys.argv[1]
    meet = sys.argv[2] if len(sys.argv) > 2 else None
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), 'data.json')
    data = build(proj, meet)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print('OK total=%d days=%d pending=%d mismatch=%d -> %s' % (
        data['total'], len(data['calendar']), len(data['pending']), len(data['mismatch']), out))
