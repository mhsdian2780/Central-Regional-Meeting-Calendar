# refresh_data.py — 从两份腾讯文档 CSV 重新生成 data.json
# 用法: python refresh_data.py <项目明细表.csv> <会议明细.csv> [输出data.json]
#      [--proj-header N] [--meet-header N]   指定真实表头所在行(0-based)
# 设计：列名按关键词匹配，容错表头微调；只保留 9 月；中央市场 region 强制=中央。
# 项目明细表仅统计「中央配套」类型，区域自办全部剔除；活动收集表仅取 9 月中央活动。
import sys, re, json, csv, os, argparse
from datetime import datetime, timedelta

# 最终更新日（取本地当前日期，格式 YYYY/M/D，如 2026/9/7）
UPDATED_AT = '{y}/{m}/{d}'.format(y=datetime.now().year, m=datetime.now().month, d=datetime.now().day)

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

# ===== 多天会议日期展开 =====
# 支持: 2026/9/16-20 / 2026/9/16-9/18 / 2026/7/31-8/1 / 2026/9/16-2026/9/18
#       9月16-20日 / 2026年9月16-20日 / 7.17-18
_RANGE = r'\s*[-–~—至到]\s*'

def _walk(y, m1, d1, m2, d2, cap=62):
    """从 (m1,d1) 逐日走到 (m2,d2)，返回 [(month,day),...]；非法日期返回 []"""
    try:
        start = datetime(y, m1, d1)
    except ValueError:
        return []
    for ytry in (y, y + 1):  # 结束月日可能跨年（如 12/30-1/2）
        try:
            end = datetime(ytry, m2, d2)
        except ValueError:
            continue
        if end < start:
            continue
        out, cur = [], start
        while cur <= end and len(out) < cap:
            out.append((cur.month, cur.day))
            cur += timedelta(days=1)
        return out
    return []

def parse_days(text):
    """解析活动时间 → [(month, day), ...]。范围返回逐日列表；单日/无法解析返回 []（走旧逻辑）"""
    if not text:
        return []
    t = str(text).strip()
    # 1) 完整日期-完整日期: 2026/9/16-2026/9/18
    m = re.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})' + _RANGE +
                  r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', t)
    if m:
        return _walk(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                     int(m.group(5)), int(m.group(6)))
    # 2) 完整日期-(月/)日: 2026/9/16-20 / 2026/9/16-9/18 / 2026/7/31-8/1
    m = re.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})' + _RANGE +
                  r'(?:(\d{1,2})[/\-.])?(\d{1,2})(?!\d)', t)
    if m:
        y, m1, d1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m2 = int(m.group(4)) if m.group(4) else m1
        return _walk(y, m1, d1, m2, int(m.group(5)))
    # 3) 中文: 2026年9月16-20日 / 9月16-20日
    m = re.search(r'(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*' + _RANGE +
                  r'\s*(\d{1,2})\s*日?', t)
    if m:
        y = int(m.group(1)) if m.group(1) else datetime.now().year
        m1, d1, d2 = int(m.group(2)), int(m.group(3)), int(m.group(4))
        return _walk(y, m1, d1, m1, d2)
    # 4) M.D-D: 7.17-18
    m = re.search(r'(\d{1,2})\.(\d{1,2})\s*' + _RANGE + r'\s*(\d{1,2})(?!\d)', t)
    if m:
        m1, d1, d2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _walk(datetime.now().year, m1, d1, m1, d2)
    return []

# ===== 卡片右下角日期文本 =====
# 单日: 9月16日；多天(同月): 9月16日-20日；多天(跨月): 9月30日-10月2日
def _fmt_md(m, d):
    return '%d月%d日' % (m, d)

def fmt_date_text(days):
    """由 parse_days 的逐日列表生成规范日期文本"""
    if not days:
        return ''
    (m1, d1), (m2, d2) = days[0], days[-1]
    if (m1, d1) == (m2, d2):
        return _fmt_md(m1, d1)
    if m1 == m2:
        return '%d月%d日-%d日' % (m1, d1, d2)
    return '%s-%s' % (_fmt_md(m1, d1), _fmt_md(m2, d2))

def build(proj_csv, meeting_csv, proj_header=0, meet_header=0):
    calendar = {}
    pending = []
    mismatch = []
    uid_seq = [0]

    def ingest(path, typ, force_region=None, header_row=0, type_keep=None):
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
        c_status = find_col(header, '执行情况')
        c_type   = find_col(header, '类型')
        for r in rows[header_row + 1:]:
            rec = dict(zip(header, r))
            g = lambda k: norm(rec.get(k, ''))
            if not g(c_name) and not g(c_zhanyi) and not g(c_time):
                continue  # 跳过空行
            # 项目明细表：仅统计「中央配套」类型，区域自办全部剔除
            if type_keep is not None:
                src = g(c_type) if c_type else ''
                if not type_keep(src):
                    continue
            month = month_of(g(c_month)) if c_month else None
            time = g(c_time)
            tmonth = month_of(time)
            target = month if month else tmonth
            uid_seq[0] += 1
            item = {
                'uid': '%s-%d' % (typ, uid_seq[0]),
                'line': g(c_line),
                'region': force_region if force_region else (g(c_region) if c_region else '—'),
                'zhanyi': g(c_zhanyi),
                'name': g(c_name),
                'time': time,
                'place': g(c_place),
                'form': g(c_form),
                'filler': g(c_filler),
                'type': typ,
                'status': g(c_status) if c_status else '',
            }
            if target is None:
                continue  # 无有效月份信息，无法判定为 9 月，剔除
            if target != 9:
                continue  # 非 9 月，剔除
            # 多天会议：日期范围展开为逐日，每一天都显示（同一 uid，前端去重统计）
            days = parse_days(time)
            if days:
                sept_days = [d for (m, d) in days if m == 9]
                if not sept_days:
                    mismatch.append(item); continue  # 月份标 9 月但日期范围全在其他月份
                item['dateText'] = fmt_date_text(days)  # 右下角规范日期文本（按完整范围）
                for d in sept_days:
                    calendar.setdefault(str(d), []).append(item)
                continue
            if tmonth is not None and tmonth != 9:
                mismatch.append(item); continue  # 月份标 9 月但活动时间月份不一致
            d = day_of(time)
            if d is None:
                pending.append(item); continue  # 9 月但日期待定
            item['dateText'] = _fmt_md(9, d)
            calendar.setdefault(str(d), []).append(item)

    ingest(proj_csv, '中央配套', header_row=proj_header,
           type_keep=lambda t: '中央配套' in t and '区域自办' not in t)
    if meeting_csv and os.path.exists(meeting_csv):
        ingest(meeting_csv, '中央市场', force_region='中央', header_row=meet_header)

    total = len({it['uid'] for v in calendar.values() for it in v})  # 按会议去重（多天会议只计 1 场）
    return {
        'calendar': calendar,
        'pending': pending,
        'mismatch': mismatch,
        'total': total,
        'updatedAt': UPDATED_AT,
    }

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
