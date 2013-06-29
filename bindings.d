module testlib;

import bio.sam.header;
import bio.bam.reader;
import bio.bam.writer;
import bio.bam.read;
import bio.bam.referenceinfo;
import bio.bam.pileup;
import bio.bam.thirdparty.msgpack;

import core.memory : GC;
import std.c.stdlib : malloc, free;
import std.conv;
import std.range;
import std.typecons;
import std.typetuple;
import std.algorithm;
import std.traits;
import std.string;
import std.parallelism;

import core.runtime : Runtime;

debug import std.stdio;

extern (C) export void attach() { Runtime.initialize(); }
extern (C) export void detach() { Runtime.terminate(); }

extern (C) export void d_free(void* p) { GC.removeRange(p); free(p); }

void main() {}

__gshared string error_message;
void setErrorMessage(string msg) { 
    synchronized {
        error_message = msg ~ '\0';
    }
}

extern(C) export immutable(char)* last_error_message() {
    return error_message.ptr;
}

struct DArray(T) { T* ptr; ulong length; }
auto d_array(T)(T[] array) { return DArray!T(array.ptr, array.length); }

// -------------------------------------------------------------------------

import std.range;

template Handle(T) {
    struct Handle { T instance; }
}

template DtoC(T) {
    static if (is(T == void))
        alias void DtoC;
    else static if (isNumeric!T || isSomeChar!T || isPointer!T || isBoolean!T)
        alias Unqual!T DtoC;
    else static if (is(T == string))
        alias DArray!(immutable(char)) DtoC;
    else static if (isDynamicArray!T)
        alias DArray!(ElementType!T) DtoC;
    else
        alias Handle!T* DtoC;
}

template CtoD(T) {
    static if (is(T == void))
        alias void CtoD;
    else static if (is(T == Handle!C*, C))
        alias C CtoD;
    else static if (is(T == DArray!U, U))
        alias U[] CtoD;
    else static if (isNumeric!T || isBoolean!T || isSomeChar!T || isPointer!T)
        alias T CtoD;
}

auto convertCtoD(T)(T obj) {
    static if (is(T == Handle!U, U) || is(T == Handle!U*, U))
        return obj.instance;
    else static if (isNumeric!T || isSomeChar!T || isPointer!T || isBoolean!T)
        return obj;
    else static if (is(T == DArray!U, U))
        return obj.ptr[0 .. obj.length];
    else static assert(false);
}

auto convertDtoC(T)(T obj) {
    static if (isNumeric!T || isSomeChar!T || isPointer!T || isBoolean!T)
        return obj;
    else static if (is(T == string))
        return d_array(obj);
    else static if (is(T == class) || is(T == struct) || is(T == interface)) {
        return createHandle(obj);
    }
    else static if (isDynamicArray!T)
        return d_array(obj);
    else static assert(false);
}

Handle!C* createHandle(C)(C obj) if (is(C == class) || is(C == interface)) {
    if (obj is null)
        return null;

    auto p = cast(Handle!C*)malloc(Handle!C.sizeof);
    debug writeln("[createHandle/", C.stringof, "] allocated ", Handle!C.sizeof, " bytes");

    GC.addRange(p, Handle!C.sizeof);
    p.instance = obj;
    return p;
}

Handle!S* createHandle(S)(auto ref S obj) if (is(S == struct)) {
    auto p = cast(Handle!S*) malloc(Handle!S.sizeof);
    debug writeln("[createHandle/", S.stringof, "] allocated ", Handle!S.sizeof, " bytes");

    memcpy(p, &obj, S.sizeof);
    static if (hasIndirections!S)
        GC.addRange(p, S.sizeof);
    return p;
}

mixin template constructorWrapper(string exportName, C, Args...) 
    if (is(C == class)) 
{
    alias Handle!C H;
    alias staticMap!(DtoC, Args) CArgs;

    pragma(mangle, exportName)
    extern(C) export int helper(H** object, CArgs args) {
        try {
            Tuple!Args d_args;
            foreach (i, e; args)
                d_args[i] = convertCtoD(e);
            auto obj = new C(d_args.expand);
            *object = createHandle(obj);
        } catch (Throwable e) {
            setErrorMessage(e.msg);
            return 1;
        }
        return 0;
    }
}

