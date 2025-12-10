# pylint: disable=missing-module-docstring
# .pylintrc

[MASTER]
ignore-files=TODO: ADD_IGNORE_FILES_HERE
ignore=node_modules,dist,build

[MESSAGES CONTROL]
disable=
    missing-module-docstring,
    missing-class-docstring,
    missing-function-docstring,
    too-many-arguments,
    too-many-locals,
    too-many-branches,
    too-many-statements,
    R0903, # Too few public methods
    C0114, # Missing module docstring
    C0115, # Missing class docstring
    C0116, # Missing function or method docstring
    W0511, # TODO or FIXME found
    W0703, # Catching too general exception Exception
    W1203, # Using an f-string that does not have any interpolated variables
    C0301  # Line too long