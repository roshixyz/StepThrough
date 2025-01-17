import json
import os
import re
import sys
import tempfile

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


from pathlib import Path

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)


def execute_temp_code(code_string):
    current_dir = Path(os.getcwd())
    
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            dir=current_dir
        ) as temp_file:
            temp_file.write(code_string)
            temp_file.flush()
            temp_file_path = temp_file.name
        
        try:
            sys.path.insert(0, str(current_dir))
            
            with open(temp_file_path, 'r') as file:
                code = compile(file.read(), temp_file_path, 'exec')
                namespace = {}
                exec(code, namespace)
                return namespace.get('result', None)
                
        finally:
            try:
                os.unlink(temp_file_path)
            except OSError as e:
                print(f"Warning: Failed to delete temporary file {temp_file_path}: {e}")
            
            sys.path.pop(0)
            
    except Exception as e:
        raise Exception(f"Error executing code: {str(e)}")



def transform_code(input_code):
    
    has_imports = bool(re.match(r'\s*(import|from)\s+', input_code.lstrip()))
    
    if has_imports:
        lines = input_code.split('\n')
        
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                last_import_idx = i
        
        lines[last_import_idx:last_import_idx + 1] = [
            lines[last_import_idx],
            "",
            "from tracer import Tracer",
            "from utils import process_logs",
            "",
            "tracer_instance = Tracer()",
        ]
        input_code = '\n'.join(lines)
    else:
        imports = [
            "from tracer import Tracer",
            "from utils import process_logs",
            "",
            "tracer_instance = Tracer()",
            ""
        ]
        input_code = '\n'.join(imports) + input_code.lstrip()
    
    def add_decorator(match):
        full_match = match.group(0)
        indentation = match.group(1)
        func_def = match.group(2)
        
        lines_before = input_code[:match.start()].split('\n')
        for line in reversed(lines_before):
            line_stripped = line.strip()
            if line_stripped and len(line) - len(line.lstrip()) < len(indentation):
                if line_stripped.startswith('class '):
                    return full_match
                break
                
        return f"{indentation}@tracer_instance\n{indentation}{func_def}"

    pattern = r'([ \t]*)(def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:)'
    
    code_with_decorators = re.sub(pattern, add_decorator, input_code)
    
    final_code = code_with_decorators.rstrip() + "\n\n"
    if not any(line.strip().startswith('log_data = ') for line in code_with_decorators.split('\n')):
        final_code += "log_data = tracer_instance.log_data\nprocess_logs(log_data)\n"
    
    return final_code




class CodeRequest(BaseModel):
    code: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_path = Path(__file__).parent / "main.html"
    return HTMLResponse(content=html_path.read_text())


@app.post("/send-code")
async def receive_code(request: CodeRequest):

    code = request.code
    
    try: 
        server_code = transform_code(code)
        # print(server_code)
        
        lines = code.split('\n')
        lines = [line.strip() for line in lines]
        
        try:
            execute_temp_code(server_code)
        except Exception as e:
            return {"error": str(e)}
        
        with open('data.json', 'r') as json_file:
            data = json.load(json_file)
            
            for log in data:
                if log['exec_line'] in lines:
                    log['line_no'] = lines.index(log['exec_line']) + 1 
                
            
        return {"output": data}

            
    except Exception as e:
        return {"error": str(e)}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
