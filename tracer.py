import inspect
import sys
import copy
from functools import wraps
import types
import collections.abc

def should_exclude_object(obj):
    return (
        inspect.isgenerator(obj) or
        inspect.isfunction(obj) or
        inspect.isclass(obj) or
        inspect.ismodule(obj) or
        inspect.isbuiltin(obj) or
        inspect.iscoroutine(obj) or
        inspect.isawaitable(obj) or
        inspect.isgeneratorfunction(obj) or
        inspect.iscoroutinefunction(obj) or
        inspect.isasyncgenfunction(obj) or
        isinstance(obj, (
            types.ModuleType,
            types.CodeType,
            types.FrameType,
            types.TracebackType,
            types.GeneratorType,
            collections.abc.Iterator,
            collections.abc.Generator
        ))
    )

def create_tracer(log_data, target_function):
    
    call_depth = 0

    def trace_function(frame, event, arg):
        # print(inspect.getsourcelines(frame.f_code)[0])
        
        func_name = frame.f_code.co_name
        line_no = frame.f_lineno
        
        lines = inspect.getsourcelines(frame.f_code)[0]
        
        # temporary fix for Counter and backtracking issue
        if inspect.getsourcelines(frame.f_code)[1] > 100:
            return trace_function
        
        current_line = lines[line_no - frame.f_code.co_firstlineno].strip()
    
        nonlocal call_depth

        
        
        if event == "call":  # Entering a function call
            if frame.f_code is target_function.__code__:
                call_depth += 1
            return trace_function

        elif event == "return":  # Exiting a function call
            if frame.f_code is target_function.__code__:
                call_depth -= 1
            return trace_function
        

        if event == "line" and call_depth > 0:  # Only trace if inside the target function
            
            local_vars = {}
            for k, v in frame.f_locals.items():
                if k.startswith('__') or should_exclude_object(v):
                    continue
                    
                if k == 'self':
                    for attr_name, attr_value in vars(v).items():
                        if not attr_name.startswith('__') and not should_exclude_object(attr_value):
                            try:
                                local_vars[f"self.{attr_name}"] = copy.deepcopy(attr_value)
                            except:
                                local_vars[f"self.{attr_name}"] = str(attr_value)
                else:
                    try:
                        local_vars[k] = copy.deepcopy(v)
                    except:
                        local_vars[k] = str(v)
        
            
            class_name = None
            if 'self' in frame.f_locals:
                class_name = frame.f_locals['self'].__class__.__name__
            

            log_entry = {
                "line_no": line_no - 3,
                "current_line": current_line,
                "variables": local_vars
            }
            
            if class_name:
                log_entry["class"] = class_name

            log_data.append(log_entry)

        return trace_function

    return trace_function

def trace_execution(target):
    if inspect.isclass(target):
        for attr_name, attr_value in target.__dict__.items():
            if inspect.isfunction(attr_value):
                if attr_name == '__init__':
                    setattr(target, attr_name, trace_init(attr_value))
                else:
                    setattr(target, attr_name, trace_execution(attr_value))
        return target
    
    @wraps(target)
    def wrapper(*args, **kwargs):
        log_data = []
        tracer = create_tracer(log_data, target)
        sys.settrace(tracer)
        result = target(*args, **kwargs)
        sys.settrace(None)
        return result, log_data
    
    return wrapper

def trace_init(init_method):
    @wraps(init_method)
    def wrapper(*args, **kwargs):
        log_data = []
        tracer = create_tracer(log_data, init_method)
        sys.settrace(tracer)
        init_method(*args, **kwargs)
        sys.settrace(None)

        if args and hasattr(args[0], '__dict__'):
            args[0].__trace_log__ = log_data
        return None
    return wrapper