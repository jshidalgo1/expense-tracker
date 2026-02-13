import time
import streamlit as st
from contextlib import contextmanager

class Profiler:
    def __init__(self):
        if 'profiler_stats' not in st.session_state:
            st.session_state['profiler_stats'] = {}
        
    def add_stat(self, name: str, duration: float):
        st.session_state['profiler_stats'][name] = duration

    def get_stats(self):
        return st.session_state.get('profiler_stats', {})

    def clear(self):
        st.session_state['profiler_stats'] = {}

@contextmanager
def scope_timer(name: str):
    """
    Context manager to measure execution time of a block.
    Stores the result in st.session_state['profiler_stats'].
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        profiler = Profiler()
        profiler.add_stat(name, duration)

def get_profiler_stats():
    return Profiler().get_stats()
