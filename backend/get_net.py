import json

def get_netqty():
    with open('soya_netqty.log', 'r', encoding='utf-8') as f:
        content = f.read()
        start = content.find('Final Verdicts: [')
        end = content.find(']', start) + 1
        j = json.loads(content[start+16:end])
        for v in j:
            if v.get('field_type') == 'net_quantity':
                return v

print(json.dumps(get_netqty(), indent=2))
