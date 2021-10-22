
**`c_check`** can be used to inspect  C programs in introductory programing courses
for features that either, 

* a student should not be using generally (e.g. goto), or
* are not permitted for a specific exercises  (perhaps array)

It can also:

* detect incorrect indenting
* warn if integer constants are used for ASCII codes , e.g `10` instead of `'\n'`
* warn if functions like getchar are assigned to an int

For example:

```
$ c_check.py --not-permitted=global_variable,goto,static_local_variable \
            --not-recommended=ternary \
            --where-text="in COMP1511" \
            --extra-text="See the COMP1511 style guide at https://example.com"  \
            --warning=assign_getchar_char,integer_ascii_code,indenting \
            example.c
example.c:3:2 error: goto statement used - this is not permitted in COMP1511
	goto a;
    ^~~~~~
See the COMP1511 style guide at https://example.com
```

Available checkers include:


|     |     |
| --- | --- |
| **`array`**                   | check if array used (for exercises where ararys are not permitted) |
| **`assign_getchar_char`**      | check for common bug of getchar/fgetc/getc being assigned to char variable, e.g char c = getchar(); |
| **`break`**                    | check if break used |
| **`comma`**                    | check if comma operator used |
| **`continue`**                 | check if continue used |
| **`do_while`**                 | check if do while used |
| **`global_variable`**         | check global variables used |
| **`goto`**                     | check if goto used |
| **`indenting`**                | check indenting consistent with functions, and tabs/spaces not mixed within function |
| **`integer_ascii_code`**       | check integer constants not used for ASCII codes e.g. 10 instead of ' |
| ' |
| **`multiple_malloc`**          | check if malloc is called in more than 1 location  (for exercises where this is not permitted) |
| **`non_char_array`**          | check for use of array other than char array  (for exercises where this is not permitted) |
| **`static_local_variable`**   | check for use of static local variables |
| **`string_library`**           | check for use of functions from string.h (for exercises where this is not permitted) |
| **`switch`**                   | check if switch used |
| **`ternary`**                | check for use of the ?: operator |
| **`union`**                    | check if union used |



# Author

Andrew Taylor (andrewt@unsw.edu.au)

Except help_cs50.py  is almost entirely from  https://github.com/cs50/help50-server/blob/master/helpers/clang.py

# License

GPLv3
