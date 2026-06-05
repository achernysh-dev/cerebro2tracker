# -*- coding: utf-8 -*-
"""
Manipulate Mirada playlists

.. rubric:: Classes

* :py:class:`pycerebro.vista.Vista`

"""

import os
import sys
import time
import tempfile
import shutil
import sqlite3
import struct
import json
import base64

# ===============================================
# ============== PLAYLIST HELPERS ===============
# ===============================================


class ListaBase(object):
	def dict(self):
		old = self.__dict__
		res = {}
		for key in old.keys():
			if key[0] == '_':
				target_key = key[1:]
			else:
				target_key = key
			if self._allowed(key, target_key):
				res[target_key] = old[key]
		for key in self._db_attributes:
			res[key] = self._get(key)
		return res

	def from_dict(self, dic):
		for key in dic.keys():
			if key == 'id':
				continue
			setattr(self, key, dic[key])

	# to check is list of attributes allowed to convert
	def _allowed(self, *args):
		return all(list(not k in self._restricted_attributes for k in args))

	def attrs(self):
		return self.dict().keys()

	def __init__(self, tableClass, vista, execute_method, id):
		self._special_attributes = ['_db_attributes', '_special_getters',
			'_special_setters', '_table_names', '_defaults', '_id',
			'_restricted_attributes', '_vista', '_table', '_tableClass',
			'_execute', '_special_attributes']
		self._db_attributes = []
		self._restricted_attributes = []
		# this dict defines which attributes have special methods
		# for example: if we change ListaFile's "id" we have to
		# redefine "file_id" of his children in ListaFile.get_versions()
		# keys - attributes
		# values - lambda functions
		self._special_getters = {}
		self._special_setters = {}
		# keys of table_names - it's names of class attributes,
		# values - names of them in table
		self._table_names = {}

		# this dict helps save given values before db creation
		self._defaults = {}

		self._restricted_attributes.extend([
			'_vista',
			'_db_attributes',
			'_restricted_attributes',
			'_table',
			'_tableClass',
			'_execute',
			'_table_names',
			'_defaults',
			'_special_setters',
			'_special_getters',
			'_special_attributes'
		])
		# table means t_users, t_answers etc
		self._tableClass = tableClass
		self._vista = vista
		self._table = self._tableClass(self._vista.VERSION)
		self._execute = execute_method
		self.id = id

	def apply_defaults(self):
		# separated list created to avoid
		# resizing error in loop
		keys = list(self._defaults.keys())
		for key in keys:
			if getattr(self, key) == '':
				setattr(self, key, self._defaults[key])
			del self._defaults[key]

	def _check_vista(self):
		if not self._vista:
			raise Exception('No vista for {} with id {}'.format(type(self), self.id))

	# this function made to get attribute name in table and in class
	def _get_table_name(self, attr):
		if attr in self._table_names.keys():
			return self._table_names[attr]
		else:
			return attr

	def _update(self, values={}):
		keys = list(values.keys())
		for key in keys:
			if key in self._defaults.keys():
				self._defaults[key] = values[key]
				del values[key]
		if len(values.keys()) != 0:
			self._check_vista()
			version = self._vista.VERSION

			up_query = self._table.update('id', self.id,
				list(self._get_table_name(key) for key in values.keys()),
				version)
			self._execute(up_query, tuple(values.values()))

	def _get(self, attribute):
		if attribute in self._defaults.keys():
			return self._defaults[attribute]
		attribute = self._get_table_name(attribute)
		self._check_vista()
		version = self._vista.VERSION

		sel_query = self._table.select(version, where={'id': self._id})
		sel_query = sel_query.replace('*', attribute, 1)
		res = self._execute(sel_query, [])
		if len(res) > 0:
			res = res[0]
			return res[0]
		else:
			return None

	def __setattr__(self, attr, value):
		if attr == '_special_attributes' or attr in self._special_attributes:
			self.__dict__[attr] = value
		elif attr in self._defaults.keys():
			self._defaults[attr] = value
		elif attr in self._db_attributes:
			self._update({attr: value})
		elif attr in self._special_setters.keys():
			self._special_setters[attr](self, value)
		elif attr == 'id' or attr == '_id':
			self.__dict__['_id'] = value

	def __getattr__(self, attr):
		if attr == '_special_attributes' or attr in self._special_attributes:
			result = self.__dict__[attr]
		elif attr in self._defaults.keys():
			result = self._defaults[attr]
		elif attr in self._db_attributes:
			result = self._get(attr)
		elif attr in self._special_getters.keys():
			result = self._special_getters[attr](self)
		elif attr == 'id' or attr == '_id':
			result = self.__dict__['_id']
		return result


class ListaUser(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
			flags=0, fname="Anonymous", lname="", email="", avatar=""):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['flags', 'fname', 'lname', 'email', 'avatar']
		self._db_attributes.extend(new_attrs)
		self._table_names['fname'] = 'firstname'
		self._table_names['lname'] = 'lastname'

		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''

			self.flags = flags
			self.fname = fname
			self.lname = lname
			self.email = email
			self.avatar = avatar

	def set_from_cerebro_user(self, cerebro_user):
		from cerebro.aclasses import Users as CUsers

		self.id = cerebro_user[CUsers.DATA_ID]
		self.flags = cerebro_user[CUsers.DATA_FLAGS]
		self.fname = cerebro_user[CUsers.DATA_FIRST_NAME]
		self.lname = cerebro_user[CUsers.DATA_LAST_NAME]
		self.email = cerebro_user[CUsers.DATA_EMAIL]
		self.avatar = ""


class ListaVersion(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
			event_id=0, group_id=0, flags="", created_utc=None,
			name="", duration=0, fps=0, path="", download_url="",
			download_path="", file_id=-3):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['event_id', 'duration', 'fps', 'path', 'download_url', 'download_path', 'file_id', 'created_utc', 'name']
		self._db_attributes.extend(new_attrs)

		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''
			self.event_id = event_id
			self.group_id = group_id
			self.flags = flags
			# Current msec since epoch
			self.created_utc = int(time.time() * 1000) if created_utc is None \
				else created_utc
			self.name = name
			self.duration = duration
			self.fps = fps
			self.path = path
			self.download_url = download_url
			self.download_path = download_path
			self.file_id = file_id

	def set_from_cerebro_attachment(self, cerebro_attachment):
		self.event_id = cerebro_attachment.data()[cerebro_attachment.DATA_EVENT_ID]
		self.path = cerebro_attachment.file_path()
		self.name = cerebro_attachment.name()
		self.flags = cerebro_attachment.data()[cerebro_attachment.DATA_FLAGS]

	def is_null(self):
		return not self.path and not self.download_url


class ListaFile(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
				flags=0, task_id=0, task_name="", url="", name="",
				duration=0, fps=0):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['flags', 'task_id', 'task_name', 'url', 'name', 'duration', 'fps']
		self._db_attributes.extend(new_attrs)

		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''

			self.flags = flags
			self.task_id = task_id
			self.task_name = task_name
			self.url = url
			self.name = name
			self.duration = duration
			self.fps = fps

		def id_setter(s, nid):
			s._id = nid
			for vers in s.get_versions():
				vers.id = nid

		self._restricted_attributes.append('id_setter')
		self._special_attributes.append('id_setter')
		self._special_setters['id'] = id_setter

	def set_from_cerebro_attachment(self, cerebro_attachment):
		vers = self._vista.add_version()
		vers.set_from_cerebro_attachment(cerebro_attachment)
		self.add_version(vers)
		self.flags = cerebro_attachment.data()[cerebro_attachment.DATA_FLAGS]

	def add_version(self, vers):
		vers.file_id = self.id

	def get_versions(self):
		self._check_vista()
		version = self._vista.VERSION

		table = ListaVersions(version)
		sel_query = table.select(version, where={'file_id': self.id})
		sel_query = sel_query.replace('*', 'id', 1)
		res = self._execute(sel_query, [])
		result = tuple(self._vista.add_version(load=True, id=verstuple[0])
				for verstuple in res)

		return result


class ListaStatus(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
			flags="", name="", color="", icon="", order_no=0):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['flags', 'name', 'color', 'icon', 'order_no']
		self._db_attributes.extend(new_attrs)

		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''
			self.flags = flags
			self.name = name
			self.color = color
			self.icon = icon
			self.order_no = order_no


class ListaBitmap(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
				comment_id=-3, number_bitmap=0, flags=0, typ=0, frame=0,
				duration=0, version_id=0, pos_x=0, pos_y=0, pos_z=0, scale=0,
				width=0, height=0, data=''):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['file_id', 'comment_id', 'number_comment', 'flags',
				'create_utc', 'frame', 'duration', 'version_id', 'user_id',
				'mark_x', 'mark_y', 'comment']
		self._db_attributes.extend(new_attrs)
		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''
			self.comment_id = comment_id
			self.number_bitmap = number_bitmap
			self.flags = flags
			self.type = typ
			self.frame = frame
			self.duration = duration
			self.version_id = version_id
			self.pos_x = pos_x
			self.pos_y = pos_y
			self.pos_z = pos_z
			self.scale = scale
			self.width = width
			self.height = height
			self.data = data


