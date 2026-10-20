Author: Konstantin M.J. Winkel, M.Sc.

# sarif_converters

This projects presents a simple and easy to use set python implementation of different converter specific formats to SARIF. Currently supported analyzers are:

- Pylint (json2 format) - a replacement for [this reporisory](https://github.com/GrammaTech/pylint-sarif).
- Shellcheck (json format)
- Clippy (json format)

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
| -c     | --converter       | String | Yes      | Select the converter to use, either pylint, shellcheck or clippy |
| -i     | --input           | Path   | Yes      | Path to the input json file |
|        | --max-artifacts   | Int    | No       | The maximum number of unique artifacts to process |
|        | --max-input-size  | Int    | No       | The maximum size of the input json file, in megabyte |
|        | --max-messages    | Int    | No       | The maximum number of unique rules to process |
|        | --max-output-size | Int    | No       | The maximum size of the output sarif file, in megabyte |
|        | --max-rules       | Int    | No       | The maximum number of messages to process |
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

### Clippy Example
```bash
cd examples/bad_rust_example
cargo clippy --message-format=json > ../clippy_output.json
cd -
python3 -m src.main -i examples/clippy_output.json -o examples/clippy_output.sarif -c clippy
```

## Example Usage as a Python Module
This tool can also be directly integrated into existing python projects as a module. Simply clone it into your project and import it using the following code:

```python
from sarif_converters import convert_pylint, convert_shellcheck
```

The supplied `convert_*` methods do the conversion. The arguments of the methods are identical to the CLI argmuments.

## Test Suite

This tool provides a test suite that allows all converters to be tested either together or individually.

```bash
python3 -m tests                        # test all suites
python3 -m tests --converter pylint     # test only the pylint suite
python3 -m tests --converter shellcheck # test only the shellcheck suite
python3 -m tests --converter clippy     # test only the clippy suite
```

## Further information
- [The SARIF Standard](https://sarifweb.azurewebsites.net/)
- [Pylint](https://www.pylint.org/)
- [Shellcheck](https://www.shellcheck.net)
- [Clipps](https://doc.rust-lang.org/clippy/index.html)

