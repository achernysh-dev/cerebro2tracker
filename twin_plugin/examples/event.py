# -*- coding: utf-8 -*-
"""
The example shows message creation, task creation and progress altering event handling.
Below we will: 

a) check if a file is being attached while posting a new report;
b) make a newly created task highly prioritized if it starts today;
c) ask a user for a confirmation if he/she is lowering the progress value down.

The functions:

before_event() - the action before changing data
after_event() - the action after changing data
error_event() - data change error handling
"""

import cerebro
import datetime, time
import twin_plugin.custom as custom

def before_event(event):	
	
	# Checking if a new report being posted contains attachment(-s)
	if event.event_type() == event.EVENT_CREATION_OF_MESSAGE: # if the event type is "Creation of message"		
		if event.type() == event.TYPE_REPORT: # if the new message is "Report"
			
			attachs = event.new_attachments() # getting all attachments to the message
			if len(attachs) == 0: # if there are no attachments there, raising an exception
				raise Exception('Please attach a file to your report') 
				# The report will not be posted, the user will be displayed a window with this text instead.
	
	# Asking a user for a confirmation when he/she is trying to lower the task progress down
	elif event.event_type() == event.EVENT_CHANGING_OF_TASKS_PROGRESS: # if the event type is "Changing of task progress"
		
		tasks = event.tasks() # getting tasks being changed
		new_progress = event.new_value() # getting the progress value input by user
		for task in tasks: # checking if the new value is higher or lower than the old one
			if new_progress < task.progress(): # if the new progress value is lower, then:
				# asking the user for a confirmation
				q = 'Are you sure you want to lower the "'+task.name()+'" task progress?'
				if cerebro.gui.question_box('Changing of progress',  q) == False: # if the user is not sure, then:
					raise Exception('') 
				# the progress change will not be saved




def after_event(event):
	cerebro.core.print_error('Entering event def')	
	
	# a newly created task highly prioritized if it starts today
	if event.event_type() == event.EVENT_CREATION_OF_TASK: # if the event type is "Creation of task"
		
		start = event.start() # getting the task starting time		
		delta = start - datetime.datetime.now()	
		if delta.days == 0 or delta.days == -1: # if today is the starting date
			event.set_priority(event.PRIORITY_HIGHT) # the task is attributed with "High Priority"	
	if event.event_type() == 121: #if it is a change tag field event
		tasks = event.tasks()
		custom.update_frames(tasks) # perform the update
		
		#return
		
# 		parent_tasks = []
# 		for task in tasks:
# 			parent_id = task.parent_id()
# 			parent_task = cerebro.core.task (parent_id)
# 			parent_tasks.append(parent_task)
# 		parent_tasks = set (parent_tasks)
# 		parent_tasks = list (parent_tasks)
# 		
# 		cerebro.core.refresh_all()
# 		custom.refresh_seq_length(parent_tasks)
# 		
# 		cerebro.core.refresh_all()
# 		custom.refresh_seq_length(parent_tasks) # perform the refresh the 2nd time to be sure
# 		cerebro.core.print_error(repr(dir(event)))
			
			
	if event.event_type() == 123: #if it is a SWITCH STATUS event
		tasks = event.tasks()
		for task in tasks:
			custom.analyze_task(task)
# 			cerebro.core.print_error('CHANGED TASK STATUS to'+repr(name))	


def error_event(error, event):		
	print('Event error',  event.type_str(),  error)	
