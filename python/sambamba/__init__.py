import os
fname = os.path.join(os.path.dirname(__file__), 'sambamba.h')
with open('sambamba.h', 'r') as f:
    _header = f.read()

from cffi import FFI
_ffi = FFI()
_ffi.cdef(_header)
_lib = _ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libsambamba.so'))
_lib.attach()

def _d_arr(type, cdata):
    return list(_ffi.cast(type + "[%d]" % cdata.len, cdata.buf))

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

_byteType = _ffi.typeof("uint8_t[]")
_bamReadType = _ffi.typeof("bam_read_s *")

class _tagsetter(object):
    def __init__(self, typename):
        _lib = globals()['_lib']
        self._d_fn = getattr(_lib, 'df_bam_read_set_' + typename + '_tag')

    def __call__(self, _):
        def wrapper(obj, tag, value):
            if (len(tag) != 2):
                raise InvalidTagNameException(tag)
            arr = self._d_fn(obj._d_read, tag, value)
            obj._d_read.len = arr.len
            obj._c_data = _ffi.new(_byteType, arr.len) # !!! keep it alive
            obj._d_read.buf = obj._c_data
            _lib.memcpy(obj._c_data, arr.buf, arr.len)
            _lib.d_free(arr)
        return wrapper

class CigarOperation(object):
    def __repr__(self):
        return str(self.length) + self.type

    @staticmethod
    def _raw(int32):
        length = int32 >> 4
        type = CigarOperation._type2char(int32 & 0xF)
        return CigarOperation(length, type)

    @staticmethod
    def _type2char(i):
        return "MIDNSHP=X????????"[i]

    @staticmethod
    def _char2type(c):
        i = "MIDNSHP=X".find(c)
        if i == -1:
            raise "Invalid CIGAR operation: %s" % c
        return i

    def _int(self):
        return (self.length << 4) + CigarOperation._char2type(self.type)

    def __init__(self, length, type):
        """
        Type must be one of MIDNSHP=X
        """
        self.length = length
        self.type = type

    @property
    def consumes_reference(self):
        return "M=XDN".find(self.type) != -1

    @property
    def consumes_query(self):
        return "M=XIS".find(self.type) != -1

    @property
    def consumes_both(self):
        return "M=X".find(self.type) != -1

class ReadOnlyBamRead(object):
    def __init__(self, d_ptr):
        self._d_read = d_ptr
    
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
        buf = _ffi.new(_byteType, len + 1)
        _lib.bam_read_copy_sequence(self._d_read, buf)
        return _ffi.string(buf)

    @property
    def base_qualities(self):
        arr = _lib.bam_read_base_qualities(self._d_read)
        return _d_arr("int8_t", arr)

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
    def flags(self):
        return _lib.bam_read_flag(self._d_read)

    @property
    def template_length(self):
        return _lib.bam_read_template_length(self._d_read)

    def tag(self, tag):
        if len(tag) != 2:
            raise InvalidTagNameException(tag)
        typeid = _lib.bam_read_tag_type_id(self._d_read, tag)
        global _tag_getters
        return _tag_getters[typeid](self._d_read, tag)

    @property
    def cigar(self):
        d_cigar = _lib.bam_read_cigar(self._d_read)
        return [CigarOperation._raw(op) for op in d_cigar.buf[0:d_cigar.len]]

    @property
    def cigar_string(self):
        return "".join(str(c) for c in self.cigar)

    @property
    def extended_cigar(self):
        d_cigar = _lib.f_bam_read_extended_cigar(self._d_read)
        result = [CigarOperation._raw(op) for op in d_cigar.buf[0:d_cigar.len]]
        _lib.free(d_cigar.buf)
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
        return _lib.bam_read_mate_strand(self._d_read)

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

