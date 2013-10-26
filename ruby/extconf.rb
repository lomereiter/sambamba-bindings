require 'mkmf'
$LOCAL_LIBS = " -L. -lphobos2 -lsambambawrapper"
create_makefile 'sambamba'
