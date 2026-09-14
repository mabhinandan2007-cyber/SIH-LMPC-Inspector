import requests

try:
    r1 = requests.get('http://localhost:8000/api/scans/1/report')
    with open('scan_1_passed.pdf', 'wb') as f:
        f.write(r1.content)
    print("Scan 1 PDF saved:", len(r1.content), "bytes")
    
    r2 = requests.get('http://localhost:8000/api/scans/2/report')
    with open('scan_2_uncertain.pdf', 'wb') as f:
        f.write(r2.content)
    print("Scan 2 PDF saved:", len(r2.content), "bytes")
except Exception as e:
    print(e)
