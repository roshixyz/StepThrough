import copy
import functools
import inspect
import json
import os
import re
import sys
import threading
from collections import OrderedDict

from cheap_repr import cheap_repr, find_repr_function

from utils import (ArgDefaultDict,
                    is_comprehension_frame, iscoroutinefunction,
                    no_args_decorator)


find_repr_function(str).maxparts = 100
find_repr_function(bytes).maxparts = 100
find_repr_function(object).maxparts = 100
find_repr_function(int).maxparts = 999999
cheap_repr.suppression_threshold = 999999



class FrameInfo(object):
    def __init__(self, frame):
        self.frame = frame
        self.local_reprs = {}
        self.last_line_no = frame.f_lineno
        self.comprehension_variables = OrderedDict()
        code = frame.f_code
        self.is_generator = code.co_flags & inspect.CO_GENERATOR
        self.had_exception = False
        

thread_global = threading.local()
internal_directories = (os.path.dirname((lambda: 0).__code__.co_filename),)


class TracerMeta(type):
    def __new__(mcs, *args, **kwargs):
        result = super(TracerMeta, mcs).__new__(mcs, *args, **kwargs)
        result.default = result()
        return result

    def __call__(cls, *args, **kwargs):
        if no_args_decorator(args, kwargs):
            return cls.default(args[0])
        else:
            return super(TracerMeta, cls).__call__(*args, **kwargs)

    def __enter__(self):
        return self.default.__enter__(context=1)

    def __exit__(self, *args):
        return self.default.__exit__(*args, context=1)


class Tracer(metaclass=TracerMeta):
    def __init__(
            self,
            depth=1,
    ):
        self.frame_infos = ArgDefaultDict(FrameInfo)
        self.depth = depth
        assert self.depth >= 1
        self.target_codes = set()
        self.target_frames = set()
        self.variable_whitelist = None
        self.last_frame = None
        self.thread_local = {}
        self.trace_event = {}
        self.log_data = []
        
        

    def __call__(self, function):
        if iscoroutinefunction(function):
            raise NotImplementedError("coroutines are not supported, sorry!")

        self.target_codes.add(function.__code__)

        @functools.wraps(function)
        def simple_wrapper(*args, **kwargs):
            with self:
                result = function(*args, **kwargs)
                return result

        @functools.wraps(function)
        def generator_wrapper(*args, **kwargs):
            gen = function(*args, **kwargs)
            method, incoming = gen.send, None
            while True:
                with self:
                    try:
                        outgoing = method(incoming)
                    except StopIteration:
                        return
                try:
                    method, incoming = gen.send, (yield outgoing)
                except Exception as e:
                    method, incoming = gen.throw, e

        if inspect.isgeneratorfunction(function):
            return generator_wrapper
        else:
            return simple_wrapper

    def __enter__(self, context=0):
        
        self.thread_local = {'depth':-1}

        calling_frame = sys._getframe(context + 1)
        if not self._is_internal_frame(calling_frame):
            calling_frame.f_trace = self.trace
            self.target_frames.add(calling_frame)
            self.last_frame = calling_frame
            self.trace(calling_frame, 'enter', None)

        stack = thread_global.__dict__.setdefault('original_trace_functions', [])
        stack.append(sys.gettrace())
        sys.settrace(self.trace)

    def __exit__(self, context=0):

        previous_trace = thread_global.original_trace_functions.pop()
        sys.settrace(previous_trace)
        calling_frame = sys._getframe(context + 1)
        calling_frame.f_trace = previous_trace
        self.trace(calling_frame, 'exit', None)
        self.target_frames.discard(calling_frame)
        self.frame_infos.pop(calling_frame, None)

    def _is_internal_frame(self, frame):
        return frame.f_code.co_filename.startswith(internal_directories)

    def _is_traced_frame(self, frame):
        return frame.f_code in self.target_codes or frame in self.target_frames

    def trace(self, frame, event, arg):
        if not self._is_traced_frame(frame):
            if (
                self.depth == 1
                or self._is_internal_frame(frame)
            ) and not is_comprehension_frame(frame):
                return None
            else:
                candidate = frame
                i = 0
                while True:
                    if is_comprehension_frame(candidate):
                        candidate = candidate.f_back
                        continue
                    i += 1
                    if self._is_traced_frame(candidate):
                        break
                    candidate = candidate.f_back
                    if i >= self.depth or candidate is None or self._is_internal_frame(candidate):
                        return None

        frame_info = self.frame_infos[frame]
        
        if event in ('call', 'enter'):
            self.thread_local['depth'] += 1
            
        elif self.last_frame and self.last_frame is not frame:
            
            line_no = frame_info.last_line_no
            lines = inspect.getsourcelines(frame.f_code)[0]
            
            if event == 'call' and lines[self.trace_event['line_no'] - frame.f_code.co_firstlineno].strip().startswith('@'):
                while True:
                    line_no += 1
                    try:
                        if lines[self.trace_event['line_no'] - frame.f_code.co_firstlineno].strip().startswith('def'):
                            break
                    except IndexError:
                        line_no = self.frame.lineno
                        break
                    
            self.trace_event = {
                'frame_info': frame_info,
                'event': event,
                'arg': arg,
                'depth': self.thread_local['depth'],
                'line_no': line_no,
            }

        if event == 'exception':
            frame_info.had_exception = True

        self.last_frame = frame
        line_no = frame.f_lineno
        lines = inspect.getsourcelines(frame.f_code)[0]
        
        if event == 'call' and lines[line_no - frame.f_code.co_firstlineno].strip().startswith('@'):
            while True:
                line_no += 1
                try:
                    if lines[line_no - frame.f_code.co_firstlineno].strip().startswith('def'):
                        break
                except IndexError:
                    line_no = self.frame.lineno
                    break
                
        self.trace_event['frame_info'] = frame_info
        self.trace_event['event'] = event
        self.trace_event['arg'] = arg
        self.trace_event['depth'] = self.thread_local['depth']
        self.trace_event['line_no'] = line_no
        
        current_line = lines[self.trace_event['line_no'] - frame.f_code.co_firstlineno].strip()
        variables = copy.deepcopy(frame.f_locals)

        if event in ('return', 'exit'):
            del self.frame_infos[frame]
            self.thread_local['depth'] -= 1
   
        
        self.log_data.append(copy.deepcopy({
            'line_no': self.trace_event['line_no'],
            'current_line': current_line,
            'variables': variables,
            'event': event,
            'arg': arg
        }))

        return self.trace
