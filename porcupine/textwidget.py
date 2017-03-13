# Copyright (c) 2017 Akuli

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The big text widget in the middle of the editor."""

import tkinter as tk


def spacecount(string):
    """Count how many spaces the string starts with.

    >>> spacecount('  123')
    2
    >>> spacecount('  \n')
    2
    """
    result = 0
    for char in string:
        if char == '\n' or not char.isspace():
            break
        result += 1
    return result


class EditorText(tk.Text):

    def __init__(self, master, settings, **kwargs):
        self._settings = settings
        self._cursorpos = '1.0'
        super().__init__(master, **kwargs)

        # These will contain callback functions that are called with no
        # arguments after the text in the textview is updated.
        self.on_cursor_move = []
        self.on_modified = []

        def cursor_move(event):
            self.after_idle(self._do_cursor_move)

        self.bind('<<Modified>>', self._do_modified)
        self.bind('<Button-1>', cursor_move)
        self.bind('<Key>', cursor_move)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', self._on_backspace)
        self.bind('<Return>', self._on_return)
        self.bind('<parenright>', self._on_closing_brace)
        self.bind('<bracketright>', self._on_closing_brace)
        self.bind('<braceright>', self._on_closing_brace)
        self.bind('<Tab>', lambda event: self._on_tab(False))

        if self.tk.call('tk', 'windowingsystem') == 'x11':
            # even though the event keysym says Left, holding down right
            # shift and pressing tab also runs this event... 0_o
            self.bind('<ISO_Left_Tab>', lambda event: self._on_tab(True))
        else:
            self.bind('<Shift-Tab>', lambda event: self._on_tab(True))

    def _do_modified(self, event):
        # this runs recursively if we don't unbind
        self.unbind('<<Modified>>')
        self.edit_modified(False)
        self.bind('<<Modified>>', self._do_modified)
        for callback in self.on_modified:
            callback()

    def _do_cursor_move(self):
        cursorpos = self.index('insert')
        if cursorpos != self._cursorpos:
            self._cursorpos = cursorpos
            for callback in self.on_cursor_move:
                callback()

    def _on_backspace(self, event):
        if not self.tag_ranges('sel'):
            # nothing is selected, we can do non-default stuff
            lineno = int(self.index('insert').split('.')[0])
            before_cursor = self.get('%d.0' % lineno, 'insert')
            if before_cursor and before_cursor.isspace():
                self.dedent(lineno)
                return 'break'

        self.after_idle(self._do_cursor_move)
        return None

    def _on_ctrl_a(self, event):
        """Select all."""
        self.tag_add('sel', '1.0', 'end-1c')
        return 'break'     # don't run _on_key or move cursor

    def _on_return(self, event):
        """Schedule automatic indent and whitespace stripping."""
        # the whitespace must be stripped after autoindenting,
        # see _autoindent()
        self.after_idle(self._autoindent)
        self.after_idle(self._strip_whitespace)
        self.after_idle(self._do_cursor_move)

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
            return True
        return False

    def _on_tab(self, shifted):
        """Indent, dedent or autocomplete."""
        if shifted:
            action = self.dedent
        else:
            action = self.indent

        try:
            sel_start, sel_end = map(str, self.tag_ranges('sel'))
        except ValueError:
            # no text is selected
            lineno = int(self.index('insert').split('.')[0])
            before_cursor = self.get('%d.0' % lineno, 'insert')
            if before_cursor.isspace() or not before_cursor:
                action(lineno)
            else:
                print("complete", "previous" if shifted else "next")
        else:
            # something selected, indent/dedent block
            first_lineno = int(sel_start.split('.')[0])
            last_lineno = int(sel_end.split('.')[0])
            for lineno in range(first_lineno, last_lineno+1):
                action(lineno)

        # indenting and autocomplete: don't insert the default tab
        # dedenting: don't move focus out of this widget
        return 'break'

    def indent(self, lineno):
        """Indent by one level.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0+1l' % lineno)
        spaces = spacecount(line)

        # make the indent consistent, for example, add 1 space
        # if self._settings['indent'] is 4 and there are 7 spaces
        indent = self._settings['indent']
        spaces2add = indent - (spaces % indent)
        self.insert('%d.0' % lineno, ' ' * spaces2add)
        self._do_cursor_move()
        return spaces + spaces2add

    def dedent(self, lineno):
        """Unindent by one level if possible.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0+1l' % lineno)
        spaces = spacecount(line)
        if spaces == 0:
            return 0
        howmany2del = spaces % self._settings['indent']
        if howmany2del == 0:
            howmany2del = self._settings['indent']
        self.delete('%d.0' % lineno, '%d.%d' % (lineno, howmany2del))
        self._do_cursor_move()
        return spaces - howmany2del

    def _autoindent(self):
        """Indent the current line automatically as needed."""
        lineno = int(self.index('insert').split('.')[0])
        prevline = self.get('%d.0-1l' % lineno, '%d.0' % lineno)
        # we can't strip trailing whitespace before this because then
        # pressing enter twice would get rid of all indentation
        if prevline.rstrip().endswith((':', '(', '[', '{')):
            # start of a new block
            self.indent(lineno)
        # a block continues
        self.insert('insert', spacecount(prevline) * ' ')

    def _strip_whitespace(self):
        """Strip whitespace after end of previous line."""
        lineno = int(self.index('insert').split('.')[0])
        line = self.get('%d.0-1l' % lineno, '%d.0-1c' % lineno)

        spaces = spacecount(line[::-1])
        if spaces == 0:
            return

        start = '{}.0-1c-{}c'.format(lineno, spaces)
        end = '{}.0-1c'.format(lineno)
        self.delete(start, end)

    def undo(self):
        try:
            self.edit_undo()
        except tk.TclError:     # nothing to undo
            return
        self._do_cursor_move()
        return 'break'

    def redo(self):
        try:
            self.edit_redo()
        except tk.TclError:     # nothing to redo
            return
        self._do_cursor_move()
        return 'break'

    def cut(self):
        self.event_generate('<<Cut>>')
        self._do_cursor_move()

    def copy(self):
        self.event_generate('<<Copy>>')
        self._do_cursor_move()

    def paste(self):
        self.event_generate('<<Paste>>')

        # Without this, pasting while some text is selected is annoying
        # because the selected text doesn't go away :(
        try:
            sel_start, sel_end = self.tag_ranges('sel')
        except ValueError:
            # nothing selected
            pass
        else:
            self.delete(sel_start, sel_end)

        self._do_cursor_move()