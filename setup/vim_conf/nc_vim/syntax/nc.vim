" Vim syntax file
" Language:	NesC
" Maintainer:	Lau Ming Leong <http://aming.no-ip.com>
" Version:	1.0
" Last Change:	2007 Apr 01
" Description:	Modified from syntax/cpp.vim by Ken Shan <ccshan@post.harvard.edu>

" For version 5.x: Clear all syntax items
" For version 6.x: Quit when a syntax file was already loaded
if version < 600
	syntax clear
elseif exists("b:current_syntax")
	finish
endif

" Read the C syntax to start with
if version < 600
	so <sfile>:p:h/c.vim
else
	runtime! syntax/c.vim
	unlet b:current_syntax
endif

" C++ extentions
syn keyword cppStatement	new delete this friend using
syn keyword cppAccess		public protected private
syn keyword cppType		inline virtual explicit export bool wchar_t
syn keyword cppExceptions	throw try catch
syn keyword cppOperator		operator typeid
syn keyword cppOperator		and bitor or xor compl bitand and_eq or_eq xor_eq not not_eq
syn match cppCast		"\<\(const\|static\|dynamic\|reinterpret\)_cast\s*<"me=e-1
syn match cppCast		"\<\(const\|static\|dynamic\|reinterpret\)_cast\s*$"
syn keyword cppStorageClass	mutable
syn keyword cppStructure	class typename template namespace
syn keyword cppNumber		NPOS
syn keyword cppBoolean		true false

"Nesc extensions
syn keyword ncFunction		command event task interface
syn keyword ncCall		call post fire as
syn keyword ncPreProc		includes
syn keyword ncInterface		module implementation configuration
syn keyword ncWiring		provides uses components
syn keyword ncConstant		SUCCESS FAIL
syn keyword ncBoolean		TRUE FALSE

" The minimum and maximum operators in GNU C++
syn match cppMinMax "[<>]?"

" Default highlighting
    
if version >= 508 || !exists("did_cpp_syntax_inits")
	if version < 508
		let did_cpp_syntax_inits = 1
		command -nargs=+ HiLink hi link <args>
	else
	command -nargs=+ HiLink hi def link <args>
	endif
	HiLink cppaccess	cppstatement
	HiLink cppcast		cppstatement
	HiLink cppexceptions	exception
	HiLink cppoperator	operator
	HiLink cppstatement	statement
	HiLink cpptype		type
	HiLink cppstorageclass	storageclass 
	HiLink cppstructure	structure
	HiLink cppnumber	number
	HiLink ncboolean	boolean
	HiLink ncfunction	type
	HiLink nccall		statement
	HiLink ncpreproc	structure
	HiLink ncinterface	cppstructure
	HiLink ncwiring		cppstatement
	HiLink ncconstant	constant
	delcommand HiLink
endif

let b:current_syntax = "nc"

" vim: ts=8