class ListaAnswer(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
				file_id=-3, comment_id=-3, number_reply=0, user_id=-3,
				create_utc=0, comment=''):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['file_id', 'comment_id', 'number_reply', 'user_id',
				'create_utc', 'comment']
		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''
			self._db_attributes.extend(new_attrs)
			self.file_id = file_id
			self.comment_id = comment_id
			self.number_reply = number_reply
			self.user_id = user_id
			self.create_utc = create_utc
			self.comment = comment


class ListaComment(ListaBase):
	def __init__(self, tableClass, vista, execute_method, id, load=False,
				file_id=0, comment_id=0, number_comment=0, flags=0,
				create_utc=0, frame=0, duration=0, version_id=0, user_id=0,
				mark_x=0, mark_y=0, comment=''):
		super().__init__(tableClass, vista, execute_method, id)
		new_attrs = ['file_id', 'comment_id', 'number_comment', 'flags',
					'create_utc', 'frame', 'duration', 'version_id',
					'user_id', 'mark_x', 'mark_y', 'comment']
		self._db_attributes.extend(new_attrs)
		if not load:
			for attr in new_attrs:
				self._defaults[attr] = ''
			self.file_id = file_id
			self.comment_id = comment_id
			self.number_comment = number_comment
			self.flags = flags
			self.create_utc = create_utc
			self.frame = frame
			self.duration = duration
			self.version_id = version_id
			self.user_id = user_id
			self.mark_x = mark_x
			self.mark_y = mark_y
			self.comment = comment

		def id_setter(s, value):
			s._id = value
			for bmap in s.get_bitmaps():
				bmap.comment_id = value

		self._restricted_attributes.append('id_setter')
		self._special_attributes.append('id_setter')
		self._special_setters['id'] = id_setter

	def add_bitmap(self, bitmap):
		bitmap.file_id = self.id

	def get_bitmaps(self):
		self._check_vista()
		version = self._vista.VERSION

		table = ListaBitmaps(version)
		sel_query = table.select(version, where={'comment_id': self.id})
		sel_query = sel_query.replace('*', 'id', 1)
		res = self._execute(sel_query, [])
		result = tuple(self._vista.add_bitmap(load=True, id=verstuple[0])
				for verstuple in res)

		return result


# ===============================================
# ============ PLAYLIST MANIPULATOR =============
# ===============================================


