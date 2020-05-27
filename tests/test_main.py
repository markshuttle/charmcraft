# Copyright 2020 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For further info, check https://github.com/canonical/charmcraft

import argparse
import io
import textwrap
from unittest.mock import patch

from charmcraft.main import Dispatcher
from charmcraft.cmdbase import BaseCommand, CommandError
from tests.factory import create_command

import pytest


# --- Tests for the CustomArgumentParser


def get_generated_help(groups):
    """Helper to use the dispatcher to make the custom arg parser to generate special help."""
    dispatcher = Dispatcher([], groups)
    with patch.object(argparse.ArgumentParser, 'format_help', str):
        generated_help = dispatcher.main_parser.format_help()
    return generated_help


def test_customhelp_simplest():
    """Simplest situation: one command in (of course) one group."""
    groups = [
        ('test-group', "simple stuff (test)", [create_command('cmd-name', 'cmd help blah')]),
    ]
    generated_help = get_generated_help(groups)
    expected_help = """
        commands:

            simple stuff (test):
                cmd-name   cmd help blah
    """
    assert generated_help == textwrap.dedent(expected_help)


def test_customhelp_onegroup_severalcommands():
    """Multiple commands in the same group.

    Note that commands are ordered.
    """
    groups = [
        ('test-group', 'whatever title', [
            create_command('name1', 'cmd help 1'),
            create_command('zz-name2', 'cmd help 2'),
            create_command('other-name', 'super long help'),
        ]),
    ]
    generated_help = get_generated_help(groups)
    expected_help = """
        commands:

            whatever title:
                name1        cmd help 1
                other-name   super long help
                zz-name2     cmd help 2
    """
    assert generated_help == textwrap.dedent(expected_help)


def test_customhelp_several_simple_groups():
    """Multiple groups (each one simple).

    Note that the groups order are respected.
    """
    groups = [
        ('test-group-1', 'whatever title', [
            create_command('cmd-name', 'cmd help 1'),
        ]),
        ('test-group-2', 'other title', [
            create_command('cmd-longer-name', 'cmd help 2'),
        ]),
    ]
    generated_help = get_generated_help(groups)
    expected_help = """
        commands:

            whatever title:
                cmd-name          cmd help 1

            other title:
                cmd-longer-name   cmd help 2
    """
    assert generated_help == textwrap.dedent(expected_help)


def test_customhelp_combined():
    """Several commands in several groups."""
    groups = [
        ('test-group-1', 'this is very long title but we do not prejudge much', [
            create_command('1-name', 'cmd help 1'),
        ]),
        ('test-group-2', 'short', [
            create_command('cmd-B1', 'cmd help which is very long but whatever'),
            create_command('cmd-B2', 'cmd help'),
            create_command('cmd-longer-name', 'cmd help'),
        ]),
    ]
    generated_help = get_generated_help(groups)
    expected_help = """
        commands:

            this is very long title but we do not prejudge much:
                1-name            cmd help 1

            short:
                cmd-B1            cmd help which is very long but whatever
                cmd-B2            cmd help
                cmd-longer-name   cmd help
    """
    assert generated_help == textwrap.dedent(expected_help)


# --- Tests for the Dispatcher


def test_dispatcher_no_command():
    """When no command is given we should get the "usage" help."""
    groups = [('test-group', 'title', [create_command('cmd-name', 'cmd help')])]
    dispatcher = Dispatcher([], groups)
    fake_stdout = io.StringIO()
    with patch('sys.stdout', fake_stdout):
        retcode = dispatcher.run()
    assert retcode == -1
    assert "usage: charmcraft" in fake_stdout.getvalue()


def test_dispatcher_command_execution_ok():
    """Command execution depends of the indicated name in command line, return code ok."""
    class MyCommandControl(BaseCommand):
        help_msg = "some help"

        def __init__(self, group):
            super().__init__(group)
            self.executed = None

        def run(self, parsed_args):
            self.executed = parsed_args

    class MyCommand1(MyCommandControl):
        name = 'name1'

    class MyCommand2(MyCommandControl):
        name = 'name2'

    groups = [('test-group', 'title', [MyCommand1, MyCommand2])]
    dispatcher = Dispatcher(['name2'], groups)
    retcode = dispatcher.run()
    assert dispatcher.commands['name1'].executed is None
    assert isinstance(dispatcher.commands['name2'].executed, argparse.Namespace)
    assert retcode == 0


def test_dispatcher_command_execution_crash():
    """Command crashing is let pass through."""
    class MyCommand(BaseCommand):
        help_msg = "some help"
        name = 'cmdname'

        def run(self, parsed_args):
            raise ValueError()

    groups = [('test-group', 'title', [MyCommand])]
    dispatcher = Dispatcher(['cmdname'], groups)
    with pytest.raises(ValueError):
        dispatcher.run()


def test_dispatcher_command_execution_controlled_error():
    """Commands can indicate "fatal error" through a specific exception."""
    class MyCommand(BaseCommand):
        help_msg = "some help"
        name = 'cmdname'

        def run(self, parsed_args):
            raise CommandError("boom", retcode=-13)

    groups = [('test-group', 'title', [MyCommand])]
    dispatcher = Dispatcher(['cmdname'], groups)
    retcode = dispatcher.run()
    assert retcode == -13


@pytest.mark.parametrize("option", ['--verbose', '-v'])
def test_dispatcher_generic_setup_verbose(option):
    """Generic parameter handling for verbose log setup."""
    dispatcher = Dispatcher([option], [])
    with patch('charmcraft.logsetup.configure') as mock:
        dispatcher.run()
    mock.assert_called_with('verbose')


@pytest.mark.parametrize("option", ['--quiet', '-q'])
def test_dispatcher_generic_setup_quiet(option):
    """Generic parameter handling for silent log setup."""
    dispatcher = Dispatcher([option], [])
    with patch('charmcraft.logsetup.configure') as mock:
        dispatcher.run()
    mock.assert_called_with('quiet')


def test_dispatcher_load_commands_ok():
    """Correct command loading."""
    cmd0, cmd1, cmd2 = [create_command('cmd-name-{}'.format(n), 'cmd help') for n in range(3)]
    groups = [
        ('test-group-A', 'whatever title', [cmd0]),
        ('test-group-B', 'other title', [cmd1, cmd2]),
    ]
    dispatcher = Dispatcher([], groups)
    assert len(dispatcher.commands) == 3
    for cmd, group in [(cmd0, 'test-group-A'), (cmd1, 'test-group-B'), (cmd2, 'test-group-B')]:
        expected_cmd = dispatcher.commands[cmd.name]
        assert isinstance(expected_cmd, BaseCommand)
        assert expected_cmd.group == group


def test_dispatcher_load_commands_repeated():
    """Error while loading commands with repeated name."""
    class Foo(BaseCommand):
        help_msg = "some help"
        name = 'repeated'

    class Bar(BaseCommand):
        help_msg = "some help"
        name = 'cool'

    class Baz(BaseCommand):
        help_msg = "some help"
        name = 'repeated'

    groups = [
        ('test-group-1', 'whatever title', [Foo, Bar]),
        ('test-group-2', 'other title', [Baz]),
    ]
    expected_msg = "Multiple commands with same name: (Foo|Baz) and (Baz|Foo)"
    with pytest.raises(RuntimeError, match=expected_msg):
        Dispatcher([], groups)