mixin template constructorWrapperNothrow(string exportName, C, Args...) 
    if (is(C == class)) 
{
    alias Handle!C H;
    alias staticMap!(DtoC, Args) CArgs;

    pragma(mangle, exportName)
    extern(C) export H* helper(CArgs args) {
        Tuple!Args d_args;
        foreach (i, e; args)
            d_args[i] = convertCtoD(e);
        auto obj = new C(d_args.expand);
        return createHandle(obj);
    }
}

// ---------------------- function/method wrapping -------------------------------------------
mixin template commonBoilerplate(string wrapperName, string exportName, ReturnType, Args...) {
    alias DtoC!ReturnType CReturnType;
    alias staticMap!(DtoC, Args) CArgs;

    debug {
        enum printResult = isNumeric!ReturnType || 
                           isSomeString!ReturnType || 
                           isBoolean!ReturnType;

        static if (!is(ReturnType == void))
        void showResult(ReturnType d_result) {
            static if (printResult) writeln("    result: ", d_result);
        }
    }

    debug void printFuncName() {
        writeln("[", wrapperName, "/", exportName, "] : ", 
                CArgs.stringof, " => ", CReturnType.stringof);
    }
}

mixin template commonMWBoilerplate(string wrapperName, 
        string exportName, T, string methodName, Args...) 
{
    enum ret = "T.init." ~ methodName ~ "(Tuple!Args.init.expand)";
    alias typeof(mixin(ret)) ReturnType;
    mixin commonBoilerplate!(wrapperName, exportName, ReturnType, Args);
    alias Handle!T H;
    
    auto getDResult(H* handle, CArgs args) {
        Tuple!Args d_args;
        foreach (i, e; args)
            d_args[i] = convertCtoD(e);

        enum ret = "handle.instance." ~ methodName ~ "(d_args.expand)";
        debug printFuncName();
        static if (is(ReturnType == void)) {
            mixin(ret ~ ";");
        } else {
            mixin(q{auto d_result = } ~ ret ~ ";");
            debug showResult(d_result);
            return d_result;
        }
    }
}

mixin template commonFWBoilerplate(string wrapperName, 
        string exportName, string functionName, Args...) 
{
    enum ret = functionName ~ "(Tuple!Args.init.expand)";
    alias typeof(mixin(ret)) ReturnType;
    mixin commonBoilerplate!(wrapperName, exportName, ReturnType, Args);

    auto getDResult(CArgs args) {
        Tuple!Args d_args;
        foreach (i, e; args)
            d_args[i] = convertCtoD(e);

        enum ret = functionName ~ "(d_args.expand)";
        debug printFuncName();
        static if (is(ReturnType == void)) {
            mixin(ret ~ ";");
        } else {
            mixin(q{auto d_result = } ~ ret ~ ";");
            debug showResult(d_result);
            return d_result;
        }
    }
}

mixin template functionWrapperHelper(string exportName, ReturnType, CArgs...)
{
    static if(is(ReturnType == void)) {
        pragma(mangle, exportName)
        extern(C) export int helper(CArgs args) {
            try {
                d_result(args);
            } catch (Throwable e) {
                setErrorMessage(e.msg);
                return 1;
            }
            return 0;
        }
    } else {
        pragma(mangle, exportName)
        extern(C) export int helper(DtoC!ReturnType* result, CArgs args) {
            try {
                auto d_result = getDResult(args);
                *result = cast()convertDtoC(d_result);
            } catch (Throwable e) {
                setErrorMessage(e.msg);
                return 1;
            }
            return 0;
        }
    }
}

mixin template functionWrapperHelperNothrow(string exportName, ReturnType, CArgs...)
{
    static if(is(ReturnType == void)) {
        pragma(mangle, exportName)
        extern(C) export void helper(CArgs args) {
            debug {
                try {
                    getDResult(args);
                } catch (Throwable e) {
                    import std.stdio;
                    stderr.writeln(e.msg);
                }
            } else {
                getDResult(args);
            }
        }
    } else {
        pragma(mangle, exportName)
        extern(C) export CReturnType helper(CArgs args) {
            version(Debug) {
                try {
                    auto d_result = getDResult(args);
                } catch (Throwable e) {
                    import std.stdio;
                    stderr.writeln(e.msg);
                }
            } else {
                auto d_result = getDResult(args);
            }
            return cast()convertDtoC(d_result);
        }
    }
}

mixin template methodWrapper(string exportName, T, string methodName, Args...) 
{
    mixin commonMWBoilerplate!("methodWrapper", exportName, T, methodName, Args);
    alias TypeTuple!(H*, CArgs) FullArgs;
    mixin functionWrapperHelper!(exportName, ReturnType, FullArgs);
}

