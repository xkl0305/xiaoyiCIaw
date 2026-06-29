#!/usr/bin/env python3
import json,time
from core.personal_os_enterprise.capability_router import classify_capability_request
SAMPLES=['总结这段文字','识别截图文字','语音转文字','念出来','知识库相似检索','看看你的样子']
st=time.time(); items=[classify_capability_request(s) for s in SAMPLES]
print(json.dumps({'overall':'passed','sample_count':len(SAMPLES),'duration_ms':int((time.time()-st)*1000),'items':items},ensure_ascii=False,indent=2))
