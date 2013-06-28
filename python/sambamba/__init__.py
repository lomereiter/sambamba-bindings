import os
fname = os.path.join(os.path.dirname(__file__), 'sambamba.h')
with open('sambamba.h', 'r') as f:
    _header = f.read()

from cffi import FFI
_ffi = FFI()
_ffi.cdef(_header)

def _d_arr(type, cdata):
    return _ffi.cast(type + "[%d]" % cdata.len, cdata.buf)

def _d_str(cdata):
    return _ffi.string(cdata.buf, cdata.len)

_tag_getters_dict = {
  0b00100100 : lambda r, t: _lib.bam_read_char_tag(r, t),
  0b00100000 : lambda r, t: _lib.bam_read_uint8_tag(r, t),
  0b01000000 : lambda r, t: _lib.bam_read_uint16_tag(r, t),
  0b10000000 : lambda r, t: _lib.bam_read_uint32_tag(r, t),
  0b00110000 : lambda r, t: _lib.bam_read_int8_tag(r, t),
  0b01010000 : lambda r, t: _lib.bam_read_int16_tag(r, t),
  0b10010000 : lambda r, t: _lib.bam_read_int32_tag(r, t),
  0b10001000 : lambda r, t: _lib.bam_read_float_tag(r, t),
  0b00100001 : lambda r, t: _d_arr("uint8_t", _lib.bam_read_uint8_array_tag(r, t)),
  0b01000001 : lambda r, t: _d_arr("uint16_t", _lib.bam_read_uint16_array_tag(r, t)),
  0b10000001 : lambda r, t: _d_arr("uint32_t", _lib.bam_read_uint32_array_tag(r, t)),
  0b00110001 : lambda r, t: _d_arr("int8_t", _lib.bam_read_int8_array_tag(r, t)),
  0b01010001 : lambda r, t: _d_arr("int16_t", _lib.bam_read_int16_array_tag(r, t)),
  0b10010001 : lambda r, t: _d_arr("int32_t", _lib.bam_read_int32_array_tag(r, t)),
  0b10001001 : lambda r, t: _d_arr("float", _lib.bam_read_float_array_tag(r, t)),
  0b00100101 : lambda r, t: _d_str(_lib.bam_read_string_tag(r, t)),
  0b00101101 : lambda r, t: _d_str(_lib.bam_read_string_tag(r, t)),
  0b00000010 : lambda r, t: None
}

_tag_getters = [lambda r, t: None] * 256
for id in _tag_getters_dict:
    _tag_getters[id] = _tag_getters_dict[id]

_charType = _ffi.typeof("char[]")
_bamReadType = _ffi.typeof("bam_read_s *")

class CigarOperation(object):
    def __init__(self, int32):
        self._d_int32 = int32

    @property
    def length(self):
        return _lib.bam_cigar_operation_length(self._d_int32)

    @property
    def type(self):
        return _lib.bam_cigar_operation_type(self._d_int32)

    @property
    def consumes_reference(self):
        return _lib.bam_cigar_operation_consumes_ref(self._d_int32)

    @property
    def consumes_query(self):
        return _lib.bam_cigar_operation_consumes_query(self._d_int32)

    @property
    def consumes_both(self):
        return _lib.bam_cigar_operation_consumes_both(self._d_int32)

