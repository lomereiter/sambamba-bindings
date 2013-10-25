require 'ffi'

module SambambaWrapper
  extend FFI::Library
  ffi_lib './libsambamba.so'
end

require_relative 'bio/bamreader.rb'
