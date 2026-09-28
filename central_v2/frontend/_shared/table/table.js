export function createTable(columns, rows, label, { emptyMessage } = {}) {
  const table = document.createElement("table");
  table.className = "data-table";
  table.dataset.columnCount = String(columns.length);
  table.setAttribute("aria-label", label);
  const head = table.createTHead().insertRow();
  for (const column of columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    if (column.header) cell.append(column.header());
    else cell.textContent = column.label;
    head.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const column of columns) {
      const cell = tr.insertCell();
      if (column.className) cell.className = column.className(row);
      const value = column.render(row);
      if (column.title) cell.title = String(column.title(row) ?? "");
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value == null ? "—" : String(value);
    }
  }
  if (!rows.length && emptyMessage) {
    const tr = body.insertRow();
    const cell = tr.insertCell();
    cell.colSpan = columns.length;
    cell.className = "data-table-empty";
    cell.textContent = emptyMessage;
  }
  return table;
}
