from pathlib import Path
import duckdb

DB="data/scout_web_02c.duckdb"

def load():
    Path("data").mkdir(exist_ok=True)
    con=duckdb.connect(DB)
    con.execute("CREATE OR REPLACE TABLE evidence_passports AS SELECT * FROM read_json_auto('data/normalized/evidence_passports.jsonl', format='newline_delimited')")
    con.execute("CREATE OR REPLACE TABLE trade_events AS SELECT * FROM read_json_auto('data/normalized/trade_events.jsonl', format='newline_delimited')")
    con.execute("CREATE OR REPLACE TABLE graph_proposals AS SELECT * FROM read_json_auto('data/normalized/graph_proposals.jsonl', format='newline_delimited')")
    print(con.execute("SELECT count(*) FROM evidence_passports").fetchone())
    con.close()

if __name__=="__main__":
    load()
