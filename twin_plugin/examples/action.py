# -*- coding: utf-8 -*-
"""
Этот пример покажет как работать с элементами меню и кнопками приложения.
В примере рассмотрена работа с главным меню, контексными меню задач, сообщений и вложений.

Функции:

main() - функция для запуска примера
remove_menu() - удаляет и скрывает меню приложения
add_menu() - Создает меню приложения

hello_user() - Приветствие пользователя
hello_administrator() - Приветствие администратора
task_info() - заглушка для действия с чекбоксом
task_info_show() - Показать информацию о сообщении
message_text() - Показать текст сообщения
message_id() - показать ID сообщения
attach_size() - Показать размер вложения
"""


import cerebro, time, json, os, datetime
from operator import itemgetter
import twin_plugin.pycerebro as pycerebro
import twin_plugin.custom as custom
import twin_plugin.uic as uic
import shutil
# import twin_plugin.examples.event as event


# from PyQt6.uic import loadUi

# id_temp = 3096224744668970
task_copy_from_ids=[]
# db=None


def explorer_open(fname):
	cmd = 'explorer "'+fname+'"'
	cmd = cmd.replace('/','\\')
	cmd = cmd.replace('explorer ', 'explorer /select, ')
	os.system(cmd)		

def main():
	# Добавление меню и действий
	add_menu()
# 	db_init()
# 	print ("main started")
	cerebro.core.print_error("by plugin started!")
	# Удаление меню и действий
# 	remove_menu()

def db_init():
	db = pycerebro.database.Database('192.168.50.9', 5432)
	db.connect_from_cerebro_client()
	cerebro.core.print_error("DB = "+repr(db))
	return db

def add_menu():
	# Путь к иконке
	icon = cerebro.core.python_api_dir() + '/examples/icon.png'
# 	cerebro.core.print_error("Cerebro ROOT = "+repr(cerebro.core.python_api_dir()))
	# Добавим в главное меню пользовательское меню
	# mainMenu = cerebro.actions.MainMenu() # Получили главное меню
	# userMenu = mainMenu.add_menu('Glukoza') # добавили пользовательское меню
	# userSubmenu = userMenu.add_menu('Technical') # добавили в пользовательское меню подменю

	current_user = cerebro.core.user_profile() # получили профиль пользователя

	# В пользовательское меню добавим действия
# 	userSubmenu.add_action('twin_plugin.examples.action.hello_user', 'Приветствие', icon) # добавили действие
# 	adminAction = userSubmenu.add_action('examples.action.hello_administrator', 'Приветствие администратора', icon) # добавили действие
	# Сделаем кнопку администратора недоступной для пользователя
# 	if current_user[cerebro.aclasses.Users.DATA_LOGIN] != 'Администратор': # проверяем пользователя
# 		adminAction.set_enabled(False) # Сделали кнопку недоступной

	# Добавим действия в контекстное меню задачи на вкладке навигация
	taskMenu = cerebro.actions.TaskNavigatorMenu() # Получили контестное меню задачи
# 	taskInfoAction = taskMenu.add_action('twin_plugin.examples.action.task_info', 'Информация о задаче(ID + Name)') # добавили действие
	# Сформируем действие для его использование в других меню
# 	act = cerebro.actions.Action('twin_plugin.examples.action.task_info_show', 'Информация о задаче', icon)
# 	taskMenu.add_action(act) # добавили действие
	
	# actCopy = cerebro.actions.Action('twin_plugin.examples.action.copy_task', 'Копирование задачи', icon)
	# taskMenu.add_action(actCopy) # добавили действие
	
	# actPaste = cerebro.actions.Action('twin_plugin.examples.action.paste_task', 'Вставка_задачи', icon)
	# taskMenu.add_action(actPaste) # добавили действие
	
	# actRemoveAssigned = cerebro.actions.Action('twin_plugin.examples.action.remove_all_assigned', 'Удалить ВСЕХ назначенных', icon)
	# userMenu.add_action(actRemoveAssigned) # добавили действие
	
	# tmpButton = cerebro.actions.Action('twin_plugin.examples.action.change_link_for_cam', 'Временная кнопка', icon)
	# userSubmenu.add_action(tmpButton) # добавили действие
	
	# tmpButton = cerebro.actions.Action('twin_plugin.examples.action.export_sel_to_file', 'Временная кнопка (кспорт в файл)', icon)
	# userSubmenu.add_action(tmpButton) # добавили действие
	
	# tmpButton2 = cerebro.actions.Action('twin_plugin.examples.action.sync_asset_path', 'Переброс ассетов по путям', icon)
	# userSubmenu.add_action(tmpButton2) # добавили действие
	
	# preProdLinks = cerebro.actions.Action('twin_plugin.examples.action.make_preprod_links', 'Установить связи препродакшена ', icon)
	# userMenu.add_action(preProdLinks) # добавили действие
	
	
	# refreshSeqLen = cerebro.actions.Action('twin_plugin.custom.refresh_seq_length', 'Refresh sequence length ', icon)
	# userMenu.add_action(refreshSeqLen) # добавили действие
	
	# preProdLinks = cerebro.actions.Action('twin_plugin.custom.update_frames', 'Обновить поле FRAMES', icon)
	# userMenu.add_action(preProdLinks) # добавили действие
	
	# disconnectCam = cerebro.actions.Action('twin_plugin.examples.action.disconnect_cam', 'Разорвать связи задач', icon)
	# userMenu.add_action(disconnectCam) # добавили действие
	
	# testAction = cerebro.actions.Action('twin_plugin.examples.action.test_2', 'Обнулить время задачи', icon)
	# userSubmenu.add_action(testAction) # добавили действие
	
