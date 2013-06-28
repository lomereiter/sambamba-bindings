from sambamba import *

import time
import os

filename = os.path.join(os.path.dirname(__file__), 
                        '../BioD/test/data/mg1655_chunk.bam')

bam = BamReader(filename)
bam.createIndex()
print("References: %s" % bam.references)
print("Number of reads: %s" % sum(1 for _ in bam.reads()))

cur_time = time.time()

reads = (r for r in bam.references[0].fetch(500000, 500100) if r.quality > 10)

covsum = 0
columns = 0

for column in Pileup(reads, use_md=True):
    coverage = column.coverage
    covsum += coverage
    columns += 1
    if 500000 <= column.position < 500010:
        b = column.bases
        print("Position: %s\tReference base: %s\tCoverage: %s\tSame as reference: %s" \
              % (column.position, column.reference_base, 
                 coverage, b.count(column.reference_base)))

exec_time = time.time() - cur_time
print("Time elapsed: %.2fs" % exec_time)

print("Processed columns: %s" % columns)
#print("Average coverage: %s" % (float(covsum) / columns))
