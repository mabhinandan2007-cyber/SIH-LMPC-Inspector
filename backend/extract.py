import json

def extract_netqty_result(log_path):
    with open(log_path, 'r', encoding='utf-16') as f:
        content = f.read()
        try:
            # find Final Verdicts: [ ... ]
            start = content.find('Final Verdicts: [')
            if start == -1: return "Not found"
            
            end = content.find(']', start) + 1
            json_str = content[start + 16:end]
            # It's an array of dicts
            verdicts = json.loads(json_str)
            for v in verdicts:
                if v.get('field_type') == 'net_quantity':
                    return json.dumps(v, indent=2)
            return "No net_quantity verdict"
        except Exception as e:
            return f"Error: {e}"

print("Soya:")
print(extract_netqty_result('soya_netqty.log'))
print("\nPatanjali:")
print(extract_netqty_result('patanjali_netqty.log'))