class BamRead(ReadOnlyBamRead):
    """
    Modifiable BAM read
    """
    def __init__(self, cdata, csz, reader):
        _d_read = _ffi.new(_bamReadType)
        _d_read.len = csz
        _d_read.buf = cdata
        _d_read.reader = reader
        self._c_data = cdata # keep alive
        ReadOnlyBamRead.__init__(self, _d_read)

    @ReadOnlyBamRead.name.setter
    def name(self, new_name):
        assert(len(new_name) < 255)
        arr = _lib.df_bam_read_set_name(self._d_read, new_name)
        self._d_read.len = arr.len
        self._d_read.buf = self._c_data = _ffi.new(_byteType, arr.len)
        _lib.memcpy(self._c_data, arr.buf, arr.len)
        _lib.d_free(arr)

    @ReadOnlyBamRead.sequence.setter
    def sequence(self, new_sequence):
        """
        Sets all base qualities to 0xFF
        """
        arr = _lib.df_bam_read_set_sequence(self._d_read, new_sequence)
        self._d_read.len = arr.len
        self._d_read.buf = self._c_data = _ffi.new(_byteType, arr.len)
        _lib.memcpy(self._c_data, arr.buf, arr.len)
        _lib.d_free(arr)

    @ReadOnlyBamRead.base_qualities.setter
    def base_qualities(self, base_qualities):
        assert(len(base_qualities) == _lib.bam_read_sequence_length(self._d_read))
        quals = _ffi.new("int8_t[]", base_qualities)
        arr = _lib.df_bam_read_set_base_qualities(self._d_read, quals, len(base_qualities))
        self._d_read.len = arr.len
        self._d_read.buf = self._c_data = _ffi.new(_byteType, arr.len)
        _lib.memcpy(self._c_data, arr.buf, arr.len)
        _lib.d_free(arr)

    @ReadOnlyBamRead.cigar.setter
    def cigar(self, new_cigar):
        length = len(new_cigar)
        ints = _ffi.new("uint32_t[]", [c._int() for c in new_cigar])
        arr = _lib.df_bam_read_set_cigar(self._d_read, ints, length)
        self._d_read.len = arr.len
        self._d_read.buf = self._c_data = _ffi.new(_byteType, arr.len)
        _lib.memcpy(self._c_data, arr.buf, arr.len)
        _lib.d_free(arr)

    @ReadOnlyBamRead.reference_id.setter
    def reference_id(self, new_id):
        _lib.bam_read_set_ref_id(self._d_read, new_id)

    @ReadOnlyBamRead.position.setter
    def position(self, new_pos):
        _lib.bam_read_set_position(self._d_read, new_pos)

    @ReadOnlyBamRead.quality.setter
    def quality(self, new_qual):
        _lib.bam_read_set_mapping_quality(self._d_read, new_qual)

    @ReadOnlyBamRead.flags.setter
    def flags(self, new_flags):
        _lib.bam_read_set_flag(self._d_read, new_flags)

    @ReadOnlyBamRead.mate_reference_id.setter
    def mate_reference_id(self, new_mate_ref_id):
        _lib.bam_read_set_mate_ref_id(self._d_read, new_mate_ref_id)

    @ReadOnlyBamRead.mate_position.setter
    def mate_position(self, new_mate_pos):
        _lib.bam_read_set_mate_position(self._d_read, new_mate_pos)

    @ReadOnlyBamRead.template_length.setter
    def template_length(self, new_tlen):
        _lib.bam_read_set_template_length(self._d_read, new_tlen)
    
    @ReadOnlyBamRead.is_mapped.setter
    def is_mapped(self, value):
        return not _lib.bam_read_set_is_unmapped(self._d_read, value)

    @ReadOnlyBamRead.mate_is_mapped.setter
    def mate_is_mapped(self, value):
        return not _lib.bam_read_set_mate_is_unmapped(self._d_read, value)

    @ReadOnlyBamRead.proper_pair.setter
    def proper_pair(self, value):
        return _lib.bam_read_set_proper_pair(self._d_read, value)

    @ReadOnlyBamRead.strand.setter
    def strand(self, value):
        assert(value == '+' or value == '-')
        return _lib.bam_read_set_strand(self._d_read, value)

    @ReadOnlyBamRead.mate_strand.setter
    def mate_strand(self, strand, value):
        assert(value == '+' or value == '-')
        return _lib.bam_read_set_mate_strand(self._d_read, value)

    @ReadOnlyBamRead.is_first_of_pair.setter
    def is_first_of_pair(self, value):
        return _lib.bam_read_set_is_first_of_pair(self._d_read, value)

    @ReadOnlyBamRead.is_second_of_pair.setter
    def is_second_of_pair(self, value):
        return _lib.bam_read_set_is_second_of_pair(self._d_read, value)

    @ReadOnlyBamRead.is_secondary.setter
    def is_secondary(self, value):
        return _lib.bam_read_set_is_secondary_alignment(self._d_read, value)

    @ReadOnlyBamRead.failed_QC.setter
    def failed_QC(self, value):
        return _lib.bam_read_set_failed_quality_control(self._d_read, value)

    @ReadOnlyBamRead.is_duplicate.setter
    def is_duplicate(self, value):
        return _lib.bam_read_set_is_duplicate(self._d_read, value)

    @_tagsetter("char")
    def setCharTag(self, tag, value):
        pass

    @_tagsetter("uint8")
    def setUInt8Tag(self, tag, value):
        pass

    @_tagsetter("int8")
    def setInt8Tag(self, tag, value):
        pass

    @_tagsetter("uint16")
    def setUInt16Tag(self, tag, value):
        pass
    
    @_tagsetter("int16")
    def setInt16Tag(self, tag, value):
        pass

    @_tagsetter("uint32")
    def setUInt32Tag(self, tag, value):
        pass

    @_tagsetter("int32")
    def setInt32Tag(self, tag, value):
        pass

    @_tagsetter("float")
    def setFloatTag(self, tag, value):
        pass

    @_tagsetter("string")
    def setStringTag(self, tag, value):
        pass


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
        data = _ffi.new(_byteType, sz)
        reader = _lib.bam_readrange_front_copy_into_and_pop_front(self._d_reads, data)
        read = BamRead(data, sz, reader)
        return read

