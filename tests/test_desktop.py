"""Exercise real Tk event loop, asynchronous exports and settings isolation."""
from pathlib import Path
import sys
import tempfile
import time
import json
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'program'))
import corner_guard as g
from desktop_ui import App, HISTORY


def wait(root, condition):
    deadline=time.monotonic()+30
    while not condition():
        root.update()
        if time.monotonic()>deadline: raise AssertionError('GUI job timed out')
        time.sleep(.02)
    root.update()


with tempfile.TemporaryDirectory(prefix='cover-ui-') as directory:
    base=Path(directory)
    root=tk.Tk(); root.withdraw()
    root.report_callback_exception=lambda *args: (_ for _ in ()).throw(args[1])
    app=App(root,g,base/'settings.json')
    try:
        app.destination.set(str(base/'中文输出'))
        for index,(kind,_,_,_) in enumerate(app.types):
            app.select(index)
            wait(root,lambda:app.future is None and app.preview_revision==app.revision)
            assert app.view.mesh is not None
            before=app.last
            app.generate_button.invoke()
            wait(root,lambda:app.last!=before)
            report=json.loads((app.last/'parameters.json').read_text(encoding='utf-8'))
            assert report['type']==kind,report
            assert (app.last/'preview.html').exists()
            print('PASS desktop preview and export',kind)
        app.values['square']['side'].set('invalid')
        assert app.validation.get() and str(app.generate_button['state'])=='disabled'
        assert app.view.mesh is None
        app.select(1)
        wait(root,lambda:app.future is None and app.preview_revision==app.revision)
        assert not app.validation.get(), 'Hidden invalid fields block another type'
        app.select(6); app.defaults()
        wait(root,lambda:app.future is None and app.preview_revision==app.revision)
        app.show_history(); root.update()
        assert app.history.winfo_manager()=='pack'
        assert [v for v,_,_ in HISTORY]==['1.5.0','1.4.0','1.3.0','1.2.0','1.1.0','1.0.0']
        app.select(0); app.values['pcb']['arm'].set('27')
        # Changing types during a preview must not display an obsolete result.
        app.select(4); app.select(3)
        wait(root,lambda:app.future is None and app.preview_revision==app.revision)
        assert list(app.view.mesh.extents)==list(g.ClosedCoverParameters().extents)
        app.save()
    finally: app.close()
    root=tk.Tk(); root.withdraw(); restored=App(root,g,base/'settings.json')
    try:
        assert restored.values['pcb']['arm'].get()=='27'
        assert restored.destination.get()==str(base/'中文输出')
    finally: restored.close()
print('PASS validation, navigation, history, stale preview and settings persistence')