mixin template methodWrapperNothrow(string exportName, T, string methodName, Args...) 
{
    mixin commonMWBoilerplate!("methodWrapperNothrow", exportName, T, methodName, Args);
    alias TypeTuple!(H*, CArgs) FullArgs;
    mixin functionWrapperHelperNothrow!(exportName, ReturnType, FullArgs);
}

mixin template functionWrapper(string exportName, string functionName, Args...) 
{
    mixin commonFWBoilerplate!("functionWrapper", exportName, functionName, Args);
    mixin functionWrapperHelper!(exportName, ReturnType, CArgs);
}

mixin template functionWrapperNothrow(string exportName, string functionName, Args...) 
{
    mixin commonFWBoilerplate!("functionWrapperNothrow", exportName, functionName, Args);
    mixin functionWrapperHelperNothrow!(exportName, ReturnType, CArgs);
}

string returnNullOnException(string code) {
    return "try {"
        ~ code ~ `
    } catch (Throwable e) {
        import std.stdio;
        setErrorMessage(e.msg);
        return null;
    }`;
}

string returnMinusOneOnException(string code) {
    return "try {"
        ~ code ~ `
        return 0;
    } catch (Throwable e) {
        import std.stdio;
        debug { writeln("*** Caught exception *** ", e); }
        setErrorMessage(e.msg);
        return -1;
    }`;
}

// ------------------------- end of function/method wrapping ------------------------------------

alias constructorWrapperNothrow constructorN;
alias methodWrapperNothrow methodN;
alias functionWrapperNothrow functionN;

/* --------------------- TaskPool interface --------------------------------------------------------------- */
mixin constructorN!("task_pool_new", TaskPool, uint);
mixin methodN!("task_pool_finish", TaskPool, "finish");

/* --------------------- BamReader interface -------------------------------------------------------------- */
BamReader bamReaderNew1(immutable(char)* filename) { 
    mixin(returnNullOnException(q{
        return new BamReader(to!string(filename)); 
    }));
}

BamReader bamReaderNew2(immutable(char)* filename, TaskPool taskpool) { 
    mixin(returnNullOnException(q{
        return new BamReader(to!string(filename), taskpool); 
    }));
}

mixin functionN!("bam_reader_new", "bamReaderNew1", immutable(char)*);
mixin functionN!("bam_reader_new2", "bamReaderNew2", immutable(char)*, TaskPool);
mixin methodN!("bam_reader_filename", BamReader, "filename");
mixin methodN!("bam_reader_create_index", BamReader, "createIndex", bool);
mixin methodN!("bam_reader_references", BamReader, "reference_sequences");
alias InputRange!BamRead BamReadRange;

BamReadRange bamReaderFetchC(BamReader b, char* ref_name, uint start, uint end) {
    mixin(returnNullOnException(q{
        auto reads = b[to!string(ref_name)][start .. end];
        return inputRangeObject(map!"a.read"(reads));
    }));
}
mixin methodN!("bam_reader_fetch", BamReader, "bamReaderFetchC", char*, uint, uint);

BamReadRange bamReaderReadsC(BamReader b) { 
    mixin(returnNullOnException(q{
        return inputRangeObject(b.reads); 
    }));
}
mixin methodN!("bam_reader_reads", BamReader, "bamReaderReadsC");

/* ------------------ BamReadRange interface -------------------------------------------------------------- */
mixin methodN!("bam_readrange_front", BamReadRange, "front");
mixin methodN!("bam_readrange_empty", BamReadRange, "empty");
mixin methodN!("bam_readrange_pop_front", BamReadRange, "popFront");

size_t frontAllocSize(BamReadRange range) {
    if (range.empty)
        return 0;
    return range.front.size_in_bytes - 4;
}

ubyte[] getBuffer(BamRead read) {
    return *(cast(ubyte[]*)(&read));
}

// Returns pointer to the reader;
// copies the chunk to the provided buffer;
// advances the range.
// ----------------
// Sounds rather crazy, huh? 
// But this way, only two FFI calls per read are needed.
void* frontCopyIntoAndPopFront(BamReadRange range, ubyte* ptr) {
    auto read = range.front;
    auto chunk = read.getBuffer();
    ptr[0 .. chunk.length] = chunk[];
    ptr[32 + read.name.length] = 0; // HACK _is_slice = false
    auto result = cast(void*)(range.front.reader);
    range.popFront();
    return result;
}

