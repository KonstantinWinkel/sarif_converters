Author: Konstantin M.J. Winkel, M.Sc.

#sarif_converters

This projects presents a simple and easy to use set python implementation of different converter specific formats to SARIF. Currently supported analyzers are:

- Pylint (json2 format) - a replacement for [this reporisory](https://github.com/GrammaTech/pylint-sarif).
- Shellcheck (json format)

## Setup
To clone and setup this repository run the following commands.

```bash
git clone https://github.com/KonstantinWinkel/sarif_converters.git
cd sarif_converters
git submodule update --init shell_utils
./project_utils.sh setup
```

## Example Usage as CLI tool

### CLI Arguments

Many CLI options are available, see the table below.

| Option | Long Option       | Type   | Required | Description |
| ------ | -----------       | ----   | -------- | ----------- |
| -c     | --converter       | String | Yes      | Select the converter to use, either pylint or shellcheck |
| -i     | --input           | Path   | Yes      | Path to the input json file |
|        | --max-artifacts   | Int    | No       | The maximum number of unique artifacts to process |
|        | --max-input-size  | Int    | No       | The maximum size of the input json file, in megabyte |
|        | --max-messages    | Int    | No       | The maximum number of unique Pylint rules to process |
|        | --max-output-size | Int    | No       | The maximum size of the output sarif file, in megabyte |
|        | --max-rules       | Int    | No       | The maximum number of Pylint messages to process |
| -o     | --output          | Path   | Yes      | Path to the output sarif file |
| -v     | --verbose         |        | No       | Increase verbosity (-v, -vv, -vvv) |

### Pylint Example

```bash
pylint -f json2 --output examples/pylint_output.json examples/bad_python_example.py
python3 -m src.main -i examples/pylint_output.json -o examples/pylint_output.sarif -c pylint
```

### Shellcheck Example

```bash
shellcheck --format=json examples/bad_shell_example.sh > examples/shellcheck_output.json
python3 -m src.main -i examples/shellcheck_output.json -o examples/shellcheck_output.sarif -c shellcheck
```


## Example Usage as a Python Module
This tool can also be directly integrated into existing python projects as a module. Simply clone it into your project and import it using the following code:

```python
from sarif_converters import def convert_pylint, convert_shellcheck
```

The supplied `convert_*` methods do the conversion. The arguments of the methods are identical to the CLI argmuments.

## Test Suite

## Further information
- [The SARIF Standard](https://sarifweb.azurewebsites.net/)
- [Pylint](https://www.pylint.org/)
- [Shellcheck](https://www.shellcheck.net)

