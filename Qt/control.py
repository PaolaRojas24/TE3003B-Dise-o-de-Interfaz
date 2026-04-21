# control.py
import warnings
warnings.filterwarnings("ignore")

import os
import sys
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

IP     = "172.23.254.167"
SPEED  = 30
MVACC  = 200
DELTA  = 5  # mm por clic

class HiloControl(QThread):
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._mutex   = QMutex()
        self._espera  = QWaitCondition()
        self._comando = None   # guarda el próximo movimiento
        self._activo  = True   # False = terminar el hilo

    # ── Llamados desde los botones en main.py ────────────────────────
    def mover(self, eje, delta):
        """eje: 'x' | 'y' | 'z'   delta: +DELTA o -DELTA"""
        self._mutex.lock()
        self._comando = (eje, delta)
        self._espera.wakeAll()
        self._mutex.unlock()

    def ir_a_home(self):
        self._mutex.lock()
        self._comando = ("home", 0)
        self._espera.wakeAll()
        self._mutex.unlock()

    def detener(self):
        self._mutex.lock()
        self._activo  = False
        self._comando = ("salir", 0)
        self._espera.wakeAll()
        self._mutex.unlock()

    # ── Hilo principal ───────────────────────────────────────────────
    def run(self):
        try:
            arm = XArmAPI(IP)
            arm.motion_enable(enable=True)
            arm.set_mode(0)
            arm.set_state(state=0)

            while self._activo:
                # Esperar hasta que llegue un comando
                self._mutex.lock()
                while self._comando is None and self._activo:
                    self._espera.wait(self._mutex)
                comando = self._comando
                self._comando = None
                self._mutex.unlock()

                if comando is None or comando[0] == "salir":
                    break

                if comando[0] == "home":
                    arm.reset(wait=True)
                    continue

                # Leer posición actual
                code, current = arm.get_position()
                if code != 0:
                    self.error.emit(f"Error leyendo posición: código {code}")
                    continue

                x, y, z, roll, pitch, yaw = current
                eje, delta = comando

                if   eje == "x": x += delta
                elif eje == "y": y += delta
                elif eje == "z": z += delta

                code = arm.set_position(
                    x=x, y=y, z=z,
                    roll=roll, pitch=pitch, yaw=yaw,
                    speed=SPEED, mvacc=MVACC,
                    wait=True
                )
                if code != 0:
                    self.error.emit(f"Error moviendo {eje}: código {code}")
                    arm.clean_error()
                    arm.clean_warn()

            arm.disconnect()

        except Exception as e:
            self.error.emit(str(e))