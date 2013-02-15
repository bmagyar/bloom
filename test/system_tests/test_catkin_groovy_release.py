"""
These system tests are testing the release of groovy+ catkin projects.
"""

from __future__ import print_function

import os
import sys

try:
    from vcstools.vcs_abstraction import get_vcs_client
except ImportError:
    print("vcstools was not detected, please install it.", file=sys.stderr)
    sys.exit(1)

from .common import create_release_repo

from ..utils.common import bloom_answer
from ..utils.common import change_directory
from ..utils.common import in_temporary_directory
from ..utils.common import user
from ..utils.package_version import change_upstream_version

from bloom.git import branch_exists
from bloom.git import inbranch

from bloom.util import code

from bloom.commands.git.patch import export_cmd
from bloom.commands.git.patch import import_cmd
from bloom.commands.git.patch import remove_cmd


def create_upstream_repository(packages, directory=None):
    upstream_dir = 'upstream_repo_groovy'
    user('mkdir ' + upstream_dir)
    with change_directory(upstream_dir):
        user('git init .')
        user('echo "readme stuff" >> README.md')
        user('git add README.md')
        user('git commit -m "Initial commit"')
        user('git checkout -b groovy_devel')
        for package in packages:
            user('mkdir ' + package)
            with change_directory(package if len(packages) != 1 else '.'):
                package_xml = """\
<?xml version="1.0"?>
<package>
  <name>{0}</name>
  <version>0.1.0</version>
  <description>A catkin (groovy) ROS package called '{0}'</description>
  <maintainer email="bar@baz.com">Bar</maintainer>
  <license>BSD</license>

  <url type="bugtracker">https://github.com/ros/this/issues</url>
  <url type="repository">https://github.com/ros/this</url>

  <build_depend>catkin</build_depend>

  <run_depend>catkin</run_depend>
  <!-- required for messages generated by gencpp -->
  <run_depend>roscpp_core</run_depend>
</package>
    """.format(package)
                with open('package.xml', 'w+') as f:
                    f.write(package_xml)
                user('touch .cproject')
                user('touch .project')
                user('mkdir -p include')
                user('touch include/{0}.h'.format(package))
                user('git add package.xml .cproject .project include')
        user('git commit -m "Releasing version 0.1.0"')
        user('git tag 0.1.0 -m "Releasing version 0.1.0"')
        return os.getcwd()


def _test_unary_package_repository(release_dir, version, directory=None):
    print("Testing in {0} at version {1}".format(release_dir, version))
    with change_directory(release_dir):
        ###
        ### Import upstream
        ###
        user('git-bloom-import-upstream --quiet')
        # does the upstream branch exist?
        assert branch_exists('upstream', local_only=True), "no upstream branch"
        # does the upstrea/<version> tag exist?
        ret, out, err = user('git tag', return_io=True)
        assert out.count('upstream/' + version) == 1, "no upstream tag created"
        # Is the package.xml from upstream in the upstream branch now?
        with inbranch('upstream'):
            assert os.path.exists('package.xml'), \
                   "upstream did not import: '" + os.getcwd() + "': " + \
                   str(os.listdir(os.getcwd()))
            with open('package.xml') as f:
                package_xml = f.read()
                assert package_xml.count(version), "not right file"

        ###
        ### Release generator
        ###
        with bloom_answer(bloom_answer.ASSERT_NO_QUESTION):
            ret = user('git-bloom-generate -y release -s upstream --quiet')
        # patch import should have reported OK
        assert ret == code.OK, "actually returned ({0})".format(ret)
        # do the proper branches exist?
        assert branch_exists('release/foo'), "no release/foo branch"
        assert branch_exists('patches/release/foo'), \
               "no patches/release/foo branch"
        # was the release tag created?
        ret, out, err = user('git tag', return_io=True)
        assert out.count('release/foo/' + version) == 1, \
               "no release tag created"

        ###
        ### Make patch
        ###
        with inbranch('release/foo'):
            if os.path.exists('include/foo.h'):
                user('git rm include/foo.h')
            else:
                if not os.path.exists('include'):
                    os.makedirs('include')
                user('touch include/foo.h')
                user('git add include/foo.h')
            user('git commit -m "A release patch"')

        ###
        ### Test import and export
        ###
        with inbranch('release/foo'):
            export_cmd.export_patches()
            remove_cmd.remove_patches()
            import_cmd.import_patches()

        ###
        ### Release generator, again
        ###
        with bloom_answer(bloom_answer.ASSERT_NO_QUESTION):
            ret = user('git-bloom-generate -y release -s upstream --quiet')
        # patch import should have reported OK
        assert ret == code.OK, "actually returned ({0})".format(ret)
        # do the proper branches exist?
        assert branch_exists('release/foo'), "no release/foo branch"
        assert branch_exists('patches/release/foo'), \
               "no patches/release/foo branch"
        # was the release tag created?
        ret, out, err = user('git tag', return_io=True)
        assert out.count('release/foo/' + version) == 1, \
               "no release tag created"


@in_temporary_directory
def test_unary_package_repository(directory=None):
    """
    Release a single package catkin (groovy) repository.
    """
    directory = directory if directory is not None else os.getcwd()
    # Setup
    upstream_dir = create_upstream_repository(['foo'], directory)
    upstream_url = 'file://' + upstream_dir
    release_url = create_release_repo(upstream_url, 'git', 'groovy_devel')
    release_dir = os.path.join(directory, 'foo_release_clone')
    release_client = get_vcs_client('git', release_dir)
    release_client.checkout(release_url)
    versions = ['0.1.0', '0.1.1', '0.2.0']
    for index in range(len(versions)):
        _test_unary_package_repository(release_dir, versions[index], directory)
        if index != len(versions) - 1:
            change_upstream_version(upstream_dir, versions[index + 1])