# 	testui = cerebro.actions.Action('twin_plugin.examples.action.testui', 'Test UI', icon)
# 	userMenu.add_action(testui) # добавили действие
	
# 	actAnalyze = cerebro.actions.Action('twin_plugin.examples.action.analyze_this', 'Анализируй это!', icon)
# 	taskMenu.add_action(actAnalyze) # добавили действие
	
# 	taskInfoAction.set_checkable(True) # установили кнопку с чекбоксом

	# Добавим действие в панель инструментов задач
	taskToolBar = cerebro.actions.TaskToolBar() # Получили панель инструментов
	# taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.assign_me_to_task', 'Взять в работу') # вставим меню на предпоследнюю позицию панели инструментов
# 	taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.sync_asset_path', 'Переброс ассетов по путям') # вставим меню на предпоследнюю позицию панели инструментов
	# taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.analyze_this', 'Анализируй это!') # вставим меню на предпоследнюю позицию панели инструментов
	# taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.init_asset', '-= INIT NEW ASSET =-') # вставим меню на предпоследнюю позицию панели инструментов
# 	taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.test', '   test   ') # вставим меню на предпоследнюю позицию панели инструментов
	taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.sync_ui.sync_ui', 'Sync to Tracker') # вставим меню на предпоследнюю позицию панели инструментов
	# taskToolBarUserMenu = taskToolBar.insert_action(taskToolBar.size() - 1,'twin_plugin.examples.action.insert_cache_task', 'Вставить задачу на кэширование') # вставим меню на предпоследнюю позицию панели инструментов
# 	taskToolBarUserMenu.add_action(act) # добавим действие

	# Добавим подменю в контекстное меню сообщения
# 	messageMenu = cerebro.actions.MessageForumMenu()
# 	userMessageMenu = messageMenu.insert_menu(0, 'User Message menu') # вставим меню на первую позицию
# 	messageMenu.insert_separator(1)
# 	userMessageMenu.add_action('twin_plugin.examples.action.message_text', 'Текст сообщения') # добавили действие
# 	userMessageMenu.add_separator() # добавили разделитель
# 	userMessageMenu.add_action('twin_plugin.examples.action.message_creator', 'Автор сообщения') # добавили действие

	# Добавим действие на панель инструментов вложений задачи
# 	attachToolBar = cerebro.actions.AttachmentForumToolBar() # Получили панель инструментов
# 	attachToolBar.add_action('twin_plugin.examples.action.attach_size', 'Размер вложения', icon) # добавили действие


window = None

def test_2():
	import datetime, cerebro.gui

	tasks = cerebro.core.selected_tasks()
	for task in tasks:

		dinput = cerebro.gui.InputDialog(cerebro.gui.InputDialog.TYPE_INT, 'Enter', 'Введите планируемое количество часов на задачу')
		dinput.set_range(0, 100)
		dinput.set_value(4)    
		res = dinput.execute()
		if res == True:
		     print('Entered value:', dinput.value())	
		     task.set_planned_time(float(dinput.value()))
		else: return	 		

		
		start = task.start()
		cerebro.core.print_error('START DATE: ' + repr(start))
		
		datetime_now = datetime.datetime.utcnow()
		datetime_2000 = datetime.datetime(2000, 1, 1)
		timedelta = datetime_now - datetime_2000
		days = timedelta.total_seconds()/(24*60*60)     
		task.set_start(days)
		 		

def  disconnect_cam():
	tasks = cerebro.core.selected_tasks()
	db=db_init()
	for task in tasks:
		
# 		if not db: db=db_init()
		
		try:connections = db.task_links(task.id())
		except: 
			db=db_init()
			connections = db.task_links(task.id())
			
		for conn in connections:
			conn_id = conn[pycerebro.dbtypes.TASK_LINK_ID] 
			try:db.drop_link_tasks(conn_id)
			except:
				db=db_init()
				db.drop_link_tasks(conn_id)
			cerebro.core.print_error('CONNECTION ID: ' + repr(conn_id))
		time.sleep(0.1)
	
	cerebro.gui.information_box('Success', 'Finished')


def test():
# 	db=db_init()
	tasks = cerebro.core.selected_tasks()
		

def insert_cache_task():
	