class BamReaderException(Exception):
    def __init__(self):
        self.args = (_ffi.string(_lib.last_error_message()),)

class BamWriterException(Exception):
    def __init__(self):
        self.args = (_ffi.string(_lib.last_error_message()),)

class InvalidTagNameException(Exception):
    def __init__(self, tagname):
        self.args = ("Invalid tag name: %s" % tagname, )

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
        _lib.task_pool_finish(self._d_tp)
        _lib.d_free(self._d_tp)

    @property
    def header(self):
        """
        SAM header (text)
        """
        header = _lib.bam_reader_header(self._d_bam)
        dtext = _lib.df_sam_header_text(header)
        text = _ffi.string(dtext.buf, dtext.len)
        _lib.d_free(dtext)
        return text

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

class BamWriter(object):
    def __init__(self, filename, threads=1, compression_level=-1):
        self._task_pool = _lib.task_pool_new(threads)
        self._d_writer = _lib.bam_writer_new2(filename, compression_level, self._task_pool)
        if self._d_writer == _ffi.NULL:
            raise BamWriterException()

    def writeHeader(self, sam_header_text):
        d_header = _lib.sam_header_new(sam_header_text)
        if d_header == _ffi.NULL:
            raise BamWriterException()
        ret = _lib.bam_writer_push_header(self._d_writer, d_header)
        _lib.d_free(d_header)
        if ret < 0:
            raise BamWriterException()

    def writeRefs(self, references):
        """
        references must be a list of BamReferenceSequence objects
        """
        n = len(references)
        info = _ffi.new("reference_info_s[]", n)
        for i, ref in enumerate(references):
            info[i].name_len = len(ref.name)
            info[i].name_buf = _ffi.new("char[]", ref.name)
            info[i].length = ref.length;
        ret = _lib.bam_writer_push_ref_info(self._d_writer, info, n)
        if ret < 0:
            raise BamWriterException()

    def writeRead(self, read):
        ret = _lib.bam_writer_push_read(self._d_writer, read._d_read)
        if ret < 0:
            raise BamWriterException()

    def close(self):
        """
        Flush the buffers and append EOF block
        """
        ret = _lib.bam_writer_close(self._d_writer)
        if ret < 0:
            raise BamWriterException()

    def __del__(self):
        _lib.bam_writer_close(self._d_writer)
        _lib.task_pool_finish(self._task_pool)
        _lib.d_free(self._task_pool)
        _lib.d_free(self._d_writer)

class BamReadPythonRange(object):
    def __init__(self, callback):
        self._d_cb = callback
        self._d_reads = _lib.bam_read_range_adapter_new(self._d_cb)

    def __del__(self):
        _lib.d_free(self._d_reads) 
  
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
            self._d_ptr = self._d_iter._d_reads
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

class PileupRead(ReadOnlyBamRead):
    """
    WARNING:
    Pileup read can be used only while operating on the *current column*.
    It is a read-only interface to the part of internal data structure,
    and pileup engine is free to move the reads around in the memory 
    when it advances to the next position on the reference.
    (More specifically, the pileup engine maintains an array of reads
     overlapping the current column, and PileupRead merely references 
     an element of that array for the sake of performance.)
    """
    def __init__(self, cstruct):
        ReadOnlyBamRead.__init__(self, cstruct.read)
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
        return CigarOperation._raw(_lib.bam_pileup_read_cigar_operation(self._d_addr))

    @property
    def cigar_operation_offset(self):
        return _lib.bam_pileup_read_cigar_operation_offset(self._d_addr)

    @property
    def cigar_before(self):
        d_cigar = _lib.bam_pileup_read_cigar_before(self._d_addr)
        return [CigarOperation._raw(op) for op in d_cigar.buf[0:d_cigar.len]]

    @property
    def cigar_after(self):
        d_cigar = _lib.bam_pileup_read_cigar_after(self._d_addr)
        return [CigarOperation._raw(op) for op in d_cigar.buf[0:d_cigar.len]]