mixin methodN!("bam_readrange_front_alloc_size", BamReadRange, "frontAllocSize");
mixin methodN!("bam_readrange_front_copy_into_and_pop_front", BamReadRange, "frontCopyIntoAndPopFront", ubyte*);

/* ------------------ BamRead interface ------------------------------------------------------------------- */
mixin methodN!("bam_read_name", BamRead, "name");
mixin methodN!("bam_read_sequence_length", BamRead, "sequence_length");
mixin methodN!("bam_read_mapping_quality", BamRead, "mapping_quality");
mixin methodN!("bam_read_ref_id", BamRead, "ref_id");
mixin methodN!("bam_read_position", BamRead, "position");
mixin methodN!("bam_read_mate_ref_id", BamRead, "mate_ref_id");
mixin methodN!("bam_read_mate_position", BamRead, "mate_position");
mixin methodN!("bam_read_flag", BamRead, "flag");
mixin methodN!("bam_read_template_length", BamRead, "template_length");

auto bamReadToSamC(BamRead read) { return d_array(to!string(read)); }
mixin methodN!("df_bam_read_to_sam", BamRead, "bamReadToSamC");

immutable(char)* bamReadReferenceNameC(BamRead read) {
    if (read.ref_id == -1) {
        return "*".ptr;
    }
    return read.reader.reference_sequences[read.ref_id].name.ptr;
}

string bamReadReferenceName(BamRead read) {
    if (read.ref_id == -1) {
        return "*";
    }
    return read.reader.reference_sequences[read.ref_id].name;
}
mixin methodN!("bam_read_reference_name", BamRead, "bamReadReferenceNameC");
mixin methodN!("bam_read_reference_name2", BamRead, "bamReadReferenceName");

void bamReadCopySequenceC(BamRead read, char* buf) { 
    auto q = buf;
    foreach (base; read.sequence) *q++ = base;
    *q = 0;
}
mixin methodN!("bam_read_copy_sequence", BamRead, "bamReadCopySequenceC", char*);

extern(C) export uint bam_cigar_operation_length(CigarOperation op) { return op.length; }
extern(C) export char bam_cigar_operation_type(CigarOperation op) { return op.type; }
extern(C) export bool bam_cigar_operation_consumes_ref(CigarOperation op) { return op.is_reference_consuming; }
extern(C) export bool bam_cigar_operation_consumes_query(CigarOperation op) { return op.is_query_consuming; }
extern(C) export bool bam_cigar_operation_consumes_both(CigarOperation op) { return op.is_match_or_mismatch; }
mixin methodN!("bam_read_cigar", BamRead, "cigar");

CigarOperation[] bamReadExtendedCigarC(BamRead read) {
    auto len = read.extended_cigar.walkLength();
    auto p = cast(CigarOperation*)malloc(len * CigarOperation.sizeof);
    auto q = p;
    foreach (op; read.extended_cigar) *q++ = op;
    return p[0 .. len];
}
mixin methodN!("f_bam_read_extended_cigar", BamRead, "bamReadExtendedCigarC");
mixin methodN!("bam_read_bases_covered", BamRead, "basesCovered");

mixin methodN!("bam_read_strand", BamRead, "strand");
extern(C) export char bam_read_mate_strand(BamRead* read) { return read.mate_is_reverse_strand ? '-' : '+'; }
mixin methodN!("bam_read_base_qualities", BamRead, "base_qualities");

/* -------------------- flag getters ---------------------------------------------------------------------- */
mixin methodN!("bam_read_is_paired", BamRead, "is_paired");
mixin methodN!("bam_read_proper_pair", BamRead, "proper_pair");
mixin methodN!("bam_read_is_unmapped", BamRead, "is_unmapped");
mixin methodN!("bam_read_mate_is_unmapped", BamRead, "mate_is_unmapped");
mixin methodN!("bam_read_is_reverse_strand", BamRead, "is_reverse_strand");
mixin methodN!("bam_read_mate_is_reverse_strand", BamRead, "mate_is_reverse_strand");
mixin methodN!("bam_read_is_first_of_pair", BamRead, "is_first_of_pair");
mixin methodN!("bam_read_is_second_of_pair", BamRead, "is_second_of_pair");
mixin methodN!("bam_read_is_secondary_alignment", BamRead, "is_secondary_alignment");
mixin methodN!("bam_read_failed_quality_control", BamRead, "failed_quality_control");
mixin methodN!("bam_read_is_duplicate", BamRead, "is_duplicate");

