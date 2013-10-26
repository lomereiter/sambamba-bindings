#include <ruby.h>
#include <ruby/intern.h>

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
typedef int bool;

#include "sambamba.h"

static VALUE cBamReadIter;
static VALUE cBamRead;

static void rb_bam_read_deallocate(void* ptr)
{
    free(ptr);
}

typedef struct {
    size_t len;
    bam_reader_t reader;
    VALUE buf;
} rb_bam_read;

static bam_read_s convert_to_bam_read_s(rb_bam_read * read) {
    bam_read_s result;
    result.len = read->len;
    result.buf = (uint8_t*)(RSTRING_PTR(read->buf));
    result.reader = read->reader;
    return result;
}

static VALUE rb_bam_read_allocate(VALUE klass)
{
    rb_bam_read * read = malloc(sizeof(rb_bam_read));
    return Data_Wrap_Struct(klass, NULL, &rb_bam_read_deallocate, read);
}

static VALUE rb_reads(VALUE self, VALUE filename) {
    bam_reader_t reader;
    bam_read_range_t read_range;
    size_t len;
    volatile VALUE buf;
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

        read = malloc(sizeof(rb_bam_read));
        read->len = len;
        
        buf = rb_str_buf_new(len);
        read->reader = bam_readrange_front_copy_into_and_pop_front(read_range, 
                (uint8_t*)(RSTRING_PTR(buf)));

        read->buf = buf;
        val = Data_Wrap_Struct(cBamRead, NULL, &rb_bam_read_deallocate, read);

        rb_yield(val);
    }

    return Qnil;
}

static VALUE rb_bam_read_name(VALUE self) {
    bam_read_s r;
    dstring_s result;
    rb_bam_read * read;
    Data_Get_Struct(self, rb_bam_read, read);
    r = convert_to_bam_read_s(read);
    result = bam_read_name(&r);
    return rb_str_new(result.buf, result.len);
}

void Init_sambamba() {
    attach();

    cBamReadIter = rb_define_class("BamReadIter", rb_cObject);
    rb_define_method(cBamReadIter, "reads", &rb_reads, 1);

    cBamRead = rb_define_class("BamRead", rb_cObject);
    rb_define_alloc_func(cBamRead, &rb_bam_read_allocate);
    rb_define_method(cBamRead, "name", &rb_bam_read_name, 0);
}
