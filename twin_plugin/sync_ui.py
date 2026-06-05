# coding: utf-8
import time

import cerebro

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QLabel,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal

from .populate_cerebro_structure import fetch_children_branches, task_summary_light
from . import sync_settings
from . import sync_log
from .tracker_client import make_client_from_settings
from .tracker_structure import build_hierarchy, node_display_label
from .sync_engine import SyncRunner, collect_sync_jobs

_ITEM_DATA_USER_ROLE = (
    Qt.ItemDataRole.UserRole
    if hasattr(Qt, "ItemDataRole")
    else Qt.UserRole
)
_ITEM_NODE_TYPE_ROLE = (
    Qt.ItemDataRole.UserRole + 1
    if hasattr(Qt, "ItemDataRole")
    else Qt.UserRole + 1
)
_BASE_TITLE = "Tracker Sync"
_CEREBRO_TICK_MS = 1
_CEREBRO_TICK_BUDGET_S = 0.045
_CEREBRO_MAX_NODES_PER_TICK = 80


class MainThreadCerebroLoader(QObject):
    """BFS on main thread; branch nodes only, batched per timer tick."""

    nodes_batch_ready = pyqtSignal(object)
    loading_name = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._queue = []
        self._roots_done = False
        self._active = False
        self._nodes_loaded = 0
        self._parents_processed = 0
        self._names_by_id = {}

    def start(self):
        self._queue = []
        self._roots_done = False
        self._active = True
        self._nodes_loaded = 0
        self._parents_processed = 0
        self._names_by_id = {}
        self._log_scan("Cerebro scan started…")
        self._timer.start(_CEREBRO_TICK_MS)

    def _log_scan(self, message):
        sync_log.log(message)

    def stop(self):
        self._active = False
        self._timer.stop()

    def _schedule_next(self):
        if self._active:
            self._timer.start(_CEREBRO_TICK_MS)

    def _tick(self):
        if not self._active:
            return
        try:
            if not self._roots_done:
                self._load_roots()
                self._schedule_next()
                return

            batch = []
            deadline = time.perf_counter() + _CEREBRO_TICK_BUDGET_S
            parents_this_tick = 0
            while self._queue and len(batch) < _CEREBRO_MAX_NODES_PER_TICK:
                parent_id = self._queue.pop(0)
                parent_label = self._names_by_id.get(parent_id, "#%s" % parent_id)
                queued_after = len(self._queue)
                self._log_scan(
                    "Cerebro: fetching «%s» (%d queued, %d branches loaded)"
                    % (parent_label, queued_after, self._nodes_loaded)
                )
                children = fetch_children_branches(parent_id)
                parents_this_tick += 1
                for child in children:
                    self._names_by_id[child["id"]] = child["name"]
                    batch.append((parent_id, child))
                    if child["has_children"]:
                        self._queue.append(child["id"])
                self._log_scan(
                    "Cerebro: «%s» → %d branch(es), %d still queued"
                    % (parent_label, len(children), len(self._queue))
                )
                if time.perf_counter() >= deadline:
                    break

            if batch:
                self._nodes_loaded += len(batch)
                self._parents_processed += parents_this_tick
                self.nodes_batch_ready.emit(batch)
                self.loading_name.emit(batch[-1][1]["name"])
            elif not self._queue:
                self._active = False
                self._log_scan(
                    "Cerebro scan done: %d branches from %d parents"
                    % (self._nodes_loaded, self._parents_processed)
                )
                self.finished.emit()
                return
        except Exception as e:
            self._active = False
            self.error.emit(str(e))
            return
        self._schedule_next()

    def _load_roots(self):
        roots = []
        for proj in cerebro.core.root_tasks():
            node = task_summary_light(proj, node_type="project")
            roots.append((None, node))
            if node["has_children"]:
                self._queue.append(node["id"])
        if roots:
            for _pid, node in roots:
                self._names_by_id[node["id"]] = node["name"]
            self._nodes_loaded += len(roots)
            self.nodes_batch_ready.emit(roots)
            self.loading_name.emit(roots[-1][1]["name"])
            self._log_scan(
                "Cerebro: %d root project(s), %d parent(s) queued"
                % (len(roots), len(self._queue))
            )
        else:
            self._log_scan("Cerebro: no root projects found")
        self._roots_done = True


