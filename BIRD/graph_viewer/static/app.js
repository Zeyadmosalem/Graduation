async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

const qs = (sel) => document.querySelector(sel);

async function loadMeta() {
  const meta = await api('/api/meta');
  const splitSel = qs('#split');
  const dbSel = qs('#db');
  const split = splitSel.value;
  dbSel.innerHTML = '';
  (meta.meta[split] || []).forEach(({ db_id, count }) => {
    const opt = document.createElement('option');
    opt.value = db_id; opt.textContent = `${db_id} (${count})`;
    dbSel.appendChild(opt);
  });
}

async function loadList() {
  const split = qs('#split').value;
  const db = qs('#db').value;
  const search = qs('#search').value.trim().toLowerCase();
  const data = await api(`/api/list?split=${encodeURIComponent(split)}&db_id=${encodeURIComponent(db)}`);
  const list = qs('#list');
  list.innerHTML = '';
  (data.rows || []).forEach((r) => {
    if (search) {
      const hay = `${r.question_en} ${r.SQL}`.toLowerCase();
      if (!hay.includes(search)) return;
    }
    const div = document.createElement('div');
    div.className = 'item';
    div.textContent = r.question_en || '(no question)';
    div.addEventListener('click', () => showItem(split, r.idx));
    list.appendChild(div);
  });
}

function renderGraph(g) {
  const nodesDiv = qs('#nodes');
  const edgesDiv = qs('#edges');
  nodesDiv.innerHTML = '';
  edgesDiv.innerHTML = '';
  (g.nodes || []).forEach((n) => {
    const sec = document.createElement('div');
    const title = document.createElement('div');
    title.innerHTML = `<strong>${n.table_name}</strong>`;
    const cols = document.createElement('ul');
    (n.columns || []).forEach((c) => {
      const li = document.createElement('li');
      li.textContent = c.description ? `${c.name}: ${c.description}` : c.name;
      cols.appendChild(li);
    });
    sec.appendChild(title);
    sec.appendChild(cols);
    nodesDiv.appendChild(sec);
  });
  (g.edges || []).forEach((e) => {
    const div = document.createElement('div');
    const d = e.description ? ` (${e.description})` : '';
    div.textContent = `${e.child_table}.${e.child_column} → ${e.parent_table}.${e.parent_column}${d}`;
    edgesDiv.appendChild(div);
  });
}

async function showItem(split, idx) {
  const rec = await api(`/api/item?split=${encodeURIComponent(split)}&idx=${idx}`);
  qs('#meta').textContent = `db: ${rec.db_id}`;
  qs('#question').textContent = (rec.question_en || '') + (rec.question_ar ? `\nAR: ${rec.question_ar}` : '');
  qs('#sql').textContent = rec.SQL || '';
  qs('#context').textContent = rec.context_text || '';
  renderGraph(rec.gold_graph || { nodes: [], edges: [] });
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadMeta();
  await loadList();
  qs('#split').addEventListener('change', async () => { await loadMeta(); await loadList(); });
  qs('#db').addEventListener('change', loadList);
  qs('#refresh').addEventListener('click', loadList);
  qs('#search').addEventListener('input', loadList);
});

