# main.py
import os
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "0"

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

from PyQt5 import QtGui, QtCore
from interfaz import Ui_MainWindow

from control import HiloControl, DELTA
from trazo import HiloTrazo
from dibujo import HiloDibujo
from camara import HiloCamara

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.hilo     = None
        self.hilo_ctrl = HiloControl()
        self.hilo_ctrl.error.connect(self.control_error)
        self.hilo_ctrl.start()

        self.hilo_trazo  = None
        self.figura_sel  = None

        self.ruta_gnc = None

        self.hilo_cam = None

        # ── Navegación del menú ──────────────────────────────────────
        self.ui.bt_control.clicked.connect(lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_control))
        self.ui.bt_camara.clicked.connect( lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_camara))
        self.ui.bt_dIbujo.clicked.connect( lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_dibujo))
        self.ui.bt_trazo.clicked.connect(  lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.p_trazo))

        # ── Botones de control direccional ───────────────────────────
        self.ui.pushButton.clicked.connect(  lambda: self.hilo_ctrl.mover("x", -DELTA))
        self.ui.pushButton_2.clicked.connect(lambda: self.hilo_ctrl.mover("x", +DELTA))
        self.ui.pushButton_4.clicked.connect(lambda: self.hilo_ctrl.mover("y", -DELTA))
        self.ui.pushButton_3.clicked.connect(lambda: self.hilo_ctrl.mover("y", +DELTA))
        self.ui.pushButton_5.clicked.connect(lambda: self.hilo_ctrl.mover("z", +DELTA))
        self.ui.pushButton_6.clicked.connect(lambda: self.hilo_ctrl.mover("z", -DELTA))
        self.ui.pushButton_7.clicked.connect(self.hilo_ctrl.ir_a_home)

        # Botones de figura
        self.ui.pushButton_8.clicked.connect(lambda: self.seleccionar_figura("cuadrado"))
        self.ui.pushButton_9.clicked.connect(lambda: self.seleccionar_figura("triangulo"))
        self.ui.pushButton_10.clicked.connect(lambda: self.seleccionar_figura("circulo"))

        # Botones de trazo
        self.ui.bt_iniciar_trazo.clicked.connect(self.conectar_robot_trazo)
        self.ui.bt_bajar_trazo.clicked.connect(self.bajar_lapiz_trazo)
        self.ui.bt_confirmar_trazo.clicked.connect(self.confirmar_trazo)

        # ── Página Dibujo ────────────────────────────────────────────
        self.ui.bt_cargar.clicked.connect(self.cargar_archivo)
        self.ui.bt_iniciar.clicked.connect(self.conectar_robot)
        self.ui.bt_bajar.clicked.connect(self.bajar_lapiz)
        self.ui.bt_confirmar.clicked.connect(self.confirmar_altura)

        # Activar/desactivar cámara al cambiar de página
        self.ui.bt_camara.clicked.connect(self.iniciar_camara)
        self.ui.bt_control.clicked.connect(self.detener_camara)
        self.ui.bt_dIbujo.clicked.connect(self.detener_camara)
        self.ui.bt_trazo.clicked.connect(self.detener_camara)


    def control_error(self, msg):
        QMessageBox.critical(self, "Error de control", f"Ocurrió un error:\n{msg}")

    
    # ── Trazo ─────────────────────────────────────────────────────────────
    def seleccionar_figura(self, figura):
        self.figura_sel = figura
        self.ui.lbl_trazo.setText(f"✔ {figura.capitalize()} seleccionado")
        self.ui.bt_iniciar_trazo.setEnabled(True)

    def conectar_robot_trazo(self):
        self.ui.bt_iniciar_trazo.setEnabled(False)
        self.ui.pushButton_8.setEnabled(False)
        self.ui.pushButton_9.setEnabled(False)
        self.ui.pushButton_10.setEnabled(False)
        self.ui.lbl_trazo.setText("⏳ Conectando robot...")

        self.hilo_trazo = HiloTrazo(self.figura_sel)
        self.hilo_trazo.listo_para_bajar.connect(self.mostrar_controles_trazo)
        self.hilo_trazo.terminado.connect(self.trazo_terminado)
        self.hilo_trazo.error.connect(self.trazo_error)
        self.hilo_trazo.start()

    def mostrar_controles_trazo(self):
        self.ui.bt_bajar_trazo.setEnabled(True)
        self.ui.bt_confirmar_trazo.setEnabled(True)
        self.ui.lbl_trazo.setText("⬇ Ajusta la altura del lápiz")

    def bajar_lapiz_trazo(self):
        if self.hilo_trazo:
            self.hilo_trazo.bajar_un_mm()

    def confirmar_trazo(self):
        if self.hilo_trazo:
            self.ui.bt_bajar_trazo.setEnabled(False)
            self.ui.bt_confirmar_trazo.setEnabled(False)
            self.ui.lbl_trazo.setText("⏳ Trazando figura...")
            self.hilo_trazo.confirmar_inicio()

    def trazo_terminado(self):
        self.ui.lbl_trazo.setText("✅ ¡Figura completada!")
        self.ui.pushButton_8.setEnabled(True)
        self.ui.pushButton_9.setEnabled(True)
        self.ui.pushButton_10.setEnabled(True)
        self.ui.bt_iniciar_trazo.setEnabled(True)

    def trazo_error(self, msg):
        self.ui.lbl_trazo.setText("❌ Error")
        self.ui.pushButton_8.setEnabled(True)
        self.ui.pushButton_9.setEnabled(True)
        self.ui.pushButton_10.setEnabled(True)
        self.ui.bt_iniciar_trazo.setEnabled(True)
        QMessageBox.critical(self, "Error de trazo", f"Ocurrió un error:\n{msg}")

    # ── Cargar archivo .gnc ──────────────────────────────────────────
    def cargar_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo G-code", "", "GNC Files (*.gnc *.ngc);;All Files (*)"
        )
        if ruta:
            self.ruta_gnc = ruta
            nombre = ruta.split("/")[-1]
            self.ui.lbl_archivo.setText(f"✔ {nombre}")
            self.ui.bt_iniciar.setEnabled(True)

    # ── Conectar robot y llevarlo a posición base ────────────────────
    def conectar_robot(self):
        self.ui.bt_iniciar.setEnabled(False)
        self.ui.bt_cargar.setEnabled(False)
        self.ui.lbl_archivo.setText("⏳ Conectando robot...")

        self.hilo = HiloDibujo(self.ruta_gnc)
        self.hilo.listo_para_bajar.connect(self.mostrar_controles_altura)
        self.hilo.terminado.connect(self.dibujo_terminado)
        self.hilo.error.connect(self.dibujo_error)
        self.hilo.start()

    # ── Se activan cuando el robot ya está en posición base ──────────
    def mostrar_controles_altura(self):
        self.ui.bt_bajar.setEnabled(True)
        self.ui.bt_confirmar.setEnabled(True)
        self.ui.lbl_archivo.setText("⬇ Ajusta la altura del lápiz")

    # ── Bajar el lápiz 1mm ───────────────────────────────────────────
    def bajar_lapiz(self):
        if self.hilo:
            self.hilo.bajar_un_mm()

    # ── Confirmar altura y empezar a dibujar ─────────────────────────
    def confirmar_altura(self):
        if self.hilo:
            self.ui.bt_bajar.setEnabled(False)
            self.ui.bt_confirmar.setEnabled(False)
            self.ui.lbl_archivo.setText("⏳ Dibujando...")
            self.hilo.confirmar_inicio()

    # ── Dibujo terminado ─────────────────────────────────────────────
    def dibujo_terminado(self):
        self.ui.lbl_archivo.setText("✅ ¡Dibujo completado!")
        self.ui.bt_cargar.setEnabled(True)
        self.ui.bt_iniciar.setEnabled(True)

    # ── Error del robot ──────────────────────────────────────────────
    def dibujo_error(self, msg):
        self.ui.lbl_archivo.setText("❌ Error")
        self.ui.bt_cargar.setEnabled(True)
        self.ui.bt_iniciar.setEnabled(True)
        QMessageBox.critical(self, "Error del robot", f"Ocurrió un error:\n{msg}")
    
    # ── Cámara ───────────────────────────────────────────────────────────
    def iniciar_camara(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.p_camara)
        if self.hilo_cam is None or not self.hilo_cam.isRunning():
            self.hilo_cam = HiloCamara()
            self.hilo_cam.frame_listo.connect(self.actualizar_frame)
            self.hilo_cam.error.connect(self.camara_error)
            self.hilo_cam.start()

    def detener_camara(self):
        if self.hilo_cam and self.hilo_cam.isRunning():
            self.hilo_cam.detener()
            self.hilo_cam.wait()
            self.hilo_cam = None

    def actualizar_frame(self, imagen):
        pixmap = QtGui.QPixmap.fromImage(imagen)
        self.ui.lbl_camara.setPixmap(
            pixmap.scaled(self.ui.lbl_camara.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation)
        )

    def camara_error(self, msg):
        self.ui.lbl_camara.setText(f"❌ {msg}")
    
    def closeEvent(self, event):
        self.detener_camara()
        self.hilo_ctrl.detener()
        self.hilo_ctrl.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())