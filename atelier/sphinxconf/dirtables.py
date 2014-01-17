# -*- coding: utf-8 -*-
# Copyright 2014 by Luc Saffre.
# License: BSD, see LICENSE for more details.

from __future__ import print_function
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from os import path

from os.path import abspath, dirname, join

from docutils.parsers.rst import directives


from sphinx.util import docname_join
from sphinx.util.matching import patfilter

from atelier import rstgen

from .insert_input import InsertInputDirective

package_dir = abspath(dirname(__file__))

from jinja2 import FileSystemLoader, TemplateNotFound
from jinja2 import Environment
# from jinja2.sandbox import SandboxedEnvironment as Environment

template_dirs = [join(package_dir, 'templates')]
template_loader = FileSystemLoader(template_dirs)
template_env = Environment(loader=template_loader)


def render_entry(tplname, context):
    try:
        template = template_env.get_template(tplname)
    except TemplateNotFound:
        template = template_env.get_template('dirtables/entry.rst')
    return template.render(context)

def rel_docname(a, b):
    """
    >>> print(rel_docname('tickets/index','tickets/2'))
    2
    >>> print(rel_docname('tickets/index','/todo/index'))
    /todo/index
    """
    if b.startswith('/'):
        return b
    a1 = a.rsplit('/')[0] + '/'
    if b.startswith(a1):
        return b[len(a1):]
    return b


class Entry(object):

    def __init__(self, docname, title, meta):
        self.docname = docname
        self.title = title
        self.meta = meta

    @classmethod
    def create(cls, env, docname):
        return cls(rel_docname(env.docname, docname),
                   env.titles.get(docname),
                   env.metadata.get(docname))


class DirectoryTable(InsertInputDirective):
    entry_class = Entry
    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        'filter': directives.unchanged,
        'orderby': directives.unchanged,
    }

    def get_rst(self):
        env = self.state.document.settings.env
        entries = []
        all_docnames = env.found_docs.copy()
        found = set([env.docname])  # don't include myself
        for entry in self.content:
            if not entry:
                continue
            patname = docname_join(env.docname, entry)
            docnames = sorted(patfilter(all_docnames, patname))
            for docname in docnames:
                if not docname in found:
                    found.add(docname)
                    entries.append(self.entry_class.create(env, docname))
        expr = self.options.get('filter')
        if expr:
            def func(e):
                return eval(expr, dict(e=e))
            entries = filter(func, entries)

        orderby = self.options.get('orderby')
        if orderby:
            def func(a, b):
                va = getattr(a, orderby, '')
                vb = getattr(b, orderby, '')
                return cmp(va, vb)
            entries = sorted(entries, func)

        headers = self.get_headers()
        rows = []
        for e in entries:
            rows.append(self.format_entry(e))
        return rstgen.table(headers, rows)

    def get_headers(self):
        return ['title', 'author', 'date']

    def format_entry(self, e):
        cells = []
        text = ''.join([unicode(c) for c in e.title.children])
        cells.append(":doc:`%s <%s>`" % (text, e.docname))
        cells.append(unicode(e.meta.get('author', '')))
        cells.append(unicode(e.meta.get('date', '')))
        return cells


class TicketsTable(DirectoryTable):

    def get_headers(self):
        return ['title', 'state', 'module', 'since', 'for']

    def format_entry(self, e):
        cells = []
        # cells.append(e.docname)
        text = ''.join([unicode(c) for c in e.title.children])
        cells.append(":doc:`%s <%s>`" % (text, e.docname))
        cells.append(unicode(e.meta.get('state', '')))
        # cells.append(unicode(e.meta.get('reporter', '')))
        ref = e.meta.get('module', '')
        if ref:
            cells.append(":mod:`%s`" % ref)
        else:
            cells.append("(N/A)")

        cells.append(unicode(e.meta.get('since', '')))
        cells.append(unicode(e.meta.get('for', '')))
        return cells


class EntryIntro(InsertInputDirective):
    
    def get_rst(self):
        env = self.state.document.settings.env
        docname = env.docname
        meta = env.process_metadata(docname, self.state.document)
        # e = Entry.create(env, env.docname)
        context = dict(this=self,
                       env=self.state.document.settings.env,
                       dir=dir,
                       document=self.state.document,
                       meta=meta)
        template = 'dirtables/entry.rst'
        return render_entry(template, context)

# from docutils import nodes
# from sphinx.roles import XRefRole

# RREFS


# class ReferingRefRole(XRefRole):
#     def result_nodes(self, document, env, node, is_ref):
#         # RREFS[]
#         print("20140115 result_nodes", document, env, node, is_ref)
#         return [node], []

from docutils import nodes
from sphinx import addnodes


class RefsToThis(InsertInputDirective):
    def get_rst(self):
        # return str(self.state.document.refnames)
        env = self.state.document.settings.env
        target = ' '.join(self.content).strip()
        entries = []
        rows = []

        headers = 'children attributes \
        child_text_separator \
        resolved referenced indirect_reference_name \
        tagname'.split()

        for docname in env.found_docs:
            if env.temp_data['docname'] == docname:  # skip myself
                continue

            try:
                doc = env.get_doctree(docname)
            except Exception:
                # 20140117 i had the following after a fab clean:
                #   File "/home/luc/pythonenvs/py27/local/lib/python2.7/site-packages/sphinx/environment.py", line 1077, in get_doctree
                #     f = open(doctree_filename, 'rb')
                # IOError: [Errno 2] No such file or directory: u'/home/luc/hgwork/lino/docs/.build/.doctrees/topics/names.doctree'

                continue

            # print("20140115 traversing", docname)
            for ref in doc.traverse(addnodes.pending_xref):
                if ref['reftarget'] == target:
                    refdoc = ref['refdoc']
                    mtime = path.getmtime(env.doc2path(refdoc))
                    entries.append((mtime, refdoc))
                else:
                    row = []
                    for h in headers:
                        row.append(getattr(ref, h, 'N/A'))
                    rows.append(row)
    
        if len(entries) == 0:
            return """No documents found, but here is a list of all
            pending xrefs:
    
            """ + rstgen.table(headers, rows)
        
    
        def f(a, b):
            return cmp(a[0], b[0])
        entries.sort(f)
        entries.reverse()
    
        import time
        # from time import strftime
    
        items = [':doc:`/%(doc)s` (%(time)s)' % dict(
            time=time.ctime(e[0]),
            doc=e[1]) for e in entries]
    
        return rstgen.ul(items)
    

        # data = env.domains['std'].data
        # for k, v in data['labels'].items():
        #     docname, labelid, sectname = v
        #     if labelid == target:
        #         entries.append([k, docname, sectname])

        return "**%s** / %s" % (target, entries)


def setup(app):
    app.add_directive('refstothis', RefsToThis)
    app.add_directive('directory', DirectoryTable)
    app.add_directive('tickets_table', TicketsTable)
    app.add_directive('entry_intro', EntryIntro)
    # app.add_role(str('rref'), ReferingRefRole(
    #     lowercase=True,
    #     innernodeclass=nodes.emphasis,
    #     warn_dangling=True))

