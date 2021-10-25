#!/usr/bin/python3 -I


# inspect  C programs in introductory programing courses
# for features that either,
#
# * a student should not be using generally (e.g. goto), or
# * are not permitted for a specific exercises  (perhaps array)
#
# Also:
#
# * detect incorrect indenting
# * warn if integer constants are used for ASCII codes , e.g `10` instead of `'\n'`
# * warn if functions like getchar are assigned to an int
#
# Author: Andrew Taylor (andrewt@unsw.edu.au)
#
# Repo: https://github.com/COMP1511UNSW/c_check

import argparse, collections, glob, os, re, sys
import clang.cindex
from clang.cindex import CursorKind as CKind, TypeKind as TKind

# clang cindex source: https://github.com/llvm-mirror/clang/blob/master/bindings/python/clang/cindex.py
# API description: https://www.pydoc.io/pypi/prophy-1.0.1/autoapi/parsers/clang/cindex/index.html#parsers.clang.cindex.Cursor
# example code at: https://github.com/coala/coala-bears/blob/master/bears/c_languages/codeclone_detection/ClangCountingConditions.py

EXAMPLE_TEXT = r"""
c_check.py --not-permitted=global_variable,goto,static_local_variable \
			--not-recommended=ternary \
			--where-text="in COMP1511" \
			--extra-text="see the COMP1511 style guide at https://example.com"  \
			--warning=assign_getchar_char,integer_ascii_code,indenting \
			file.c
"""

SYNTAX_TREE_NODE_CHECKS = {
	"array"                 : "check if array used (for exercises where ararys are not permitted)",
	"break"                  : "check if break used",
	"comma"                  : "check if comma operator used",
	"continue"               : "check if continue used",
	"do_while"               : "check if do while used",
	"global_variable"       : "check global variables used",
	"goto"                   : "check if goto used",
	"multiple_malloc"        : "check if malloc is called in more than 1 location  (for exercises where this is not permitted)",
	"non_char_array"        : "check for use of array other than char array  (for exercises where this is not permitted)",
	"static_local_variable" : "check for use of static local variables",
	"string_library"         : "check for use of functions from string.h (for exercises where this is not permitted)",
	"switch"                 : "check if switch used",
	"ternary"              : "check for use of the ?: operator",
	"union"                  : "check if union used",
	"unistd_library"         : "check for use of functions from unistd.h",
}


FUNCTION_CHECKS = {
	"assign_getchar_char"    : "check for common bug of getchar/fgetc/getc being assigned to char variable, e.g char c = getchar();",
	"indenting"              : "check indenting consistent with functions, and tabs/spaces not mixed within function",
	"integer_ascii_code"     : "check integer constants not used for ASCII codes e.g. 10 instead of '\n'",
}


CHECKS = {**SYNTAX_TREE_NODE_CHECKS, **FUNCTION_CHECKS}

EXTRA_HELP_TEXT = f"""

For example:

{EXAMPLE_TEXT}

Available checkers are:

""" + '\n'.join(f"{k:24} - {v}" for (k,v) in sorted(CHECKS.items()))

def main():
	args = args_parser()

	global colored
	if args.colorize:
		try:
			from termcolor import colored as colored
		except ImportError:
			colored = lambda x, *args, **kwargs: x
			print('hello')
			args.colorize = False

		# colorama if available should improve WIN32 output
		try:
			from colorama import init
			init()
		except ImportError:
			pass

	else:
		colored = lambda x, *args, **kwargs: x

	# if NDEBUG is not specified use of assert will trigger ternary warnings
	index_parse_args = get_library_include() + ['-I' + i for i in args.include_directories] + ['-DNDEBUG']

	index = clang.cindex.Index.create()
	error_occurred = False
	for filename in args.source_files:
		if filename.endswith('.c'):
			if not check_file(index, filename, args, index_parse_args):
				error_occurred = True
	sys.exit(1 if error_occurred else 0)



