"""六類高風險標記｜判定參考實作（Python 3，無外部套件）

依據：判斷邏輯 v4（2026-11-04）＋ 題目清單 v2（2026-11-08）的欄位變動。規格文字見 02_六類標記判定規格.md。
用途：給工程師對照；07 測試案例的「預期結果」就是用這支算的。正式系統用什麼語言實作都可以，結果要跟這支一致。

輸入：answers（dict），key 用 01_題目規格 的「代碼」欄（code），沒填就不要放或放 None。
輸出：每一類的 status（標記／資料未齊／未標記）、觸發代碼、缺漏欄位。

三值：每個條件回傳 Y（符合）、N（不符合）、U（無法判斷）。
類別：任一條件 Y → 標記；沒有 Y 但有 U → 資料未齊（不可顯示成無風險）；全部 N → 未標記。
"""
from datetime import date

Y, N, U = 'Y', 'N', 'U'
RULE_VERSION = 'v4_20261104+formv2_20261108'
NEURO_L2 = {'帕金森氏症', '失智症', '小腦疾病', '前庭疾病／眩暈症', '視力障礙'}  # 「其他神經系統疾病」不算（v4 L2 只列這五項）
PARQ_GENERAL = ['parq_g1', 'parq_g2', 'parq_g3', 'parq_g4', 'parq_g5', 'parq_g6', 'parq_g7']


def blank(v):
    return v is None or v == '' or v == []


# ---------- 衍生值 ----------
def fill_date(a):
    d = a.get('fill_date')
    return date.fromisoformat(d) if d else None


def age(a):
    """birth：{'age': 71} 或 {'year': 1955, 'month': 4, 'day': 12}（月日可缺）。以 fill_date 為基準日。"""
    b = a.get('birth') or {}
    ref = fill_date(a) or date.today()
    if b.get('year') and b.get('month') and b.get('day'):
        y, m, d = int(b['year']), int(b['month']), int(b['day'])
        return ref.year - y - ((ref.month, ref.day) < (m, d))
    if b.get('age') not in (None, ''):
        return int(b['age'])
    if b.get('year'):  # 只有年份：粗估（表單上年齡與年份擇一填，正常不會走到這裡）
        return ref.year - int(b['year'])
    return None


def bmi(a):
    h, w = a.get('height'), a.get('weight')
    return None if blank(h) or blank(w) else w / (h / 100) ** 2


def sarcopenia(a):
    """AWGS 2025（判斷邏輯 v4）：max(左右握力) < 切點 且 SMI < 切點。<50 歲不判定（當作 N）。"""
    sex, ag = a.get('sex'), age(a)
    if blank(sex) or ag is None:
        return U
    if ag < 50:
        return N
    grips = [g for g in (a.get('grip_l'), a.get('grip_r')) if not blank(g)]
    smi = a.get('smi')
    if not grips or blank(smi):
        return U
    if ag >= 65:
        gc, sc = (28, 7.0) if sex == '男' else (18, 5.7)
    else:
        gc, sc = (34, 7.6) if sex == '男' else (20, 5.7)
    return Y if (max(grips) < gc and smi < sc) else N


def osta_flag(a):
    """F3：照骨鬆學會計算器，指數先四捨五入成整數；用整數寫法避免浮點誤差。
    女 round(0.2×(w−age)) < −1  ⇔  w ≤ age − 7.5
    男 round(0.3×w − 0.1×age) ≤ 11  ⇔  3×w − age < 115"""
    sex, w, ag = a.get('sex'), a.get('weight'), age(a)
    if blank(sex) or blank(w) or ag is None:
        return U
    if sex == '女':
        return Y if w * 10 <= ag * 10 - 75 else N
    return Y if 3 * w - ag < 115 else N


# ---------- PAR-Q+ 追問題的空白處理 ----------
def parq_follow(a, code):
    """通用 7 題全答否 → 追問全部 N；大題答「沒有」→ 該題小題 N；其他空白 → U。"""
    v = a.get(code)
    if v in ('是', '有'):
        return Y
    if v in ('否', '沒有'):
        return N
    gen = [a.get(k) for k in PARQ_GENERAL]
    if all(x == '否' for x in gen):
        return N
    main = code.rstrip('abcde') if code[-1] in 'abcde' else None
    if main and a.get(main) == '沒有':
        return N
    return U


def yn(a, code):
    v = a.get(code)
    return Y if v in ('是', '有', '會') else N if v in ('否', '沒有', '不會') else U


def any_of(*vals):
    return Y if Y in vals else U if U in vals else N


