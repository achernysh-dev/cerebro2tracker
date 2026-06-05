import sys
print (sys.path)
sys.path.append("c:\\Program Files\\Cerebro\\py-site-packages") # Add Cerebro's Python site-packages to the path
import cerebro
from pycerebro import database
db = database.Database()
db.connect_from_cerebro_client()

db = cerebro.db.Db()
projects = db.execute('select "listProjects_01"(%s,%s)', False, True) # выполняем запрос на список проектов
print('Список проектов', projects) # печатаем результат
print (db)






