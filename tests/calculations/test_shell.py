# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Tests for the :mod:`aiida_shell.calculations.shell` module."""
import io
import pathlib

from aiida.common.datastructures import CodeInfo
from aiida.orm import Data, Float, FolderData, Int, List, SinglefileData, Str
import pytest

from aiida_shell.calculations.shell import ShellJob


def test_code(generate_calc_job, generate_code):
    """Test the ``code`` input."""
    code = generate_code()
    inputs = {'code': code}
    dirpath, calc_info = generate_calc_job('core.shell', inputs)

    assert len(calc_info.codes_info) == 1
    assert isinstance(calc_info.codes_info[0], CodeInfo)
    assert calc_info.codes_info[0].code_uuid == code.uuid
    assert calc_info.codes_info[0].cmdline_params == []
    assert calc_info.codes_info[0].stdout_name == ShellJob.FILENAME_STDOUT
    assert calc_info.retrieve_temporary_list == ShellJob.DEFAULT_RETRIEVED_TEMPORARY
    assert not list(dirpath.iterdir())


def test_nodes_single_file_data(generate_calc_job, generate_code):
    """Test the ``nodes`` input with ``SinglefileData`` nodes ."""
    inputs = {
        'code': generate_code(),
        'nodes': {
            'xa': SinglefileData(io.StringIO('content')),
            'xb': SinglefileData(io.StringIO('content')),
        }
    }
    dirpath, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]

    assert code_info.cmdline_params == []
    assert code_info.stdout_name == ShellJob.FILENAME_STDOUT
    assert calc_info.retrieve_temporary_list == ShellJob.DEFAULT_RETRIEVED_TEMPORARY
    assert sorted([p.name for p in dirpath.iterdir()]) == ['xa', 'xb']


def test_nodes_folder_data(generate_calc_job, generate_code, tmp_path):
    """Test the ``nodes`` input with ``FolderData`` nodes ."""
    (tmp_path / 'file_a.txt').write_text('content a')
    (tmp_path / 'file_b.txt').write_text('content b')

    folder_flat = FolderData(tree=tmp_path.absolute())
    folder_nested = FolderData()
    folder_nested.base.repository.put_object_from_tree(tmp_path.absolute(), 'dir')
    inputs = {
        'code': generate_code(),
        'arguments': ['{nested}', '{nested_explicit}'],
        'nodes': {
            'flat': folder_flat,
            'nested': folder_nested,
            'flat_explicit': folder_flat,
            'nested_explicit': folder_nested,
        },
        'filenames': {
            'flat_explicit': 'sub',
            'nested_explicit': 'sub'
        }
    }
    dirpath, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]

    assert code_info.cmdline_params == ['nested', 'sub']
    assert code_info.stdout_name == ShellJob.FILENAME_STDOUT
    assert calc_info.retrieve_temporary_list == ShellJob.DEFAULT_RETRIEVED_TEMPORARY
    assert sorted([p.name for p in dirpath.iterdir()]) == ['dir', 'file_a.txt', 'file_b.txt', 'sub']
    assert sorted([p.name for p in (dirpath / 'dir').iterdir()]) == ['file_a.txt', 'file_b.txt']
    assert sorted([p.name for p in (dirpath / 'sub').iterdir()]) == ['dir', 'file_a.txt', 'file_b.txt']
    assert sorted([p.name for p in (dirpath / 'sub' / 'dir').iterdir()]) == ['file_a.txt', 'file_b.txt']
    assert (dirpath / 'file_a.txt').read_text() == 'content a'
    assert (dirpath / 'file_b.txt').read_text() == 'content b'


def test_nodes_base_types(generate_calc_job, generate_code):
    """Test the ``nodes`` input with ``BaseType`` nodes ."""
    inputs = {
        'code': generate_code(),
        'arguments': ['{float}', '{int}', '{str}'],
        'nodes': {
            'float': Float(1.0),
            'int': Int(2),
            'str': Str('string'),
        }
    }
    _, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]

    assert code_info.cmdline_params == ['1.0', '2', 'string']
    assert code_info.stdout_name == ShellJob.FILENAME_STDOUT
    assert calc_info.retrieve_temporary_list == ShellJob.DEFAULT_RETRIEVED_TEMPORARY