def args_parser():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EXTRA_HELP_TEXT)

	parser.add_argument("--error", help="error if any of comma separated list of checks fails, exit with status 1")
	parser.add_argument("--not-permitted", help="error plus not permitted message if any of comma separated list of checks fails, exit with status 1")
	parser.add_argument("--warning", help="warn if any of comma separated list of checks fails")
	parser.add_argument("--not-recommended", help="warning plus not recommended message if any of comma separated list of checks fails")
	parser.add_argument("--do-not-check", help="do not run any of this comma separated list of checks")

	parser.add_argument("--where-text", dest="where_text", help="text added to error messages indicating where features are not permitted/recommended")
	parser.add_argument("--extra-text", dest="extra_text",  help="text added to message if not permitted/recommended code found")

	parser.add_argument("--highlight-incorrect-indenting", action="store_true", dest="highlight_incorrect_indenting", default=True,   help="highlight incorrect indenting")
	parser.add_argument("--no-highlight-incorrect-indenting", action="store_false", dest="highlight_incorrect_indenting", help="do not highlight incorrect indenting")
	parser.add_argument("--mixed-indenting-text",dest="mixed_indenting_text",  help="text added to error messages if mixture of tabs and spaces found")

	parser.add_argument("--colorize", action="store_true", default=os.environ.get('C_CHECK_COLORIZE_OUTPUT', sys.stdout.isatty()), help="colorize output")
	parser.add_argument("--no-colorize", action="store_false", dest='colorize', help="do not colorize output")


	parser.add_argument("-I",  dest="include_directories", action="append", default=[], help="add directory for include directories")

	parser.add_argument("-d", "--debug", action="count", default=0 ,  help="show debug ouput")
	parser.add_argument("source_files",  nargs='*', default=[], help="")

	args = parser.parse_args()

	for check in CHECKS:
		setattr(args, check, None)

	for which in "not_recommended warning error not_permitted do_not_check".split():
		g = getattr(args, which)
		if not g:
			continue
		value = which
		if which == "do_not_check":
			value = None
		for raw_check in g.split(','):
			check =  raw_check.strip().replace('-', '_')
			if check not in CHECKS:
				print(f"Invalid checker: '{check}'\n", file=sys.stderr)
				print(f"Valid checks are: {' '.join(CHECKS)}\n", file=sys.stderr)
				sys.exit(1)
			setattr(args, check, value)

	return args


def get_library_include():
	import shutil, subprocess
	clang_bin = shutil.which('clang')
	if not clang_bin:
		print("c_check: no 'clang' binary found!", file=sys.stderr)
		return []

	clang_resource_dir = subprocess.check_output([clang_bin, '-print-resource-dir'], universal_newlines=True).splitlines()[0]
	include_directory = os.path.join(clang_resource_dir, 'include')

	# it'd sure be nice if clang knew where libclang was...
	libclang_path = os.path.dirname(os.path.dirname(clang_resource_dir))
	libclangs = glob.glob(f'{libclang_path}/libclang.so.*')
	if not libclangs:
		print("c_check: can't find 'libclang.so'!", file=sys.stderr)
		return []

	libclang = libclangs[0]
	clang.cindex.Config.set_library_file(libclang)

	return ['-isystem', include_directory]


def check_file(index, C_source_filename, args, index_parse_args):
	"""
	@returns False if any check fails, True otherwise
	"""
	try:
		with open(C_source_filename, encoding='utf-8', errors='replace') as f:
			C_source = f.read()
	except OSError as e:
		print(e, file=sys.stderr)
		return False
	try:
		# using the unsaved_files parameter to avoid rereading the file produces
		# a syntax error with activities/crack_substitution/solutions/crack_substitution.c
		tu = index.parse(C_source_filename, args=index_parse_args)
		for diagnostic in tu.diagnostics:
			if diagnostic.severity in [clang.cindex.Diagnostic.Error, clang.cindex.Diagnostic.Fatal]:
				print(diagnostic.format())
				return 1
			elif args.debug:
				print(diagnostic.format())
		abstract_syntax_tree = tu.cursor
	except clang.cindex.TranslationUnitLoadError:
		return False

	if args.debug:
		print_ast(abstract_syntax_tree)

	C_source_lines = C_source.splitlines()

	checkers = [check_syntax_tree, check_file_expressions, check_tabs_spaces_mixed, check_body_indents]

	for checker in checkers:
		diagnostics_printed = checker(abstract_syntax_tree, args, C_source_lines, C_source_filename)
		if ('not_permitted' in diagnostics_printed) or ('error' in diagnostics_printed):
			return False

	return True


