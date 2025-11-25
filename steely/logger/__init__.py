import multiprocessing
import os
import threading
from time import sleep
from datetime import datetime
from steely.design import UnicodeColors


def relative(path):
	return os.path.join(os.path.dirname(__file__), path)


class Logger:
	clean = False
	master_clean = False
	environment = None
	log_path = None

	def __init__(self, app_name: str, owner: str, destination: str = None, debug: bool = True, clean: bool = False, **kwargs):

		self.kwargs = kwargs

		if clean:
			self.master_clean = True

		if app_name is None:
			self.app_name_upper = 'YOUR-APP-NAME-GOES-HERE'
		else:
			self.app_name_upper = str(app_name).upper()

		self.path = destination
		self.debug = debug
		self.owner = owner

		if debug:
			self.environment = "debug"

	@staticmethod
	def _subprocess_log(logger, level: str, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, self_debug: bool = True, **kwargs):
		"""

		Args:
			level:
			message:
			app_name:
			clean:
			supress:
			**kwargs:

		Returns:
		"""

		def generate_log_path():
			# Initialize base directory path
			if logger.environment is not None and logger.path is not None:
				try:
					base_dir = f"{logger.path}_{logger.environment}"
				except TypeError:
					base_dir = os.path.join('.', f"log_{logger.environment}")
			else:
				base_dir = str(logger.path) if logger.path is not None else '.'

			# Ensure base_dir is treated as a directory
			try:
				os.makedirs(base_dir, exist_ok=True)
			except Exception:
				pass

			# Construct filename and full path
			filename = datetime.now().strftime('%d-%m-%Y') + ".log"
			full_path = os.path.join(base_dir, filename)

			return full_path

		if logger.clean:
			os.system('cls' if os.name == 'nt' else 'clear')
			if not logger.master_clean:
				logger.clean = False

		timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
		level = level.upper()
		owner = logger.owner.upper()
		correspondent_clr = UnicodeColors.reset
		_current_app = logger.app_name_upper

		if app_name is not None:
			_current_app = str(app_name).upper()

		try:
			del kwargs["suppress"]
		except: pass

		message_enclouser = timestamp + f" - [{_current_app}]" + f" [{owner}]" + ' ' + ' '.join(
			[f'[{str(item).upper()}]' for item in [*logger.kwargs.values()]]) + ' '.join(
			[f'[{str(item).upper()}]' for item in [*kwargs.values()]]) + f" [{level}]"

		content = f"\n{message_enclouser.replace('  ', ' ')}: {str(message)}"

		if logger.path is not None:
			with open(generate_log_path(), 'a+') as f:
				f.write(str(content))

		if level == 'INFO' or level == 'START':
			correspondent_clr = UnicodeColors.success_cyan
		elif level == 'WARNING' or level == 'ALERT':
			correspondent_clr = UnicodeColors.alert
		elif level == 'SUCCESS' or level == 'OK':
			correspondent_clr = UnicodeColors.success
		elif level in ['CRITICAL', 'ERROR', 'FAULT', 'FAIL', 'FATAL']:
			correspondent_clr = UnicodeColors.fail

		if not supress or debug or self_debug:
			print(correspondent_clr, content[1:], UnicodeColors.reset)
			if clean:
				logger.clean = True

		return content

	def log(self, level: str, message, app_name: str = None, clean: bool = False, supress: bool = False, debug: bool = True, **kwargs) -> bool:
		"""

		Args:
			level:
			message:
			app_name:
			clean:
			supress:
			**kwargs:

		Returns:

		"""
		thread = threading.Thread(target=self._subprocess_log, kwargs={
			"logger": self, "level": level, "message": message, "app_name": app_name, "clean": clean, "suppress": supress, "debug": debug, "self_debug": self.debug, **kwargs
		})
		thread.start()

		#self._subprocess_log(self, level, message, app_name=app_name, clean=clean, supress=supress, debug=debug, self_debug=self.debug, **kwargs)
		return True

	def __call__(self, *args, **kwargs):
		self.log(*args, **kwargs)