class Vista:
	LISTA_EXT = "lista"
	VERSION = 2
	VERSION_BASE = 1

	def __init__(self, temp_dir = ""):
		self.__temp_dir = os.path.join(tempfile.gettempdir(), "tempMirada") if not temp_dir else temp_dir
		self.__temp_file = os.path.join(self.__temp_dir, "~vistade_{}.{}".format(int(time.time()), Vista.LISTA_EXT))
		self.__db = None

		if not os.path.exists(self.__temp_dir):
			os.makedirs(self.__temp_dir)

	def __del__(self):
		self.close_lista()

	# Public Vista
	def create_lista(self, lista_user = None, lista_path = ""):
		# it's impossible to predefine in attributes
		if lista_user == None:
			lista_user = ListaUser(ListaUsers, self, self.query, -2)
		if lista_path:
			if os.path.isfile(lista_path):
				os.remove(lista_path)

			self.__temp_file = lista_path
		else:
			self.__temp_file = os.path.join(self.__temp_dir, "~vistade_{}.{}".format(int(time.time()), Vista.LISTA_EXT))

		self.__open_lista(self.__temp_file)
		self.__init_lista(lista_user)
		lista_user.apply_defaults()

	def close_lista(self):
		if self.__db:
			self.__db.commit()
			self.__db.close()
			self.__db = None

		return self.__temp_file

	def set_lista(self, lista_path):
		self.__temp_file = os.path.join(self.__temp_dir, "~{}_{}.{}".format(os.path.basename(lista_path), int(time.time()), Vista.LISTA_EXT))

		dbTemp = sqlite3.connect(lista_path)

		try:
			dbTemp.execute("PRAGMA journal_mode = OFF;")

			ver_from = self.__version_lista(dbTemp)

			if ver_from == Vista.VERSION:
				if self.__temp_file != lista_path:
					shutil.copy2(lista_path, self.__temp_file)

				self.__open_lista(self.__temp_file)
			else:
				self.__temp_file = os.path.join(self.__temp_dir, "~vistade_{}.{}".format(int(time.time()), Vista.LISTA_EXT))
				self.__open_lista(self.__temp_file)

				self.__db.execute("ATTACH DATABASE \"{0}\" AS copydb".format(lista_path))

				try:
					self.__copy_tables_new(self.__db, dbTemp)
				except:
					raise
				finally:
					# Commit to unlock copydb
					self.__db.commit()
					self.__db.execute("DETACH DATABASE copydb")
		except:
			raise
		finally:
			dbTemp.close()

	def add_lista(self, lista_path):
		pass

	def import_lista(self, lista_path, file_id):
		if self.__db:
			dbFrom = sqlite3.connect(lista_path)

			try:
				dbFrom.execute("PRAGMA journal_mode = OFF;")

				self.__db.execute("ATTACH DATABASE \"{0}\" AS copydb".format(lista_path))

				try:
					self.__import_tables(self.__db, dbFrom, file_id)
				except:
					raise
				finally:
					# Commit to unlock copydb
					self.__db.commit()
					self.__db.execute("DETACH DATABASE copydb")
			except:
				raise
			finally:
				dbFrom.close()
		else:
			raise Exception("No current lista")

	def export_lista(self, lista_path, file_id):
		if self.__db:
			dbTo = sqlite3.connect(lista_path)

			try:
				dbTo.execute("PRAGMA journal_mode = OFF;")

				self.__db.execute("ATTACH DATABASE \"{0}\" AS copydb".format(lista_path))

				try:
					self.__create_tables(dbTo, Vista.VERSION)
					self.__export_tables(dbTo, self.__db, file_id)
				except:
					raise
				finally:
					# Commit to unlock copydb
					self.__db.commit()
					self.__db.execute("DETACH DATABASE copydb")
			except:
				raise
			finally:
				dbTo.close()
		else:
			raise Exception("No current lista")

	# Public Lista
	def query(self, query_text, query_args = ()):
		if not self.__db:
			raise Exception("No current lista")

		trans = self.__db.cursor()
		if isinstance(query_args, (list, tuple)) and len(query_args) and isinstance(query_args[0], (list, tuple)):
			trans.executemany(query_text, query_args)
		else:
			trans.execute(query_text, query_args)

		return trans.fetchall()

	def to_json(self):
		if not self.__db:
			raise Exception("No current lista")

		data = {"files": {}, "users": {}}

		trans = self.__db.cursor()
		t_files = ListaFiles(Vista.VERSION)
		t_comments = ListaComments(Vista.VERSION)
		t_bitmaps = ListaBitmaps(Vista.VERSION)
		t_answers = ListaAnswers(Vista.VERSION)
		t_cur_user = ListaCurUser(Vista.VERSION)
		t_users = ListaUsers(Vista.VERSION)

		trans.execute(t_files.select())
		list_files = trans.fetchall()
		trans.execute(t_comments.select())
		list_comments = trans.fetchall()
		trans.execute(t_bitmaps.select())
		list_bitmaps = trans.fetchall()
		trans.execute(t_answers.select())
		list_answers = trans.fetchall()
		trans.execute(t_users.select())
		list_users = trans.fetchall()

		columns = { col: i for i, col in enumerate(t_files.columns()) }
		for file in list_files:
			data["files"][file[columns["id"]]] = {
				"task_id": file[columns["task_id"]]
				, "task_name": file[columns["task_name"]]
				, "name": file[columns["name"]]
				, "duration": file[columns["duration"]]
				, "fps": file[columns["fps"]]
				, "comments": {}
			}

		columns = { col: i for i, col in enumerate(t_comments.columns()) }
		for comment in list_comments:
			fcomments = data["files"][comment[columns["file_id"]]]["comments"]
			fcomments[comment[columns["comment_id"]]] = {
				"user_id": comment[columns["user_id"]]
				, "comment": comment[columns["comment"]]
				, "number_comment": comment[columns["number_comment"]]
				, "frame": comment[columns["frame"]]
				, "duration": comment[columns["duration"]]
				, "flags": comment[columns["flags"]]
				, "bitmaps": {}
				, "answers": []
			}

		columns = { col: i for i, col in enumerate(t_bitmaps.columns()) }
		for bitmap in list_bitmaps:
			fcomments = data["files"][bitmap[columns["file_id"]]]["comments"]
			fbitmaps = fcomments[bitmap[columns["comment_id"]]]["bitmaps"]
			fbitmaps[bitmap[columns["number_bitmap"]]] = {
				"frame": bitmap[columns["frame"]]
				, "duration": bitmap[columns["duration"]]
				, "pos_x": bitmap[columns["pos_x"]]
				, "pos_y": bitmap[columns["pos_y"]]
				, "scale": bitmap[columns["scale"]]
				, "width": bitmap[columns["width"]]
				, "height": bitmap[columns["height"]]
			}

			if bitmap[columns["type"]] == ListaBitmaps.TYPE_MACROS:
				# Track
				count_events = struct.unpack(">I", bitmap[columns["data"]][:struct.calcsize(">I")])[0]
				size_events = count_events * struct.calcsize(">iidd")
				count_sound_bytes = struct.unpack(">I", bitmap[columns["data"]][struct.calcsize(">I") + size_events:2 * struct.calcsize(">I") + size_events])[0]
				# int event count
				# Events (int, int, double, double)
				# int sound data byte size
				# bytes sound data
				event_queue = struct.unpack(">{}".format("iidd" * count_events), bitmap[columns["data"]][struct.calcsize(">I"):struct.calcsize(">I") + size_events])
				sound_data = bitmap[columns["data"]][2 * struct.calcsize(">I") + size_events:2 * struct.calcsize(">I") + size_events + count_sound_bytes]
				event_list = [ {"time": event_queue[i], "type": event_queue[i + 1]
					, "param1": event_queue[i + 2], "param2": event_queue[i + 3]} for i in range(0, count_events * 4, 4) ]

				fbitmaps[bitmap[columns["number_bitmap"]]]["type"] = "track"
				fbitmaps[bitmap[columns["number_bitmap"]]]["track"] = {
					"event_list": event_list
					, "sound_data": base64.b64encode(sound_data).decode("ascii")
				}

			elif bitmap[columns["type"]] == ListaBitmaps.TYPE_BITMAP:
				# Pixmap
				# int is_null
				# bytes image data
				valid = struct.unpack(">i", bitmap[columns["data"]][:struct.calcsize(">i")])[0]
				image_data = bitmap[columns["data"]][struct.calcsize(">i"):] if valid else b''

				fbitmaps[bitmap[columns["number_bitmap"]]]["type"] = "pixmap"
				fbitmaps[bitmap[columns["number_bitmap"]]]["pixmap"] = base64.b64encode(image_data).decode("ascii")

			elif bitmap[columns["type"]] == ListaBitmaps.TYPE_TEXT:
				# Text box
				# QString text (length, str)
				# QColor color (cspec, a, r, g, b, pad)
				# QColor bgColor (cspec, a, r, g, b, pad)
				# QFont font
				# - QString fontFamily (length, str)
				# - QString styleName (length, str)
				# - double pointSize
				# - int pixelSize
				# - unsigned char styleHint
				# - unsigned short styleStrategy
				# - unsigned char 0
				# - unsigned char weight
				# - unsigned char fontBits
				# - unsigned short stretch
				# - unsigned char extendedFontBits
				# - int letterSpacing
				# - int wordSpacing
				# - unsigned char hintingPreference
				# - unsigned char capital
				# - QStringList families
				# QPainterPath path (element_count, [(type, x, y)], cStart, fillRule)
				ptr = 0

				text, ptr = unpack_string(bitmap[columns["data"]], ptr)

				color_hex, ptr = unpack_color(bitmap[columns["data"]], ptr)
				color_bg_hex, ptr = unpack_color(bitmap[columns["data"]], ptr)

				font_family, ptr = unpack_string(bitmap[columns["data"]], ptr)
				_, ptr = unpack_string(bitmap[columns["data"]], ptr)

				font_size, ptr = unpack_single(bitmap[columns["data"]], ">d", ptr)

				ptr += struct.calcsize(">iBHBBBHBiiBB")
				
				list_length = struct.unpack(">i", bitmap[columns["data"]][ptr:ptr + struct.calcsize(">i")])[0]
				ptr += struct.calcsize(">i")
				for i in range(list_length):
					text_length = struct.unpack(">i", bitmap[columns["data"]][ptr:ptr + struct.calcsize(">i")])[0]
					ptr += struct.calcsize(">i")
					if text_length > 0:
						ptr += text_length
				
				count = struct.unpack(">i", bitmap[columns["data"]][ptr:ptr + struct.calcsize(">i")])[0]
				ptr += struct.calcsize(">i")
				el_list = struct.unpack(">{}".format("idd" * count), bitmap[columns["data"]][ptr:-struct.calcsize(">ii")])
				point_list = [ (el_list[i + 1], el_list[i + 2]) for i in range(0, count * 3, 3) ]

				fbitmaps[bitmap[columns["number_bitmap"]]]["type"] = "text_box"
				fbitmaps[bitmap[columns["number_bitmap"]]]["text_box"] = {
					"text": text
					, "color": color_hex
					, "color_bg": color_bg_hex
					, "font_family": font_family
					, "font_size": font_size
					, "box": point_list
				}

			elif bitmap[columns["type"]] in (ListaBitmaps.TYPE_PEN, ListaBitmaps.TYPE_RECT, ListaBitmaps.TYPE_ELLIPSE
											, ListaBitmaps.TYPE_ARROW, ListaBitmaps.TYPE_LINE):
				# Vector
				# double line_width
				# QColor color (cspec, a, r, g, b, pad)
				# QPainterPath path (element_count, [(type, x, y)], cStart, fillRule)
				ptr = struct.calcsize(">db5H")
				count = struct.unpack(">i", bitmap[columns["data"]][ptr:ptr + struct.calcsize(">i")])[0]
				# Unpacking doesn't work in PY2
				#line_width, _, c_a, c_r, c_g, c_b, _, _, *el_list, _, _ = struct.unpack(">db5Hi{}ii".format("idd" * count), bitmap[columns["data"]])
				unpacked = struct.unpack(">db5Hi{}ii".format("idd" * count), bitmap[columns["data"]])
				line_width, _, c_a, c_r, c_g, c_b = unpacked[:6]
				el_list = unpacked[8:-2]
				
				color_hex = "#{:0>2X}{:0>2X}{:0>2X}{:0>2X}".format(c_r >> 8, c_g >> 8, c_b >> 8, c_a >> 8)
				point_list = [ (el_list[i + 1], el_list[i + 2]) for i in range(0, count * 3, 3) ]

				shape = "pen"
				if bitmap[columns["type"]] == ListaBitmaps.TYPE_RECT:
					shape = "rect"
				elif bitmap[columns["type"]] == ListaBitmaps.TYPE_ELLIPSE:
					shape = "ellipse"
				elif bitmap[columns["type"]] == ListaBitmaps.TYPE_ARROW:
					shape = "arrow"
				elif bitmap[columns["type"]] == ListaBitmaps.TYPE_LINE:
					shape = "line"

				fbitmaps[bitmap[columns["number_bitmap"]]]["type"] = "vector"
				fbitmaps[bitmap[columns["number_bitmap"]]]["vector"] = {
					"color": color_hex
					, "shape": shape
					, "line_width": line_width
					, "points": point_list
				}

		columns = { col: i for i, col in enumerate(t_answers.columns()) }
		for answer in list_answers:
			fcomments = data["files"][answer[columns["file_id"]]]["comments"]
			fanswers = fcomments[answer[columns["comment_id"]]]["answers"]
			fanswers.append({
				"number_reply": answer[columns["number_reply"]]
				, "user_id": answer[columns["user_id"]]
				, "create_utc": answer[columns["create_utc"]]
				, "comment": answer[columns["comment"]]
			})

		columns = { col: i for i, col in enumerate(t_users.columns()) }
		for user in list_users:
			data["users"][user[columns["id"]]] = {
				"firstname": user[columns["firstname"]]
				, "lastname": user[columns["lastname"]]
				, "email": user[columns["email"]]
				, "flags": user[columns["flags"]]
			}

		return json.dumps(data)

	def from_json(self, json_data):
		if not self.__db:
			raise Exception("No current lista")

		data = json.loads(json_data)

		if not ("files" in data and len(data["files"])):
			raise Exception("No files in JSON")

		trans = self.__db.cursor()
		t_files = ListaFiles(Vista.VERSION)
		t_comments = ListaComments(Vista.VERSION)
		t_bitmaps = ListaBitmaps(Vista.VERSION)
		t_answers = ListaAnswers(Vista.VERSION)
		t_cur_user = ListaCurUser(Vista.VERSION)
		t_users = ListaUsers(Vista.VERSION)

		for uid, user in data["users"].items():
			trans.execute(t_users.insert(), (
				uid
				, user["flags"]
				, user["firstname"]
				, user["lastname"]
				, user["email"]
				, None
			))

		for fid, file in data["files"].items():
			fcomments = file.get("comments", {})

			trans.execute(t_files.insert(), (
				fid
				, 0
				, file["task_id"]
				, file["task_name"]
				, None
				, file["name"]
				, file["duration"]
				, file["fps"]
			))

			for cid, comment in fcomments.items():
				fbitmaps = comment.get("bitmaps", {})
				fanswers = comment.get("answers", [])

				trans.execute(t_comments.insert(), (
					fid
					, cid
					, comment["number_comment"]
					, comment.get("flags", 0)
					, comment.get("create_utc", int(time.time() * 1000))
					, comment.get("frame", 0)
					, comment.get("duration", 1)
					, comment.get("version_id", fid)
					, comment["user_id"]
					, comment.get("mark_x", 0.0)
					, comment.get("mark_y", 0.0)
					, comment.get("comment", "")
				))

				for bid, bitmap in fbitmaps.items():
					bdata = None
					btype = ListaBitmaps.TYPE_PEN
					
					if bitmap["type"] == "track":
						event_queue = []
						event_list = bitmap["track"]["event_list"]
						sound_data = base64.b64decode(bitmap["track"]["sound_data"].encode("ascii"))
						count_events = len(event_list)
						count_sound_bytes = len(sound_data)

						for event in event_list:
							event_queue.append(event["time"])
							event_queue.append(event["type"])
							event_queue.append(event["param1"])
							event_queue.append(event["param2"])

						bdata = struct.pack(">I{}I".format("iidd" * count_events), count_events, *(event_queue + [count_sound_bytes]))
						bdata += sound_data
						btype = ListaBitmaps.TYPE_MACROS

					elif bitmap["type"] == "pixmap":
						bdata = struct.pack(">i", 1 if len(bitmap["pixmap"]) else 0)
						bdata += base64.b64decode(bitmap["pixmap"].encode("ascii"))
						btype = ListaBitmaps.TYPE_BITMAP

					elif bitmap["type"] == "text_box":
						el_list = []
						text = bitmap["text_box"]["text"]
						color_hex = bitmap["text_box"]["color"]
						color_bg_hex = bitmap["text_box"]["color_bg"]
						font_family = bitmap["text_box"]["font_family"]
						font_size = bitmap["text_box"]["font_size"]
						point_list = bitmap["text_box"]["box"]
						count = len(point_list)

						for point in point_list:
							el_list.append(0)
							el_list.append(point[0])
							el_list.append(point[1])

						c_r = (int(color_hex[1:3], 16) << 8) & 255
						c_g = (int(color_hex[3:5], 16) << 8) & 255
						c_b = (int(color_hex[5:7], 16) << 8) & 255
						c_a = (int(color_hex[7:9], 16) << 8) & 255

						cb_r = (int(color_bg_hex[1:3], 16) << 8) & 255
						cb_g = (int(color_bg_hex[3:5], 16) << 8) & 255
						cb_b = (int(color_bg_hex[5:7], 16) << 8) & 255
						cb_a = (int(color_bg_hex[7:9], 16) << 8) & 255

						bdata = struct.pack(">i{}sb5Hb5Hi{}sii{}ii".format(len(text), len(font_family), "idd" * count)
							, len(text), text
							, 1, c_a, c_r, c_g, c_b, 0
							, 1, cb_a, cb_r, cb_g, cb_b, 0
							, len(font_family), font_family
							, font_size
							, count, *(el_list + [0, 0])
						)
						btype = ListaBitmaps.TYPE_TEXT

					elif bitmap["type"] == "vector":
						el_list = []
						line_width = bitmap["vector"]["line_width"]
						color_hex = bitmap["vector"]["color"]
						point_list = bitmap["vector"]["points"]
						shape = bitmap["vector"]["shape"]
						count = len(point_list)

						for point in point_list:
							el_list.append(0)
							el_list.append(point[0])
							el_list.append(point[1])

						c_r = (int(color_hex[1:3], 16) << 8) & 255
						c_g = (int(color_hex[3:5], 16) << 8) & 255
						c_b = (int(color_hex[5:7], 16) << 8) & 255
						c_a = (int(color_hex[7:9], 16) << 8) & 255

						bdata = struct.pack(">db5Hi{}ii".format("idd" * count)
							, line_width
							, 1, c_a, c_r, c_g, c_b, 0
							, count, *(el_list + [0, 0])
						)

						btype = ListaBitmaps.TYPE_PEN
						if shape == "rect":
							btype = ListaBitmaps.TYPE_RECT
						elif shape == "ellipse":
							btype = ListaBitmaps.TYPE_ELLIPSE
						elif shape == "arrow":
							btype = ListaBitmaps.TYPE_ARROW
						elif shape == "line":
							btype = ListaBitmaps.TYPE_LINE
					
					trans.execute(t_bitmaps.insert(), (
						fid
						, cid
						, bid
						, 0
						, btype
						, bitmap["frame"]
						, bitmap["duration"]
						, fid
						, bitmap["pos_x"]
						, bitmap["pos_y"]
						, 1
						, bitmap["scale"]
						, bitmap["width"]
						, bitmap["height"]
						, bdata
					))

				for answer in fanswers:
					trans.execute(t_answers.insert(), (
						fid
						, cid
						, answer["number_reply"]
						, answer["user_id"]
						, answer["create_utc"]
						, answer["comment"]
					))

	def add_user(self, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_users()) > 0:
				id = max(list(user.id for user in self.get_users()))

			id += 1

		lista_user = ListaUser(ListaUsers, self, self.query, id, load=load)

		if self.__db and not load:
			trans = self.__db.cursor()
			t_users = ListaUsers(self.VERSION)
			lista_user_dict = lista_user.dict()

			keys = tuple(lista_user._get_table_name(key) for key in lista_user_dict.keys())
			vals = tuple(lista_user_dict.values())
			trans.execute(t_users.insert(keys), vals)
			lista_user.apply_defaults()
		return lista_user

	def insert_users(self, lista_users):
		for user in lista_users:
			self.insert_user(user)

	def insert_user(self, old_user):
		user = self.add_user()
		user.from_dict(old_user.dict())
		return user

	def get_users(self):
		users = []
		if self.__db:
			trans = self.__db.cursor()
			t_users = ListaUsers(Vista.VERSION)

			trans.execute(t_users.select())
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				user = self.add_user(dic['id'], load=True)
				user.from_dict(dic)
				users.append(user)
		return users

	def add_version(self, file_id=-3, id=-3, load=False):
		if id < -2 and not load:
			if self.__db and len(self.get_versions()) > 0:
				id = max(list(version.id for version in self.get_versions()))

			id += 1

		if file_id < -2 and not load:
			raise Exception("You tried to add new version without file ID")

		lista_version = ListaVersion(ListaVersions, self, self.query, id, load=load, file_id=file_id)

		if self.__db:
			trans = self.__db.cursor()
			t_versions = ListaVersions(self.VERSION)
			lista_version_dict = lista_version.dict()

			if not load:
				keys = tuple(lista_version._get_table_name(key) for key in lista_version_dict.keys())
				vals = tuple(lista_version_dict.values())
				trans.execute(t_versions.insert(keys), vals)
			lista_version.apply_defaults()
		return lista_version

	def insert_versions(self, lista_versions):
		for version in lista_versions:
			self.insert_version(version)

	def insert_version(self, old_version, file_id):
		version = self.add_version()
		dic = old_version.dict()
		dic[file_id] = file_id
		version.from_dict(dic)
		return version

	def get_versions(self, file_id=-3):
		versions = []
		if self.__db:
			trans = self.__db.cursor()
			t_versions = ListaVersions(Vista.VERSION)

			where = {'file_id': file_id} if file_id > -3 else {}
			trans.execute(t_versions.select(where=where))
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				version = self.add_version(id=dic['id'], file_id=dic['file_id'], load=True)
				version.from_dict(dic)
				versions.append(version)
		return versions

	def add_file(self, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_files()) > 0:
				id = max(list(file.id for file in self.get_files()))

			id += 1

		lista_file = ListaFile(ListaFiles, self, self.query, id, load=load)

		if self.__db:
			trans = self.__db.cursor()
			t_files = ListaFiles(self.VERSION)
			lista_file_dict = lista_file.dict()

			keys = tuple(lista_file._get_table_name(key) for key in lista_file_dict.keys())
			vals = tuple(lista_file_dict.values())
			trans.execute(t_files.insert(keys), vals)
			lista_file.apply_defaults()
		return lista_file

	def insert_files(self, lista_files):
		for file in lista_files:
			self.insert_file(file)

	def insert_file(self, old_file):
		file = self.add_file()
		file.from_dict(old_file.dict())

		for version in old_file.get_versions():
			vers = self.insert_version(version, file.id)
			file.add_version(vers)

		return file

	def get_files(self):
		files = []
		if self.__db:
			trans = self.__db.cursor()
			t_files = ListaFiles(Vista.VERSION)

			trans.execute(t_files.select())
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				file = self.add_file(dic['id'], load=True)
				file.from_dict(dic)
				files.append(file)
		return files


	def insert_ab(self, file_id, version_a, version_b = None):
		if self.__db:
			trans = self.__db.cursor()
			t_file_ab = ListaFileAb(Vista.VERSION)

			trans.execute(t_file_ab.insert(), (file_id, version_a, version_b))

	def insert_file_status(self, file_id, status_id):
		if self.__db:
			trans = self.__db.cursor()
			t_file_status = ListaFileStatus(Vista.VERSION)

			trans.execute(t_file_status.insert(), (file_id, status_id))

	def add_status(self, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_statuses()) > 0:
				id = max(list(status.id for status in self.get_statuses()))

			id += 1

		lista_status = ListaStatus(ListaStatuses, self, self.query, id, load=load)

		if self.__db and not load:
			trans = self.__db.cursor()
			t_statuses = ListaStatuses(self.VERSION)
			lista_status_dict = lista_status.dict()

			keys = tuple(lista_status._get_table_name(key) for key in lista_status_dict.keys())
			vals = tuple(lista_status_dict.values())
			trans.execute(t_statuses.insert(keys), vals)
			lista_status.apply_defaults()
		return lista_status

	def insert_status(self, old_status):
		status = self.add_status()
		status.from_dict(old_status.dict())
		return status

	def insert_statuses(self, lista_statuses):
		for status in lista_statuses:
			self.insert_status(status)

	def get_statuses(self):
		statuses = []
		if self.__db:
			trans = self.__db.cursor()
			t_statuses = ListaStatuses(Vista.VERSION)

			trans.execute(t_statuses.select())
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				status = self.add_status(dic['id'], load=True)
				status.from_dict(dic)
				statuses.append(status)
		return statuses

	def add_answer(self, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_answers()) > 0:
				id = max(list(answer.id for answer in self.get_answers()))

			id += 1

		lista_answer = ListaAnswer(ListaAnswers, self, self.query, id, load=load)

		if self.__db and not load:
			trans = self.__db.cursor()
			t_answers = ListaAnswers(self.VERSION)
			lista_answer_dict = lista_answer.dict()

			keys = tuple(lista_answer._get_table_name(key) for key in lista_answer_dict.keys())
			vals = tuple(lista_answer_dict.values())
			trans.execute(t_answers.insert(keys), vals)
			lista_answer.apply_defaults()
		return lista_answer

	def insert_answers(self, lista_answers):
		for answer in lista_answers:
			self.insert_answer(answer)

	def insert_answer(self, old_answer):
		answer = self.add_answer()
		answer.from_dict(old_answer.dict())
		return answer

	def get_answers(self):
		answers = []
		if self.__db:
			trans = self.__db.cursor()
			t_answers = ListaAnswers(Vista.VERSION)

			trans.execute(t_answers.select())
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				answer = self.add_answer(dic['id'], load=True)
				answer.from_dict(dic)
				answers.append(answer)
		return answers

	def add_bitmap(self, comment_id=-3, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_bitmaps()) > 0:
				id = max(list(bitmap.id for bitmap in self.get_bitmaps()))

			id += 1

		lista_bitmap = ListaBitmap(ListaBitmaps, self, self.query, id, load=load)

		if self.__db and not load:
			trans = self.__db.cursor()
			t_bitmaps = ListaBitmaps(self.VERSION)
			lista_bitmap_dict = lista_bitmap.dict()

			keys = tuple(lista_bitmap._get_table_name(key) for key in lista_bitmap_dict.keys())
			vals = tuple(lista_bitmap_dict.values())
			trans.execute(t_bitmaps.insert(keys), vals)
			lista_bitmap.apply_defaults()
		return lista_bitmap

	def insert_bitmap(self, old_bitmap):
		bitmap = self.add_bitmap()
		bitmap.from_dict(old_bitmap.dict())
		return bitmap

	def get_bitmaps(self, comment_id=-3):
		bitmaps = []
		if self.__db:
			trans = self.__db.cursor()
			t_bitmaps = ListaBitmaps(Vista.VERSION)

			where = {'comment_id': comment_id} if comment_id > -3 else {}
			trans.execute(t_bitmaps.select(where=where))
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				bitmap = self.add_bitmap(dic['id'], load=True)
				bitmap.from_dict(dic)
				bitmaps.append(bitmap)
		return bitmaps

	def add_comment(self, id=-3, load=False):
		if id < -2:
			if self.__db and len(self.get_versions()) > 0:
				id = max(list(version.id for version in self.get_versions()))

			id += 1

		lista_comment = ListaComment(ListaComments, self, self.query, id, load=load)

		if self.__db:
			trans = self.__db.cursor()
			t_comments = ListaComments(self.VERSION)
			lista_comment_dict = lista_comment.dict()

			keys = tuple(lista_comment._get_table_name(key) for key in lista_comment_dict.keys())
			vals = tuple(lista_comment_dict.values())
			trans.execute(t_comments.insert(keys), vals)
			lista_comment.apply_defaults()
		return lista_comment

	def insert_comments(self, lista_comments):
		for comment in lista_comments:
			self.insert_comment(comment)

	def insert_comment(self, old_comment):
		comment = self.add_comment()
		comment.from_dict(old_comment.dict())

		for bitmap in old_comment.get_bitmaps():
			bitmap = self.insert_bitmap(bitmap, comment.id)
			comment.add_bitmap(bitmap)

		return comment

	def get_comments(self):
		comments = []
		if self.__db:
			trans = self.__db.cursor()
			t_comments = ListaComments(Vista.VERSION)

			trans.execute(t_comments.select())
			for values in trans.fetchall():
				names = list(description[0] for description in trans.description)
				dic = dict(zip(names, values))
				comment = self.add_comment(dic['id'], load=True)
				comment.from_dict(dic)
				comments.append(comment)
		return comments


	# Private Vista
	def __open_lista(self, lista_path):
		self.close_lista()

		self.__db = sqlite3.connect(lista_path)
		self.__db.execute("PRAGMA journal_mode = WAL;")
		self.__create_tables(self.__db, Vista.VERSION)

	def __init_lista(self, lista_user):
		self.__init_tables(self.__db, Vista.VERSION, lista_user)

	def __version_lista(self, db):
		trans = db.cursor()
		t_format = ListaFormat(Vista.VERSION_BASE)

		trans.execute(t_format.exists())
		exists = len(trans.fetchall()) == 1

		if exists:
			trans.execute(t_format.select())
			cur_version = trans.fetchall()
			if len(cur_version) != 1 or len(cur_version[0]) != 1:
				raise Exception("Can't determine DB version")

			return int(cur_version[0][0])

		return -1

	# Private Lista
	def __copy_by_id(self, lista_table, db, db_from, column, id):
		trans = db.cursor()
		trans_exists = db_from.cursor()

		trans_exists.execute(lista_table.exists())
		exists = len(trans_exists.fetchall()) == 1

		if exists:
			insert = lista_table.copy() + " WHERE copydb.{0}.{1}={2}".format(lista_table.name(), column, id)
			trans.execute(insert)

	def __import_by_id(self, lista_table, db, db_from, column, id):
		trans = db.cursor()
		trans_exists = db_from.cursor()

		trans_exists.execute(lista_table.exists())
		exists = len(trans_exists.fetchall()) == 1

		if exists:
			insert = "copydb.{0}.{1}".format(lista_table.name(), column)
			trans.execute(lista_table.copy().replace(insert, str(id)))

	def __copy(self, lista_table, db, db_from):
		trans = db.cursor()
		trans_exists = db_from.cursor()

		trans_exists.execute(lista_table.exists())
		exists = len(trans_exists.fetchall()) == 1

		if exists:
			trans.execute(lista_table.copy())

	def __create_table(self, lista_table, trans):
		trans.execute(lista_table.exists())
		exists = len(trans.fetchall()) == 1

		if not exists:
			trans.execute(lista_table.create())

		return not exists

	def __create_tables(self, db, version):
		trans = db.cursor()

		trans.execute("PRAGMA foreign_keys = ON;")

		t_format = ListaFormat(version)
		if self.__create_table(t_format, trans):
			trans.execute(t_format.insert())

		self.__create_table(ListaApi(version), trans)
		self.__create_table(ListaStatuses(version), trans)
		self.__create_table(ListaFiles(version), trans)
		self.__create_table(ListaFileStatus(version), trans)
		self.__create_table(ListaVersions(version), trans)
		self.__create_table(ListaFileAb(version), trans)
		self.__create_table(ListaFileOrder(version), trans)
		self.__create_table(ListaCurUser(version), trans)
		self.__create_table(ListaUsers(version), trans)
		self.__create_table(ListaFileChanges(version), trans)
		self.__create_table(ListaCurState(version), trans)
		self.__create_table(ListaTails(version), trans)
		self.__create_table(ListaAspects(version), trans)
		self.__create_table(ListaMark(version), trans)
		self.__create_table(ListaLoop(version), trans)
		self.__create_table(ListaOnionSkin(version), trans)
		self.__create_table(ListaViewport(version), trans)
		self.__create_table(ListaTools(version), trans)
		self.__create_table(ListaRender(version), trans)
		self.__create_table(ListaComments(version), trans)
		self.__create_table(ListaBitmaps(version), trans)
		self.__create_table(ListaAnswers(version), trans)
		self.__create_table(ListaCommentsWatched(version), trans)
		self.__create_table(ListaFileGenerated(version), trans)
		self.__create_table(ListaSupport(version), trans)
		self.__create_table(ListaFileExported(version), trans)

	def __copy_tables_new(self, db, db_from):
		ver_from = self.__version_lista(db_from)

		t_api = ListaApi(Vista.VERSION).from_version(ver_from)
		t_statuses = ListaStatuses(Vista.VERSION).from_version(ver_from)
		t_files = ListaFiles(Vista.VERSION).from_version(ver_from)
		t_file_status = ListaFileStatus(Vista.VERSION).from_version(ver_from)
		t_versions = ListaVersions(Vista.VERSION).from_version(ver_from)
		t_file_ab = ListaFileAb(Vista.VERSION).from_version(ver_from)
		t_file_order = ListaFileOrder(Vista.VERSION).from_version(ver_from)
		t_cur_user = ListaCurUser(Vista.VERSION).from_version(ver_from)
		t_users = ListaUsers(Vista.VERSION).from_version(ver_from)
		t_file_changes = ListaFileChanges(Vista.VERSION).from_version(ver_from)
		t_cur_state = ListaCurState(Vista.VERSION).from_version(ver_from)
		t_tails = ListaTails(Vista.VERSION).from_version(ver_from)
		t_aspects = ListaAspects(Vista.VERSION).from_version(ver_from)
		t_mark = ListaMark(Vista.VERSION).from_version(ver_from)
		t_loop = ListaLoop(Vista.VERSION).from_version(ver_from)
		t_onion_skin = ListaOnionSkin(Vista.VERSION).from_version(ver_from)
		t_viewport = ListaViewport(Vista.VERSION).from_version(ver_from)
		t_tools = ListaTools(Vista.VERSION).from_version(ver_from)
		t_render = ListaRender(Vista.VERSION).from_version(ver_from)
		t_comments = ListaComments(Vista.VERSION).from_version(ver_from)
		t_bitmaps = ListaBitmaps(Vista.VERSION).from_version(ver_from)
		t_answers = ListaAnswers(Vista.VERSION).from_version(ver_from)
		t_comments_w = ListaCommentsWatched(Vista.VERSION).from_version(ver_from)
		t_file_gen = ListaFileGenerated(Vista.VERSION).from_version(ver_from)
		t_support = ListaSupport(Vista.VERSION).from_version(ver_from)
		t_file_exp = ListaFileExported(Vista.VERSION).from_version(ver_from)

		self.__copy(t_api, db, db_from)
		self.__copy(t_statuses, db, db_from)
		self.__copy(t_files, db, db_from)
		self.__copy(t_file_status, db, db_from)
		self.__copy(t_versions, db, db_from)
		self.__copy(t_file_ab, db, db_from)
		self.__copy(t_file_order, db, db_from)
		self.__copy(t_cur_user, db, db_from)
		self.__copy(t_users, db, db_from)
		self.__copy(t_file_changes, db, db_from)
		self.__copy(t_cur_state, db, db_from)
		self.__copy(t_tails, db, db_from)
		self.__copy(t_aspects, db, db_from)
		self.__copy(t_mark, db, db_from)
		self.__copy(t_loop, db, db_from)
		self.__copy(t_onion_skin, db, db_from)
		self.__copy(t_viewport, db, db_from)
		self.__copy(t_tools, db, db_from)
		self.__copy(t_render, db, db_from)
		self.__copy(t_comments, db, db_from)
		self.__copy(t_bitmaps, db, db_from)
		self.__copy(t_answers, db, db_from)
		self.__copy(t_comments_w, db, db_from)
		self.__copy(t_file_gen, db, db_from)
		self.__copy(t_support, db, db_from)
		self.__copy(t_file_exp, db, db_from)

	def __import_tables(self, db, db_from, file_id):
		ver_from = self.__version_lista(db_from)

		t_comments = ListaComments(Vista.VERSION).from_version(ver_from)
		t_bitmaps = ListaBitmaps(Vista.VERSION).from_version(ver_from)
		t_answers = ListaAnswers(Vista.VERSION).from_version(ver_from)
		t_comments_w = ListaCommentsWatched(Vista.VERSION).from_version(ver_from)
		t_users = ListaUsers(Vista.VERSION).from_version(ver_from)

		self.__import_by_id(t_comments, db, db_from, "file_id", file_id)
		self.__import_by_id(t_bitmaps, db, db_from, "file_id", file_id)
		self.__import_by_id(t_answers, db, db_from, "file_id", file_id)
		self.__import_by_id(t_comments_w, db, db_from, "file_id", file_id)

		self.__copy(t_users, db, db_from)

	def __export_tables(self, db, db_from, file_id):
		ver_from = self.__version_lista(db_from)

		t_files = ListaFiles(Vista.VERSION).from_version(ver_from)
		t_comments = ListaComments(Vista.VERSION).from_version(ver_from)
		t_bitmaps = ListaBitmaps(Vista.VERSION).from_version(ver_from)
		t_answers = ListaAnswers(Vista.VERSION).from_version(ver_from)
		t_comments_w = ListaCommentsWatched(Vista.VERSION).from_version(ver_from)
		t_users = ListaUsers(Vista.VERSION).from_version(ver_from)

		self.__copy_by_id(t_files, db, db_from, "id", file_id)
		self.__copy_by_id(t_comments, db, db_from, "file_id", file_id)
		self.__copy_by_id(t_bitmaps, db, db_from, "file_id", file_id)
		self.__copy_by_id(t_answers, db, db_from, "file_id", file_id)
		self.__copy_by_id(t_comments_w, db, db_from, "file_id", file_id)

		self.__copy(t_users, db, db_from)

	def __init_tables(self, db, version, lista_user):
		trans = db.cursor()

		# Set current user data
		t_cur_user = ListaCurUser(version)
		t_users = ListaUsers(version)

		trans.execute(t_cur_user.select())
		if len(trans.fetchall()) == 0:
			trans.execute(t_cur_user.insert(), (
					lista_user.id
					, lista_user.flags
					, lista_user.fname
					, lista_user.lname
					, lista_user.email
					, lista_user.avatar
				)
			)

		trans.execute(t_cur_user.select())
		cur_user = trans.fetchall()[0]
		trans.execute(t_users.insert(), cur_user)

		# Ensure file order is set
		self.__insert_order(trans, version)

		# Enable Cerebro API by default
		t_api = ListaApi(version)

		trans.execute(t_api.select())
		if len(trans.fetchall()) == 0:
			trans.execute(t_api.insert(), (
					1
					, None
					, None
					, None
					, 0
				)
			)

	def __insert_order(self, trans, version):
		t_file_order = ListaFileOrder(version)
		t_files = ListaFiles(version)

		trans.execute("INSERT OR IGNORE INTO {0}(file_id) SELECT {1}.id FROM {1}".format(
			t_file_order.name(), t_files.name()))