def test_nodes_single_file_data_filename(generate_calc_job, generate_code):
    """Test the selection rules for the filename used for ``SinglefileData`` nodes.

    The filename is determined in the following order:

     * Explicitly defined in ``filenames``,
     * The ``filename`` property of the ``SinglefileData`` node,
     * The key of the node in the ``nodes`` inputs dictionary.
    """
    inputs = {
        'code': generate_code(),
        'nodes': {
            'xa': SinglefileData(io.StringIO('content'), filename='single_file_a'),
            'xb': SinglefileData(io.StringIO('content')),
            'xc': SinglefileData(io.StringIO('content')),
        },
        'filenames': {
            'xb': 'filename_b',
        }
    }
    dirpath, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]

    assert code_info.cmdline_params == []
    assert code_info.stdout_name == ShellJob.FILENAME_STDOUT
    assert calc_info.retrieve_temporary_list == ShellJob.DEFAULT_RETRIEVED_TEMPORARY
    assert sorted([p.name for p in dirpath.iterdir()]) == ['filename_b', 'single_file_a', 'xc']


@pytest.mark.parametrize(
    'arguments, exception', (
        (['{place}{holder}'], r'argument `.*` is invalid as it contains more than one placeholder.'),
        (['{placeholder}'], r'argument placeholder `.*` not specified in `nodes`.'),
    )
)
def test_arguments_invalid(generate_calc_job, generate_code, arguments, exception):
    """Test the ``arguments`` input with invalid placeholders."""
    inputs = {
        'arguments': List(arguments),
        'code': generate_code(),
    }
    with pytest.raises(ValueError, match=exception):
        generate_calc_job('core.shell', inputs)


def test_arguments(generate_calc_job, generate_code):
    """Test the ``arguments`` input."""
    arguments = List(['-a', '--flag', 'local/filepath'])
    inputs = {'code': generate_code(), 'arguments': arguments}
    _, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]
    assert code_info.cmdline_params == arguments.get_list()


def test_arguments_files(generate_calc_job, generate_code):
    """Test the ``arguments`` with placeholders for inputs."""
    arguments = List(['{file_a}'])
    inputs = {
        'code': generate_code(),
        'arguments': arguments,
        'nodes': {
            'file_a': SinglefileData(io.StringIO('content'))
        },
    }
    _, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]
    assert code_info.cmdline_params == ['file_a']


def test_arguments_files_filenames(generate_calc_job, generate_code):
    """Test the ``arguments`` with placeholders for files and explicit filenames.

    Nested directories should be created automatically.
    """
    arguments = List(['{file_a}'])
    inputs = {
        'code': generate_code(),
        'arguments': arguments,
        'nodes': {
            'file_a': SinglefileData(io.StringIO('content')),
            'file_b': SinglefileData(io.StringIO('content')),
        },
        'filenames': {
            'file_a': 'custom_filename',
            'file_b': 'nested/custom_filename',
        }
    }
    _, calc_info = generate_calc_job('core.shell', inputs)
    code_info = calc_info.codes_info[0]
    assert code_info.cmdline_params == ['custom_filename']


def test_filename_stdin(generate_calc_job, generate_code, file_regression):
    """Test the ``metadata.options.filename_stdin`` input."""
    inputs = {
        'code': generate_code('cat'),
        'arguments': List(['{filename}']),
        'nodes': {
            'filename': SinglefileData(io.StringIO('content'))
        },
        'metadata': {
            'options': {
                'filename_stdin': 'filename'
            }
        }
    }
    tmp_path, calc_info = generate_calc_job('core.shell', inputs, presubmit=True)
    code_info = calc_info.codes_info[0]
    assert code_info.stdin_name == 'filename'

    options = ShellJob.spec_metadata['options']
    filename_submit_script = options['submit_script_filename'].default  # type: ignore[index,union-attr]
    file_regression.check((pathlib.Path(tmp_path) / filename_submit_script).read_text(), encoding='utf-8')


@pytest.mark.parametrize('redirect_stderr', (True, False, None))
def test_redirect_stderr(generate_calc_job, generate_code, redirect_stderr):
    """Test the ``metadata.options.redirect_stderr`` input."""
    inputs = {'code': generate_code('cat'), 'metadata': {'options': {}}}

    if redirect_stderr is not None:
        inputs['metadata']['options']['redirect_stderr'] = redirect_stderr

    _, calc_info = generate_calc_job('core.shell', inputs, presubmit=True)
    code_info = calc_info.codes_info[0]

    if redirect_stderr is True:
        assert code_info.join_files == redirect_stderr
    else:
        assert code_info.stderr_name == ShellJob.FILENAME_STDERR


