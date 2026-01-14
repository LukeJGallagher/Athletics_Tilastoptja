import sqlite3
import pandas as pd
import re

def is_para(event):
    return bool(re.search(r'\b[TF]\d{2}\b', str(event)))

conn = sqlite3.connect('SQL/athletics_deploy.db')

# Total count
total = pd.read_sql('SELECT COUNT(*) as cnt FROM athletics_data', conn)['cnt'].iloc[0]
print(f'Total rows: {total:,}')

# Sample events
events = pd.read_sql('SELECT DISTINCT eventname FROM athletics_data ORDER BY eventname LIMIT 30', conn)
print(f'\nFirst 30 events (out of {len(events)} total):')
for idx, event in enumerate(events['eventname'], 1):
    marker = 'PARA' if is_para(event) else 'OK'
    print(f'  {idx:2d}. [{marker:4s}] {event}')

conn.close()
