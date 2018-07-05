#!/usr/bin/env python3

import argparse
import os.path
import os
import subprocess
import sys
import difflib
import shlex
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

max_workers = 48
verbose = False
dump_on_failure = False


Failure = namedtuple('Failure', ['fname', 'expected', 'output'])

"""
Per-test flags passed to test executable. Expected to be in a file with
same name as test, but with .flags extension.
"""


def get_test_flags(f):
    prefix, _ext = os.path.splitext(f)
    path = prefix + '.flags'

    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return shlex.split(f.read().strip())


def run_test_program(files, program, expect_ext, get_flags, use_stdin):
    """
    Run the program and return a list of Failures.
    """
    def run(f):
        test_dir, test_name = os.path.split(f)
        flags = get_flags(test_dir)
        test_flags = get_test_flags(f)
        cmd = [program]
        if not use_stdin:
            cmd.append(test_name)
        cmd += flags + test_flags
        if verbose:
            print('Executing', ' '.join(cmd))
        try:
            def go(stdin=None):
                return subprocess.check_output(
                    cmd, stderr=subprocess.STDOUT, cwd=test_dir,
                    universal_newlines=True, stdin=stdin)
            if use_stdin:
                with open(f) as stdin:
                    output = go(stdin)
            else:
                output = go()
        except subprocess.CalledProcessError as e:
            # we don't care about nonzero exit codes... for instance, type
            # errors cause hh_single_type_check to produce them
            output = e.output
        return check_result(f, expect_ext, output)

    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = [executor.submit(run, f) for f in files]

    results = [f.result() for f in futures]
    return [r for r in results if r is not None]


def filter_ocaml_stacktrace(text):
    """take a string and remove all the lines that look like
    they're part of an OCaml stacktrace"""
    assert isinstance(text, str)
    it = text.splitlines()
    out = []
    for x in it:
        drop_line = (
            x.lstrip().startswith("Called") or
            x.lstrip().startswith("Raised")
        )
        if drop_line:
            pass
        else:
            out.append(x)
    # force trailing newline
    return "\n".join(out) + "\n"


def check_result(fname, expect_exp, out):
    try:
        with open(fname + expect_exp, 'rt') as fexp:
            exp = fexp.read()
    except FileNotFoundError:
        exp = ''
    if exp != out and exp != filter_ocaml_stacktrace(out):
        return Failure(fname=fname, expected=exp, output=out)


def record_failures(failures, out_ext):
    for failure in failures:
        outfile = failure.fname + out_ext
        with open(outfile, 'wb') as f:
            f.write(bytes(failure.output, 'UTF-8'))


def dump_failures(failures):
    for f in failures:
        expected = f.expected
        actual = f.output
        diff = difflib.ndiff(
            expected.splitlines(1),
            actual.splitlines(1))
        print("Details for the failed test %s:" % f.fname)
        print("\n>>>>>  Expected output  >>>>>>\n")
        print(expected)
        print("\n=====   Actual output   ======\n")
        print(actual)
        print("\n<<<<< End Actual output <<<<<<<\n")
        print("\n>>>>>       Diff        >>>>>>>\n")
        print(''.join(diff))
        print("\n<<<<<     End Diff      <<<<<<<\n")


def get_hh_flags(test_dir):
    path = os.path.join(test_dir, 'HH_FLAGS')
    if not os.path.isfile(path):
        if verbose:
            print("No HH_FLAGS file found")
        return []
    with open(path) as f:
        return shlex.split(f.read().strip())


def files_with_ext(files, ext):
    """
    Returns the set of filenames in :files that end in :ext
    """
    result = set()
    for f in files:
        prefix, suffix = os.path.splitext(f)
        if suffix == ext:
            result.add(prefix)
    return result


def list_test_files(root, disabled_ext, test_ext):
    if os.path.isfile(root):
        if root.endswith(test_ext):
            return [root]
        else:
            return []
    elif os.path.isdir(root):
        result = []
        children = os.listdir(root)
        disabled = files_with_ext(children, disabled_ext)
        for child in children:
            if child != 'disabled' and child not in disabled:
                result.extend(
                    list_test_files(
                        os.path.join(root, child),
                        disabled_ext,
                        test_ext))
        return result
    elif os.path.islink(root):
        # Some editors create broken symlinks as part of their locking scheme,
        # so ignore those.
        return []
    else:
        raise Exception('Could not find test file or directory at %s' %
            args.test_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('test_path', help='A file or a directory. ')
    parser.add_argument('--program', type=os.path.abspath)
    parser.add_argument('--out-extension', type=str, default='.out')
    parser.add_argument('--expect-extension', type=str, default='.exp')
    parser.add_argument('--in-extension', type=str, default='.php')
    parser.add_argument('--disabled-extension', type=str,
            default='.no_typecheck')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--max-workers', type=int, default='48')
    parser.add_argument('--diff', action='store_true',
                       help='On test failure, show the content of the files and a diff')
    parser.add_argument('--flags', nargs=argparse.REMAINDER)
    parser.add_argument('--stdin', action='store_true',
                        help='Pass test input file via stdin')
    parser.epilog = "Unless --flags is passed as an argument, "\
                    "%s looks for a file named HH_FLAGS in the same directory" \
                    " as the test files it is executing. If found, the " \
                    "contents will be passed as arguments to " \
                    "<program>." % parser.prog
    args = parser.parse_args()

    max_workers = args.max_workers
    verbose = args.verbose
    dump_on_failure = args.diff

    if os.getenv('SANDCASTLE') is not None:
        dump_on_failure = True

    if not os.path.isfile(args.program):
        raise Exception('Could not find program at %s' % args.program)

    files = list_test_files(
        args.test_path,
        args.disabled_extension,
        args.in_extension)

    if len(files) == 0:
        raise Exception(
            'Could not find any files to test in ' + args.test_path)

    flags_cache = {}

    def get_flags(test_dir):
        if args.flags is not None:
            flags = args.flags
        else:
            if test_dir not in flags_cache:
                flags_cache[test_dir] = get_hh_flags(test_dir)
            flags = flags_cache[test_dir]
        hacksperimental_file = os.path.join(test_dir, '.hacksperimental')
        if os.path.isfile(hacksperimental_file):
            flags += ["--hacksperimental"]
        return flags

    failures = run_test_program(
        files, args.program, args.expect_extension, get_flags, args.stdin)
    total = len(files)
    if failures == []:
        print("All %d tests passed!\n" % total)
    else:
        record_failures(failures, args.out_extension)
        fnames = [failure.fname for failure in failures]
        print("To review the failures, use the following command: ")
        print("OUT_EXT=%s EXP_EXT=%s ./hphp/hack/test/review.sh %s" %
                (args.out_extension, args.expect_extension, " ".join(fnames)))
        if dump_on_failure:
            dump_failures(failures)
        print("Failed %d out of %d tests." % (len(failures), total))
        sys.exit(1)
