import sqlite3
import pandas as pd
conn = sqlite3.connect('..\storage\sql_app.db')
df = pd.read_sql_query('SELECT * FROM scans ORDER BY created_at DESC LIMIT 5', conn)
for idx, row in df.iterrows():
    print(f"Scan {row['id']}: {row['image_path']}")
