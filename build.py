#!/usr/bin/env python3
"""data.txt (+ materials/*.txt) -> index.html 안의 MATS 배열로 변환한다.

사용법: python3 build.py
index.html 은 서버 없이 더블클릭으로 열리므로 학습 자료를 파일에 직접 내장한다.
자료를 고친 뒤에는 이 스크립트를 다시 실행하면 된다.
"""
import glob, hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, 'index.html')

# 헤더([...]) → 시대. 위에서부터 첫 매칭.
SECTION_ERA = [
    (r'^(고구려|백제|신라|삼국)', '삼국'),
    (r'^(통일신라|발해|후백제|후고구려)', '남북국'),
    (r'^고려', '고려'),
    (r'^조선 말기', '근대'),
    (r'^조선', '조선 전기'),
    (r'^(1920년대|1930년대|1940)', '일제강점기'),
    (r'^광복', '현대'),
]
LATE_TERM = re.compile(
    r'후기|광해군|인조|효종|현종|숙종|경종|영조|정조|순조|철종|세도|실학|대동법|균역|환국|예송|'
    r'어영청|금위영|송상|통신사|정선|안정복|박제가|이덕무|정약용|김정희|정약전|유형원|정상기|'
    r'이제마|이익|박지원|유수원|김홍도|양명학|천하공물설|윤휴|호론|낙론|노론|인왕제색도|영통골|'
    r'옥순봉도|매화초옥도|채제공|비변사|영정법|전황|이앙법|인삼|고구마')
JIL_TERM = re.compile(
    r'^(신채호|박은식|안창호|독립의군부|의열단|한용운|조선광문회|하와이|북간도|토지조사사업|'
    r'신흥무관학교|대종교|원불교|불교|대한민국 임시정부|한글 관련|19\d0년대)')


def split_top(s):
    """괄호 밖의 쉼표로만 나눈다."""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '([': depth += 1
        elif ch in ')]': depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    out.append(cur)
    return [x.strip().rstrip('\\').strip() for x in out if x.strip().rstrip('\\').strip()]


def norm(t):
    return re.sub(r'\s+', '', re.sub(r'\(.*?\)', '', t))


def parse(path):
    facts = []
    era, group, after1910 = '선사·고조선', '', False
    for raw in open(path, encoding='utf-8'):
        line = raw.strip().rstrip('\\').strip()
        if not line or line[0] in '*<(':
            continue
        m = re.match(r'^\[(.+?)\]\s*$', line)
        if m:
            group = re.split(r'[(~]', m.group(1))[0].strip()
            after1910 = False
            for pat, e in SECTION_ERA:
                if re.match(pat, m.group(1)):
                    era = e; break
            continue
        if line.startswith('1910 이후'):
            era, group, after1910 = '근대', '', True
            continue

        year, body = None, line
        ym = re.match(r'^(\d{4})(?:\.\d{1,2})?\s+(.*)$', line)
        if ym:
            year, body = int(ym.group(1)), ym.group(2)

        cm = re.search(r'[:：]', body)
        if cm:
            term, desc = body[:cm.start()].strip(), body[cm.end():].strip()
            tm = re.split(r'\s\d{4}\s', term)   # "… 1931 조선어학회" 처럼 한 줄에 두 항목이 붙은 경우
            term = tm[-1].strip()
        else:
            term, desc = body.strip(), ''
            if year is None or len(term) > 30:      # 연도도 설명도 없는 줄은 문제로 못 만든다
                continue
        if not term or len(term) > 40:
            continue

        # 시대 결정
        e = era
        if era == '조선 전기':
            if term.startswith('고종'): e = '근대'
            elif re.search(r'말기', term): e = '근대'
            elif LATE_TERM.search(term): e = '조선 후기'
        if era in ('근대', '일제강점기'):
            if year is not None: e = '근대' if year < 1910 else '일제강점기'
            if after1910 and JIL_TERM.match(term): e = '일제강점기'
            if re.match(r'^19[1-4]0년대', term): e = '일제강점기'
        items = split_top(desc) if desc else []
        facts.append({'era': e, 'term': term, 'items': items, 'year': year, 'group': group})
    return facts


def merge(facts):
    by = {}
    for f in facts:
        by.setdefault(norm(f['term']), []).append(f)
    out = []
    for _, fs in by.items():
        subs = {}
        for f in fs:
            subs.setdefault((f['era'], f['group']), []).append(f)
        groups = {k[1] for k in subs}
        for (era, group), g in subs.items():
            items, year = [], None
            for f in g:
                for it in f['items']:
                    if it not in items: items.append(it)
                year = year if year is not None else f['year']
            term = g[0]['term']
            if len(subs) > 1:
                label = group if len(groups) > 1 and group else era
                if label and not term.startswith(label):
                    term = f'{label} {term}'
            out.append({'era': era, 'term': term, 'items': items, 'year': year, 'group': group})
    return out


def main():
    srcs = [p for p in [os.path.join(ROOT, 'data.txt')] + sorted(glob.glob(os.path.join(ROOT, 'materials', '*.txt'))) if os.path.exists(p)]
    facts = []
    for p in srcs:
        facts += parse(p)
    facts = merge(facts)
    rows, seen = [], set()
    for f in facts:
        fid = 'm' + hashlib.sha1((f['era'] + '|' + f['term']).encode()).hexdigest()[:8]
        if fid in seen: continue
        seen.add(fid)
        desc = ', '.join('[[%s]]' % it for it in f['items'])
        rows.append([fid, f['era'], f['term'], desc, f['year'], f['group']])
    block = '/*MAT_START*/\nconst MATS=[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows) + \
        '\n].map(r=>({id:r[0],era:r[1],term:r[2],desc:r[3],year:r[4],group:r[5],list:!!r[3],src:\'mat\'}));\n/*MAT_END*/'
    html = open(HTML, encoding='utf-8').read()
    new, n = re.subn(r'/\*MAT_START\*/.*?/\*MAT_END\*/', lambda _: block, html, flags=re.S)
    if n != 1:
        sys.exit('index.html 에서 /*MAT_START*/ … /*MAT_END*/ 구간을 찾지 못했습니다.')
    open(HTML, 'w', encoding='utf-8').write(new)
    from collections import Counter
    c = Counter(r[1] for r in rows)
    print(f'{len(rows)}개 항목 ({", ".join(os.path.basename(s) for s in srcs)})')
    for k, v in c.most_common(): print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
