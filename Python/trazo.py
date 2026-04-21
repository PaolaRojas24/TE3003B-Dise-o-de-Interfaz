# trazo.py
import warnings
warnings.filterwarnings("ignore")

import os
import sys
import math
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

IP     = "172.23.254.167"
BASE_X = 150
BASE_Y = 320
BASE_Z = 140
SPEED  = 50
LADO   = 50

class HiloTrazo(QThread):
    terminado        = pyqtSignal()
    error            = pyqtSignal(str)
    listo_para_bajar = pyqtSignal()

    def __init__(self, figura):
        super().__init__()
        self.figura  = figura  # "cuadrado", "triangulo" o "circulo"
        self.altura  = 1
        self._mutex  = QMutex()
        self._espera = QWaitCondition()
        self._bajar  = False
        self._iniciar = False

    def bajar_un_mm(self):
        self._mutex.lock()
        self._bajar = True
        self._espera.wakeAll()
        self._mutex.unlock()

    def confirmar_inicio(self):
        self._mutex.lock()
        self._iniciar = True
        self._espera.wakeAll()
        self._mutex.unlock()

    def _puntos_cuadrado(self):
        # 4 esquinas de un cuadrado de LADO mm centrado en BASE_X, BASE_Y
        mitad = LADO / 2
        return [
            (BASE_X - mitad, BASE_Y - mitad),
            (BASE_X + mitad, BASE_Y - mitad),
            (BASE_X + mitad, BASE_Y + mitad),
            (BASE_X - mitad, BASE_Y + mitad),
            (BASE_X - mitad, BASE_Y - mitad),  # cerrar figura
        ]

    def _puntos_triangulo(self):
        # Triángulo equilátero de LADO mm centrado en BASE_X, BASE_Y
        h = (math.sqrt(3) / 2) * LADO
        return [
            (BASE_X,            BASE_Y - (h * 2/3)),   # vértice superior
            (BASE_X + LADO / 2, BASE_Y + (h / 3)),     # vértice inferior derecho
            (BASE_X - LADO / 2, BASE_Y + (h / 3)),     # vértice inferior izquierdo
            (BASE_X,            BASE_Y - (h * 2/3)),   # cerrar figura
        ]

    def _dibujar_circulo(self, arm, z_dibujo):
        # Aproximar círculo con 36 puntos (cada 10°)
        radio = LADO / 2
        pasos = 36
        for i in range(pasos + 1):
            angulo = (2 * math.pi / pasos) * i
            x = BASE_X + radio * math.cos(angulo)
            y = BASE_Y + radio * math.sin(angulo)
            arm.set_position(x=x, y=y, z=z_dibujo,
                             roll=180, pitch=0, yaw=0,
                             speed=SPEED, wait=True)

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

            # Avisar que ya puede ajustar altura
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
                    break

            # ── Dibujar figura ───────────────────────────────────────
            z_dibujo = BASE_Z - self.altura

            if self.figura == "cuadrado":
                puntos = self._puntos_cuadrado()
                # Ir al primer punto con lápiz arriba
                arm.set_position(x=puntos[0][0], y=puntos[0][1], z=BASE_Z,
                                 roll=180, pitch=0, yaw=0, speed=SPEED, wait=True)
                # Bajar y trazar
                for x, y in puntos:
                    arm.set_position(x=x, y=y, z=z_dibujo,
                                     roll=180, pitch=0, yaw=0,
                                     speed=SPEED, wait=True)

            elif self.figura == "triangulo":
                puntos = self._puntos_triangulo()
                arm.set_position(x=puntos[0][0], y=puntos[0][1], z=BASE_Z,
                                 roll=180, pitch=0, yaw=0, speed=SPEED, wait=True)
                for x, y in puntos:
                    arm.set_position(x=x, y=y, z=z_dibujo,
                                     roll=180, pitch=0, yaw=0,
                                     speed=SPEED, wait=True)

            elif self.figura == "circulo":
                # Ir al punto de inicio del círculo con lápiz arriba
                arm.set_position(x=BASE_X + LADO/2, y=BASE_Y, z=BASE_Z,
                                 roll=180, pitch=0, yaw=0, speed=SPEED, wait=True)
                self._dibujar_circulo(arm, z_dibujo)

            # ── Finalización ─────────────────────────────────────────
            arm.set_position(x=BASE_X, y=BASE_Y, z=BASE_Z + 50,
                             roll=180, pitch=0, yaw=0, speed=100, wait=True)
            arm.move_gohome(wait=True)
            arm.disconnect()
            self.terminado.emit()

        except Exception as e:
            self.error.emit(str(e))