# -*- coding: utf-8 -*-
"""
Mirada playlist format OTIO adapter

"""

import os
import sys
import time

# File is imported directly by OTIO
from pycerebro.vista import *


OTIO_VAR = "OTIO_PLUGIN_MANIFEST_PATH"
OTIO_FILE_PREFIX = "file://"
OTIO_MANIFEST = "vista.plugin_manifest.json"


def setup_otio():
	"""
	Ensure Vista adapter is available in OTIO
	"""
	env_value = [ i for i in os.environ.get(OTIO_VAR, "").split(os.pathsep) if len(i) ]
	manifest_location = os.path.normpath(os.path.join(os.path.dirname(__file__), OTIO_MANIFEST))
	
	if not manifest_location in env_value:
		env_value.append(manifest_location)
		os.environ[OTIO_VAR] = os.pathsep.join(env_value)
		
		if "opentimelineio" in sys.modules:
			import opentimelineio as otio
			# Reload manifest
			otio.plugins.ActiveManifest(True)

def parseInt(strval, default = 0):
	"""
	No exception int(str) helper
	"""
	try:
		return int(strval)
	except:
		return default

def supportFps(fps):
	# SMPTE support
	conversion = {
		23: 23.98,
		24: 24,
		25: 25,
		29: 29.97,
		30: 30,
		47: 47.95,
		48: 48,
		50: 50,
		59: 59.94,
		60: 60,
		95: 95.90,
		96: 96,
		119: 119.88,
		120: 120
	}
	
	#if fps in [24, 25, 30, 48, 50, 60, 96, 120]:
	#	return fps

	return conversion.get(fps, fps)

def read_from_file(filepath):
	"""
	Generate OTIO timeline based on Vista playlist
	"""
	import opentimelineio as otio
	from pathlib import Path
	
	timeline = otio.schema.Timeline()
	timeline.name = "Cerebro Mirada Export"
	#timeline.metadata["cerebro"] = {
	#	"taskId": ""
	#}
	
	lista = Vista()
	lista.set_lista(filepath)
	
	t_versions = ListaVersions()
	t_files = ListaFiles()
	t_file_ab = ListaFileAb()
	t_file_order = ListaFileOrder()
	t_tails = ListaTails()
	t_comments = ListaComments()
	
	qversions = lista.query(t_versions.select())
	qfiles = lista.query(t_files.select())
	qfiles_ab = lista.query(t_file_ab.select())
	qfiles_order = lista.query(t_file_order.select())
	qfiles_tails = lista.query(t_tails.select())
	qcomments = lista.query(t_comments.select())
	
	cversions = { col: i for i, col in enumerate(t_versions.columns()) }
	cfiles = { col: i for i, col in enumerate(t_files.columns()) }
	cfiles_tails = { col: i for i, col in enumerate(t_tails.columns()) }
	ccomments = { col: i for i, col in enumerate(t_comments.columns()) }
	
	file_ids = [ i[1] for i in sorted(qfiles_order, key=lambda fo: fo[0]) ]
	file_versions = { i[0]: (i[1], i[2]) for i in qfiles_ab }
	file_tails = { i[0]: i for i in qfiles_tails }
	files = { i[0]: i for i in qfiles }
	versions = { i[0]: i for i in qversions }
	comments = { file_id: {} for file_id in file_ids }
	
	for comment in qcomments:
		comments[comment[ccomments["file_id"]]][comment[ccomments["comment_id"]]] = {
			"user_id": comment[ccomments["user_id"]]
			, "comment": comment[ccomments["comment"]]
			, "number_comment": comment[ccomments["number_comment"]]
			, "frame": comment[ccomments["frame"]]
			, "duration": comment[ccomments["duration"]]
		}
	
	for ver_num, ver_name in enumerate(['A', 'B']):
		track = otio.schema.Track()
		track.name = "Mirada Track {}".format(ver_name)
		
		frame_start = 0
		
		for file_id in file_ids:
			tail_begin = 0
			tail_end = 0
			file_duration = parseInt(files[file_id][cfiles["duration"]])
			file_fps = parseInt(files[file_id][cfiles["fps"]])
			
			# Only video/audio tracks are accepted by OTIO
			if file_duration < 2: continue
			
			if file_id in file_tails:
				tail_begin = file_tails[file_id][file_tails["at_begin"]]
				tail_end = file_tails[file_id][file_tails["at_end"]]
			
			ver_id = file_versions[file_id][ver_num]
			
			if ver_id is not None:
				ver_duration = parseInt(versions[ver_id][cversions["duration"]])
				ver_fps = supportFps(parseInt(versions[ver_id][cversions["fps"]]))
				ver_path = str(versions[ver_id][cversions["path"]])
				
				# Only video/audio tracks are accepted by OTIO
				if ver_duration < 2: continue
				
				clip = otio.schema.Clip()
				clip.name = str(versions[ver_id][cversions["name"]])
				clip.metadata["cerebro"] = {
					"file_id": str(file_id)
					, "version_id": str(ver_id)
					, "event_id": str(versions[ver_id][cversions["event_id"]])
					, "group_id": str(versions[ver_id][cversions["group_id"]])
					, "task_id": str(files[file_id][cfiles["task_id"]])
				}
				
				# displayed range
				clip.source_range = otio.opentime.TimeRange(
					start_time=otio.opentime.RationalTime(frame_start + tail_begin, ver_fps),
					duration=otio.opentime.RationalTime(file_duration - (tail_begin + tail_end), ver_fps)
				)
				clip.media_reference = otio.schema.ExternalReference(
					target_url=Path(ver_path).as_uri(),
					# actual file range
					available_range=otio.opentime.TimeRange(
						start_time=otio.opentime.RationalTime(frame_start, ver_fps),
						duration=otio.opentime.RationalTime(ver_duration, ver_fps)
				  )
				)
				
				for comment_id, comment in comments[file_id].items():
					marker = otio.schema.Marker()
					marker.marked_range = otio.opentime.TimeRange(
						start_time=otio.opentime.RationalTime(comment["frame"], ver_fps),
						duration=otio.opentime.RationalTime(comment["duration"], ver_fps)
					)
					marker.name = comment["comment"] if comment["comment"] else ''
					marker.color = otio.schema.Marker.Color.BLUE
					marker.comment = "Cerebro Mirada comment {}".format(comment["number_comment"])
					marker.metadata["cerebro"] = {
						"user_id": comment["user_id"]
						, "number_comment": comment["number_comment"]
						, "frame": comment["frame"]
						, "duration": comment["duration"]
					}
					
					clip.markers.append(marker)
				
				track.append(clip)
			
			frame_start += file_duration + 1
		
		if len(track) > 0:
			timeline.tracks.append(track)
	
	return timeline