/* -------------------- tag getters ----------------------------------------------------------------------- */
ubyte bamReadTagTypeId(BamRead read, immutable(char)* tag) { auto v = read[tag[0 .. 2]]; return v.tag; }
mixin methodN!("bam_read_tag_type_id", BamRead, "bamReadTagTypeId", immutable(char)*);

T bamReadTagC(T)(BamRead read, immutable(char)* tag) { auto v = read[tag[0 .. 2]]; return *cast(T*)(&v); }
/* the following functions are meant to be wrapped with a high-level interface, 
   which checks type id of a tag and calls the corresponding function */
mixin methodN!("bam_read_string_tag", BamRead, q{bamReadTagC!string}, immutable(char)*);
mixin methodN!("bam_read_char_tag", BamRead, q{bamReadTagC!char}, immutable(char)*);
mixin methodN!("bam_read_int8_tag", BamRead, q{bamReadTagC!byte}, immutable(char)*);
mixin methodN!("bam_read_uint8_tag", BamRead, q{bamReadTagC!ubyte}, immutable(char)*);
mixin methodN!("bam_read_int16_tag", BamRead, q{bamReadTagC!short}, immutable(char)*);
mixin methodN!("bam_read_uint16_tag", BamRead, q{bamReadTagC!ushort}, immutable(char)*);
mixin methodN!("bam_read_int32_tag", BamRead, q{bamReadTagC!int}, immutable(char)*);
mixin methodN!("bam_read_uint32_tag", BamRead, q{bamReadTagC!uint}, immutable(char)*);
mixin methodN!("bam_read_float_tag", BamRead, q{bamReadTagC!float}, immutable(char)*);
mixin methodN!("bam_read_int8_array_tag", BamRead, q{bamReadTagC!(byte[])}, immutable(char)*);
mixin methodN!("bam_read_uint8_array_tag", BamRead, q{bamReadTagC!(ubyte[])}, immutable(char)*);
mixin methodN!("bam_read_int16_array_tag", BamRead, q{bamReadTagC!(short[])}, immutable(char)*);
mixin methodN!("bam_read_uint16_array_tag", BamRead, q{bamReadTagC!(ushort[])}, immutable(char)*);
mixin methodN!("bam_read_int32_array_tag", BamRead, q{bamReadTagC!(int[])}, immutable(char)*);
mixin methodN!("bam_read_uint32_array_tag", BamRead, q{bamReadTagC!(uint[])}, immutable(char)*);
mixin methodN!("bam_read_float_array_tag", BamRead, q{bamReadTagC!(float[])}, immutable(char)*);

/// How about (input) ranges created in the dynamic language?
/// The simplest interface is a callback T* next()
/// which returns null to designate that the range is empty.
struct OuterRange(T) {
    private T* function() _next;
    private T _front;
    private bool _empty = false;

    this(T* function() next) {
        _next = next;
        auto front = _next();
        if (front is null) {
            _empty = true;
        } else {
            _front = front.dup;
        }
    }

    bool empty() @property { return _empty; }
    T front() @property { return _front; }
    void popFront() {
        auto front = _next();
        if (front is null) {
            _empty = true;
        } else {
            _front = front.dup;
        }
    }
}

BamReadRange makeReadRange(BamRead* function() next) {
    return inputRangeObject(OuterRange!BamRead(next));
}
/// now if a callback of type BamRead* function() is provided, we can use it as a D range!
mixin functionN!("bam_read_range_adapter_new", "makeReadRange", BamRead* function());

/* ---------------------------- Pileup engine --------------------------------------------------- */
alias std.traits.ReturnType!(pileupColumns!BamReadRange) BamPileupRange;
alias PileupRead!EagerBamRead BamPileupRead;
alias PileupColumn!(BamPileupRead[]) BamPileupColumn;
mixin functionN!("bam_pileup_new", q{pileupColumns!BamReadRange}, BamReadRange, bool, bool);

// this is surely a weird interface but it allows to move to the next element in one FFI call
// instead of two or three (empty/front/popFront)
extern(C) export BamPileupColumn* bam_pileup_next(BamPileupRange* range, bool do_pop_front) { 
    if (do_pop_front)
        range.popFront();
    if (range.empty)
        return null;
    return &(range.front());
}

