# plugins/lua_debugger.py
"""
Lua Debugger Plugin for NeoPyxel
Provides a visual debugger for Lua scripts with breakpoints, call stack, variable inspection, and interactive console.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter, QLabel,
    QLineEdit, QDockWidget, QMenu, QMessageBox
)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QColor

class LuaDebuggerPlugin(QDockWidget):
    """Main debugger dock widget"""

    def __init__(self, editor):
        super().__init__("Lua Debugger", editor)
        self.editor = editor
        self.setObjectName("LuaDebugger")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)

        # Access debugger API from editor's script bridge
        self.debugger_api = None
        if hasattr(editor, 'script_bridge') and hasattr(editor.script_bridge, 'debugger'):
            self.debugger_api = editor.script_bridge.debugger
        else:
            self.setWidget(QLabel("Debugger API not available in this version of NeoPyxel."))
            return

        # UI setup
        main_widget = QWidget()
        self.setWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(2, 2, 2, 2)

        # Control buttons
        btn_layout = QHBoxLayout()
        self.btn_continue = QPushButton("▶ Continue")
        self.btn_step_over = QPushButton("↷ Step Over")
        self.btn_step_into = QPushButton("⇣ Step Into")
        self.btn_step_out = QPushButton("⇡ Step Out")
        self.btn_stop = QPushButton("■ Stop")

        for btn in [self.btn_continue, self.btn_step_over, self.btn_step_into, self.btn_step_out, self.btn_stop]:
            btn_layout.addWidget(btn)
            btn.setEnabled(False)

        layout.addLayout(btn_layout)

        # Splitter for stack/variables/breakpoints
        splitter = QSplitter(Qt.Vertical)

        # Call stack widget
        stack_widget = QWidget()
        stack_layout = QVBoxLayout(stack_widget)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(QLabel("Call Stack:"))
        self.stack_list = QListWidget()
        self.stack_list.setFont(QFont("Courier New", 10))
        stack_layout.addWidget(self.stack_list)
        splitter.addWidget(stack_widget)

        # Variables tree
        var_widget = QWidget()
        var_layout = QVBoxLayout(var_widget)
        var_layout.setContentsMargins(0, 0, 0, 0)
        var_layout.addWidget(QLabel("Variables:"))
        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderLabels(["Name", "Value"])
        self.var_tree.setFont(QFont("Courier New", 10))
        var_layout.addWidget(self.var_tree)
        splitter.addWidget(var_widget)

        # Breakpoints list
        bp_widget = QWidget()
        bp_layout = QVBoxLayout(bp_widget)
        bp_layout.setContentsMargins(0, 0, 0, 0)
        bp_layout.addWidget(QLabel("Breakpoints:"))
        self.bp_list = QListWidget()
        self.bp_list.setFont(QFont("Courier New", 10))
        self.bp_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bp_list.customContextMenuRequested.connect(self.show_breakpoint_context_menu)
        bp_layout.addWidget(self.bp_list)
        splitter.addWidget(bp_widget)

        layout.addWidget(splitter, 3)  # 3 = stretch factor

        # Lua console
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.addWidget(QLabel("Lua Console:"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier New", 10))
        console_layout.addWidget(self.console_output)

        input_layout = QHBoxLayout()
        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Enter Lua expression...")
        self.console_input.returnPressed.connect(self.evaluate_console)
        self.btn_eval = QPushButton("Evaluate")
        self.btn_eval.clicked.connect(self.evaluate_console)
        input_layout.addWidget(self.console_input)
        input_layout.addWidget(self.btn_eval)
        console_layout.addLayout(input_layout)

        layout.addWidget(console_widget, 1)  # 1 = stretch factor

        # Connect button signals
        self.btn_continue.clicked.connect(self.cmd_continue)
        self.btn_step_over.clicked.connect(self.cmd_step_over)
        self.btn_step_into.clicked.connect(self.cmd_step_into)
        self.btn_step_out.clicked.connect(self.cmd_step_out)
        self.btn_stop.clicked.connect(self.cmd_stop)

        # Debugger state
        self.is_paused = False
        self.current_stack = []

        # Attach to debugger API
        try:
            self.debugger_api.attach(self)
        except Exception as e:
            QMessageBox.warning(self, "Debugger Error", f"Failed to attach to debugger: {e}")

    # ----------------------------------------------------------------------
    # Callbacks from debugger API (called by script_bridge.debugger)
    # ----------------------------------------------------------------------
    def on_pause(self, reason, stack, locals, upvalues, env):
        """Called when execution pauses (breakpoint, step, etc.)"""
        self.is_paused = True
        self.current_stack = stack
        self._update_ui_on_pause(stack, locals, upvalues, env)
        self._enable_buttons(True)
        self.console_output.append(f"Paused: {reason}")

    def on_continue(self):
        """Called when execution resumes"""
        self.is_paused = False
        self._enable_buttons(False)
        self._clear_ui()
        self.console_output.append("Continued...")

    def on_stop(self):
        """Called when debugging ends"""
        self.is_paused = False
        self._enable_buttons(False)
        self._clear_ui()
        self.console_output.append("Debugging stopped.")

    # ----------------------------------------------------------------------
    # Command handlers
    # ----------------------------------------------------------------------
    def cmd_continue(self):
        if self.is_paused:
            try:
                self.debugger_api.do_continue()
            except Exception as e:
                self.console_output.append(f"Error: {e}")

    def cmd_step_over(self):
        if self.is_paused:
            try:
                self.debugger_api.step_over()
            except Exception as e:
                self.console_output.append(f"Error: {e}")

    def cmd_step_into(self):
        if self.is_paused:
            try:
                self.debugger_api.step_into()
            except Exception as e:
                self.console_output.append(f"Error: {e}")

    def cmd_step_out(self):
        if self.is_paused:
            try:
                self.debugger_api.step_out()
            except Exception as e:
                self.console_output.append(f"Error: {e}")

    def cmd_stop(self):
        if self.is_paused:
            try:
                self.debugger_api.stop_debugging()
            except Exception as e:
                self.console_output.append(f"Error: {e}")

    # ----------------------------------------------------------------------
    # Console evaluation
    # ----------------------------------------------------------------------
    def evaluate_console(self):
        expr = self.console_input.text().strip()
        if not expr:
            return
        self.console_input.clear()
        if not self.is_paused:
            self.console_output.append("Cannot evaluate: debugger is not paused.")
            return

        try:
            result = self.debugger_api.evaluate(expr)
            self.console_output.append(f">>> {expr}")
            self.console_output.append(str(result))
        except Exception as e:
            self.console_output.append(f"Error: {e}")

    # ----------------------------------------------------------------------
    # Breakpoint management
    # ----------------------------------------------------------------------
    def add_breakpoint(self, file, line):
        """Add a breakpoint (call this from editor integration)"""
        try:
            self.debugger_api.set_breakpoint(file, line)
            self.bp_list.addItem(f"{file}:{line}")
        except Exception as e:
            QMessageBox.warning(self, "Breakpoint Error", str(e))

    def remove_breakpoint(self, item):
        """Remove a breakpoint given its list item"""
        text = item.text()
        try:
            file, line_str = text.rsplit(':', 1)
            line = int(line_str)
            self.debugger_api.clear_breakpoint(file, line)
            self.bp_list.takeItem(self.bp_list.row(item))
        except Exception as e:
            QMessageBox.warning(self, "Breakpoint Error", str(e))

    def show_breakpoint_context_menu(self, pos: QPoint):
        """Show context menu for breakpoint list"""
        item = self.bp_list.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        remove_action = menu.addAction("Remove breakpoint")
        action = menu.exec_(self.bp_list.mapToGlobal(pos))
        if action == remove_action:
            self.remove_breakpoint(item)

    # ----------------------------------------------------------------------
    # UI helpers
    # ----------------------------------------------------------------------
    def _enable_buttons(self, enabled):
        self.btn_continue.setEnabled(enabled)
        self.btn_step_over.setEnabled(enabled)
        self.btn_step_into.setEnabled(enabled)
        self.btn_step_out.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)

    def _clear_ui(self):
        self.stack_list.clear()
        self.var_tree.clear()

    def _update_ui_on_pause(self, stack, locals, upvalues, env):
        self.stack_list.clear()
        for level, frame in enumerate(stack):
            name = frame.get('name', '<anonymous>')
            file = frame.get('file', '?')
            line = frame.get('line', '?')
            self.stack_list.addItem(f"{level}: {name} at {file}:{line}")

        self.var_tree.clear()
        # Locals
        if locals:
            local_item = QTreeWidgetItem(["Locals", ""])
            for name, value in locals.items():
                child = QTreeWidgetItem([name, str(value)[:80]])
                local_item.addChild(child)
            self.var_tree.addTopLevelItem(local_item)

        # Upvalues
        if upvalues:
            up_item = QTreeWidgetItem(["Upvalues", ""])
            for name, value in upvalues.items():
                child = QTreeWidgetItem([name, str(value)[:80]])
                up_item.addChild(child)
            self.var_tree.addTopLevelItem(up_item)

        # Globals (environment)
        if env:
            env_item = QTreeWidgetItem(["Globals", ""])
            count = 0
            for name, value in env.items():
                if count < 100:  # limit to avoid slowdown
                    child = QTreeWidgetItem([name, str(value)[:80]])
                    env_item.addChild(child)
                count += 1
            if count >= 100:
                child = QTreeWidgetItem(["...", f"and {count-100} more"])
                env_item.addChild(child)
            self.var_tree.addTopLevelItem(env_item)

        self.var_tree.expandAll()

    # ----------------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------------
    def closeEvent(self, event):
        """Detach debugger when dock is closed"""
        if self.debugger_api:
            try:
                self.debugger_api.detach(self)
            except:
                pass
        event.accept()


def setup(editor):
    """
    Entry point called by NeoPyxel plugin manager.
    Returns the plugin instance or None if requirements not met.
    """
    # Create and add dock widget
    debugger = LuaDebuggerPlugin(editor)

    # Try to add to editor using standard QMainWindow method
    if hasattr(editor, 'addDockWidget'):
        editor.addDockWidget(Qt.RightDockWidgetArea, debugger)
    elif hasattr(editor, 'add_dock_widget'):  # fallback to custom method
        editor.add_dock_widget("Lua Debugger", debugger)
    else:
        # If all else fails, just show it as a floating window
        debugger.setFloating(True)
        debugger.show()

    return debugger
