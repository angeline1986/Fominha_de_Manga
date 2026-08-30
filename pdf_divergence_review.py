from __future__ import annotations
import json, re
from pathlib import Path
LABELS={"image_validation_failed":"Imagem incompatível","pdf_page_count_mismatch":"Páginas do PDF divergentes","pdf_validation_failed":"Validação do PDF","download_not_completed":"Download em andamento","download_state_invalid":"Estado de download inválido"}
def load_reports(manga_dir):
    d=Path(manga_dir)/"reports"
    if not d.is_dir(): return []
    out=[]
    for p in d.glob("*.validation.json"):
        try: data=json.loads(p.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): data={"chapter":p.name.removesuffix(".validation.json"),"issue_type":"invalid_report","message":"Relatório inválido ou ilegível."}
        out.append((p,data))
    return sorted(out,key=lambda x:[int(v) if v.isdigit() else v.lower() for v in re.split(r"(\d+)",str(x[1].get("chapter") or x[0].stem))])
def build_analysis(data):
    ch=str(data.get("chapter") or "?"); issue=str(data.get("issue_type") or ""); images=data.get("images") or {}; pdf=data.get("pdf") or {}; exp=images.get("expected"); found=images.get("found"); meta=images.get("metadata") or []
    bad=[]
    for e in images.get("errors") or []:
        for n in re.findall(r"page-\d+\.[A-Za-z0-9]+",str(e),re.I):
            if n not in bad: bad.append(n)
    by={str(x.get("file")):x for x in meta if isinstance(x,dict)}; nums=[]
    for x in meta:
        m=re.match(r"^page-(\d+)\.[^.]+$",str(x.get("file") or ""),re.I)
        if m: nums.append(int(m.group(1)))
    nums.sort(); seq=isinstance(exp,int) and exp>0 and nums==list(range(1,exp+1)); complete=isinstance(exp,int) and isinstance(found,int) and exp==found and (not nums or seq)
    lines=[f"CAPÍTULO {ch} — {'PDF GERADO' if data.get('pdf_generated') else 'PDF NÃO GERADO'}","","Validação do capítulo"]
    if isinstance(exp,int) and isinstance(found,int): lines.append(f"{'✓' if exp==found else '✕'} {found} de {exp} páginas encontradas")
    elif isinstance(found,int): lines.append(f"✓ {found} páginas encontradas")
    if nums and isinstance(exp,int): lines.append("✓ Sequência completa" if seq else "✕ Sequência de páginas divergente")
    if isinstance(found,int) and found>0 and len(meta)==found: lines.append("✓ Imagens legíveis")
    lines += ["","Divergência"]
    if issue=="image_validation_failed" and bad:
        for fn in bad:
            item=by.get(fn,{}); lines.append(f"✕ {fn}")
            if item:
                lines.append(f"  Dimensão da imagem: {item.get('width')}x{item.get('height')}")
                if item.get("pdf_width") is not None and item.get("pdf_height") is not None: lines.append(f"  Dimensão no PDF: {float(item['pdf_width']):.2f}x{float(item['pdf_height']):.2f}")
            lines.append("  Motivo: altura/dimensão abaixo do mínimo permitido")
    elif issue=="pdf_page_count_mismatch": lines.append(f"✕ Quantidade de páginas do PDF divergente: esperado {pdf.get('expected_pages')}, encontrado {pdf.get('found_pages')}")
    else: lines.append(f"✕ {data.get('message') or 'Divergência registrada.'}")
    lines += ["","Conclusão"]
    if issue=="image_validation_failed" and complete:
        lines += ["O capítulo está completo.","A geração do PDF foi bloqueada por uma única imagem incompatível" if len(bad)==1 else f"A geração do PDF foi bloqueada por {len(bad)} imagens incompatíveis","com a regra de segurança do PDF."]
    elif issue=="pdf_page_count_mismatch": lines += ["As imagens do capítulo foram validadas.","O PDF gerado apresentou quantidade de páginas divergente."]
    elif issue=="download_not_completed": lines += ["O capítulo ainda estava em download.","A geração do PDF foi bloqueada para evitar um arquivo incompleto."]
    elif issue=="download_state_invalid": lines += ["O estado persistente do capítulo não pôde ser validado.","A geração do PDF foi bloqueada por segurança."]
    else: lines.append(str(data.get("message") or "A divergência requer revisão."))
    lines += ["","Ação sugerida"]
    if issue=="image_validation_failed" and bad:
        pages=[str(int(m.group(1))) for fn in bad if (m:=re.search(r"page-(\d+)",fn,re.I))]
        lines.append(f"Revisar visualmente a página {pages[0]} antes de decidir por exceção/correção." if len(pages)==1 else "Revisar visualmente as páginas divergentes antes de decidir por exceção/correção.")
    elif issue=="pdf_page_count_mismatch": lines.append("Comparar a quantidade de imagens com as páginas do PDF antes de gerar novamente.")
    elif issue=="download_not_completed": lines.append("Aguardar a conclusão do download antes de gerar o PDF.")
    elif issue=="download_state_invalid": lines.append("Revisar o estado do capítulo antes de tentar gerar o PDF.")
    else: lines.append("Revisar os detalhes técnicos do relatório.")
    return lines
def run_divergence_review(manga_dir,*,ask_number,print_header,c):
    reports=load_reports(manga_dir)
    if not reports:
        print(c("warning","Nenhuma divergência registrada para esta obra.")); print(c("muted",f"└─ {Path(manga_dir)/'reports'}")); return
    while True:
        print_header("VALIDAR DIVERGÊNCIAS")
        for i,(p,data) in enumerate(reports,1):
            ch=str(data.get("chapter") or p.name.removesuffix(".validation.json")); label=LABELS.get(str(data.get("issue_type") or ""),str(data.get("issue_type") or "Divergência")); print(f"  {c('number',str(i)+'.',bold=True)} {('Capítulo '+ch):<24} {c('muted',label)}")
        print(); print(f"  {c('number','0.',bold=True)} Voltar"); choice=ask_number("\nSelecione a divergência › ",range(0,len(reports)+1))
        if choice==0:return
        print(); [print(x) for x in build_analysis(reports[choice-1][1])]; print(); input(c("prompt","Pressione Enter para voltar › ",bold=True))
