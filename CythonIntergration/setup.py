# cythonintegration/setup.py
from setuptools import setup
from Cython.Build import cythonize

setup(
    name='arbitrage_logic',
    ext_modules=cythonize("arbitrage_logic.pyx", compiler_directives={'language_level': "3"}),
    zip_safe=False,
)