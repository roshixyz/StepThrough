from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import tempfile
import os
import sys
import re
import copy

from pathlib import Path

from expressions import LeetCodeDebugger

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

def execute_code_from_file(code_str):

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code_str)
        temp_file = f.name
    
    try:
        dir_path = os.path.dirname(temp_file)
        sys.path.insert(0, dir_path)
        
        # module_name = os.path.splitext(os.path.basename(temp_file))[0]
        
        with open(temp_file, 'r') as f:
            compiled_code = compile(f.read(), temp_file, 'exec')
        
        namespace = {
            '__file__': temp_file,
            '__name__': '__main__'
        }
        exec(compiled_code, namespace)
        
        return namespace.get('res'), namespace.get('log_data')
    
    finally:

        if dir_path in sys.path:
            sys.path.remove(dir_path)
        os.unlink(temp_file)




def modify_code(func_str):
    # Split the input string into lines and handle empty lines
    lines = func_str.strip().splitlines()
    
    # Separate imports, function definition, and function call
    import_lines = []
    func_lines = []
    current_section = 'imports'
    
    for line in lines:
        stripped_line = line.strip()
        if current_section == 'imports':
            if stripped_line.startswith('def '):
                current_section = 'function'
                func_lines.append(line)
            elif stripped_line.startswith('import ') or stripped_line.startswith('from '):
                import_lines.append(line)
            elif stripped_line:  # Skip empty lines between imports and function
                current_section = 'function'
                func_lines.append(line)
        else:
            func_lines.append(line)

    # Extract function signature and body
    func_signature = next(line for line in func_lines if line.strip().startswith('def '))
    body_start = func_lines.index(func_signature) + 1
    body = '\n'.join(func_lines[body_start:-1])

    # Parse function name and parameters
    func_name_match = re.match(r"def\s+(\w+)\((.*)\):", func_signature)
    if not func_name_match:
        raise ValueError("Invalid function signature", func_signature)
    
    func_name = func_name_match.group(1)

    # Parse the function call line
    call_line = func_lines[-1].strip()
    call_match_with_return = re.match(r"(\w+(?:,\s*\w+)*)\s*=\s*" + rf"{func_name}\((.*)\)", call_line)
    call_match_no_return = re.match(rf"{func_name}\((.*)\)", call_line)

    if call_match_with_return:
        return_vars = call_match_with_return.group(1)
        call_args = call_match_with_return.group(2)
        modified_return_vars = f"{return_vars}, log_data"
    elif call_match_no_return:
        call_args = call_match_no_return.group(1)
        modified_return_vars = "res, log_data"
    else:
        raise ValueError("Invalid function call format")

    # Combine everything with proper spacing and ordering
    modified_func_str = []
    
    # Add original imports if they exist
    if import_lines:
        modified_func_str.extend(import_lines)
        modified_func_str.append("")  # Empty line after imports
    
    # Add tracer import
    modified_func_str.append("from tracer import trace_execution")
    modified_func_str.append("")  # Empty line after tracer import
    
    # Add decorated function
    modified_func_str.append("@trace_execution")
    modified_func_str.append(func_signature)
    modified_func_str.append(body)
    modified_func_str.append("")  # Empty line before function call
    modified_func_str.append(f"{modified_return_vars} = {func_name}({call_args})")

    return "\n".join(modified_func_str)




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
        server_code = modify_code(code)
        # print(server_code)
        
        try:
            _, log_data = execute_code_from_file(server_code)
        except Exception as e:
            return {"error": str(e)}
        
        data = []

        for i in range(len(log_data)):
            line_no = log_data[i]["line_no"]
            prev_variables = log_data[i]["variables"]
            exec_line = log_data[i]["current_line"]
            exec_res = {}

            if i < len(log_data) - 1:
                exec_res = log_data[i+1]["variables"]
            else:
                exec_res = log_data[i]["variables"]

            temp_data = {"line_no": line_no, "prev_variables": prev_variables, "exec_line": exec_line, "exec_res": exec_res}

            debugger = LeetCodeDebugger()
            results = debugger.process_line(exec_line, prev_variables)
            
            sub_exp_line = {}

            for expr, value in results:
                sub_exp_line[str(expr)] = str(value)


            temp_data.update({"sub_exp": sub_exp_line})

            temp_data["exec_res"] = copy.deepcopy(temp_data["exec_res"])
            temp_data["prev_variables"] = copy.deepcopy(temp_data["prev_variables"])

            for key, value in temp_data["exec_res"].items():
                temp_data["exec_res"][key] = str(value)
            for key, value in temp_data["prev_variables"].items():
                temp_data["prev_variables"][key] = str(value)


            data.append(temp_data)
            
        return {"output": data}

            
    except Exception as e:
        return {"error": str(e)}




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
