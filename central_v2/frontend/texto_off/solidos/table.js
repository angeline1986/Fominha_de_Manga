import { iconMarkup } from "/_shared/icons/icons.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls, createPageSizeControl } from "/_shared/pagination/pagination.js";

function check(label,checked,disabled,onChange) {
  const element=document.createElement("input");
  element.type="checkbox"; element.checked=checked; element.disabled=disabled;
  element.setAttribute("aria-label",label);
  element.addEventListener("change",()=>onChange(element.checked));
  return element;
}
export function createSolidTable(container,actions) {
  const pagination=createPagination(13);
  const sizeControl=createPageSizeControl(() => actions.changePage(0));
  return {draw(rows,selected,page,busy) {
    container.replaceChildren();
    pagination.reset();
    for(let i=0;i<page;i++) pagination.move(1);
    const view=pagination.select(rows);
    const eligible=view.rows.filter(row=>!row.processed).map(row=>row.chapter);
    const columns=[
      { id:"select",header:()=>check("Selecionar todos desta página",
          eligible.length>0&&eligible.every(x=>selected.has(x)),
          busy||!eligible.length,v=>actions.onSelectPage(eligible,v)),
        render:row=>check(`Selecionar capítulo ${row.chapter}`,
          selected.has(row.chapter),busy||row.processed,
          v=>actions.onSelect(row.chapter,v)) },
      {id:"chapter",label:"CAPÍTULO",render:row=>row.chapter},
      {id:"merges",label:"MERGES",render:row=>row.merge_count??"—"},
      {id:"regions",label:"ÁREAS SÓLIDAS",render:row=>String(row.regions)},
      {id:"pending",label:"PENDENTES",render:row=>row.processed?"—":String(row.regions)},
      {id:"done",label:"CONCLUÍDAS",render:row=>row.processed?"✓":"—"},
      {id:"status",label:"STATUS",render:row=>row.processed?"Prévia disponível":"Pendente"},
      {id:"inspect",label:"VISUALIZAR",render:row=>{
        const button=document.createElement("button");
        button.type="button";button.className="btn comparison-open";
        button.title="Visualizar capítulo";
        button.setAttribute("aria-label",`Visualizar capítulo ${row.chapter}`);
        button.innerHTML=iconMarkup("eye");button.disabled=!row.processed;
        button.addEventListener("click",()=>actions.inspect(row));
        return button;
      }},
    ];
    container.append(createTable(columns,view.rows,"Capítulos do Auto-Cleaner Sólidos",{
      emptyMessage:"Nenhum capítulo corresponde ao filtro."
    }));
    container.append(createPaginationControls(view,delta=>actions.changePage(page+delta),
      {leading:sizeControl.element}));
  }};
}
