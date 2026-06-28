from __future__ import annotations
import os
try:
    from infrastructure.offline_runtime_guard import activate; activate()
except Exception: pass
def get_connector(name, mode='auto'):
    return {'name':name,'status':'mock' if os.environ.get('NO_EXTERNAL_API')=='true' else 'deferred','mode':'offline_mock' if os.environ.get('NO_EXTERNAL_API')=='true' else mode,'real_external_call':False}
def call(connector, request=None): return {'status':'ok','connector':connector,'request':request or {},'mode':'mock','real_external_call':False}