# 	activ_list = cerebro.core.activities()
# 	cerebro.core.print_error(str(activ_list))
# 	for act in activ_list:
# 		id = activ_list[pycerebro.dbtypes.ACTIVITY_DATA_ID] 
# 		name = activ_list[pycerebro.dbtypes.ACTIVITY_DATA_NAME] 
# 		cerebro.core.print_error('ACTIVITY NAME ' + name)
# 	users = cerebro.core.users()
# 	for user in users.data(): 
# 		cerebro.core.print_error(str(users.data()) + '\n')
# 	return
	
	tasks = cerebro.core.selected_tasks()
	if tasks:

		name = tasks[0].name()
		tasks_num = str( len(tasks) )
		result = cerebro.gui.question_box('Подтверждение', 'Создать ' + tasks_num + ' задач на кэширование после \n' + name)
		cerebro.core.print_error('BUTTON PRESSED : ' + repr(result))
		if not result: return
	else: cerebro.gui.information_box('Error', 'Выдели задачу');return
	
	db=db_init()
	
	for task in tasks:
	
# 		task = tasks[0]
		task_id = task.id()
		parent_id = task.parent_id()
		try: activity = task.activity()[0]
		except: activity=0
		connections = db.task_links(task_id)
		
		conn_list = []
		
		for conn in connections:
			conn_id = conn[pycerebro.dbtypes.TASK_LINK_ID]
	# 		conn_dict[conn_id] = {}
			dest_task_id = conn[pycerebro.dbtypes.TASK_LINK_DST]
			if not task_id==dest_task_id: conn_list.append([dest_task_id, conn_id])
	# 		conn_dict[conn_id] ['dest_task_id'] = dest_task_id
	# 		dest_task_status = conn[pycerebro.dbtypes.TASK_LINK_DEL ]
	# 		task_conn = cerebro.core.task(dest_task_id)
	# 		task_name = task_conn.name()
			cerebro.core.print_error('connections NAME: ' + str(task_id) + ', '+ str(dest_task_id))
		new_task_id = db.add_task(parent_id, 'cache', activity)
		cerebro.core.print_error('CACHE task created, id ' + str(new_task_id))
		
		time.sleep(1)
		
		set_task_to_status(new_task_id, 'ready to start')
		task_unsubscribe_all(new_task_id, db)
		
		# Subscribe users
		
		
		for con_id, connection_id in conn_list:
			db.set_link_tasks(new_task_id, con_id)
			db.drop_link_tasks(connection_id)
	
	
	# 	cerebro.core.print_error('DEST links created ')
		db.set_link_tasks(task_id, new_task_id)
	# 	cerebro.core.print_error('SCR links created ')
		
	# 	conn_tasks = connections #[pycerebro.dbtypes.TASK_LINK_ID ]
	# 	cerebro.core.print_error('connections ID: ' + str(conn_tasks))
	
		
	

def init_asset():
	tasks = cerebro.core.selected_tasks()
	
	if not tasks: 
		msg = 'Select a task' # сформировали сообщение
		cerebro.gui.information_box('Error', msg) # показали сообщение
		return 
	task = tasks[0]
	if  not task.name()=='Modeling':
		cerebro.gui.information_box('Error', 'Select a Modeling task') # показали сообщение
		return
	tags = task.tags()
	task_tag=None
	for tag in tags:
		cerebro.core.print_error (  tag.name() + ' ' + str(tag.type() ))
		if tag.name()=='Asset_file': task_tag=tag
	if  not task_tag:
		cerebro.gui.information_box('Error', 'No tag Asset_file') # показали сообщение
		return
	# we have got the tag instance
	
	data = custom.config_read()
	root = data['cerebro_root_disk_root']
	root = json.loads(root)
	root = root['/BABA_YAGA']
	cerebro.core.print_error (  'DATA  ' + root)
	
	
	#form the path for the new asset
	tokens = task.parent_url().split('/')
	asset_name = tokens[len(tokens)-2]
	new_folder=''
	for name in tokens[1:-1]:
		new_folder+=name+'/'
	
	
# 	cerebro.core.print_error ( repr(tokens))
	new_folder =  new_folder.replace(tokens[1], root)
	new_folder =  new_folder.lstrip('/')
	new_folder += 'wip/' 
	new_path_mdl = new_folder+ asset_name+'_mdl.ma' 
	new_path_rig = new_folder+ asset_name+'_rig.ma' 
	new_path_shd = new_folder+ asset_name+'_shd.ma' 
	answer = cerebro.gui.question_box('Correct path for ' + task.name() + ' ?', new_path_mdl)
	if not answer: return
	task_tag.set_value(new_path_mdl) # Writing the file tag with the path
	if os.path.exists(new_path_mdl):
		cerebro.gui.information_box('Warning - File already exists!', 'Already exists \n'+new_path_mdl)