class BamRead(object):
    def __init__(self, d_ptr, auxdata=None):
        self._d_read = d_ptr
        self._aux = auxdata

    # self._d_read is either obtained via _ffi.new, or it is internal
    # to some data structure on the D side.
    # As such, __del__ is not needed. In fact, it's the very reason why
    # the read contents are copied into memory allocated via _ffi.new,
    # and not on the D heap--for this would require having a finalizer,
    # which would cause a huge drop in performance.

    @staticmethod
    def fromCopy(cdata, csz, reader):
        _d_read = _ffi.new(_bamReadType)
        _d_read.len = csz
        _d_read.buf = cdata
        _d_read.reader = reader
        return BamRead(_d_read, cdata)

    @property
    def reference_name(self):
        data = _lib.bam_read_reference_name(self._d_read)
        return _ffi.string(data)

    @property
    def reference_id(self):
        return _lib.bam_read_ref_id(self._d_read)

    @property
    def mate_reference_id(self):
        return _lib.bam_read_mate_ref_id(self._d_read)

    @property
    def name(self):
        return _ffi.string(_lib.bam_read_name(self._d_read).buf)

    @property
    def quality(self):
        """
        Mapping quality.
        If missing, returns -1
        """
        return _lib.bam_read_mapping_quality(self._d_read)

    @property
    def sequence(self):
        len = _lib.bam_read_sequence_length(self._d_read)
        buf = _ffi.new(_charType, len)
        _lib.bam_read_copy_sequence(self._d_read, buf)
        return _ffi.string(buf)

    def __repr__(self):
        sam = _lib.df_bam_read_to_sam(self._d_read)
        s = _ffi.string(sam.buf, sam.len)
        _lib.d_free(sam)
        return s
    
    @property
    def position(self):
        """
        Zero-based position of the leftmost mapped base on the reference
        """
        return _lib.bam_read_position(self._d_read)

    @property
    def mate_position(self):
        return _lib.bam_read_mate_position(self._d_read)

    @property
    def flag(self):
        return _lib.bam_read_flag(self._d_read)

    @property
    def template_length(self):
        return _lib.bam_read_template_length(self._d_read)

    def tag(self, tag):
        if len(tag) != 2:
            raise "Invalid tag: %s" % tag
        typeid = _lib.bam_read_tag_type_id(self._d_read, tag)
        global tag_getters
        return tag_getters[typeid](self._d_read, tag)

    @property
    def cigar(self):
        d_cigar = _lib.bam_read_cigar(self._d_read)
        return [CigarOperation(op) for op in d_cigar.buf[0:d_cigar.len]]

    @property
    def extended_cigar(self):
        d_cigar = _lib.f_bam_read_extended_cigar(self._d_read)
        result = [CigarOperation(op) for op in d_cigar.buf[0:d_cigar.len]]
        _lib.free(d_cigar)
        return result

    @property
    def is_mapped(self):
        return not _lib.bam_read_is_unmapped(self._d_read)

    @property
    def mate_is_mapped(self):
        return not _lib.bam_read_mate_is_unmapped(self._d_read)

    @property
    def proper_pair(self):
        return _lib.bam_read_proper_pair(self._d_read)

    @property
    def strand(self):
        return _lib.bam_read_strand(self._d_read)

    @property
    def mate_strand(self):
        if _lib.bam_read_mate_is_reverse_strand(self._d_read):
            return '-'
        else:
            return '+'

    @property
    def is_first_of_pair(self):
        return _lib.bam_read_is_first_of_pair(self._d_read)

    @property
    def is_second_of_pair(self):
        return _lib.bam_read_is_second_of_pair(self._d_read)

    @property
    def is_secondary(self):
        return _lib.bam_read_is_secondary_alignment(self._d_read)

    @property
    def failed_QC(self):
        return _lib.bam_read_failed_quality_control(self._d_read)

    @property
    def is_duplicate(self):
        return _lib.bam_read_is_duplicate(self._d_read)

class BamReadDRange(object):
    def __init__(self, creads):
        self._d_reads = creads

    def __del__(self):
        _lib.d_free(self._d_reads) 
    
    def __iter__(self):
        return self
    
    def next(self):
        # Here we make a deep copy of the current read,
        # using _ffi.new so that the memory is managed by Python.
        sz = _lib.bam_readrange_front_alloc_size(self._d_reads)
        if sz == 0: # empty
            raise StopIteration
        data = _ffi.new(_charType, sz)
        reader = _lib.bam_readrange_front_copy_into_and_pop_front(self._d_reads, data)
        read = BamRead.fromCopy(data, sz, reader)
        return read

class BamReaderException(Exception):
    def __init__(self):
        self.args = (_ffi.string(_lib.last_error_message()),)

class BamReferenceSequence(object):
    def __init__(self, id, name, length, d_bam):
        self.id = id
        self.name = name
        self.length = length
        self._d_bam = d_bam

    def __repr__(self):
        return "(%s) %s - length %sbp" % (self.id, self.name, self.length)

    def fetch(self, start, end):
        p = _lib.bam_reader_fetch(self._d_bam, self.name, start, end)
        if p == _ffi.NULL:
            raise BamReaderException()
        return BamReadDRange(p)

    def reads(self):
        return self.fetch(0, self.length)