def check_syntax_tree(abstract_syntax_tree, args, C_source_lines, C_source_filename):
	"""
	@returns list of levels of diagnostic messages printed
	"""
	state = {}
	levels = []
	for n in abstract_syntax_tree_nodes(abstract_syntax_tree):
		for check in SYNTAX_TREE_NODE_CHECKS:
			level = getattr(args, check)
			if not level:
				continue
			function = globals()['check_' + check]
			description = function(n, args, state)
			if description:
				print_diagnostic(n, description, args, level=level, source_lines=C_source_lines)
				levels.append(level)

	if args.extra_text and (('not_permitted' in levels) or ('not_recommended' in levels)):
		print(args.extra_text)

	return levels


def print_diagnostic(n, message, args, level='warning', source_lines=[]):
	prefix = level
	if level in ["not_permitted", "not_recommended"]:
		prefix = "error" if level == "not_permitted" else "warning"
		message += f" - this is {colored(level.replace('_', ' '), 'red')}"
		if args.where_text:
			message += " " + args.where_text
	print(f"{node_location(n)} {colored(prefix, 'red')}: {message}")

	line_number = n.extent.start.line
	if line_number != n.extent.end.line:
		# should we display multi-line constructs
		return

	if not line_number or line_number > len(source_lines):
		return

	line = source_lines[line_number - 1]
	start = n.extent.start.column
	end = n.extent.end.column

	if not start or not end:
		return
	if start > len(line) or end > len(line) or start >= end:
		return

	print(line)
	underline = '^' + '~' * (end - start - 1)
	print(' ' * (start - 1) + colored(underline, 'green'))


def check_break(n, args, state):     return check_kind(n, "break statement",    CKind.BREAK_STMT)
def check_continue(n, args, state):  return check_kind(n, "continue statement", CKind.CONTINUE_STMT)
def check_do_while(n, args, state):  return check_kind(n, "do while statement", CKind.DO_STMT,)
def check_goto(n, args, state):      return check_kind(n, "goto statement",     CKind.GOTO_STMT)
def check_switch(n, args, state):    return check_kind(n, "switch statement",   CKind.SWITCH_STMT)
def check_ternary(n, args, state):   return check_kind(n, "ternary 'if' ?:",    CKind.CONDITIONAL_OPERATOR)
def check_union(n, args, state):     return check_kind(n, "union",              CKind.UNION_DECL)


def check_kind(n, name, value):
	if n.kind == value:
		return name + " used"


def check_array(n, args, state):
	if n.kind == CKind.VAR_DECL and '[' in n.type.spelling:
		return "array used"


def check_comma(n, args, state):
	if n.kind == CKind.BINARY_OPERATOR and get_operator(n) == ',':
		return "comma operator used"


def check_global_variable(n, args, state):
	if (n.kind == CKind.VAR_DECL and
			n.parent.kind == CKind.TRANSLATION_UNIT and
			'debug' not in n.displayname):
		pointer_type = n.type.get_canonical()
		while pointer_type.kind == TKind.POINTER:
			if not pointer_type.is_const_qualified():
				return f"variable '{colored(n.displayname, 'cyan')}' is a global variable"
			pointer_type = pointer_type.get_pointee()
		if not pointer_type.is_const_qualified():
			return f"variable '{colored(n.displayname, 'cyan')}' is a global variable"


def check_multiple_malloc(n, args, state):
	if n.kind == CKind.CALL_EXPR and n.spelling in ['malloc', 'calloc', 'realloc']:
		n_calls = state.get('malloc_calls_count', 0) + 1
		state['malloc_calls_count'] = n_calls
		if n_calls > 1:
			return "malloc called"


