#include <ruby.h>
#include <ruby/intern.h>

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
typedef int bool;

#include "sambamba.h"

static VALUE cBamReadIter;
static VALUE cBamRead;

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

static VALUE rb_bam_read_name(VALUE self) {
    dstring_s result = bam_read_name(BAM_READ(self));
    return rb_str_new(result.buf, result.len);
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
static VALUE rb_reads(VALUE self, VALUE filename) {
    bam_reader_t reader;
    bam_read_range_t read_range;
    size_t len;
    rb_bam_read * read;
    VALUE val;

    Check_Type(filename, T_STRING);
    reader = bam_reader_new(StringValueCStr(filename));
    if (reader == NULL)
        rb_throw(last_error_message(), rb_eRuntimeError);
    read_range = bam_reader_reads(reader);

    RETURN_ENUMERATOR(self, 1, NULL);

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

void Init_sambamba() {
    attach();

    cBamReadIter = rb_define_class("BamReadIter", rb_cObject);
    rb_define_method(cBamReadIter, "reads", &rb_reads, 1);

    cBamRead = rb_define_class("BamRead", rb_cObject);
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
