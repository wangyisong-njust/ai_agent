import json

with open('D:/code/PythonProject_New/AI_agent/wavespeed_models.json', encoding='utf-8') as f:
    data = json.load(f)

print('HTTP Code:', data.get('code'))
print('Message:', data.get('message'))
models = data.get('data', [])
print(f'Total models: {len(models)}')
print()

# Filter for LLM / text generation models
llm_keywords_type = ['text', 'llm', 'chat', 'language']
llm_keywords_id = ['llm', 'gpt', 'claude', 'llama', 'gemini', 'mistral', 'qwen', 'deepseek', 'any-llm', 'phi', 'falcon']

llm_models = [
    m for m in models
    if any(kw in m.get('type', '').lower() for kw in llm_keywords_type)
    or any(kw in m.get('model_id', '').lower() for kw in llm_keywords_id)
    or any(kw in m.get('name', '').lower() for kw in llm_keywords_id)
]

print(f'LLM/Text models found: {len(llm_models)}')
print()
for m in llm_models:
    print(f"  model_id : {m['model_id']}")
    print(f"  name     : {m['name']}")
    print(f"  type     : {m.get('type', 'N/A')}")
    print(f"  price    : {m.get('base_price', 'N/A')}")
    print(f"  desc     : {m.get('description', '')[:150]}")
    print()

# Also print all unique types to understand the taxonomy
print("\n--- All unique model types ---")
types = sorted(set(m.get('type', 'unknown') for m in models))
for t in types:
    count = sum(1 for m in models if m.get('type') == t)
    print(f"  {t}: {count} models")