# ===============================================
# =========== LISTA TABLE BASE CLASS ============
# ===============================================

class ListaTable:

	STATEMENT_SELECT_ORDER = 0
	STATEMENT_INSERT = 1
	STATEMENT_COPY = 2

	DEFAULT_SELECT_ORDER = None
	DEFAULT_INSERT = "INSERT OR REPLACE"
	DEFAULT_COPY = "INSERT OR IGNORE"

	def __init__(self, name, version, columns = None):
		self.__name = name
		self.__version = version
		self.__version_from = version
		self.__version_columns = []
		self.__version_attributes = []
		self.__version_statements = {}

		if columns:
			self._set_version_columns(self.__version, columns)

	# protected
	def _set_version_columns(self, version, columns):
		version = int(version)
		if version > 0:
			defined_versions = len(self.__version_columns)
			col_types = [ i.strip().split(maxsplit=1) for i in columns ]
			col_names = [ i[0] for i in col_types if not i[0].upper() in ["PRIMARY", "FOREIGN"] ]
			col_attributes = [ " ".join(i) for i in col_types ]
			for i in range(defined_versions, version):
				self.__version_columns.append(col_names)
				self.__version_attributes.append(col_attributes)
			if defined_versions >= version:
				self.__version_columns[version - Vista.VERSION_BASE] = col_names
				self.__version_attributes[version - Vista.VERSION_BASE] = col_attributes

	def _set_version_statement(self, version, statement, value):
		self.__version_statements[(version, statement)] = value

	# private
	def __check_columns(self, version):
		if version > len(self.__version_columns):
			raise Exception("Table '{0}' has no columns for version '{1}'".format(self.__name, version))

	def __columns(self, version_from, version_to):
		self.__check_columns(version_from)
		self.__check_columns(version_to)

		columns = []
		if version_from != version_to:
			columns = [ i for i in self.__version_columns[version_from - Vista.VERSION_BASE]
						if i in self.__version_columns[version_to - Vista.VERSION_BASE] ]
		else:
			columns = self.__version_columns[version_from - Vista.VERSION_BASE]

		return columns

	# public
	def from_version(self, version_from):
		self.__version_from = version_from

		return self

	def column_of(self, column, version = -1):
		if version < Vista.VERSION_BASE: version = self.__version

		columns = self.__columns(version, version)

		return columns.index(column) if column in columns else -1

	def columns(self, version = -1):
		if version < Vista.VERSION_BASE: version = self.__version

		return self.__columns(version, version)

	def name(self):
		return self.__name

	def version(self):
		return self.__version

	def copy(self, version_from = -1, version_to = -1):
		if version_from < Vista.VERSION_BASE: version_from = self.__version_from
		if version_to < Vista.VERSION_BASE: version_to = self.__version

		columns = self.__columns(version_from, version_to)
		if len(columns) == 0: return None

		copy_statement = self.__version_statements.get((version_to, ListaTable.STATEMENT_COPY), ListaTable.DEFAULT_COPY)

		return "{0} INTO {1}({2}) SELECT {3} FROM copydb.{1}".format(
			copy_statement
			, self.__name
			, ", ".join(columns)
			, ", ".join([ "copydb.{0}.{1}".format(self.__name, n) for n in columns ])
		)

	def insert(self, columns = [], version = -1):
		if version < Vista.VERSION_BASE: version = self.__version

		self.__check_columns(version)

		if not columns:
			columns = self.__version_columns[version - Vista.VERSION_BASE]
		elif not set(columns).issubset(set(self.__version_columns[version - Vista.VERSION_BASE])):
			raise Exception("Invalid column(s) for INSERT into {0}: {1}".format(
				self.__name
				, ", ".join(set(columns).difference(set(self.__version_columns[version - Vista.VERSION_BASE])))
			))

		if len(columns) == 0: return None

		ins_statement = self.__version_statements.get((version, ListaTable.STATEMENT_INSERT), ListaTable.DEFAULT_INSERT)

		return "{0} INTO {1}({2}) VALUES({3})".format(
			ins_statement
			, self.__name
			, ", ".join(columns)
			, ", ".join([ "?" for i in range(len(columns)) ])
		)

	def update(self, id_columns, id, columns = [], version = -1):
		if version < Vista.VERSION_BASE: version = self.__version

		# we work with id as tuple for cases when id is complex
		# of two or three columns
		if not (isinstance(id, list) or isinstance(id, tuple)):
			id = [id]
		if not (isinstance(id_columns, list) or isinstance(id_columns, tuple)):
			id_columns = [id_columns]
		if len(id_columns) != len(id):
			raise Exception("Unequal count of ids and values ({}, {})"
						.format(str(id), str(id_columns)))
		if not (isinstance(columns, list) or isinstance(columns, tuple)):
			columns = [columns]

		self.__check_columns(version)

		# c_columns used to check id columns too
		c_columns = columns.copy()
		c_columns.extend(id_columns)

		if not columns:
			columns = self.__version_columns[version - Vista.VERSION_BASE]
		elif not set(c_columns).issubset(set(self.__version_columns[version - Vista.VERSION_BASE])):
			raise Exception("Invalid column(s) for INSERT into {0}: {1}".format(
				self.__name
				, ", ".join(set(c_columns).difference(set(self.__version_columns[version - Vista.VERSION_BASE])))
			))

		if len(columns) == 0: return None

		where_statement = []
		for index in range(len(id_columns)):
			key = id_columns[index]
			val = id[index]
			where_statement.append("{} = {}".format(key, val))
		where_statement = ', '.join(where_statement)
		set_statement = ', '.join(list("{} = ?".format(col) for col in columns))

		return "UPDATE {0} SET {1} WHERE {2}".format(
			self.__name
			, set_statement
			, where_statement
		)


	def create(self, version = -1):
		if version < Vista.VERSION_BASE: version = self.__version

		self.__check_columns(version)

		attributes = self.__version_attributes[version - Vista.VERSION_BASE]
		if len(attributes) == 0: return None

		return "CREATE TABLE {0}({1})".format(
			self.__name
			, ", ".join(attributes)
		)

	def exists(self, version = -1):
		return "SELECT 1 from sqlite_master where name='{0}'".format(self.__name)

	def select(self, version = -1, where={}):
		if version < Vista.VERSION_BASE: version = self.__version

		order_by = self.__version_statements.get((version, ListaTable.STATEMENT_SELECT_ORDER), ListaTable.DEFAULT_SELECT_ORDER)
		order_clause = " ORDER BY {0}".format(order_by) if order_by else ""

		where_statement = ''
		if len(where.keys()) != 0:
			where_statement = []
			for key in where.keys():
				val = where[key]
				where_statement.append("{} = {}".format(key, val))
			where_statement = ', '.join(where_statement)
			where_statement = ' WHERE {} '.format(where_statement)

		return "SELECT * from {0}{2}{1}".format(self.__name, order_clause, where_statement)

