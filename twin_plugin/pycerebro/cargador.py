# -*- coding: utf-8 -*-
"""
Access module to the Cargador file storage.
More on Cargador settings, see section:
":ref:`carga-advanced-params`"

.. rubric:: Classes

* :py:class:`pycerebro.cargador.Cargador`

"""

import os
import requests
import threading, socket, struct
from datetime import datetime, timedelta

from requests.utils import requote_uri
from .cclib import string_byte, string_unicode, PY3

try:
	import xmlrpc.client as xmlrpc
except:
	import xmlrpclib as xmlrpc

try:
	import httplib
except ImportError:
	import http.client as httplib


class Cargador(xmlrpc.ServerProxy): 

	__slots__ = ('host', 'http_port', 'proxy_list')

	"""
	Cargador class to access the Cargador file storage.
	"""		

	
	def __init__(self, storage, _rpc_port = None, _http_port = None, _proxy = None, timeout = 3):		

		if type(storage) is dict:
			self.set_storage(storage)			
		else:
			secure = False
			use_datetime = 0

			if _rpc_port and _rpc_port != 0:
				transport = TimeoutTransport(use_datetime, timeout, secure=secure)
				xmlrpc.ServerProxy.__init__(self, 'http://{0}:{1}'.format(storage, _rpc_port), transport)

			self.proxy_list = {}
			
			self.user = ""
			self.unid = 0
			self.host = storage
			self.http_port = _http_port
			self.rpc_port = _rpc_port
			self.local_port = 45430
			self.remote_port = 45431		
			self.key = None

		self.set_proxy(_proxy)


	def set_storage(self, storage):
		self.user = storage.get('user')		
		self.unid = storage.get('unid')
		self.host = storage.get('host')
		self.http_port = storage.get('http_port')
		self.rpc_port = storage.get('rpc_port')
		self.local_port = storage.get('local_port')
		self.remote_port = storage.get('remote_port')		
		self.key = storage.get('key')

	def storage(self):
		return {
			'user': self.user
			, 'unid': self.unid
			, 'host': self.host
			, 'http_port': self.http_port
			, 'rpc_port': self.rpc_port
			, 'local_port': self.local_port
			, 'remote_port': self.remote_port			
			, 'key': self.key
		}
	

	def set_proxy(self, _proxy):
		if _proxy is not None and len(_proxy) > 0:			
			if len(_proxy.split("://")) < 2:
				self.proxy_list = {"http": "http://" + _proxy, "https": "https://" + _proxy}
			else:
				self.proxy_list = {"http": _proxy, "https": _proxy}
		else:
			self.proxy_list = {}	

	def upload(self, file_path, storage_path):
		
		hash = None
		
		if not os.path.exists(file_path):
			raise Exception('{} file does not exists'.format(file_path))
		
		if not self.host or len(self.host) == 0:
			raise Exception('Host is not specified')
		
		if not self.http_port or self.http_port == 0:
			raise Exception('Http port is not specified')
		
		hash = self.__http_upload(self.host, self.http_port, -int(self.key) if self.key and (self.key != 0) else self.unid, file_path, storage_path)					

		if not hash:
			raise Exception('{} file upload failed'.format(file_path))
			
		return hash

	def download(self, hash, file_path):

		if not self.host or len(self.host) == 0:
			raise Exception('Host is not specified')
		
		if not self.http_port or self.http_port == 0:
			raise Exception('Http port is not specified')

		fpath = self.__http_download(self.host, self.http_port, hash, file_path)	

		return fpath
		
	def local_is_valid(self):
		res = True
		try:
			pth = self.local_path()
			res = pth and len(pth) > 0
		except Exception as err:			
			res = False
		return res
	
	def remote_is_valid(self):
		res = True
		try:
			self.remote_check_exists('0000000000000000000000000000000000000000000000000000000000000000')
		except Exception as err:			
			res = False
		return res

	def remote_check_exists(self, hash):
		if not self.remote_port or self.remote_port == 0:
			raise Exception('Remote port is not specified')
		
		query = self.__remote_check_exists(hash)
		return self.__request(self.host, self.remote_port, query, self.__recv_check_exists)

	def local_resolve(self, hash):
		if not self.local_port or self.local_port == 0:
			raise Exception('Local port is not specified')

		query = self.__local_resolve(hash, self.user)
		return self.__request(self.host, self.local_port, query, self.__recv_resolve)

	def local_path(self):
		if not self.local_port or self.local_port == 0:
			raise Exception('Local port is not specified')
		
		query = self.__local_path(self.user)
		return self.__request(self.host, self.local_port, query, self.__recv_path)
	

	def import_file(self, file_name, url):
		"""
		obsolette
		"""
		return self.upload(file_name, url)	

	def download_file(self, file_name, hash):
		"""
		obsolette
		"""
		return self.download(hash, file_name)
	

	def __http_upload(self, host, port, store_key, file_path, store_path):
		hash = None
		
		store_path = u'{0}{1}/{2}'.format(u'' if store_path.startswith('/') else u'/', store_path.rstrip('/'), os.path.basename(file_path))
		store_host = u'{0}:{1}'.format(host, port)
		content_length = '{0}'.format(os.stat(file_path).st_size)

		full_url = u'http://{0}{1}'.format(store_host, store_path)
		if '%' in full_url:
			full_url = full_url.replace('%', '_')
		if not PY3: full_url = string_byte(full_url)

		session = requests.Session()
		adapter = requests.adapters.HTTPAdapter(max_retries=5)
		session.mount('http://', adapter)		

		headers = {
			"User-Agent": "Python uploader",
			"Content-type": "application/octet-stream",
			"Accept": "text/plain",
			"host": host,
			"unid": str(store_key),
			"accept-encoding": "gzip, deflate",
			"content-length": content_length
		}

		with open(file_path, "rb") as fh:
			response = session.put(requote_uri(full_url)
									, headers=headers
									, proxies = self.proxy_list
									, data=fh.read()
									)
			if response.status_code != 201:
				raise Exception('Upload failed with code: ' + str(response.status_code) + '. reason: ' + response.reason)
			
			hash = response.content.decode('ascii').strip()

		return hash
	
	def __http_download(self, host, port, hash, file_path):
		
		host = '{0}:{1}'.format(host, port)
		headers = {
			"User-Agent": "Python downloader",
			"Content-type": "application/octet-stream",
			"Accept": "text/plain",
			"host": host,
			"accept-encoding": "gzip, deflate",
		}
		full_url = "http://{0}/file?hash={1}".format(host, hash)

		response = requests.get(requote_uri(full_url)
								, headers=headers
								, proxies = self.proxy_list
								, stream=True
								)
		if response.status_code == 200:
			with open(file_path, 'wb') as fh:
				for chunk in response.iter_content(1024):
					fh.write(chunk)
		else:
			raise Exception('Download failed with code: ' + str(response.status_code) + '. reason: ' + response.reason)

		return file_path
	
		
	def __proto_head(self, msg):
		head = struct.pack('II', int('EEEEFF01', 16), len(msg))
		return head

	def __proto_request(self, type):
		qtype = struct.pack('IIIIIIII', 1, type, 0, 0, 0, 0, 0, 0)
		return qtype

	def __proto_hash(self, hash):	
		qhash = struct.pack('IIII', 0, 0, 0, 0)
		for i in range(0, len(hash), 2):	
			octo = hash[i+0] + hash[i+1]
			qhash += struct.pack('B', int(octo, 16))

		return qhash

	def __proto_flags(self, flags):
		qflags = struct.pack('II', 1, 0)
		return qflags

	def __remote_proto_hello(self):
		hello = struct.pack('III', int('7fff0000', 16), ((3 << 8) | 232), 0)
		return hello

	def __local_proto_hello(self, uname):
		hello = hello = struct.pack('III', int('7fff0000', 16), ((8 << 8) | 1), 1)
		username = struct.pack('II', 0, 0)
		if uname and len(uname) > 0:
			bname = uname.encode('utf-8') + b'\0'			
			username = struct.pack('I{}s'.format(len(bname)), len(bname), bname)		

		return hello + username	
	
	def __remote_check_exists(self, hash):	
		msg = self.__remote_proto_hello() + self.__proto_request(2) + self.__proto_hash(hash)
		head = self.__proto_head(msg)
		return head + msg

	def __local_resolve(self, hash, uname):	
		msg = self.__local_proto_hello(uname) + self.__proto_request(1) + self.__proto_hash(hash)
		head = self.__proto_head(msg)
		return head + msg

	def __local_path(self, uname):	
		msg = self.__local_proto_hello(uname) + self.__proto_request(5) + self.__proto_flags(1)
		head = self.__proto_head(msg)
		return head + msg 

	def __recv_head(self, data):
		if not data:
			raise Exception('Read Failed')

		head = struct.unpack('II', data[0:8])	
		
		if len(head)!=2 or head[0]!=int('EEEEFF01', 16) or head[0]==-286327039:
			raise Exception('Protocol violated (1)')

		return head[1]

	def __recv_hello(self, msg):	
		hello_reply = struct.unpack('II', msg[0:8])
		if len(hello_reply) != 2:
			raise Exception('Handshaking failed (2)')

		mj_ver = (hello_reply[0] >> 8)
		if mj_ver < 3:
			raise Exception('Too old Cargador version')

	def __recv_query(self, msg, qtype):
		query_reply = struct.unpack('IIIII', msg[0:20])
		if len(query_reply) != 5:
			raise Exception('Query result missed (1)')

		if query_reply[0] != qtype:
			raise Exception('Query result has invalid type')

		if query_reply[3] != 0:
			raise Exception('Query failed with error: ' + query_reply[3])	
		
		res = msg[4*8:]	

		return res

	def __request(self, dns, port, query, fresult):
		result = None
		
		ip = None
		try:
			ip = socket.gethostbyname(dns)
		except Exception as err:		
			raise

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)
		try:
			sock.settimeout(3)
			sock.connect((ip, int(port)))
			sock.settimeout(None)			
			sock.send(query)			
			
			start = datetime.now()
			while (datetime.now() - start) < timedelta(seconds=3):
				data = sock.recv(4096)				
				while len(data) > 0: 					  
					msgsize = self.__recv_head(data)					
					if msgsize > 0:
						pt = struct.unpack('I', data[8:8+4])						
						if len(pt) != 1:
							raise Exception('Packet type missed')						
						msg = data[8+4:8+4+msgsize-4]												
						if pt[0] == int('7fff0101', 16):
							self.__recv_hello(msg)
						elif pt[0] == 101:							
							pass
						elif pt[0] == 102:								
							result = fresult(msg)													
							sock.close()	
							return result					

					data = data[8+msgsize:]
			
			sock.close()
		except Exception as err:			
			sock.close()
			raise

		return result

	def __recv_check_exists(self, msg):
		qres = self.__recv_query(msg, 2)
		res = struct.unpack('I3IB', qres)	
		if len(res) != 5:
			raise Exception('Query result missed (2)')
		
		return res[4] != 0

	def __recv_resolve(self, msg):
		qres = self.__recv_query(msg, 1)		
		res = struct.unpack('I{}s'.format(len(msg[32+28:]) - 4), msg[32+28:])
		return string_unicode(res[1]).strip('\0')

	def __recv_path(self, msg):
		qres = self.__recv_query(msg, 5)		
		res = struct.unpack('I{}s'.format(len(msg[32+12:]) - 4), msg[32+12:])
		return string_unicode(res[1]).strip('\0')



class TimeoutTransport(xmlrpc.Transport):

	def __init__(self, use_datetime=0, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, secure=False):
		xmlrpc.Transport.__init__(self, use_datetime)

		self.timeout = timeout
		self.secure = secure

	def make_connection(self, host):
		if self._connection and host == self._connection[0]:
			return self._connection[1]

		chost, self._extra_headers, x509 = self.get_host_info(host)
		if self.secure:
			self._connection = host, httplib.HTTPSConnection(
				chost, None, timeout=self.timeout, **(x509 or {})
			)
		else:
			self._connection = host, httplib.HTTPConnection(
				chost, timeout=self.timeout
			)

		return self._connection[1]
	
