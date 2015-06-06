" Vim filetype plugin file
" Language:	NesC
" Maintainer:	Lau Ming Leong <http://aming.no-ip.com>
" Last Change:	2007 Apr 02

" Only do this when not done yet for this buffer
if exists("b:did_ftplugin")
  finish
endif

" Behaves just like C
runtime! ftplugin/c.vim ftplugin/c_*.vim ftplugin/c/*.vim
