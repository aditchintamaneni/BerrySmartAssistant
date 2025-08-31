import time
from functools import wraps
from contextlib import contextmanager

class Timer:
    def __init__(self):
        self.measurements = {}
    
    def measure(self, name):
        """a decorator for timing functions"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                self.measurements[name] = elapsed
                print(f"[{name}] {elapsed:.0f}ms")
                return result
            return wrapper
        return decorator
    
    @contextmanager
    def section(self, name):
        """a context manager for timing blocks of code"""
        start = time.perf_counter()
        yield
        elapsed = (time.perf_counter() - start) * 1000
        self.measurements[name] = elapsed
        print(f"[{name}] {elapsed:.0f}ms")
    
    def report(self):
        """print all the measurements"""
        if self.measurements:
            sum_of_all_times = sum(self.measurements.values())
            for name, ms in self.measurements.items():
                print(f"{name}: {ms:.0f}ms ({ms/sum_of_all_times*100:.0f}%)")

# testing 
timer = Timer()
if __name__ == "__main__":
    @timer.measure("my_func")
    def my_func():
        time.sleep(0.2)
        return "done"
    my_func()
    
    with timer.section("my_block"):
        time.sleep(0.05)

    timer.report()