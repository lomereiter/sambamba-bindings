sambamba-cffi
=============

CFFI bindings for the sambamba library. Known to work on PyPy 2.0, Linux 64-bit.

Compilation:
- install DMD compiler
- create a symlink libphobos2.so.0.63 -> libphobos2.so (the library comes with the compiler)
- point LD_LIBRARY_PATH to the shared library
- run `make` from the root directory
