#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import codecs
import glob
import os
import posixpath
import subprocess
import sys
import time
import urllib
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

import jinja2
import markdown


GREEN = '\033[32m'
RED = '\033[31m'
DEFAULT = '\033[0m'
PINK = '\033[91m'
YELLOW = '\033[33m'


PARTS = [
  '', [
    'Table of Contents',
  ],
  'The Lay of the Land', [
    'Introduction',
    'The Pancake Language',
    'The Lox Language',
    # ...
  ],
  'The View from the Top', [
    'Read, Evaluate, Print, Loop',
    'Scanning',
    'Representing Code',
    'Parsing Expressions',
    'Evaluating Expressions',
    'Statements and State',
    'Control Flow',
    'Functions',
    'Resolving and Binding',
    'Classes',
    'Inheritance',
    'Reaching the Summit',
  ],
  'The Long Way Down', [
    'Chunks of Bytecode',
    'A Virtual Machine',
    'Scanning on Demand',
    'Compiling Expressions',
    'Types of Values',
    'Strings',
    'Hash Tables',
    'Global Variables',
    'Local Variables',
    'Jumping Forward and Back',
    'Function Calls',
    'User-Defined Functions',
    'Closures',
    'Garbage Collection',
    'Classes and Instances',
    'Methods and Initializers',
    'Superclasses',
    'Optimization',
  ],
  '', [
    'Glossary'
  ]
]


def flatten_pages():
  """Flatten the list of parts and chapters to a single linear list of pages."""
  pages = []
  for part in PARTS:
    if part == '':
      # Empty names are for the front- and backmatter "parts".
      pass
    elif isinstance(part, str):
      pages.append(part)
    else:
      pages.extend(part)

  return pages

PAGES = flatten_pages()

def roman(n):
  """Convert n to roman numerals."""
  if n <= 3:
    return "I" * n
  elif n == 4:
    return "IV"
  elif n < 10:
    return "V" + "I" * (n - 5)
  else:
    raise "Can't convert " + str(n) + " to Roman."

def number_chapters():
  """Determine the part or chapter numbers for each part or chapter."""
  numbers = {}
  part_num = 1
  in_matter = False
  chapter_num = 1
  for part in PARTS:
    if part == '':
      # Empty names are for the front- and backmatter "parts".
      in_matter = True
      pass
    elif isinstance(part, str):
      numbers[part] = roman(part_num)
      part_num += 1
      in_matter = False
    else:
      for chapter in part:
        if in_matter:
          # Front and backmatter content is not numbered.
          numbers[chapter] = "-"
        else:
          numbers[chapter] = chapter_num
          chapter_num += 1

  return numbers

NUMBERS = number_chapters()

num_chapters = 0
empty_chapters = 0
total_words = 0


class RootedHTTPServer(HTTPServer):
  """Simple server that resolves paths relative to a given directory.

  From: http://louistiao.me/posts/python-simplehttpserver-recipe-serve-specific-directory/
  """
  def __init__(self, base_path, *args, **kwargs):
    HTTPServer.__init__(self, *args, **kwargs)
    self.RequestHandlerClass.base_path = base_path


class RootedHTTPRequestHandler(SimpleHTTPRequestHandler):
  """Simple handler that resolves paths relative to a given directory.

  From: http://louistiao.me/posts/python-simplehttpserver-recipe-serve-specific-directory/
  """
  def translate_path(self, path):
    # Refresh on request.
    format_files(True)
    build_sass(True)

    path = posixpath.normpath(urllib.unquote(path))
    words = path.split('/')
    words = filter(None, words)
    path = self.base_path
    for word in words:
      drive, word = os.path.splitdrive(word)
      head, word = os.path.split(word)
      if word in (os.curdir, os.pardir):
        continue
      path = os.path.join(path, word)
    return path


def title_to_file(title):
  '''Given a title like "Hash Tables", converts it to the corresponding file
  name like "hash-tables".'''
  if title == "Table of Contents":
    return "contents"

  return title.lower().replace(" ", "-").translate(None, ',.?!:/"')


def adjacent_page(title, offset):
  '''Generate template data to link to the previous or next page.'''
  page_index = PAGES.index(title) + offset
  if page_index < 0 or page_index >= len(PAGES): return None

  return PAGES[page_index]


def pretty(text):
  '''Use nicer HTML entities and special characters.'''
  text = text.replace(" -- ", "&#8202;&mdash;&#8202;")
  text = text.replace("à", "&agrave;")
  text = text.replace("ï", "&iuml;")
  text = text.replace("ø", "&oslash;")
  text = text.replace("æ", "&aelig;")
  return text