# 		explorer_open(new_path)
		return
	
	cerebro.core.print_error ( 'Result:   YES')
	try: os.makedirs(new_folder)
	except: pass
	try:
		shutil.copy('z:/maya/default.ma', new_path_mdl)
		shutil.copy('z:/maya/default.ma', new_path_rig)
		shutil.copy('z:/maya/default.ma', new_path_shd)
		
		cerebro.gui.information_box('Success', 'OK')
		explorer_open(new_path_mdl)
		
	except:
		cerebro.gui.information_box('Error', 'Failed to create file!')
		

def export_sel_to_file():
	f=open('c:/selected_tasks.txt', 'wb')
	tasks = cerebro.core.selected_tasks()
	lines = []
	failed=[]
	for task in tasks:
		line = str (task.parent_url() )
		tokens = line.split('/')
		name = tokens[len(tokens)-2]
		line = 'S:'+line+'wip/'+name+'_rig.ma'
		
		
		
		if os.path.exists(line): 
			line = line +'\n'
			lines.append(bytes(line, 'UTF-8'))
		else: 
			if not line in failed:
				cerebro.core.print_error('FAILED: ' + line)
				failed.append(line)
	cerebro.core.print_error('FAILED: '+ str(len(failed)))
	lines = set(lines)
	lines = list(lines)
	f.writelines(lines)
# 		except:cerebro.core.print_error('Failed to write to file')
	f.close()
		

def find_children_recursive(task_id, db, all_kids=[]):
	id =task_id
# 	cerebro.core.print_error ( 'id='+str(id))
	time.sleep(0.05)
# 	subtasks = cerebro.core.task_children(id)
	subtasks = db.task_children(id)
	if subtasks:
		all_kids.extend(subtasks)
# 		cerebro.core.print_error ( 'ADDED subs num'+str(len(subtasks)) )
		for subtask in subtasks:
			subtask_id = subtask[pycerebro.dbtypes.TASK_DATA_ID]
			result = find_children_recursive(subtask_id, db, all_kids)
			all_kids.extend(result)
# 			cerebro.core.print_error ( 'ADDED result num'+str(len(result)) )
		return all_kids
	else: return [] 
			

def sync_asset_path_old():
	cerebro.core.print_error ( 'sync_asset_path ACTIVATED')
	db=db_init()
	tasks = cerebro.core.selected_tasks()
	cerebro.core.print_error ( repr(tasks[0].name()))
	all_subtasks=[]
# 	return
	for selected_task in tasks:
		task_id = selected_task.id()
	# 	subtasks = db.task_children(tasks[0].id())
	# 	subtasks = cerebro.core.task_children(tasks[0].id())
		subtasks = find_children_recursive(task_id, db, all_kids=[])
		all_subtasks.extend(subtasks)
		cerebro.core.print_error ( 'stage1 '+repr(subtasks))
	for subtask in all_subtasks:
		id = subtask[pycerebro.dbtypes.TASK_DATA_ID]
		task_name = subtask[pycerebro.dbtypes.TASK_DATA_NAME]
		task = cerebro.core.task(id)
		task_parent_id = task.parent_id()
		task_parent = cerebro.core.task(task_parent_id)
		task_parent_name = task_parent.name()
		cerebro.core.print_error ( 'SUBTASK '+task_name+' => '+task_parent_name)
	

def sync_asset_path():
# 	cerebro.core.notify_user('Эта задача начнется через 5 минут', None,  is_show_box=True)
	cerebro.core.print_error ( 'sync_asset_path ACTIVATED')
	db=db_init()
	tasks = cerebro.core.selected_tasks()
	cerebro.core.print_error ( repr(tasks[0].name()))
	failed_tasks=[]
	success_tasks={}
	wip_tasks=[]
	
	f=open('c:/failed_tasks.txt', 'w+')
	f2=open('c:/success_tasks.txt', 'w+')
	f3=open('c:/wip_tasks.txt', 'w+')
	
	for task in tasks:
		name = task.name()
		task_id = task.id() 
		task_parent_id = task.parent_id()
		task_parent = cerebro.core.task(task_parent_id)
		task_parent_name = task_parent.name()
		task_status = task.status()[1]
		
# 		cerebro.core.print_error (name+' => '+task_parent_name)
		
		messages = db.task_messages(task_id)
		if not messages: continue
		posted_time_list = []
		for message in messages:
			message_data_id =message[pycerebro.dbtypes.MESSAGE_DATA_ID  ]
			message_obj = cerebro.core.message(message_data_id)
			text = message_obj.text_as_plain()
			posted_time = message_obj.posted_time()
			if text.count('alienbrain://'):
				posted_time_list.append((text, posted_time))
			
		
		if posted_time_list:
			sorted_time_list = sorted(posted_time_list, key=itemgetter(1), reverse=1)
			text  = sorted_time_list[0][0]
			index_start = text.find('alienbrain://')
			index_end = text.find('.ma')
			if index_end==-1: index_end = text.find('.mb') 
			
			if index_start>-1 and index_end>-1: ## Here we get our GOOD tasks
				ab_path = text[index_start:index_end+3]
				tokens = ab_path.split('Assets')
				if not len(tokens)>1: continue
				old_file_path = 's:/BABA_YAGA/Assets'+tokens[1]
				filename = os.path.split(old_file_path)[1]
				
				tokens = task.parent_url().split('ASSETS')
				if not len(tokens)>1: continue
				if old_file_path.count('wip'): new_file_path = 's:/BABA_YAGA/Assets'+tokens[1]+'wip/'+filename
				else: new_file_path = 's:/BABA_YAGA/Assets'+tokens[1]+filename
				
				success_tasks[old_file_path]= [ab_path, task.parent_url()+name, new_file_path]
				cerebro.core.print_error (task_parent_name+name+', '+task_status)
				