class BamReader(object):
    def __init__(self, filename, threads=1):
        """
        Decompression of BGZF blocks can be run in several additional threads.
        """
        #TODO: The default value should depend on the system characteristics
        self._d_tp = _lib.task_pool_new(threads)
        self._d_bam = _lib.bam_reader_new2(filename, self._d_tp)
        if self._d_bam == _ffi.NULL:
            raise BamReaderException()

    def __del__(self):
        _lib.d_free(self._d_bam)
        _lib.task_pool_finish(_d_tp)

    @property
    def references(self):
        p = _lib.bam_reader_references(self._d_bam)
        refs = []
        for i in xrange(p.len):
            ri = p.buf[i]
            name = _ffi.string(ri.name_buf, ri.name_len)
            refs.append(BamReferenceSequence(i, name, ri.length, self._d_bam))
        return refs

    def createIndex(self, overwrite_if_exists=False):
        print self._d_bam
        _lib.bam_reader_create_index(self._d_bam, overwrite_if_exists)

    def reads(self):
        p = _lib.bam_reader_reads(self._d_bam)
        if p == _ffi.NULL:
            raise BamReaderException()
        return BamReadDRange(p)

    def fetch(self, reference_name, start, end):
        p = _lib.bam_reader_fetch(self._d_bam, reference_name, start, end)
        if p == _ffi.NULL:
            raise BamReaderException()
        return BamReadDRange(p)

    def __iter__(self):
        return self.reads()


class BamReadPythonRange(object):
    def __init__(self, callback):
        self._d_cb = callback
        self._d_reads = _lib.bam_read_range_adapter_new(self._d_cb)

    def __del__(self):
        _lib.d_free(self._d_reads) 

    @property
    def pointer(self):
        return self._d_reads
  
def makeDReadIterator(read_iter):
    read_iter = iter(read_iter)
    def next():
        try:
            r = read_iter.next()
            return r._d_read
        except StopIteration:
            return _ffi.NULL
    cb = _ffi.callback("bam_read_t(void)", next)
    return BamReadPythonRange(cb)

class Pileup(object):
    def __init__(self, read_iter, use_md=False, skip_zero_coverage=True):
        if isinstance(read_iter, BamReadDRange):
            # keep reference so that memory doesn't get freed prematurely
            self._d_iter = read_iter
            self._d_ptr = read_iter._d_reads
        else:
            self._d_iter = makeDReadIterator(read_iter)
            self._d_ptr = self._d_iter.pointer
        self._d_pileup = _lib.bam_pileup_new(self._d_ptr, use_md, 
                                            skip_zero_coverage)
        self._d_next_func = _lib.bam_pileup_next
        self._consumed_first = False

    def __del__(self):
        _lib.d_free(self._d_pileup)

    def __iter__(self):
        return self

    def next(self):
        column = self._d_next_func(self._d_pileup, self._consumed_first)
        self._consumed_first = True
        if column == _ffi.NULL:
            raise StopIteration
        return PileupColumn(column)

class PileupColumn(object):
    def __init__(self, ptr):
        self._d_column = ptr

    @property
    def reference_id(self):
        return _lib.bam_pileup_column_ref_id(self._d_column)

    @property
    def reads(self):
        array = _lib.bam_pileup_column_reads(self._d_column)
        return [PileupRead(x) for x in array.buf[0:array.len]]

    @property
    def coverage(self):
        return _lib.bam_pileup_column_coverage(self._d_column)

    @property
    def position(self):
        return _lib.bam_pileup_column_position(self._d_column)

    @property
    def bases(self):
        ptr = _lib.f_bam_pileup_column_bases(self._d_column)
        s = _ffi.string(ptr)
        _lib.free(ptr)
        return s

    @property
    def base_qualities(self):
        arr = _lib.f_bam_pileup_column_base_quals(self._d_column)
        result = list(arr.buf[0:arr.len])
        _lib.free(arr.buf)
        return result

    @property
    def reference_base(self):
        """
        Reference base if MD tags are used, otherwise 'N'
        """
        return _lib.bam_pileup_column_ref_base(self._d_column)

class PileupRead(BamRead):
    def __init__(self, cstruct):
        BamRead.__init__(self, cstruct.read)
        self._d_pread = cstruct
        self._d_addr = _ffi.addressof(cstruct)

    @property
    def current_base(self):
        return _lib.bam_pileup_read_current_base(self._d_addr)

    @property
    def current_base_quality(self):
        return _lib.bam_pileup_read_current_base_quality(self._d_addr)

    @property
    def cigar_operation(self):
        return CigarOperation(_lib.bam_pileup_read_cigar_operation(self._d_addr))

    @property
    def cigar_operation_offset(self):
        return _lib.bam_pileup_read_cigar_operation_offset(self._d_addr)

    @property
    def cigar_before(self):
        d_cigar = _lib.bam_pileup_read_cigar_before(self._d_addr)
        return [CigarOperation(op) for op in d_cigar.buf[0:d_cigar.len]]

    @property
    def cigar_after(self):
        d_cigar = _lib.bam_pileup_read_cigar_after(self._d_addr)
        return [CigarOperation(op) for op in d_cigar.buf[0:d_cigar.len]]

_lib = _ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libsambamba.so'))
_lib.attach()