def check_non_char_array(n, args, state):
	if n.kind == CKind.VAR_DECL and '[' in n.type.spelling and 'char' not in n.type.spelling:
		return "non-char array used"


def check_static_local_variable(n, args, state):
	if (n.kind == CKind.VAR_DECL and
			n.storage_class == clang.cindex.StorageClass.STATIC and
			n.parent.kind != CKind.TRANSLATION_UNIT and
			'debug' not in n.displayname):
		pointer_type = n.type.get_canonical()
		while pointer_type.kind == TKind.POINTER:
			if not pointer_type.is_const_qualified():
				return f"variable '{colored(n.displayname, 'cyan')}' is a static variable"
			pointer_type = pointer_type.get_pointee()
		if not pointer_type.is_const_qualified():
			return f"variable '{colored(n.displayname, 'cyan')}' is a static variable"


def check_string_library(n, args, state):
	if (n.kind == CKind.DECL_REF_EXPR and
		n.referenced and
		n.referenced.location and
		n.referenced.location.file and
		n.referenced.location.file.name == "/usr/include/string.h"):
		return "string.h used"


def check_unistd_library(n, args, state):
	if (n.kind == CKind.DECL_REF_EXPR and
		n.referenced and
		n.referenced.location and
		n.referenced.location.file and
		n.referenced.location.file.name == "/usr/include/unistd.h"):
		return "unistd.h used"


def check_file_expressions(abstract_syntax_tree, args, source_lines, C_source_filename):
	levels = []
	for function in get_functions(abstract_syntax_tree):
		variables_used_for_ASCII = set()
		for n in abstract_syntax_tree_nodes(function):
			levels += check_for_char_input_function_assigned_to_char_variable(args, n, source_lines)
			levels += check_for_integer_ascii_codes(n, args, variables_used_for_ASCII, source_lines)
	return levels


def check_for_char_input_function_assigned_to_char_variable(args, n, source_lines):
	level = args.assign_getchar_char
	if not level:
		return []
	variable = None
	function = None
	if n.kind == CKind.BINARY_OPERATOR:
		left, right = n.get_children()
		variable = is_variable(left)
		function = is_char_input_function(right)
	elif n.kind == CKind.VAR_DECL:
		variable = n
		children = list(n.get_children())
		if children:
			function = is_char_input_function(children[0])
	if variable and function and variable.type.spelling == 'char':
		message = f" return value of {function.spelling} assigned to {colored('char', 'red')} variable '{variable.spelling}', change the type of '{variable.spelling}' to {colored('int', 'red')}"
		print_diagnostic(n, message, args, level=level, source_lines=source_lines)
		return [level]
	return []


def check_for_integer_ascii_codes(n, args, variables_used_for_ASCII, source_lines):
	level = args.integer_ascii_code
	if not level:
		return []
	"""
	issue warnings for ASCII codes represented as integer constants,
	e.g.: code like this

		int c = getchar();
		if (c == 10) {

	by tracking variables which are used to hold char values
	"""

	if n.kind == CKind.VAR_DECL:
		try:
			initializer = next(n.get_children())
			if is_char_expr(initializer, variables_used_for_ASCII):
				variables_used_for_ASCII.add(n.hash)
		except StopIteration:
			pass
		return []

	if n.kind != CKind.BINARY_OPERATOR:
		return []

	operator = get_operator(n)

	if operator == '=':
		(left, right) = n.get_children()
		variable = is_variable(left)
		if variable:
			if is_char_expr(right, variables_used_for_ASCII):
				# note variable has been assigned result of getchar etc.
				variables_used_for_ASCII.add(variable.hash)
			else:
				# variable previously assigned result of getchar is being reused for different purpose
				# so delete from variables being tracked
				variables_used_for_ASCII.discard(variable.hash)
		return []

	if operator not in ['==', '!=', '<=', '>=', '<', '>']:
		return []

	integer_literal = test_children(n, lambda x: x.kind == CKind.INTEGER_LITERAL)
	if not integer_literal:
		return []
	char_expr = test_children(n, lambda x: is_char_expr(x, variables_used_for_ASCII))
	if not char_expr:
		return []

	#  variable previously assigned result of getchar etc. is  compared to integer literal
	try:
		ascii_code = int(next(integer_literal.get_tokens()).spelling)
		if 6 < ascii_code < 13 or 31 < ascii_code < 126:
			correct = repr(chr(ascii_code))
			message = f"ASCII code {colored(str(ascii_code), 'red')} used, replace with {colored(correct, 'red')}"
			print_diagnostic(integer_literal, message, args, level='warning', source_lines=source_lines)
			return [level]
	except ValueError:
		pass
	return []


