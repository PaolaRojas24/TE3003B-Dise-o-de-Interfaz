# camara.py
import os
import sys
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

sys.path.append(os.path.join(os.path.dirname(__file__),
                '../xArm-Python-SDK/example/wrapper/common'))

# ── Configuración ─────────────────────────────────────────────────────
CAM_URL   = 'http://10.50.88.149:4747/video'
ROBOT_IP  = "172.23.254.167"
SPEED     = 30
MVACC     = 200
Z_TRABAJO = 150

fx, fy         = 1078.65, 1077.06
cx_img, cy_img = 626.20, 253.81
h_cam          = 300.0
cy_horiz       = -392.4
dist = np.array([[ 7.31329515e-02,  8.23424300e-01, -1.44209467e-02,
                  -2.29809355e-03, -3.89945277e+00]])

R = np.array([[ 0,  0, -1],
              [ 1,  0,  0],
              [ 0, -1,  0]], dtype=float)
t = np.array([460.0 + 132, 320.0 - 161, 250.0])

T_BASE_CAM = np.eye(4)
T_BASE_CAM[:3, :3] = R
T_BASE_CAM[:3,  3] = t

FRAMES_REQUERIDOS = 5

# ── Detección de figuras ──────────────────────────────────────────────
def _detectar(frame, criterio):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)
    contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mejor, mayor_area = None, 0

    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < 1000:
            continue
        perimetro = cv2.arcLength(contorno, True)
        approx    = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)
        x, y, w, h = cv2.boundingRect(approx)
        resultado = criterio(approx, area, perimetro, w, h)
        if resultado and area > mayor_area:
            mayor_area = area
            mejor = {"figura": resultado[0], "color": resultado[1],
                     "cx": x + w // 2, "cy": y + h // 2, "contorno": approx}
    return mejor

def det_triangulo(frame):
    def criterio(approx, area, perim, w, h):
        if len(approx) == 3:
            return ("Triangulo", (0, 255, 255))
    return _detectar(frame, criterio)

def det_cuadrado(frame):
    def criterio(approx, area, perim, w, h):
        if len(approx) == 4:
            ar = float(w) / h
            nombre = "Cuadrado" if 0.85 <= ar <= 1.15 else "Rectangulo"
            return (nombre, (0, 0, 255))
    return _detectar(frame, criterio)

def det_circulo(frame):
    def criterio(approx, area, perim, w, h):
        if (4 * np.pi * area) / (perim ** 2) > 0.75:
            return ("Circulo", (255, 0, 0))
    return _detectar(frame, criterio)

def pixel_a_robot(px, py):
    if py <= cy_horiz:
        py = cy_horiz + 1
    z_cam = h_cam * fy / (py - cy_horiz)
    Xc = (px - cx_img) * z_cam / fx
    Yc = (py - cy_img) * z_cam / fy
    P  = T_BASE_CAM @ np.array([Xc, Yc, z_cam, 1.0])
    return P[:3]

# ── Hilo de video ─────────────────────────────────────────────────────
class HiloCamara(QThread):
    frame_listo = pyqtSignal(QImage)
    error       = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._activo = True

    def detener(self):
        self._activo = False

    def run(self):
        cap = cv2.VideoCapture(CAM_URL)
        if not cap.isOpened():
            self.error.emit("No se pudo conectar a la cámara")
            return
        try:
            while self._activo:
                ret, frame = cap.read()
                if not ret:
                    self.error.emit("Se perdió la conexión con la cámara")
                    break
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch  = frame_rgb.shape
                imagen    = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_listo.emit(imagen)
        finally:
            cap.release()

# ── Hilo de secuencia robot + visión ─────────────────────────────────
class HiloSecuencia(QThread):
    frame_listo      = pyqtSignal(QImage)   # frames con anotaciones
    estado_actualizado = pyqtSignal(str)    # texto de estado para la UI
    terminado        = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._activo = True

    def detener(self):
        self._activo = False

    def run(self):
        try:
            from xarm.wrapper import XArmAPI
            arm = XArmAPI(ROBOT_IP)
            arm.motion_enable(enable=True)
            arm.set_mode(0)
            arm.set_state(0)

            cap = cv2.VideoCapture(CAM_URL)
            if not cap.isOpened():
                self.error.emit("No se pudo conectar a la cámara")
                return

            SECUENCIA = [det_triangulo, det_cuadrado,  det_circulo]
            NOMBRES   = ["Triangulo",   "Cuadrado",    "Circulo"]
            idx = 0
            frames_conf = 0

            while self._activo and idx < len(SECUENCIA):
                ret, frame = cap.read()
                if not ret:
                    self.error.emit("Se perdió la conexión con la cámara")
                    break

                
                det   = SECUENCIA[idx](frame)

                if det:
                    cv2.drawContours(frame, [det["contorno"]], -1, det["color"], 2)
                    cv2.circle(frame, (det["cx"], det["cy"]), 6, (255, 255, 255), -1)
                    cv2.putText(frame, det["figura"], (det["cx"] - 40, det["cy"] - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, det["color"], 2)
                    frames_conf += 1
                else:
                    frames_conf = 0

                cv2.putText(frame, f"Buscando: {NOMBRES[idx]} ({idx+1}/{len(SECUENCIA)})",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Emitir frame anotado a la UI
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch  = frame_rgb.shape
                imagen    = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_listo.emit(imagen)

                # Mover robot cuando hay suficientes frames
                if frames_conf >= FRAMES_REQUERIDOS:
                    frames_conf = 0
                    pos = pixel_a_robot(det["cx"], det["cy"])
                    _, current = arm.get_position()
                    _, _, _, roll, pitch, yaw = current
                    self.estado_actualizado.emit(
                        f"⏳ Moviendo a {NOMBRES[idx]}: x={pos[0]:.1f}, y={pos[1]:.1f}")
                    arm.set_position(x=pos[0], y=pos[1], z=Z_TRABAJO,
                                     roll=roll, pitch=pitch, yaw=yaw,
                                     speed=SPEED, mvacc=MVACC, wait=True)
                    self.estado_actualizado.emit(f"✔ {NOMBRES[idx]} listo")
                    idx += 1

            cap.release()
            arm.disconnect()

            if idx >= len(SECUENCIA):
                self.estado_actualizado.emit("✅ Secuencia completa")
                self.terminado.emit()

        except Exception as e:
            self.error.emit(str(e))