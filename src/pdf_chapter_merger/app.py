import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .processing import MergeTask


class MergerApp:
    def __init__(self, root):
        self.root, self.paths = root, []
        self.busy, self.last_output = False, None
        self.task = None
        root.protocol('WM_DELETE_WINDOW', self.close_window)
        root.title('PDF Chapter Merger')
        root.geometry('850x680')
        root.minsize(700, 480)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=9)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='One PDF. Clear chapters.', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Add PDFs, arrange their order, then merge. The app does not upload your files.').pack(anchor='w', pady=(8, 20))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x')
        for label, action in [('Add PDFs', self.add), ('Move up', lambda: self.move(-1)),
                              ('Move down', lambda: self.move(1)), ('Remove', self.remove)]:
            ttk.Button(toolbar, text=label, command=action).pack(side='left', padx=(0, 8))
        area = ttk.Frame(frame)
        area.pack(fill='both', expand=True, pady=12)
        self.listbox = tk.Listbox(area, font=('Segoe UI', 12), activestyle='none',
            relief='flat', borderwidth=10, selectbackground='#24566d', exportselection=False)
        scroll = ttk.Scrollbar(area, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.listbox.pack(side='left', fill='both', expand=True)
        self.titles = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text='Add a chapter title page before each file', variable=self.titles).pack(anchor='w')
        ttk.Label(frame, text='Chapter bookmarks always use the filenames without .pdf.').pack(anchor='w', pady=(4, 16))
        ttk.Label(frame, text='Scripts, attachments, forms, and other annotations are removed. Normal links are retained.\nEncrypted PDFs are rejected. Output PDFs are unencrypted.\nSave outside synced folders if you do not want OneDrive or backup tools to copy the result.',
                  wraplength=780).pack(anchor='w', pady=(0, 12))
        bottom = ttk.Frame(frame)
        bottom.pack(fill='x')
        self.merge_button = ttk.Button(bottom, text='Merge and save PDF', command=self.save)
        self.merge_button.pack(side='right')
        self.open_button = ttk.Button(bottom, text='Open result', command=self.open_result, state='disabled')
        self.open_button.pack(side='right', padx=8)
        self.cancel_button = ttk.Button(bottom, text='Cancel', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='right')
        self.status = tk.StringVar(value='Add PDFs to get started.')
        ttk.Label(bottom, textvariable=self.status).pack(side='left')

    def refresh(self, selected=None):
        self.listbox.delete(0, 'end')
        for index, path in enumerate(self.paths, 1):
            self.listbox.insert('end', f'{index:02d}    {path.stem}')
        if selected is not None:
            self.listbox.selection_set(selected)
            self.listbox.see(selected)
        self.status.set(f'{len(self.paths)} PDF(s) ready.')

    def add(self):
        if self.busy:
            return
        for filename in filedialog.askopenfilenames(title='Choose PDFs', filetypes=[('PDF files', '*.pdf')]):
            path = Path(filename)
            if path not in self.paths:
                self.paths.append(path)
        self.refresh()

    def move(self, direction):
        if self.busy or not self.listbox.curselection():
            return
        old = self.listbox.curselection()[0]
        new = old + direction
        if 0 <= new < len(self.paths):
            self.paths[old], self.paths[new] = self.paths[new], self.paths[old]
            self.refresh(new)

    def remove(self):
        if not self.busy and self.listbox.curselection():
            self.paths.pop(self.listbox.curselection()[0])
            self.refresh()

    def save(self):
        if self.busy:
            return
        if not self.paths:
            messagebox.showinfo('Add PDFs', 'Choose the PDFs you want to merge first.')
            return
        destination = filedialog.asksaveasfilename(title='Save merged PDF', defaultextension='.pdf',
            initialfile='Merged chapters.pdf', filetypes=[('PDF files', '*.pdf')])
        if not destination:
            return
        try:
            self.task = MergeTask(list(self.paths), destination, self.titles.get())
        except Exception as exc:
            messagebox.showerror('Could not start merge', str(exc))
            return
        self.busy = True
        self.merge_button.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Merging PDFs...')
        self.root.after(100, self.poll_task)

    def poll_task(self):
        if not self.task:
            return
        if not self.task.poll():
            self.root.after(100, self.poll_task)
            return
        destination = str(self.task.destination)
        try:
            pages = self.task.finish()
        except Exception as exc:
            self.finished(None, 0, str(exc))
        else:
            self.finished(destination, pages, None)
        finally:
            self.task.close()
            self.task = None

    def cancel(self):
        if self.task:
            self.task.cancel()
            self.task = None
        self.busy = False
        self.merge_button.configure(state='normal')
        self.cancel_button.configure(state='disabled')
        self.status.set('Cancelled. No output replaced.')

    def close_window(self):
        if self.task:
            self.task.cancel()
        self.root.destroy()

    def finished(self, destination, pages, error):
        self.busy = False
        self.merge_button.configure(state='normal')
        self.cancel_button.configure(state='disabled')
        if error:
            self.status.set('Merge failed.')
            messagebox.showerror('Could not merge PDFs', error)
        else:
            self.last_output = destination
            self.open_button.configure(state='normal')
            self.status.set(f'Saved. {pages} pages.')

    def open_result(self):
        if self.last_output:
            try:
                os.startfile(self.last_output)
            except OSError as exc:
                messagebox.showerror('Could not open PDF', str(exc))


def main():
    window = tk.Tk()
    MergerApp(window)
    window.mainloop()


if __name__ == '__main__':
    main()
