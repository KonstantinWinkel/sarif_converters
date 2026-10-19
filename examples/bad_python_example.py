# Author: Konstantin M.J. Winkel, M.Sc.

def method_without_docstring() -> int:

    return 1

def method_with_trailing_whitespace() -> int:
    """This method contains a comment with a trailing whitespace"""

    # this comment has a trailing whitespace 

    return 1

def method_with_too_long_line() -> int:
    """This method contains a line that is too long"""

    variable_name_that_is_way_longer_than_it_should_be = 1

    return variable_name_that_is_way_longer_than_it_should_be + variable_name_that_is_way_longer_than_it_should_be

def method_with_unused_variable() -> int:
    """This method contains a variable that is not used"""

    variable_that_is_not_used = 1

    return 1

def method_with_a_todo() -> None:
    """This method contains a todo"""

    # TODO add something here

    return None

def method_with_inconsistent_returns(value: int) -> int:
    """This method has multiple branches but not all of them return something"""

    if value == 0:
        return 0

    if value == 1:
        return

    return -1

def method_with_unecessary_pass() -> None:
    """This method contains an unnecessary pass"""

    pass

def method_with_unecessary_parentesies(number: int) -> bool:
    """This method contains if statements with unnecessary brackets"""

    if(number == 1):
        return True

    return False

def method_with_undefined_variabled() -> None:
    """This method contains a variable that has not been defined"""

    return undefined_variable_name
# Trailing new lines below!



