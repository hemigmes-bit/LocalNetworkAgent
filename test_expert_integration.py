import sys
sys.path.insert(0, 'python/src/main/python')
import emma_tools

q = 'how does a blockchain work'
out = emma_tools.gather_tool_context(q, lang='en', model='qwen3.5:9b')
print('Keys:', list(out.keys()))
print('USED:', out['used'])
print('SOURCES:', len(out['sources']))
for s in out['sources'][:3]:
    print(f'  - {s.get("site")} | {s.get("kind")} | {s.get("title")[:80]}')
print()
if out['sources']:
    print('First source payload:')
    print(out['sources'][0])