sambamba-bindings
=================

Bindings for the sambamba library (BAM reading and writing)

CFFI bindings are known to work on PyPy 2.0, Linux 64-bit.
They also run on CPython 2.\*, but about 5x slower (stick with PySam or join PyPy users).

## Compilation
- `git clone --recursive https://github.com/lomereiter/sambamba-bindings.git`
- install DMD compiler (http://dlang.org/download)
- create a symlink `libphobos2.so.0.65` -> `libphobos2.so` (the library comes with the compiler)
- run `make` from the root directory

## Usage
- set `LD_LIBRARY_PATH` to be the directory where `libphobos2.so.0.65` is located
- if you use CPython 2.\*, install CFFI: `pip install cffi`
- try to run `python python/example.py`

## Ruby bindings
 - After running `make` as described above, `cd ruby/ && ruby extconf.rb && make'
 - This will create file `sambamba.so` which can be loaded as `require './sambamba.so'`; `libsambambawrapper.so` must be findable through the shared library path.
