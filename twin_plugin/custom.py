import cerebro
import xml.etree.ElementTree as ET
import platform, time

import twin_plugin.examples
import twin_plugin.pycerebro as pycerebro

from threading import *

def config_read():
    if platform.system()=='Windows': config_file = 'z:/config/config.xml'

    tree = ET.parse(config_file)
    root = tree.getroot()

    dict = {}
    for child in root.attrib:
        dict[child]= root.attrib[child]
    return dict



def refresh_seq_length(tasks_seq = None, frames_dict={}):
    if tasks_seq: tasks = tasks_seq
    else: tasks = cerebro.core.selected_tasks()
    cerebro.core.print_error('tasks_seq: '  + ' ' + repr(tasks))
    for task in tasks:
        id = task.id()
#         continue
        tags_seq = task.tags()
        tag_frames_seq=None
        for tag_seq in tags_seq:
            if tag_seq.name()=='frames': tag_frames_seq=tag_seq

        
        children_tasks = cerebro.core.task_children(id)
        sum = 0
        
        for child_task in children_tasks:
            
            task_full_path = child_task.parent_url() + child_task.name()
            if task_full_path in frames_dict:
                sum +=frames_dict[task_full_path]
                cerebro.core.print_error('FOUND:' + task_full_path + ' in dictionary')
                continue
            else: cerebro.core.print_error('NOT FOUND:' + task_full_path + ' in dictionary')
            
            
            tags = child_task.tags()
            tag_frames=None
            for tag in tags:
                if tag.name()=='frames': tag_frames=tag
            
            if tag_frames and tag_frames.value():
                cerebro.core.print_error('tag_frames: '  + ' ' + repr(tag_frames.value()))
                try: sum+=tag_frames.value(); cerebro.core.print_error(' sum: ' + str(tag_frames.value()))
                except: cerebro.core.print_error('Could not sum: ' + str(tag_frames.value()))
            
#             cerebro.core.print_error('Child task name: ' + repr(child_task.name()))
        
        if not sum==0: tag_frames_seq.set_value(sum)
#             subtask = cerebro.core.task(child_id) 
            
            
            
            
def analyze_task(task):
    status = task.status()
    status_id=status[0]
    name = status[1]
    if status_id==0:task.set_progress(0.0);return status_id, name # IF no status
    if name=='in progress': task.set_progress(47.0)
    elif name=='ready to start': task.set_progress(0.0)
    elif name=='to correction': task.set_progress(51.0)
    elif name=='completed': task.set_progress(100.0)
    elif name=='paused':pass
    elif name=='pending review':pass
    else:pass
    return status_id, name

def update_frames(tasks=None):

    if not tasks: tasks = cerebro.core.selected_tasks()

    ##################################
    parent_tasks = []
    for task in tasks:
        parent_id = task.parent_id()
        parent_task = cerebro.core.task (parent_id)
        parent_tasks.append(parent_task)
    parent_tasks = set (parent_tasks)
    parent_tasks = list (parent_tasks)
    ##################################

    frames_dict={}
    

    for task in tasks:
        
#         parent_url = task.parent_url()
#         task_name = task.name()
        task_full_path = task.parent_url() + task.name()
        
        tags = task.tags()
        tag_start, tag_end, tag_frames=None, None, None
        for tag in tags:
            if tag.name()=='start_frame': tag_start=tag
            if tag.name()=='end_frame': tag_end=tag
            if tag.name()=='frames': tag_frames=tag
#             if tag.name()=='temporal': cerebro.gui.information_box('Error', 'Temporal')
        if tag_start:
            if tag_end:
                if tag_frames: 
    
                    st_frame = tag_start.value()
                    end_frame = tag_end.value()
                    
                    try:
                        value = end_frame - st_frame +1
                        tag_frames.set_value(value)
                        frames_dict[task_full_path]=value
                    except:
                        tag_frames.set_value(0)
                        frames_dict[task_full_path]=0
                        
    refresh_seq_length(tasks_seq = parent_tasks, frames_dict = frames_dict)
#                     if tag_start.value():
#                         if tag_end.value():
#                             value = st_frame + end_frame+1
#                             tag_frames.set_value(value)
#                         tag_frames.set_value(11111)
#                     tag_frames.set_value(11111)

#                     if not tag_start.value(): cerebro.core.print_error(tag_start.name() + '  --- EMPTY VALUE')
#                     else: cerebro.core.print_error(tag_start.name() + ': '+repr(tag_end.value()))
#                      
#                     if not tag_end.value(): cerebro.core.print_error(tag_end.name() + '  --- EMPTY VALUE')
#                     else: cerebro.core.print_error(tag_end.name() + ': '+repr(tag_end.value()))
#                      
#                     if not tag_frames.value(): cerebro.core.print_error(tag_frames.name() + '  --- EMPTY VALUE')
#                     else: cerebro.core.print_error(tag_frames.name() + ': '+repr(tag_frames.value()))
