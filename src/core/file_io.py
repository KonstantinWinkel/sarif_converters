# Author: Konstantin M.J. Winkel, M.Sc.

"""File loading, path validation, and atomic SARIF output helpers."""

import json
import os
import stat
import tempfile


class SizeLimitedTextWriter:
    """Text writer that enforces a UTF-8 byte limit."""

    def __init__(self, file_object, maximum_bytes: int):
        self._file_object = file_object
        self._maximum_bytes = maximum_bytes
        self._bytes_written = 0

    def write(self, value: str) -> int:
        """Write text only while the configured UTF-8 byte limit is respected."""

        encoded_size = len(value.encode("utf-8"))
        if self._bytes_written + encoded_size > self._maximum_bytes:
            raise ValueError(
                f"Generated SARIF exceeds the {self._maximum_bytes}-byte output limit"
            )
        written = self._file_object.write(value)
        self._bytes_written += encoded_size

        return written


def validate_input_output_paths(input_path: str, output_path: str) -> None:
    """Reject paths that resolve to the same filesystem object."""

    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if os.path.exists(output_path):
        try:
            paths_collide = os.path.samefile(input_path, output_path)
        except OSError as exc:
            raise ValueError("Unable to safely compare input and output paths") from exc
    else:
        paths_collide = (
            os.path.normcase(os.path.realpath(input_path))
            == os.path.normcase(os.path.realpath(output_path))
        )
    if paths_collide:
        raise ValueError("Input and output paths must refer to different files")


def load_json(path: str, maximum_bytes: int) -> object:
    """Load bounded JSON content from a regular file."""

    open_flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        open_flags |= os.O_NONBLOCK
    if hasattr(os, "O_CLOEXEC"):
        open_flags |= os.O_CLOEXEC

    file_descriptor = os.open(path, open_flags)
    try:
        file_status = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_status.st_mode):
            raise ValueError("Input path must refer to a regular file")
        if file_status.st_size > maximum_bytes:
            raise ValueError(f"Input file exceeds the {maximum_bytes}-byte size limit")

        with os.fdopen(file_descriptor, "rb", closefd=False) as file_object:
            content = file_object.read(maximum_bytes + 1)
    finally:
        os.close(file_descriptor)

    if len(content) > maximum_bytes:
        raise ValueError(f"Input file exceeds the {maximum_bytes}-byte size limit")

    return json.loads(content.decode("utf-8"))


def load_template(path: str) -> dict:
    """Load a JSON template file."""

    with open(path, 'r', encoding='utf-8') as file_object:
        return json.load(file_object)


def save_json_atomically(content: dict, path: str, maximum_bytes: int) -> None:
    """Atomically publish JSON without overwriting an existing entry."""

    output_path = os.path.abspath(path)
    output_directory = os.path.dirname(output_path)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=output_directory,
                prefix=f".{os.path.basename(output_path)}.", suffix='.tmp',
                delete=False) as file_object:
            temporary_path = file_object.name
            limited_writer = SizeLimitedTextWriter(file_object, maximum_bytes)
            json.dump(content, limited_writer, ensure_ascii=False, indent=4)
            file_object.flush()
            os.fsync(file_object.fileno())

        try:
            os.link(temporary_path, output_path)
        except FileExistsError as exc:
            raise FileExistsError(
                f"Refusing to overwrite existing output path: {path}"
            ) from exc
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
