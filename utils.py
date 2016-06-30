import os
import subprocess
import logging
import hashlib
import time
import xml.etree.ElementTree as ET

logging.basicConfig(format='[%(asctime)s] %(levelname)8s [%(filename)16s:%(lineno)4d] %(message)s', level=logging.DEBUG)
logger = logging.getLogger('phonelab')


DEVNULL = open(os.devnull, 'w')

def call(cmd, verbose=False, dryrun=False):
  if verbose:
    logger.debug(cmd)
    if not dryrun:
      subprocess.check_call(cmd, shell=True)
  else:
    if not dryrun:
      subprocess.check_call(cmd, stdout=DEVNULL, stderr=DEVNULL, shell=True)


def repo_forall(cmd, verbose=False, dryrun=False):
  """Wrap of ``repo forall`` without output pager.
  """
  call('GIT_PAGER= repo forall -j 4 -epv -c %s' % (cmd), verbose, dryrun)


def bump_version(ver):
  """Bump up patch part of version.
  """
  numbers = ver.split('.')
  assert all([len(i) == 1 for i in numbers]), "Version number should be x.y.x, where x, y and z are one digit numbers."
  current = int(ver.replace('.', ''))
  return '.'.join(str(int(current+1)))


def md5_hash(path):
  """Compute file's MD5 hash.

  Args:
      path (str): file's path.

  Returns:
      string: file's MD5 hash.
  """
  hashlib.md5(open(path, 'rb').read()).hexdigest()


def find(dir, filename):
  """Recursively find files under directory.

  Args:
      dir (str): directory to search
      filename: file name to search

  Returns:
      list: A list of file paths. Could be empty.
  """
  hit = []
  for dirpath, dirname, filenames in os.walk(dir):
    if filename in filenames:
      hit.append(os.path.join(dirpath, filename))
  return hit


def time_it(func):

  def func_wrapper(*args, **kwargs):
    start = time.time()
    func(*args, **kwargs)
    duration_sec = time.time() - start
    logger.debug("%s finished, time elapesd: %d min %d sec" % (func.__name__,\
        int(duration_sec / 60), int(duration_sec % 60)))

  return func_wrapper


def get_repo_projs(aosp_root):
    projs = []
    for child in ET.parse(os.path.join(aosp_root, '.repo', 'manifests',\
        'default.xml')).getroot():
      if child.tag == 'project' and 'notdefault' not in child.attrib.get(\
          'groups', ''):
        projs.append(child.attrib['path'])

    return projs