# ---------- 各條件 ----------
def conditions(a):
    c = {}
    # 骨折
    t, z, done = a.get('dxa_t'), a.get('dxa_z'), a.get('dxa_done')
    if (not blank(t) and t < -1.0) or (not blank(z) and z < -2.0):
        c['F1'] = Y
    elif done == '沒做過' or not blank(t) or not blank(z):
        c['F1'] = N
    else:
        c['F1'] = U
    wall = a.get('wall')  # 題目清單 v2：靠得到／靠不到（＝距離 > 0 cm）
    c['F2'] = Y if wall == '靠不到' else N if wall == '靠得到' else U
    c['F3'] = osta_flag(a)
    sp = a.get('hx_spine_fx')
    c['F4'] = Y if sp == '有' else N if sp == '沒有' else U  # 不確定＝U，提醒教練追問
    steroid = a.get('med_steroid') if not blank(a.get('med_steroid')) else a.get('parq_1c')  # S12 沒出現時自動帶 S37
    b = bmi(a)
    ag = age(a)
    es = a.get('exercise_stage')
    f5 = {
        'F5a': yn(a, 'sym_spine'),
        'F5b': Y if steroid == '是' else N if steroid == '否' else U,
        'F5c': U if blank(es) else Y if es.startswith(('(一)', '(二)')) else N,
        'F5d': sarcopenia(a),
        'F5e': U if b is None else Y if b < 18.5 else N,
        'F5f': U if ag is None else Y if ag > 60 else N,
    }
    ny = sum(v == Y for v in f5.values())
    nu = sum(v == U for v in f5.values())
    c['F5'] = Y if ny >= 2 else N if ny + nu < 2 else U  # 6 選 2；三值合併方式依 v4 空白原則推得
    c['_F5_detail'] = f5
    # 跌倒
    c['L1'] = any_of(parq_follow(a, 'parq_9'), parq_follow(a, 'parq_9b'))
    dx = a.get('dx')
    c['L2'] = U if blank(dx) else Y if NEURO_L2 & set(dx) else N
    s5 = a.get('sts5')
    if blank(s5):
        c['L3'] = U
    elif ag is None:
        c['L3'] = Y if s5 >= 12 else N if s5 < 10 else U
    else:
        c['L3'] = Y if s5 >= (10 if ag < 65 else 12) else N
    w4 = a.get('walk4')
    c['L4'] = U if blank(w4) else Y if w4 > 4 else N  # K14「超過 4 秒」11/6 停用，秒數必填
    c['L5'] = sarcopenia(a)
    g3, g3ab = a.get('parq_g3'), a.get('parq_g3ab') or []
    if g3 == '否':
        c['L6'] = c['S1'] = N
    elif g3 == '是':
        c['L6'] = Y if '因頭暈而失去平衡' in g3ab else (N if g3ab else U)
        c['S1'] = Y if '失去意識' in g3ab else (N if g3ab else U)
    else:
        c['L6'] = c['S1'] = U
    # 癌症
    c['C1'] = any_of(parq_follow(a, 'parq_2'), parq_follow(a, 'parq_2b'))
    # 術後／傷後
    c['P1'] = yn(a, 'parq_g6')
    c['P2'] = parq_follow(a, 'parq_9c')
    c['P3'] = p3(a)
    # 心血管
    sbp, dbp = a.get('sbp'), a.get('dbp')
    c['H1'] = yn(a, 'parq_g1')
    c['H2'] = parq_follow(a, 'parq_3')
    bp_hi = Y if ((not blank(sbp) and sbp >= 160) or (not blank(dbp) and dbp >= 90)) else (U if blank(sbp) or blank(dbp) else N)
    c['H3'] = any_of(parq_follow(a, 'parq_4'), parq_follow(a, 'parq_4b'), bp_hi)
    c['H4'] = yn(a, 'parq_g2')
    c['H5'] = parq_follow(a, 'parq_9')  # 題目清單 v2：S09 拿掉「心血管疾病」→ 只剩 PAR-Q+ 9（待宇劭確認，見 08）
    # 暈厥（S1 在上面）
    c['S2'] = any_of(parq_follow(a, 'parq_5b'), parq_follow(a, 'parq_8b'))
    c['S3'] = U if blank(sbp) else Y if sbp < 90 else N
    # 其他
    c['O1'] = yn(a, 'parq_g7')  # PAR-Q+ 通用 7 自動送；店長勾選另走人工流程（不在本函式）
    return c


def p3(a):
    """有一筆 type＝手術 且 距 fill_date ≤ 12 個月 → Y。月份精度：(填寫年月) − (手術年月) ≤ 12（以月計是推論）。"""
    if a.get('no_surgery_12m') == '是':
        return N
    rows = a.get('surgery') or []
    fd = fill_date(a)
    if not rows:
        return U
    res = N
    for r in rows:
        typ, ym = r.get('type'), r.get('ym')
        if typ == '其他治療':
            continue
        if typ != '手術' or not ym or fd is None:
            res = U if res != Y else res
            continue
        y, m = (int(x) for x in ym.replace('-', '/').split('/')[:2])
        if (fd.year * 12 + fd.month) - (y * 12 + m) <= 12:
            return Y
    return res


CATS = {
    '骨折': ['F1', 'F2', 'F3', 'F4', 'F5'],
    '跌倒': ['L1', 'L2', 'L3', 'L4', 'L5', 'L6'],
    '心血管': ['H1', 'H2', 'H3', 'H4', 'H5'],
    '暈厥': ['S1', 'S2', 'S3'],
    '癌症': ['C1'],
    '術後': ['P1', 'P2', 'P3'],
    '其他': ['O1'],
}


def evaluate(a):
    c = conditions(a)
    out = {}
    for cat, codes in CATS.items():
        trig = [k for k in codes if c[k] == Y]
        unk = [k for k in codes if c[k] == U]
        status = '標記' if trig else '資料未齊' if unk else '未標記'
        out[cat] = dict(status=status, triggers=trig, undetermined=unk)
    return dict(rule_version=RULE_VERSION, categories=out, conditions={k: v for k, v in c.items() if not k.startswith('_')},
                f5_detail=c['_F5_detail'])


if __name__ == '__main__':
    import json, sys
    a = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    print(json.dumps(evaluate(a), ensure_ascii=False, indent=1))