def test_children(n, condition):
	for child in n.get_children():
		value = condition(child)
		if value:
			return child if value is True else value


def is_variable(n):
	while n.kind == CKind.UNEXPOSED_EXPR:
		n = next(n.get_children())
	if n and n.kind == CKind.DECL_REF_EXPR:
		return n.referenced


def is_char_expr(n, variables_used_for_ASCII):
	while n.kind == CKind.UNEXPOSED_EXPR:
		n = next(n.get_children())
	if n and n.type and n.type.spelling == 'char':
		return n
	# these return int, but are char for these purposes
	if is_char_input_function(n):
		return n
	# int variable previously assigned char
	if n and n.kind == CKind.DECL_REF_EXPR and n.referenced.hash in variables_used_for_ASCII:
		return n


def is_char_input_function(n):
	while n and n.kind == CKind.UNEXPOSED_EXPR:
		n = next(n.get_children())
	if n and n.kind == CKind.CALL_EXPR and n.spelling in ['getchar', 'getc', 'fgetc']:
		return n


def get_operator(n):
	"""
	for some reason n.spelling doesn't contain the operator
	for a binary operator - so use n.extent to find the appropriate token
	we could instead use n.extent to drag the chars from the file
	"""
	(left,right) = n.get_children()
	left_end = (left.extent.end.line, left.extent.end.column)
	right_start = (right.extent.start.line, right.extent.start.column)
	for t in n.get_tokens():
		if (
			left_end <= (t.extent.start.line, t.extent.start.column) and
			right_start >= (t.extent.end.line, t.extent.end.column)
			):
			return t.spelling


def check_tabs_spaces_mixed(abstract_syntax_tree, args, C_source_lines, C_source_filename):
	"""
	check tabs & spaces not mixed in formatting
	"""
	level = args.indenting
	if not level:
		return []
	line_indent_type = collections.defaultdict(lambda:set())
	for (line_number, line) in enumerate(C_source_lines):
		indent_type = categorize_line(line)
		if indent_type:
			line_indent_type[indent_type].add(line_number)

	if line_indent_type['mixed']:
		lines_description = describe_line_set(line_indent_type['mixed'])
		print(f"{C_source_filename}: {colored('warning', 'red')}: {lines_description} indented with a mixture of tabs and spaces")
		if args.mixed_indenting_text:
			print(args.mixed_indenting_text)
		return [level]

	# only warn if tabs and spaced used in same function
	# to avoid warning when student has been supplied code indented with spaces
	# and uses tabs for their own code or vice versa

	for function in get_functions(abstract_syntax_tree):
		function_lines = set(range(function.extent.start.line, function.extent.end.line + 1))
		tabbed_lines = function_lines & line_indent_type['tabs']
		spaced_lines = function_lines & line_indent_type['spaces']
		if not tabbed_lines or not spaced_lines:
			continue
		tabbed_description = describe_line_set(tabbed_lines)
		spaced_description = describe_line_set(spaced_lines)
		print(f"""{C_source_filename}: {colored('warning', 'red')}: function {colored(function.spelling, 'cyan')} is indented with a mixture of tabs and spaces:
	{tabbed_description} indented with tabs
	{spaced_description} indented with spaces""")
		if args.mixed_indenting_text:
			print(args.mixed_indenting_text)
		return [level]

	return []


