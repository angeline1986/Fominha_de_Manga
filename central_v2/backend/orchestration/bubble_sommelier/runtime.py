import os, subprocess
from pathlib import Path
def central_root() -> Path:
    return Path(__file__).resolve().parents[3]
def runtime_dir() -> Path:
    return central_root()/"runtime"/"bubble_sommelier"
def resolve_runtime():
    root=runtime_dir(); worker=root/"worker.js"; model=root/"models"/"detector.onnx"; modules=root/"node_modules"
    missing=[]
    if not worker.is_file(): missing.append(str(worker))
    if not model.is_file(): missing.append(str(model))
    if not modules.is_dir(): missing.append(str(modules))
    if missing:
        raise RuntimeError("Runtime próprio do BubbleSommelier não está instalado/configurado em central_v2/runtime/bubble_sommelier. Ausente: "+", ".join(missing))
    return worker,model,modules
def run(source:Path,target:Path,chapter:str):
    worker,model,modules=resolve_runtime(); target.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env["NODE_PATH"]=str(modules)
    command=["node",str(worker),"--input",str(source),"--model",str(model),"--output",str(target),"--chapter",chapter]
    completed=subprocess.run(command,cwd=runtime_dir(),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError(f"BubbleSommelier falhou no capítulo {chapter}: {completed.stdout[-2000:]}")
