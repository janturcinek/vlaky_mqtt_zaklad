import sqlite3
from nastaveni import DevelopmentConfig
conn = sqlite3.connect(DevelopmentConfig.DATABASE)
c = conn.cursor()
c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
for row in c.fetchall():
    print(f"-- {row[0]}")
    print(row[1])
    print()
conn.close()