# 			cerebro.core.print_error (ab_path)
# 			success_tasks.append(ab_path)
		else: 
			if task_status=='completed': failed_tasks.append(task)
			if not task_status=='completed': wip_tasks.append(task)
	
	for failed_task in failed_tasks:
		line = failed_task.parent_url()+failed_task.name()+'\n' 
		f.write(line)
		cerebro.core.print_error ('FAILED '+line)
	f.close()
	for failed_task in wip_tasks:
		line = failed_task.parent_url()+failed_task.name()+'\n' 
		f3.write(line)
		cerebro.core.print_error ('WIP '+line)
	f3.close()
	
	json.dump(success_tasks, f2)
# 	for s_task in success_tasks.iterkeys():
# 		line = s_task+'\n' 
# 		f2.write(line)
	f2.close()
# 		break
	
	
	

def change_link_for_cam():
	db=db_init()
	cerebro.core.print_error ( 'def change_link_for_cam')
	tasks = cerebro.core.selected_tasks()
	
	for task in tasks:
		task_id = task.id()
		connections = db.task_links(task_id)
		cerebro.core.print_error ( 'connections: '+repr(connections)) #Задача, к которой идет связь.
# 		
		conn_task_id = connections[0][4]
		link_id = connections[0][1]
		conn_task = cerebro.core.task(conn_task_id)
		cerebro.core.print_error ( 'connection TASK: '+repr(conn_task.name()))
		db.drop_link_tasks(link_id)
	
# class cerebro_obj():
# 	def __init__(self):
from_connection={'Anim_Library':['Setup'], 'Comp':['Render', 'FX'], 'Shading':['Texturing'],  'Anim_Library':['Setup'], 'Animation_test':['Setup'], 'Cloth_setup':['Modeling'], 'Hair-Fur':['Modeling'], 'Modeling':['Art'], 'Render':['Shading'], 'Setup':['Modeling']}
to_connection={'Art':['Modeling'], 'Modeling':['Cloth_setup', 'Setup', 'Texturing', 'Hair'], 'Setup':['Animation_test'], 'Hair-Fur':['Render']}

def make_preprod_links():
	db=db_init()
	tasks = cerebro.core.selected_tasks()
	for task in tasks:
		id = task.id()
		sub_tasks = db.task_children(id)
		for sub_task in sub_tasks:
			id = sub_task[pycerebro.dbtypes.TASK_DATA_ID]
			task_name = sub_task[pycerebro.dbtypes.TASK_DATA_NAME]
			
			try: from_conn = from_connection[task_name]
			except: from_conn =[]
			try: to_conn = to_connection[task_name]
			except: to_conn =[]
			
			for tmp_task in sub_tasks:
				tmp_id = tmp_task[pycerebro.dbtypes.TASK_DATA_ID]
				tmp_task_name = tmp_task[pycerebro.dbtypes.TASK_DATA_NAME]
 				
				if tmp_task_name in from_conn:
					try: db.set_link_tasks(tmp_id, id)
					except: cerebro.core.print_error ('could NOT set FROM CONNECTION from '+tmp_task_name+' to ' + task_name)
 
				if tmp_task_name in to_conn:
					try: db.set_link_tasks(id, tmp_id)
					except: cerebro.core.print_error ('could NOT set TO CONNECTION from '+task_name+' to ' + tmp_task_name)
				
			cerebro.core.print_error ( repr (id))
			
def analyze_this():
	db=db_init()
# 	task = cerebro.core.current_task()
	tasks = cerebro.core.selected_tasks()
	cerebro.core.print_error ( 'TASK: '+repr(tasks))
	all_subtasks=[]
	for task in tasks:
		id = task.id()
		cerebro.core.print_error ( 'id = task.id()')
		db.task_set_progress(id, None) # сброс индикатора, чтобы прогресс считался автоматически
# 		task.set_progress(3.0) # сброс индикатора, чтобы прогресс считался автоматически
		cerebro.core.print_error ( 'SET PROGRESS TO NONE : '+repr(task.name()))