class MainThreadTrackerLoader(QObject):
    """Load Tracker hierarchy on main thread, one node per tick."""

    node_ready = pyqtSignal(object, object)
    loading_name = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._flat = []
        self._index = 0
        self._active = False

    def start(self):
        self._flat = []
        self._index = 0
        self._active = True
        self._timer.start(0)

    def stop(self):
        self._active = False
        self._timer.stop()

    def _tick(self):
        if not self._active:
            return
        try:
            if not self._flat:
                hierarchy = build_hierarchy(self._client)
                self._flat = self._flatten_hierarchy(hierarchy)
                self._index = 0
            if self._index >= len(self._flat):
                self._active = False
                self.finished.emit()
                return
            parent_id, node = self._flat[self._index]
            self._index += 1
            name = node.get("name") or node.get("key") or "?"
            self.loading_name.emit(name)
            self.node_ready.emit(parent_id, node)
        except Exception as e:
            self._active = False
            self.error.emit(str(e))
            return
        self._timer.start(0)

    def _flatten_hierarchy(self, nodes, parent_id=None, out=None):
        if out is None:
            out = []
        for node in nodes:
            out.append((parent_id, node))
            children = node.get("children") or []
            nid = node.get("id") or node.get("key")
            self._flatten_hierarchy(children, nid, out)
        return out


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Tracker Settings")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        settings = settings or sync_settings.load()

        layout = QFormLayout()
        self.token_input = QLineEdit()
        self.token_input.setText(settings.get("tracker_token", ""))
        self.cloud_org_input = QLineEdit()
        self.cloud_org_input.setText(settings.get("tracker_cloud_org_id", ""))
        self.portfolio_id_input = QLineEdit()
        self.portfolio_id_input.setText(settings.get("parent_portfolio_id", ""))

        layout.addRow("TRACKER_TOKEN:", self.token_input)
        layout.addRow("TRACKER_CLOUD_ORG_ID:", self.cloud_org_input)
        layout.addRow("PARENT_PORTFOLIO_ID:", self.portfolio_id_input)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        layout.addRow(self.save_button)
        self.setLayout(layout)

    def get_values(self):
        return {
            "tracker_token": self.token_input.text().strip(),
            "tracker_cloud_org_id": self.cloud_org_input.text().strip(),
            "parent_portfolio_id": self.portfolio_id_input.text().strip(),
        }


