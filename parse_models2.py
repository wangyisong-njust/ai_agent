import json

with open('D:/code/PythonProject_New/AI_agent/wavespeed_models.json', encoding='utf-8') as f:
    data = json.load(f)

print('HTTP Code:', data.get('code'))
print('Message:', data.get('message'))
models = data.get('data', [])
print(f'Total models: {len(models)}')

# Print all unique types to understand the taxonomy
print("\n--- All unique model types and counts ---")
types = sorted(set(m.get('type', 'unknown') for m in models))
for t in types:
    count = sum(1 for m in models if m.get('type') == t)
    print(f"  {t}: {count} models")

print()
print("=" * 70)
print("LLM / Text Generation models only")
print("=" * 70)

# Filter strictly for LLM text generation (not text-to-image/video)
llm_types = ['llm', 'text-generation', 'chat', 'language-model', 'text']
llm_id_keywords = ['any-llm', 'llm']

llm_models = [
    m for m in models
    if m.get('type', '').lower() in llm_types
    or any(kw in m.get('model_id', '').lower() for kw in llm_id_keywords)
]

print(f'\nStrict LLM models found: {len(llm_models)}')
print()
for m in llm_models:
    print(f"  model_id : {m['model_id']}")
    print(f"  name     : {m['name']}")
    print(f"  type     : {m.get('type', 'N/A')}")
    print(f"  price    : {m.get('base_price', 'N/A')}")
    print(f"  desc     : {m.get('description', '')[:200]}")
    # Show API path if available
    api_schema = m.get('api_schema', {})
    schemas = api_schema.get('api_schemas', [])
    for s in schemas:
        if s.get('api_path'):
            print(f"  api_path : {s['api_path']}")
            break
    print()