# we could condense ranges here
def describe_line_set(lines):
	max_lines_shown = 5
	line_numbers = sorted(lines)
	description = ",".join(map(str, line_numbers[0:max_lines_shown]))
	if len(line_numbers) == 1:
		return f"line {description} is"
	elif len(line_numbers) > max_lines_shown:
		return f"lines {description}, ... are"
	else:
		return f"lines {description} are"


def categorize_line(line):
	if re.match(r'^ +\S', line):
		return "spaces"
	if re.match(r'^\t+\S', line):
		return "tabs"
	if re.match(r'^[ \t]+\S', line):
		return "mixed"


def check_body_indents(abstract_syntax_tree, args, C_source_lines, C_source_filename):
	"""
	check bodies of of if/while/for/functions consistently indented
	This is done per function, to avoid warnings when student has been supplied code
	indented with a different indent to which they use
	"""
	level = args.indenting
	if not level:
		return []
	line_indent = {}
	show_lines = set()
	for function in get_functions(abstract_syntax_tree):
		show_lines |= check_function_indent(C_source_filename, function, args, line_indent)
	incorrectly_indented_lines = len(show_lines)

	if incorrectly_indented_lines and args.highlight_incorrect_indenting:
		show_lines = expand_lines_shown(C_source_lines, show_lines)
		print_indents(C_source_filename, C_source_lines, args, line_indent, show_lines)

	return [level] if incorrectly_indented_lines else []


def check_function_indent(C_source_filename, abstract_syntax_tree, args, file_line_indent):
	"""
	determine the indent_unit for a function
	then check lines are consistently indented
	"""
	line_indent = {}
	get_indents(abstract_syntax_tree, None, 0, line_indent)
	indent_counts = collections.Counter(i.relative_indent for i in line_indent.values() if i.relative_indent > 0)
	if args.debug:
		print('indent_counts', indent_counts)
	if len(indent_counts) < 2:
		return set()

	# FIXME - change extraction of indent_unit to be per function
	# for small program ensure an indent of 4 has priority
	#indent_counts[4] += 2
	indent_unit = indent_counts.most_common(1)[0][0]
	show_lines = set()
	incorrectly_indented_lines = 0
	for (line, indent) in sorted(line_indent.items()):
		file_line_indent.setdefault(line, indent)
		indent.correct_indent = indent.indent_depth * indent_unit
		if not indent.correctly_indented():
			if not args.highlight_incorrect_indenting:
				print(f"{C_source_filename}:{line} indented {indent.absolute_indent} should be {indent.correct_indent}")
			incorrectly_indented_lines += 1
			show_lines = show_lines.union(range(indent.parent.extent.start.line, indent.parent.extent.end.line + 1))
	return show_lines


def expand_lines_shown(C_source_lines, show_lines):
	"""
		fill in small gaps in lines shown from a file for prettier less confusing output
	"""
	last_line_number = 0
	for line_number in sorted(show_lines):
		if last_line_number + 1 < line_number < last_line_number + 5:
			show_lines = show_lines.union(range( last_line_number + 1, line_number))
		last_line_number = line_number

	if len(C_source_lines) < last_line_number + 5:
		show_lines = show_lines.union(range(last_line_number + 1, len(C_source_lines) + 1))
	return show_lines



def print_indents(C_source_filename, C_source_lines, args, line_indent, show_lines):
	"""
	display correct/incorrect indents in red/green - idea due to AndrewB
	"""
	print(f"{C_source_filename}: {colored('warning', 'red')}: some lines are not consistently indented.")
	print("Incorrectly indented lines are marked with an *.", end='')
	if args.colorize:
		print(f" The correct indent is {colored('shown in red', on_color='on_red')}.")
		print(f"Correctly indented lines are {colored('shown in green', on_color='on_green')}.", end='')
	print()
	last_line_number = 0
	for line_number in sorted(show_lines):
		if last_line_number and line_number > last_line_number + 5:
			print('......')
		line = C_source_lines[line_number - 1]
		print(f'{line_number:6}', end='')
		if line_number in line_indent:
			print(line_indent[line_number].get_indent_string(line))
		else:
			print(' ', line)
		last_line_number = line_number

