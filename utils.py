import ast
import copy
import inspect
import json
import os
import sys
from itertools import chain

from cheap_repr import cheap_repr, try_register_repr

from expressions import ExpExec

PYPY = 'pypy' in sys.version.lower()
NO_BIRDSEYE = PYPY

pp_name_prefix = '__deep_pp_hidden__'

file_reading_errors = (
    IOError,
    OSError,
    ValueError  # IronPython weirdness.
)


def shitcode(s):
    return ''.join(
        (c if (0 < ord(c) < 256) else '?') for c in s
    )


def truncate(seq, max_length, middle):
    if len(seq) > max_length:
        left = (max_length - len(middle)) // 2
        right = max_length - len(middle) - left
        seq = seq[:left] + middle + seq[-right:]
    return seq


def truncate_string(string, max_length):
    return truncate(string, max_length, '...')


def truncate_list(lst, max_length):
    return truncate(lst, max_length, ['...'])


def ensure_tuple(x, split=False):
    if split and isinstance(x, str):
        x = x.replace(',', ' ').split()
    if not isinstance(x, (list, set, tuple)):
        x = (x,)
    return tuple(x)


def short_filename(code):
    result = os.path.basename(code.co_filename)
    if result.endswith('.pyc'):
        result = result[:-1]
    return result


def is_comprehension_frame(frame):
    return frame.f_code.co_name in ('<listcomp>', '<dictcomp>', '<setcomp>')


def needs_parentheses(source):
    def code(s):
        return compile(s.format(source), '<variable>', 'eval').co_code

    try:
        without_parens = code('{}.x')
    except SyntaxError:
        # Likely a multiline expression that needs parentheses to be valid
        code('({})')
        return True
    else:
        return without_parens != code('({}).x')


def with_needed_parentheses(source):
    if needs_parentheses(source):
        return '({})'.format(source)
    else:
        return source


REPR_TARGET_LENGTH = 100


def my_cheap_repr(x):
    return cheap_repr(x, target_length=REPR_TARGET_LENGTH)


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


def is_pathlike(x):
    if hasattr(os, 'PathLike'):
        return isinstance(x, os.PathLike)

    return (
            hasattr(x, '__fspath__') or
            # Make a concession for older `pathlib` versions:
            (hasattr(x, 'open') and
             'path' in x.__class__.__name__.lower())
    )


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


class DirectRepr(str):
    def __repr__(self):
        return self


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
