.PHONY: sambamba-bindings

FLAGS=-O -release -inline --exclude=etc
DEBUG_FLAGS=-debug

sambamba-bindings:
	rdmd --build-only --force -shared -fPIC -L-lphobos2 -IBioD $(FLAGS) -oflibsambamba.so bindings.d
	cp libsambamba.so ruby/libsambambawrapper.so
	mv libsambamba.so python/sambamba
	cp sambamba.h python/sambamba/sambamba.h

sambamba-bindings-debug:
	rdmd --build-only --force -shared -fPIC -L-lphobos2 -IBioD $(DEBUG_FLAGS) -oflibsambamba.so bindings.d
	cp libsambamba.so ruby/libsambambawrapper.so
	mv libsambamba.so python/sambamba
	cp sambamba.h python/sambamba/sambamba.h
