import inspect

# Global debug flag
DEBUG = True
def dprint(*args, **kwargs):
    if DEBUG:
        caller_frame = inspect.currentframe().f_back
        module_name = inspect.getmodule(caller_frame).__name__
        function_name = caller_frame.f_code.co_name
        print(f"[{module_name}.{function_name}]:", *args, **kwargs)