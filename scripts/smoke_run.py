"""실제 LLM 스모크: 합성 메일을 Supervisor 에 통과시켜 분류 결과·초안을 확인 (Gmail 접근 없음, FakeMailbox 사용)."""
import sys
import time

from evals.synthetic import SYNTHETIC
from mail_agent.llm import make_chat_model
from mail_agent.platform import build_platform
from mail_agent.security.sanitize import sanitize
from mail_agent.settings import get_settings
from mail_agent.tools.mailbox import FakeMailbox

get_settings()
ids = set(sys.argv[1:])
items = [x for x in SYNTHETIC if not ids or x["raw"].id in ids]
mb = FakeMailbox([x["raw"] for x in items])
p = build_platform(mb, make_chat_model)
ok = 0
for x in items:
    raw = x["raw"]
    t0 = time.time()
    res = p.supervisor.start(f"smoke-{raw.id}", sanitize(raw))
    cls = res["artifacts"].get("classification", {})
    match = cls.get("label") == x["expected"]
    ok += match
    print(f"{'✓' if match else '✗'} {raw.id} [{x['edge']:<20}] expected={x['expected']:<13} got={cls.get('label','-'):<13} conf={cls.get('confidence',0):.2f} status={res['status']:<14} {time.time()-t0:4.1f}s")
    if "draft" in res["artifacts"]:
        rv = res["artifacts"].get("review", {})
        print(f"    review={'PASS' if rv.get('passed') else 'FAIL ' + str(rv.get('issues'))}\n    draft: " + res['artifacts']['draft']['body'].replace('\n', '\n           '))
print(f"\n분류 일치 {ok}/{len(items)} · 생성된 Gmail 초안(가짜) {len(mb.drafts)}개 · 감사로그 {len(p.gateway.audit)}건 (허용 {sum(a.allowed for a in p.gateway.audit)})")