def sync_ui():
    class SyncDialog(QDialog):
        def __init__(self, parent=None):
            super(SyncDialog, self).__init__(parent)
            self.setWindowTitle(_BASE_TITLE)
            self.setWindowModality(Qt.WindowModality.ApplicationModal)

            self._settings = sync_settings.load()
            self._items_by_id = {}
            self._nodes_by_id = {}
            self._tracker_items_by_id = {}
            self._tracker_nodes_by_id = {}
            self._root_ids = set()
            self._cerebro_title_counter = 0
            self._restoring_tracker_selection = False
            self._cerebro_loader = None
            self._tracker_loader = None
            self._sync_runner = None
            self._cerebro_load_done = False
            self._tracker_load_done = False
            self._restoring_checks = False
            self._loading_side = None

            main_layout = QVBoxLayout()

            self.settings_button = QPushButton("Settings...")
            self.settings_button.clicked.connect(self.open_settings)
            main_layout.addWidget(self.settings_button)

            sync_layout = QHBoxLayout()

            self.left_tree = QTreeWidget()
            self.left_tree.setHeaderLabel("Cerebro Structure")
            self.left_tree.itemChanged.connect(self._on_left_item_changed)

            self.sync_button = QPushButton("Sync")
            self.sync_button.setEnabled(False)
            self.sync_button.clicked.connect(self.do_sync)

            self.right_tree = QTreeWidget()
            self.right_tree.setHeaderLabel("Tracker Structure")
            self.right_tree.currentItemChanged.connect(
                self._on_tracker_current_changed
            )

            sync_layout.addWidget(self.left_tree)
            sync_layout.addWidget(self.sync_button)
            sync_layout.addWidget(self.right_tree)

            main_layout.addLayout(sync_layout)

            sync_settings.ensure_config_files()
            self.log_path_label = QLabel(
                "Settings file: %s\nStatus map file: %s\nActivity log file: %s"
                % (
                    sync_settings.get_settings_path(),
                    sync_settings.get_status_map_path(),
                    sync_log.get_activity_log_path(),
                )
            )
            self.log_path_label.setWordWrap(True)
            main_layout.addWidget(self.log_path_label)

            self.activity_log = QTextEdit()
            self.activity_log.setReadOnly(True)
            self.activity_log.setMaximumHeight(120)
            self.activity_log.setPlaceholderText("Scan and sync messages appear here…")
            main_layout.addWidget(self.activity_log)

            sync_log.set_ui_callback(self._append_activity_log)
            sync_log.log("Tracker Sync opened")
            sync_log.log("Settings file: %s" % sync_settings.get_settings_path())
            sync_log.log(
                "Status map file: %s" % sync_settings.get_status_map_path()
            )

            self.setLayout(main_layout)

            if not sync_settings.has_tracker_credentials(self._settings):
                QMessageBox.warning(
                    self,
                    "Tracker credentials",
                    "Configure TRACKER_TOKEN and TRACKER_CLOUD_ORG_ID in Settings "
                    "to load the Tracker structure.",
                )
                self._tracker_load_done = True
            else:
                self._start_tracker_load()

            self._start_cerebro_load()

        def _append_activity_log(self, line):
            self.activity_log.append(line)
            bar = self.activity_log.verticalScrollBar()
            bar.setValue(bar.maximum())
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

        def _update_title_loading(self, name, side):
            self.setWindowTitle("%s — loading %s (%s)" % (_BASE_TITLE, name, side))

        def _update_title_idle(self):
            if self._cerebro_load_done and self._tracker_load_done:
                self.setWindowTitle(_BASE_TITLE)
                self._update_sync_enabled()

        def _update_sync_enabled(self):
            has_checks = bool(self._collect_checked_ids())
            has_creds = sync_settings.has_tracker_credentials(self._settings)
            self.sync_button.setEnabled(
                self._cerebro_load_done and has_checks and has_creds
            )

        def _start_cerebro_load(self):
            self._stop_cerebro_load()
            self.left_tree.clear()
            self._items_by_id.clear()
            self._nodes_by_id.clear()
            self._root_ids.clear()
            self._cerebro_load_done = False
            self._cerebro_title_counter = 0

            loading = QTreeWidgetItem(["Loading Cerebro structure..."])
            self.left_tree.addTopLevelItem(loading)

            self._cerebro_loader = MainThreadCerebroLoader(self)
            self._cerebro_loader.nodes_batch_ready.connect(self._on_cerebro_batch)
            self._cerebro_loader.loading_name.connect(self._on_cerebro_loading_name)
            self._cerebro_loader.finished.connect(self._on_cerebro_finished)
            self._cerebro_loader.error.connect(self._on_cerebro_error)
            self._cerebro_loader.start()

        def _start_tracker_load(self):
            self._stop_tracker_load()
            self.right_tree.clear()
            self._tracker_items_by_id.clear()
            self._tracker_nodes_by_id.clear()
            self._tracker_load_done = False

            client, err = make_client_from_settings(self._settings)
            if err:
                self._tracker_load_done = True
                item = QTreeWidgetItem(["Tracker: %s" % err])
                self.right_tree.addTopLevelItem(item)
                self._update_title_idle()
                return

            loading = QTreeWidgetItem(["Loading Tracker structure..."])
            self.right_tree.addTopLevelItem(loading)

            self._tracker_loader = MainThreadTrackerLoader(client, self)
            self._tracker_loader.node_ready.connect(self._on_tracker_node)
            self._tracker_loader.loading_name.connect(
                lambda n: self._update_title_loading(n, "Tracker")
            )
            self._tracker_loader.finished.connect(self._on_tracker_finished)
            self._tracker_loader.error.connect(self._on_tracker_error)
            self._tracker_loader.start()

        def _stop_cerebro_load(self):
            if self._cerebro_loader:
                self._cerebro_loader.stop()

        def _stop_tracker_load(self):
            if self._tracker_loader:
                self._tracker_loader.stop()

        def _stop_sync(self):
            if self._sync_runner:
                self._sync_runner.stop()
                self._sync_runner = None

        def _remove_loading_placeholder(self, tree):
            if tree.topLevelItemCount() == 1:
                top = tree.topLevelItem(0)
                if top and top.data(0, _ITEM_DATA_USER_ROLE) is None:
                    idx = tree.indexOfTopLevelItem(top)
                    if idx >= 0:
                        tree.takeTopLevelItem(idx)

        def _on_cerebro_loading_name(self, name):
            self._cerebro_title_counter += 1
            if self._cerebro_title_counter % 5 == 1:
                self._update_title_loading(name, "Cerebro")

        def _append_cerebro_node(self, parent_id, node):
            item = QTreeWidgetItem([node["name"]])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, _ITEM_DATA_USER_ROLE, node["id"])

            node_entry = dict(node)
            node_entry["cerebro_parent_id"] = parent_id
            self._nodes_by_id[node["id"]] = node_entry

            if parent_id is None:
                self.left_tree.addTopLevelItem(item)
                self._root_ids.add(node["id"])
            else:
                parent_item = self._items_by_id.get(parent_id)
                if parent_item:
                    parent_item.addChild(item)

            self._items_by_id[node["id"]] = item

        def _on_cerebro_batch(self, batch):
            self._remove_loading_placeholder(self.left_tree)
            self.left_tree.setUpdatesEnabled(False)
            try:
                for parent_id, node in batch:
                    self._append_cerebro_node(parent_id, node)
            finally:
                self.left_tree.setUpdatesEnabled(True)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

        def _on_cerebro_finished(self):
            self._remove_loading_placeholder(self.left_tree)
            self._cerebro_load_done = True
            self._restore_checked_items()
            self._update_title_idle()

        def _on_cerebro_error(self, message):
            self._remove_loading_placeholder(self.left_tree)
            self.left_tree.addTopLevelItem(QTreeWidgetItem(["Error: %s" % message]))
            self._cerebro_load_done = True
            sync_log.log("Cerebro structure load error: %s" % message)
            self._update_title_idle()

        def _tracker_node_id(self, node):
            return node.get("id") or node.get("key")

        def _on_tracker_node(self, parent_id, node):
            self._remove_loading_placeholder(self.right_tree)
            label = node_display_label(node)
            item = QTreeWidgetItem([label])
            nid = self._tracker_node_id(node)
            item.setData(0, _ITEM_DATA_USER_ROLE, nid)
            item.setData(0, _ITEM_NODE_TYPE_ROLE, node.get("nodeType"))

            if parent_id is None:
                self.right_tree.addTopLevelItem(item)
            else:
                parent_item = self._tracker_items_by_id.get(str(parent_id))
                if parent_item:
                    parent_item.addChild(item)

            if nid is not None:
                sid = str(nid)
                self._tracker_items_by_id[sid] = item
                self._tracker_nodes_by_id[sid] = node

        def _on_tracker_current_changed(self, current, _previous):
            if self._restoring_tracker_selection or current is None:
                return
            ntype = current.data(0, _ITEM_NODE_TYPE_ROLE)
            if ntype != "portfolio":
                return
            nid = current.data(0, _ITEM_DATA_USER_ROLE)
            if nid is None:
                return
            node = self._tracker_nodes_by_id.get(str(nid), {})
            short_id = node.get("shortId")
            portfolio_ref = (
                str(short_id) if short_id is not None else str(nid)
            )
            self._settings["selected_tracker_portfolio_id"] = str(nid)
            self._settings["parent_portfolio_id"] = portfolio_ref
            sync_settings.save(self._settings)

        def _restore_tracker_selection(self):
            saved_id = (
                self._settings.get("selected_tracker_portfolio_id") or ""
            ).strip()
            if not saved_id:
                pref = (self._settings.get("parent_portfolio_id") or "").strip()
                if pref:
                    for nid, node in self._tracker_nodes_by_id.items():
                        if node.get("nodeType") != "portfolio":
                            continue
                        if str(node.get("shortId")) == pref or str(nid) == pref:
                            saved_id = nid
                            break
            if not saved_id:
                return
            item = self._tracker_items_by_id.get(saved_id)
            if item is None:
                return
            parent = item.parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()
            self._restoring_tracker_selection = True
            self.right_tree.setCurrentItem(item)
            self.right_tree.scrollToItem(item)
            self._restoring_tracker_selection = False

        def _on_tracker_finished(self):
            self._remove_loading_placeholder(self.right_tree)
            self._tracker_load_done = True
            self._restore_tracker_selection()
            self._update_title_idle()

        def _on_tracker_error(self, message):
            self._remove_loading_placeholder(self.right_tree)
            self.right_tree.addTopLevelItem(QTreeWidgetItem(["Error: %s" % message]))
            self._tracker_load_done = True
            sync_log.log("Tracker structure load error: %s" % message)
            self._update_title_idle()

        def _restore_checked_items(self):
            saved = set(self._settings.get("checked_cerebro_task_ids") or [])
            if not saved:
                return
            self._restoring_checks = True
            self.left_tree.blockSignals(True)

            def walk(item):
                tid = item.data(0, _ITEM_DATA_USER_ROLE)
                if tid in saved:
                    item.setCheckState(0, Qt.CheckState.Checked)
                for i in range(item.childCount()):
                    walk(item.child(i))

            for i in range(self.left_tree.topLevelItemCount()):
                walk(self.left_tree.topLevelItem(i))

            self.left_tree.blockSignals(False)
            self._restoring_checks = False

        def _on_left_item_changed(self, item, column):
            if self._restoring_checks or column != 0:
                return
            state = item.checkState(0)
            self._restoring_checks = True
            self.left_tree.blockSignals(True)
            self._set_children_check_state(item, state)
            self.left_tree.blockSignals(False)
            self._restoring_checks = False
            self._update_sync_enabled()

        def _set_children_check_state(self, item, state):
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, state)
                self._set_children_check_state(child, state)

        def _collect_checked_ids(self):
            ids = []

            def walk(item):
                if item.checkState(0) == Qt.CheckState.Checked:
                    tid = item.data(0, _ITEM_DATA_USER_ROLE)
                    if tid is not None:
                        ids.append(tid)
                for i in range(item.childCount()):
                    walk(item.child(i))

            for i in range(self.left_tree.topLevelItemCount()):
                walk(self.left_tree.topLevelItem(i))
            return ids

        def _collect_checked_nodes(self):
            """Only explicitly checked items in the tree (no hidden leaf level)."""
            ids = set(self._collect_checked_ids())
            return [self._nodes_by_id[i] for i in ids if i in self._nodes_by_id]

        def _persist_settings(self):
            self._settings["checked_cerebro_task_ids"] = self._collect_checked_ids()
            sync_settings.save(self._settings)

        def open_settings(self):
            dlg = SettingsDialog(self, self._settings)
            if dlg.exec():
                values = dlg.get_values()
                self._settings.update(values)
                sync_settings.save(self._settings)
                if sync_settings.has_tracker_credentials(self._settings):
                    self._start_tracker_load()
                self._update_sync_enabled()

        def do_sync(self):
            checked = self._collect_checked_nodes()
            if not checked:
                QMessageBox.warning(self, "Sync", "Select at least one Cerebro item.")
                return
            if not sync_settings.has_tracker_credentials(self._settings):
                QMessageBox.warning(
                    self,
                    "Sync",
                    "Configure TRACKER_TOKEN and TRACKER_CLOUD_ORG_ID in Settings.",
                )
                return
            if not (self._settings.get("parent_portfolio_id") or "").strip():
                QMessageBox.warning(
                    self,
                    "Sync",
                    "Set PARENT_PORTFOLIO_ID in Settings (target portfolio for new projects).",
                )
                return

            jobs = collect_sync_jobs(checked, self._nodes_by_id, self._root_ids)
            issue_count = sum(1 for j in jobs if j["kind"] == "issue")
            if issue_count == 0 and not any(j["kind"] == "project" for j in jobs):
                QMessageBox.information(
                    self,
                    "Sync",
                    "Nothing to sync. Check branch items in the Cerebro tree "
                    "(leaf tasks are not synced).",
                )
                return
            confirm = QMessageBox.question(
                self,
                "Confirm sync",
                "Sync %d Tracker task(s) from checked Cerebro items?\n"
                "(Hidden leaf tasks such as rig/layout are excluded.)" % issue_count,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            self.sync_button.setEnabled(False)
            self._sync_runner = SyncRunner(
                self._settings,
                jobs,
                self._nodes_by_id,
                self._root_ids,
                self,
            )
            self._sync_runner.progress.connect(self._on_sync_progress)
            self._sync_runner.finished.connect(self._on_sync_finished)
            self._sync_runner.error.connect(self._on_sync_error)
            self._sync_runner.start()

        def _on_sync_progress(self, msg):
            self.setWindowTitle("%s — %s" % (_BASE_TITLE, msg))
            sync_log.log(msg)

        def _on_sync_finished(self, stats):
            self.setWindowTitle(_BASE_TITLE)
            self._sync_runner = None
            self._settings = sync_settings.load()
            self._update_sync_enabled()
            total_links = len(self._settings.get("task_map") or {})
            msg = (
                "Sync complete.\n"
                "Projects created: %(projects)s\n"
                "Issues created: %(issues_created)s\n"
                "Issues updated: %(issues_updated)s\n"
                "Dependency links created: %(dependencies_created)s\n"
                "Links updated this run: %(links_updated)s\n"
                "Total links in settings: %(total_links)s"
            ) % dict(stats, total_links=total_links)
            if stats.get("errors"):
                msg += "\n\nErrors:\n" + "\n".join(stats["errors"][:10])
            sync_log.log(msg.replace("\n", " | "))
            QMessageBox.information(self, "Sync", msg)

        def _on_sync_error(self, message):
            self.setWindowTitle(_BASE_TITLE)
            self._sync_runner = None
            self._update_sync_enabled()
            sync_log.log("Sync error: %s" % message)
            QMessageBox.critical(self, "Sync error", message)

        def closeEvent(self, event):
            sync_log.clear_ui_callback()
            self._persist_settings()
            self._stop_cerebro_load()
            self._stop_tracker_load()
            self._stop_sync()
            super().closeEvent(event)

    dialog = SyncDialog()
    dialog.show()
    global _sync_dialog
    _sync_dialog = dialog
