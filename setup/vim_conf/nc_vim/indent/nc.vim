" Vim indent file
" Language:	NesC
" Maintainer:	Lau Ming Leong <http://aming.no-ip.com
" Last Change:	2007 Apr 02

" Only load this indent file when no other was loaded.
if exists("b:did_indent")
   finish
endif
let b:did_indent = 1

" C++ indenting is built-in, thus this is very simple
setlocal cindent