BamPileupRead[] pileupColumnReads(BamPileupColumn* column) {
    return column.reads.release();
}
mixin functionN!("bam_pileup_column_reads", "pileupColumnReads", BamPileupColumn*);
mixin methodN!("bam_pileup_column_coverage", BamPileupColumn, "coverage");
mixin methodN!("bam_pileup_column_position", BamPileupColumn, "position");
mixin methodN!("bam_pileup_column_ref_id", BamPileupColumn, "ref_id");
mixin methodN!("bam_pileup_column_ref_base", BamPileupColumn, "reference_base");

char* bamPileupColumnBasesC(BamPileupColumn* column) {
    auto cov = column.coverage;
    char* s = cast(char*)malloc(cov + 1);
    foreach (i; 0 .. cov) s[i] = column.reads[i].current_base;
    s[cov] = '\0';
    return s;
}
ubyte[] bamPileupColumnBaseQualsC(BamPileupColumn* column) {
    auto cov = column.coverage;
    ubyte* s = cast(ubyte*)malloc(cov);
    foreach (i; 0 .. cov) s[i] = column.reads[i].current_base_quality;
    return s[0 .. cov];
}
mixin functionN!("f_bam_pileup_column_bases", "bamPileupColumnBasesC", BamPileupColumn*);
mixin functionN!("f_bam_pileup_column_base_quals", "bamPileupColumnBaseQualsC", BamPileupColumn*);
bool bamPileupColumnIsUnivocalC(BamPileupColumn* column) {
    auto reads = column.reads;
    auto cov = reads.length;
    if (reads.empty()) return true;
    auto base = reads[0].current_base;
    reads.popFront();
    foreach (r; reads)
        if (r.current_base != base)
            return false;
    return true;
}
mixin functionN!("bam_pileup_column_is_univocal", "bamPileupColumnIsUnivocalC", BamPileupColumn*);

mixin methodN!("bam_pileup_read_current_base", BamPileupRead, "current_base");
mixin methodN!("bam_pileup_read_current_base_quality", BamPileupRead, "current_base_quality");
extern(C) export auto bam_pileup_read_cigar_operation(BamPileupRead* read) { return read.cigar_operation; }
mixin methodN!("bam_pileup_read_cigar_operation_offset", BamPileupRead, "cigar_operation_offset");
mixin methodN!("bam_pileup_read_cigar_before", BamPileupRead, "cigar_before");
mixin methodN!("bam_pileup_read_cigar_after", BamPileupRead, "cigar_after");
mixin methodN!("bam_pileup_read_query_offset", BamPileupRead, "query_offset");

BamWriter bamWriterNew(char* filename, int compression_level) {
    mixin(returnNullOnException(q{
        return new BamWriter(to!string(filename), compression_level);
    }));
}

BamWriter bamWriterNew2(char* filename, int compression_level, TaskPool pool) {
    mixin(returnNullOnException(q{
        return new BamWriter(to!string(filename), compression_level, pool);
    }));
}

int bamWriterPushHeader(BamWriter writer, SamHeader header) {
    mixin(returnMinusOneOnException(q{ writer.writeSamHeader(header); }));
}

int bamWriterPushReferenceInfo(BamWriter writer, ReferenceSequenceInfo* info, size_t n) {
    mixin(returnMinusOneOnException(q{ 
        auto duped_info = info[0 .. n].dup;
        foreach (ref seq; duped_info)
            seq = ReferenceSequenceInfo(seq.name.idup, seq.length);
        writer.writeReferenceSequenceInfo(duped_info); 
    }));
}

int bamWriterPushRead(BamWriter writer, BamRead read) {
    mixin(returnMinusOneOnException(q{ writer.writeRecord(read); }));
}

int bamWriterClose(BamWriter writer) { mixin(returnMinusOneOnException(q{ writer.finish(); })); }
int bamWriterFlush(BamWriter writer) { mixin(returnMinusOneOnException(q{ writer.flush(); })); }

mixin functionN!("bam_writer_new", "bamWriterNew", char*, int);
mixin functionN!("bam_writer_new2", "bamWriterNew2", char*, int, TaskPool);
mixin functionN!("bam_writer_push_header", "bamWriterPushHeader", BamWriter, SamHeader);
mixin functionN!("bam_writer_push_ref_info", "bamWriterPushReferenceInfo", BamWriter, ReferenceSequenceInfo*, size_t);
mixin functionN!("bam_writer_push_read", "bamWriterPushRead", BamWriter, BamRead);
mixin functionN!("bam_writer_close", "bamWriterClose", BamWriter);
mixin functionN!("bam_writer_flush", "bamWriterFlush", BamWriter);

