import subprocess
import shlex
from time import sleep

commands = 'pade start-runtime --config_file pade_config.json'
commands = shlex.split(commands)
p1 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(6.0)

commands = 'python demo.py'
commands = shlex.split(commands)
p2 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(60.0)

p1.terminate()
p2.terminate()
