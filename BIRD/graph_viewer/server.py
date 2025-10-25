import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
TMP = STATIC / "_tmp"


def load_gold(split: str):
    if split == "train":
        p = ROOT / "train" / "train_gold_graphs.json"
    else:
        p = ROOT / "dev_20240627" / "dev_gold_graphs.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


DATA = {
    "train": load_gold("train"),
    "dev": load_gold("dev"),
}


def build_index(records):
    idx = {}
    for i, r in enumerate(records):
        db = r.get("db_id", "")
        idx.setdefault(db, []).append(i)
    return idx


INDEX = {
    "train": build_index(DATA["train"]),
    "dev": build_index(DATA["dev"]),
}


class App(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path == "/" or path.startswith("/static/"):
            if path == "/":
                return str(STATIC / "index.html")
            return str(STATIC / path[len("/static/"):])
        return super().translate_path(path)

    def _json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/meta":
            meta = {}
            for split in ("train", "dev"):
                dbs = [
                    {"db_id": db, "count": len(INDEX[split][db])}
                    for db in sorted(INDEX[split].keys())
                ]
                meta[split] = dbs
            self._json({"meta": meta})
            return

        if parsed.path == "/graph":
            qs = parse_qs(parsed.query)
            split = (qs.get("split", [""])[0] or "train").lower()
            try:
                idx = int(qs.get("idx", [""])[0])
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing idx")
                return
            records = DATA.get(split) or []
            if not (0 <= idx < len(records)):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return
            rec = records[idx]
            try:
                from pyvis.network import Network
            except Exception as e:
                html = f"""
                <html><body>
                <h3>pyvis is not installed</h3>
                <p>Please install: <code>pip install pyvis</code></p>
                <pre>{e}</pre>
                </body></html>
                """
                data = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            TMP.mkdir(parents=True, exist_ok=True)
            net = Network(height="600px", width="100%", directed=False, bgcolor="#ffffff", font_color="#222")
            net.toggle_physics(True)

            g = rec.get("gold_graph") or {"nodes": [], "edges": []}
            # Add nodes with column tooltips
            for n in g.get("nodes", []):
                t = n.get("table_name", "")
                cols = n.get("columns", [])
                tip = "<br/>".join(
                    [f"<b>{c.get('name','')}</b> : {c.get('description','')}" if c.get('description') else f"{c.get('name','')}" for c in cols]
                )
                net.add_node(t, label=t, shape="box", title=tip)

            # Add edges with labels and titles
            for e in g.get("edges", []):
                u = e.get("child_table"); v = e.get("parent_table")
                if not u or not v:
                    continue
                label = f"{e.get('child_column','')} → {e.get('parent_column','')}"
                title = e.get("description", "")
                net.add_edge(u, v, label=label, title=title)

            out_file = TMP / f"{split}_{idx}.html"
            net.save_graph(str(out_file))
            data = out_file.read_text(encoding="utf-8").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == "/api/list":
            qs = parse_qs(parsed.query)
            split = (qs.get("split", [""])[0] or "train").lower()
            db_id = qs.get("db_id", [None])[0]
            records = DATA.get(split) or []
            if db_id:
                ids = INDEX.get(split, {}).get(db_id, [])
                rows = [{
                    "idx": i,
                    "db_id": records[i].get("db_id"),
                    "question_en": records[i].get("question_en", ""),
                    "question_ar": records[i].get("question_ar", ""),
                    "SQL": records[i].get("SQL", ""),
                } for i in ids]
            else:
                rows = [{
                    "idx": i,
                    "db_id": r.get("db_id"),
                    "question_en": r.get("question_en", ""),
                    "question_ar": r.get("question_ar", ""),
                    "SQL": r.get("SQL", ""),
                } for i, r in enumerate(records)]
            self._json({"rows": rows})
            return

        if parsed.path == "/api/item":
            qs = parse_qs(parsed.query)
            split = (qs.get("split", [""])[0] or "train").lower()
            try:
                idx = int(qs.get("idx", [""])[0])
            except Exception:
                self._json({"error": "missing idx"}, status=400)
                return
            records = DATA.get(split) or []
            if 0 <= idx < len(records):
                self._json(records[idx])
            else:
                self._json({"error": "out_of_range"}, status=404)
            return

        return super().do_GET()


def run(addr="127.0.0.1", port=8081):
    httpd = HTTPServer((addr, port), App)
    print(f"Graph viewer at http://{addr}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
