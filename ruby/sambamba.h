/* naming conventions:
 f_... means that free is to be called on the return value (if it's a pointer)
       or on `buf` field of the return value;
 df_... or ...new... means that d_free is to be called */

enum {
    SAMBAMBA_CFFI_VERSION_MAJOR = 0,
    SAMBAMBA_CFFI_VERSION_MINOR = 1
};

void attach(); /* must be called to initialize D runtime */
void detach();

/*
void* memcpy(void* dest, void* src, size_t n);
void free(void* ptr);
*/

void d_free(void*); /* frees the pointer and notifies D garbage collector */

char* last_error_message(void); /* zero-terminated error message string */

/* --------------------- Main types used throughout ------------------------- */

/* In D, the array layout is as follows */
typedef struct { char* buf; size_t len; } dstring_s;
typedef struct { int8_t* buf; size_t len; } aint8_s;
typedef struct { uint8_t* buf; size_t len; } auint8_s;
typedef struct { int16_t* buf; size_t len; } aint16_s;
typedef struct { uint16_t* buf; size_t len; } auint16_s;
typedef struct { int32_t* buf; size_t len; } aint32_s;
typedef struct { uint32_t* buf; size_t len; } auint32_s;
typedef struct { float* buf; size_t len; } afloat_s;

typedef void* bam_reader_t; /* BAM reader object */

typedef struct {
    size_t len;          /* length of raw data */
    const uint8_t* buf;  /* raw data */
    bam_reader_t reader; /* parent reader */
} bam_read_s;                   
typedef bam_read_s* bam_read_t; /* single read */

typedef void* sam_header_t; /* SAM header */

/* For now, the interface for SAM header is very limited:
   1) get header from a BAM file
   2) get its text representation
   3) create new header from text

   (anyway, text manipulation is not a big deal in most dynamic languages.)
 */
sam_header_t bam_reader_header(bam_reader_t);
dstring_s* df_sam_header_text(sam_header_t);
sam_header_t sam_header_new(char* header_text);

/* -------------------------- D ranges of reads ----------------------------- */

typedef void* bam_read_range_t; /* range (in D sense) of BAM reads */

typedef bam_read_t (*next_func_t)(void);
/* callback that returns next BAM read or NULL to stop iteration,
   can be passed to this function and made into a D range */
bam_read_range_t bam_read_range_adapter_new(next_func_t);

/* Iteration is meant to be done as follows: 
   1) get the size of raw data using bam_readrange_front_alloc_size 
   2) if the size is 0, the range is empty; stop iteration 
   3) otherwise, allocate chunk of memory in the target language
      and pass it to bam_readrange_front_copy_into_and_pop_front.
      It will fill the buffer, return bam_reader_t object, and
      move to the next read.
   4) create new bam_read_t object and fill its fields
      (length of raw data, pointer to raw data, and reader).
      All its memory is now managed by _target_ language, not D.
   
   This looks quite cumbersome, and it surely is, but:
   1) If the memory was managed by D, finalizers would be needed
      in order to free the memory, which is a huge performance hit.
   2) Only two FFI calls per read make for less overhead. */
size_t bam_readrange_front_alloc_size(bam_read_range_t);

bam_reader_t 
bam_readrange_front_copy_into_and_pop_front(bam_read_range_t, const uint8_t* buffer);
/* FIXME: currently, the latter function doesn't catch any exceptions.
         That is, if the file is somehow broken, it will just segfault. */

/* ------------------ Reference sequence information ------------------------ */
typedef struct {
    size_t name_len; /* length of reference sequence name */
    char* name_buf;  /* reference sequence name (zero-terminated) */
    int32_t length;  /* length of reference sequence */
} reference_info_s;  /* information about single reference sequence */

typedef struct {
    reference_info_s* buf;
    size_t len;
} areference_info_s; /* array containing reference sequence information */

typedef struct {
    uint8_t* buf;
    size_t len;
} buffer_s;

/* --------------------- BAM reader object -------- ------------------------- */

typedef void* task_pool_t; /* D task pool */
task_pool_t task_pool_new(uint32_t n_threads);

