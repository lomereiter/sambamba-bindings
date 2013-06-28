.PHONY: sambamba-cffi

FLAGS=-O -release -inline
DEBUG_FLAGS=-debug

sambamba-cffi:
	rdmd --build-only --force -shared -fPIC -L-lphobos2 -IBioD $(FLAGS) -oflibsambamba.so bindings.d
	mv libsambamba.so python/sambamba
	cp sambamba.h python/sambamba/sambamba.h

sambamba-cffi-debug:
	rdmd --build-only --force -shared -fPIC -L-lphobos2 -IBioD $(DEBUG_FLAGS) -oflibsambamba.so bindings.d
	mv libsambamba.so python/sambamba
	cp sambamba.h python/sambamba/sambamba.h
