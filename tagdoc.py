#!/usr/bin/python

"""Collect and generate documentation of existing tags.

.. argparse::
  :module: platform_tools.tagdoc
  :func: arg_parser
  :prog: python tagdoc.py

"""

import os
import sys
import re
import subprocess
import json
import argparse
import datetime
import xml.etree.ElementTree as ET

from utils import logger

COMMENT_PATTERN = re.compile(r'''/\*(?P<body>.*?)\*/''', re.DOTALL)

PHONELAB_DOC_PATTERN = re.compile(r'''PhoneLab.*?(?P<json>\{.*\})''',
                                  re.DOTALL)


DEFAULT_AOSP_BASE = 'cm-13.0'
DEFAULT_AOSP_ROOT = os.getcwd()
DEFAULT_OUT_FILE = os.path.join(os.getcwd(), 'tagdoc.rst')
DEFAULT_FORMAT = 'rst'

HTTP_SERVER = 'http://platform.phone-lab.org:8080'


class RepoProject(object):

    def __init__(self, root, path, name):
        self.root = root
        self.path = path
        self.name = name

        cwd = os.getcwd()
        os.chdir(os.path.join(self.root, self.path))
        self.current_branch = subprocess.check_output(
            'git rev-parse --abbrev-ref HEAD', shell=True).strip().strip('\n')
        os.chdir(cwd)

    @property
    def url(self):
        return '%s/gitweb?p=cm-shamu/%s.git' % (HTTP_SERVER, self.name)

    @property
    def abs_path(self):
        return os.path.join(self.root, self.path)

    def get_relative_path(self, path):
        return path[path.index(self.path) + len(self.path) + 1:]

    def get_file_url(self, file_path, line_no=None):
        url = '%s;a=blob;f=%s;hb=refs/heads/%s' %\
            (self.url, self.get_relative_path(file_path),
             self.current_branch)
        if line_no is not None:
            url = '%s#l%d' % (url, line_no)
        return url

    @classmethod
    def create_from_dir(self, repo_root):
        projs = []
        for child in ET.parse(os.path.join(repo_root, '.repo', 'manifests',
                                           'default.xml')).getroot():
            if child.tag == 'project' and 'notdefault' not in child.attrib.get(
                    'groups', ''):
                if 'path' in child.attrib:
                    projs.append(RepoProject(repo_root, child.attrib['path'],
                                             child.attrib['name']))
                else:
                    projs.append(RepoProject(repo_root, child.attrib['name'],
                                             child.attrib['name']))

        return projs

    def __repr__(self):
        return self.name


class TagDoc(object):

    FIELD_MAPPING = {
        'category': 'Category',
        'sub_category': 'SubCategory',
        'tag': 'Tag',
        'action': 'Action',
        'description': 'Description',
    }

    SRC_EXTENSIONS = ['.c', '.cpp', '.java']

    def __init__(self, doc, proj, file, line_no):
        self.proj = proj
        self.file = file
        self.line_no = line_no

        cls = self.__class__
        for attr, key in cls.FIELD_MAPPING.items():
            setattr(self, attr, doc[key])

        self.institution = self.tag.split('-')[-1]

    @classmethod
    def create_from_file(cls, proj, src_file):
        filename, extention = os.path.splitext(src_file)
        if extention not in cls.SRC_EXTENSIONS:
            return []

        tag_docs = []

        with open(src_file, 'r') as f:
            s = f.read()
            for comment in COMMENT_PATTERN.finditer(s):
                match = PHONELAB_DOC_PATTERN.search(comment.group('body'))
                if match is None:
                    continue
                try:
                    text = ' '.join([l.strip() for l in match.group(
                        'json').replace('*', '').splitlines()])
                    doc = json.loads(text)
                    tag_docs.append(TagDoc(doc, proj, src_file,
                                           s.count('\n', 0, comment.start()) + 1))
                except:
                    logger.exception("Invalid doc string in file %s: %s" %
                                     (src_file, match.group('json')))
                    logger.info("JSON Text: %s" % (text))
                    continue

        return tag_docs

    @classmethod
    def create_from_proj(cls, proj):
        tag_docs = []
        for dirpath, dirnames, filenames in os.walk(proj.abs_path):
            for f in filenames:
                tag_docs.extend(cls.create_from_file(
                    proj, os.path.join(dirpath, f)))

        return tag_docs


class HTMLFormatter(object):

    def __init__(self, tag_docs):
        self.tag_docs = tag_docs

    def __repr__(self):
        body = ''

        for category in sorted(list(set([t.category for t in self.tag_docs]))):
            body += '<h2><b>Category</b>: %s</h2>\n' % (category)
            category_tags = [
                t for t in self.tag_docs if t.category == category]
            for tag in sorted(list(set([t.tag for t in category_tags]))):
                body += '<h4><b>Tag</b>: <code>%s</code></h4>\n' % (tag)
                body += '<ol>\n'
                for tag in sorted([t for t in category_tags if t.tag == tag], key=lambda t: t.action):
                    body += '<li style="margin-bottom: 10px;">\n'
                    body += '<b>Action</b>: <code>%s</code></br>\n' % (
                        tag.action)
                    body += '<b>File</b>: <code><a href="%s" target="_blanck"><b>%s</b></a>/<a href="%s" target="_blank">%s:%d</a></code></br>\n'\
                        % (tag.proj.url, tag.proj.path, tag.proj.get_file_url(tag.file, tag.line_no), tag.proj.get_relative_path(tag.file), tag.line_no)
                    body += '<b>Description</b>: %s</br>\n' % (tag.description)
                    body += '</li>\n'
                body += '</ol>\n'

        tags = set([t.tag for t in self.tag_docs])
        actions = set([t.action for t in self.tag_docs])
        categories = set([t.category for t in self.tag_docs])
        institutions = set([t.institution for t in self.tag_docs])

        summary = '<h2>Summary</h2>\n'
        summary += "<p>PhoneLab's instrumented Android platform currently contains:</p>\n"
        summary += '<ul>\n'
        summary += '<li><b>%d</b> tags, <b>%d</b> actions,</li>\n' % (
            len(tags), len(actions))
        summary += '<li>... in <b>%d</b> categories,</li>\n' % (
            len(categories))
        summary += '<li>... added by <b>%d</b> institution%s.</li>\n' % (
            len(institutions), 's' if len(institutions) > 1 else '')
        summary += '</ul>\n'

        footer = '<hr>\n'
        footer += '<p><i>Last updated %s.</i></p>' % (datetime.date.today())

        return summary + body + footer