def format_file(path, skip_up_to_date):
  basename = os.path.basename(path)
  basename = basename.split('.')[0]

  output_path = "site/" + basename + ".html"

  # See if the HTML is up to date.
  if skip_up_to_date:
    source_mod = max(
        os.path.getmtime(path),
        os.path.getmtime('asset/template/page.html'),
        os.path.getmtime('asset/template/toc.html'))
    # if os.path.exists(cpp_path(basename)):
    #   source_mod = max(source_mod, os.path.getmtime(cpp_path(basename)))

    dest_mod = os.path.getmtime(output_path)

    if source_mod < dest_mod:
      return

  title = ''
  title_html = ''
  part = None
  # isoutline = False

  sections = []

  # Read the markdown file and preprocess it.
  contents = ''
  with open(path, 'r') as input:
    # Read each line, preprocessing the special codes.
    for line in input:
      stripped = line.lstrip()
      indentation = line[:len(line) - len(stripped)]

      if stripped.startswith('^'):
        command,_,args = stripped.rstrip('\n').lstrip('^').partition(' ')
        args = args.strip()

        if command == 'title':
          title = args
          title_html = title

          # Remove any discretionary hyphens from the title.
          title = title.replace('&shy;', '')
        elif command == 'part':
          part = args
        # elif command == 'code':
        #   contents = contents + include_code(basename, args, indentation)
        # elif command == 'outline':
        #   isoutline = True
        # else:
        #   print "UNKNOWN COMMAND:", command, args

      elif stripped.startswith('#'):
        # Build the section navigation from the headers.
        index = stripped.find(" ")
        header_type = stripped[:index]
        header = pretty(stripped[index:].strip())
        anchor = title_to_file(header)
        anchor = anchor.translate(None, '.?!:/"')

        # Add an anchor to the header.
        contents += indentation + header_type
        contents += '<a href="#' + anchor + '" name="' + anchor + '">' + header + '</a>\n'

        # Build the section navigation.
        if len(header_type) == 2:
          sections.append(header)

      else:
        contents += pretty(line)

  chapters = []
  first_chapter = 0
  if title in PARTS:
    chapters = PARTS[PARTS.index(title) + 1]
    first_chapter = NUMBERS[chapters[0]]

  # title_text = title
  # section_header = ""

  # if section != "":
  #   title_text = title + " &middot; " + section
  #   section_href = section.lower().replace(" ", "-")
  #   section_header = '<span class="section"><a href="{}.html">{}</a></span>'.format(
  #     section_href, section)

  # Allow processing markdown inside asides.
  contents = contents.replace('<aside', '<aside markdown="1"')
  body = markdown.markdown(contents, ['extra', 'codehilite', 'smarty'])
  body = body.replace('<aside markdown="1"', '<aside')

  data = {
    'title': title,
    'part': part,
    'body': body,
    'sections': sections,
    'chapters': chapters,
    'first_chapter': first_chapter,
    'number': NUMBERS[title],
    'prev': adjacent_page(title, -1),
    'next': adjacent_page(title, 1)
  }

  template = environment.get_template('page.html')
  output = template.render(data)

  # Write the output.
  with codecs.open(output_path, "w", encoding="utf-8") as out:
    out.write(output)

  global total_words
  global num_chapters
  global empty_chapters

  word_count = len(contents.split(None))
  # Non-chapter pages aren't counted like regular chapters.
  if part:
    num_chapters += 1
    if word_count < 50:
      empty_chapters += 1
      print "  {}".format(basename)
    elif word_count < 2000:
      empty_chapters += 1
      print "{}-{} {} ({} words)".format(
        YELLOW, DEFAULT, basename, word_count)
    else:
      total_words += word_count
      print "{}✓{} {} ({} words)".format(
        GREEN, DEFAULT, basename, word_count)
  else:
    print "{}•{} {} ({} words)".format(
      GREEN, DEFAULT, basename, word_count)


def format_files(skip_up_to_date):
  '''Process each markdown file.'''
  for file in glob.iglob("book/*.md"):
    format_file(file, skip_up_to_date)


def build_sass(skip_up_to_date):
  '''Process each SASS file.'''
  for source in glob.iglob("asset/*.scss"):
    dest = "site/" + os.path.basename(source).split(".")[0] + ".css"

    if skip_up_to_date:
      source_mod = os.path.getmtime(source)
      dest_mod = os.path.getmtime(dest)
      if source_mod < dest_mod:
        continue

    subprocess.call(['sass', source, dest])
    print "{}✓{} {}".format(GREEN, DEFAULT, dest)


def run_server():
  port = 8000
  handler = RootedHTTPRequestHandler
  server = RootedHTTPServer("site", ('', port), handler)

  print 'Serving at port', port
  server.serve_forever()


environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('asset/template'))

environment.filters['file'] = title_to_file

if len(sys.argv) == 2 and sys.argv[1] == "--watch":
  run_server()
  while True:
    format_files(True)
    build_sass(True)
    time.sleep(0.3)
if len(sys.argv) == 2 and sys.argv[1] == "--serve":
  run_server()
else:
  format_files(False)
  build_sass(False)

  average_word_count = total_words / (num_chapters - empty_chapters)
  estimated_word_count = total_words + (empty_chapters * average_word_count)
  percent_finished = total_words * 100 / estimated_word_count

  print "{}/~{} words ({}%)".format(
    total_words, estimated_word_count, percent_finished)