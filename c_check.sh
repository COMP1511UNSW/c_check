#!/bin/sh

# example wrapper script for c_check.py

where_text="in COMP1511"

extra_text="
  For more information on C features not permitted in COMP1511
  See https://cgi.cse.unsw.edu.au/~cs1521/resources/style_guide.html
"

mixed_indenting_text="
  This makes the display of your code unreliable including when your tutor is marking for style.
  In COMP1511 we recommend indenting with spaces only, using 4 spaces per indent level.
  You can replace the tabs in C source with this command: replace_tabs
  For example to replace the tabs in example.c run:  replace_tabs example.c
"

c_check=/usr/local/lib/c_check/c_check.py

warning=assign_getchar_char,indenting,integer_ascii_code

not_permitted=global_variable,goto,static_local_variable,unistd_library

not_recommended=comma,do_while,switch,ternary,union

exec /usr/bin/python3 -I "$c_check" \
	--where-text "$where_text" \
	--extra-text "$extra_text" \
	--mixed-indenting-text "$mixed_indenting_text" \
	--not-permitted="$not_permitted" \
	--not-recommended="$not_recommended" \
	--warning="$warning" \
	--highlight-incorrect-indenting \
	"$@"
