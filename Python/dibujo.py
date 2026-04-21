# dibujo.py
import warnings
warnings.filterwarnings("ignore")

import os
import sys
import re
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

IP     = "172.23.254.167"
BASE_X = 150
BASE_Y = 320
BASE_Z = 140

class HiloDibujo(QThread):
    terminado        = pyqtSignal()
    error            = pyqtSignal(str)
    listo_para_bajar = pyqtSignal()  # <-- señal nueva

    def __init__(self, ruta_archivo):
        super().__init__()
        self.ruta_archivo = ruta_archivo
        self.altura       = 1
        self._mutex       = QMutex()
        self._espera      = QWaitCondition()
        self._bajar       = False
        self._iniciar     = False

    # Llamado desde bt_bajar en main.py
    def bajar_un_mm(self):
        self._mutex.lock()
        self._bajar = True
        self._espera.wakeAll()
        self._mutex.unlock()

    # Llamado desde bt_confirmar en main.py
    def confirmar_inicio(self):
        self._mutex.lock()
        self._iniciar = True
        self._espera.wakeAll()
        self._mutex.unlock()

    def run(self):
        try:
            arm = XArmAPI(IP)
            arm.motion_enable(enable=True)
            arm.set_mode(0)
            arm.set_state(state=0)
            arm.move_gohome(wait=True)

            # Posición inicial
            arm.set_position(x=BASE_X, y=BASE_Y, z=BASE_Z + 50,
                             roll=180, pitch=0, yaw=0, speed=100, wait=True)
            arm.set_position(x=BASE_X, y=BASE_Y, z=BASE_Z,
                             roll=180, pitch=0, yaw=0, speed=100, wait=True)

            # Avisar a la UI que el robot ya está listo para ajustar altura
            self.listo_para_bajar.emit()

            # ── Bucle de ajuste de altura ────────────────────────────
            while True:
                self._mutex.lock()
                while not self._bajar and not self._iniciar:
                    self._espera.wait(self._mutex)

                if self._bajar:
                    self._bajar = False
                    self._mutex.unlock()
                    arm.set_position(
                        x=BASE_X, y=BASE_Y, z=BASE_Z - self.altura,
                        roll=180, pitch=0, yaw=0, speed=100, wait=True
                    )
                    self.altura += 1

                elif self._iniciar:
                    self._iniciar = False
                    self._mutex.unlock()
                    break  # salir y empezar a dibujar

            # ── Leer G-code y dibujar ────────────────────────────────
            with open(self.ruta_archivo) as gcode:
                for line in gcode:
                    coord = re.findall(r'[XY].?\d+.\d+', line.strip())
                    if coord:
                        xx = float(coord[0].split('X')[1])
                        yy = float(coord[1].split('Y')[1])
                        arm.set_position(
                            x=BASE_X - xx, y=BASE_Y - yy, z=BASE_Z - self.altura,
                            roll=180, pitch=0, yaw=0, speed=100, wait=True
                        )

            # ── Finalización ─────────────────────────────────────────
            arm.set_position(x=BASE_X, y=BASE_Y, z=BASE_Z + 50,
                             roll=180, pitch=0, yaw=0, speed=100, wait=True)
            arm.move_gohome(wait=True)
            arm.disconnect()
            self.terminado.emit()

        except Exception as e:
            self.error.emit(str(e))