import ast
import copy
import inspect
import json
from itertools import chain

from cheap_repr import cheap_repr, try_register_repr

from expressions import ExpExec

file_reading_errors = (
    IOError,
    OSError,
    ValueError
)

def is_comprehension_frame(frame):
    return frame.f_code.co_name in ('<listcomp>', '<dictcomp>', '<setcomp>')



REPR_TARGET_LENGTH = 100

class ArgDefaultDict(dict):
    def __init__(self, factory):
        super(ArgDefaultDict, self).__init__()
        self.factory = factory

    def __missing__(self, key):
        result = self[key] = self.factory(key)
        return result


def optional_numeric_label(i, lst):
    if len(lst) == 1:
        return ''
    else:
        return ' ' + str(i + 1)

def process_logs(log_data):
    
    data = []

    for i in range(len(log_data)):
        
        line_no = log_data[i]["line_no"]
        variables = log_data[i]["variables"]
        exec_line = log_data[i]["current_line"]
        event = log_data[i]["event"]
        arg = log_data[i]["arg"]
        
        exec_res = {}

        if i < len(log_data) - 1:
            exec_res = log_data[i+1]["variables"]
        else:
            exec_res = log_data[i]["variables"]
        
        if "@" in exec_line:
            pass
        elif ".0" in variables:
            pass
        else:
            temp_data = {
                "line_no": line_no - 5,
                "variables": variables,
                "exec_line": exec_line, 
                "exec_res": exec_res, 
                "event": event,
                "arg": {} if arg is None else str(arg)
            }
        
            exp_exec = ExpExec()

            exp_exec_res = exp_exec.process_line(exec_line, variables)

            sub_exp = {}
            for expr, value in exp_exec_res:
                sub_exp[expr] = value
                
            temp_data['sub_exp'] = sub_exp

            temp_data["exec_res"] = copy.deepcopy(temp_data["exec_res"])
            temp_data["variables"] = copy.deepcopy(temp_data["variables"])
            
            for key, value in temp_data["exec_res"].items():
                temp_data["exec_res"][key] = str(value)
            for key, value in temp_data["variables"].items():
                temp_data["variables"][key] = str(value)
            for key, value in temp_data["sub_exp"].items():
                temp_data["sub_exp"][key] = str(value)
            
            data.append(temp_data)
        
    with open('data.json', 'w') as json_file:
        json.dump(data, json_file)

    return None

try:
    iscoroutinefunction = inspect.iscoroutinefunction
except AttributeError:
    def iscoroutinefunction(_):
        return False

try:
    try_statement = ast.Try
except AttributeError:
    try_statement = ast.TryExcept


try:
    builtins = __import__("__builtin__")
except ImportError:
    builtins = __import__("builtins")


try:
    FormattedValue = ast.FormattedValue
except Exception:
    class FormattedValue(object):
        pass


def no_args_decorator(args, kwargs):
    return len(args) == 1 and inspect.isfunction(args[0]) and not kwargs

def _register_cheap_reprs():
    def _sample_indices(length, max_length):
        if length <= max_length + 2:
            return range(length)
        else:
            return chain(range(max_length // 2),
                         range(length - max_length // 2,
                               length))

    @try_register_repr('pandas', 'Series')
    def _repr_series_one_line(x, helper):
        n = len(x)
        if n == 0:
            return repr(x)
        newlevel = helper.level - 1
        pieces = []
        maxparts = _repr_series_one_line.maxparts
        for i in _sample_indices(n, maxparts):
            try:
                k = x.index[i:i + 1].format(sparsify=False)[0]
            except TypeError:
                k = x.index[i:i + 1].format()[0]
            v = x.iloc[i]
            pieces.append('%s = %s' % (k, cheap_repr(v, newlevel)))
        if n > maxparts + 2:
            pieces.insert(maxparts // 2, '...')
        return '; '.join(pieces)


_register_cheap_reprs()