SamHeader samHeaderNew(char* text) {
    mixin(returnNullOnException(q{ return new SamHeader(to!string(text)); }));
}

auto samHeaderText(SamHeader header) { return d_array(header.text); }
mixin methodN!("bam_reader_header", BamReader, "header");
mixin functionN!("sam_header_new", "samHeaderNew", char*);
mixin functionN!("df_sam_header_text", "samHeaderText", SamHeader);

/* ------------------------------- modifying reads ------------------------------------------ */
auto setTagValue(T)(BamRead read, immutable(char)* tagname, T value) {
    auto r = read.dup; // TODO: find a way without so much copying
    r[tagname[0 .. 2]] = value;
    return d_array(r.getBuffer());
}

auto bamReadSetStringTagC(BamRead read, immutable(char)* tagname, immutable(char)* value) {
    auto r = read.dup;
    r[tagname[0 .. 2]] = to!string(value);
    return d_array(r.getBuffer());
}

mixin methodN!("df_bam_read_set_char_tag", BamRead, q{setTagValue!char}, immutable(char)*, char);
mixin methodN!("df_bam_read_set_int8_tag", BamRead, q{setTagValue!byte}, immutable(char)*, byte);
mixin methodN!("df_bam_read_set_uint8_tag", BamRead, q{setTagValue!ubyte}, immutable(char)*, ubyte);
mixin methodN!("df_bam_read_set_int16_tag", BamRead, q{setTagValue!short}, immutable(char)*, short);
mixin methodN!("df_bam_read_set_uint16_tag", BamRead, q{setTagValue!ushort}, immutable(char)*, ushort);
mixin methodN!("df_bam_read_set_int32_tag", BamRead, q{setTagValue!int}, immutable(char)*, int);
mixin methodN!("df_bam_read_set_uint32_tag", BamRead, q{setTagValue!uint}, immutable(char)*, uint);
mixin methodN!("df_bam_read_set_float_tag", BamRead, q{setTagValue!float}, immutable(char)*, float);
mixin methodN!("df_bam_read_set_string_tag", BamRead, "bamReadSetStringTagC", immutable(char)*, immutable(char)*);

mixin methodN!("bam_read_set_ref_id", BamRead, "ref_id", int);
mixin methodN!("bam_read_set_position", BamRead, "position", int);
mixin methodN!("bam_read_set_mapping_quality", BamRead, "mapping_quality", ubyte);
mixin methodN!("bam_read_set_flag", BamRead, "flag", ushort);
mixin methodN!("bam_read_set_mate_ref_id", BamRead, "mate_ref_id", int);
mixin methodN!("bam_read_set_mate_position", BamRead, "mate_position", int);
mixin methodN!("bam_read_set_template_length", BamRead, "template_length", int);

mixin methodN!("bam_read_set_is_paired", BamRead, "is_paired", bool);
mixin methodN!("bam_read_set_proper_pair", BamRead, "proper_pair", bool);
mixin methodN!("bam_read_set_is_unmapped", BamRead, "is_unmapped", bool);
mixin methodN!("bam_read_set_mate_is_unmapped", BamRead, "mate_is_unmapped", bool);
mixin methodN!("bam_read_set_is_reverse_strand", BamRead, "is_reverse_strand", bool);
mixin methodN!("bam_read_set_mate_is_reverse_strand", BamRead, "mate_is_reverse_strand", bool);
mixin methodN!("bam_read_set_is_first_of_pair", BamRead, "is_first_of_pair", bool);
mixin methodN!("bam_read_set_is_second_of_pair", BamRead, "is_second_of_pair", bool);
mixin methodN!("bam_read_set_is_secondary_alignment", BamRead, "is_secondary_alignment", bool);
mixin methodN!("bam_read_set_failed_quality_control", BamRead, "failed_quality_control", bool);
mixin methodN!("bam_read_set_is_duplicate", BamRead, "is_duplicate", bool);
extern(C) export void bam_read_set_strand(BamRead* read, char dir) { read.strand = dir; }
extern(C) export void bam_read_set_mate_strand(BamRead* read, char dir) { 
    read.mate_is_reverse_strand = (dir == '-');
}