def write_to_file(input_otio, filepath):
	"""
	Generate Vista playlist based on OTIO timeline
	"""
	import opentimelineio as otio
	
	lista = Vista()
	lista.create_lista(lista_path=filepath)
	
	iter_file_id = (i for i in range(-3, -1000000, -1))
	iter_version_id = (i for i in range(-3, -1000000, -1))
	
	file_order = []
	file_versions = {}
	files = {}
	versions = {}
	
	if input_otio.tracks and len(input_otio.tracks):
		for track in input_otio.tracks[:2]:
			for clip in track:
				ver_name = clip.name
				ver_path = clip.media_reference.target_url
				ver_meta = clip.metadata.get("cerebro", {})
				
				ver_start = clip.source_range.start_time.value
				ver_duration = clip.source_range.duration.value
				ver_fps = clip.source_range.start_time.rate
				ver_id = ver_meta.get("version_id", next(iter_version_id))
				
				file_start = clip.visible_range().start_time.value
				file_duration = clip.visible_range().duration.value
				file_fps = clip.visible_range().start_time.rate
				
				ver_path = ver_path[ver_path.startswith(OTIO_FILE_PREFIX) and len(OTIO_FILE_PREFIX):].lstrip("\\/")
				if len(ver_path) > 1 and ver_path[1] != ':': ver_path = "//" + ver_path
				
				if file_start not in files:
					files[file_start] = {
						"start": file_start
						, "duration": file_duration
						, "fps": file_fps
						, "name": ver_name
						, "id": ver_meta.get("file_id", next(iter_file_id))
						, "task_id": ver_meta.get("task_id", None)
					}
					
					file_versions[files[file_start]["id"]] = []
					file_order.append(file_start)
				
				versions[ver_id] = {
					"start": ver_start
					, "duration": ver_duration
					, "fps": ver_fps
					, "name": ver_name
					, "path": ver_path
					, "id": ver_id
					, "file_id": files[file_start]["id"]
					, "group_id": ver_meta.get("group_id", None)
					, "event_id": ver_meta.get("event_id", None)
					, "id": ver_id
				}
				
				file_versions[files[file_start]["id"]].append(ver_id)
	
	for file_start in file_order:
		lista.insert_file({
			"id": files[file_start]["id"]
			, "flags": 0
			, "task_id": files[file_start]["task_id"]
			, "name": files[file_start]["name"]
			, "duration": files[file_start]["duration"]
			, "fps": files[file_start]["fps"]
		})
	
	for ver_id, version in versions.items():
		lista.insert_version({
			"id": ver_id
			, "flags": 0
			, "file_id": versions[ver_id]["file_id"]
			, "created_utc": parseInt(time.time() * 1000)
			, "name": versions[ver_id]["name"]
			, "event_id": versions[ver_id]["event_id"]
			, "group_id": versions[ver_id]["group_id"]
			, "duration": versions[ver_id]["duration"]
			, "fps": versions[ver_id]["fps"]
			, "path": versions[ver_id]["path"]
		})
	
	for file_id, ver_list in file_versions.items():
		lista.insert_ab(
			file_id
			, ver_list[0]
			, ver_list[1] if len(ver_list) > 1 else None
		)
	
	return
