#include <ruby.h>
#include <ruby/intern.h>

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
typedef int bool;

#include "sambamba.h"

static VALUE cBamReader;
static VALUE cBamReadEnumerator;
static VALUE cBamRead;

/* must be used only for return values where NULL means error */
static inline void CHECK_FOR_NULL(void* ptr) {
    if (ptr == NULL)
        rb_throw(last_error_message(), rb_eRuntimeError);
}

static inline VALUE FROM_DSTRING(dstring_s str) {
    return rb_str_new(str.buf, str.len);
}

/* ------------------------ bam read interface ------------------------------ */
typedef bam_read_s rb_bam_read;

static void rb_bam_read_deallocate(rb_bam_read* ptr)
{
    if (ptr->buf != NULL)
        xfree(ptr->buf);
    xfree(ptr);
}

static inline rb_bam_read * BAM_READ(VALUE self) {
    rb_bam_read * read;
    Data_Get_Struct(self, rb_bam_read, read);
    return read;
}

static VALUE rb_bam_read_to_sam(VALUE self) {
    dstring_s* sam = df_bam_read_to_sam(BAM_READ(self));
    volatile VALUE result = FROM_DSTRING(*sam);
    d_free(sam);
    return result;
}

static VALUE rb_bam_read_name(VALUE self) {
    return FROM_DSTRING(bam_read_name(BAM_READ(self)));
}

#define DEFINE_BAM_FLAG_GETTER(flagname)\
    static VALUE rb_bam_read_##flagname(VALUE self) {\
        return bam_read_##flagname(BAM_READ(self)) ? Qtrue : Qfalse;\
    }

#define DEFINE_BAM_FLAG_SETTER(flagname)\
    static VALUE rb_bam_read_set_##flagname(VALUE self, VALUE new_value) {\
        if (new_value == Qtrue)\
            bam_read_set_##flagname(BAM_READ(self), 1);\
        else if (new_value == Qfalse)\
            bam_read_set_##flagname(BAM_READ(self), 0);\
        else\
            rb_throw("Flag must be boolean", rb_eTypeError);\
        return Qnil;\
    }

DEFINE_BAM_FLAG_GETTER(is_paired)
DEFINE_BAM_FLAG_GETTER(proper_pair)
DEFINE_BAM_FLAG_GETTER(is_unmapped)
DEFINE_BAM_FLAG_GETTER(mate_is_unmapped)
DEFINE_BAM_FLAG_GETTER(is_reverse_strand)
DEFINE_BAM_FLAG_GETTER(mate_is_reverse_strand)
DEFINE_BAM_FLAG_GETTER(is_first_of_pair)
DEFINE_BAM_FLAG_GETTER(is_second_of_pair)
DEFINE_BAM_FLAG_GETTER(is_secondary_alignment)
DEFINE_BAM_FLAG_GETTER(failed_quality_control)
DEFINE_BAM_FLAG_GETTER(is_duplicate)

DEFINE_BAM_FLAG_SETTER(is_paired)
DEFINE_BAM_FLAG_SETTER(proper_pair)
DEFINE_BAM_FLAG_SETTER(is_unmapped)
DEFINE_BAM_FLAG_SETTER(mate_is_unmapped)
DEFINE_BAM_FLAG_SETTER(is_reverse_strand)
DEFINE_BAM_FLAG_SETTER(mate_is_reverse_strand)
DEFINE_BAM_FLAG_SETTER(is_first_of_pair)
DEFINE_BAM_FLAG_SETTER(is_second_of_pair)
DEFINE_BAM_FLAG_SETTER(is_secondary_alignment)
DEFINE_BAM_FLAG_SETTER(failed_quality_control)
DEFINE_BAM_FLAG_SETTER(is_duplicate)


/* ------------------------ bam read iterator ------------------------------- */
static VALUE rb_bam_read_enumerator_each(VALUE self) {
    bam_read_range_t read_range;
    size_t len;
    rb_bam_read * read;
    VALUE val;

    Data_Get_Struct(self, void, read_range);

    RETURN_ENUMERATOR(self, 0, NULL);

    while (1) {
        len = bam_readrange_front_alloc_size(read_range);
        if (len == 0)
            break;

        read = ALLOC(rb_bam_read);
        read->len = len;
        read->buf = ALLOC_N(uint8_t, len);
        read->reader = bam_readrange_front_copy_into_and_pop_front(read_range, 
                                                                   read->buf);

        val = Data_Wrap_Struct(cBamRead, NULL, &rb_bam_read_deallocate, read);

        rb_yield(val);
    }

    return Qnil;
}

/* ----------------------- bam reader interface ----------------------------- */
typedef bam_reader_t rb_bam_reader;

#include <stdio.h>
static void rb_bam_reader_deallocate(rb_bam_reader* ptr) {
    if (ptr != NULL)
        d_free(ptr);
}

static VALUE rb_bam_reader_allocate(VALUE klass) {
    rb_bam_reader reader = NULL;
    return Data_Wrap_Struct(cBamReader, NULL, rb_bam_reader_deallocate, reader);
}

static inline rb_bam_reader BAM_READER(VALUE self) {
    rb_bam_reader reader;
    Data_Get_Struct(self, void, reader);
    CHECK_FOR_NULL(reader);
    return reader;
}

static VALUE rb_bam_reader_filename(VALUE self) {
    return rb_str_new2(bam_reader_filename(BAM_READER(self)));
}

