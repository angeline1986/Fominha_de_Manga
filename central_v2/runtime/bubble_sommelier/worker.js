const ort = require("onnxruntime-node");
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SIZE=640, THRESHOLD=0.30, GRID=12, TOLERANCE=42;
const MIN_COVERAGE=0.75, MIN_LUMA_MAD=1.0;

function arg(name){ const i=process.argv.indexOf(name); return i>=0 ? process.argv[i+1] : null; }
const INPUT=arg("--input"), MODEL=arg("--model"), OUTPUT=arg("--output"), CHAPTER=arg("--chapter");
if(!INPUT || !MODEL || !OUTPUT || !CHAPTER) throw new Error("Uso: worker.js --input DIR --model detector.onnx --output report.json --chapter N");

function median(values){ if(!values.length) return 0; const a=[...values].sort((x,y)=>x-y), m=Math.floor(a.length/2); return a.length%2?a[m]:(a[m-1]+a[m])/2; }
function mad(values){ const m=median(values); return median(values.map(v=>Math.abs(v-m))); }
function dist(r,g,b,ref){ return Math.sqrt((r-ref.r)**2+(g-ref.g)**2+(b-ref.b)**2); }
function iou(a,b){
  const x1=Math.max(a.x1,b.x1), y1=Math.max(a.y1,b.y1), x2=Math.min(a.x2,b.x2), y2=Math.min(a.y2,b.y2);
  const inter=Math.max(0,x2-x1)*Math.max(0,y2-y1);
  const aa=Math.max(0,a.x2-a.x1)*Math.max(0,a.y2-a.y1), ab=Math.max(0,b.x2-b.x1)*Math.max(0,b.y2-b.y1);
  return inter/(aa+ab-inter+1e-6);
}

async function detect(session,input){
  const meta=await sharp(input).metadata(), tileSize=meta.width, stride=Math.round(tileSize*.75);
  let detections=[];
  for(let top=0;top<meta.height;top+=stride){
    const height=Math.min(tileSize,meta.height-top); if(height<200) break;
    const {data}=await sharp(input).extract({left:0,top,width:meta.width,height})
      .resize(SIZE,SIZE,{fit:"contain",background:{r:0,g:0,b:0}}).removeAlpha().raw().toBuffer({resolveWithObject:true});
    const tensorData=new Float32Array(3*SIZE*SIZE), plane=SIZE*SIZE;
    for(let y=0;y<SIZE;y++) for(let x=0;x<SIZE;x++){
      const src=(y*SIZE+x)*3,dst=y*SIZE+x;
      tensorData[dst]=data[src]/255; tensorData[plane+dst]=data[src+1]/255; tensorData[2*plane+dst]=data[src+2]/255;
    }
    const outputs=await session.run({
      images:new ort.Tensor("float32",tensorData,[1,3,SIZE,SIZE]),
      orig_target_sizes:new ort.Tensor("int64",BigInt64Array.from([BigInt(height),BigInt(meta.width)]),[1,2])
    });
    const labels=outputs.labels.data, boxes=outputs.boxes.data, scores=outputs.scores.data;
    for(let i=0;i<scores.length;i++){
      const score=Number(scores[i]), label=Number(labels[i]); if(score<THRESHOLD || label!==0) continue;
      const b=i*4;
      const d={label,score,x1:Math.max(0,Math.min(meta.width,Number(boxes[b]))),
        y1:Math.max(0,Math.min(meta.height,Number(boxes[b+1])+top)),
        x2:Math.max(0,Math.min(meta.width,Number(boxes[b+2]))),
        y2:Math.max(0,Math.min(meta.height,Number(boxes[b+3])+top))};
      if(d.x2>d.x1 && d.y2>d.y1) detections.push(d);
    }
  }
  detections.sort((a,b)=>b.score-a.score); const kept=[];
  for(const d of detections) if(!kept.some(k=>iou(d,k)>.50)) kept.push(d);
  return kept;
}

async function analyzeRegion(input,box){
  const left=Math.floor(box.x1), top=Math.floor(box.y1), width=Math.max(1,Math.ceil(box.x2)-left), height=Math.max(1,Math.ceil(box.y2)-top);
  const {data,info}=await sharp(input).extract({left,top,width,height}).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const cx0=Math.floor(info.width*.40),cx1=Math.ceil(info.width*.60),cy0=Math.floor(info.height*.40),cy1=Math.ceil(info.height*.60);
  const cr=[],cg=[],cb=[];
  for(let y=cy0;y<cy1;y++) for(let x=cx0;x<cx1;x++){ const i=(y*info.width+x)*info.channels; cr.push(data[i]);cg.push(data[i+1]);cb.push(data[i+2]); }
  const ref={r:median(cr),g:median(cg),b:median(cb)};
  const x0=Math.floor(info.width*.10),x1=Math.ceil(info.width*.90),y0=Math.floor(info.height*.10),y1=Math.ceil(info.height*.90);
  let accepted=0,total=0; const cells=[];
  for(let gy=0;gy<GRID;gy++) for(let gx=0;gx<GRID;gx++){
    const ax0=Math.floor(x0+(x1-x0)*gx/GRID),ax1=Math.floor(x0+(x1-x0)*(gx+1)/GRID);
    const ay0=Math.floor(y0+(y1-y0)*gy/GRID),ay1=Math.floor(y0+(y1-y0)*(gy+1)/GRID);
    const l=[]; let cellTotal=0,cellAccepted=0;
    for(let y=ay0;y<ay1;y++) for(let x=ax0;x<ax1;x++){ const i=(y*info.width+x)*info.channels,r=data[i],g=data[i+1],b=data[i+2]; total++;cellTotal++;
      if(dist(r,g,b,ref)<=TOLERANCE){accepted++;cellAccepted++;l.push(.2126*r+.7152*g+.0722*b);}
    }
    if(cellTotal && cellAccepted/cellTotal>=.05 && l.length) cells.push(median(l));
  }
  const coverage=total?accepted/total:0, lumaMad=mad(cells);
  return {coverage,lumaMad,validCells:cells.length,reference:ref};
}

async function main(){
  const files=fs.readdirSync(INPUT).filter(f=>/\.(png|jpg|jpeg|webp)$/i.test(f)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  const session=await ort.InferenceSession.create(MODEL), pages=[]; let balloons=0,special=0;
  for(const file of files){
    const input=path.join(INPUT,file), detections=await detect(session,input), regions=[];
    for(const box of detections){
      const metrics=await analyzeRegion(input,box);
      const route=metrics.coverage>=MIN_COVERAGE && metrics.lumaMad>MIN_LUMA_MAD ? "SPECIAL":"NORMAL";
      if(route==="SPECIAL") special++;
      balloons++;
      regions.push({type:"bubble",confidence:box.score,bbox:[box.x1,box.y1,box.x2,box.y2],...metrics,route});
    }
    pages.push({file,regions});
    console.log(`${file}: balloons=${detections.length}`);
  }
  const report={schema:"bubble_sommelier_v1",status:"completed",chapter:CHAPTER,
    contract:{detector:"RT-DETR comic-text-and-bubble-detector",detector_threshold:THRESHOLD,detection_label:"bubble",
      mask_tolerance:TOLERANCE,grid:"12x12",minimum_coverage:MIN_COVERAGE,candidate_rule:"Luma MAD > 1.0"},
    summary:{pages:files.length,balloons,normal:balloons-special,special},pages};
  fs.mkdirSync(path.dirname(OUTPUT),{recursive:true}); fs.writeFileSync(OUTPUT,JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exit(1);});