##		sub_tasks = cerebro.core.task_children(id)
		cerebro.core.print_error ( 'BEFORE sub_tasks')
		sub_tasks = db.task_children(id)
		cerebro.core.print_error ( 'ANALAZY THIS' + repr(len(sub_tasks)))
		for sub_task in list(sub_tasks):
			cerebro.core.print_error ( 'BEFORE try')
			try: id = sub_task[pycerebro.dbtypes.TASK_DATA_ID]
			except: cerebro.core.print_error ( 'FAILED: '+repr(id))
			cerebro.core.print_error ( 'AFTER except')
			task = cerebro.core.task(id)
			custom.analyze_task(task)
			cerebro.core.print_error ( 'SUBTASK: '+repr(id))


def remove_menu():
	# Уберем всем пользователям меню Web conference из главного меню
	mainMenu = cerebro.actions.MainMenu() # Получили главное меню
	mainMenu.remove_menu('conference') # удалили меню Web conference

	# В контестном меню задачи запретим всем пользователям кроме пользователя с логином 'Администратор' вырезать задачи
	taskNavMenu = cerebro.actions.TaskNavigatorMenu() # получили контекстное меню задачи
	current_user = cerebro.core.user_profile() # получили профиль пользователя
	if current_user[cerebro.aclasses.Users.DATA_LOGIN] != 'Администратор': # проверяем пользователя
		if taskNavMenu.has_action('app.action.task.cut'): # проверяем существует ли такой пункт меню
			taskNavMenu.action('app.action.task.cut').set_visible(False) # скрываем меню
		if taskNavMenu.has_action('app.action.task.cut_referense'): # проверяем существует ли такой пункт меню
			taskNavMenu.action('app.action.task.cut_referense').set_visible(False) # скрываем меню

def set_task_to_status(task_id, status_name):
	in_progress_id=None
	task = cerebro.core.task(task_id)
	for status in cerebro.core.statuses().data():
		in_progress_id=status[0]
		name = status[1]
		if name==status_name:break
	if in_progress_id: task.set_status(in_progress_id); return True
	else: return False

def assign_me_to_task():
	# Activating the 'My Task context menu item'
	
	# getting the task, on which the item was activated
	task = cerebro.core.current_task()
	users = cerebro.core.users()

#----------------------------------------------------------
# 	dinput = cerebro.gui.InputDialog(cerebro.gui.InputDialog.TYPE_INT, 'Enter', 'Введите планируемое количество часов на задачу')
# 	dinput.set_range(0, 100)
# 	dinput.set_value(4)    
# 	res = dinput.execute()
# 	if res == True:
# # 	     print('Entered value:', dinput.value())	
# 	task.set_planned_time(float(8))
# 	else: return	 		

	
# 	start = task.start()
# 	cerebro.core.print_error('START DATE: ' + repr(start))
	
# 	datetime_now = datetime.datetime.utcnow()
# 	datetime_2000 = datetime.datetime(2000, 1, 1)
# 	timedelta = datetime_now - datetime_2000
# 	days = timedelta.total_seconds()/(24*60*60)     
# 	task.set_start(days)
#----------------------------------------------------------


	allocated = task.allocated()
	if not allocated: allocated=[]
	
	for user in allocated: task.remove_allocated(user[users.DATA_ID])
#                print user
	
	userId  = cerebro.core.user_profile()[users.DATA_ID]
	userName  = cerebro.core.user_profile()[users.DATA_FULL_NAME]
	
	
# 	print type(task)
	task.set_allocated(userId)
# 	cerebro.core.print_error ( repr(cerebro.core.statuses().data() ))
	tags = task.tags()
	in_progress_id=None
	for status in cerebro.core.statuses().data():
		in_progress_id=status[0]
		name = status[1]
		if name=='in progress':break
	if in_progress_id: task.set_status(in_progress_id)
# 		cerebro.core.print_error ( repr(status[1] ))
	# displaying a window with a message
	inf = 'Task '+task.name()+' is SUCCESSFULLY assigned to user: '+userName
# 	task.set_status(12)
# 	print user[0]
	cerebro.gui.information_box('Cerebro Python API', inf)	

def hello_user(): # Приветствие пользователя
	current_user = cerebro.core.user_profile() # получили профиль пользователя
	msg = 'Hello ' + current_user[cerebro.aclasses.Users.DATA_FULL_NAME] # сформировали сообщение
	print (msg)
	cerebro.core.print_error(msg)
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение

def hello_administrator(): # Приветствие администратора
	current_user = cerebro.core.user_profile() # получили профиль пользователя
	msg = 'Hello administrator' + current_user[cerebro.aclasses.Users.DATA_FULL_NAME] # сформировали сообщение
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение

def task_info(): # заглушка для действия с чекбоксом
	pass

def task_info_show(): # Показать информацию о сообщении
	task = cerebro.core.current_task() # Получили текущее сообщение

	# Получим состояние кнопки 'Информация о задаче(ID + Name)'
	taskMenu = cerebro.actions.TaskNavigatorMenu() # Получили контестное меню задачи
	chkAction = taskMenu.action('twin_plugin.examples.action.task_info')
