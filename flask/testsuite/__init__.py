# -*- coding: utf-8 -*-
"""
    flask.testsuite
    ~~~~~~~~~~~~~~~

    Tests Flask itself.  The majority of Flask is already tested
    as part of Werkzeug.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
import flask
import warnings
import unittest
from StringIO import StringIO
from functools import update_wrapper
from contextlib import contextmanager
from werkzeug.utils import import_string, find_modules


def add_to_path(path):
    """Adds an entry to sys.path_info if it's not already there."""
    if not os.path.isdir(path):
        raise RuntimeError('Tried to add nonexisting path')

    def _samefile(x, y):
        try:
            return os.path.samefile(x, y)
        except (IOError, OSError):
            return False
    for entry in sys.path:
        try:
            if os.path.samefile(path, entry):
                return
        except (OSError, IOError):
            pass
    sys.path.append(path)


def iter_suites():
    """Yields all testsuites."""
    for module in find_modules(__name__):
        mod = import_string(module)
        if hasattr(mod, 'suite'):
            yield mod.suite()


def find_all_tests(suite):
    """Yields all the tests and their names from a given suite."""
    suites = [suite]
    while suites:
        s = suites.pop()
        try:
            suites.extend(s)
        except TypeError:
            yield s, '%s.%s.%s' % (
                s.__class__.__module__,
                s.__class__.__name__,
                s._testMethodName
            )


@contextmanager
def catch_warnings():
    """Catch warnings in a with block in a list"""
    # make sure deprecation warnings are active in tests
    warnings.simplefilter('default', category=DeprecationWarning)

    filters = warnings.filters
    warnings.filters = filters[:]
    old_showwarning = warnings.showwarning
    log = []
    def showwarning(message, category, filename, lineno, file=None, line=None):
        log.append(locals())
    try:
        warnings.showwarning = showwarning
        yield log
    finally:
        warnings.filters = filters
        warnings.showwarning = old_showwarning


@contextmanager
def catch_stderr():
    """Catch stderr in a StringIO"""
    old_stderr = sys.stderr
    sys.stderr = rv = StringIO()
    try:
        yield rv
    finally:
        sys.stderr = old_stderr


def emits_module_deprecation_warning(f):
    def new_f(self, *args, **kwargs):
        with catch_warnings() as log:
            f(self, *args, **kwargs)
            self.assert_(log, 'expected deprecation warning')
            for entry in log:
                self.assert_('Modules are deprecated' in str(entry['message']))
    return update_wrapper(new_f, f)


class FlaskTestCase(unittest.TestCase):
    """Baseclass for all the tests that Flask uses.  Use these methods
    for testing instead of the camelcased ones in the baseclass for
    consistency.
    """

    def ensure_clean_request_context(self):
        # make sure we're not leaking a request context since we are
        # testing flask internally in debug mode in a few cases
        self.assert_equal(flask._request_ctx_stack.top, None)

    def setup(self):
        pass

    def teardown(self):
        pass

    def setUp(self):
        self.setup()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        self.ensure_clean_request_context()
        self.teardown()

    def assert_equal(self, x, y):
        return self.assertEqual(x, y)


class BetterLoader(unittest.TestLoader):
    """A nicer loader that solves two problems.  First of all we are setting
    up tests from different sources and we're doing this programmatically
    which breaks the default loading logic so this is required anyways.
    Secondly this loader has a nicer interpolation for test names than the
    default one so you can just do ``run-tests.py ViewTestCase`` and it
    will work.
    """

    def getRootSuite(self):
        return suite()

    def loadTestsFromName(self, name, module=None):
        root = self.getRootSuite()
        if name == 'suite':
            return root

        all_tests = []
        for testcase, testname in find_all_tests(root):
            if testname == name or \
               testname.endswith('.' + name) or \
               ('.' + name + '.') in testname or \
               testname.startswith(name + '.'):
                all_tests.append(testcase)

        if not all_tests:
            raise LookupError('could not find test case for "%s"' % name)

        if len(all_tests) == 1:
            return all_tests[0]
        rv = unittest.TestSuite()
        for test in all_tests:
            rv.addTest(test)
        return rv


def setup_path():
    add_to_path(os.path.abspath(os.path.join(
        os.path.dirname(__file__), 'test_apps')))


def suite():
    """A testsuite that has all the Flask tests.  You can use this
    function to integrate the Flask tests into your own testsuite
    in case you want to test that monkeypatches to Flask do not
    break it.
    """
    setup_path()
    suite = unittest.TestSuite()
    for other_suite in iter_suites():
        suite.addTest(other_suite)
    return suite


def main():
    """Runs the testsuite as command line application."""
    try:
        unittest.main(testLoader=BetterLoader(), defaultTest='suite')
    except Exception, e:
        print 'Error: %s' % e
