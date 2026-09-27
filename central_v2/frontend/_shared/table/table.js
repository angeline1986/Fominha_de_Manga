export function createTable(columns, rows, label) {
  const table = document.createElement("table");
  table.className = "data-table";
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
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value == null ? "—" : String(value);
    }
  }
  return table;
}