# 	users = cerebro.core.users()
	cerebro.core.print_error ( repr(task.data() ))
	# Сформируем сообщение в зависимости от условия
	if chkAction.is_checked():
		msg = 'Имя задачи: ' + task.name() + ', ID задачи: ' + str(task.id()) # Сообщение при включенном пункте 'Информация о задаче(ID + Name)'
	else:
		msg = 'Имя задачи: ' + task.name() # Сообщение при выключенном пункте 'Информация о задаче(ID + Name)'
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение

def copy_task():
	global task_copy_from_ids
	tasks = cerebro.core.selected_tasks()
	task_copy_from_ids = [task.id() for task in tasks]
	cerebro.core.print_error ( str(task_copy_from_ids ))

def paste_task():
	global task_copy_from_ids
	db=db_init()
	tasks = cerebro.core.selected_tasks()
	for task in tasks:
# 		task = cerebro.core.current_task()
		task_copy_to_id = task.id()
		tup_list = []
		for task_copy_from_id in task_copy_from_ids:
			task_copy_from_name = cerebro.core.task(task_copy_from_id).name()
			tup_list.append((task_copy_from_id, task_copy_from_name))
		
		copied_ids = db.copy_tasks(task_copy_to_id, tup_list, flags=512|1|1024|64|4|8|16 ) 		 
		cerebro.core.print_error('Copied tasks'+str(copied_ids))
	
		copied_ids_sorted = []
		for task_copy_from_id in task_copy_from_ids:
			task_copy_from_name = cerebro.core.task(task_copy_from_id).name()
			for copied_id in copied_ids:
				 copied_id_name = cerebro.core.task(copied_id).name()
				 if task_copy_from_name == copied_id_name:
				 	copied_ids_sorted.append(copied_id)
	
		cerebro.core.print_error('Copied tasks NEW'+str(copied_ids_sorted))
	
		for task_copy_from_id, copied_id in zip(task_copy_from_ids, list(copied_ids_sorted)):
		
			task_copy_from_name = cerebro.core.task(task_copy_from_id).name()
			cerebro.core.print_error('task_copy_from_id '+str(task_copy_from_id))
			cerebro.core.print_error('task_copy_to_id '+str(task_copy_to_id))
			cerebro.core.print_error('task name '+task_copy_from_name)
	# 		copied_ids = db.copy_tasks(task_copy_to_id, [(task_copy_from_id, task_copy_from_name)])
	# 		cerebro.core.print_error('RESULT '+str(copied_ids))
			
			#retrive subscribed   select "interrestUsersTask"($1)  select "userSetTaskInterrest_a"($1,$2,$3)
			subscribed_ids = task_get_subscribed(task_copy_from_id, db)
		# 	cmd = 'select "interrestUsersTask"(' + str(task_copy_from_id) + ')'
		# 	result = db.execute(cmd)
		# 	subscribed_ids = [id[0] for id in result]
	# 		cerebro.core.print_error('Subscribed '+str(subscribed_ids))
			
			arg1 = [copied_id]
			arg2 = list(subscribed_ids)
		# 	arg2 = repr(result)
		# 	cmd = 'select "userSetTaskInterrest_a"(' + arg1 + ', ' + arg2 + ',1)'
		# 	cerebro.core.print_error('Cmd to subscribe '+cmd)
		
			#First un-subscr all from the task, then add necessary users
			
			task_unsubscribe_all(copied_id, db)
		
			result = db.execute('select "userSetTaskInterrest_a"(%s,%s,%s)', arg1, arg2, 1)
			cerebro.core.print_error('Subscribed! ')
		
# 		db.add_definition(copied_id, 'Automatic definition (init)')
# 		cerebro.core.print_error('Created automatic definition for task! ')
# 	result = db.execute(cmd)


def paste_task_custom(tasks_copy_to, task_copy_from_ids, suffix, db):
# 	global task_copy_from_ids
# 	db=db_init()
# 	tasks = cerebro.core.selected_tasks()
	cerebro.core.print_error('tRYING to execute paste custom')
	tasks = tasks_copy_to
	for task in tasks:
# 		task = cerebro.core.current_task()
		task_copy_to_id = task.id()
		tup_list = []
		for task_copy_from_id in task_copy_from_ids:
			task_copy_from_name = cerebro.core.task(task_copy_from_id).name() + suffix
			tup_list.append((task_copy_from_id, task_copy_from_name))
		
		copied_ids = db.copy_tasks(task_copy_to_id, tup_list, flags=512|1|1024|64|4|8|16 ) 		 
		cerebro.core.print_error('Copied tasks'+str(copied_ids) + str(type(copied_ids)))
	
		copied_ids_sorted = list(copied_ids)
# 		for task_copy_from_id in task_copy_from_ids:
# 			task_copy_from_name = cerebro.core.task(task_copy_from_id).name()
# 			for copied_id in copied_ids:
# 				 copied_id_name = cerebro.core.task(copied_id).name()
# 				 if task_copy_from_name == copied_id_name:
# 				 	copied_ids_sorted.append(copied_id)
	
		cerebro.core.print_error('Copied tasks NEW'+str(copied_ids_sorted))
	
		for task_copy_from_id, copied_id in zip(task_copy_from_ids, list(copied_ids_sorted)):
		
