# camara.py
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

URL_CAMARA = 'http://10.50.119.250:4747/video'

class HiloCamara(QThread):
    frame_listo = pyqtSignal(QImage)  # envía cada frame a la UI
    error       = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._activo = True

    def detener(self):
        self._activo = False

    def detectar_figuras(self, frame):
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges   = cv2.Canny(blurred, 50, 150)

        contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contorno in contornos:
            area = cv2.contourArea(contorno)
            if area < 1000:
                continue

            perimetro = cv2.arcLength(contorno, True)
            approx    = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)
            x, y, w, h = cv2.boundingRect(approx)
            cx, cy    = x + w // 2, y + h // 2

            figura = ""
            color  = (0, 255, 0)
            num_vertices = len(approx)

            if num_vertices == 3:
                figura = "Triangulo"
                color  = (0, 255, 255)

            elif num_vertices == 4:
                aspect_ratio = float(w) / h
                figura = "Cuadrado" if 0.85 <= aspect_ratio <= 1.15 else "Rectangulo"
                color  = (0, 0, 255)

            else:
                circularidad = (4 * np.pi * area) / (perimetro ** 2)
                if circularidad > 0.75:
                    figura = "Circulo"
                    color  = (255, 0, 0)

            if figura:
                cv2.drawContours(frame, [approx], -1, color, 2)
                cv2.putText(frame, figura, (cx - 40, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return frame

    def run(self):
        cap = cv2.VideoCapture(URL_CAMARA)
        if not cap.isOpened():
            self.error.emit("No se pudo conectar a la cámara")
            return

        try:
            while self._activo:
                ret, frame = cap.read()
                if not ret:
                    self.error.emit("Se perdió la conexión con la cámara")
                    break

                frame = cv2.flip(frame, 1)
                frame = self.detectar_figuras(frame)

                # Convertir frame de OpenCV (BGR) a QImage (RGB) para mostrarlo en Qt
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch  = frame_rgb.shape
                imagen     = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_listo.emit(imagen)

        finally:
            cap.release()