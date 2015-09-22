#!/usr/bin/env python


"""Platform Verify Tool for Experimenters.

This script will try to merge your experiment branch into our PhoneLab develop
branch, and then build the platform. You should pass this checker before
notifying us that your experiment changes are ready to deploy.

.. argparse::
  :module: platform_tools.release
  :func: arg_parser
  :prog: python release.py

"""

import argparse
import os
import random
import string
import multiprocessing
import subprocess

import utils
from utils import logger, time_it


EXPERIMENT_BRANCH_PREFIX = 'experiment'
"""Git branch prefix for experiment branches.

Experiment branch pattern is
``$EXPERIMENT_BRANCH_PREFIX/android-$tag/$id/$name``. See :mod:`new_exp` for
more details.
"""

DEFAULT_ANDROID_BASE = '5.1.1_r3'
"""Default AOSP version that we forked from.

See a `full list of AOSP version numbers
<https://source.android.com/source/build-numbers.html>`_.

.. note::
  This should probably be updated when upgrading to a new AOSP base.
"""

DEFAULT_DEVELOP_BRANCH = 'phonelab/android-%s/develop' % (DEFAULT_ANDROID_BASE)
"""Default develop branch name.

The develop branch contains bug fixes, statiblity, functionality, etc. And
should serve as an base for all other instrumentations or experiments.

.. note::
  The develop branch itself should NOT contain any particular insturmentations
  or experiments, which should reside in their own branch that forked from the
  develop branch.
"""

DEFAULT_REMOTE = 'aosp'
"""Default Git remote name for each branch.

This value is configuration in repo manifest xml file.
"""

DEFAULT_ROOT = os.getcwd()
"""Default AOSP root directory.
"""

DEFAULT_J = multiprocessing.cpu_count()*2
"""Default number of parallel workers.
"""

DEFAULT_TARGET = 'hammerhead'
"""Default build target.

This should be the `device code name
<https://source.android.com/source/running.html>`_.
codenames.
"""

DEFAULT_VARIANT = 'userdebug'
"""Default build variant.

See `here <http://blog.udinic.com/2014/06/04/aosp-part-2-build-variants/>`_ for
documents on build variants.
"""


def rand_string(len=64):
  """Return a random string of certain length.

  The string only contains ASCII characters (upper or lower case) and digits.

  """
  return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase\
      + string.digits) for _ in range(len))


class ReleaseInfo(object):
  """A all-in-one vehicle that contains various release information.
  """

  def __init__(self, *args, **kwargs):
    for attr, val in kwargs.items():
      setattr(self, attr, val)


def arg_parser():
  parser = argparse.ArgumentParser(\
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument('--exp', required=True, help="Experiment to merge, you"
      "should use your experiment code name, instead of the whole branch name.")

  parser.add_argument('--aosp_root', default=DEFAULT_ROOT,\
      help="Root of AOSP tree.")
  parser.add_argument('--j', type=int, default=DEFAULT_J,\
      help="# of processes for parallel build.")
  parser.add_argument('--target', default=DEFAULT_TARGET,
      help="Build target.")
  parser.add_argument('--variant', default=DEFAULT_VARIANT,
      help="Build variant.")
  parser.add_argument('--remote', default=DEFAULT_REMOTE,\
      help="Remote name.")

  parser.add_argument('--aosp_base', default=DEFAULT_ANDROID_BASE,\
      help="AOSP base release version code.")
  parser.add_argument('--dev', default=DEFAULT_DEVELOP_BRANCH,\
      help="Development branch.")

  parser.add_argument('--verbose', action='store_true', help="Verbose output.")
  return parser


def parse_args(rel_info):
  parser = arg_parser()
  args = parser.parse_args()

  for d in ['aosp_root']:
    setattr(args, d, os.path.abspath(getattr(args, d)))

  if not os.path.isdir(os.path.join(args.aosp_root, '.repo')):
    raise Exception("Invalide AOSP root: %s" % (args.aosp_root))

  rel_info.args = args


@time_it
def setup_test_branch(rel_info):
  """Set up temporal test branch.

  The test branch is forked base on the latest PhoneLab develop branch.
  """
  args = rel_info.args

  os.chdir(args.aosp_root)

  logger.info("Fetching latest PhoneLab develop branch: %s" % (args.dev))
  utils.repo_forall('git fetch %s %s:%s' % (args.remote, args.dev, args.dev), verbose=args.verbose)

  branch = rand_string()
  logger.info("Creating temp branch %s" % (branch))
  utils.repo_forall('git checkout -B %s %s' % (branch,\
      args.dev), verbose=args.verbose)

  rel_info.test_branch = branch


@time_it
def merge_branches(rel_info):
  """Merge the experiment branch.

  First figure out the exact branch name, then merge the experiment into the
  test branch.

  Throws:
    Exception: if the experiment branch does not exist.
  """
  args = rel_info.args

  os.chdir(os.path.join(args.aosp_root, 'frameworks', 'base'))

  logger.debug("Parsing experiment branches.")
  lines = subprocess.check_output('git branch -a', shell=True)

  experiment_branch = None
  for line in sorted(lines.split('\n')):
    line = line.strip()
    if line.startswith('remotes/%s/%s/android-%s' % (args.remote,\
        EXPERIMENT_BRANCH_PREFIX, args.aosp_base)):
      experiment_branch = '/'.join(line.split('/')[2:])
      if args.exp in experiment_branch:
        break

  if experiment_branch is None:
    raise Exception("No experiment branch found for experiment %s" % (args.exp))

  # refer to remote branch instead of local branch in case
  # the branch is not checked out yet for some projects
  experiment_branch = args.remote + '/' + experiment_branch

  # assign the experiment branch to rel_info right now.
  # otherwise, cleanup will not fail because of
  # undefined field.
  rel_info.experiment_branch = experiment_branch

  os.chdir(args.aosp_root)

  logger.info("Merging %s into %s" % (experiment_branch, rel_info.test_branch))
  utils.repo_forall('git merge %s -m "merge"' % (experiment_branch), verbose=args.verbose)


@time_it
def build_platform(rel_info):
  """Do a clean build of the platform (w/ experiment changes).
  """
  args = rel_info.args

  logger.info("Building platform.")
  os.chdir(args.aosp_root)
  utils.call('make clean', verbose=args.verbose)
  utils.call('make -j %d dist' % (args.j), verbose=args.verbose)


def cleanup(rel_info):
  """Delete test branch, switch back to experiment branch.
  """
  args = rel_info.args

  os.chdir(args.aosp_root)

  utils.repo_forall('git checkout %s' % (rel_info.experiment_branch), verbose=args.verbose)
  utils.repo_forall('git branch -D %s' % (rel_info.test_branch), verbose=args.verbose)


@time_it
def main():
  rel_info = ReleaseInfo()
  start_directory = os.getcwd()
  parse_args(rel_info)
  try:
    setup_test_branch(rel_info)
    merge_branches(rel_info)
    build_platform(rel_info)
  except:
    logger.exception("[FAILED] Please check your changes.")
  else:
    logger.info("[PASS] Your changes can be successfully merged and build.")
  finally:
    cleanup(rel_info)
    os.chdir(start_directory)


if __name__ == '__main__':
  main()