# 			task_copy_from_name = cerebro.core.task(task_copy_from_id).name()
# 			cerebro.core.print_error('task_copy_from_id '+str(task_copy_from_id))
# 			cerebro.core.print_error('task_copy_to_id '+str(task_copy_to_id))
# 			cerebro.core.print_error('task name '+task_copy_from_name)
	# 		copied_ids = db.copy_tasks(task_copy_to_id, [(task_copy_from_id, task_copy_from_name)])
	# 		cerebro.core.print_error('RESULT '+str(copied_ids))
			
			#retrive subscribed   select "interrestUsersTask"($1)  select "userSetTaskInterrest_a"($1,$2,$3)
			subscribed_ids = task_get_subscribed(task_copy_from_id, db)
		# 	cmd = 'select "interrestUsersTask"(' + str(task_copy_from_id) + ')'
		# 	result = db.execute(cmd)
		# 	subscribed_ids = [id[0] for id in result]
	# 		cerebro.core.print_error('Subscribed '+str(subscribed_ids))
			
			arg1 = [copied_id]
			arg2 = list(subscribed_ids)
		# 	arg2 = repr(result)
		# 	cmd = 'select "userSetTaskInterrest_a"(' + arg1 + ', ' + arg2 + ',1)'
		# 	cerebro.core.print_error('Cmd to subscribe '+cmd)
		
			#First un-subscr all from the task, then add necessary users
			
			task_unsubscribe_all(copied_id, db)
		
			result = db.execute('select "userSetTaskInterrest_a"(%s,%s,%s)', arg1, arg2, 1)
			cerebro.core.print_error('Subscribed! ')
		
# 		db.add_definition(copied_id, 'Automatic definition (init)')
# 		cerebro.core.print_error('Created automatic definition for task! ')
# 	result = db.execute(cmd)

	return copied_ids_sorted

def remove_all_assigned():
	db=db_init()
	tasks = cerebro.core.selected_tasks()
	task_copy_from_ids = [task.id() for task in tasks]
	for task_id in task_copy_from_ids:
		allocated = db.task_allocated(task_id)
		allocated_ids = [id_tuple[0] for id_tuple in allocated]
		cerebro.core.print_error('Got ALLOCATED users: '+ repr( allocated))
# 		result = db.execute('select "userSetTaskInterrest_a"(%s,%s,%s)', [], [], 1)
		for user_id in allocated_ids:
			db.task_remove_allocated(task_id, user_id)
			db.execute('select "userSetTaskInterrest_a"(%s,%s,%s)', [task_id], allocated_ids, 1)
		cerebro.core.print_error('CLEARED ASSIGNED! ')		
		


def task_get_subscribed(task_id, db):
	cmd = 'select "interrestUsersTask"(' + str(task_id) + ')'
	result = db.execute(cmd)	
	subscribed_ids = [id[0] for id in result]
	cerebro.core.print_error('Got subscribed users: '+ repr( subscribed_ids))
	return subscribed_ids
	
def task_unsubscribe_all(task_id, db):
	subscribed_ids = task_get_subscribed(task_id, db)
	arg2 = list(subscribed_ids)
	result = db.execute('select "userSetTaskInterrest_a"(%s,%s,%s)', [task_id], arg2, 0)	
	
	cerebro.core.print_error('Un-subscribed '+str(task_id))	

def message_text(): # Показать текст сообщения
	# Проверяем выбрано ли сообщение
	if cerebro.core.selected_messages():
		message = cerebro.core.selected_messages()[0] # Получили первое выбранное сообщение
		msg = 'Текст сообщения: \n' + message.text_as_plain()  # Сформировали сообщение
	else:
		msg = 'Не выбрано ни одного сообщения!'  # Сформировали сообщение
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение

def message_creator(): # показать ID сообщения
	# Проверяем выбрано ли сообщение
	if cerebro.core.selected_messages():
		message = cerebro.core.selected_messages()[0] # Получили первое выбранное сообщение
		msg = 'Автор сообщения: ' + message.data()[cerebro.aclasses.Message.DATA_CREATOR_NAME] # Сформировали сообщение
	else:
		msg = 'Не выбрано ни одного сообщения!'  # Сформировали сообщение
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение

def attach_size(): # Показать размер вложения
	# Проверяем выбрано ли вложение
	if cerebro.core.selected_attachments():
		attach = cerebro.core.selected_attachments()[0] # Получили первое выбранное вложение
		msg = 'Размер вложения: ' + str(attach.file_size())  # Сформировали сообщение
	else:
		msg = 'Не выбрано ни одного вложения!'  # Сформировали сообщение
	cerebro.gui.information_box('Cerebro Python API', msg) # показали сообщение