# ===============================================
# ================ LISTA TABLES =================
# ===============================================

class ListaFormat(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "format", version, (
				"version INTEGER NOT NULL DEFAULT({0})".format(version),
			)
		)

	def copy(self, version_from = -1, version_to = -1):
		return None

	def insert(self, columns = [], version = -1):
		return "INSERT OR REPLACE INTO {0}(version) VALUES({1})".format(self.name(), self.version())

class ListaApi(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "api", version, (
				"sending_type INTEGER NOT NULL DEFAULT(0)"
				, "sending_url TEXT"
				, "session_key TEXT"
				, "session_key_name TEXT"
				, "flags INTEGER NOT NULL DEFAULT(0)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_INSERT, "INSERT OR IGNORE")

class ListaStatuses(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "statuses", version)

		self._set_version_columns(1, (
				"id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "name TEXT NOT NULL"
				, "color TEXT"
				, "icon BLOB"
			)
		)
		self._set_version_columns(2, (
				"id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "name TEXT NOT NULL"
				, "color TEXT"
				, "icon BLOB"
				, "order_no INTEGER NOT NULL"
			)
		)
		self._set_version_statement(2, ListaTable.STATEMENT_SELECT_ORDER, "order_no, id")

class ListaFiles(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "files", version, (
				"id INTEGER PRIMARY KEY NOT NULL "
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "task_id INTEGER"
				, "task_name TEXT"
				, "url TEXT"
				, "name TEXT"
				, "duration INTEGER"
				, "fps INTEGER"
			)
		)

class ListaFileStatus(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_status", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "status_id INTEGER"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
				, "FOREIGN KEY(status_id) REFERENCES statuses(id)"
			)
		)

class ListaVersions(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "versions", version, (
				"id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "file_id INTEGER NOT NULL"
				, "created_utc INTEGER NOT NULL"
				, "name TEXT NOT NULL"
				, "event_id INTEGER"
				, "group_id INTEGER"
				, "duration INTEGER"
				, "fps INTEGER"
				, "path TEXT"
				, "download_url TEXT"
				, "download_path TEXT"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaFileAb(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_ab", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "version_a INTEGER NOT NULL"
				, "version_b INTEGER"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
				, "FOREIGN KEY(version_a) REFERENCES versions (id)"
				, "FOREIGN KEY(version_b) REFERENCES versions (id)"
			)
		)

class ListaFileOrder(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_order", version, (
				"number INTEGER PRIMARY KEY AUTOINCREMENT"
				, "file_id INTEGER NOT NULL UNIQUE"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

	def copy(self, version_from = -1, version_to = -1):
		return "INSERT OR IGNORE INTO {0}(file_id) SELECT copydb.{0}.file_id FROM copydb.{0} ORDER BY copydb.{0}.number".format(
			self.name()
		)

	def insert(self, columns = [], version = -1):
		return "INSERT OR IGNORE INTO {0}(file_id) VALUES (?)".format(self.name())

class ListaCurUser(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "cur_user", version, (
				"id INTEGER NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "firstname TEXT NOT NULL"
				, "lastname TEXT"
				, "email TEXT"
				, "avatar BLOB"
			)
		)

class ListaUsers(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "users", version, (
				"id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "firstname TEXT NOT NULL"
				, "lastname TEXT"
				, "email TEXT"
				, "avatar BLOB"
			)
		)

class ListaFileChanges(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_changes", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaCurState(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "cur_state", version, (
				"file_id INTEGER NOT NULL"
				, "frame INTEGER"
				, "comment_id  INTEGER"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_SELECT_ORDER, "file_id")

class ListaAspects(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "aspects", version, (
				"file_id INTEGER PRIMARY KEY"
				, "flags INTEGER DEFAULT(0)"
				, "aspect REAL NOT NULL"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_COPY, "INSERT OR REPLACE")

class ListaTails(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "tails", version, (
				"file_id INTEGER PRIMARY KEY"
				, "flags INTEGER DEFAULT(0)"
				, "at_begin INTEGER NOT NULL"
				, "at_end INTEGER NOT NULL"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_COPY, "INSERT OR REPLACE")

class ListaMark(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "mark", version, (
				"file_id INTEGER PRIMARY KEY"
				, "flags INTEGER DEFAULT(0)"
				, "frame INTEGER NOT NULL"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaLoop(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "playback_loop", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "flags INTEGER DEFAULT(0)"
				, "frame NOT NULL"
				, "duration INTEGER NOT NULL"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaOnionSkin(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "onion_skin", version, (
				"flags INTEGER NOT NULL DEFAULT(0)"
				, "left INTEGER NOT NULL DEFAULT(1)"
				, "right INTEGER NOT NULL DEFAULT(1)"
			)
		)

class ListaViewport(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "viewport", version, (
				"flags INTEGER NOT NULL  DEFAULT(0)"
				, "compare_mode INTEGER NOT NULL DEFAULT(0)"
				, "pan_x INTEGER NOT NULL DEFAULT(0)"
				, "pan_y INTEGER NOT NULL DEFAULT(0)"
				, "zoom INTEGER NOT NULL DEFAULT(100)"
			)
		)

	def insert(self, columns = [], version = -1):
		return "INSERT OR REPLACE INTO {0}(flags) VALUES (0)".format(self.name())

class ListaTools(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "tools", version)

		self._set_version_columns(1, (
				"flags INTEGER NOT NULL DEFAULT(0)"
				, "tool INTEGER NOT NULL DEFAULT(1)"
				, "size INTEGER NOT NULL DEFAULT(8)"
				, "color TEXT NOT NULL DEFAULT('#FF4072') "
				, "transparency INTEGER NOT NULL DEFAULT(0) "
			)
		)
		self._set_version_columns(2, (
				"flags INTEGER NOT NULL DEFAULT(0)"
				, "tool INTEGER NOT NULL DEFAULT(1)"
				, "size INTEGER NOT NULL DEFAULT(8)"
				, "size_eraser INTEGER NOT NULL DEFAULT(8)"
				, "color TEXT NOT NULL DEFAULT('#FF4072') "
				, "transparency INTEGER NOT NULL DEFAULT(0) "
			)
		)

	def insert(self, columns = [], version = -1):
		return "INSERT OR REPLACE INTO {0}(tool) VALUES (0)".format(self.name())

class ListaRender(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "render", version)

		self._set_version_columns(1, (
				"flags INTEGER NOT NULL DEFAULT(0)"
				, "metadata TEXT"
				, "lut TEXT"
				, "aspect REAL NOT NULL DEFAULT(1.77777777777778)"
				, "letterboxing REAL NOT NULL DEFAULT(1.77777777777778)"
				, "letterboxing_transparency INTEGER NOT NULL DEFAULT(15)"
				, "watermark TEXT"
			)
		)
		self._set_version_columns(2, (
				"flags INTEGER NOT NULL DEFAULT(0)"
				, "metadata TEXT"
				, "lut TEXT"
				, "aspect REAL NOT NULL DEFAULT(1.77777777777778)"
				, "letterboxing REAL  NOT NULL DEFAULT(1.77777777777778)"
				, "letterboxing_transparency INTEGER NOT NULL DEFAULT(15)"
				, "watermark TEXT"
				, "sequence_quality INTEGER DEFAULT(-1)"
			)
		)

	def insert(self, columns = [], version = -1):
		return "INSERT OR REPLACE INTO {0}(flags) VALUES (0)".format(self.name())

class ListaComments(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "comments", version, (
				"file_id INTEGER NOT NULL"
				, "comment_id INTEGER NOT NULL"
				, "number_comment INTEGER NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "create_utc INTEGER"
				, "frame INTEGER NOT NULL"
				, "duration INTEGER NOT NULL"
				, "version_id INTEGER NOT NULL"
				, "user_id INTEGER NOT NULL"
				, "mark_x REAL NOT NULL DEFAULT(0)"
				, "mark_y REAL NOT NULL DEFAULT(0)"
				, "comment TEXT"
				, "PRIMARY KEY(file_id, comment_id)"
				, "FOREIGN KEY(user_id) REFERENCES users(id)"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_SELECT_ORDER, "file_id, comment_id")

class ListaBitmaps(ListaTable):
	TYPE_MACROS = 0
	TYPE_BITMAP = 1
	TYPE_PEN = 2
	TYPE_RECT = 3
	TYPE_ELLIPSE = 4
	TYPE_ARROW = 5
	TYPE_LINE = 6
	TYPE_TEXT = 7

	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "bitmaps", version)

		self._set_version_columns(1, (
				"file_id INTEGER NOT NULL"
				, "comment_id INTEGER NOT NULL"
				, "number_bitmap INTEGER NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "type INTEGER NOT NULL"
				, "frame INTEGER NOT NULL"
				, "version_id INTEGER NOT NULL"
				, "pos_x REAL NOT NULL DEFAULT(0)"
				, "pos_y REAL NOT NULL DEFAULT(0)"
				, "pos_z REAL NOT NULL DEFAULT(0)"
				, "scale REAL NOT NULL DEFAULT(1)"
				, "width INTEGER NOT NULL DEFAULT(0)"
				, "height INTEGER NOT NULL DEFAULT(0)"
				, "data BLOB NOT NULL"
				, "PRIMARY KEY(file_id, comment_id, number_bitmap)"
				, "FOREIGN KEY(file_id, comment_id) REFERENCES comments(file_id, comment_id)"
			)
		)

		self._set_version_columns(2, (
				"file_id INTEGER NOT NULL"
				, "comment_id INTEGER NOT NULL"
				, "number_bitmap INTEGER NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "type INTEGER NOT NULL"
				, "frame INTEGER NOT NULL"
				, "duration INTEGER NOT NULL DEFAULT(0)"
				, "version_id INTEGER NOT NULL"
				, "pos_x REAL NOT NULL DEFAULT(0)"
				, "pos_y REAL NOT NULL DEFAULT(0)"
				, "pos_z REAL NOT NULL DEFAULT(0)"
				, "scale REAL NOT NULL DEFAULT(1)"
				, "width INTEGER NOT NULL DEFAULT(0)"
				, "height INTEGER NOT NULL DEFAULT(0)"
				, "data BLOB NOT NULL"
				, "PRIMARY KEY(file_id, comment_id, number_bitmap)"
				, "FOREIGN KEY(file_id, comment_id) REFERENCES comments(file_id, comment_id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_COPY, "INSERT OR REPLACE")

class ListaAnswers(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "answers", version, (
				"file_id INTEGER NOT NULL"
				, "comment_id INTEGER NOT NULL"
				, "number_reply INTEGER NOT NULL"
				, "user_id INTEGER NOT NULL"
				, "create_utc INTEGER NOT NULL"
				, "comment TEXT NOT NULL"
				, "PRIMARY KEY(file_id, comment_id, number_reply)"
				, "FOREIGN KEY(user_id) REFERENCES users(id)"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_COPY, "INSERT OR REPLACE")

class ListaCommentsWatched(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "comments_watched", version, (
				"file_id INTEGER NOT NULL"
				, "comment_id INTEGER NOT NULL"
				, "user_id INTEGER NOT NULL"
				, "watch_utc INTEGER"
				, "PRIMARY KEY (file_id, comment_id, user_id)"
				, "FOREIGN KEY(user_id) REFERENCES users(id)"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

		for i in range(Vista.VERSION_BASE, version + 1):
			self._set_version_statement(i, ListaTable.STATEMENT_COPY, "INSERT OR REPLACE")

class ListaFileGenerated(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_generated", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "thumbs TEXT"
				, "pdf TEXT"
				, "mov TEXT"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaSupport(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "support", version, (
				"file_id INTEGER PRIMARY KEY NOT NULL"
				, "tiff_comments TEXT"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

class ListaFileExported(ListaTable):
	def __init__(self, version=Vista.VERSION):
		ListaTable.__init__(self, "file_exported", version, (
				"file_id INTEGER NOT NULL"
				, "export_id INTEGER NOT NULL"
				, "flags INTEGER NOT NULL DEFAULT(0)"
				, "export_file TEXT"
				, "export_thumbs TEXT"
				, "PRIMARY KEY(file_id, export_id)"
				, "FOREIGN KEY(file_id) REFERENCES files(id)"
			)
		)

# ===============================================
# =================== HELPERS ===================
# ===============================================

def unpack_single(array, format, start = 0):
	end = start + struct.calcsize(format)
	return struct.unpack(format, array[start : end])[0], end

def unpack_string(array, start = 0):
	end = start + struct.calcsize(">i")
	text_length = struct.unpack(">i", array[start : end])[0]
	if text_length > 0:
		val, end = unpack_single(array, ">{}s".format(text_length), end)
		return val.decode("utf-8"), end
	return u"", end

def unpack_color(array, start = 0):
	end = start + struct.calcsize(">b5H")
	_, c_a, c_r, c_g, c_b, _ = struct.unpack(">b5H", array[start : end])
	color_hex = "#{:0>2X}{:0>2X}{:0>2X}{:0>2X}".format(c_r >> 8, c_g >> 8, c_b >> 8, c_a >> 8)
	return color_hex, end