@in_temporary_directory
def test_multi_package_repository(directory=None):
    """
    Release a multi package catkin (groovy) repository.
    """
    directory = directory if directory is not None else os.getcwd()
    # Setup
    pkgs = ['foo', 'bar', 'baz']
    upstream_dir = create_upstream_repository(pkgs, directory)
    upstream_url = 'file://' + upstream_dir
    release_url = create_release_repo(upstream_url, 'git', 'groovy_devel')
    release_dir = os.path.join(directory, 'foo_release_clone')
    release_client = get_vcs_client('git', release_dir)
    release_client.checkout(release_url)
    with change_directory(release_dir):
        ###
        ### Import upstream
        ###
        user('git-bloom-import-upstream --quiet')
        # does the upstream branch exist?
        assert branch_exists('upstream', local_only=True), "no upstream branch"
        # does the upstrea/0.1.0 tag exist?
        ret, out, err = user('git tag', return_io=True)
        assert out.count('upstream/0.1.0') == 1, "no upstream tag created"
        # Is the package.xml from upstream in the upstream branch now?
        with inbranch('upstream'):
            for pkg in pkgs:
                with change_directory(pkg):
                    assert os.path.exists('package.xml'), \
                           "upstream did not import: " + os.listdir()
                    with open('package.xml') as f:
                        assert f.read().count('0.1.0'), "not right file"

        ###
        ### Release generator
        ###
        with bloom_answer(bloom_answer.ASSERT_NO_QUESTION):
            ret = user('git-bloom-generate -y release -s upstream --quiet')
        # patch import should have reported OK
        assert ret == code.OK, "actually returned ({0})".format(ret)
        # Check the environment after the release generator
        ret, out, err = user('git tag', return_io=True)
        for pkg in pkgs:
            # Does the release/pkg branch exist?
            assert branch_exists('release/' + pkg), \
                   "no release/" + pkg + " branch"
            # Does the patches/release/pkg branch exist?
            assert branch_exists('patches/release/' + pkg), \
                   "no patches/release/" + pkg + " branch"
            # Did the release tag get created?
            assert out.count('release/' + pkg + '/0.1.0') == 1, \
                   "no release tag created for " + pkg
            # Is there a package.xml in the top level?
            with inbranch('release/' + pkg):
                assert os.path.exists('package.xml'), "release branch invalid"
                # Is it the correct package.xml for this pkg?
                package_xml = open('package.xml', 'r').read()
                assert package_xml.count('<name>' + pkg + '</name>'), \
                       "incorrect package.xml for " + str(pkg)

        # Make a patch
        with inbranch('release/' + pkgs[0]):
            user('echo "This is a change" >> README.md')
            user('git add README.md')
            user('git commit -m "added a readme"')

        ###
        ### Release generator, again
        ###
        with bloom_answer(bloom_answer.ASSERT_NO_QUESTION):
            ret = user(
                'git-bloom-generate -y release -s upstream', silent=False
            )
        # patch import should have reported OK
        assert ret == code.OK, "actually returned ({0})".format(ret)
        # Check the environment after the release generator
        ret, out, err = user('git tag', return_io=True)
        for pkg in pkgs:
            # Does the release/pkg branch exist?
            assert branch_exists('release/' + pkg), \
                   "no release/" + pkg + " branch"
            # Does the patches/release/pkg branch exist?
            assert branch_exists('patches/release/' + pkg), \
                   "no patches/release/" + pkg + " branch"
            # Did the release tag get created?
            assert out.count('release/' + pkg + '/0.1.0') == 1, \
                   "no release tag created for " + pkg
            # Is there a package.xml in the top level?
            with inbranch('release/' + pkg):
                assert os.path.exists('package.xml'), "release branch invalid"
                # Is it the correct package.xml for this pkg?
                with open('package.xml', 'r') as f:
                    assert f.read().count('<name>' + pkg + '</name>'), \
                       "incorrect package.xml for " + str(pkg)

        ###
        ### ROSDebian Generator
        ###
        with bloom_answer(bloom_answer.ASSERT_NO_QUESTION):
            ret, out, err = user('git-bloom-generate -y rosdebian '
                                 '-p release groovy', return_io=True,
                                 auto_assert=False)
            if ret != 0:
                print(out)
                print(err)
            assert ret == 0
        expected = "Debian Distributions: ['oneiric', 'precise', 'quantal']"
        assert out.count(expected) > 0, "not using expected ubuntu distros"
        # generator should have reported OK
        assert ret == code.OK, "actually returned ({0})".format(ret)
        # Check the environment after the release generator
        ret, out, err = user('git tag', return_io=True)
        for pkg in pkgs:
            for distro in ['oneiric', 'precise', 'quantal']:
                # Does the debian/distro/pkg branch exist?
                assert branch_exists('debian/groovy/' + distro + '/' + pkg), \
                       "no release/" + pkg + " branch"
                # Does the patches/debian/distro/pkg branch exist?
                patches_branch = 'patches/debian/groovy/' + distro + '/' + pkg
                assert branch_exists(patches_branch), \
                       "no patches/release/" + pkg + " branch"
                # Did the debian tag get created?
                tag = 'debian/ros-groovy-' + pkg + '_0.1.0-0_' + distro
                assert out.count(tag) == 1, \
                   "no release tag created for '" + pkg + "': `" + out + "`"
            # Is there a package.xml in the top level?
            with inbranch('debian/groovy/' + distro + '/' + pkg):
                assert os.path.exists('package.xml'), "release branch invalid"
                # Is it the correct package.xml for this pkg?
                with open('package.xml', 'r') as f:
                    assert f.read().count('<name>' + pkg + '</name>'), \
                       "incorrect package.xml for " + str(pkg)