@pytest.mark.parametrize(
    'outputs, message', (
        ([ShellJob.FILENAME_STATUS], r'`.*` is a reserved output filename and cannot be used in `outputs`.'),
        ([ShellJob.FILENAME_STDERR], r'`.*` is a reserved output filename and cannot be used in `outputs`.'),
        ([ShellJob.FILENAME_STDOUT], r'`.*` is a reserved output filename and cannot be used in `outputs`.'),
    )
)
def test_validate_outputs(generate_calc_job, generate_code, outputs, message):
    """Test the validator for the ``outputs`` argument."""
    with pytest.raises(ValueError, match=message):
        generate_calc_job('core.shell', {'code': generate_code(), 'outputs': outputs})


@pytest.mark.parametrize(
    'node_cls, message', (
        (Data, r'.*Unsupported node type for `.*` in `nodes`: .* does not have the `value` property.'),
        (Int, r'.*Casting `value` to `str` for `.*` in `nodes` excepted: .*'),
    )
)
def test_validate_nodes(generate_calc_job, generate_code, node_cls, message, monkeypatch):
    """Test the validator for the ``nodes`` argument."""
    nodes = {'node': node_cls()}

    if node_cls is Int:

        @property  # type: ignore[misc]
        def value_raises(self):
            """Raise an exception."""
            raise ValueError()

        monkeypatch.setattr(node_cls, 'value', value_raises)

    with pytest.raises(ValueError, match=message):
        generate_calc_job('core.shell', {'code': generate_code(), 'nodes': nodes})


@pytest.mark.parametrize(
    'arguments, message', (
        (['string', 1], r'.*all elements of the `arguments` input should be strings'),
        (['string', {input}], r'.*all elements of the `arguments` input should be strings'),
        (['<', '{filename}'], r'`<` cannot be specified in the `arguments`.*'),
        (['{filename}', '>'], r'the symbol `>` cannot be specified in the `arguments`.*'),
    )
)
def test_validate_arguments(generate_calc_job, generate_code, arguments, message):
    """Test the validator for the ``arguments`` argument."""
    with pytest.raises(ValueError, match=message):
        generate_calc_job('core.shell', {'code': generate_code(), 'arguments': arguments})


def test_build_process_label(generate_calc_job, generate_code):
    """Test the :meth:`~aiida_shell.calculations.shell_job.ShellJob.build_process_label` method."""
    computer = 'localhost'
    executable = '/bin/echo'
    code = generate_code(executable, computer_label=computer, label='echo')
    process = generate_calc_job('core.shell', {'code': code}, return_process=True)
    assert process._build_process_label() == f'ShellJob<{code.full_label}>'  # pylint: disable=protected-access


def test_submit_to_daemon(generate_code, submit_and_await):
    """Test submitting a ``ShellJob`` to the daemon."""
    builder = generate_code('echo').get_builder()
    builder.arguments = ['testing']
    node = submit_and_await(builder)
    assert node.is_finished_ok, node.process_state
    assert node.outputs.stdout.get_content().strip() == 'testing'


def test_parser(generate_calc_job, generate_code):
    """Test the ``parser`` input for valid input."""

    def parser(self, dirpath):  # pylint: disable=unused-argument
        pass

    process = generate_calc_job('core.shell', inputs={'code': generate_code(), 'parser': parser}, return_process=True)
    assert isinstance(process.inputs.parser, SinglefileData)


def test_parser_invalid_not_callable(generate_calc_job, generate_code):
    """Test the ``parser`` validation when input is not callable."""
    with pytest.raises(ValueError, match=r'The `parser` is not a callable function: .* is not a callable object'):
        generate_calc_job('core.shell', inputs={'code': generate_code(), 'parser': 'not-callable'})


def test_parser_invalid_signature(generate_calc_job, generate_code):
    """Test the ``parser`` validation when input is not callable."""
    with pytest.raises(ValueError, match=r'The `parser` has an invalid function signature, it should be:.*'):
        generate_calc_job('core.shell', inputs={'code': generate_code(), 'parser': lambda x: x})


def test_parser_over_daemon(generate_code, submit_and_await):
    """Test submitting a ``ShellJob`` with a custom parser over the daemon."""
    value = 'testing'

    def parser(self, dirpath):  # pylint: disable=unused-argument
        from aiida.orm import Str  # pylint: disable=reimported
        return {'string': Str((dirpath / 'stdout').read_text().strip())}

    builder = generate_code('/bin/echo').get_builder()
    builder.arguments = [value]
    builder.parser = parser

    node = submit_and_await(builder)
    assert node.is_finished_ok, (node.exit_status, node.exit_message)
    assert node.outputs.string == value