static VALUE rb_bam_reader_header(VALUE self) {
    sam_header_t header = bam_reader_header(BAM_READER(self));
    dstring_s* str = df_sam_header_text(header);
    VALUE result = FROM_DSTRING(*str);
    d_free(str);
    return result;
}

static VALUE rb_bam_reader_initialize(VALUE self, VALUE filename) {
    rb_bam_reader reader;
    Check_Type(self, T_DATA);
    Check_Type(filename, T_STRING);
    reader = bam_reader_new(StringValueCStr(filename));
    CHECK_FOR_NULL(reader);
    RDATA(self)->data = reader;
    return self;
}

static VALUE rb_bam_reader_reads(VALUE self) {
    rb_bam_reader reader = BAM_READER(self);
    bam_read_range_t reads = bam_reader_reads(reader);
    CHECK_FOR_NULL(reads);
    return Data_Wrap_Struct(cBamReadEnumerator, NULL, &d_free, reads);
}

static VALUE rb_bam_reader_fetch(VALUE self, VALUE refname, VALUE from, VALUE to) {
    rb_bam_reader reader = BAM_READER(self);
    bam_read_range_t reads;
    Check_Type(refname, T_STRING);
    Check_Type(from, T_FIXNUM);
    Check_Type(to, T_FIXNUM);
    reads = bam_reader_fetch(reader, RSTRING_PTR(refname), FIX2UINT(from), FIX2UINT(to));
    CHECK_FOR_NULL(reads);
    return Data_Wrap_Struct(cBamReadEnumerator, NULL, &d_free, reads);
}

void Init_sambamba() {
    attach();

    cBamReadEnumerator = rb_define_class("BamReadEnumerator", rb_cObject);
    rb_define_method(cBamReadEnumerator, "each", &rb_bam_read_enumerator_each, 0);
    rb_include_module(cBamReadEnumerator, rb_mEnumerable);

    cBamReader = rb_define_class("BamReader", rb_cObject);
    rb_define_alloc_func(cBamReader, &rb_bam_reader_allocate);
    rb_define_method(cBamReader, "initialize", &rb_bam_reader_initialize, 1);
    rb_define_method(cBamReader, "filename", &rb_bam_reader_filename, 0);
    rb_define_method(cBamReader, "header", &rb_bam_reader_header, 0);
    rb_define_method(cBamReader, "reads", &rb_bam_reader_reads, 0);
    rb_define_method(cBamReader, "fetch", &rb_bam_reader_fetch, 3);

    cBamRead = rb_define_class("BamRead", rb_cObject);
    rb_define_method(cBamRead, "to_sam", &rb_bam_read_to_sam, 0);
    rb_define_method(cBamRead, "to_s", &rb_bam_read_to_sam, 0);
    rb_define_method(cBamRead, "name", &rb_bam_read_name, 0);

    rb_define_method(cBamRead, "is_paired", &rb_bam_read_is_paired, 0);
    rb_define_method(cBamRead, "proper_pair", &rb_bam_read_proper_pair, 0);
    rb_define_method(cBamRead, "is_unmapped", &rb_bam_read_is_unmapped, 0);
    rb_define_method(cBamRead, "mate_is_unmapped", &rb_bam_read_mate_is_unmapped, 0);
    rb_define_method(cBamRead, "is_reverse_strand", &rb_bam_read_is_reverse_strand, 0);
    rb_define_method(cBamRead, "mate_is_reverse_strand", &rb_bam_read_mate_is_reverse_strand, 0);
    rb_define_method(cBamRead, "is_first_of_pair", &rb_bam_read_is_first_of_pair, 0);
    rb_define_method(cBamRead, "is_second_of_pair", &rb_bam_read_is_second_of_pair, 0);
    rb_define_method(cBamRead, "is_secondary_alignment", &rb_bam_read_is_secondary_alignment, 0);
    rb_define_method(cBamRead, "failed_quality_control", &rb_bam_read_failed_quality_control, 0);
    rb_define_method(cBamRead, "is_duplicate", &rb_bam_read_is_duplicate, 0);

    rb_define_method(cBamRead, "is_paired=", &rb_bam_read_set_is_paired, 1);
    rb_define_method(cBamRead, "proper_pair=", &rb_bam_read_set_proper_pair, 1);
    rb_define_method(cBamRead, "is_unmapped=", &rb_bam_read_set_is_unmapped, 1);
    rb_define_method(cBamRead, "mate_is_unmapped=", &rb_bam_read_set_mate_is_unmapped, 1);
    rb_define_method(cBamRead, "is_reverse_strand=", &rb_bam_read_set_is_reverse_strand, 1);
    rb_define_method(cBamRead, "mate_is_reverse_strand=", &rb_bam_read_set_mate_is_reverse_strand, 1);
    rb_define_method(cBamRead, "is_first_of_pair=", &rb_bam_read_set_is_first_of_pair, 1);
    rb_define_method(cBamRead, "is_second_of_pair=", &rb_bam_read_set_is_second_of_pair, 1);
    rb_define_method(cBamRead, "is_secondary_alignment=", &rb_bam_read_set_is_secondary_alignment, 1);
    rb_define_method(cBamRead, "failed_quality_control=", &rb_bam_read_set_failed_quality_control, 1);
    rb_define_method(cBamRead, "is_duplicate=", &rb_bam_read_set_is_duplicate, 1);

}