class RSTFormatter(object):

    def __init__(self, tag_docs):
        self.tag_docs = tag_docs

    def wrap_title(self, title, level='='):
        return '%s\n%s\n' % (title, level * len(title))

    def __repr__(self):
        body = ''
        for category in sorted(list(set([t.category for t in self.tag_docs]))):
            body += '\n\n'
            body += self.wrap_title('Catetory: %s' % (category), level='+')

            category_tags = [
                t for t in self.tag_docs if t.category == category]
            for tag in sorted(list(set([t.tag for t in category_tags]))):
                body += '\n\n'
                body += self.wrap_title('Tag: ``%s``' % (tag), level='~')
                body += '\n'
                for tag in sorted([t for t in category_tags if t.tag == tag],
                                  key=lambda t: t.action):
                    body += '#. | **Action**: ``%s``\n' % (tag.action)
                    body += '   | **Project**: `%s <%s>`_\n' % (tag.proj.path,
                                                                tag.proj.url)
                    body += '   | **File**: `%s:%d <%s>`_\n' %\
                        (tag.proj.get_relative_path(tag.file), tag.line_no,
                         tag.proj.get_file_url(tag.file, tag.line_no))
                    body += '   | **Description**: %s\n\n' % (tag.description)

        tags = set([t.tag for t in self.tag_docs])
        actions = set([t.action for t in self.tag_docs])
        categories = set([t.category for t in self.tag_docs])
        institutions = set([t.institution for t in self.tag_docs])

        summary = self.wrap_title('Summary', level='-')
        summary += "PhoneLab's instrumented Android platform currently contains:\n\n"
        summary += '* %d tags, %d actions,\n\n' % (len(tags), len(actions))
        summary += '* ... in %d categories,\n\n' % (len(categories))
        summary += '* ... added by %d institution%s.\n\n' % (len(institutions),
                                                             's' if len(institutions) > 1 else '')

        footer = 'Last updated %s' % (datetime.date.today())

        header = '.. Generated by %s on %s, DO NOT MODIFY.\n\n' % (
            os.path.basename(__file__), datetime.date.today())

        return header + summary + body + footer


FORMATTER_MAPPING = {
    'html': HTMLFormatter,
    'rst': RSTFormatter,
}


def arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--root', default=DEFAULT_AOSP_ROOT,
                        help="Repo root directory.")
    parser.add_argument('--out', default=DEFAULT_OUT_FILE,
                        help="Output file path.")
    parser.add_argument('--aosp', default=DEFAULT_AOSP_BASE,
                        help="AOSP base tag.")
    parser.add_argument('--format', default=DEFAULT_FORMAT,
                        choices=FORMATTER_MAPPING.keys(), help="Output format.")

    return parser


def main():
    parser = arg_parser()
    args = parser.parse_args()

    for attr in ['root', 'out']:
        setattr(args, attr, os.path.abspath(getattr(args, attr)))

    if not os.path.isdir(os.path.join(args.root, '.repo')):
        logger.error("No .repo dir found under %s" % (args.root))
        return

    release_branch_prefix = 'phonelab/%s/release-' % (args.aosp)
    develop_branch = 'phonelab/%s/develop' % (args.aosp)

    projects = RepoProject.create_from_dir(args.root)
    for proj in projects:
        if not proj.current_branch.startswith(release_branch_prefix):
            logger.error("Project %s not in release branch, current branch is %s."
                         % (proj.path, proj.current_branch))
            # return

    all_branches = set([proj.current_branch for proj in projects])
    if len(all_branches) > 1:
        logger.error(
            "Not all projects in same branch, do a `repo status` and check.")
        # return

    cwd = os.getcwd()
    tag_docs = []
    for proj in projects:
        os.chdir(proj.abs_path)
        ret = subprocess.call('git diff %s --exit-code 2>&1 >/dev/null' %
                              (develop_branch), shell=True)
        if ret == 0:
            logger.debug("Ignoring repo %s: not changes" % (proj))
            continue

        logger.info("Parsing project %s" % (proj.path))
        new_tags = TagDoc.create_from_proj(proj)
        logger.info("%d tags found." % (len(new_tags)))
        tag_docs.extend(new_tags)

    os.chdir(cwd)

    with open(args.out, 'w') as f:
        print >>f, str(FORMATTER_MAPPING[args.format](tag_docs))


if __name__ == '__main__':
    main()