/* MUST be called to terminate the threads */
int32_t task_pool_finish(task_pool_t); 

/* constructors */
bam_reader_t bam_reader_new(const char* filename);
bam_reader_t bam_reader_new2(const char*, task_pool_t);

/* zero-terminated filename */
char* bam_reader_filename(bam_reader_t); 

/* create BAI index file (unless it already exists and !force) */
void bam_reader_create_index(bam_reader_t, bool force); 

/* all reads in the BAM file */
bam_read_range_t bam_reader_reads(bam_reader_t);

/* fetch reads overlapping a region */
bam_read_range_t 
bam_reader_fetch(bam_reader_t, char* refname, uint32_t from, uint32_t to);

/* reference sequences presented in the file */
areference_info_s bam_reader_references(bam_reader_t); 

/* --------------------------------- BAM read ------------------------------- */

/* get SAM representation of the read */
dstring_s* df_bam_read_to_sam(bam_read_t);

/* '+' or '-' */
char bam_read_strand(bam_read_t);
char bam_read_mate_strand(bam_read_t);

/* character must be checked in the target language */
void bam_read_set_strand(bam_read_t, char);
void bam_read_set_mate_strand(bam_read_t, char);

/* read sequence length (bp) */
size_t bam_read_sequence_length(bam_read_t); 

/* copy the sequence into a preallocated buffer 
  (get its size using the above function, and add one for the '\0') */
void bam_read_copy_sequence(const bam_read_t, char* buf); 

/* automatically resizes the qualities to the length of the sequence
   and sets them all to 0xFF (i.e. missing) */
buffer_s* df_bam_read_set_sequence(bam_read_t, const char* new_sequence);

aint8_s bam_read_base_qualities(const bam_read_t);
buffer_s* df_bam_read_set_base_qualities(bam_read_t, int8_t* buf, size_t len);

dstring_s bam_read_name(const bam_read_s*);
buffer_s* df_bam_read_set_name(bam_read_t, const char* new_name);

int8_t bam_read_mapping_quality(const bam_read_t); /* -1 if missing */
void bam_read_set_mapping_quality(bam_read_t, int8_t);

int32_t bam_read_ref_id(const bam_read_t);
void bam_read_set_ref_id(bam_read_t, int32_t);

char* bam_read_reference_name(const bam_read_t);   /* zero-terminated */

/* zero-based position on the reference */
int32_t bam_read_position(const bam_read_t);       
void bam_read_set_position(bam_read_t, int32_t);

int32_t bam_read_mate_ref_id(const bam_read_t);
void bam_read_set_mate_ref_id(bam_read_t, int32_t);

int32_t bam_read_mate_position(const bam_read_t);  /* zero-based */
void bam_read_set_mate_position(bam_read_t, int32_t);

uint16_t bam_read_flag(const bam_read_t);
void bam_read_set_flag(bam_read_t, uint16_t);

int32_t bam_read_template_length(const bam_read_t);
void bam_read_set_template_length(bam_read_t, int32_t);

typedef struct { uint32_t* buf; size_t len; } cigar_s;
uint32_t bam_cigar_operation_length(uint32_t);
char bam_cigar_operation_type(uint32_t);           /* MIDNSHP=X */
bool bam_cigar_operation_consumes_ref(uint32_t);   /* types M=XDN */
bool bam_cigar_operation_consumes_query(uint32_t); /* types M=XIS */
bool bam_cigar_operation_consumes_both(uint32_t);  /* types M=X */
cigar_s bam_read_cigar(const bam_read_t);
cigar_s f_bam_read_extended_cigar(const bam_read_t);

buffer_s* df_bam_read_set_cigar(bam_read_t, uint32_t* buf, size_t len);

/* read flags */
bool bam_read_is_paired(const bam_read_t);
bool bam_read_proper_pair(const bam_read_t);
bool bam_read_is_unmapped(const bam_read_t);
bool bam_read_mate_is_unmapped(const bam_read_t);
bool bam_read_is_reverse_strand(const bam_read_t);
bool bam_read_mate_is_reverse_strand(const bam_read_t);
bool bam_read_is_first_of_pair(const bam_read_t);
bool bam_read_is_second_of_pair(const bam_read_t);
bool bam_read_is_secondary_alignment(const bam_read_t);
bool bam_read_failed_quality_control(const bam_read_t);
bool bam_read_is_duplicate(const bam_read_t);

