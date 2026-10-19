#!/bin/bash

# Author: Konstantin M.J. Winkel, M.Sc.

# This file contains some examples of bad shell code that is detected by shellcheck.
# Examples coppied from the "Gallery of bad code" on shellchecks github page: https://github.com/koalaman/shellcheck

# Quoting

echo $1                           # Unquoted variables
find . -name *.ogg                # Unquoted find/grep patterns
rm "~/my file.txt"                # Quoted tilde expansion
v='--verbose="true"'; cmd $v      # Literal quotes in variables
touch $@                          # Unquoted $@
echo 'Don't forget to restart!'   # Singlequote closed by apostrophe
echo 'Don\'t try this at home'    # Attempting to escape ' in ''
echo 'Path is $PATH'              # Variables in single quotes
trap "echo Took ${SECONDS}s" 0    # Prematurely expanded trap
unset var[i]                      # Array index treated as glob

# Conditionals

[[ n != 0 ]]                      # Constant test expressions
[[ -e *.mpg ]]                    # Existence checks of globs
[[ $foo==0 ]]                     # Always true due to missing spaces
[[ -n "$foo " ]]                  # Always true due to literals
[[ $foo =~ "fo+" ]]               # Quoted regex in =~
[ foo =~ re ]                     # Unsupported [ ] operators
[ $1 -eq "shellcheck" ]           # Numerical comparison of strings
[ $n && $m ]                      # && in [ .. ]
[[ "$$file" == *.jpg ]]           # Comparisons that can't succeed
(( 1 -lt 2 ))                     # Using test operators in ((..))
[ x ] & [ y ] | [ z ]             # Accidental backgrounding and piping

# Frequently misused commands

grep '*foo*' file                 # Globs in regex contexts
find . -exec foo {} && bar {} \;  # Prematurely terminated find -exec
sudo echo 'Var=42' > /etc/profile # Redirecting sudo
time --format=%s sleep 10         # Passing time(1) flags to time builtin
while read h; do ssh "$h" uptime  # Commands eating while loop input
alias archive='mv $1 /backup'     # Defining aliases with arguments
tr -cd '[a-zA-Z0-9]'              # [] around ranges in tr
exec foo; echo "Done!"            # Misused 'exec'
find -name \*.bak -o -name \*~ -delete  # Implicit precedence in find
# find . -exec foo > bar \;       # Redirections in find
f() { whoami; }; sudo f           # External use of internal functions

# Common beginner's mistakes

var = 42                          # Spaces around = in assignments
$foo=42                           # $ in assignments
for $var in *; do ...             # $ in for loop variables
var$n="Hello"                     # Wrong indirect assignment
echo ${var$n}                     # Wrong indirect reference
var=(1, 2, 3)                     # Comma separated arrays
array=( [index] = value )         # Incorrect index initialization
echo $var[14]                     # Missing {} in array references
echo "Argument 10 is $10"         # Positional parameter misreference
if $(myfunction); then ..; fi     # Wrapping commands in $()
else if othercondition; then ..   # Using 'else if'
f; f() { echo "hello world"; }     # Using function before definition
[ false ]                         # 'false' being true
if ( -f file )                    # Using (..) instead of test
