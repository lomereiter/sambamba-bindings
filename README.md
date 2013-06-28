sambamba-bindings
=================

Bindings for the sambamba library. 

CFFI bindings are known to work on PyPy 2.0, Linux 64-bit.
They also run on CPython 2.*, but about 5x slower (stick with PySam or join PyPy users).

Compilation:
- install DMD compiler
- create a symlink `libphobos2.so.0.63` -> `libphobos2.so` (the library comes with the compiler)
- point `LD_LIBRARY_PATH` to the shared library
- run `make` from the root directory