void bam_read_set_is_paired(bam_read_t, bool);
void bam_read_set_proper_pair(bam_read_t, bool);
void bam_read_set_is_unmapped(bam_read_t, bool);
void bam_read_set_mate_is_unmapped(bam_read_t, bool);
void bam_read_set_is_reverse_strand(bam_read_t, bool);
void bam_read_set_mate_is_reverse_strand(bam_read_t, bool);
void bam_read_set_is_first_of_pair(bam_read_t, bool);
void bam_read_set_is_second_of_pair(bam_read_t, bool);
void bam_read_set_is_secondary_alignment(bam_read_t, bool);
void bam_read_set_failed_quality_control(bam_read_t, bool);
void bam_read_set_is_duplicate(bam_read_t, bool);

                        /* -------- Accessing read tags -------- */

enum tag_type_id {
    TYPE_UINT8 = 32,
    TYPE_UINT16 = 64,
    TYPE_UINT32 = 128,
    TYPE_INT8 = 48,
    TYPE_INT16 = 80,
    TYPE_INT32 = 144,
    TYPE_FLOAT = 136,
    TYPE_CHAR = 36,
    TYPE_UINT8_ARRAY = 33,
    TYPE_UINT16_ARRAY = 65,
    TYPE_UINT32_ARRAY = 129,
    TYPE_INT8_ARRAY = 49,
    TYPE_INT16_ARRAY = 81,
    TYPE_INT32_ARRAY = 145,
    TYPE_FLOAT_ARRAY = 137,
    TYPE_STRING = 37,
    TYPE_HEX_STRING = 45,       /* should be treated same as string */
    TYPE_NULL = 2               /* indicates absence of tag in a read */
};

/* In order to get the tag value, first get the type of the tag.
   Then call the corresponding function.
   (tag_name length must be 2 - check that in the target language) */
uint8_t bam_read_tag_type_id(const bam_read_t, const char* tag_name);

char bam_read_char_tag(const bam_read_t, const char*);
int8_t bam_read_int8_tag(const bam_read_t, const char*);
uint8_t bam_read_uint8_tag(const bam_read_t, const char*);
int16_t bam_read_int16_tag(const bam_read_t, const char*);
uint16_t bam_read_uint16_tag(const bam_read_t, const char*);
int32_t bam_read_int32_tag(const bam_read_t, const char*);
uint32_t bam_read_uint32_tag(const bam_read_t, const char*);
float bam_read_float_tag(const bam_read_t, const char*);
aint8_s bam_read_int8_array_tag(const bam_read_t, const char*);
auint8_s bam_read_uint8_array_tag(const bam_read_t, const char*);
aint16_s bam_read_int16_array_tag(const bam_read_t, const char*);
auint16_s bam_read_uint16_array_tag(const bam_read_t, const char*);
aint32_s bam_read_int32_array_tag(const bam_read_t, const char*);
auint32_s bam_read_uint32_array_tag(const bam_read_t, const char*);
afloat_s bam_read_float_array_tag(const bam_read_t, const char*);
dstring_s bam_read_string_tag(const bam_read_t, const char*);

/* The following functions return a structure with updated 'buf' and 'len'.
   If the pointer is different from the initial 'buf' field of the read,
   the data from the buffer must be copied into newly allocated memory. 
   Otherwise only the length must be updated. */
buffer_s* df_bam_read_set_char_tag(bam_read_t, const char*, char);
buffer_s* df_bam_read_set_int8_tag(bam_read_t, const char*, int8_t);
buffer_s* df_bam_read_set_uint8_tag(bam_read_t, const char*, uint8_t);
buffer_s* df_bam_read_set_int16_tag(bam_read_t, const char*, int16_t);
buffer_s* df_bam_read_set_uint16_tag(bam_read_t, const char*, uint16_t);
buffer_s* df_bam_read_set_int32_tag(bam_read_t, const char*, int32_t);
buffer_s* df_bam_read_set_uint32_tag(bam_read_t, const char*, uint32_t);
buffer_s* df_bam_read_set_float_tag(bam_read_t, const char*, float);
buffer_s* df_bam_read_set_string_tag(bam_read_t, const char*, const char* strz);