def get_indents(n, parent, indent_depth, line_indent):
	n.parent = parent
	if n.kind == CKind.COMPOUND_STMT:
		if parent.kind not in [CKind.IF_STMT, CKind.WHILE_STMT, CKind.FOR_STMT, CKind.FUNCTION_DECL]:
			return
		# handle if else if chains
		while parent.parent and parent.parent.kind == CKind.IF_STMT:
			parent = parent.parent
		for child in n.get_children():
			li = Indent(
				relative_indent = child.extent.start.column - parent.extent.start.column,
				absolute_indent = child.extent.start.column - 1,
				indent_depth = indent_depth + 1,
				parent = parent)
			line_indent.setdefault(child.extent.start.line, li)
			get_indents(child, n, indent_depth + 1 , line_indent)
		closing_brace = Indent(
			relative_indent = n.extent.end.column - parent.extent.start.column - 1,
			absolute_indent = n.extent.end.column - 2,
			indent_depth = indent_depth,
			parent = parent)
		line_indent.setdefault(n.extent.end.line, closing_brace)
	else:
		parent_filename = n.location.file.name if n.location.file else n.displayname
		for child in n.get_children():
			child_filename = child.location.file.name if child.location.file else child.displayname
			if child_filename == parent_filename:
				get_indents(child, n, indent_depth, line_indent)


class Indent():
	def __init__(self, absolute_indent=None, relative_indent=None, indent_depth=None, parent=None):
		self.absolute_indent = absolute_indent
		self.relative_indent = relative_indent
		self.indent_depth = indent_depth
		self.parent = parent
		self.correct_indent = None # calculated later

	def correctly_indented(self):
		return self.correct_indent == self.absolute_indent

	def get_indent_string(self, line):
		if self.correctly_indented():
			on_color = 'on_green'
			marker = ' '
		else:
			on_color = 'on_red'
			marker = '*'
		if len(line) < self.correct_indent:
			line += ' ' * (self.correct_indent - len(line))
		prefix = line[0:self.correct_indent]
		suffix = line[self.correct_indent:]
		return f'{marker} {colored(prefix, on_color=on_color)}{suffix}'


def abstract_syntax_tree_nodes(node, depth=0, parent=None):
	"""
	traverse ast nodes from same file (don't go into #includes)
	semantic_parent & lexical parents don't seem to be implement so add own our parent & depth
	"""
	node.depth = depth
	node.parent = parent
	yield node
	parent_filename = node.location.file.name if node.location.file else node.displayname
	for child in node.get_children():
		child_filename = child.location.file.name if child.location.file else child.displayname
		if  child_filename == parent_filename:
			for rn in abstract_syntax_tree_nodes(child, depth + 1, node):
				yield rn


def get_functions(root):
	for function in root.get_children():
		if (function.kind != CKind.FUNCTION_DECL or
			not function.location.file or
			function.location.file.name != root.displayname or
			# skip declarations
			not any(c.kind == CKind.COMPOUND_STMT for c in function.get_children())):
			continue
		yield function


def print_ast(node):
	for n in abstract_syntax_tree_nodes(node):
		print(' ' * n.depth, end='')
		print(f"{n.location.file}:{n.extent.start.line}:{n.extent.start.column} {n.kind.name} spelling='{n.spelling}' type='{n.type.spelling}'")


def node_location(n):
	return f'{n.location.file}:{n.extent.start.line}:{n.extent.start.column}'


def dump(obj):
	for attr in dir(obj):
		try:
			print("obj.%s = %r" % (attr, getattr(obj, attr)))
		except Exception:
			pass


if __name__ == "__main__":
	try:
		sys.exit(1 if main() else 0)
	except KeyboardInterrupt:
		sys.exit(2)
