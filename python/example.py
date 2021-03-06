from sambamba import *

import time
import os

filename = os.path.join(os.path.dirname(__file__), 
                        '../BioD/test/data/mg1655_chunk.bam')

cur_time = time.time()

bam = BamReader(filename)
bam.createIndex()
print("References: %s" % bam.references)
print("Number of reads: %s" % sum(1 for _ in bam.reads()))
print("===========")
print("SAM header:")
print(bam.header)

reads = (r for r in bam.references[0].fetch(500000, 500100) if r.quality > 10)

columns = 0

for column in Pileup(reads, use_md=True):
    coverage = column.coverage
    columns += 1
    if 500000 <= column.position < 500010:
        b = column.bases
        print("Position: %s\tReference base: %s\tCoverage: %s\tSame as reference: %s" \
              % (column.position, column.reference_base, 
                 coverage, b.count(column.reference_base)))

              
new_fn = filename + ".v1"        
w = BamWriter(new_fn, threads=2)
w.writeHeader(bam.header)
w.writeRefs(bam.references)
for r in bam.reads():
    if r.tag('NM') > 2:
        r.setInt16Tag('NM', -42)
        r.position = 666
        r.sequence = "A" * 1000
        r.base_qualities = [25] * 1000
        r.cigar = [CigarOperation(333, 'M'), CigarOperation(333, 'S')]
        r.setStringTag('XW', "this read is weird")
    w.writeRead(r)
w.close()

new_bam = BamReader(new_fn)
print("Reads with NM == -42: %s" % sum(1 for r in new_bam.reads() if r.tag('NM') == -42))
for read in new_bam.reads():
    if read.tag('NM') == -42:
        assert(read.tag('XW') != None)
        assert(read.position == 666)
        assert(read.cigar_string == "333M333S")
        assert(read.sequence == "A" * 1000)
        assert(read.base_qualities == [25] * 1000)

os.unlink(new_fn)
os.unlink(filename + ".bai")

exec_time = time.time() - cur_time
print("Time elapsed: %.2fs" % exec_time)
print("Processed columns: %s" % columns)