/* ----------------------------- Read in a pileup --------------------------- */

/* notice that pileup_read_t can be passed as an argument
   to all functions that expect bam_read_t */
typedef struct {
    bam_read_s read;
    int32_t additional_info[5];
} pileup_read_s;
typedef pileup_read_s* pileup_read_t;

typedef struct { pileup_read_s* buf; size_t len; } apileup_read_s;

/* CIGAR operations after the current one */
cigar_s bam_pileup_read_cigar_before(pileup_read_t);

/* CIGAR operations before the current one */
cigar_s bam_pileup_read_cigar_after(pileup_read_t);

/* current CIGAR operation */
uint32_t bam_pileup_read_cigar_operation(pileup_read_t);

/* how many bases were consumed from the current CIGAR operation */
uint32_t bam_pileup_read_cigar_operation_offset(pileup_read_t);

/* how many bases were consumed from the query sequence */
int32_t bam_pileup_read_query_offset(pileup_read_t);

/* current base */
char bam_pileup_read_current_base(pileup_read_t);

/* current base quality (-1 if deletion) */
int8_t bam_pileup_read_current_base_quality(pileup_read_t);

/* -------------------------- Pileup engine --------------------------------- */

typedef void* pileup_t;         /* pileup engine */
typedef void* pileup_column_t;  /* single pileup column */

/* Create a pileup engine.
   The reads must be coordinate-sorted (can be from different references),
   unmapped ones will be skipped automatically.
   If use_md is true, MD tag will be used to get reference bases.
   If skip_zeros is true, columns with zero coverage will be skipped. */
pileup_t bam_pileup_new(bam_read_range_t, bool use_md, bool skip_zeros);

/* Proceed to the next pileup column.
   The interface is a bit weird: you should tell the function
   whether you call it the first time on the pileup or not
   (otherwise, the first column will be skipped).
   This allows to move to the next column in a single FFI call.
   The returned value of NULL means that all columns are processed. */
pileup_column_t bam_pileup_next(pileup_t, bool it_wasnt_first_call);

/* --------------------------- Pileup column -------------------------------- */

/* reference ID */
int32_t bam_pileup_column_ref_id(pileup_column_t);

/* current reference base (always 'N' if use_md wasn't specified) */
char bam_pileup_column_ref_base(pileup_column_t);

/* array of reads overlapping current column */
apileup_read_s bam_pileup_column_reads(pileup_column_t);

/* coverage at the site */
size_t bam_pileup_column_coverage(pileup_column_t);

/* zero-based position on the reference */
uint64_t bam_pileup_column_position(pileup_column_t);

/* bases ('-' stay for deletions), length is equal to coverage */
char* f_bam_pileup_column_bases(pileup_column_t);

/* base qualities (-1 on deletions) */
aint8_s f_bam_pileup_column_base_quals(pileup_column_t);

/* ---------------------------- BAM writer ---------------------------------- */
typedef void* bam_writer_t;

/* default compression level is -1, the number can be in range -1 .. 9;
   BAM magic is automatically written during the construction;
   NULL return value indicates that an exception has occurred. */
bam_writer_t bam_writer_new(char* filename, int32_t compression_level);
bam_writer_t bam_writer_new2(char* filename, int32_t, task_pool_t);

/* the following functions return 0 if everything is OK, otherwise -1. */

/* next step after construction is to write SAM header */
int32_t bam_writer_push_header(bam_writer_t, sam_header_t);

/* then reference sequence information follows */
int32_t bam_writer_push_ref_info(bam_writer_t, reference_info_s* refs, size_t nrefs);

/* and then reads */
int32_t bam_writer_push_read(bam_writer_t, bam_read_t);

/* don't forget to close the stream! This also adds BGZF EOF block. */
int32_t bam_writer_close(bam_writer_t);

/* flushes current BGZF block; may be useful in some cases */
int32_t bam_writer_flush(bam_writer_t);
